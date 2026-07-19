from datetime import datetime

from pydantic import BaseModel, Field


# ── Request Models ──────────────────────────────────────────────


class PortfolioHolding(BaseModel):
    symbol: str
    shares: float
    current_price: float | None = None  # If None, fetched live


class StressTestRequest(BaseModel):
    portfolio: list[PortfolioHolding] | None = None  # None = use Robinhood
    scenario_id: str | None = None
    custom_scenario: str | None = None
    include_correlation_adjustment: bool = True
    confidence_level: str = Field(default="medium", pattern=r"^(low|medium|high)$")


# ── Response Models ─────────────────────────────────────────────


class ScenarioInfo(BaseModel):
    id: str
    name: str
    description: str
    category: str
    severity: int
    sp500_impact: float | None = None
    duration_months: int | None = None
    tags: list[str] = []
    version: str


class StockImpact(BaseModel):
    symbol: str
    name: str
    sector: str
    current_value: float
    stressed_value: float
    change_pct: float
    change_usd: float
    weight_pct: float  # % of portfolio
    sensitivity_factors: list[str] = []
    historical_actual: float | None = None  # actual move if historical scenario


class PortfolioImpactSummary(BaseModel):
    total_value_before: float
    total_value_after: float
    total_change_pct: float
    total_change_usd: float
    worst_day_estimate_pct: float
    recovery_time_months: int | None = None


class CorrelationAdjustment(BaseModel):
    applied: bool
    normal_portfolio_correlation: float
    stressed_portfolio_correlation: float
    additional_impact_pct: float


class ConfidenceMetadata(BaseModel):
    level: str
    methodology: str  # "sector_factor_model" | "historical_replay" | "llm_estimated"
    data_coverage_pct: float
    disclaimer: str


class StressTestResult(BaseModel):
    result_id: str
    scenario: ScenarioInfo
    portfolio_impact: PortfolioImpactSummary
    per_stock_impact: list[StockImpact]
    correlation_adjustment: CorrelationAdjustment | None = None
    confidence: ConfidenceMetadata
    computed_at: datetime
    cache_key: str
    cached_until: datetime


# ── Scenario List ───────────────────────────────────────────────


class ScenarioListItem(BaseModel):
    id: str
    name: str
    category: str
    severity: int
    description: str
    sp500_impact: float | None = None
    duration_months: int | None = None
    tags: list[str] = []
    version: str


class ScenarioListResponse(BaseModel):
    scenarios: list[ScenarioListItem]
    categories: list[str]
    total: int
    version: str
