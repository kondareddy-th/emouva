from pydantic import BaseModel, Field


class BriefAlert(BaseModel):
    type: str = Field(description="Alert category: rebalance | tax_harvest | thesis_break | risk | opportunity | overvalued | undervalued")
    severity: str = Field(description="info | warning | critical")
    title: str
    description: str
    action: str | None = Field(default=None, description="Suggested action")


class StockVerdict(BaseModel):
    symbol: str
    verdict: str = Field(description="strong_hold | hold | watch | trim | sell")
    quality_score: int = Field(default=5, ge=1, le=10, description="Overall quality 1-10")
    thesis: str = Field(default="", description="1-2 sentence investment thesis")
    concerns: str = Field(default="", description="Key risk or concern")
    action: str = Field(default="", description="Recommended action")


class PortfolioAnalysisRequest(BaseModel):
    portfolio_context: str | None = Field(
        default=None,
        description="Optional context (e.g. 'I want more dividend income', 'Concerned about tech concentration')",
    )


class PortfolioAnalysisResponse(BaseModel):
    summary: str = Field(description="2-3 sentence executive summary")
    alerts: list[BriefAlert]
    stock_analyses: list[StockVerdict] = Field(default_factory=list, description="Per-stock analysis and verdicts")
    market_context: str = Field(description="Macro outlook relevant to this portfolio")
    raw_brief: str = Field(description="Full AI-generated analysis text")


# Backward compatibility aliases
DailyBriefRequest = PortfolioAnalysisRequest
DailyBriefResponse = PortfolioAnalysisResponse
