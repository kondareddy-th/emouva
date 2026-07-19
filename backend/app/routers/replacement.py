


"""
Replacement pipeline router — API endpoints for holding review.

Endpoints:
  POST /api/replacement/review      — Full 8-stage pipeline
  GET  /api/replacement/thesis/{t}  — Thesis health only (lightweight)
  GET  /api/replacement/etf-map     — List all ETF mappings
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException, Depends

from app.dependencies import get_api_key

from app.models.replacement import ReviewRequest, ReviewResponse, ThesisHealthResult, ETFAlternative
from app.services.replacement.engine import run_replacement_pipeline
from app.services.replacement.thesis_health import compute_thesis_health
from app.services.replacement.etf_mapping import SECTOR_ETFS, SUB_INDUSTRY_ETFS, get_etf_alternative

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/replacement", tags=["replacement"])


ALLOWED_MODELS = {
    "claude-sonnet-4-5-20250514",
    "claude-sonnet-4-6-20250725",
    "claude-opus-4-6-20250918",
}


@router.post("/review", response_model=ReviewResponse)
async def review_holding(
    request: ReviewRequest,
    api_key: str = Depends(get_api_key),
    x_claude_model: str | None = Header(None, alias="X-Claude-Model"),
):
    """Run the full 8-stage replacement pipeline for a holding.

    - Stages 1-3 (underperformance, thesis health, hold gate) always run
    - Stages 4-7 (candidates, scoring, context, ETF) run if hold gate passes
    - Stage 8 (LLM narrative) runs with the server API key
    """
    model = "claude-sonnet-4-5-20250514"
    if x_claude_model and x_claude_model in ALLOWED_MODELS:
        model = x_claude_model

    try:
        result = await run_replacement_pipeline(
            request=request,
            api_key=api_key,
            model=model,
        )
        return result
    except Exception:
        logger.exception("Replacement pipeline failed for %s", request.ticker)
        raise HTTPException(status_code=500, detail="Replacement analysis failed. Please try again.")


@router.get("/thesis/{ticker}", response_model=ThesisHealthResult)
async def get_thesis_health(ticker: str):
    """Lightweight endpoint: thesis health score only (no replacements).

    Uses yfinance data — no API key required.
    """
    ticker = ticker.upper()
    try:
        result = await asyncio.to_thread(compute_thesis_health, ticker)
        return result
    except Exception:
        logger.exception("Thesis health failed for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Failed to compute thesis health for {ticker}")


@router.get("/etf-map")
async def get_etf_mappings():
    """List all sector and sub-industry ETF mappings."""
    sectors = {}
    for sector_name, entry in SECTOR_ETFS.items():
        if sector_name not in sectors:  # Dedupe aliases
            sectors[sector_name] = {
                "ticker": entry.ticker,
                "name": entry.name,
                "expense_ratio": entry.expense_ratio,
                "top_holdings": list(entry.top_holdings),
            }

    sub_industries = {}
    for industry_name, entry in SUB_INDUSTRY_ETFS.items():
        sub_industries[industry_name] = {
            "ticker": entry.ticker,
            "name": entry.name,
            "expense_ratio": entry.expense_ratio,
            "top_holdings": list(entry.top_holdings),
        }

    return {
        "sectors": sectors,
        "sub_industries": sub_industries,
    }
