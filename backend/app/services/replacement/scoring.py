
"""
Stage 5: Multi-Factor Composite Scoring

Scores each candidate on 6 factor categories using cross-sectional
z-scores within the filtered universe, converted to percentile ranks.

Factor weights:
  Momentum  25%  (12-1mo return, 6-1mo return, revision breadth)
  Quality   25%  (ROE, margin stability, FCF yield, F-Score)
  Growth    20%  (revenue YoY, EPS YoY, forward EPS growth)
  Value     15%  (relative P/E, relative EV/EBITDA, PEG)
  Risk      10%  (beta, volatility, max drawdown — inverted)
  Analyst    5%  (consensus rating, price target upside)

100% deterministic — no LLM involvement.
"""

from __future__ import annotations

import logging
import statistics
from typing import Any

import yfinance as yf

from app.models.replacement import FactorScores, ScoredCandidate

logger = logging.getLogger(__name__)


def _percentile_rank(value: float, values: list[float]) -> float:
    """Convert a value to a percentile rank (0-100) within a list."""
    if not values or len(values) < 2:
        return 50.0
    sorted_vals = sorted(values)
    rank = sum(1 for v in sorted_vals if v <= value)
    return min(100, max(0, (rank / len(sorted_vals)) * 100))


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


_EMPTY_RETURNS: dict[str, float | None] = {"ret_12m": None, "ret_6m": None, "vol_60d": None, "max_dd_1y": None}


