"""Portfolio P/L breakdowns beyond the all-time unrealized number the client
computes from cost basis.

YTD return of *current* holdings. The subtle part is the baseline: for a position
held since before this year the baseline is its Jan-1 close (measures this-year
price move); for a position opened *this* year the baseline is what you actually
paid (avg cost) — otherwise you'd be charged the drop from January on shares you
never owned then, which is badly wrong for anyone who bought dips or opened new
positions mid-year.

The Robinhood agentic MCP exposes no lot dates or order history, so we infer
"held since before this year" as: avg cost is below the stock's *entire* price
range this year (you paid less than any price in the range → you must have bought
earlier). Prices are split/dividend adjusted (yfinance auto_adjust) and cached.

Note this is a simple cumulative return, NOT Robinhood's time-weighted figure —
we can't match that without cash-flow dates, and it ignores idle-cash drag.
"""
from __future__ import annotations

import datetime as dt
import logging
import time

logger = logging.getLogger(__name__)

# f"{year}:{SYMBOL}" -> (fetched_at, jan1_close, year_low)
_PRICE_CACHE: dict[str, tuple[float, float, float]] = {}
_TTL = 12 * 3600  # refresh the year-low periodically; jan1 never changes


def _ytd_prices(symbols: list[str], year: int) -> dict[str, tuple[float, float]]:
    """{symbol: (jan1_close, year_low)} for the current year."""
    now = time.time()
    need = sorted({s for s in symbols
                   if now - _PRICE_CACHE.get(f"{year}:{s}", (0.0, 0.0, 0.0))[0] > _TTL})
    if need:
        import yfinance as yf
        try:
            df = yf.download(need, start=f"{year}-01-01", progress=False,
                             auto_adjust=True, threads=True)
            close, low = df["Close"], df["Low"]
            for s in need:
                try:
                    cser = (close[s] if len(need) > 1 else close).dropna()
                    lser = (low[s] if len(need) > 1 else low).dropna()
                    if len(cser):
                        ylow = float(lser.min()) if len(lser) else float(cser.min())
                        _PRICE_CACHE[f"{year}:{s}"] = (now, float(cser.iloc[0]), ylow)
                except Exception:
                    continue
        except Exception:
            logger.warning("YTD price fetch failed", exc_info=True)
    return {s: _PRICE_CACHE[f"{year}:{s}"][1:] for s in symbols if f"{year}:{s}" in _PRICE_CACHE}


def compute_ytd(positions: list[dict]) -> dict:
    """positions: get_positions() output (symbol, shares, avg_cost, current_price)."""
    year = dt.datetime.now().year
    symbols = [p["symbol"] for p in positions if p.get("symbol")]
    px = _ytd_prices(symbols, year)

    base = cur = 0.0
    covered = held_prior = 0
    for p in positions:
        info = px.get(p.get("symbol"))
        shares = p.get("shares") or 0
        if not info or not shares:
            continue
        jan1, year_low = info
        cost = p.get("avg_cost") or 0.0
        # Paid less than any price this year → the lot predates this year.
        prior_year = cost > 0 and cost < year_low * 0.98
        baseline = jan1 if prior_year else (cost or jan1)
        base += shares * baseline
        cur += shares * (p.get("current_price") or 0)
        covered += 1
        held_prior += 1 if prior_year else 0

    gain = cur - base
    return {
        "ytd_gain": round(gain, 2),
        "ytd_gain_pct": round(gain / base * 100, 2) if base > 0 else 0.0,
        "baseline": f"Jan 1, {year}",
        "covered": covered,
        "total_positions": len(symbols),
        "held_since_prior_year": held_prior,
        "time_weighted": False,  # simple cumulative return, not Robinhood's TWR
        "source": "robinhood" if covered else "disconnected",
    }
