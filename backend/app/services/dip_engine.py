
"""
Dip-buying engine — evaluates buy rules against real-time market conditions.

Logic:
1. Stock must be down X% from user's avg cost
2. Market benchmark (e.g., QQQ) must also be down Y% from its 52-week high
3. Stock's drop can't exceed market drop by more than Z% (company-specific issue filter)
4. If all conditions met → place buy order
"""

import logging
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import BuyRule, Execution, User
from app.services import robinhood
from app.services.notifications import create_notification

logger = logging.getLogger(__name__)


async def evaluate_rule(
    rule: BuyRule,
    db: AsyncSession,
) -> dict:
    """Evaluate a single buy rule against current market conditions.
    Returns a result dict with evaluation details."""

    result = {
        "rule_id": str(rule.id),
        "symbol": rule.symbol,
        "triggered": False,
        "reason": "",
        "details": {},
    }

    # Pre-flight: market hours check
    if not robinhood.is_market_open():
        result["reason"] = "Market is closed"
        return result

    # Pre-flight: Robinhood connection
    if not robinhood.is_connected():
        result["reason"] = "Robinhood not connected"
        return result

    # Step 1: Get user's positions to find avg cost
    positions = robinhood.get_positions()
    position = next((p for p in positions if p["symbol"] == rule.symbol), None)
    if position is None:
        result["reason"] = f"No position found for {rule.symbol}"
        return result

    avg_cost = position["avg_cost"]
    if avg_cost <= 0:
        result["reason"] = f"Invalid avg cost for {rule.symbol}: {avg_cost}"
        return result

    # Step 2: Get current price
    quotes = robinhood.get_quotes_fast([rule.symbol])
    if not quotes:
        result["reason"] = f"Could not get quote for {rule.symbol}"
        return result

    current_price = quotes[0]["price"]
    stock_drop_pct = ((avg_cost - current_price) / avg_cost) * 100

    result["details"]["current_price"] = current_price
    result["details"]["avg_cost"] = avg_cost
    result["details"]["stock_drop_pct"] = round(stock_drop_pct, 2)

    # Step 3: Check if stock has dropped enough
    if stock_drop_pct < rule.drop_pct:
        result["reason"] = f"{rule.symbol} down {stock_drop_pct:.1f}% (need {rule.drop_pct}%+)"
        return result

    # Step 4: Get benchmark data
    benchmark = rule.market_benchmark
    fundamentals = robinhood.get_fundamentals_data([benchmark])
    bench_data = fundamentals.get(benchmark)
    if not bench_data:
        result["reason"] = f"Could not get fundamentals for benchmark {benchmark}"
        return result

    bench_52w_high = bench_data["high_52_weeks"]
    if bench_52w_high <= 0:
        result["reason"] = f"Invalid 52-week high for {benchmark}"
        return result

    bench_quotes = robinhood.get_quotes_fast([benchmark])
    if not bench_quotes:
        result["reason"] = f"Could not get quote for benchmark {benchmark}"
        return result

    bench_price = bench_quotes[0]["price"]
    market_drop_pct = ((bench_52w_high - bench_price) / bench_52w_high) * 100

    result["details"]["benchmark"] = benchmark
    result["details"]["benchmark_price"] = bench_price
    result["details"]["benchmark_52w_high"] = bench_52w_high
    result["details"]["market_drop_pct"] = round(market_drop_pct, 2)

    # Step 5: Check if market has dropped enough
    if market_drop_pct < rule.market_drop_pct:
        result["reason"] = (
            f"Market ({benchmark}) down {market_drop_pct:.1f}% from 52w high "
            f"(need {rule.market_drop_pct}%+)"
        )
        return result

    # Step 6: Check excess drop (company-specific filter)
    excess_drop = stock_drop_pct - market_drop_pct
    result["details"]["excess_drop_pct"] = round(excess_drop, 2)

    if excess_drop > rule.max_excess_drop_pct:
        result["reason"] = (
            f"{rule.symbol} excess drop {excess_drop:.1f}% vs market "
            f"(max allowed: {rule.max_excess_drop_pct}%). Likely company-specific issue."
        )
        return result

    # ALL CONDITIONS MET — execute buy
    result["triggered"] = True
    result["reason"] = (
        f"All conditions met: {rule.symbol} down {stock_drop_pct:.1f}% from avg cost, "
        f"{benchmark} down {market_drop_pct:.1f}% from 52w high, "
        f"excess drop {excess_drop:.1f}% within threshold"
    )

    # Execute buy order
    order_result = robinhood.place_buy_order(rule.symbol, rule.buy_amount_usd)

    # Log execution
    execution = Execution(
        rule_id=rule.id,
        user_id=rule.user_id,
        symbol=rule.symbol,
        trigger_price=current_price,
        avg_cost=avg_cost,
        market_benchmark_price=bench_price,
        market_drop_pct_actual=market_drop_pct,
        stock_drop_pct_actual=stock_drop_pct,
        buy_amount_usd=rule.buy_amount_usd,
        shares_bought=float(order_result.get("quantity", 0) or 0),
        order_id=order_result.get("order_id"),
        status="executed" if order_result["status"] == "submitted" else "failed",
        error_message=order_result.get("error"),
        executed_at=datetime.utcnow(),
    )
    db.add(execution)

    # Update rule timestamps
    await db.execute(
        update(BuyRule)
        .where(BuyRule.id == rule.id)
        .values(last_checked_at=datetime.utcnow(), last_triggered_at=datetime.utcnow())
    )
    await db.commit()

    # Create notification
    if order_result["status"] == "submitted":
        await create_notification(
            db, rule.user_id, "order_executed",
            f"Bought ${rule.buy_amount_usd:.0f} of {rule.symbol}",
            (
                f"Auto-buy triggered: {rule.symbol} at ${current_price:.2f} "
                f"(down {stock_drop_pct:.1f}% from ${avg_cost:.2f} avg cost). "
                f"{benchmark} down {market_drop_pct:.1f}% from 52w high."
            ),
            rule_id=rule.id,
        )
    else:
        await create_notification(
            db, rule.user_id, "order_failed",
            f"Failed to buy {rule.symbol}",
            f"Error: {order_result.get('error', 'Unknown error')}",
            rule_id=rule.id,
        )

    result["order"] = order_result
    return result


async def check_rules_for_user(user_id, db: AsyncSession) -> list[dict]:
    """Evaluate all active rules for a user."""
    result = await db.execute(
        select(BuyRule).where(BuyRule.user_id == user_id, BuyRule.is_active.is_(True))
    )
    rules = result.scalars().all()

    results = []
    for rule in rules:
        eval_result = await evaluate_rule(rule, db)

        # Update last_checked_at even if not triggered
        if not eval_result["triggered"]:
            await db.execute(
                update(BuyRule)
                .where(BuyRule.id == rule.id)
                .values(last_checked_at=datetime.utcnow())
            )
            await db.commit()

        results.append(eval_result)

    return results


async def scheduled_check_all(db: AsyncSession) -> list[dict]:
    """Check all active rules for all users. Called by scheduler."""
    result = await db.execute(
        select(User).where(
            User.id.in_(
                select(BuyRule.user_id).where(BuyRule.is_active.is_(True)).distinct()
            )
        )
    )
    users = result.scalars().all()

    all_results = []
    for user in users:
        user_results = await check_rules_for_user(user.id, db)
        all_results.extend(user_results)

    return all_results
