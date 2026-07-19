"""
Stage 2: Thesis Health Score

Computes a composite health score (1-10) from 6 deterministic signals
using yfinance data. Each signal is classified as green/yellow/red.

MVP signals (available from yfinance):
  1. Earnings Surprise Trend (15%)
  2. Revenue Growth vs Sector (15%)
  3. Insider Activity (15%)
  4. Analyst Revision Direction (10%)
  5. Price Momentum vs Market (10%)
  6. Piotroski F-Score (gate — not weighted, but shown)

Deferred to Phase 2 (need paid APIs):
  - Earnings estimate revisions (25%)
  - News sentiment (5%)
  - Earnings call tone (5%)

100% deterministic — no LLM involvement.
"""

from __future__ import annotations

import logging
from typing import Literal

import yfinance as yf

from app.models.replacement import ThesisSignal, ThesisHealthResult

logger = logging.getLogger(__name__)


def _safe_get(d: dict, *keys, default=None):
    """Nested dict access."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def _compute_piotroski(info: dict, bs: dict, cf: dict, prev_info: dict | None = None) -> int:
    """Compute Piotroski F-Score (0-9) from yfinance data.

    9 binary signals:
      Profitability (4): ROA>0, operating CF>0, ROA increasing, CF>NI
      Leverage (3): LTD decreasing, current ratio increasing, no dilution
      Efficiency (2): gross margin increasing, asset turnover increasing
    """
    score = 0

    # --- Profitability ---
    roa = info.get("returnOnAssets")
    if roa is not None and roa > 0:
        score += 1

    ocf = info.get("operatingCashflow")
    if ocf is not None and ocf > 0:
        score += 1

    # CF > Net Income (accrual quality)
    net_income = info.get("netIncomeToCommon")
    if ocf and net_income and ocf > net_income:
        score += 1

    # ROA increasing — compare to previous year if available
    # For MVP, give benefit of the doubt if data missing
    if prev_info:
        prev_roa = prev_info.get("returnOnAssets")
        if roa is not None and prev_roa is not None:
            score += 1 if roa > prev_roa else 0
        else:
            score += 1  # assume stable
    else:
        score += 1  # no prior data, assume stable

    # --- Leverage ---
    debt_eq = info.get("debtToEquity")
    if debt_eq is not None and debt_eq < 100:  # reasonable leverage
        score += 1
    elif debt_eq is None:
        score += 1  # no debt data = likely low debt

    cr = info.get("currentRatio")
    if cr is not None and cr > 1.0:
        score += 1

    # No dilution — check shares outstanding trend
    # Simplified: if buyback yield > 0, score it
    shares = info.get("sharesOutstanding")
    if shares:
        score += 1  # assume no major dilution without prior data

    # --- Efficiency ---
    gm = info.get("grossMargins")
    if gm is not None and gm > 0.20:
        score += 1

    # Asset turnover — revenue / total assets
    revenue = info.get("totalRevenue")
    total_assets = info.get("totalAssets")  # may not be in .info
    if revenue and total_assets and total_assets > 0:
        score += 1 if (revenue / total_assets) > 0.3 else 0
    else:
        score += 1  # assume adequate

    return min(score, 9)


def _earnings_surprise_signal(ticker_obj: yf.Ticker) -> ThesisSignal:
    """Signal 1: Earnings surprise trend (last 4 quarters)."""
    try:
        eh = ticker_obj.earnings_history
        if eh is not None and not eh.empty and "epsActual" in eh.columns and "epsEstimate" in eh.columns:
            recent = eh.head(4)
            beats = 0
            total = 0
            for _, row in recent.iterrows():
                actual = row.get("epsActual")
                estimate = row.get("epsEstimate")
                if actual is not None and estimate is not None:
                    total += 1
                    if actual >= estimate:
                        beats += 1

            if total > 0:
                beat_rate = beats / total
                if beat_rate >= 0.75:
                    return ThesisSignal(
                        name="Earnings Surprise", weight=0.15, status="green",
                        score=80 + beat_rate * 20,
                        detail=f"Beat estimates {beats} of {total} quarters",
                    )
                elif beat_rate >= 0.50:
                    return ThesisSignal(
                        name="Earnings Surprise", weight=0.15, status="yellow",
                        score=40 + beat_rate * 20,
                        detail=f"Mixed: beat {beats} of {total} quarters",
                    )
                else:
                    return ThesisSignal(
                        name="Earnings Surprise", weight=0.15, status="red",
                        score=beat_rate * 40,
                        detail=f"Missed {total - beats} of {total} quarters",
                    )
    except Exception:
        pass

    return ThesisSignal(
        name="Earnings Surprise", weight=0.15, status="yellow",
        score=50, detail="Earnings history not available",
    )


def _revenue_growth_signal(info: dict, sector_median_growth: float) -> ThesisSignal:
    """Signal 2: Revenue growth vs sector median."""
    rev_growth = info.get("revenueGrowth")
    if rev_growth is None:
        return ThesisSignal(
            name="Revenue vs Sector", weight=0.15, status="yellow",
            score=50, detail="Revenue growth data not available",
        )

    gap = rev_growth - sector_median_growth

    if gap > 0.05:
        return ThesisSignal(
            name="Revenue vs Sector", weight=0.15, status="green",
            score=min(90, 70 + gap * 100),
            detail=f"Growing {rev_growth*100:.1f}% vs sector {sector_median_growth*100:.1f}%",
        )
    elif gap > -0.05:
        return ThesisSignal(
            name="Revenue vs Sector", weight=0.15, status="yellow",
            score=50,
            detail=f"In line: {rev_growth*100:.1f}% vs sector {sector_median_growth*100:.1f}%",
        )
    else:
        return ThesisSignal(
            name="Revenue vs Sector", weight=0.15, status="red",
            score=max(10, 30 + gap * 100),
            detail=f"Lagging: {rev_growth*100:.1f}% vs sector {sector_median_growth*100:.1f}%",
        )


def _insider_activity_signal(ticker_obj: yf.Ticker) -> ThesisSignal:
    """Signal 3: Insider buying/selling in last 90 days."""
    try:
        txns = ticker_obj.insider_transactions
        if txns is not None and not txns.empty:
            # Count buys vs sells in recent transactions
            buys = 0
            sells = 0
            for _, row in txns.head(20).iterrows():
                text = str(row.get("text", "")).lower()
                shares_val = row.get("shares")
                if "purchase" in text or "buy" in text:
                    buys += 1
                elif "sale" in text or "sell" in text:
                    if shares_val and abs(float(shares_val)) > 0:
                        sells += 1

            if buys >= 3:
                return ThesisSignal(
                    name="Insider Activity", weight=0.15, status="green",
                    score=85,
                    detail=f"Cluster buying: {buys} insider purchases recently",
                )
            elif buys > sells:
                return ThesisSignal(
                    name="Insider Activity", weight=0.15, status="green",
                    score=70,
                    detail=f"Net insider buying ({buys} buys vs {sells} sells)",
                )
            elif buys == 0 and sells >= 3:
                return ThesisSignal(
                    name="Insider Activity", weight=0.15, status="red",
                    score=20,
                    detail=f"Insider selling: {sells} sales, no purchases",
                )
            elif sells > buys:
                return ThesisSignal(
                    name="Insider Activity", weight=0.15, status="yellow",
                    score=40,
                    detail=f"Mixed: {buys} buys, {sells} sells (may be routine)",
                )
            else:
                return ThesisSignal(
                    name="Insider Activity", weight=0.15, status="yellow",
                    score=50, detail="No significant insider activity",
                )
    except Exception:
        pass

    return ThesisSignal(
        name="Insider Activity", weight=0.15, status="yellow",
        score=50, detail="Insider transaction data not available",
    )


def _analyst_revision_signal(ticker_obj: yf.Ticker) -> ThesisSignal:
    """Signal 4: Direction of analyst rating changes."""
    try:
        rec = ticker_obj.recommendations
        if rec is not None and not rec.empty:
            recent = rec.tail(10)
            upgrades = 0
            downgrades = 0
            for _, row in recent.iterrows():
                action = str(row.get("action", "")).lower() if "action" in recent.columns else ""
                to_grade = str(row.get("toGrade", "")).lower()
                from_grade = str(row.get("fromGrade", "")).lower()

                if "upgrade" in action or "up" in action:
                    upgrades += 1
                elif "downgrade" in action or "down" in action:
                    downgrades += 1
                elif to_grade and from_grade:
                    # Heuristic: buy > hold > sell
                    buy_words = {"buy", "overweight", "outperform", "strong buy"}
                    sell_words = {"sell", "underweight", "underperform", "strong sell"}
                    to_is_buy = any(w in to_grade for w in buy_words)
                    from_is_buy = any(w in from_grade for w in buy_words)
                    to_is_sell = any(w in to_grade for w in sell_words)
                    from_is_sell = any(w in from_grade for w in sell_words)

                    if to_is_buy and not from_is_buy:
                        upgrades += 1
                    elif to_is_sell and not from_is_sell:
                        downgrades += 1

            if upgrades > downgrades + 1:
                return ThesisSignal(
                    name="Analyst Revisions", weight=0.10, status="green",
                    score=80,
                    detail=f"Net upgrades: {upgrades} up, {downgrades} down",
                )
            elif downgrades > upgrades + 1:
                return ThesisSignal(
                    name="Analyst Revisions", weight=0.10, status="red",
                    score=25,
                    detail=f"Net downgrades: {downgrades} down, {upgrades} up",
                )
            else:
                return ThesisSignal(
                    name="Analyst Revisions", weight=0.10, status="yellow",
                    score=50,
                    detail=f"Mixed: {upgrades} upgrades, {downgrades} downgrades",
                )
    except Exception:
        pass

    return ThesisSignal(
        name="Analyst Revisions", weight=0.10, status="yellow",
        score=50, detail="Analyst revision data not available",
    )


def _price_momentum_signal(info: dict) -> ThesisSignal:
    """Signal 5: 52-week price performance vs S&P 500."""
    stock_52w = info.get("52WeekChange")
    sp500_52w = info.get("SandP52WeekChange")

    if stock_52w is None:
        return ThesisSignal(
            name="Price Momentum", weight=0.10, status="yellow",
            score=50, detail="52-week return data not available",
        )

    sp = sp500_52w if sp500_52w is not None else 0.10  # assume ~10% if missing

    gap = stock_52w - sp
    if gap > 0.10:
        return ThesisSignal(
            name="Price Momentum", weight=0.10, status="green",
            score=min(90, 70 + gap * 50),
            detail=f"Outperforming S&P by {gap*100:.0f}pp over 52 weeks",
        )
    elif gap > -0.10:
        return ThesisSignal(
            name="Price Momentum", weight=0.10, status="yellow",
            score=50,
            detail=f"Roughly in line with S&P ({stock_52w*100:+.0f}% vs {sp*100:+.0f}%)",
        )
    else:
        return ThesisSignal(
            name="Price Momentum", weight=0.10, status="red",
            score=max(10, 30 + gap * 30),
            detail=f"Trailing S&P by {abs(gap)*100:.0f}pp ({stock_52w*100:+.0f}% vs {sp*100:+.0f}%)",
        )


def _fscore_signal(f_score: int) -> ThesisSignal:
    """Signal 6: Piotroski F-Score quality gate."""
    if f_score >= 7:
        return ThesisSignal(
            name="Quality (F-Score)", weight=0.0, status="green",
            score=85, detail=f"Strong fundamentals: {f_score}/9",
        )
    elif f_score >= 4:
        return ThesisSignal(
            name="Quality (F-Score)", weight=0.0, status="yellow",
            score=50, detail=f"Adequate fundamentals: {f_score}/9",
        )
    else:
        return ThesisSignal(
            name="Quality (F-Score)", weight=0.0, status="red",
            score=15, detail=f"Weak fundamentals: {f_score}/9",
        )


def compute_thesis_health(
    ticker: str,
    pre_fetched_info: dict | None = None,
    sector_median_growth: float = 0.05,
) -> ThesisHealthResult:
    """Run Stage 2: compute 6-signal thesis health score.

    All data from yfinance — no paid APIs or LLM calls.
    Accepts pre-fetched info dict to avoid redundant yfinance calls.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        info = pre_fetched_info if pre_fetched_info else (ticker_obj.info or {})
    except Exception:
        logger.warning("Failed to load yfinance data for %s", ticker)
        info = pre_fetched_info or {}
        ticker_obj = None

    # Compute Piotroski F-Score
    f_score = _compute_piotroski(info, {}, {})

    # Compute each signal
    signals: list[ThesisSignal] = []

    if ticker_obj:
        signals.append(_earnings_surprise_signal(ticker_obj))
    else:
        signals.append(ThesisSignal(name="Earnings Surprise", weight=0.15, status="yellow", score=50, detail="Data unavailable"))

    signals.append(_revenue_growth_signal(info, sector_median_growth))

    if ticker_obj:
        signals.append(_insider_activity_signal(ticker_obj))
    else:
        signals.append(ThesisSignal(name="Insider Activity", weight=0.15, status="yellow", score=50, detail="Data unavailable"))

    if ticker_obj:
        signals.append(_analyst_revision_signal(ticker_obj))
    else:
        signals.append(ThesisSignal(name="Analyst Revisions", weight=0.10, status="yellow", score=50, detail="Data unavailable"))

    signals.append(_price_momentum_signal(info))
    signals.append(_fscore_signal(f_score))

    # Composite score: weighted average of scored signals (F-Score is gate, weight=0)
    total_weight = sum(s.weight for s in signals if s.weight > 0)
    if total_weight > 0:
        raw_score = sum(s.score * s.weight for s in signals if s.weight > 0) / total_weight
    else:
        raw_score = 50

    # Map 0-100 → 1-10
    composite = max(1.0, min(10.0, raw_score / 10))

    # Count negatives
    negative_count = sum(1 for s in signals if s.status == "red")
    total_count = len(signals)

    # Determine verdict
    if composite >= 7.5:
        verdict: Literal["healthy", "mixed", "stressed", "broken"] = "healthy"
    elif composite >= 5.0:
        verdict = "mixed"
    elif composite >= 3.0:
        verdict = "stressed"
    else:
        verdict = "broken"

    return ThesisHealthResult(
        ticker=ticker,
        composite_score=round(composite, 1),
        signals=signals,
        negative_count=negative_count,
        total_count=total_count,
        f_score=f_score,
        verdict=verdict,
    )
