

"""
Portfolio data endpoints.
Returns real Robinhood data when connected, empty responses otherwise.
"""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import PortfolioSummary, RiskData, QuotesResponse, WatchlistResponse
from app.database import get_db
from app.dependencies import get_optional_user
from app.services import robinhood
from app.services import robinhood_store as store, robinhood_portfolio as rp
from app.services import accounts as paper
from app.services.risk import compute_risk_metrics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_DISCONNECTED_SUMMARY = {
    "total_value": 0, "daily_change": 0, "daily_change_pct": 0,
    "total_gain": 0, "total_gain_pct": 0, "buying_power": 0,
    "risk_score": 0, "source": "disconnected",
}


@router.get("/summary", response_model=PortfolioSummary)
async def portfolio_summary(account: str | None = None, user=Depends(get_optional_user),
                            db: AsyncSession = Depends(get_db)):
    # Per-user read via the Robinhood agentic MCP (default account unless `account` set).
    if user:
        if paper.is_paper_number(account):
            return await paper.get_summary(db, account)
        token = await store.get_valid_access_token(db, user.id)
        if token:
            try:
                acct = await rp.resolve_account_number(token, account)
                if acct:
                    return await rp.get_summary(token, acct)
            except Exception as e:
                logger.warning("MCP summary failed: %s", e)
    return _DISCONNECTED_SUMMARY


@router.get("/positions")
async def portfolio_positions(account: str | None = None, user=Depends(get_optional_user),
                              db: AsyncSession = Depends(get_db)):
    if user:
        if paper.is_paper_number(account):
            return {"positions": await paper.get_positions(db, account),
                    "source": "paper", "account_number": account}
        token = await store.get_valid_access_token(db, user.id)
        if token:
            try:
                acct = await rp.resolve_account_number(token, account)
                if acct:
                    return {"positions": await rp.get_positions(token, acct),
                            "source": "robinhood", "account_number": acct}
            except Exception as e:
                logger.warning("MCP positions failed: %s", e)
    return {"positions": [], "source": "disconnected"}