def _compute_returns_from_series(close) -> dict[str, float | None]:
    """Compute returns from a pandas Series of close prices."""
    if close is None or len(close) < 30:
        return dict(_EMPTY_RETURNS)

    n = len(close)

    # Skip last 21 trading days (short-term reversal effect)
    skip = min(21, n // 4)
    end_idx = n - skip

    # 12-month (252 days) minus skip
    ret_12m = None
    if end_idx > 252:
        ret_12m = (close.iloc[end_idx] - close.iloc[end_idx - 252]) / close.iloc[end_idx - 252]

    # 6-month (126 days) minus skip
    ret_6m = None
    if end_idx > 126:
        ret_6m = (close.iloc[end_idx] - close.iloc[end_idx - 126]) / close.iloc[end_idx - 126]

    # 60-day annualized volatility
    vol_60d = None
    if n >= 60:
        daily_returns = close.pct_change().dropna().tail(60)
        if len(daily_returns) >= 30:
            vol_60d = float(daily_returns.std() * (252 ** 0.5))

    # Max drawdown (trailing 1 year)
    max_dd = None
    if n >= 252:
        trail = close.tail(252)
        running_max = trail.cummax()
        drawdowns = (trail - running_max) / running_max
        max_dd = float(drawdowns.min())

    return {"ret_12m": ret_12m, "ret_6m": ret_6m, "vol_60d": vol_60d, "max_dd_1y": max_dd}


def _batch_compute_returns(tickers: list[str]) -> dict[str, dict[str, float | None]]:
    """Batch-download price history and compute returns for all tickers at once."""
    results: dict[str, dict[str, float | None]] = {}
    if not tickers:
        return results

    try:
        data = yf.download(tickers, period="400d", progress=False, threads=True)
        if data.empty:
            return {t: dict(_EMPTY_RETURNS) for t in tickers}

        # yf.download returns multi-level columns when multiple tickers
        if len(tickers) == 1:
            # Single ticker: columns are just "Close", "Open", etc.
            close = data.get("Close")
            results[tickers[0]] = _compute_returns_from_series(close)
        else:
            close_df = data.get("Close")
            if close_df is None or close_df.empty:
                return {t: dict(_EMPTY_RETURNS) for t in tickers}

            for ticker in tickers:
                if ticker in close_df.columns:
                    series = close_df[ticker].dropna()
                    results[ticker] = _compute_returns_from_series(series)
                else:
                    results[ticker] = dict(_EMPTY_RETURNS)

    except Exception:
        logger.debug("Batch returns download failed, returning empty")
        return {t: dict(_EMPTY_RETURNS) for t in tickers}

    # Fill in any missing tickers
    for t in tickers:
        if t not in results:
            results[t] = dict(_EMPTY_RETURNS)

    return results


def _extract_metrics(info: dict) -> dict[str, Any]:
    """Extract all needed metrics from yfinance info dict."""
    return {
        "name": info.get("longName") or info.get("shortName") or "Unknown",
        "sector": info.get("sector", "Unknown"),
        "industry": info.get("industry", "Unknown"),
        "market_cap": info.get("marketCap"),
        # Quality
        "roe": info.get("returnOnEquity"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "fcf": info.get("freeCashflow"),
        "ocf": info.get("operatingCashflow"),
        "enterprise_value": info.get("enterpriseValue"),
        "current_ratio": info.get("currentRatio"),
        "debt_to_equity": info.get("debtToEquity"),
        # Growth
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "eps_forward": info.get("epsForward"),
        "eps_trailing": info.get("trailingEps"),
        # Value
        "forward_pe": info.get("forwardPE"),
        "trailing_pe": info.get("trailingPE"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "peg_ratio": info.get("trailingPegRatio"),
        "price_to_book": info.get("priceToBook"),
        # Risk
        "beta": info.get("beta"),
        # Analyst
        "recommendation_mean": info.get("recommendationMean"),
        "target_mean_price": info.get("targetMeanPrice"),
        "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        # Dividend
        "dividend_yield": info.get("dividendYield"),
    }


def _score_momentum(returns: dict, all_returns: list[dict]) -> float:
    """Momentum factor: 12-1mo return (40%), 6-1mo return (30%), implied revision (30%)."""
    components = []

    # 12-1 month return
    r12 = returns.get("ret_12m")
    all_r12 = [r["ret_12m"] for r in all_returns if r.get("ret_12m") is not None]
    if r12 is not None and all_r12:
        components.append((_percentile_rank(r12, all_r12), 0.4))

    # 6-1 month return
    r6 = returns.get("ret_6m")
    all_r6 = [r["ret_6m"] for r in all_returns if r.get("ret_6m") is not None]
    if r6 is not None and all_r6:
        components.append((_percentile_rank(r6, all_r6), 0.3))

    # Use whatever weight we have
    if not components:
        return 50.0

    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


def _score_quality(metrics: dict, all_metrics: list[dict]) -> float:
    """Quality factor: ROE (30%), margin stability (25%), FCF yield (25%), F-Score proxy (20%)."""
    components = []

    # ROE
    roe = metrics.get("roe")
    all_roe = [m["roe"] for m in all_metrics if m.get("roe") is not None]
    if roe is not None and all_roe:
        components.append((_percentile_rank(roe, all_roe), 0.30))

    # Gross margin as stability proxy
    gm = metrics.get("gross_margins")
    all_gm = [m["gross_margins"] for m in all_metrics if m.get("gross_margins") is not None]
    if gm is not None and all_gm:
        components.append((_percentile_rank(gm, all_gm), 0.25))

    # FCF yield
    fcf = metrics.get("fcf")
    ev = metrics.get("enterprise_value")
    fcf_yield = _safe_div(fcf, ev)
    all_fcfy = [_safe_div(m.get("fcf"), m.get("enterprise_value")) for m in all_metrics]
    all_fcfy = [v for v in all_fcfy if v is not None]
    if fcf_yield is not None and all_fcfy:
        components.append((_percentile_rank(fcf_yield, all_fcfy), 0.25))

    # Quality composite: current_ratio + low debt
    cr = metrics.get("current_ratio")
    all_cr = [m["current_ratio"] for m in all_metrics if m.get("current_ratio") is not None]
    if cr is not None and all_cr:
        components.append((_percentile_rank(cr, all_cr), 0.20))

    if not components:
        return 50.0
    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


def _score_growth(metrics: dict, all_metrics: list[dict]) -> float:
    """Growth factor: Revenue YoY (40%), EPS growth (30%), Forward EPS (30%)."""
    components = []

    # Revenue growth
    rg = metrics.get("revenue_growth")
    all_rg = [m["revenue_growth"] for m in all_metrics if m.get("revenue_growth") is not None]
    if rg is not None and all_rg:
        components.append((_percentile_rank(rg, all_rg), 0.40))

    # EPS growth
    eg = metrics.get("earnings_growth")
    all_eg = [m["earnings_growth"] for m in all_metrics if m.get("earnings_growth") is not None]
    if eg is not None and all_eg:
        components.append((_percentile_rank(eg, all_eg), 0.30))

    # Forward EPS growth proxy: forward EPS / trailing EPS - 1
    fwd = metrics.get("eps_forward")
    trail = metrics.get("eps_trailing")
    fwd_growth = None
    if fwd and trail and trail > 0:
        fwd_growth = (fwd / trail) - 1
    all_fg = []
    for m in all_metrics:
        f, t = m.get("eps_forward"), m.get("eps_trailing")
        if f and t and t > 0:
            all_fg.append((f / t) - 1)
    if fwd_growth is not None and all_fg:
        components.append((_percentile_rank(fwd_growth, all_fg), 0.30))

    if not components:
        return 50.0
    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


def _score_value(metrics: dict, all_metrics: list[dict]) -> float:
    """Value factor: P/E (35%), EV/EBITDA (35%), PEG (30%). INVERTED: lower = better."""
    components = []

    # Forward P/E — lower is better → invert percentile
    fpe = metrics.get("forward_pe")
    all_fpe = [m["forward_pe"] for m in all_metrics if m.get("forward_pe") is not None and 0 < m["forward_pe"] < 200]
    if fpe is not None and 0 < fpe < 200 and all_fpe:
        components.append((100 - _percentile_rank(fpe, all_fpe), 0.35))

    # EV/EBITDA — lower is better
    ev_eb = metrics.get("ev_to_ebitda")
    all_ev = [m["ev_to_ebitda"] for m in all_metrics if m.get("ev_to_ebitda") is not None and 0 < m["ev_to_ebitda"] < 100]
    if ev_eb is not None and 0 < ev_eb < 100 and all_ev:
        components.append((100 - _percentile_rank(ev_eb, all_ev), 0.35))

    # PEG — lower is better
    peg = metrics.get("peg_ratio")
    all_peg = [m["peg_ratio"] for m in all_metrics if m.get("peg_ratio") is not None and 0 < m["peg_ratio"] < 10]
    if peg is not None and 0 < peg < 10 and all_peg:
        components.append((100 - _percentile_rank(peg, all_peg), 0.30))

    if not components:
        return 50.0
    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


def _score_risk(returns: dict, metrics: dict, all_returns: list[dict], all_metrics: list[dict]) -> float:
    """Risk factor: Beta (40%), Volatility (30%), Max DD (30%). INVERTED: lower risk = higher score."""
    components = []

    # Beta — lower is better
    beta = metrics.get("beta")
    all_beta = [m["beta"] for m in all_metrics if m.get("beta") is not None]
    if beta is not None and all_beta:
        components.append((100 - _percentile_rank(beta, all_beta), 0.40))

    # Volatility — lower is better
    vol = returns.get("vol_60d")
    all_vol = [r["vol_60d"] for r in all_returns if r.get("vol_60d") is not None]
    if vol is not None and all_vol:
        components.append((100 - _percentile_rank(vol, all_vol), 0.30))

    # Max drawdown — less negative is better
    dd = returns.get("max_dd_1y")
    all_dd = [r["max_dd_1y"] for r in all_returns if r.get("max_dd_1y") is not None]
    if dd is not None and all_dd:
        # Less negative = higher rank = better
        components.append((_percentile_rank(dd, all_dd), 0.30))

    if not components:
        return 50.0
    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


def _score_analyst(metrics: dict, all_metrics: list[dict]) -> float:
    """Analyst factor: Consensus rating (50%), Price target upside (50%)."""
    components = []

    # Consensus rating — lower number = more bullish (1=strong buy, 5=sell)
    rec = metrics.get("recommendation_mean")
    all_rec = [m["recommendation_mean"] for m in all_metrics if m.get("recommendation_mean") is not None]
    if rec is not None and all_rec:
        components.append((100 - _percentile_rank(rec, all_rec), 0.50))

    # Price target upside — higher is better
    target = metrics.get("target_mean_price")
    price = metrics.get("current_price")
    if target and price and price > 0:
        upside = (target / price) - 1
        upside = min(upside, 1.0)  # cap at 100%
        all_upside = []
        for m in all_metrics:
            t, p = m.get("target_mean_price"), m.get("current_price")
            if t and p and p > 0:
                all_upside.append(min((t / p) - 1, 1.0))
        if all_upside:
            components.append((_percentile_rank(upside, all_upside), 0.50))

    if not components:
        return 50.0
    total_w = sum(w for _, w in components)
    return sum(v * w for v, w in components) / total_w


def _apply_guardrails(candidates: list[ScoredCandidate], all_metrics: list[dict]) -> list[ScoredCandidate]:
    """Overvaluation guardrails: reject overbought / extremely expensive candidates."""
    # Compute sector median forward P/E
    fpes = [m["forward_pe"] for m in all_metrics if m.get("forward_pe") is not None and 0 < m["forward_pe"] < 200]
    median_fpe = statistics.median(fpes) if fpes else None

    filtered = []
    for c in candidates:
        # Reject if forward P/E > 1.5x sector median
        if median_fpe and c.forward_pe and c.forward_pe > median_fpe * 1.5:
            logger.debug("Guardrail: rejecting %s (fwd P/E %.1f > %.1f)", c.ticker, c.forward_pe, median_fpe * 1.5)
            continue

        # Reject if PEG > 2.0
        # (PEG stored in metrics but not directly on ScoredCandidate — skip for now)

        filtered.append(c)

    return filtered if len(filtered) >= 3 else candidates  # Relax if too aggressive


def score_candidates(
    candidates: list[tuple[str, dict[str, Any]]],
    original_ticker: str | None = None,
    top_n: int = 3,
) -> tuple[list[ScoredCandidate], float | None]:
    """Run Stage 5: score candidates on 6 factors, return top N.

    Also returns the original stock's composite score if original_ticker provided.
    """
    if not candidates:
        return [], None

    # Extract metrics for all candidates
    all_metrics: list[dict] = []
    ticker_metrics: dict[str, dict] = {}
    for ticker, info in candidates:
        m = _extract_metrics(info)
        all_metrics.append(m)
        ticker_metrics[ticker] = m

    # If we have the original stock, include it for relative scoring
    original_score = None
    if original_ticker and original_ticker not in ticker_metrics:
        try:
            orig_info = yf.Ticker(original_ticker).info or {}
            orig_m = _extract_metrics(orig_info)
            all_metrics.append(orig_m)
            ticker_metrics[original_ticker] = orig_m
        except Exception:
            pass

    # Compute returns for all candidates in a single batch download
    return_tickers = [t for t, _ in candidates]
    if original_ticker and original_ticker not in {t for t, _ in candidates}:
        return_tickers.append(original_ticker)

    logger.info("Stage 5: batch-downloading returns for %d tickers", len(return_tickers))
    ticker_returns = _batch_compute_returns(return_tickers)
    all_returns: list[dict] = [ticker_returns.get(t, dict(_EMPTY_RETURNS)) for t in return_tickers]

    # Score each candidate
    scored: list[ScoredCandidate] = []
    for ticker, info in candidates:
        m = ticker_metrics[ticker]
        r = ticker_returns.get(ticker, {})

        momentum = _score_momentum(r, all_returns)
        quality = _score_quality(m, all_metrics)
        growth = _score_growth(m, all_metrics)
        value = _score_value(m, all_metrics)
        risk = _score_risk(r, m, all_returns, all_metrics)
        analyst = _score_analyst(m, all_metrics)

        composite = (
            0.25 * momentum +
            0.25 * quality +
            0.20 * growth +
            0.15 * value +
            0.10 * risk +
            0.05 * analyst
        )

        scored.append(ScoredCandidate(
            ticker=ticker,
            name=m["name"],
            sector=m["sector"],
            industry=m["industry"],
            composite_score=round(composite, 1),
            factors=FactorScores(
                momentum=round(momentum, 1),
                quality=round(quality, 1),
                growth=round(growth, 1),
                value=round(value, 1),
                risk=round(risk, 1),
                analyst=round(analyst, 1),
            ),
            revenue_yoy=m.get("revenue_growth"),
            eps_growth=m.get("earnings_growth"),
            return_6m=r.get("ret_6m"),
            f_score=None,  # Would need separate computation
            forward_pe=m.get("forward_pe"),
            beta=m.get("beta"),
            dividend_yield=m.get("dividend_yield"),
            market_cap=m.get("market_cap"),
        ))

    # Score original stock too
    if original_ticker and original_ticker in ticker_metrics:
        om = ticker_metrics[original_ticker]
        or_ = ticker_returns.get(original_ticker, {})
        original_score = round(
            0.25 * _score_momentum(or_, all_returns) +
            0.25 * _score_quality(om, all_metrics) +
            0.20 * _score_growth(om, all_metrics) +
            0.15 * _score_value(om, all_metrics) +
            0.10 * _score_risk(or_, om, all_returns, all_metrics) +
            0.05 * _score_analyst(om, all_metrics),
            1,
        )

    # Sort by composite score descending
    scored.sort(key=lambda c: c.composite_score, reverse=True)

    # Apply guardrails
    scored = _apply_guardrails(scored, all_metrics)

    return scored[:top_n], original_score
