"""
Stock Validity Scorer — scores each stock's investment validity weekly.
Uses existing _build_enrichment() data + Claude to produce a composite score.
Persists scores in the DB for week-over-week tracking.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import StockScore
from app.models.scores import (
    ScoreBreakdown,
    ScoreDetail,
    StockScoreItem,
    StockScoreChange,
)

logger = logging.getLogger(__name__)


def _current_week_label() -> str:
    """ISO week label, e.g. '2026-W11'."""
    now = datetime.utcnow()
    return f"{now.isocalendar()[0]}-W{now.isocalendar()[1]:02d}"


STOCK_SCORER_SYSTEM = """You are a quantitative equity analyst producing a weekly stock validity score.
The user owns this stock as a long-term (10-15 year) investment. Your job is to assess whether the
investment thesis is STILL VALID this week based on the latest data.

You will be provided with real-time financial data. Use ONLY the provided figures.

Score the stock across 4 dimensions (each 0-100):

1. **fundamental_score** (0-100): Business quality right now.
   - Margin trends (expanding = good, contracting = bad)
   - Revenue/earnings growth trajectory
   - Cash flow quality and consistency
   - Balance sheet strength (debt levels, current ratio)
   - ROE/ROA trends
   Score 80+ = excellent fundamentals, 60-79 = solid, 40-59 = mixed, <40 = deteriorating

2. **valuation_score** (0-100): How attractive is the current price?
   - P/E vs 5-year average and sector peers
   - PEG ratio (growth-adjusted valuation)
   - Price vs analyst targets (discount = good)
   - EV/EBITDA, P/S, P/B relative to peers
   Score 80+ = very attractive, 60-79 = fair, 40-59 = fully valued, <40 = overvalued

3. **thesis_score** (0-100): Is the original investment thesis intact?
   - Are the core growth drivers still working?
   - Any structural changes to the business or industry?
   - Management execution on stated strategy
   - Competitive position maintained/improved?
   Score 80+ = thesis strengthening, 60-79 = intact, 40-59 = cracks showing, <40 = thesis breaking

4. **momentum_score** (0-100): Near-term market sentiment and trajectory.
   - Price vs 50-day and 200-day moving averages
   - Analyst rating distribution and recent revisions
   - Insider buying/selling signals
   - Short interest trends
   Score 80+ = strong positive momentum, 60-79 = neutral-positive, 40-59 = neutral, <40 = negative

Also provide:
- **validity_score**: Weighted composite = 30% fundamental + 25% valuation + 30% thesis + 15% momentum
- **verdict**: One of: strong_buy | hold | watch | trim | sell
  - strong_buy: score >= 75, thesis strengthening
  - hold: score 55-74, thesis intact
  - watch: score 40-54, some concerns
  - trim: score 25-39, thesis weakening
  - sell: score < 25, thesis broken
- **thesis_summary**: 1-2 sentence current thesis assessment
- **concerns**: Key risk or concern right now
- **key_changes**: What changed since last week (if prior score context provided, otherwise "Initial scoring")
- **details**: Object with fundamental_notes, valuation_notes, thesis_notes, momentum_notes (1-2 sentences each), catalysts (list of 2-3), risks (list of 2-3)

