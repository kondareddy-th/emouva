
"""Stress test engine — orchestrates the full pipeline.

1. Resolve portfolio (from request or Robinhood)
2. Resolve scenario (pre-built or Claude classification)
3. Check cache
4. Load stock sensitivity profiles
5. Compute per-stock impacts (deterministic math)
6. Compute correlation adjustment
7. Aggregate and return
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stress_test import (
    ConfidenceMetadata,
    CorrelationAdjustment,
    PortfolioHolding,
    PortfolioImpactSummary,
    ScenarioInfo,
    StockImpact,
    StressTestResult,
)
from app.services.stress_test.cache import (
    build_cache_key,
    build_portfolio_hash,
    get_cached_result,
    store_result,
)
from app.services.stress_test.impact_calculator import (
    compute_correlation_adjustment,
    compute_stock_impact,
    estimate_recovery_months,
    get_sensitivity_factors,
)
from app.services.stress_test.profile_builder import get_profiles
from app.services.stress_test.scenarios import SCENARIO_VERSION, SCENARIOS

logger = logging.getLogger(__name__)


# ── Public API ──────────────────────────────────────────────────


async def run_stress_test(
    portfolio: list[PortfolioHolding] | None,
    scenario_id: str | None,
    custom_scenario: str | None,
    include_correlation: bool,
    confidence_level: str,
    api_key: str,
    model: str,
    db: AsyncSession,
) -> StressTestResult:
    """Main orchestrator — runs the full stress test pipeline."""
    start_time = time.time()

    # 1. Resolve portfolio
    holdings = await _resolve_portfolio(portfolio)
    if not holdings:
        raise ValueError("No portfolio holdings available. Connect Robinhood in Settings.")

    # 2. Resolve scenario
    if scenario_id:
        scenario_def = SCENARIOS[scenario_id]
        methodology = "historical_replay" if scenario_def.actual_stock_impacts else "sector_factor_model"
        custom_input = None
    else:
        from app.services.stress_test.custom_classifier import classify_custom_scenario
        scenario_def = await classify_custom_scenario(custom_scenario, api_key, model)
        methodology = "llm_estimated"
        custom_input = custom_scenario

    # 3. Cache check
    holdings_for_key = [{"symbol": h.symbol, "shares": h.shares} for h in holdings]
    scenario_id_for_key = _get_attr(scenario_def, "id", "custom")
    cache_key = build_cache_key(
        holdings=holdings_for_key,
        scenario_id=scenario_id_for_key,
        scenario_version=SCENARIO_VERSION,
        confidence_level=confidence_level,
        include_correlation=include_correlation,
    )

    cached = await get_cached_result(cache_key, db)
    if cached:
        return StressTestResult(**cached)

    # 4. Load sensitivity profiles
    symbols = [h.symbol for h in holdings]
    profiles = await get_profiles(symbols, db)

    # 5. Compute per-stock impacts
    per_stock: list[dict] = []
    for holding in holdings:
        symbol = holding.symbol
        profile = profiles.get(symbol, {"symbol": symbol, "sector": "Unknown"})
        current_value = holding.shares * (holding.current_price or 0)

        impact_pct = compute_stock_impact(profile, scenario_def, confidence_level)
        change_usd = current_value * (impact_pct / 100)

        per_stock.append({
            "symbol": symbol,
            "name": profile.get("name", symbol),
            "sector": profile.get("sector", "Unknown"),
            "current_value": round(current_value, 2),
            "stressed_value": round(current_value + change_usd, 2),
            "change_pct": impact_pct,
            "change_usd": round(change_usd, 2),
            "weight_pct": 0.0,
            "sensitivity_factors": get_sensitivity_factors(profile, scenario_def),
            "historical_actual": _get_historical_actual(symbol, scenario_def),
        })

    # Compute weights
    total_before = sum(s["current_value"] for s in per_stock)
    if total_before > 0:
        for s in per_stock:
            s["weight_pct"] = round(s["current_value"] / total_before * 100, 1)

    # 6. Correlation adjustment
    corr_adj = None
    if include_correlation:
        corr_data = compute_correlation_adjustment(per_stock, scenario_def, total_before)
        if corr_data["applied"]:
            corr_adj = CorrelationAdjustment(**corr_data)

    # 7. Aggregate
    total_change_usd = sum(s["change_usd"] for s in per_stock)
    if corr_adj:
        total_change_usd += total_before * (corr_adj.additional_impact_pct / 100)

    total_after = total_before + total_change_usd
    total_change_pct = (total_change_usd / total_before * 100) if total_before else 0

    severity = _get_attr(scenario_def, "severity", 5)

    now = datetime.utcnow()
    result_id = str(uuid.uuid4())
    computation_ms = int((time.time() - start_time) * 1000)

    # Sort by impact (worst first)
    per_stock_sorted = sorted(per_stock, key=lambda s: s["change_pct"])

    result = StressTestResult(
        result_id=result_id,
        scenario=ScenarioInfo(
            id=str(_get_attr(scenario_def, "id", "custom")),
            name=str(_get_attr(scenario_def, "name", "Custom")),
            description=str(_get_attr(scenario_def, "description", "")),
            category=str(_get_attr(scenario_def, "category", "custom")),
            severity=severity,
            sp500_impact=_get_attr(scenario_def, "sp500_impact", None),
            duration_months=_get_attr(scenario_def, "duration_months", None),
            tags=list(_get_attr(scenario_def, "tags", [])),
            version=SCENARIO_VERSION,
        ),
        portfolio_impact=PortfolioImpactSummary(
            total_value_before=round(total_before, 2),
            total_value_after=round(total_after, 2),
            total_change_pct=round(total_change_pct, 1),
            total_change_usd=round(total_change_usd, 2),
            worst_day_estimate_pct=round(total_change_pct * 0.25, 1),
            recovery_time_months=estimate_recovery_months(severity),
        ),
        per_stock_impact=[StockImpact(**s) for s in per_stock_sorted],
        correlation_adjustment=corr_adj,
        confidence=ConfidenceMetadata(
            level=confidence_level,
            methodology=methodology,
            data_coverage_pct=round(len(profiles) / max(len(holdings), 1) * 100, 1),
            disclaimer=_get_disclaimer(methodology),
        ),
        computed_at=now,
        cache_key=cache_key,
        cached_until=now + timedelta(hours=1),
    )

    # Persist to cache (background)
    asyncio.create_task(_persist_result(
        cache_key=cache_key,
        result=result,
        scenario_id_for_key=scenario_id_for_key,
        portfolio_hash=build_portfolio_hash(holdings_for_key),
        portfolio_size=len(holdings),
        methodology=methodology,
        confidence_level=confidence_level,
        computation_ms=computation_ms,
        custom_input=custom_input,
        db=db,
    ))

    return result


# ── Portfolio Resolution ────────────────────────────────────────


async def _resolve_portfolio(
    portfolio: list[PortfolioHolding] | None,
) -> list[PortfolioHolding]:
    """Get portfolio from request or fall back to Robinhood."""
    if portfolio:
        return portfolio

    from app.services import robinhood
    if not robinhood.is_connected():
        return []

    positions = await asyncio.to_thread(robinhood.get_positions)
    return [
        PortfolioHolding(
            symbol=p["symbol"],
            shares=float(p.get("shares", 0)),
            current_price=float(p.get("current_price") or p.get("price") or 0),
        )
        for p in positions
        if float(p.get("shares", 0)) > 0
    ]


# ── Helpers ─────────────────────────────────────────────────────


def _get_attr(obj: object | dict, key: str, default: object = None) -> object:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _get_historical_actual(symbol: str, scenario: object | dict) -> float | None:
    actuals = _get_attr(scenario, "actual_stock_impacts", {}) or {}
    return actuals.get(symbol)


def _get_disclaimer(methodology: str) -> str:
    disclaimers = {
        "sector_factor_model": (
            "Based on sector-level factor model with beta, size, and quality adjustments. "
            "Individual stock outcomes may vary significantly. Not financial advice."
        ),
        "historical_replay": (
            "Blends historical actual returns (50%) with factor model estimates (50%). "
            "Past performance does not guarantee future results. Not financial advice."
        ),
        "llm_estimated": (
            "Scenario classified by AI and mapped to nearest pre-built model. "
            "Custom scenarios have wider confidence intervals. Not financial advice."
        ),
    }
    return disclaimers.get(methodology, "Hypothetical illustration only. Not financial advice.")


async def _persist_result(
    cache_key: str,
    result: StressTestResult,
    scenario_id_for_key: str,
    portfolio_hash: str,
    portfolio_size: int,
    methodology: str,
    confidence_level: str,
    computation_ms: int,
    custom_input: str | None,
    db: AsyncSession,
) -> None:
    """Background task to persist result to DB cache."""
    try:
        await store_result(
            cache_key=cache_key,
            result=result.model_dump(mode="json"),
            scenario_id=scenario_id_for_key,
            scenario_version=SCENARIO_VERSION,
            portfolio_hash=portfolio_hash,
            portfolio_size=portfolio_size,
            methodology=methodology,
            confidence_level=confidence_level,
            computation_ms=computation_ms,
            custom_input=custom_input,
            db=db,
        )
    except Exception:
        logger.warning("Failed to persist stress test result", exc_info=True)
