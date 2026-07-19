"""Conservative fair-value estimate — triangulate three independent methods and
report a RANGE, not a false-precision point:

  • DCF            (compute_dcf — trailing FCF discounted)
  • analyst target (mean, with low/high spread)
  • earnings multiple (a conservative fair P/E × trailing EPS)

The margin of safety is always measured against the CONSERVATIVE (low) end.
``confident`` is False when we can't value it with conviction (no DCF and <2
methods) — which the agent treats as "outside the circle → skip", exactly as a
Munger-style investor would. Cached 24h per symbol (shared across all users)."""
from __future__ import annotations

import logging
import time

from app.services.market_data import compute_dcf, get_company_info, get_batch_quotes

logger = logging.getLogger(__name__)

FAIR_PE = 18.0            # a conservative market-ish earnings multiple (cross-check only)
HAIRCUT = 0.10            # shave the median FV to lean conservative (uncertainty buffer)
MAX_DISPERSION = 2.5      # if methods disagree by more than this (max/min), we don't trust the value
_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 24 * 3600


def _median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def fair_value(symbol: str, price: float | None = None) -> dict:
    """{symbol, current_price, low, base, high, conservative, margin_pct, methods[], confident}.
    margin_pct = (conservative_fv − price) / conservative_fv × 100 (positive = a margin of safety).

    conservative = median(estimates) × (1 − HAIRCUT); robust to a single bad method.
    confident is False with <2 methods OR when methods disagree too much (>MAX_DISPERSION) —
    an honest 'we can't value this → outside the circle'."""
    key = symbol.upper()
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _TTL and price is None:
        return hit[1]

    info = get_company_info(symbol) or {}
    dcf_fv = 0.0
    dcf_price = None
    try:
        d = compute_dcf(symbol) or {}
        dcf_fv = float(d.get("fair_value") or 0)
        dcf_price = float(d.get("current_price") or 0) or None
    except Exception as e:
        logger.debug("dcf failed for %s: %s", symbol, e)

    if price is None:
        q = get_batch_quotes([symbol])
        px = float(q[0]["price"]) if (q and q[0].get("price")) else (dcf_price or float(info.get("current_price") or 0) or None)
    else:
        px = price

    ests: list[tuple[str, float]] = []
    if dcf_fv > 0:
        ests.append(("dcf", dcf_fv))
    tm = info.get("target_mean_price")
    if tm:
        ests.append(("analyst", float(tm)))
    eps = info.get("eps_trailing") or info.get("eps_forward")
    if eps and float(eps) > 0:
        ests.append(("multiples", FAIR_PE * float(eps)))

    if not ests:
        out = {"symbol": key, "current_price": round(px, 2) if px else None, "low": None, "base": None,
               "high": None, "conservative": None, "margin_pct": None, "methods": [], "confident": False}
        if price is None:
            _CACHE[key] = (time.time(), out)
        return out

    methods = [m for m, _ in ests]
    vals = [v for _, v in ests]
    base = sum(vals) / len(vals)                            # balanced central estimate
    dispersion = (max(vals) / min(vals)) if min(vals) > 0 else 99.0
    conservative = base * (1 - HAIRCUT)                     # lean conservative
    low = min(vals + ([float(info["target_low_price"])] if info.get("target_low_price") else []))
    high = max(vals + ([float(info["target_high_price"])] if info.get("target_high_price") else []))
    confident = len(methods) >= 2 and dispersion <= MAX_DISPERSION
    margin = round((conservative - px) / conservative * 100, 1) if (conservative and px) else None

    out = {"symbol": key, "current_price": round(px, 2) if px else None,
           "low": round(low, 2), "base": round(base, 2), "high": round(high, 2),
           "conservative": round(conservative, 2), "margin_pct": margin,
           "methods": methods, "confident": confident, "dispersion": round(dispersion, 2)}
    if price is None:
        _CACHE[key] = (time.time(), out)
    return out


def mos_status(margin_pct: float | None, threshold: float, confident: bool) -> str:
    """Position/candidate standing vs the user's required margin of safety:
    unvaluable | margin (≥ threshold) | fair (0..threshold) | rich (< 0, over conservative FV)."""
    if not confident or margin_pct is None:
        return "unvaluable"
    if margin_pct >= threshold:
        return "margin"
    if margin_pct >= 0:
        return "fair"
    return "rich"


async def batch_fair_values(symbols: list[str]) -> dict[str, dict]:
    """FV for many symbols (each 24h-cached). Sync yfinance work off the loop."""
    import asyncio
    out: dict[str, dict] = {}
    for s in symbols:
        out[s] = await asyncio.to_thread(fair_value, s)
    return out
