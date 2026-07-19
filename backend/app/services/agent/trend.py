"""Falling-knife / price-trend guard — "don't catch a falling knife."

A deeply-undervalued stock is still a bad buy while it's actively falling: the
margin of safety means nothing if the price keeps making new lows. This scores a
name's recent PRICE ACTION (not its fundamentals) so the pipeline can skip
actively-declining names and the agent can check trend before buying.

    status: falling | basing | stable | rising
      falling  — actively declining, near recent lows, short MA sloping down  → WAIT
      basing   — was down but stabilizing (reclaimed the 20d MA / bounced off lows)
      stable   — range-bound, not trending down
      rising   — in an uptrend
    falling_knife = (status == "falling")

Pure price/technicals, computed from ~8 months of daily closes (yfinance), cached
6h. No fundamentals, no LLM — cheap enough to run on every buy candidate.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 6 * 3600

# thresholds (tunable)
STEEP_DROP_20D = -0.12     # a >12% fall over ~1 month is "steep"
NEAR_LOW = 0.03            # within 3% of the 20-day low = still making/near new lows
BOUNCE_OFF_LOW = 0.06      # 6%+ above the 20-day low = meaningful bounce
WEAK_60D = -0.10           # down >10% over ~3 months = a damaged chart


def _sma(xs: list[float], n: int) -> float | None:
    return sum(xs[-n:]) / n if len(xs) >= n else None


def _rsi(closes: list[float], n: int = 14) -> float | None:
    if len(closes) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(-n, 0):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    if losses == 0:
        return 100.0
    rs = (gains / n) / (losses / n)
    return round(100 - 100 / (1 + rs), 1)


def _ret(closes: list[float], k: int) -> float | None:
    return (closes[-1] / closes[-1 - k] - 1) if len(closes) > k else None


def _fetch_closes(symbol: str) -> list[float]:
    # Daily closes via the resilient provider chain (FMP EOD → yfinance fallback).
    from app.services import market_providers as mp
    return mp.get_history(symbol) or []


def assess_trend(symbol: str) -> dict:
    """Classify a ticker's recent price trend. Returns {status, falling_knife,
    trend_score(0-100, higher=healthier), summary, signals}. status='unknown' when
    there isn't enough price history (fail-open — never blocks on missing data)."""
    sym = (symbol or "").upper().strip()
    if not sym:
        return {"symbol": symbol, "status": "unknown", "falling_knife": False, "trend_score": None,
                "summary": "no symbol"}
    hit = _CACHE.get(sym)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]

    closes = _fetch_closes(sym)
    if len(closes) < 30:
        out = {"symbol": sym, "status": "unknown", "falling_knife": False, "trend_score": None,
               "summary": "insufficient price history"}
        _CACHE[sym] = (time.time(), out)
        return out

    px = closes[-1]
    sma20, sma50 = _sma(closes, 20), _sma(closes, 50)
    sma20_prev = (sum(closes[-25:-5]) / 20) if len(closes) >= 25 else None   # the 20d MA as of 5d ago
    ret5, ret20, ret60 = _ret(closes, 5), _ret(closes, 20), _ret(closes, 60)
    low20 = min(closes[-20:])
    high60 = max(closes[-60:]) if len(closes) >= 60 else max(closes)
    above_low20 = (px / low20 - 1) if low20 else 0.0
    drawdown = (px / high60 - 1) if high60 else 0.0
    rsi = _rsi(closes)

    sma20_falling = sma20 is not None and sma20_prev is not None and sma20 < sma20_prev
    downtrend = sma50 is not None and sma20 is not None and px < sma50 and sma20 < sma50
    steep = ret20 is not None and ret20 <= STEEP_DROP_20D
    near_lows = above_low20 <= NEAR_LOW
    reclaimed = sma20 is not None and px > sma20
    bounced = above_low20 >= BOUNCE_OFF_LOW

    if (downtrend or steep) and near_lows and sma20_falling and not reclaimed:
        status = "falling"
    elif (downtrend or (ret60 is not None and ret60 < WEAK_60D)) and (reclaimed or bounced) \
            and (ret5 is None or ret5 >= -0.01):
        status = "basing"
    elif reclaimed and (sma50 is None or px > sma50) and (ret20 is not None and ret20 >= 0.02):
        status = "rising"
    else:
        status = "stable"

    # trend_score 0-100 (higher = healthier price action) — for ranking/annotation
    score = 50.0
    if ret20 is not None:
        score += max(-25.0, min(25.0, ret20 * 120))
    if reclaimed:
        score += 10
    if downtrend:
        score -= 15
    if near_lows and sma20_falling:
        score -= 20
    score = int(max(0, min(100, round(score))))

    def pct(x):
        return f"{x * 100:+.0f}%" if x is not None else "n/a"

    summary = (f"{status} — {pct(drawdown)} from 60d high, {pct(ret20)} in 20d, "
               f"{above_low20 * 100:.0f}% above the 20d low"
               + (f", RSI {rsi}" if rsi is not None else ""))
    out = {"symbol": sym, "status": status, "falling_knife": status == "falling",
           "trend_score": score, "summary": summary,
           "signals": {"ret_20d": round(ret20, 3) if ret20 is not None else None,
                       "ret_60d": round(ret60, 3) if ret60 is not None else None,
                       "drawdown_60d": round(drawdown, 3), "above_20d_low": round(above_low20, 3),
                       "below_sma50": bool(downtrend), "sma20_falling": bool(sma20_falling), "rsi14": rsi}}
    _CACHE[sym] = (time.time(), out)
    return out
