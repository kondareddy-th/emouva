"""
Real risk computation engine.
Computes VaR, CVaR, correlations, drawdown, volatility, sector concentration,
market-cap bucketing, geographic exposure, factor regression, and a composite
concentration risk score from actual Robinhood position data and historical prices.

Correlation model: 90-day Pearson + 30-day rolling Spearman rank correlation,
combined via max(). Threshold 0.65 for alerts.

Factor exposure: OLS regression of portfolio returns against SPY benchmark
to compute real market beta, plus sector-derived factor estimates.

Stress tests: Historical + modern macro scenarios.
"""

import logging
import time
from typing import Any

import numpy as np
from scipy import stats as scipy_stats
import robin_stocks.robinhood as r

logger = logging.getLogger(__name__)

# ── Market cap tier thresholds ──
_MCAP_TIERS = [
    ("Mega Cap",  200_000_000_000),   # >$200B
    ("Large Cap",  10_000_000_000),   # $10B–$200B
    ("Mid Cap",     2_000_000_000),   # $2B–$10B
    ("Small Cap",     300_000_000),   # $300M–$2B
    ("Micro Cap",               0),   # <$300M
]

# ── Country → region mapping (headquarter country from yfinance) ──
_REGION_MAP: dict[str, str] = {
    "United States": "US",
    "China": "China",
    "Hong Kong": "China",
    "Taiwan": "Asia-Pacific",
    "Japan": "Asia-Pacific",
    "South Korea": "Asia-Pacific",
    "India": "Asia-Pacific",
    "Singapore": "Asia-Pacific",
    "Australia": "Asia-Pacific",
    "United Kingdom": "Europe",
    "Germany": "Europe",
    "France": "Europe",
    "Netherlands": "Europe",
    "Switzerland": "Europe",
    "Ireland": "Europe",
    "Sweden": "Europe",
    "Denmark": "Europe",
    "Spain": "Europe",
    "Italy": "Europe",
    "Norway": "Europe",
    "Finland": "Europe",
    "Belgium": "Europe",
    "Israel": "Middle East",
    "Canada": "Americas (ex-US)",
    "Brazil": "Americas (ex-US)",
    "Mexico": "Americas (ex-US)",
    "Argentina": "Americas (ex-US)",
}


def _mcap_tier(market_cap: float | None) -> str:
    if not market_cap or market_cap <= 0:
        return "Unknown"
    for label, threshold in _MCAP_TIERS:
        if market_cap >= threshold:
            return label
    return "Micro Cap"


def _country_to_region(country: str | None) -> str:
    if not country:
        return "Unknown"
    return _REGION_MAP.get(country, "Other")

_cache: dict[str, tuple[float, Any]] = {}
RISK_CACHE_TTL = 900  # 15 minutes — keeps a login→browse gap warm so Risk Center is instant


def _get_cached(key: str) -> Any | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < RISK_CACHE_TTL:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


