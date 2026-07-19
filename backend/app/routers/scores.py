

"""
Stock Validity Scores — weekly scoring with persistence and trend tracking.
"""

import asyncio
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_api_key, get_claude_model, get_current_user, rate_limit
from app.models.db import User
from app.models.scores import (
    ScoreRefreshRequest,
    ScoreRefreshResponse,
    ScoreHistoryResponse,
    ScoreChangesResponse,
    LatestScoresResponse,
)
from app.services import stock_scorer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.post("/refresh", response_model=ScoreRefreshResponse)
async def refresh_scores(
    body: ScoreRefreshRequest,
    api_key: str = Depends(get_api_key),
    model: str = Depends(get_claude_model),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _rate: None = Depends(rate_limit("analysis")),
):
    """Score stocks and persist results. If symbols is null, scores all portfolio holdings."""
    start = time.time()

    symbols = body.symbols
    if not symbols:
        # Get all portfolio holdings from Robinhood
        from app.services import robinhood
        if not robinhood.is_connected():
            raise HTTPException(
                status_code=400,
                detail="Robinhood not connected. Connect in Settings or provide specific symbols.",
            )
        positions = await asyncio.to_thread(robinhood.get_positions)
        symbols = [p["symbol"] for p in positions if p.get("symbol")]

    if not symbols:
        raise HTTPException(status_code=400, detail="No symbols to score.")

    if len(symbols) > 25:
        raise HTTPException(
            status_code=400,
            detail=f"Too many symbols ({len(symbols)}). Max 25 per refresh.",
        )

    scores = await stock_scorer.score_portfolio(
        symbols=symbols,
        user_id=str(user.id),
        api_key=api_key,
        model=model,
        db=db,
    )

    elapsed = time.time() - start
    week = stock_scorer._current_week_label()

    return ScoreRefreshResponse(
        scores=scores,
        elapsed_seconds=round(elapsed, 1),
        week_label=week,
    )


@router.get("/latest", response_model=LatestScoresResponse)
async def latest_scores(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the most recent scores for all stocks."""
    scores = await stock_scorer.get_latest_scores(str(user.id), db)
    week = stock_scorer._current_week_label()
    return LatestScoresResponse(scores=scores, week_label=week)


@router.get("/history/{symbol}", response_model=ScoreHistoryResponse)
async def score_history(
    symbol: str,
    limit: int = Query(default=12, ge=1, le=52),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get score history for a specific stock."""
    history = await stock_scorer.get_score_history(
        str(user.id), symbol.upper(), db, limit
    )
    return ScoreHistoryResponse(symbol=symbol.upper(), history=history)


@router.get("/changes", response_model=ScoreChangesResponse)
async def score_changes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get week-over-week score changes for all stocks."""
    changes = await stock_scorer.get_score_changes(str(user.id), db)
    week = stock_scorer._current_week_label()
    return ScoreChangesResponse(week_label=week, changes=changes)
