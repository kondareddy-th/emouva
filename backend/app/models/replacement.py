"""
Pydantic models for the Underperformer Replacement pipeline.

8-stage semi-deterministic pipeline:
  1. Underperformance detection
  2. Thesis health score
  3. Hold gate
  4. Candidate filtering
  5. Multi-factor scoring
  6. Portfolio context adjustment
  7. ETF alternative
  8. LLM narrative
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    """Request to review a holding for potential replacement."""
    ticker: str = Field(..., description="Ticker to review (e.g. INTC)")
    cost_basis: float | None = Field(None, description="User's average cost per share")
    shares: float | None = Field(None, description="Number of shares held")
    portfolio_tickers: list[str] | None = Field(None, description="Other tickers in portfolio (for context)")


# ── Stage 1: Underperformance ────────────────────────────────────────

class PerformanceComparison(BaseModel):
    period: str  # "3m", "6m", "1y"
    stock_return: float
    sector_return: float
    gap: float  # stock_return - sector_return
    benchmark_return: float | None = None


class UnderperformanceResult(BaseModel):
    ticker: str
    sector: str
    sector_etf: str
    comparisons: list[PerformanceComparison]
    severity: Literal["none", "early_warning", "confirmed", "severe"]
    user_pnl_pct: float | None = None
    user_pnl_dollar: float | None = None
    summary: str  # "INTC is down 15% vs sector +8% over 6 months"


# ── Stage 2: Thesis Health ───────────────────────────────────────────

class ThesisSignal(BaseModel):
    name: str
    weight: float  # 0-1
    status: Literal["green", "yellow", "red"]
    score: float  # normalized 0-100
    detail: str  # human-readable explanation


class ThesisHealthResult(BaseModel):
    ticker: str
    composite_score: float  # 1-10
    signals: list[ThesisSignal]
    negative_count: int
    total_count: int
    f_score: int  # Piotroski F-Score 0-9
    verdict: Literal["healthy", "mixed", "stressed", "broken"]


# ── Stage 3: Hold Gate ───────────────────────────────────────────────

class HoldCondition(BaseModel):
    name: str
    triggered: bool
    reason: str


class HoldGateResult(BaseModel):
    should_hold: bool
    conditions: list[HoldCondition]
    hold_reasons: list[str]  # human-readable reasons to hold
    review_in_days: int | None = None  # suggest re-check


# ── Stage 5: Candidate Scoring ───────────────────────────────────────

class FactorScores(BaseModel):
    momentum: float = 0  # 0-100 percentile
    quality: float = 0
    growth: float = 0
    value: float = 0
    risk: float = 0
    analyst: float = 0


class ScoredCandidate(BaseModel):
    ticker: str
    name: str
    sector: str
    industry: str
    composite_score: float  # 0-100
    factors: FactorScores
    # Key metrics for comparison table
    revenue_yoy: float | None = None
    eps_growth: float | None = None
    return_6m: float | None = None
    f_score: int | None = None
    forward_pe: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    market_cap: float | None = None


# ── Stage 7: ETF Alternative ────────────────────────────────────────

class ETFAlternative(BaseModel):
    ticker: str
    name: str
    expense_ratio: float
    top_holdings: list[str]  # top 5 tickers
    return_1y: float | None = None
    return_3y: float | None = None
    is_sub_industry: bool = False  # True if sub-industry ETF, False if sector
    annual_cost_on_position: float | None = None  # ER × position size


# ── Stage 8: LLM Narrative ──────────────────────────────────────────

class ReplacementNarrative(BaseModel):
    current_assessment: str  # max ~150 words
    why_better: dict[str, str]  # ticker -> explanation
    etf_case: str  # why the ETF is a good option
    key_risks: dict[str, str]  # ticker -> risk
    confidence: Literal["high", "medium", "low"]
    fresh_money_test: str  # "If you had $X cash, would you buy TICKER?"


# ── Full Response ────────────────────────────────────────────────────

class TaxInfo(BaseModel):
    unrealized_gain: float | None = None
    holding_period_days: int | None = None
    is_long_term: bool | None = None
    days_to_long_term: int | None = None
    estimated_tax_savings: float | None = None
    wash_sale_risk: bool = False


class ReviewResponse(BaseModel):
    """Complete response from the 8-stage replacement pipeline."""
    ticker: str
    company_name: str

    # Stage 1
    underperformance: UnderperformanceResult

    # Stage 2
    thesis_health: ThesisHealthResult

    # Stage 3
    hold_gate: HoldGateResult

    # Stages 4-6 (only if hold_gate.should_hold is False)
    replacements: list[ScoredCandidate] = []  # top 3

    # Stage 7
    etf_alternative: ETFAlternative | None = None

    # Stage 8
    narrative: ReplacementNarrative | None = None

    # Tax info
    tax_info: TaxInfo | None = None

    # Metadata
    computed_at: datetime = Field(default_factory=datetime.utcnow)
    pipeline_ms: int = 0  # total computation time
    disclaimer: str = (
        "This analysis reflects current data and historical patterns. "
        "It is not a recommendation to buy or sell any security. "
        "Past performance does not predict future results. "
        "Consider consulting a qualified financial advisor."
    )