Respond in STRICT JSON format:
```json
{
  "validity_score": 72,
  "fundamental_score": 78,
  "valuation_score": 65,
  "thesis_score": 75,
  "momentum_score": 68,
  "verdict": "hold",
  "thesis_summary": "...",
  "concerns": "...",
  "key_changes": "...",
  "details": {
    "fundamental_notes": "...",
    "valuation_notes": "...",
    "thesis_notes": "...",
    "momentum_notes": "...",
    "catalysts": ["...", "..."],
    "risks": ["...", "..."]
  }
}
```"""


async def score_stock(
    symbol: str,
    api_key: str,
    model: str | None = None,
    prior_score: StockScore | None = None,
) -> dict:
    """Score a single stock using enrichment data + Claude.

    Returns parsed JSON dict with scores, verdict, and details.
    """
    from app.services.claude import _build_enrichment, _call_claude

    # Fetch fresh enrichment data (sync I/O → thread pool)
    enrichment_text, current_price = await asyncio.to_thread(
        _build_enrichment, symbol, True
    )

    # Build prompt with optional prior score context
    parts = [f"Score the following stock: {symbol}\n"]
    parts.append(enrichment_text)

    if prior_score:
        parts.append(f"\n--- Prior Week Score ({prior_score.week_label}) ---")
        parts.append(f"Validity: {prior_score.validity_score}/100")
        parts.append(f"Fundamental: {prior_score.fundamental_score}, Valuation: {prior_score.valuation_score}")
        parts.append(f"Thesis: {prior_score.thesis_score}, Momentum: {prior_score.momentum_score}")
        parts.append(f"Verdict: {prior_score.verdict}")
        parts.append(f"Prior thesis: {prior_score.thesis_summary}")
        parts.append(f"Prior concerns: {prior_score.concerns}")
        parts.append("\nCompare against the prior week and note what changed in key_changes.")
    else:
        parts.append('\nThis is the FIRST scoring for this stock. Set key_changes to "Initial scoring".')

    user_message = "\n".join(parts)

    raw = await _call_claude(
        system=STOCK_SCORER_SYSTEM,
        user_message=user_message,
        api_key=api_key,
        max_tokens=2048,
        model=model,
    )

    # Parse JSON from response
    from app.services.claude import _parse_json_robust
    result = _parse_json_robust(raw)
    return result


async def score_portfolio(
    symbols: list[str],
    user_id: str,
    api_key: str,
    model: str | None = None,
    db: AsyncSession | None = None,
) -> list[StockScoreItem]:
    """Score multiple stocks and persist results.

    Args:
        symbols: List of ticker symbols to score
        user_id: UUID string of the user
        api_key: Anthropic API key
        model: Claude model to use
        db: Optional async DB session for persistence
    """
    week = _current_week_label()
    results: list[StockScoreItem] = []

    # Fetch prior scores for all symbols (most recent per symbol)
    prior_scores: dict[str, StockScore] = {}
    if db:
        prior_week = _previous_week_label()
        stmt = select(StockScore).where(
            and_(
                StockScore.user_id == user_id,
                StockScore.symbol.in_(symbols),
                StockScore.week_label == prior_week,
            )
        )
        rows = await db.execute(stmt)
        for row in rows.scalars():
            prior_scores[row.symbol] = row

    # Score each stock (sequentially to avoid API rate limits)
    for symbol in symbols:
        try:
            logger.info("Scoring %s for week %s", symbol, week)
            prior = prior_scores.get(symbol)
            score_data = await score_stock(symbol, api_key, model, prior)

            # Get company name from enrichment
            company_name = score_data.get("company_name", symbol)
            if not company_name or company_name == symbol:
                try:
                    from app.services.market_data import get_company_info
                    info = await asyncio.to_thread(get_company_info, symbol)
                    company_name = info.get("name", symbol)
                except Exception:
                    company_name = symbol

            breakdown = ScoreBreakdown(
                fundamental=_clamp(score_data.get("fundamental_score", 50)),
                valuation=_clamp(score_data.get("valuation_score", 50)),
                thesis=_clamp(score_data.get("thesis_score", 50)),
                momentum=_clamp(score_data.get("momentum_score", 50)),
            )

            details_raw = score_data.get("details", {})
            details = ScoreDetail(
                fundamental_notes=details_raw.get("fundamental_notes", ""),
                valuation_notes=details_raw.get("valuation_notes", ""),
                thesis_notes=details_raw.get("thesis_notes", ""),
                momentum_notes=details_raw.get("momentum_notes", ""),
                catalysts=details_raw.get("catalysts", []),
                risks=details_raw.get("risks", []),
            )

            item = StockScoreItem(
                symbol=symbol,
                company_name=company_name,
                validity_score=_clamp(score_data.get("validity_score", 50)),
                breakdown=breakdown,
                verdict=score_data.get("verdict", "hold"),
                thesis_summary=score_data.get("thesis_summary", ""),
                concerns=score_data.get("concerns", ""),
                key_changes=score_data.get("key_changes", "Initial scoring"),
                details=details,
                week_label=week,
                scored_at=datetime.utcnow().isoformat(),
            )
            results.append(item)

            # Persist to DB
            if db:
                await _persist_score(db, user_id, item)

        except Exception as e:
            logger.error("Failed to score %s: %s", symbol, e)
            # Return a placeholder so the user knows it failed
            results.append(StockScoreItem(
                symbol=symbol,
                validity_score=0,
                breakdown=ScoreBreakdown(fundamental=0, valuation=0, thesis=0, momentum=0),
                verdict="watch",
                thesis_summary=f"Scoring failed: {e}",
                concerns="Unable to score — retry later",
                key_changes="",
                week_label=week,
                scored_at=datetime.utcnow().isoformat(),
            ))

    return results


async def get_latest_scores(
    user_id: str,
    db: AsyncSession,
) -> list[StockScoreItem]:
    """Get the most recent scores for all stocks for this user."""
    # Get the most recent week_label that has scores
    stmt = (
        select(StockScore)
        .where(StockScore.user_id == user_id)
        .order_by(StockScore.scored_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    latest = result.scalar_one_or_none()
    if not latest:
        return []

    # Get all scores for that week
    stmt = (
        select(StockScore)
        .where(
            and_(
                StockScore.user_id == user_id,
                StockScore.week_label == latest.week_label,
            )
        )
        .order_by(StockScore.validity_score.desc())
    )
    result = await db.execute(stmt)
    return [_db_to_item(row) for row in result.scalars()]


async def get_score_history(
    user_id: str,
    symbol: str,
    db: AsyncSession,
    limit: int = 12,
) -> list[StockScoreItem]:
    """Get score history for a specific stock (most recent first)."""
    stmt = (
        select(StockScore)
        .where(
            and_(
                StockScore.user_id == user_id,
                StockScore.symbol == symbol,
            )
        )
        .order_by(StockScore.scored_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return [_db_to_item(row) for row in result.scalars()]


async def get_score_changes(
    user_id: str,
    db: AsyncSession,
) -> list[StockScoreChange]:
    """Get week-over-week changes for all scored stocks."""
    week = _current_week_label()
    prior_week = _previous_week_label()

    # Fetch current and prior week scores
    current_stmt = select(StockScore).where(
        and_(StockScore.user_id == user_id, StockScore.week_label == week)
    )
    prior_stmt = select(StockScore).where(
        and_(StockScore.user_id == user_id, StockScore.week_label == prior_week)
    )

    current_result = await db.execute(current_stmt)
    prior_result = await db.execute(prior_stmt)

    current_map = {r.symbol: r for r in current_result.scalars()}
    prior_map = {r.symbol: r for r in prior_result.scalars()}

    changes: list[StockScoreChange] = []
    all_symbols = set(current_map.keys()) | set(prior_map.keys())

    for sym in sorted(all_symbols):
        curr = current_map.get(sym)
        prev = prior_map.get(sym)

        if curr:
            changes.append(StockScoreChange(
                symbol=sym,
                company_name=curr.company_name,
                current_score=curr.validity_score,
                previous_score=prev.validity_score if prev else None,
                score_delta=(curr.validity_score - prev.validity_score) if prev else None,
                current_verdict=curr.verdict,
                previous_verdict=prev.verdict if prev else None,
                verdict_changed=(prev is not None and curr.verdict != prev.verdict),
                key_changes=curr.key_changes,
            ))
        elif prev:
            # Stock was scored last week but not this week
            changes.append(StockScoreChange(
                symbol=sym,
                company_name=prev.company_name,
                current_score=prev.validity_score,
                previous_score=prev.validity_score,
                score_delta=None,
                current_verdict=prev.verdict,
                previous_verdict=prev.verdict,
                verdict_changed=False,
                key_changes="Not scored this week",
            ))

    return changes


# ── Helpers ─────────────────────────────────────────────────────


def _clamp(value: int | float, lo: int = 0, hi: int = 100) -> int:
    """Clamp value to [lo, hi] and cast to int."""
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError):
        return 50


def _previous_week_label() -> str:
    """ISO week label for the previous week."""
    last_week = datetime.utcnow() - timedelta(days=7)
    return f"{last_week.isocalendar()[0]}-W{last_week.isocalendar()[1]:02d}"


async def _persist_score(db: AsyncSession, user_id: str, item: StockScoreItem) -> None:
    """Insert or update score in DB for this user/symbol/week."""
    # Check if already exists (upsert)
    stmt = select(StockScore).where(
        and_(
            StockScore.user_id == user_id,
            StockScore.symbol == item.symbol,
            StockScore.week_label == item.week_label,
        )
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()

    if existing:
        existing.validity_score = item.validity_score
        existing.fundamental_score = item.breakdown.fundamental
        existing.valuation_score = item.breakdown.valuation
        existing.thesis_score = item.breakdown.thesis
        existing.momentum_score = item.breakdown.momentum
        existing.verdict = item.verdict
        existing.thesis_summary = item.thesis_summary
        existing.concerns = item.concerns
        existing.key_changes = item.key_changes
        existing.company_name = item.company_name
        existing.score_details = item.details.model_dump() if item.details else None
        existing.scored_at = datetime.utcnow()
    else:
        row = StockScore(
            user_id=user_id,
            symbol=item.symbol,
            company_name=item.company_name,
            validity_score=item.validity_score,
            fundamental_score=item.breakdown.fundamental,
            valuation_score=item.breakdown.valuation,
            thesis_score=item.breakdown.thesis,
            momentum_score=item.breakdown.momentum,
            verdict=item.verdict,
            thesis_summary=item.thesis_summary,
            concerns=item.concerns,
            key_changes=item.key_changes,
            score_details=item.details.model_dump() if item.details else None,
            week_label=item.week_label,
        )
        db.add(row)

    await db.commit()


def _db_to_item(row: StockScore) -> StockScoreItem:
    """Convert a DB row to a Pydantic StockScoreItem."""
    details = None
    if row.score_details:
        details = ScoreDetail(**row.score_details)

    return StockScoreItem(
        symbol=row.symbol,
        company_name=row.company_name,
        validity_score=row.validity_score,
        breakdown=ScoreBreakdown(
            fundamental=row.fundamental_score,
            valuation=row.valuation_score,
            thesis=row.thesis_score,
            momentum=row.momentum_score,
        ),
        verdict=row.verdict,
        thesis_summary=row.thesis_summary,
        concerns=row.concerns,
        key_changes=row.key_changes,
        details=details,
        week_label=row.week_label,
        scored_at=row.scored_at.isoformat() if row.scored_at else "",
    )
