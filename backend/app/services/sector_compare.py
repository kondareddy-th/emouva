"""Sector/industry peer comparison — how a stock stacks up against the top names
in its industry on size, growth, profitability, and valuation.

Peer set comes from yfinance's Industry.top_companies (by market weight); each
peer's headline metrics come from .info. Everything is cached (peers + metrics +
the computed comparison) since it moves slowly; the heavy fetch runs once per
ticker per ~12h and off the event loop.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_PEERS_CACHE: dict[str, tuple[float, list[str]]] = {}
_METRICS_CACHE: dict[str, tuple[float, dict]] = {}
_CMP_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 12 * 3600
_PEERS_TTL = 24 * 3600

# (key, label, format, higher_is_better)
_METRICS = [
    ("market_cap", "Market Cap", "money", True),
    ("revenue", "Revenue (TTM)", "money", True),
    ("rev_growth", "Rev Growth", "pct", True),
    ("gross_margin", "Gross Margin", "pct", True),
    ("net_margin", "Net Margin", "pct", True),
    ("roe", "ROE", "pct", True),
    ("pe", "P/E", "x", False),  # lower is better
]


def _num(x):
    try:
        import math
        v = float(x)
        return None if math.isnan(v) else v
    except (TypeError, ValueError):
        return None


def _peer_tickers(industry_key: str | None, sector_key: str | None) -> list[str]:
    cache_id = industry_key or sector_key or ""
    hit = _PEERS_CACHE.get(cache_id)
    if hit and time.time() - hit[0] < _PEERS_TTL:
        return hit[1]
    import yfinance as yf
    tickers: list[str] = []
    for getter, key in ((yf.Industry, industry_key), (yf.Sector, sector_key)):
        if tickers or not key:
            continue
        try:
            tc = getter(key).top_companies
            tickers = [str(s) for s in list(tc.index)[:10]]
        except Exception:
            tickers = []
    _PEERS_CACHE[cache_id] = (time.time(), tickers)
    return tickers


def _peer_metrics(ticker: str) -> dict:
    hit = _METRICS_CACHE.get(ticker)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    import yfinance as yf
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}
    m = {
        "symbol": ticker,
        "name": info.get("shortName") or info.get("longName") or ticker,
        "market_cap": _num(info.get("marketCap")),
        "revenue": _num(info.get("totalRevenue")),
        "rev_growth": _num(info.get("revenueGrowth")),
        "gross_margin": _num(info.get("grossMargins")),
        "net_margin": _num(info.get("profitMargins")),
        "roe": _num(info.get("returnOnEquity")),
        "pe": _num(info.get("trailingPE")),
    }
    _METRICS_CACHE[ticker] = (time.time(), m)
    return m


def get_sector_comparison(ticker: str) -> dict:
    ticker = ticker.upper()
    hit = _CMP_CACHE.get(ticker)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]

    # Reuse the key-stats raw cache for the target's industry/sector keys.
    try:
        from app.services.key_stats import _fetch_raw
        info = _fetch_raw(ticker)["info"]
    except Exception:
        info = {}

    peers_t = _peer_tickers(info.get("industryKey"), info.get("sectorKey"))
    if ticker not in peers_t:
        peers_t = [ticker] + peers_t
    peers_t = peers_t[:8]
    peers = [_peer_metrics(t) for t in peers_t]

    ranks: dict[str, dict] = {}
    for key, label, fmt, higher in _METRICS:
        vals = [(p["symbol"], p[key]) for p in peers if p.get(key) is not None]
        if len(vals) < 2:
            continue
        ordered = sorted(vals, key=lambda kv: kv[1], reverse=higher)
        syms = [s for s, _ in ordered]
        if ticker not in syms:
            continue
        rank = syms.index(ticker) + 1
        n = len(syms)
        sorted_vals = sorted(v for _, v in vals)
        median = sorted_vals[len(sorted_vals) // 2]
        ranks[key] = {
            "rank": rank, "of": n,
            "percentile": round((n - rank) / (n - 1) * 100) if n > 1 else 50,
            "median": median, "label": label, "fmt": fmt,
        }

    result = {
        "symbol": ticker,
        "peer_group": info.get("industry") or info.get("sector") or "Peers",
        "metrics": [{"key": k, "label": l, "fmt": f, "higher_better": h} for k, l, f, h in _METRICS],
        "peers": peers,
        "ranks": ranks,
        "source": "yfinance",
    }
    _CMP_CACHE[ticker] = (time.time(), result)
    return result
