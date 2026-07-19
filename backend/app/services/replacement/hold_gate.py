
"""
Stage 3: Hold Gate

5 deterministic conditions that prevent replacement suggestions.
If ANY condition triggers, Emouva says "Hold" with reasons.

Inspired by the META 2022 case — down 76% but thesis intact.

100% deterministic — no LLM involvement.
"""

from __future__ import annotations

import logging

import yfinance as yf

from app.models.replacement import HoldCondition, HoldGateResult, ThesisHealthResult

logger = logging.getLogger(__name__)

# Cyclical sectors that get unfairly punished at troughs
CYCLICAL_SECTORS = {"Energy", "Basic Materials", "Industrials", "Financial Services", "Financials", "Real Estate"}


def _check_oversold_and_sound(
    info: dict,
    hist_data,
    f_score: int,
) -> HoldCondition:
    """Hold Condition 1: Technically oversold + fundamentally sound.

    If RSI < 30 AND F-Score >= 7 AND revenue still growing → likely short-term overreaction.
    """
    # Compute RSI-14 from price history
    rsi = _compute_rsi(hist_data)
    rev_growth = info.get("revenueGrowth")
    rev_growing = rev_growth is not None and rev_growth > 0

    triggered = (
        rsi is not None and rsi < 30 and
        f_score >= 7 and
        rev_growing
    )

    reason = ""
    if triggered:
        reason = (
            f"Stock is technically oversold (RSI: {rsi:.0f}) with strong fundamentals "
            f"(F-Score: {f_score}/9) and revenue still growing ({rev_growth*100:.1f}% YoY). "
            f"This pattern often precedes a rebound."
        )

    return HoldCondition(
        name="Oversold + Fundamentally Sound",
        triggered=triggered,
        reason=reason,
    )


def _check_insider_buying(ticker_obj: yf.Ticker | None) -> HoldCondition:
    """Hold Condition 2: Significant insider buying (cluster buying).

    3+ insiders buying in last 90 days with total > $100K → strong hold signal.
    """
    if not ticker_obj:
        return HoldCondition(name="Insider Buying", triggered=False, reason="")

    try:
        txns = ticker_obj.insider_transactions
        if txns is None or txns.empty:
            return HoldCondition(name="Insider Buying", triggered=False, reason="")

        buy_count = 0
        buy_value = 0
        for _, row in txns.head(20).iterrows():
            text = str(row.get("text", "")).lower()
            value = row.get("value")
            if "purchase" in text or "buy" in text:
                buy_count += 1
                if value:
                    try:
                        buy_value += abs(float(value))
                    except (ValueError, TypeError):
                        pass

        triggered = buy_count >= 3 and buy_value > 100_000

        reason = ""
        if triggered:
            reason = (
                f"{buy_count} insiders bought ${buy_value:,.0f} worth of stock recently. "
                f"Cluster insider buying outperforms by 4-6% annually. "
                f"The people who know this business best are buying with their own money."
            )

        return HoldCondition(name="Insider Buying", triggered=triggered, reason=reason)

    except Exception:
        return HoldCondition(name="Insider Buying", triggered=False, reason="")


def _check_no_better_alternative(
    best_replacement_score: float | None,
    current_score: float | None,
) -> HoldCondition:
    """Hold Condition 3: No clearly better alternative.

    Replacement must score at least 10 points higher to justify swap costs.
    """
    if best_replacement_score is None or current_score is None:
        return HoldCondition(name="No Better Alternative", triggered=False, reason="")

    gap = best_replacement_score - current_score
    triggered = gap < 10

    reason = ""
    if triggered:
        reason = (
            f"The best alternative scores only {gap:.0f} points higher. "
            f"After transaction costs and tax implications, the swap may not be worth it. "
            f"A 10+ point improvement is needed to justify a switch."
        )

    return HoldCondition(name="No Better Alternative", triggered=triggered, reason=reason)


