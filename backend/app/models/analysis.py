from pydantic import BaseModel, Field


# ── Stock Analysis ──────────────────────────────────────────────


class StockAnalysisRequest(BaseModel):
    ticker: str = Field(
        min_length=1,
        max_length=10,
        description="Stock ticker symbol (e.g. NVDA, AAPL)",
    )
    context: str | None = Field(
        default=None,
        description="Optional additional context (e.g. recent news, specific concerns)",
    )


class ValuationRange(BaseModel):
    bear: float = Field(description="Bear case price target")
    base: float = Field(description="Base/fair value estimate")
    bull: float = Field(description="Bull case price target")
    methodology: str = Field(description="Valuation methodology used")


class QualityScore(BaseModel):
    moat: float = Field(default=0, ge=0, le=10, description="Competitive moat durability 1-10")
    management: float = Field(default=0, ge=0, le=10, description="Capital allocation track record 1-10")
    financial_health: float = Field(default=0, ge=0, le=10, description="Balance sheet and cash flow quality 1-10")
    growth_runway: float = Field(default=0, ge=0, le=10, description="Remaining growth opportunity 1-10")
    overall: float = Field(default=0, ge=0, le=10, description="Composite quality score 1-10")


class StockAnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    current_price: float | None = None
    valuation: ValuationRange
    investment_thesis: str
    bull_case: str
    bear_case: str
    key_risks: list[str]
    quality_score: QualityScore | None = None
    sector_outlook: str = ""
    sentiment_summary: str
    raw_analysis: str = Field(description="Full AI-generated report")


# ── Thesis Generation ───────────────────────────────────────────


class ThesisMetric(BaseModel):
    metric: str = Field(description="Metric name (e.g. 'Data Center Rev Growth')")
    current_value: str = Field(description="Current observed value")
    threshold: str = Field(description="Threshold that would break the thesis")
    why_it_matters: str = Field(default="", description="Why this metric is critical")
    status: str = Field(
        default="passing",
        description="passing | warning | failing",
    )


class ThesisRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    context: str | None = None


class ThesisResponse(BaseModel):
    ticker: str
    core_thesis: str
    key_drivers: list[ThesisMetric]
    bull_target: str
    bear_target: str
    conviction_signals: list[str] = []
    warning_signals: list[str] = []
    position_sizing: str = ""
    timeframe: str
    raw_analysis: str


# ── Bear Case ───────────────────────────────────────────────────


class BearCaseRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    current_thesis: str | None = Field(
        default=None,
        description="The user's current investment thesis to stress-test",
    )
    scenario: str | None = Field(
        default=None,
        description="Custom stress scenario (e.g. 'What if AI regulation passes?')",
    )


class BearCaseResponse(BaseModel):
    ticker: str
    competitive_threats: str
    valuation_concerns: str
    financial_risks: str = ""
    secular_headwinds: str = ""
    macro_risks: str = ""  # Kept for backward compat
    management_risks: str
    consensus_blindspots: str
    estimated_impact_pct: float | None = None
    stressed_price: float | None = None
    scenario_name: str = ""
    raw_analysis: str


# ── Sentiment Analysis ──────────────────────────────────────────


class SentimentScores(BaseModel):
    news: int = Field(ge=0, le=100, description="News sentiment 0-100")
    filings: int = Field(ge=0, le=100, description="Filing tone 0-100")
    insider: int = Field(ge=0, le=100, description="Insider activity 0-100")
    analyst: int = Field(ge=0, le=100, description="Analyst consensus 0-100")
    composite: int = Field(ge=0, le=100, description="Weighted composite 0-100")


class SentimentRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)


class SentimentResponse(BaseModel):
    ticker: str
    scores: SentimentScores
    summary: str
    raw_analysis: str


# ── Full Investment Report ─────────────────────────────────────


class FullReportRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=10)
    context: str | None = None


class FullReportResponse(BaseModel):
    ticker: str
    company_name: str
    current_price: float | None = None
    generated_at: str
    executive_summary: str
    valuation_analysis: str
    investment_thesis: str
    key_risks: list[str]
    catalysts: list[str]
    financial_highlights: str
    verdict: str
    confidence: str
    verdict_reasoning: str
    price_targets: dict
    raw_report: str
