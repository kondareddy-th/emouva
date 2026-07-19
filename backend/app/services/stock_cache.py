"""
Shared stock metrics cache with per-field TTL timestamps.
Provides stale-while-revalidate pattern for instant data serving.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import StockMetrics

logger = logging.getLogger(__name__)

# Per-field TTL configuration
FIELD_TTLS: dict[str, timedelta] = {
    "market_data": timedelta(minutes=15),
    "company_info": timedelta(hours=24),
    "earnings": timedelta(days=7),
    "news": timedelta(hours=1),
    "ai_analysis": timedelta(hours=24),
    "ai_bear_case": timedelta(hours=24),
    "ai_sentiment": timedelta(hours=6),
}

# All cacheable field names
FIELD_NAMES = list(FIELD_TTLS.keys())


def _field_status(data, timestamp: datetime | None, ttl: timedelta) -> str:
    """Return 'fresh', 'stale', or 'missing' for a single field."""
    if data is None or timestamp is None:
        return "missing"
    age = datetime.utcnow() - timestamp
    return "fresh" if age < ttl else "stale"


async def get_metrics(db: AsyncSession, ticker: str) -> StockMetrics | None:
    """Get cached metrics for a ticker. Bumps access count."""
    ticker = ticker.upper()
    result = await db.execute(
        select(StockMetrics).where(StockMetrics.ticker == ticker)
    )
    row = result.scalar_one_or_none()
    if row:
        row.access_count = (row.access_count or 0) + 1
        row.last_accessed_at = datetime.utcnow()
        await db.commit()
    return row


async def upsert_field(db: AsyncSession, ticker: str, field_name: str, data) -> None:
    """Insert or update a single cached field for a ticker."""
    ticker = ticker.upper()
    if field_name not in FIELD_TTLS:
        logger.warning("Unknown cache field: %s", field_name)
        return

    result = await db.execute(
        select(StockMetrics).where(StockMetrics.ticker == ticker)
    )
    row = result.scalar_one_or_none()

    now = datetime.utcnow()
    if row is None:
        row = StockMetrics(ticker=ticker, access_count=0)
        db.add(row)

    setattr(row, field_name, data)
    setattr(row, f"{field_name}_at", now)
    row.updated_at = now

    await db.commit()


async def get_freshness(db: AsyncSession, ticker: str) -> dict[str, str]:
    """Return freshness status for all fields of a ticker."""
    ticker = ticker.upper()
    result = await db.execute(
        select(StockMetrics).where(StockMetrics.ticker == ticker)
    )
    row = result.scalar_one_or_none()

    if row is None:
        return {f: "missing" for f in FIELD_NAMES}

    return {
        f: _field_status(
            getattr(row, f),
            getattr(row, f"{f}_at"),
            FIELD_TTLS[f],
        )
        for f in FIELD_NAMES
    }


async def get_cached_if_fresh(db: AsyncSession, ticker: str, field_name: str):
    """Return cached data only if within TTL, else None."""
    ticker = ticker.upper()
    result = await db.execute(
        select(StockMetrics).where(StockMetrics.ticker == ticker)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None

    data = getattr(row, field_name, None)
    ts = getattr(row, f"{field_name}_at", None)
    if data is None or ts is None:
        return None

    age = datetime.utcnow() - ts
    return data if age < FIELD_TTLS[field_name] else None


async def get_cached_any(db: AsyncSession, ticker: str, field_name: str) -> tuple:
    """Return (data, status) — serves stale data for SWR pattern."""
    ticker = ticker.upper()
    result = await db.execute(
        select(StockMetrics).where(StockMetrics.ticker == ticker)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None, "missing"

    data = getattr(row, field_name, None)
    ts = getattr(row, f"{field_name}_at", None)
    status = _field_status(data, ts, FIELD_TTLS[field_name])
    return data, status


async def get_trending(db: AsyncSession, limit: int = 10) -> list[dict]:
    """Get most-accessed tickers in the last 7 days."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    result = await db.execute(
        select(StockMetrics)
        .where(StockMetrics.last_accessed_at >= cutoff)
        .order_by(StockMetrics.access_count.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    trending = []
    for row in rows:
        # Extract basic info from cached data
        info = row.company_info or {}
        analysis = row.ai_analysis or {}
        sentiment = row.ai_sentiment or {}

        trending.append({
            "ticker": row.ticker,
            "name": info.get("name", row.ticker),
            "sector": info.get("sector"),
            "access_count": row.access_count,
            "last_analysis_at": row.ai_analysis_at.isoformat() if row.ai_analysis_at else None,
            "has_analysis": row.ai_analysis is not None,
            "has_sentiment": row.ai_sentiment is not None,
            "fair_value_base": analysis.get("valuation", {}).get("base") if analysis else None,
            "sentiment_composite": sentiment.get("scores", {}).get("composite") if sentiment else None,
        })

    return trending


async def get_batch(db: AsyncSession, tickers: list[str]) -> dict[str, dict]:
    """Bulk fetch cached AI data for multiple tickers (for portfolio view)."""
    upper_tickers = [t.upper() for t in tickers]
    result = await db.execute(
        select(StockMetrics).where(StockMetrics.ticker.in_(upper_tickers))
    )
    rows = {row.ticker: row for row in result.scalars().all()}

    batch = {}
    for t in upper_tickers:
        row = rows.get(t)
        if row is None:
            batch[t] = {
                "fair_value": None,
                "verdict": None,
                "sentiment_composite": None,
                "quality_score": None,
                "freshness": "missing",
            }
            continue

        analysis = row.ai_analysis or {}
        sentiment = row.ai_sentiment or {}
        valuation = analysis.get("valuation", {})
        quality = analysis.get("quality_score", {})

        # Determine overall freshness (worst of analysis + sentiment)
        a_status = _field_status(row.ai_analysis, row.ai_analysis_at, FIELD_TTLS["ai_analysis"])
        s_status = _field_status(row.ai_sentiment, row.ai_sentiment_at, FIELD_TTLS["ai_sentiment"])
        if a_status == "missing" or s_status == "missing":
            freshness = "missing"
        elif a_status == "stale" or s_status == "stale":
            freshness = "stale"
        else:
            freshness = "fresh"

        batch[t] = {
            "fair_value": {
                "bear": valuation.get("bear"),
                "base": valuation.get("base"),
                "bull": valuation.get("bull"),
            } if valuation.get("base") is not None else None,
            "verdict": quality.get("overall"),
            "sentiment_composite": sentiment.get("scores", {}).get("composite"),
            "quality_score": quality,
            "freshness": freshness,
        }

    return batch
