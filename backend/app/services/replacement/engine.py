"""
Replacement Engine — orchestrates the 8-stage pipeline.

Pipeline flow:
  1. Underperformance Detection → severity rating
  2. Thesis Health Score → 6 signals, composite 1-10
  3. Hold Gate → 5 conditions, pass/hold decision
  4. Candidate Filtering → GICS peers, quality gate (if not holding)
  5. Multi-Factor Scoring → 6-factor composite, top 3
  6. Portfolio Context → overlap, correlation, concentration
  7. ETF Alternative → always included
  8. LLM Narrative → constrained explanation (if API key provided)

The algorithm does ALL stock picking. The LLM only explains.
"""

from __future__ import annotations

import asyncio
import logging
import time

import yfinance as yf

from app.models.replacement import (
    ReviewRequest,
    ReviewResponse,
    TaxInfo,
)
from app.services.replacement.underperformance import detect_underperformance
from app.services.replacement.thesis_health import compute_thesis_health
from app.services.replacement.hold_gate import evaluate_hold_gate
from app.services.replacement.candidates import find_candidates
from app.services.replacement.scoring import score_candidates
from app.services.replacement.portfolio_context import adjust_for_portfolio
from app.services.replacement.etf_mapping import get_etf_alternative
from app.services.replacement.narrative import generate_narrative

logger = logging.getLogger(__name__)


def _get_stock_info(ticker: str) -> dict:
    """Fetch basic info from yfinance."""
    try:
        info = yf.Ticker(ticker).info or {}
        return info
    except Exception:
        return {}


def _compute_tax_info(
    cost_basis: float | None,
    current_price: float | None,
    shares: float | None,
    holding_period_days: int | None = None,
) -> TaxInfo | None:
    """Compute tax implications of selling."""
    if not cost_basis or not current_price:
        return None

    unrealized_gain = (current_price - cost_basis) * (shares or 1)
    is_loss = unrealized_gain < 0

    is_long_term = None
    days_to_lt = None
    if holding_period_days is not None:
        is_long_term = holding_period_days >= 365
        days_to_lt = max(0, 365 - holding_period_days)

    # Estimate tax savings from loss harvesting (assume 30% marginal rate)
    estimated_savings = None
    if is_loss:
        estimated_savings = round(abs(unrealized_gain) * 0.30, 2)

    return TaxInfo(
        unrealized_gain=round(unrealized_gain, 2),
        holding_period_days=holding_period_days,
        is_long_term=is_long_term,
        days_to_long_term=days_to_lt,
        estimated_tax_savings=estimated_savings,
        wash_sale_risk=False,  # Individual stocks → different companies → no wash sale
    )


