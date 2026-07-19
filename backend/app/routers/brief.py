
"""
Portfolio Analysis endpoint — deep, user-triggered research on all holdings.
Supports both regular JSON responses and Server-Sent Events (SSE) streaming.
"""

import logging

from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request, Body
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_api_key, get_claude_model, rate_limit, get_optional_user
from app.models.brief import PortfolioAnalysisRequest, PortfolioAnalysisResponse
from app.models.db import PortfolioBrief
from app.services import claude

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/brief", tags=["brief"])


@router.post("/generate", response_model=PortfolioAnalysisResponse)
async def analyze_portfolio(
    req: PortfolioAnalysisRequest | None = None,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("brief")),
):
    """Deep portfolio analysis — fetches fresh data for every position and generates
    comprehensive recommendations. User-triggered, may take 30-60 seconds."""
    try:
        context = req.portfolio_context if req else None
        result = await claude.analyze_portfolio(
            api_key=api_key,
            portfolio_context=context,
            model=claude_model,
        )
        return PortfolioAnalysisResponse(**result)
    except Exception as e:
        logger.exception("Portfolio analysis failed")
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {e}") from e


@router.get("/latest")
async def latest_brief(account: str | None = None, user=Depends(get_optional_user),
                       db: AsyncSession = Depends(get_db)):
    """The user's last-generated Portfolio Analysis (per account), served from DB
    so the same brief shows across sessions/devices until they refresh."""
    if not user:
        return {"data": None, "generated_at": None}
    acct = account or "default"
    row = (await db.execute(
        select(PortfolioBrief).where(
            PortfolioBrief.user_id == user.id, PortfolioBrief.account == acct,
        )
    )).scalar_one_or_none()
    if not row:
        return {"data": None, "generated_at": None}
    return {"data": row.data, "generated_at": row.generated_at.isoformat()}


@router.post("/save")
async def save_brief(payload: dict = Body(...), account: str | None = None,
                     user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Persist a freshly generated brief for the user (called by the client when a
    stream finishes). Upserts the single per-account row."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    acct = account or "default"
    now = datetime.utcnow()
    row = (await db.execute(
        select(PortfolioBrief).where(
            PortfolioBrief.user_id == user.id, PortfolioBrief.account == acct,
        )
    )).scalar_one_or_none()
    if row:
        row.data = payload
        row.generated_at = now
    else:
        db.add(PortfolioBrief(user_id=user.id, account=acct, data=payload, generated_at=now))
    await db.commit()
    return {"ok": True, "generated_at": now.isoformat()}


@router.get("/generate/stream")
async def stream_portfolio_analysis(
    request: Request,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("brief")),
):
    """SSE endpoint that streams portfolio analysis in real time.
    Events: status (progress), delta (AI tokens), done (final JSON), error.
    """
    context = request.query_params.get("context")

    async def event_generator():
        async for event in claude.stream_portfolio_analysis(
            api_key=api_key,
            portfolio_context=context,
            model=claude_model,
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
