


"""
Buy rules CRUD + on-demand rule checks.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import BuyRule, Execution, User
from app.services.dip_engine import evaluate_rule, check_rules_for_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rules", tags=["rules"])


# ── Schemas ──────────────────────────────────────────────────

class CreateRuleRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    drop_pct: float = Field(gt=0, le=100, description="% drop from avg cost to trigger")
    market_benchmark: str = Field(default="QQQ", max_length=10)
    market_drop_pct: float = Field(gt=0, le=100, description="% drop in benchmark from 52w high")
    max_excess_drop_pct: float = Field(default=15.0, gt=0, le=100)
    buy_amount_usd: float = Field(gt=0, le=100000, description="Dollar amount to buy")
    check_interval_hours: int = Field(default=48, ge=1, le=720)


class UpdateRuleRequest(BaseModel):
    drop_pct: float | None = Field(default=None, gt=0, le=100)
    market_benchmark: str | None = Field(default=None, max_length=10)
    market_drop_pct: float | None = Field(default=None, gt=0, le=100)
    max_excess_drop_pct: float | None = Field(default=None, gt=0, le=100)
    buy_amount_usd: float | None = Field(default=None, gt=0, le=100000)
    is_active: bool | None = None
    check_interval_hours: int | None = Field(default=None, ge=1, le=720)


class RuleResponse(BaseModel):
    id: str
    symbol: str
    drop_pct: float
    market_benchmark: str
    market_drop_pct: float
    max_excess_drop_pct: float
    buy_amount_usd: float
    is_active: bool
    check_interval_hours: int
    last_checked_at: str | None
    last_triggered_at: str | None
    created_at: str


class ExecutionResponse(BaseModel):
    id: str
    rule_id: str
    symbol: str
    trigger_price: float
    avg_cost: float
    market_drop_pct_actual: float
    stock_drop_pct_actual: float
    buy_amount_usd: float
    shares_bought: float | None
    order_id: str | None
    status: str
    error_message: str | None
    executed_at: str | None
    created_at: str


def _rule_to_response(rule: BuyRule) -> RuleResponse:
    return RuleResponse(
        id=str(rule.id),
        symbol=rule.symbol,
        drop_pct=rule.drop_pct,
        market_benchmark=rule.market_benchmark,
        market_drop_pct=rule.market_drop_pct,
        max_excess_drop_pct=rule.max_excess_drop_pct,
        buy_amount_usd=rule.buy_amount_usd,
        is_active=rule.is_active,
        check_interval_hours=rule.check_interval_hours,
        last_checked_at=rule.last_checked_at.isoformat() if rule.last_checked_at else None,
        last_triggered_at=rule.last_triggered_at.isoformat() if rule.last_triggered_at else None,
        created_at=rule.created_at.isoformat(),
    )


# ── Endpoints ────────────────────────────────────────────────

@router.get("", response_model=list[RuleResponse])
async def list_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all buy rules for the current user."""
    result = await db.execute(
        select(BuyRule).where(BuyRule.user_id == user.id).order_by(BuyRule.created_at.desc())
    )
    return [_rule_to_response(r) for r in result.scalars().all()]


@router.post("", response_model=RuleResponse)
async def create_rule(
    req: CreateRuleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new buy rule."""
    rule = BuyRule(
        user_id=user.id,
        symbol=req.symbol.upper(),
        drop_pct=req.drop_pct,
        market_benchmark=req.market_benchmark.upper(),
        market_drop_pct=req.market_drop_pct,
        max_excess_drop_pct=req.max_excess_drop_pct,
        buy_amount_usd=req.buy_amount_usd,
        check_interval_hours=req.check_interval_hours,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    logger.info("Rule created: %s %s for user %s", rule.symbol, rule.id, user.username)
    return _rule_to_response(rule)


@router.put("/{rule_id}", response_model=RuleResponse)
async def update_rule(
    rule_id: str,
    req: UpdateRuleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a buy rule."""
    result = await db.execute(
        select(BuyRule).where(BuyRule.id == rule_id, BuyRule.user_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = req.model_dump(exclude_none=True)
    for field, value in updates.items():
        setattr(rule, field, value)
    rule.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(rule)
    return _rule_to_response(rule)


@router.delete("/{rule_id}")
async def delete_rule(
    rule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a buy rule."""
    result = await db.execute(
        select(BuyRule).where(BuyRule.id == rule_id, BuyRule.user_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    await db.delete(rule)
    await db.commit()
    return {"status": "deleted"}


@router.post("/{rule_id}/check-now")
async def check_rule_now(
    rule_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """On-demand check for a single rule."""
    result = await db.execute(
        select(BuyRule).where(BuyRule.id == rule_id, BuyRule.user_id == user.id)
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    eval_result = await evaluate_rule(rule, db)
    return eval_result


@router.post("/check-all")
async def check_all_rules(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """On-demand check for all active rules."""
    results = await check_rules_for_user(user.id, db)
    return {"results": results, "total": len(results)}


@router.get("/executions", response_model=list[ExecutionResponse])
async def list_executions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """List recent execution history."""
    result = await db.execute(
        select(Execution)
        .where(Execution.user_id == user.id)
        .order_by(Execution.created_at.desc())
        .limit(limit)
    )
    executions = result.scalars().all()
    return [
        ExecutionResponse(
            id=str(e.id),
            rule_id=str(e.rule_id),
            symbol=e.symbol,
            trigger_price=e.trigger_price,
            avg_cost=e.avg_cost,
            market_drop_pct_actual=e.market_drop_pct_actual,
            stock_drop_pct_actual=e.stock_drop_pct_actual,
            buy_amount_usd=e.buy_amount_usd,
            shares_bought=e.shares_bought,
            order_id=e.order_id,
            status=e.status,
            error_message=e.error_message,
            executed_at=e.executed_at.isoformat() if e.executed_at else None,
            created_at=e.created_at.isoformat(),
        )
        for e in executions
    ]