@router.get("/history")
async def portfolio_history(days: int = 90, account: str | None = None,
                            user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if user:
        if paper.is_paper_number(account):
            return []  # paper equity curve: shown flat from the headline (no stored snapshots yet)
        token = await store.get_valid_access_token(db, user.id)
        if token:
            try:
                acct = await rp.resolve_account_number(token, account)
                if acct:
                    return await rp.get_history(token, acct, days)
            except Exception as e:
                logger.warning("MCP history failed: %s", e)
    return []


_DISCONNECTED_YTD = {"ytd_gain": 0, "ytd_gain_pct": 0, "baseline": "", "covered": 0,
                     "total_positions": 0, "source": "disconnected"}


@router.get("/ytd")
async def portfolio_ytd(request: Request, account: str | None = None):
    """Year-to-date return of current holdings (vs Jan-1 close). The all-time
    unrealized number is computed client-side from cost basis; this is the YTD
    complement the client can't compute without historical prices. DB is touched
    only briefly (token lookup) and released before the slow yfinance fetch."""
    import asyncio
    from app.services.auth import decode_token
    from app.database import async_session
    from app.services.pnl import compute_ytd

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return _DISCONNECTED_YTD
    payload = decode_token(auth[7:])
    uid = payload.get("sub") if payload else None
    if not uid:
        return _DISCONNECTED_YTD
    try:
        if paper.is_paper_number(account):
            async with async_session() as db:
                positions = await paper.get_positions(db, account)
            if not positions:
                return _DISCONNECTED_YTD
            return await asyncio.to_thread(compute_ytd, positions)
        async with async_session() as db:   # short scope — released before compute
            token = await store.get_valid_access_token(db, uid)
        if not token:
            return _DISCONNECTED_YTD
        acct = await rp.resolve_account_number(token, account)
        positions = await rp.get_positions(token, acct)
        if not positions:
            return _DISCONNECTED_YTD
        return await asyncio.to_thread(compute_ytd, positions)
    except Exception as e:
        logger.warning("MCP ytd failed: %s", e)
        return _DISCONNECTED_YTD


_DISCONNECTED_RISK = {
    "score": 0, "daily_var_95": 0, "monthly_cvar_95": 0, "risk_budget_used": 0,
    "portfolio_volatility": 0, "max_drawdown": 0, "drawdown_series": [],
    "sector_weights": [], "concentration": {"hhi": 0, "top5_pct": 0},
    "factors": [], "stress_tests": [], "correlation_alerts": [], "source": "disconnected",
}


@router.get("/risk", response_model=RiskData)
async def risk_data(request: Request, account: str | None = None):
    """Risk via the agentic MCP. The DB is only touched briefly (token lookup) and
    released BEFORE the slow MCP+compute work, so the connection isn't held idle."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from app.services.auth import decode_token
    from app.database import async_session

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return _DISCONNECTED_RISK
    payload = decode_token(auth[7:])
    uid = payload.get("sub") if payload else None
    if not uid:
        return _DISCONNECTED_RISK
    try:
        from app.services.risk import _get_cached
        if paper.is_paper_number(account):
            cached = _get_cached(f"risk:{account}")
            if cached is not None:
                return cached
            async with async_session() as db:
                positions = await paper.get_positions(db, account)
            if not positions:
                return _DISCONNECTED_RISK
            # No Robinhood token for paper — compute_risk_metrics falls back to
            # its yfinance price matrix when historicals is None.
            return await asyncio.to_thread(compute_risk_metrics, positions, None, f"risk:{account}")
        async with async_session() as db:   # short scope — released before compute
            token = await store.get_valid_access_token(db, uid)
        if not token:
            return _DISCONNECTED_RISK
        acct = await rp.resolve_account_number(token, account)
        # Warm-cache fast path: the risk compute is cached per account (see
        # RISK_CACHE_TTL). On a hit, return it WITHOUT the slow positions +
        # historicals fetch — this is what makes Risk Center feel instant once the
        # dashboard's background prefetch has warmed it.
        from app.services.risk import _get_cached
        cached = _get_cached(f"risk:{acct}")
        if cached is not None:
            return cached
        positions = await rp.get_positions(token, acct)
        if not positions:
            return _DISCONNECTED_RISK
        top = sorted(positions, key=lambda p: p.get("equity", 0), reverse=True)[:25]
        start = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hist = await rp.fetch_historicals(token, [p["symbol"] for p in top] + ["SPY"], "day", start)
        # Risk engine is sync + heavy (numpy + cached yfinance) → off the loop.
        return await asyncio.to_thread(compute_risk_metrics, positions, hist, f"risk:{acct}")
    except Exception as e:
        logger.warning("MCP risk failed: %s", e)
        return _DISCONNECTED_RISK


@router.get("/quotes", response_model=QuotesResponse)
def live_quotes(symbols: str | None = None):
    """Batch quotes via yfinance (60s cache). Accepts ?symbols=AAPL,GOOGL or auto-detects from portfolio."""
    from app.services.market_data import get_batch_quotes

    # Gather symbols: from query param, or from Robinhood positions + watchlist
    sym_set: set[str] = set()
    if symbols:
        sym_set = {s.strip().upper() for s in symbols.split(",") if s.strip()}
    elif robinhood.is_connected():
        positions = robinhood.get_positions()
        for p in positions:
            sym_set.add(p["symbol"])
        watchlist_items = robinhood.get_watchlist()
        for w in watchlist_items:
            sym_set.add(w["symbol"])

    if not sym_set:
        return {"quotes": [], "source": "disconnected"}

    quotes = get_batch_quotes(list(sym_set))
    return {"quotes": quotes, "source": "yfinance"}


@router.get("/watchlist", response_model=WatchlistResponse)
def watchlist():
    if robinhood.is_connected():
        live = robinhood.get_watchlist()
        if live:
            return {"items": live, "source": "robinhood"}
    return {"items": [], "source": "disconnected"}
