from pydantic import BaseModel, Field


# ── Sub-score detail ────────────────────────────────────────────


class ScoreBreakdown(BaseModel):
    fundamental: int = Field(ge=0, le=100, description="Margins, growth, cash flow quality")
    valuation: int = Field(ge=0, le=100, description="P/E vs historical, vs peers, DCF attractiveness")
    thesis: int = Field(ge=0, le=100, description="Are original investment drivers still intact?")
    momentum: int = Field(ge=0, le=100, description="Price action, analyst sentiment shifts")


class ScoreDetail(BaseModel):
    """Structured drilldown stored in JSONB."""
    fundamental_notes: str = ""
    valuation_notes: str = ""
    thesis_notes: str = ""
    momentum_notes: str = ""
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


# ── Per-stock score ─────────────────────────────────────────────


class StockScoreItem(BaseModel):
    symbol: str
    company_name: str = ""
    validity_score: int = Field(ge=0, le=100)
    breakdown: ScoreBreakdown
    verdict: str = Field(description="strong_buy | hold | watch | trim | sell")
    thesis_summary: str = ""
    concerns: str = ""
    key_changes: str = ""
    details: ScoreDetail | None = None
    week_label: str = ""
    scored_at: str = ""  # ISO datetime


class StockScoreChange(BaseModel):
    """Week-over-week change for a stock."""
    symbol: str
    company_name: str = ""
    current_score: int
    previous_score: int | None = None
    score_delta: int | None = None
    current_verdict: str
    previous_verdict: str | None = None
    verdict_changed: bool = False
    key_changes: str = ""


# ── Request / Response ──────────────────────────────────────────


class ScoreRefreshRequest(BaseModel):
    symbols: list[str] | None = Field(
        default=None,
        description="Specific symbols to score. If null, scores all portfolio holdings.",
    )


class ScoreRefreshResponse(BaseModel):
    scores: list[StockScoreItem]
    elapsed_seconds: float
    week_label: str


class ScoreHistoryResponse(BaseModel):
    symbol: str
    history: list[StockScoreItem]


class ScoreChangesResponse(BaseModel):
    week_label: str
    changes: list[StockScoreChange]


class LatestScoresResponse(BaseModel):
    scores: list[StockScoreItem]
    week_label: str
