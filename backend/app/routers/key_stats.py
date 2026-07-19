"""Per-stock key statistics + insights — a better take on Yahoo's key-statistics."""
import asyncio

from fastapi import APIRouter

from app.services.key_stats import build_key_stats

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/{ticker}/key-stats")
async def key_stats(ticker: str):
    """Rich fundamentals + composite scores + insights for a ticker.

    Ticker is the ONLY input — the server fetches a fresh live price itself each
    call (yfinance fast_info), so analysis never uses a lagged client quote.
    Fundamentals are cached server-side (12h); the live price overlays each call.
    """
    return await asyncio.to_thread(build_key_stats, ticker)


@router.get("/{ticker}/peers")
async def peers(ticker: str):
    """How `ticker` ranks against the top names in its industry — size, growth,
    profitability, valuation. Peers + metrics cached server-side."""
    from app.services.sector_compare import get_sector_comparison
    return await asyncio.to_thread(get_sector_comparison, ticker)
