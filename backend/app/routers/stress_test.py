

"""Stress test API endpoints.

POST /api/stress-test/run          — Run stress test
GET  /api/stress-test/scenarios    — List pre-built scenarios
GET  /api/stress-test/results/:id  — Retrieve cached result
GET  /api/stress-test/compare      — Compare multiple scenarios
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_api_key, get_claude_model
from app.models.stress_test import (
    ScenarioListItem,
    ScenarioListResponse,
    StressTestRequest,
    StressTestResult,
)
from app.services.stress_test.cache import get_cached_result_by_id
from app.services.stress_test.engine import run_stress_test
from app.services.stress_test.scenarios import SCENARIOS, SCENARIO_VERSION, list_categories

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stress-test", tags=["stress-test"])


@router.post("/run", response_model=StressTestResult)
async def run_stress_test_endpoint(
    request: StressTestRequest,
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
    model: str = Depends(get_claude_model),
) -> StressTestResult:
    """Run a stress test on a portfolio against a scenario."""
    if not request.scenario_id and not request.custom_scenario:
        raise HTTPException(400, "Provide either scenario_id or custom_scenario")
    if request.scenario_id and request.scenario_id not in SCENARIOS:
        raise HTTPException(404, f"Unknown scenario: {request.scenario_id}")

    try:
        result = await run_stress_test(
            portfolio=request.portfolio,
            scenario_id=request.scenario_id,
            custom_scenario=request.custom_scenario,
            include_correlation=request.include_correlation_adjustment,
            confidence_level=request.confidence_level,
            api_key=api_key,
            model=model,
            db=db,
        )
        return result
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception:
        logger.exception("Stress test failed")
        raise HTTPException(500, "Stress test computation failed")


@router.get("/scenarios", response_model=ScenarioListResponse)
async def list_scenarios(
    category: str | None = Query(None, description="Filter by category"),
) -> ScenarioListResponse:
    """List all pre-built stress test scenarios."""
    scenarios = list(SCENARIOS.values())

    if category:
        scenarios = [s for s in scenarios if s.category == category]

    items = [
        ScenarioListItem(
            id=s.id,
            name=s.name,
            category=s.category,
            severity=s.severity,
            description=s.description,
            sp500_impact=s.sp500_impact,
            duration_months=s.duration_months,
            tags=list(s.tags),
            version=s.version,
        )
        for s in scenarios
    ]

    return ScenarioListResponse(
        scenarios=items,
        categories=list_categories(),
        total=len(items),
        version=SCENARIO_VERSION,
    )


@router.get("/results/{result_id}")
async def get_result(
    result_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Retrieve a cached stress test result by ID."""
    result = await get_cached_result_by_id(result_id, db)
    if not result:
        raise HTTPException(404, "Result expired or not found")
    return result


@router.get("/compare")
async def compare_scenarios(
    scenario_ids: str = Query(..., description="Comma-separated scenario IDs (2-5)"),
    db: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
    model: str = Depends(get_claude_model),
) -> dict:
    """Run and compare multiple scenarios against the current portfolio."""
    ids = [s.strip() for s in scenario_ids.split(",") if s.strip()]
    if len(ids) < 2 or len(ids) > 5:
        raise HTTPException(400, "Provide 2-5 scenario IDs")

    for sid in ids:
        if sid not in SCENARIOS:
            raise HTTPException(404, f"Unknown scenario: {sid}")

    results: list[StressTestResult] = []
    for sid in ids:
        result = await run_stress_test(
            portfolio=None,
            scenario_id=sid,
            custom_scenario=None,
            include_correlation=True,
            confidence_level="medium",
            api_key=api_key,
            model=model,
            db=db,
        )
        results.append(result)

    return {
        "scenarios": [
            {
                "id": r.scenario.id,
                "name": r.scenario.name,
                "severity": r.scenario.severity,
                "portfolio_impact_pct": r.portfolio_impact.total_change_pct,
                "portfolio_impact_usd": r.portfolio_impact.total_change_usd,
                "recovery_months": r.portfolio_impact.recovery_time_months,
            }
            for r in results
        ],
        "per_stock_comparison": _build_stock_comparison(results),
    }


def _build_stock_comparison(results: list[StressTestResult]) -> list[dict]:
    """Build per-stock impact comparison across scenarios."""
    all_symbols: set[str] = set()
    for r in results:
        for s in r.per_stock_impact:
            all_symbols.add(s.symbol)

    comparison = []
    for symbol in sorted(all_symbols):
        impacts: dict[str, float] = {}
        for r in results:
            for s in r.per_stock_impact:
                if s.symbol == symbol:
                    impacts[r.scenario.id] = s.change_pct
        comparison.append({"symbol": symbol, "impacts": impacts})

    return comparison
