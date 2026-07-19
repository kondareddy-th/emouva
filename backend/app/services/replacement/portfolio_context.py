
"""
Stage 6: Portfolio Context Adjustment

Adjusts replacement candidates based on the user's existing portfolio:
  - Remove stocks already held
  - Penalize high correlation (>0.85) with existing holdings
  - Boost cross-sector candidates when concentrated (>30% in sector)

100% deterministic — no LLM involvement.
"""

from __future__ import annotations

import logging

import yfinance as yf

from app.models.replacement import ScoredCandidate

logger = logging.getLogger(__name__)

CORRELATION_PENALTY = 15  # points deducted for >0.85 correlation
DIVERSIFICATION_BONUS = 10  # points added for cross-sector when concentrated
CONCENTRATION_THRESHOLD = 0.30  # 30% in one sector = concentrated


def _batch_correlations(
    candidate_tickers: list[str],
    held_tickers: list[str],
    period: str = "1y",
) -> dict[str, dict[str, float]]:
    """Batch-download all tickers and compute pairwise correlations.

    Returns {candidate_ticker: {held_ticker: correlation}}.
    """
    all_tickers = list(set(candidate_tickers + held_tickers))
    if len(all_tickers) < 2:
        return {}

    try:
        data = yf.download(all_tickers, period=period, progress=False, threads=True)
        if data.empty:
            return {}

        if len(all_tickers) == 1:
            return {}

        close = data.get("Close")
        if close is None or close.empty or len(close) < 30:
            return {}

        returns = close.pct_change().dropna()
        if len(returns) < 20:
            return {}

        corr_matrix = returns.corr()

        results: dict[str, dict[str, float]] = {}
        for ct in candidate_tickers:
            results[ct] = {}
            if ct not in corr_matrix.columns:
                continue
            for ht in held_tickers:
                if ht not in corr_matrix.columns or ht == ct:
                    continue
                val = corr_matrix.loc[ct, ht]
                if val is not None:
                    results[ct][ht] = float(val)
        return results

    except Exception:
        logger.debug("Batch correlation download failed")
        return {}


def adjust_for_portfolio(
    candidates: list[ScoredCandidate],
    portfolio_tickers: list[str],
    original_sector: str,
    sector_weights: dict[str, float] | None = None,
) -> list[ScoredCandidate]:
    """Run Stage 6: adjust candidate scores based on portfolio context.

    Modifies candidates in-place and re-sorts by adjusted score.
    """
    if not candidates:
        return candidates

    held_set = {t.upper() for t in portfolio_tickers} if portfolio_tickers else set()

    # Step 1: Remove stocks already in portfolio
    adjusted = [c for c in candidates if c.ticker.upper() not in held_set]
    if not adjusted:
        adjusted = candidates  # Don't eliminate everything

    # Step 2: Penalize high correlation with existing holdings
    # Single batch download for all tickers instead of per-pair
    candidate_tickers = [c.ticker for c in adjusted]
    held_list = list(held_set)[:10]  # Limit to 10 holdings for perf
    if candidate_tickers and held_list:
        corr_map = _batch_correlations(candidate_tickers, held_list)
        for candidate in adjusted:
            held_corrs = corr_map.get(candidate.ticker, {})
            for ht, corr_val in held_corrs.items():
                if corr_val > 0.85:
                    candidate.composite_score = max(0, candidate.composite_score - CORRELATION_PENALTY)
                    logger.debug(
                        "Portfolio context: %s penalized %d pts (corr %.2f with %s)",
                        candidate.ticker, CORRELATION_PENALTY, corr_val, ht,
                    )
                    break  # One penalty is enough

    # Step 3: Boost cross-sector if portfolio is concentrated
    if sector_weights:
        original_weight = sector_weights.get(original_sector, 0)
        if original_weight > CONCENTRATION_THRESHOLD:
            for candidate in adjusted:
                if candidate.sector != original_sector:
                    candidate.composite_score = min(100, candidate.composite_score + DIVERSIFICATION_BONUS)
                    logger.debug(
                        "Portfolio context: %s boosted %d pts (cross-sector diversification)",
                        candidate.ticker, DIVERSIFICATION_BONUS,
                    )

    # Re-sort by adjusted score
    adjusted.sort(key=lambda c: c.composite_score, reverse=True)

    return adjusted
