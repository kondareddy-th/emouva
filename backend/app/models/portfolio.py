from pydantic import BaseModel, Field


class Position(BaseModel):
    symbol: str
    name: str
    shares: float
    avg_cost: float
    current_price: float
    previous_close: float
    sector: str = "Unknown"
    sparkline: list[float] = []
    conviction: int = Field(ge=1, le=5, default=3)
    equity: float = 0.0
    percent_change: float = 0.0
    equity_change: float = 0.0

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price

    @property
    def day_change_pct(self) -> float:
        if self.previous_close == 0:
            return 0.0
        return ((self.current_price - self.previous_close) / self.previous_close) * 100


class PortfolioSummary(BaseModel):
    total_value: float
    daily_change: float
    daily_change_pct: float
    total_gain: float
    total_gain_pct: float
    buying_power: float
    risk_score: int
    source: str = "disconnected"


class PortfolioHistoryPoint(BaseModel):
    date: str
    value: float


class FactorExposure(BaseModel):
    name: str
    exposure: int
    status: str = Field(pattern=r"^(ok|high|low)$")


class StressTest(BaseModel):
    scenario: str
    impact: float


class CorrelationAlert(BaseModel):
    pair: list[str]
    correlation: float


class DrawdownPoint(BaseModel):
    date: str
    drawdown: float


class SectorWeight(BaseModel):
    sector: str
    value: float
    weight: float


class Concentration(BaseModel):
    hhi: float
    top5_pct: float


class ConcentrationBreakdown(BaseModel):
    label: str
    value: float
    weight: float


class ConcentrationDimension(BaseModel):
    breakdown: list[ConcentrationBreakdown] = []
    hhi: float = 0.0
    top_holding_pct: float = 0.0
    rating: str = "green"  # green | yellow | red


class ConcentrationRisk(BaseModel):
    score: int = 0
    rating: str = "green"  # green | yellow | red
    dimensions: dict[str, ConcentrationDimension] = {}


class RiskData(BaseModel):
    score: int
    daily_var_95: float
    monthly_cvar_95: float
    risk_budget_used: float
    portfolio_volatility: float = 0.0
    max_drawdown: float = 0.0
    drawdown_series: list[DrawdownPoint] = []
    sector_weights: list[SectorWeight] = []
    concentration: Concentration = Concentration(hhi=0.0, top5_pct=0.0)
    factors: list[FactorExposure]
    stress_tests: list[StressTest]
    correlation_alerts: list[CorrelationAlert]
    concentration_risk: ConcentrationRisk = ConcentrationRisk()
    source: str = "disconnected"


# ── Market Data ────────────────────────────────────────────────


class EarningsQuarter(BaseModel):
    date: str
    revenue: float | None = None
    net_income: float | None = None
    eps: float | None = None


class EarningsResponse(BaseModel):
    symbol: str
    quarters: list[EarningsQuarter]


class CompanyInfo(BaseModel):
    symbol: str
    name: str = ""
    sector: str = "Unknown"
    industry: str = "Unknown"
    market_cap: float | None = None
    pe_ratio: float | None = None
    forward_pe: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    avg_volume: int | None = None
    description: str = ""


class NewsArticle(BaseModel):
    title: str
    publisher: str = ""
    link: str = ""
    published: str = ""
    symbol: str = ""


# ── Curated News ───────────────────────────────────────────────


class CuratedArticle(BaseModel):
    symbol: str
    title: str
    summary: str = ""
    impact: str = "neutral"
    urgency: str = "low"


class CuratedNewsResponse(BaseModel):
    articles: list[CuratedArticle]
    source: str = ""
    symbols_scanned: int = 0
    raw_headlines_count: int = 0


class SectorOpportunity(BaseModel):
    sector: str
    trend: str
    outlook: str = "cautious"
    reasoning: str = ""
    timeframe: str = "Medium-term"


class SectorAnalysisResponse(BaseModel):
    opportunities: list[SectorOpportunity]
    market_regime: str = ""
    source: str = ""


# ── Quotes ─────────────────────────────────────────────────────


class LiveQuote(BaseModel):
    symbol: str
    price: float
    previous_close: float
    change_pct: float


class QuotesResponse(BaseModel):
    quotes: list[LiveQuote]
    source: str = "disconnected"


class WatchlistItem(BaseModel):
    symbol: str
    name: str
    price: float
    change_pct: float
    sparkline: list[float] = []


class WatchlistResponse(BaseModel):
    items: list[WatchlistItem]
    source: str = "disconnected"