def compute_risk_metrics(positions: list[dict], historicals: dict | None = None,
                         cache_key: str = "risk_metrics") -> dict:
    """
    Compute comprehensive risk metrics from real position data.
    `historicals` (symbol -> bars from the Robinhood MCP) supplies the price
    matrix; when omitted, falls back to the legacy fetch. `cache_key` should be
    per-account to avoid cross-account bleed.
    """
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    if not positions:
        return _empty_risk()

    try:
        # Analyze top 25 positions by equity (more coverage for correlation detection)
        top = sorted(positions, key=lambda p: p.get("equity", 0), reverse=True)[:25]
        symbols = [p["symbol"] for p in top]
        weights_raw = np.array([p.get("equity", 0) for p in top], dtype=float)
        total_equity = weights_raw.sum()
        if total_equity == 0:
            return _empty_risk()
        weights = weights_raw / total_equity

        # Price matrix: injected MCP historicals (preferred) or legacy fetch.
        if historicals is not None:
            price_matrix, dates = _matrix_from_historicals(symbols, historicals)
        else:
            price_matrix, dates = _fetch_price_matrix(symbols, span="3month", interval="day")
        if price_matrix is None or price_matrix.shape[0] < 10:
            return _empty_risk()

        # Compute daily returns
        returns = np.diff(price_matrix, axis=0) / price_matrix[:-1]
        # Replace any inf/nan with 0
        returns = np.nan_to_num(returns, nan=0.0, posinf=0.0, neginf=0.0)

        # Portfolio daily returns (weighted)
        portfolio_returns = returns @ weights

        # --- VaR (95%) ---
        daily_var_95 = float(np.percentile(portfolio_returns, 5))

        # --- CVaR (95%) = expected shortfall ---
        var_threshold = np.percentile(portfolio_returns, 5)
        tail_returns = portfolio_returns[portfolio_returns <= var_threshold]
        daily_cvar_95 = float(np.mean(tail_returns)) if len(tail_returns) > 0 else daily_var_95
        # Scale to monthly (sqrt(21) approximation)
        monthly_cvar_95 = daily_cvar_95 * np.sqrt(21)

        # --- Annualized volatility ---
        daily_vol = float(np.std(portfolio_returns))
        annualized_vol = daily_vol * np.sqrt(252)

        # --- Drawdown series ---
        portfolio_values = price_matrix @ weights
        running_max = np.maximum.accumulate(portfolio_values)
        drawdowns = (portfolio_values - running_max) / running_max
        drawdowns = np.nan_to_num(drawdowns, nan=0.0)
        max_drawdown = float(np.min(drawdowns))

        drawdown_series = []
        for i, d in enumerate(dates):
            drawdown_series.append({
                "date": d,
                "drawdown": round(float(drawdowns[i]) * 100, 2),
            })

        # --- Pairwise correlations (hybrid Pearson + Spearman model) ---
        correlation_alerts = _compute_correlation_alerts(returns, symbols)

        # --- Sector concentration (enrich via cached yfinance company info) ---
        from app.services.market_data import get_company_info as _gci
        sector_map: dict[str, float] = {}
        all_equity = sum(p.get("equity", 0) for p in positions)
        for p in positions:
            sector = p.get("sector") or "Unknown"
            if sector == "Unknown":
                try:
                    sector = _gci(p["symbol"]).get("sector") or "Unknown"
                except Exception:
                    sector = "Unknown"
            sector_map[sector] = sector_map.get(sector, 0) + p.get("equity", 0)

        sector_weights = []
        for sector, val in sorted(sector_map.items(), key=lambda x: -x[1]):
            pct = (val / all_equity * 100) if all_equity else 0
            sector_weights.append({
                "sector": sector,
                "value": round(val, 2),
                "weight": round(pct, 2),
            })

        # HHI (Herfindahl-Hirschman Index) for concentration
        hhi = sum((sw["weight"] / 100) ** 2 for sw in sector_weights)
        top5_concentration = sum(sw["weight"] for sw in sector_weights[:5])

        # --- Factor exposure (OLS regression against SPY + sector-derived) ---
        factors = _compute_factor_exposure(
            portfolio_returns, annualized_vol, sector_weights, positions, dates, historicals
        )

        # --- Stress tests (sector-weighted impact estimates) ---
        stress_tests = _compute_stress_tests(sector_weights, annualized_vol)

        # --- Concentration risk (sector + market cap + geography) ---
        concentration_risk = _compute_concentration_risk(positions, sector_weights, hhi)

        # --- Composite risk score (0-100) ---
        # Weighted from multiple signals
        var_score = min(100, abs(daily_var_95) * 100 / 5 * 100)  # 5% daily loss = 100
        dd_score = min(100, abs(max_drawdown) * 100 / 30 * 100)  # 30% drawdown = 100
        conc_score = min(100, hhi * 100 / 0.3 * 100)  # HHI of 0.3 = 100
        vol_score = min(100, annualized_vol / 0.4 * 100)  # 40% annual vol = 100
        corr_score = min(100, len(correlation_alerts) * 15)  # each alert = 15 points

        risk_score = int(
            var_score * 0.25
            + dd_score * 0.20
            + conc_score * 0.20
            + vol_score * 0.20
            + corr_score * 0.15
        )
        risk_score = max(0, min(100, risk_score))

        # --- Risk budget (estimated) ---
        risk_budget_used = min(1.0, risk_score / 80)

        result = {
            "score": risk_score,
            "daily_var_95": round(daily_var_95 * 100, 2),
            "monthly_cvar_95": round(monthly_cvar_95 * 100, 2),
            "risk_budget_used": round(risk_budget_used, 2),
            "portfolio_volatility": round(annualized_vol * 100, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "drawdown_series": drawdown_series,
            "sector_weights": sector_weights,
            "concentration": {
                "hhi": round(hhi, 4),
                "top5_pct": round(top5_concentration, 2),
            },
            "factors": factors,
            "stress_tests": stress_tests,
            "correlation_alerts": correlation_alerts,
            "concentration_risk": concentration_risk,
            "source": "computed",
        }

        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to compute risk metrics")
        return _empty_risk()


def _matrix_from_historicals(symbols: list[str], historicals: dict):
    """Aligned [T x len(symbols)] close-price matrix from MCP historicals
    (symbol -> [{begins_at, close_price}]). Columns align to `symbols`; symbols
    without data get a flat column (contribute ~0 returns)."""
    per: dict[str, dict[str, float]] = {}
    for s in symbols:
        col: dict[str, float] = {}
        for b in historicals.get(s, []):
            cp = b.get("close_price")
            try:
                if cp not in (None, ""):
                    col[b["begins_at"]] = float(cp)
            except (TypeError, ValueError):
                pass
        per[s] = col

    counts: dict[str, int] = {}
    for s in symbols:
        for d in per[s]:
            counts[d] = counts.get(d, 0) + 1
    need = max(1, len(symbols) // 2)
    dates = sorted(d for d, c in counts.items() if c >= need)
    if len(dates) < 10:
        return None, []

    matrix = np.zeros((len(dates), len(symbols)))
    for j, s in enumerate(symbols):
        col = per[s]
        last = next((col[d] for d in dates if d in col), 1.0)
        for i, d in enumerate(dates):
            if d in col:
                last = col[d]
            matrix[i, j] = last
    return matrix, dates


def _fetch_price_matrix(
    symbols: list[str], span: str = "3month", interval: str = "day"
) -> tuple[np.ndarray | None, list[str]]:
    """Fetch historical close prices for multiple symbols, aligned by date."""
    all_prices: dict[str, dict[str, float]] = {}
    all_dates: set[str] = set()

    for symbol in symbols:
        try:
            hist = r.get_stock_historicals(symbol, interval=interval, span=span)
            if not hist:
                continue
            prices = {}
            for h in hist:
                if h and "close_price" in h and "begins_at" in h:
                    date = h["begins_at"][:10]
                    prices[date] = float(h["close_price"])
                    all_dates.add(date)
            if prices:
                all_prices[symbol] = prices
        except Exception:
            logger.warning("Failed to fetch historicals for %s", symbol)

    if not all_prices or not all_dates:
        return None, []

    dates = sorted(all_dates)
    # Only include dates where we have data for at least half the symbols
    min_coverage = len(all_prices) // 2

    filtered_dates = []
    for d in dates:
        count = sum(1 for s in all_prices if d in all_prices[s])
        if count >= min_coverage:
            filtered_dates.append(d)

    if len(filtered_dates) < 10:
        return None, []

    # Build price matrix, forward-filling missing data
    ordered_symbols = [s for s in symbols if s in all_prices]
    matrix = np.zeros((len(filtered_dates), len(ordered_symbols)))

    for j, symbol in enumerate(ordered_symbols):
        prices = all_prices[symbol]
        last_price = None
        for i, d in enumerate(filtered_dates):
            if d in prices:
                last_price = prices[d]
            matrix[i, j] = last_price if last_price is not None else 0

    return matrix, filtered_dates


def _compute_concentration_risk(
    positions: list[dict],
    sector_weights: list[dict],
    sector_hhi: float,
) -> dict:
    """Compute 3-dimension concentration risk: sector, market cap, geography.

    Each dimension gets:
      - breakdown: list of {label, value, weight}
      - hhi: Herfindahl-Hirschman Index for that dimension
      - rating: "green" | "yellow" | "red"
      - top_holding_pct: largest single bucket %

    Overall score is a composite of the 3 dimensions.
    """
    from app.services.market_data import get_company_info

    all_equity = sum(p.get("equity", 0) for p in positions)
    if all_equity == 0:
        return _empty_concentration_risk()

    # Enrich positions with yfinance data (cached 24h per symbol)
    mcap_map: dict[str, float] = {}
    geo_map: dict[str, float] = {}

    for p in positions:
        symbol = p["symbol"]
        equity = p.get("equity", 0)
        try:
            info = get_company_info(symbol)
            tier = _mcap_tier(info.get("market_cap"))
            region = _country_to_region(info.get("country"))
        except Exception:
            tier = "Unknown"
            region = "Unknown"

        mcap_map[tier] = mcap_map.get(tier, 0) + equity
        geo_map[region] = geo_map.get(region, 0) + equity

    # ── Build market cap breakdown ──
    mcap_breakdown = []
    for tier, val in sorted(mcap_map.items(), key=lambda x: -x[1]):
        pct = (val / all_equity * 100)
        mcap_breakdown.append({"label": tier, "value": round(val, 2), "weight": round(pct, 2)})
    mcap_hhi = sum((b["weight"] / 100) ** 2 for b in mcap_breakdown)
    mcap_top = mcap_breakdown[0]["weight"] if mcap_breakdown else 0

    # ── Build geography breakdown ──
    geo_breakdown = []
    for region, val in sorted(geo_map.items(), key=lambda x: -x[1]):
        pct = (val / all_equity * 100)
        geo_breakdown.append({"label": region, "value": round(val, 2), "weight": round(pct, 2)})
    geo_hhi = sum((b["weight"] / 100) ** 2 for b in geo_breakdown)
    geo_top = geo_breakdown[0]["weight"] if geo_breakdown else 0

    # ── Normalize sector breakdown to use "label" key (matching ConcentrationBreakdown model) ──
    sector_breakdown = [
        {"label": sw["sector"], "value": sw["value"], "weight": sw["weight"]}
        for sw in sector_weights
    ]

    # ── Score each dimension ──
    sector_top = sector_weights[0]["weight"] if sector_weights else 0
    sector_rating = _rate_concentration(sector_hhi, sector_top, thresholds_hhi=(0.15, 0.25), thresholds_top=(40, 60))
    mcap_rating = _rate_concentration(mcap_hhi, mcap_top, thresholds_hhi=(0.30, 0.50), thresholds_top=(60, 80))
    geo_rating = _rate_concentration(geo_hhi, geo_top, thresholds_hhi=(0.40, 0.65), thresholds_top=(70, 90))

    # ── Composite score (0-100, higher = more concentrated = worse) ──
    rating_scores = {"green": 0, "yellow": 50, "red": 100}
    composite = int(
        rating_scores[sector_rating] * 0.45
        + rating_scores[mcap_rating] * 0.30
        + rating_scores[geo_rating] * 0.25
    )
    composite_rating = "green" if composite < 30 else ("yellow" if composite < 60 else "red")

    return {
        "score": composite,
        "rating": composite_rating,
        "dimensions": {
            "sector": {
                "breakdown": sector_breakdown,
                "hhi": round(sector_hhi, 4),
                "top_holding_pct": round(sector_top, 1),
                "rating": sector_rating,
            },
            "market_cap": {
                "breakdown": mcap_breakdown,
                "hhi": round(mcap_hhi, 4),
                "top_holding_pct": round(mcap_top, 1),
                "rating": mcap_rating,
            },
            "geography": {
                "breakdown": geo_breakdown,
                "hhi": round(geo_hhi, 4),
                "top_holding_pct": round(geo_top, 1),
                "rating": geo_rating,
            },
        },
    }


def _rate_concentration(
    hhi: float,
    top_pct: float,
    thresholds_hhi: tuple[float, float] = (0.15, 0.25),
    thresholds_top: tuple[float, float] = (40, 60),
) -> str:
    """Rate concentration as green/yellow/red based on HHI and top-bucket percentage."""
    hhi_yellow, hhi_red = thresholds_hhi
    top_yellow, top_red = thresholds_top
    if hhi >= hhi_red or top_pct >= top_red:
        return "red"
    if hhi >= hhi_yellow or top_pct >= top_yellow:
        return "yellow"
    return "green"


def _empty_concentration_risk() -> dict:
    empty_dim = {"breakdown": [], "hhi": 0.0, "top_holding_pct": 0.0, "rating": "green"}
    return {
        "score": 0,
        "rating": "green",
        "dimensions": {
            "sector": empty_dim.copy(),
            "market_cap": empty_dim.copy(),
            "geography": empty_dim.copy(),
        },
    }


def _compute_correlation_alerts(
    returns: np.ndarray, symbols: list[str]
) -> list[dict]:
    """
    Pro-level correlation analysis using a hybrid model:

    1. **Full-period Pearson** (90 days) — standard linear correlation
    2. **Rolling 30-day Spearman rank correlation** — captures non-linear monotonic
       relationships and is robust to outliers. We take the MAX rolling window value
       to detect persistent co-movement even if recent weeks diverged.

    Combined score = max(pearson, spearman_rolling_max) to catch the strongest signal.
    Threshold: 0.65 (institutional standard for diversification alerts).
    """
    CORR_THRESHOLD = 0.65
    ROLLING_WINDOW = 30  # trading days (~6 weeks)

    n_days, n_assets = returns.shape
    if n_assets < 2:
        return []

    # 1. Full-period Pearson correlation matrix
    pearson_corr = np.corrcoef(returns.T)
    pearson_corr = np.nan_to_num(pearson_corr, nan=0.0)

    # 2. Rolling Spearman rank correlation (captures non-linear relationships)
    # For each pair, compute Spearman over rolling 30-day windows and take the max
    spearman_max = np.zeros((n_assets, n_assets))

    if n_days >= ROLLING_WINDOW:
        n_windows = n_days - ROLLING_WINDOW + 1
        for start in range(0, n_windows, 3):  # step by 3 for efficiency
            window = returns[start : start + ROLLING_WINDOW]
            for i in range(n_assets):
                for j in range(i + 1, n_assets):
                    rho, _ = scipy_stats.spearmanr(window[:, i], window[:, j])
                    rho = 0.0 if np.isnan(rho) else rho
                    if rho > spearman_max[i, j]:
                        spearman_max[i, j] = rho
                        spearman_max[j, i] = rho

    # 3. Combine: use max of full-period Pearson and rolling Spearman max
    alerts = []
    for i in range(n_assets):
        for j in range(i + 1, n_assets):
            pearson_val = float(pearson_corr[i, j])
            spearman_val = float(spearman_max[i, j])
            combined = max(pearson_val, spearman_val)

            if combined >= CORR_THRESHOLD:
                alerts.append({
                    "pair": [symbols[i], symbols[j]],
                    "correlation": round(combined, 3),
                    "pearson": round(pearson_val, 3),
                    "spearman": round(spearman_val, 3),
                    "method": "pearson" if pearson_val >= spearman_val else "spearman",
                })

    alerts.sort(key=lambda x: x["correlation"], reverse=True)
    return alerts


def _compute_factor_exposure(
    portfolio_returns: np.ndarray,
    annualized_vol: float,
    sector_weights: list[dict],
    positions: list[dict],
    dates: list[str],
    historicals: dict | None = None,
) -> list[dict]:
    """
    Compute factor exposure using OLS regression against SPY (market benchmark).

    Market Beta: actual regression of portfolio returns against SPY daily returns.
    Other factors: sector-weight-derived estimates (improved from pure heuristics).
    """
    # Fetch SPY historical data to compute real market beta
    market_beta = 1.0  # default if regression fails
    r_squared = 0.0
    try:
        # Prefer SPY bars injected from the MCP; fall back to legacy fetch.
        spy_hist = (historicals or {}).get("SPY")
        if not spy_hist:
            spy_hist = r.get_stock_historicals("SPY", interval="day", span="3month")
        if spy_hist and len(spy_hist) > 10:
            # Key by the same begins_at the portfolio `dates` use, then align.
            spy_prices: dict[str, float] = {}
            for h in spy_hist:
                if h and h.get("close_price") and h.get("begins_at"):
                    spy_prices[h["begins_at"]] = float(h["close_price"])
            spy_aligned = [spy_prices.get(d, 0.0) for d in dates]

            spy_arr = np.array(spy_aligned)
            if len(spy_arr) > 1 and spy_arr[0] > 0:
                spy_returns = np.diff(spy_arr) / spy_arr[:-1]
                spy_returns = np.nan_to_num(spy_returns, nan=0.0, posinf=0.0, neginf=0.0)

                # Ensure same length
                min_len = min(len(portfolio_returns), len(spy_returns))
                if min_len >= 20:
                    pr = portfolio_returns[:min_len]
                    sr = spy_returns[:min_len]

                    # OLS regression: portfolio = alpha + beta * SPY + epsilon
                    slope, intercept, r_val, p_val, std_err = scipy_stats.linregress(sr, pr)
                    market_beta = float(slope)
                    r_squared = float(r_val ** 2)
    except Exception:
        logger.warning("SPY regression failed, using default beta=1.0")

    # Clamp beta to reasonable range
    market_beta = max(0.1, min(3.0, market_beta))
    beta_exposure = min(95, max(5, int(market_beta * 50)))  # beta=1.0 → 50%, beta=2.0 → 100%
    beta_status = "high" if market_beta > 1.3 else ("low" if market_beta < 0.7 else "ok")

    # Sector-derived factors (improved)
    tech_weight = sum(
        sw["weight"] for sw in sector_weights
        if any(k in sw["sector"].lower() for k in ["tech", "electronic", "software"])
    )

    # Momentum: compare recent 5-day return vs 30-day average
    recent_5d = float(portfolio_returns[-5:].mean()) if len(portfolio_returns) >= 5 else 0
    avg_30d = float(portfolio_returns[-30:].mean()) if len(portfolio_returns) >= 30 else 0
    momentum_score = min(95, max(5, int(50 + (recent_5d - avg_30d) * 2000)))

    factors = [
        {
            "name": "Market Beta",
            "exposure": beta_exposure,
            "status": beta_status,
            "detail": f"β={market_beta:.2f}, R²={r_squared:.2f}",
        },
        {
            "name": "Growth/Tech",
            "exposure": min(95, max(5, int(tech_weight))),
            "status": "high" if tech_weight > 50 else "ok",
        },
        {
            "name": "Size (Small Cap)",
            "exposure": min(95, max(5, int(30 - len(positions) * 0.5))),
            "status": "ok",
        },
        {
            "name": "Momentum",
            "exposure": momentum_score,
            "status": "high" if momentum_score > 75 else ("low" if momentum_score < 25 else "ok"),
        },
        {
            "name": "Volatility",
            "exposure": min(95, max(5, int(annualized_vol * 200))),
            "status": "high" if annualized_vol > 0.3 else "ok",
        },
        {
            "name": "Rate Sensitivity",
            "exposure": min(95, max(5, int(tech_weight * 0.8))),
            "status": "high" if tech_weight > 60 else "ok",
        },
    ]
    return factors


def _compute_stress_tests(sector_weights: list[dict], volatility: float) -> list[dict]:
    """Estimate portfolio impact under historical + modern stress scenarios."""
    scenario_impacts = {
        "2008 Financial Crisis": {
            "Technology": -50, "Electronic Technology": -50, "Technology Services": -45,
            "Finance": -60, "Retail Trade": -40, "Health Technology": -20,
            "Utilities": -15, "Defense": -20, "Commodities": -40, "ETF": -38,
            "Unknown": -35, "_default": -35,
        },
        "COVID Crash (Mar 2020)": {
            "Technology": -25, "Electronic Technology": -30, "Technology Services": -20,
            "Finance": -35, "Retail Trade": -30, "Health Technology": -10,
            "Utilities": -20, "Defense": -15, "Commodities": -30, "ETF": -25,
            "Unknown": -25, "_default": -25,
        },
        "Rate Hike +200bps": {
            "Technology": -20, "Electronic Technology": -25, "Technology Services": -18,
            "Finance": 5, "Retail Trade": -10, "Health Technology": -12,
            "Utilities": -15, "Defense": -5, "Commodities": -8, "ETF": -12,
            "Unknown": -12, "_default": -12,
        },
        "Tech Selloff (-30%)": {
            "Technology": -30, "Electronic Technology": -35, "Technology Services": -28,
            "Finance": -5, "Retail Trade": -10, "Health Technology": -8,
            "Utilities": -3, "Defense": -5, "Commodities": -5, "ETF": -15,
            "Unknown": -10, "_default": -10,
        },
        "Stagflation": {
            "Technology": -15, "Electronic Technology": -18, "Technology Services": -12,
            "Finance": -20, "Retail Trade": -25, "Health Technology": -5,
            "Utilities": 5, "Defense": 0, "Commodities": 10, "ETF": -10,
            "Unknown": -10, "_default": -10,
        },
        "AI Bubble Burst": {
            "Technology": -40, "Electronic Technology": -45, "Technology Services": -38,
            "Finance": -15, "Retail Trade": -12, "Health Technology": -8,
            "Utilities": -3, "Defense": -5, "Commodities": -5, "ETF": -20,
            "Unknown": -15, "_default": -15,
        },
        "Trade War Escalation": {
            "Technology": -22, "Electronic Technology": -28, "Technology Services": -15,
            "Finance": -15, "Retail Trade": -20, "Health Technology": -8,
            "Utilities": -5, "Defense": 5, "Commodities": -15, "ETF": -18,
            "Unknown": -15, "_default": -15,
        },
        "Sovereign Debt Crisis": {
            "Technology": -18, "Electronic Technology": -20, "Technology Services": -15,
            "Finance": -40, "Retail Trade": -20, "Health Technology": -10,
            "Utilities": -12, "Defense": -8, "Commodities": -10, "ETF": -22,
            "Unknown": -18, "_default": -18,
        },
    }

    tests = []
    for scenario, impacts in scenario_impacts.items():
        weighted_impact = 0.0
        for sw in sector_weights:
            sector = sw["sector"]
            weight = sw["weight"] / 100
            impact = impacts.get(sector, impacts["_default"])
            weighted_impact += weight * impact
        tests.append({
            "scenario": scenario,
            "impact": round(weighted_impact, 1),
        })

    return tests


def _empty_risk() -> dict:
    """Return default risk data when computation isn't possible."""
    return {
        "score": 50,
        "daily_var_95": -2.0,
        "monthly_cvar_95": -8.0,
        "risk_budget_used": 0.5,
        "portfolio_volatility": 15.0,
        "max_drawdown": -10.0,
        "drawdown_series": [],
        "sector_weights": [],
        "concentration": {"hhi": 0.0, "top5_pct": 0.0},
        "factors": [
            {"name": "Market Beta", "exposure": 60, "status": "ok"},
            {"name": "Growth/Tech", "exposure": 50, "status": "ok"},
            {"name": "Size (Small Cap)", "exposure": 20, "status": "ok"},
            {"name": "Momentum", "exposure": 50, "status": "ok"},
            {"name": "Volatility", "exposure": 30, "status": "ok"},
            {"name": "Rate Sensitivity", "exposure": 40, "status": "ok"},
        ],
        "stress_tests": [
            {"scenario": "2008 Financial Crisis", "impact": -35.0},
            {"scenario": "COVID Crash (Mar 2020)", "impact": -25.0},
            {"scenario": "Rate Hike +200bps", "impact": -12.0},
            {"scenario": "Tech Selloff (-30%)", "impact": -15.0},
            {"scenario": "Stagflation", "impact": -10.0},
            {"scenario": "AI Bubble Burst", "impact": -15.0},
            {"scenario": "Trade War Escalation", "impact": -15.0},
            {"scenario": "Sovereign Debt Crisis", "impact": -18.0},
        ],
        "correlation_alerts": [],
        "concentration_risk": _empty_concentration_risk(),
        "source": "default",
    }
