


"""
Market macro indicator endpoints.
"""

from fastapi import APIRouter

from app.services.market_macro import compute_real_earnings_yield
from app.services import market_hours

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/status")
def market_status():
    """Current US-equities market status — holiday- and half-day-aware. Cheap
    (pure computation), so the UI can poll it freely."""
    return market_hours.status()


@router.get("/real-earnings-yield")
def real_earnings_yield():
    """Get S&P 500 Real Earnings Yield from 1965 to today.
    Includes historical data, current snapshot, 1-month forecast, and stats.
    Cached for 1 hour on the server.
    """
    return compute_real_earnings_yield()
