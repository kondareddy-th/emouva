"""
AI-powered analysis endpoints.
All routes call Claude via the service layer.
API key managed server-side.
Results are written through to the stock_metrics cache.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_api_key, get_claude_model, rate_limit
from app.models.analysis import (
    StockAnalysisRequest,
    StockAnalysisResponse,
    ThesisRequest,
    ThesisResponse,
    BearCaseRequest,
    BearCaseResponse,
    SentimentRequest,
    SentimentResponse,
    FullReportRequest,
    FullReportResponse,
)
from app.services import claude

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


async def _cache_field(ticker: str, field_name: str, data: dict) -> None:
    """Write-through: persist AI result + enrichment data to stock_metrics cache."""
    try:
        from app.database import async_session
        from app.services.stock_cache import upsert_field
        from app.services.claude import flush_enrichment_to_cache
        async with async_session() as db:
            await upsert_field(db, ticker, field_name, data)
        # Also flush any buffered enrichment data (company_info, earnings, news, market_data)
        await flush_enrichment_to_cache(ticker)
    except Exception:
        logger.warning("Cache write-through failed for %s/%s", ticker, field_name)


@router.post("/stock", response_model=StockAnalysisResponse)
async def analyze_stock(
    req: StockAnalysisRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """Generate a comprehensive AI research report for a stock."""
    try:
        ticker = req.ticker.upper()
        result = await claude.analyze_stock(
            ticker=ticker,
            api_key=api_key,
            context=req.context,
            model=claude_model,
        )
        background_tasks.add_task(_cache_field, ticker, "ai_analysis", result)
        return StockAnalysisResponse(**result)
    except Exception as e:
        logger.exception("Stock analysis failed for %s", req.ticker)
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}") from e


@router.post("/thesis", response_model=ThesisResponse)
async def generate_thesis(
    req: ThesisRequest,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """Generate a structured, monitorable investment thesis."""
    try:
        result = await claude.generate_thesis(
            ticker=req.ticker.upper(),
            api_key=api_key,
            context=req.context,
            model=claude_model,
        )
        return ThesisResponse(**result)
    except Exception as e:
        logger.exception("Thesis generation failed for %s", req.ticker)
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}") from e


@router.post("/bear-case", response_model=BearCaseResponse)
async def bear_case(
    req: BearCaseRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """Generate the strongest possible bear case against a stock."""
    try:
        ticker = req.ticker.upper()
        result = await claude.generate_bear_case(
            ticker=ticker,
            api_key=api_key,
            current_thesis=req.current_thesis,
            scenario=req.scenario,
            model=claude_model,
        )
        # Only cache default bear case (no custom scenario)
        if not req.scenario:
            background_tasks.add_task(_cache_field, ticker, "ai_bear_case", result)
        return BearCaseResponse(**result)
    except Exception as e:
        logger.exception("Bear case generation failed for %s", req.ticker)
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}") from e


@router.post("/sentiment", response_model=SentimentResponse)
async def sentiment(
    req: SentimentRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """Analyze multi-dimensional sentiment for a stock."""
    try:
        ticker = req.ticker.upper()
        result = await claude.analyze_sentiment(
            ticker=ticker,
            api_key=api_key,
            model=claude_model,
        )
        background_tasks.add_task(_cache_field, ticker, "ai_sentiment", result)
        return SentimentResponse(**result)
    except Exception as e:
        logger.exception("Sentiment analysis failed for %s", req.ticker)
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}") from e


@router.post("/report", response_model=FullReportResponse)
async def full_report(
    req: FullReportRequest,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """Generate a comprehensive, publishable-quality investment report."""
    try:
        result = await claude.generate_full_report(
            ticker=req.ticker.upper(),
            api_key=api_key,
            context=req.context,
            model=claude_model,
        )
        return FullReportResponse(**result)
    except Exception as e:
        logger.exception("Full report generation failed for %s", req.ticker)
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}") from e