async def run_replacement_pipeline(
    request: ReviewRequest,
    api_key: str | None = None,
    model: str = "claude-sonnet-4-5-20250514",
) -> ReviewResponse:
    """Execute the full 8-stage replacement pipeline.

    Stages 1-3 always run (Stage 1 & 2 concurrently). Stages 4-8 only run if hold gate passes.
    Stage 8 (LLM narrative) only runs if api_key is provided.
    """
    start_ms = time.time()
    ticker = request.ticker.upper()

    # ── Fetch basic stock info (shared across all stages) ────────
    info = await asyncio.to_thread(_get_stock_info, ticker)
    company_name = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector", "Technology")
    industry = info.get("industry", "Unknown")
    market_cap = info.get("marketCap")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")

    # ── Stage 1 & 2 run concurrently (independent) ───────────────
    logger.info("Stage 1+2: Running underperformance + thesis health concurrently for %s", ticker)
    underperf_task = asyncio.to_thread(
        detect_underperformance,
        ticker, sector,
        request.cost_basis, request.shares, current_price,
    )
    thesis_task = asyncio.to_thread(compute_thesis_health, ticker, info)

    underperformance, thesis_health = await asyncio.gather(underperf_task, thesis_task)

    # ── Stage 3: Hold Gate ───────────────────────────────────────
    logger.info("Stage 3: Evaluating hold gate for %s", ticker)
    hold_gate = await asyncio.to_thread(
        evaluate_hold_gate,
        ticker, sector, thesis_health, info,
        request.cost_basis, current_price, None,  # holding_period_days not yet known
        None, None,  # replacement scores not yet known
    )

    # Tax info
    tax_info = _compute_tax_info(request.cost_basis, current_price, request.shares)

    # If hold gate triggers AND thesis is not severely broken, return hold recommendation
    if hold_gate.should_hold and thesis_health.verdict not in ("broken",):
        elapsed_ms = int((time.time() - start_ms) * 1000)
        return ReviewResponse(
            ticker=ticker,
            company_name=company_name,
            underperformance=underperformance,
            thesis_health=thesis_health,
            hold_gate=hold_gate,
            replacements=[],
            etf_alternative=None,
            narrative=None,
            tax_info=tax_info,
            pipeline_ms=elapsed_ms,
        )

    # ── Stage 4: Find Replacement Candidates ─────────────────────
    logger.info("Stage 4: Finding candidates for %s (%s / %s)", ticker, sector, industry)
    raw_candidates = await asyncio.to_thread(
        find_candidates, ticker, sector, industry, market_cap,
    )

    # ── Stage 5: Score & Rank Candidates ─────────────────────────
    logger.info("Stage 5: Scoring %d candidates", len(raw_candidates))
    scored, original_score = await asyncio.to_thread(
        score_candidates, raw_candidates, ticker, 5,  # get top 5, trim to 3 after context
    )

    # ── Re-evaluate Hold Gate with replacement scores ────────────
    if original_score is not None and scored:
        best_score = scored[0].composite_score
        hold_gate_recheck = await asyncio.to_thread(
            evaluate_hold_gate,
            ticker, sector, thesis_health, info,
            request.cost_basis, current_price, None,
            best_score, original_score,
        )
        # If "no better alternative" triggers now, update hold gate
        if hold_gate_recheck.should_hold and not hold_gate.should_hold:
            hold_gate = hold_gate_recheck
            elapsed_ms = int((time.time() - start_ms) * 1000)
            return ReviewResponse(
                ticker=ticker,
                company_name=company_name,
                underperformance=underperformance,
                thesis_health=thesis_health,
                hold_gate=hold_gate,
                replacements=[],
                etf_alternative=None,
                narrative=None,
                tax_info=tax_info,
                pipeline_ms=elapsed_ms,
            )

    # ── Stage 6: Portfolio Context Adjustment ────────────────────
    if request.portfolio_tickers:
        logger.info("Stage 6: Adjusting for portfolio context")
        scored = await asyncio.to_thread(
            adjust_for_portfolio,
            scored,
            request.portfolio_tickers,
            sector,
        )

    # Trim to top 3
    replacements = scored[:3]

    # ── Stage 7: ETF Alternative ─────────────────────────────────
    logger.info("Stage 7: Getting ETF alternative")
    position_value = None
    if request.shares and current_price:
        position_value = request.shares * current_price

    etf_alternative = get_etf_alternative(sector, industry, position_value)

    # ── Stage 8: LLM Narrative ───────────────────────────────────
    narrative = None
    if api_key and replacements:
        logger.info("Stage 8: Generating narrative")
        try:
            narrative = await generate_narrative(
                ticker, underperformance, thesis_health,
                replacements, etf_alternative,
                api_key, model, position_value,
            )
        except Exception:
            logger.exception("Stage 8: Narrative generation failed, using fallback")
            from app.services.replacement.narrative import _fallback_narrative
            narrative = _fallback_narrative(
                ticker, thesis_health, replacements, etf_alternative, position_value,
            )

    elapsed_ms = int((time.time() - start_ms) * 1000)

    return ReviewResponse(
        ticker=ticker,
        company_name=company_name,
        underperformance=underperformance,
        thesis_health=thesis_health,
        hold_gate=hold_gate,
        replacements=replacements,
        etf_alternative=etf_alternative,
        narrative=narrative,
        tax_info=tax_info,
        pipeline_ms=elapsed_ms,
    )
