


"""
Stock metrics cache endpoints.
Provides read access to cached analysis data + progressive loading via SSE.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_api_key, get_claude_model
from app.services import stock_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


# ── Request / Response Models ─────────────────────────────────


class FieldInfo(BaseModel):
    data: dict | list | None = None
    status: str  # "fresh" | "stale" | "missing"
    updated_at: str | None = None


class MetricsResponse(BaseModel):
    ticker: str
    fields: dict[str, FieldInfo]
    freshness_summary: dict[str, str]


class TrendingItem(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    access_count: int
    last_analysis_at: str | None = None
    has_analysis: bool
    has_sentiment: bool
    fair_value_base: float | None = None
    sentiment_composite: int | None = None


class BatchRequest(BaseModel):
    tickers: list[str]


class BatchItem(BaseModel):
    fair_value: dict | None = None
    verdict: float | None = None
    sentiment_composite: int | None = None
    quality_score: dict | None = None
    freshness: str


class RefreshRequest(BaseModel):
    fields: list[str] | None = None  # None = refresh all


# ── Endpoints ─────────────────────────────────────────────────


@router.get("/trending", response_model=list[TrendingItem])
async def get_trending(db: AsyncSession = Depends(get_db)):
    """Get most-accessed tickers (last 7 days)."""
    trending = await stock_cache.get_trending(db, limit=10)
    return trending


@router.post("/batch")
async def get_batch(req: BatchRequest, db: AsyncSession = Depends(get_db)):
    """Bulk fetch cached AI data for multiple tickers (portfolio view)."""
    if len(req.tickers) > 50:
        raise HTTPException(400, "Maximum 50 tickers per batch request")
    results = await stock_cache.get_batch(db, req.tickers)
    return {"results": results}


@router.get("/{ticker}")
async def get_metrics(ticker: str, db: AsyncSession = Depends(get_db)):
    """Get all cached fields + freshness status for a ticker."""
    ticker = ticker.upper()
    row = await stock_cache.get_metrics(db, ticker)
    freshness = await stock_cache.get_freshness(db, ticker)

    if row is None:
        return MetricsResponse(
            ticker=ticker,
            fields={f: FieldInfo(data=None, status="missing", updated_at=None) for f in stock_cache.FIELD_NAMES},
            freshness_summary=freshness,
        )

    fields = {}
    for f in stock_cache.FIELD_NAMES:
        data = getattr(row, f, None)
        ts = getattr(row, f"{f}_at", None)
        fields[f] = FieldInfo(
            data=data,
            status=freshness[f],
            updated_at=ts.isoformat() if ts else None,
        )

    return MetricsResponse(ticker=ticker, fields=fields, freshness_summary=freshness)


@router.get("/{ticker}/stream")
async def stream_metrics(
    ticker: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
):
    """SSE endpoint for progressive loading — serves cached data instantly, then refreshes stale fields."""
    ticker = ticker.upper()

    async def event_generator():
        # Phase 1: Serve all cached fields immediately
        row = await stock_cache.get_metrics(db, ticker)
        freshness = await stock_cache.get_freshness(db, ticker)

        for f in stock_cache.FIELD_NAMES:
            data = getattr(row, f, None) if row else None
            status = freshness[f]
            if data is not None:
                yield f"event: field_cached\ndata: {json.dumps({'field': f, 'status': status, 'data': data})}\n\n"

        # Identify fields that need refresh
        stale_fields = [f for f, s in freshness.items() if s in ("stale", "missing")]
        if not stale_fields:
            yield f"event: done\ndata: {json.dumps({'message': 'All fields fresh'})}\n\n"
            return

        # Phase 2: Refresh stale/missing market data fields (cheap yfinance calls)
        market_fields = [f for f in stale_fields if f in ("company_info", "earnings", "news", "market_data")]
        if market_fields:
            for f in market_fields:
                yield f"event: field_loading\ndata: {json.dumps({'field': f})}\n\n"

            try:
                from app.services.market_data import get_company_info, get_earnings, get_news

                if "company_info" in market_fields:
                    info = await asyncio.to_thread(get_company_info, ticker)
                    if info and info.get("name"):
                        from app.database import async_session
                        async with async_session() as cache_db:
                            await stock_cache.upsert_field(cache_db, ticker, "company_info", info)
                        yield f"event: field_updated\ndata: {json.dumps({'field': 'company_info', 'data': info})}\n\n"

                if "earnings" in market_fields:
                    earnings = await asyncio.to_thread(get_earnings, ticker, 2)
                    if earnings:
                        from app.database import async_session
                        async with async_session() as cache_db:
                            await stock_cache.upsert_field(cache_db, ticker, "earnings", earnings)
                        yield f"event: field_updated\ndata: {json.dumps({'field': 'earnings', 'data': earnings})}\n\n"

                if "news" in market_fields:
                    news_data = await asyncio.to_thread(get_news, ticker)
                    if news_data:
                        from app.database import async_session
                        async with async_session() as cache_db:
                            await stock_cache.upsert_field(cache_db, ticker, "news", news_data)
                        yield f"event: field_updated\ndata: {json.dumps({'field': 'news', 'data': news_data})}\n\n"

            except Exception:
                logger.warning("Failed to refresh market data for %s", ticker)

        # Phase 3: Refresh stale AI fields (expensive Claude calls)
        ai_fields = [f for f in stale_fields if f.startswith("ai_")]
        if ai_fields:
            from app.services import claude

            for f in ai_fields:
                yield f"event: field_loading\ndata: {json.dumps({'field': f})}\n\n"

            try:
                if "ai_analysis" in ai_fields:
                    result = await claude.analyze_stock(ticker, api_key, model=claude_model)
                    from app.database import async_session
                    async with async_session() as cache_db:
                        await stock_cache.upsert_field(cache_db, ticker, "ai_analysis", result)
                    yield f"event: field_updated\ndata: {json.dumps({'field': 'ai_analysis', 'data': result})}\n\n"

                if "ai_bear_case" in ai_fields:
                    result = await claude.generate_bear_case(ticker, api_key, model=claude_model)
                    from app.database import async_session
                    async with async_session() as cache_db:
                        await stock_cache.upsert_field(cache_db, ticker, "ai_bear_case", result)
                    yield f"event: field_updated\ndata: {json.dumps({'field': 'ai_bear_case', 'data': result})}\n\n"

                if "ai_sentiment" in ai_fields:
                    result = await claude.analyze_sentiment(ticker, api_key, model=claude_model)
                    from app.database import async_session
                    async with async_session() as cache_db:
                        await stock_cache.upsert_field(cache_db, ticker, "ai_sentiment", result)
                    yield f"event: field_updated\ndata: {json.dumps({'field': 'ai_sentiment', 'data': result})}\n\n"

            except Exception:
                logger.warning("Failed to refresh AI fields for %s", ticker)
                yield f"event: error\ndata: {json.dumps({'message': 'AI refresh failed'})}\n\n"

        yield f"event: done\ndata: {json.dumps({'message': 'Refresh complete'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{ticker}/refresh")
async def refresh_metrics(
    ticker: str,
    req: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
):
    """Force-refresh specific fields for a ticker."""
    ticker = ticker.upper()
    fields_to_refresh = req.fields or list(stock_cache.FIELD_NAMES)
    refreshed = []

    # Refresh market data fields
    from app.services.market_data import get_company_info, get_earnings, get_news

    if "company_info" in fields_to_refresh:
        try:
            info = await asyncio.to_thread(get_company_info, ticker)
            if info:
                await stock_cache.upsert_field(db, ticker, "company_info", info)
                refreshed.append("company_info")
        except Exception:
            pass

    if "earnings" in fields_to_refresh:
        try:
            earnings = await asyncio.to_thread(get_earnings, ticker, 2)
            if earnings:
                await stock_cache.upsert_field(db, ticker, "earnings", earnings)
                refreshed.append("earnings")
        except Exception:
            pass

    if "news" in fields_to_refresh:
        try:
            news_data = await asyncio.to_thread(get_news, ticker)
            if news_data:
                await stock_cache.upsert_field(db, ticker, "news", news_data)
                refreshed.append("news")
        except Exception:
            pass

    # Refresh AI fields
    from app.services import claude

    if "ai_analysis" in fields_to_refresh:
        try:
            result = await claude.analyze_stock(ticker, api_key, model=claude_model)
            await stock_cache.upsert_field(db, ticker, "ai_analysis", result)
            refreshed.append("ai_analysis")
        except Exception:
            pass

    if "ai_bear_case" in fields_to_refresh:
        try:
            result = await claude.generate_bear_case(ticker, api_key, model=claude_model)
            await stock_cache.upsert_field(db, ticker, "ai_bear_case", result)
            refreshed.append("ai_bear_case")
        except Exception:
            pass

    if "ai_sentiment" in fields_to_refresh:
        try:
            result = await claude.analyze_sentiment(ticker, api_key, model=claude_model)
            await stock_cache.upsert_field(db, ticker, "ai_sentiment", result)
            refreshed.append("ai_sentiment")
        except Exception:
            pass

    freshness = await stock_cache.get_freshness(db, ticker)
    return {"ticker": ticker, "refreshed": refreshed, "freshness": freshness}
