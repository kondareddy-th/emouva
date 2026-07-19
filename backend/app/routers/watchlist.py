"""
Watchlist CRUD — persistent, DB-backed watchlist for authenticated users.

Adds: ticker SEARCH (FMP, US-listed), and on-add BACKGROUND population of FMP metrics +
last-30-days news (stored on Watchlist.meta) so the detail view is instant when the user
opens an item. The detail also drives the "Run research" button (the /api/analysis flow).
"""
import asyncio
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db, async_session
from app.dependencies import get_current_user
from app.models.db import User, Watchlist

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# curated FMP fundamentals surfaced in the watchlist detail view
_METRIC_KEYS = [
    "name", "sector", "industry", "market_cap", "pe_ratio", "forward_pe", "price_to_book",
    "price_to_sales", "profit_margins", "operating_margins", "gross_margins", "return_on_equity",
    "return_on_assets", "revenue_growth", "earnings_growth", "free_cash_flow", "debt_to_equity",
    "current_ratio", "dividend_yield", "beta", "fifty_two_week_high", "fifty_two_week_low",
    "target_mean_price", "target_low_price", "target_high_price",
    "forward_eps_est", "forward_revenue_est", "grade_trend",
]


class WatchlistAdd(BaseModel):
    symbol: str
    name: str = ""
    thesis: str = ""
    fair_value: dict | None = None
    last_price: float | None = None


class WatchlistOut(BaseModel):
    symbol: str
    name: str
    thesis: str
    fair_value: dict | None
    last_price: float | None
    last_analyzed_at: str | None
    added_at: str
    meta: dict | None = None   # {metrics, news, populated_at} — populated in the background


def _out(r: Watchlist) -> WatchlistOut:
    return WatchlistOut(
        symbol=r.symbol, name=r.name, thesis=r.thesis, fair_value=r.fair_value,
        last_price=r.last_price,
        last_analyzed_at=r.last_analyzed_at.isoformat() if r.last_analyzed_at else None,
        added_at=r.added_at.isoformat(), meta=r.meta,
    )


# ── background enrichment ────────────────────────────────────────────────────
def _metrics(symbol: str) -> dict:
    """Curated FMP fundamentals + a live price (blocking; run in a thread)."""
    from app.services.market_data import get_company_info, get_batch_quotes
    info = get_company_info(symbol) or {}
    q = get_batch_quotes([symbol])
    price = (q[0].get("price") if q else None) or info.get("current_price")
    m = {k: info.get(k) for k in _METRIC_KEYS}
    m["price"] = price
    return m


def _news_30d(symbol: str) -> list:
    """Up to 15 headlines from the last 30 days (FMP)."""
    from app.services import market_providers as mp
    cutoff = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    out = []
    for a in (mp.fmp_news(symbol, 25) or []):
        d = (a.get("publishedDate") or "")[:10]
        if d and d < cutoff:
            continue
        out.append({"title": a.get("title"), "site": a.get("site"),
                    "date": (a.get("publishedDate") or "")[:16], "url": a.get("url")})
        if len(out) >= 15:
            break
    return out


async def _populate(user_id, symbol: str) -> None:
    """Fetch metrics + 30d news and store on the row's meta. Own session (background-safe)."""
    try:
        metrics = await asyncio.to_thread(_metrics, symbol)
        news = await asyncio.to_thread(_news_30d, symbol)
    except Exception:  # noqa: BLE001
        logger.exception("watchlist populate failed for %s", symbol)
        return
    async with async_session() as db:
        row = (await db.execute(select(Watchlist).where(
            Watchlist.user_id == user_id, Watchlist.symbol == symbol))).scalar_one_or_none()
        if not row:
            return
        row.meta = {"metrics": metrics, "news": news, "populated_at": datetime.utcnow().isoformat()}
        if metrics.get("price") is not None:
            row.last_price = metrics["price"]
        if not row.name and metrics.get("name"):
            row.name = metrics["name"]
        await db.commit()


# ── endpoints ────────────────────────────────────────────────────────────────
# NOTE: /search MUST be declared before /{symbol}, else "search" is captured as a symbol.
@router.get("/search")
async def search_stocks(q: str, user: User = Depends(get_current_user)) -> list[dict]:
    """Ticker/company search (US-listed, Robinhood-tradeable) for the add box."""
    if not q or len(q.strip()) < 1:
        return []
    from app.services import market_providers as mp
    return await asyncio.to_thread(mp.search_symbols, q, 10)


@router.get("")
async def list_watchlist(user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)) -> list[WatchlistOut]:
    rows = (await db.execute(select(Watchlist).where(Watchlist.user_id == user.id)
                             .order_by(Watchlist.added_at.desc()))).scalars().all()
    return [_out(r) for r in rows]


@router.get("/{symbol}")
async def watchlist_detail(symbol: str, user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)) -> WatchlistOut:
    sym = symbol.upper().strip()
    row = (await db.execute(select(Watchlist).where(
        Watchlist.user_id == user.id, Watchlist.symbol == sym))).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Symbol not in watchlist")
    if not row.meta:   # background hasn't landed yet (or a stale row) → populate on-demand
        await _populate(user.id, sym)
        row = (await db.execute(select(Watchlist).where(
            Watchlist.user_id == user.id, Watchlist.symbol == sym))).scalar_one_or_none()
    return _out(row)


@router.post("", status_code=201)
async def add_to_watchlist(body: WatchlistAdd, background_tasks: BackgroundTasks,
                           user: User = Depends(get_current_user),
                           db: AsyncSession = Depends(get_db)) -> WatchlistOut:
    symbol = body.symbol.upper().strip()
    if not symbol:
        raise HTTPException(400, "Symbol is required")

    existing = (await db.execute(select(Watchlist).where(
        Watchlist.user_id == user.id, Watchlist.symbol == symbol))).scalar_one_or_none()
    if existing:
        existing.name = body.name or existing.name
        existing.thesis = body.thesis or existing.thesis
        if body.fair_value:
            existing.fair_value = body.fair_value
        if body.last_price is not None:
            existing.last_price = body.last_price
        row = existing
    else:
        row = Watchlist(user_id=user.id, symbol=symbol, name=body.name, thesis=body.thesis,
                        fair_value=body.fair_value, last_price=body.last_price)
        db.add(row)
    await db.commit()
    await db.refresh(row)
    # populate FMP metrics + 30d news in the background so the detail is ready on open
    background_tasks.add_task(_populate, user.id, symbol)
    return _out(row)


@router.delete("/{symbol}")
async def remove_from_watchlist(symbol: str, user: User = Depends(get_current_user),
                                db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(Watchlist).where(
        Watchlist.user_id == user.id, Watchlist.symbol == symbol.upper()))
    if result.rowcount == 0:
        raise HTTPException(404, "Symbol not in watchlist")
    await db.commit()
    return {"status": "removed", "symbol": symbol.upper()}
