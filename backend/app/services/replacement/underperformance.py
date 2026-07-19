
"""
Stage 1: Underperformance Detection

Compares a stock's return against its sector ETF and SPY benchmark
over 3-month, 6-month, and 1-year windows.

100% deterministic — no LLM involvement.
"""

from __future__ import annotations

import logging
from typing import Literal

import yfinance as yf

from app.models.replacement import PerformanceComparison, UnderperformanceResult
from app.services.replacement.etf_mapping import get_sector_etf

logger = logging.getLogger(__name__)

# Thresholds for severity classification
THRESHOLDS: list[tuple[str, int, float]] = [
    # (period_label, trading_days, min_gap_for_flag)
    ("3m", 63, 0.10),
    ("6m", 126, 0.15),
    ("1y", 252, 0.20),
]

BENCHMARK = "SPY"


def _returns_from_series(close, periods: list[int]) -> dict[int, float]:
    """Compute returns for multiple periods from a close price series."""
    if close is None or len(close) < 5:
        return {}
    results: dict[int, float] = {}
    for days in periods:
        if len(close) >= days:
            end_price = close.iloc[-1]
            start_price = close.iloc[-days]
            if start_price > 0:
                results[days] = (end_price - start_price) / start_price
    return results


def _batch_get_returns(
    tickers: list[str], periods: list[int],
) -> dict[str, dict[int, float]]:
    """Batch-download history for multiple tickers and compute returns."""
    max_days = max(periods) + 40  # buffer
    try:
        data = yf.download(tickers, period=f"{max_days}d", progress=False, threads=True)
        if data.empty:
            return {t: {} for t in tickers}
    except Exception:
        logger.warning("Batch download failed for %s", tickers)
        return {t: {} for t in tickers}

    results: dict[str, dict[int, float]] = {}
    if len(tickers) == 1:
        close = data.get("Close")
        results[tickers[0]] = _returns_from_series(close, periods)
    else:
        close_df = data.get("Close")
        if close_df is None or close_df.empty:
            return {t: {} for t in tickers}
        for t in tickers:
            if t in close_df.columns:
                series = close_df[t].dropna()
                results[t] = _returns_from_series(series, periods)
            else:
                results[t] = {}

    for t in tickers:
        if t not in results:
            results[t] = {}
    return results


def detect_underperformance(
    ticker: str,
    sector: str,
    cost_basis: float | None = None,
    shares: float | None = None,
    current_price: float | None = None,
) -> UnderperformanceResult:
    """Run Stage 1: compare stock vs sector ETF + benchmark.

    All inputs are from yfinance / Robinhood — no LLM calls.
    """
    sector_etf = get_sector_etf(sector)
    trading_day_periods = [t[1] for t in THRESHOLDS]

    # Fetch returns for stock, sector ETF, and benchmark in one batch download
    all_returns = _batch_get_returns([ticker, sector_etf, BENCHMARK], trading_day_periods)
    stock_returns = all_returns.get(ticker, {})
    sector_returns = all_returns.get(sector_etf, {})
    bench_returns = all_returns.get(BENCHMARK, {})

    comparisons: list[PerformanceComparison] = []
    worst_severity: Literal["none", "early_warning", "confirmed", "severe"] = "none"
    severity_rank = {"none": 0, "early_warning": 1, "confirmed": 2, "severe": 3}

    for label, days, threshold in THRESHOLDS:
        s_ret = stock_returns.get(days, 0.0)
        sec_ret = sector_returns.get(days, 0.0)
        b_ret = bench_returns.get(days)
        gap = s_ret - sec_ret

        comparisons.append(PerformanceComparison(
            period=label,
            stock_return=round(s_ret, 4),
            sector_return=round(sec_ret, 4),
            gap=round(gap, 4),
            benchmark_return=round(b_ret, 4) if b_ret is not None else None,
        ))

        # Classify severity based on gap magnitude
        if gap < -threshold:
            if label == "3m":
                sev = "early_warning"
            elif label == "6m":
                sev = "confirmed"
            else:
                sev = "severe"
            if severity_rank[sev] > severity_rank[worst_severity]:
                worst_severity = sev

    # User P&L calculation
    user_pnl_pct: float | None = None
    user_pnl_dollar: float | None = None
    if cost_basis and cost_basis > 0 and current_price:
        user_pnl_pct = round((current_price - cost_basis) / cost_basis, 4)
        if shares:
            user_pnl_dollar = round((current_price - cost_basis) * shares, 2)

    # Build summary string
    best_comp = max(comparisons, key=lambda c: abs(c.gap)) if comparisons else None
    if best_comp and best_comp.gap < -0.05:
        stock_pct = f"{best_comp.stock_return * 100:+.1f}%"
        sector_pct = f"{best_comp.sector_return * 100:+.1f}%"
        gap_pts = f"{abs(best_comp.gap) * 100:.0f}"
        summary = (
            f"{ticker} returned {stock_pct} vs {sector_etf} {sector_pct} "
            f"over {best_comp.period} — {gap_pts} points of underperformance."
        )
    elif best_comp:
        summary = f"{ticker} is roughly in line with its sector over recent periods."
    else:
        summary = f"Insufficient price history to assess {ticker}'s relative performance."

    return UnderperformanceResult(
        ticker=ticker,
        sector=sector,
        sector_etf=sector_etf,
        comparisons=comparisons,
        severity=worst_severity,
        user_pnl_pct=user_pnl_pct,
        user_pnl_dollar=user_pnl_dollar,
        summary=summary,
    )