def _check_tax_timing(
    cost_basis: float | None,
    current_price: float | None,
    holding_period_days: int | None,
) -> HoldCondition:
    """Hold Condition 4: Short-term capital gains tax timing.

    If stock is profitable and < 60 days from long-term rate → wait.
    """
    if not cost_basis or not current_price or not holding_period_days:
        return HoldCondition(name="Tax Timing", triggered=False, reason="")

    has_gain = current_price > cost_basis
    is_short_term = holding_period_days < 365
    days_to_lt = 365 - holding_period_days

    triggered = has_gain and is_short_term and days_to_lt <= 60

    reason = ""
    if triggered:
        reason = (
            f"You're {days_to_lt} days from the 1-year holding mark. "
            f"Selling now triggers short-term capital gains tax (up to 37%). "
            f"Waiting saves you significant taxes on your gain."
        )

    return HoldCondition(name="Tax Timing", triggered=triggered, reason=reason)


def _check_cyclical_trough(
    info: dict,
    sector: str,
) -> HoldCondition:
    """Hold Condition 5: Cyclical sector near trough.

    Cyclical stocks at troughs look terrible on trailing metrics but
    often deliver massive forward returns (Energy mid-2020, Financials early-2009).
    """
    if sector not in CYCLICAL_SECTORS:
        return HoldCondition(name="Cyclical Trough", triggered=False, reason="")

    pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    # Check if valuation is near historical lows
    # Simplified: low P/B or very low P/E for cyclicals = potential trough
    near_trough = (
        (pb is not None and pb < 1.5) or
        (pe is not None and pe < 10)
    )

    triggered = near_trough

    reason = ""
    if triggered:
        reason = (
            f"{sector} is a cyclical sector. The stock trades at "
            f"{'P/B ' + f'{pb:.1f}' if pb else ''}"
            f"{'P/E ' + f'{pe:.0f}' if pe else ''}, "
            f"near historical lows. Cyclical stocks at troughs often look terrible "
            f"on trailing metrics but deliver strong forward returns as the cycle turns."
        )

    return HoldCondition(name="Cyclical Trough", triggered=triggered, reason=reason)


def _compute_rsi(hist_data, period: int = 14) -> float | None:
    """Compute RSI from price history DataFrame."""
    try:
        if hist_data is None or hist_data.empty or len(hist_data) < period + 1:
            return None

        close = hist_data["Close"]
        delta = close.diff()

        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)

        avg_gain = gain.rolling(window=period).mean().iloc[-1]
        avg_loss = loss.rolling(window=period).mean().iloc[-1]

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)
    except Exception:
        return None


def evaluate_hold_gate(
    ticker: str,
    sector: str,
    thesis_health: ThesisHealthResult,
    pre_fetched_info: dict | None = None,
    cost_basis: float | None = None,
    current_price: float | None = None,
    holding_period_days: int | None = None,
    best_replacement_score: float | None = None,
    current_stock_score: float | None = None,
) -> HoldGateResult:
    """Run Stage 3: evaluate 5 hold conditions.

    Returns should_hold=True if ANY condition triggers.
    Accepts pre-fetched info dict to avoid redundant yfinance calls.
    """
    try:
        ticker_obj = yf.Ticker(ticker)
        info = pre_fetched_info if pre_fetched_info else (ticker_obj.info or {})
        hist = ticker_obj.history(period="60d")
    except Exception:
        info = pre_fetched_info or {}
        hist = None
        ticker_obj = None

    conditions: list[HoldCondition] = []

    # Condition 1: Oversold + Fundamentally Sound
    conditions.append(_check_oversold_and_sound(info, hist, thesis_health.f_score))

    # Condition 2: Significant Insider Buying
    conditions.append(_check_insider_buying(ticker_obj))

    # Condition 3: No Clearly Better Alternative (evaluated later, may be None)
    conditions.append(_check_no_better_alternative(best_replacement_score, current_stock_score))

    # Condition 4: Tax Timing
    conditions.append(_check_tax_timing(cost_basis, current_price, holding_period_days))

    # Condition 5: Cyclical Trough
    conditions.append(_check_cyclical_trough(info, sector))

    should_hold = any(c.triggered for c in conditions)
    hold_reasons = [c.reason for c in conditions if c.triggered and c.reason]

    review_in_days = 30 if should_hold else None

    return HoldGateResult(
        should_hold=should_hold,
        conditions=conditions,
        hold_reasons=hold_reasons,
        review_in_days=review_in_days,
    )
