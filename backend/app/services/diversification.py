"""
Behavioral Risk Profiling & Diversification Suggestions engine.

Infers real risk profile from portfolio composition (not self-reported).
Computes diversification gaps and suggests specific ETFs to reduce downside.
Produces before/after impact comparisons.

Uses data already computed by risk.py + position-level analysis.
"""

import logging
import math

logger = logging.getLogger(__name__)

# ── Persona definitions ──

PERSONAS = [
    {
        "name": "Guardian",
        "range": (0, 20),
        "description": "Your portfolio is built for preservation. You prioritize stability over growth.",
        "emoji": "shield",
    },
    {
        "name": "Steady",
        "range": (21, 40),
        "description": "A conservative approach with some growth exposure. You sleep well at night.",
        "emoji": "anchor",
    },
    {
        "name": "Balanced",
        "range": (41, 60),
        "description": "A mix of growth and stability. You accept moderate ups and downs for reasonable returns.",
        "emoji": "scale",
    },
    {
        "name": "Growth Seeker",
        "range": (61, 80),
        "description": "You lean into growth and accept higher volatility for bigger potential returns.",
        "emoji": "rocket",
    },
    {
        "name": "Thrill Rider",
        "range": (81, 100),
        "description": "Your portfolio is concentrated and aggressive. Big potential gains — and big potential losses.",
        "emoji": "fire",
    },
]

# ── ETF candidates for diversification suggestions ──

ETF_CANDIDATES = [
    {
        "symbol": "XLV",
        "name": "Health Care Select Sector SPDR",
        "category": "Healthcare",
        "fills_gap": "Health Technology",
        "expense_ratio": 0.09,
        "return_2022": -2.0,
        "return_2020": -10.0,
        "return_2008": -23.0,
        "tech_correlation": 0.45,
        "reason": "Adds defensive exposure. Healthcare dropped only 2% in 2022 while tech dropped 29%.",
    },
    {
        "symbol": "BND",
        "name": "Vanguard Total Bond Market ETF",
        "category": "Bonds",
        "fills_gap": "Fixed Income",
        "expense_ratio": 0.03,
        "return_2022": -13.0,
        "return_2020": 1.0,
        "return_2008": 5.0,
        "tech_correlation": -0.15,
        "reason": "11,000+ securities with low correlation to stocks. The foundation of any balanced portfolio.",
    },
    {
        "symbol": "XLE",
        "name": "Energy Select Sector SPDR",
        "category": "Energy",
        "fills_gap": "Energy Minerals",
        "expense_ratio": 0.09,
        "return_2022": 59.0,
        "return_2020": -35.0,
        "return_2008": -36.0,
        "tech_correlation": 0.15,
        "reason": "Energy was UP 59% in 2022 while tech crashed. Moves opposite to your current holdings.",
    },
    {
        "symbol": "XLP",
        "name": "Consumer Staples Select SPDR",
        "category": "Consumer Staples",
        "fills_gap": "Consumer Non-Durables",
        "expense_ratio": 0.09,
        "return_2022": -5.2,
        "return_2020": -12.0,
        "return_2008": -15.0,
        "tech_correlation": 0.50,
        "reason": "Recession-resistant companies (P&G, Coca-Cola, Walmart). Steady cash flows in any market.",
    },
    {
        "symbol": "XLU",
        "name": "Utilities Select Sector SPDR",
        "category": "Utilities",
        "fills_gap": "Utilities",
        "expense_ratio": 0.09,
        "return_2022": -0.6,
        "return_2020": -20.0,
        "return_2008": -29.0,
        "tech_correlation": 0.30,
        "reason": "Stable cash flows and dividends. Down only 0.6% in 2022 — the ultimate portfolio anchor.",
    },
    {
        "symbol": "IXUS",
        "name": "iShares Core MSCI International",
        "category": "International",
        "fills_gap": "Geographic",
        "expense_ratio": 0.07,
        "return_2022": -16.0,
        "return_2020": -22.0,
        "return_2008": -45.0,
        "tech_correlation": 0.65,
        "reason": "Geographic diversification across 4,000+ international stocks. Reduces single-country risk.",
    },
    {
        "symbol": "GLDM",
        "name": "SPDR Gold MiniShares",
        "category": "Gold",
        "fills_gap": "Alternatives",
        "expense_ratio": 0.10,
        "return_2022": -1.0,
        "return_2020": 25.0,
        "return_2008": 5.0,
        "tech_correlation": -0.05,
        "reason": "Safe haven asset with near-zero equity correlation. Historically rises during market panic.",
    },
    {
        "symbol": "VTV",
        "name": "Vanguard Value ETF",
        "category": "Value",
        "fills_gap": "Value",
        "expense_ratio": 0.04,
        "return_2022": -2.1,
        "return_2020": -26.0,
        "return_2008": -36.0,
        "tech_correlation": 0.70,
        "reason": "Value stocks outperform when growth sells off. Different factor exposure than tech-heavy portfolios.",
    },
    {
        "symbol": "SCHP",
        "name": "Schwab US TIPS ETF",
        "category": "TIPS",
        "fills_gap": "Inflation Protection",
        "expense_ratio": 0.03,
        "return_2022": -12.0,
        "return_2020": 8.0,
        "return_2008": -2.0,
        "tech_correlation": -0.10,
        "reason": "Inflation protection. Treasury bonds that adjust with CPI — a hedge most retail investors miss.",
    },
]

# ── Reference balanced allocation (sector weights %) ──

_REFERENCE_ALLOCATION = {
    "Technology": 15,
    "Technology Services": 10,
    "Electronic Technology": 10,
    "Health Technology": 8,
    "Finance": 10,
    "Consumer Non-Durables": 7,
    "Consumer Durables": 5,
    "Retail Trade": 5,
    "Energy Minerals": 5,
    "Utilities": 5,
    "Process Industries": 4,
    "Producer Manufacturing": 4,
    "Transportation": 3,
    "Communications": 3,
    "Distribution Services": 3,
    "Commercial Services": 3,
}

# ── Sector returns in major crashes (for stress simulation) ──

_SECTOR_RETURNS_2022: dict[str, float] = {
    "Technology": -28.9,
    "Technology Services": -28.9,
    "Electronic Technology": -35.0,
    "Finance": -10.5,
    "Health Technology": -2.0,
    "Consumer Non-Durables": -5.2,
    "Consumer Durables": -22.0,
    "Retail Trade": -25.0,
    "Energy Minerals": 59.0,
    "Utilities": -0.6,
    "Process Industries": -12.0,
    "Producer Manufacturing": -15.0,
    "Transportation": -18.0,
    "Communications": -40.4,
    "Distribution Services": -20.0,
    "Commercial Services": -15.0,
    "ETF": -20.0,
    "Unknown": -20.0,
}

# 2008 Global Financial Crisis — sector returns (peak-to-trough)
# Data from spec Section 4: Consumer Staples -15%, Healthcare -23%,
# Utilities -29%, Tech -41%, Financials -55%
_SECTOR_RETURNS_2008: dict[str, float] = {
    "Technology": -41.0,
    "Technology Services": -41.0,
    "Electronic Technology": -45.0,
    "Finance": -55.0,
    "Health Technology": -23.0,
    "Consumer Non-Durables": -15.0,
    "Consumer Durables": -45.0,
    "Retail Trade": -40.0,
    "Energy Minerals": -36.0,
    "Utilities": -29.0,
    "Process Industries": -40.0,
    "Producer Manufacturing": -35.0,
    "Transportation": -45.0,
    "Communications": -50.0,
    "Distribution Services": -35.0,
    "Commercial Services": -30.0,
    "ETF": -38.0,
    "Unknown": -38.0,
}

# 2020 COVID crash — sector returns (Feb-Mar 2020, ~5 week drawdown)
# S&P -34%, Nasdaq -30%. ETF-calibrated: XLV -10%, XLE -35%, XLP -12%,
# XLU -20%, BND +1%. V-shaped recovery benefited tech.
_SECTOR_RETURNS_2020: dict[str, float] = {
    "Technology": -30.0,
    "Technology Services": -25.0,
    "Electronic Technology": -35.0,
    "Finance": -38.0,
    "Health Technology": -10.0,
    "Consumer Non-Durables": -12.0,
    "Consumer Durables": -35.0,
    "Retail Trade": -30.0,
    "Energy Minerals": -35.0,
    "Utilities": -20.0,
    "Process Industries": -30.0,
    "Producer Manufacturing": -25.0,
    "Transportation": -40.0,
    "Communications": -25.0,
    "Distribution Services": -25.0,
    "Commercial Services": -20.0,
    "ETF": -30.0,
    "Unknown": -30.0,
}

# Map of all scenarios for iteration
_CRASH_SCENARIOS = {
    "2022": {"name": "2022 Rate Shock", "returns": _SECTOR_RETURNS_2022},
    "2020": {"name": "COVID 2020", "returns": _SECTOR_RETURNS_2020},
    "2008": {"name": "2008 Financial Crisis", "returns": _SECTOR_RETURNS_2008},
}


def _score_linear(value: float, low: float, high: float) -> float:
    """Score 0-100 linearly between low (=0) and high (=100), clamped."""
    if value <= low:
        return 0.0
    if value >= high:
        return 100.0
    return (value - low) / (high - low) * 100.0


def compute_risk_profile(
    positions: list[dict],
    risk_metrics: dict,
    portfolio_value: float,
) -> dict:
    """
    Compute behavioral risk profile from portfolio data + risk metrics.

    Returns dict with:
    - behavioral_score (0-100)
    - persona (name + description)
    - factor_breakdown (4 categories with individual scores)
    - key_findings (bulleted insights)
    - diversification_suggestions (top 3 ETFs with impact)
    - before_after (current vs suggested comparison)
    """
    if not positions or portfolio_value <= 0:
        return _empty_profile()

    # ── Extract position-level data ──
    equities = [p.get("equity", 0) for p in positions]
    total_equity = sum(equities)
    if total_equity <= 0:
        return _empty_profile()

    weights = [e / total_equity for e in equities]
    sorted_weights = sorted(weights, reverse=True)
    n_holdings = len(positions)

    top1_pct = sorted_weights[0] * 100 if sorted_weights else 0
    top3_pct = sum(sorted_weights[:3]) * 100 if len(sorted_weights) >= 3 else sum(sorted_weights) * 100

    # Sector data from risk_metrics
    sector_weights = risk_metrics.get("sector_weights", [])
    sector_hhi = risk_metrics.get("concentration", {}).get("hhi", 0)
    volatility = risk_metrics.get("portfolio_volatility", 20) / 100  # stored as %
    max_dd = abs(risk_metrics.get("max_drawdown", 10))  # stored as negative %
    correlation_alerts = risk_metrics.get("correlation_alerts", [])
    stress_tests = risk_metrics.get("stress_tests", [])
    factors = risk_metrics.get("factors", [])

    # Extract market beta from factor exposure
    market_beta = 1.0
    for f in factors:
        if f.get("name") == "Market Beta":
            detail = f.get("detail", "")
            if "β=" in detail:
                try:
                    market_beta = float(detail.split("β=")[1].split(",")[0])
                except (ValueError, IndexError):
                    pass
            break

    # Tech concentration
    tech_keywords = {"tech", "electronic", "software"}
    tech_weight = sum(
        sw["weight"] for sw in sector_weights
        if any(k in sw.get("sector", "").lower() for k in tech_keywords)
    )
    n_sectors = len([sw for sw in sector_weights if sw.get("weight", 0) > 2])

    # ── Category A: Composition (40%) ──
    beta_score = _score_linear(market_beta, 0.7, 2.0)
    holdings_score = _score_linear(15 - n_holdings, 0, 12)  # fewer = riskier
    tech_score = _score_linear(tech_weight, 15, 80)
    composition_score = (
        beta_score * 0.35
        + holdings_score * 0.30
        + tech_score * 0.35
    )

    # ── Category B: Concentration (30%) ──
    top1_score = _score_linear(top1_pct, 10, 50)
    hhi_score = _score_linear(sector_hhi, 0.08, 0.40)
    top3_score = _score_linear(top3_pct, 25, 80)
    concentration_score = (
        top1_score * 0.35
        + hhi_score * 0.35
        + top3_score * 0.30
    )

    # ── Category C: Volatility (20%) ──
    vol_score = _score_linear(volatility, 0.12, 0.40)
    dd_score = _score_linear(max_dd, 8, 40)
    worst_stress = min((t.get("impact", 0) for t in stress_tests), default=-20)
    stress_score = _score_linear(abs(worst_stress), 12, 50)
    volatility_score = (
        vol_score * 0.40
        + dd_score * 0.35
        + stress_score * 0.25
    )

    # ── Category D: Correlation (10%) ──
    n_corr_alerts = len(correlation_alerts)
    corr_score = _score_linear(n_corr_alerts, 0, 8)

    # ── Composite ──
    behavioral_score = int(
        composition_score * 0.40
        + concentration_score * 0.30
        + volatility_score * 0.20
        + corr_score * 0.10
    )
    behavioral_score = max(0, min(100, behavioral_score))

    # ── Persona ──
    persona = PERSONAS[-1]  # default: Thrill Rider
    for p in PERSONAS:
        low, high = p["range"]
        if low <= behavioral_score <= high:
            persona = p
            break

    # ── Key Findings ──
    findings = _generate_findings(
        positions, sector_weights, tech_weight, top1_pct, top3_pct,
        n_holdings, n_sectors, market_beta, n_corr_alerts, portfolio_value,
        max_dd, volatility,
    )

    # ── Diversification Suggestions ──
    suggestions = _compute_suggestions(
        positions, sector_weights, portfolio_value, stress_tests,
    )

    # ── Before / After ──
    before_after = _compute_before_after(
        positions, sector_weights, portfolio_value,
        behavioral_score, max_dd, n_sectors, sector_hhi, suggestions,
    )

    return {
        "behavioral_score": behavioral_score,
        "persona": {
            "name": persona["name"],
            "description": persona["description"],
            "emoji": persona["emoji"],
        },
        "factor_breakdown": {
            "composition": {
                "score": round(composition_score),
                "weight": 0.40,
                "details": {
                    "portfolio_beta": round(market_beta, 2),
                    "num_holdings": n_holdings,
                    "tech_weight_pct": round(tech_weight, 1),
                },
            },
            "concentration": {
                "score": round(concentration_score),
                "weight": 0.30,
                "details": {
                    "top1_pct": round(top1_pct, 1),
                    "top3_pct": round(top3_pct, 1),
                    "sector_hhi": round(sector_hhi, 4),
                },
            },
            "volatility": {
                "score": round(volatility_score),
                "weight": 0.20,
                "details": {
                    "annualized_vol_pct": round(volatility * 100, 1),
                    "max_drawdown_pct": round(max_dd, 1),
                    "worst_stress_pct": round(abs(worst_stress), 1),
                },
            },
            "correlation": {
                "score": round(corr_score),
                "weight": 0.10,
                "details": {
                    "high_corr_pairs": n_corr_alerts,
                },
            },
        },
        "key_findings": findings,
        "diversification_suggestions": suggestions,
        "before_after": before_after,
        "portfolio_value": round(portfolio_value, 2),
    }


def _generate_findings(
    positions: list[dict],
    sector_weights: list[dict],
    tech_weight: float,
    top1_pct: float,
    top3_pct: float,
    n_holdings: int,
    n_sectors: int,
    market_beta: float,
    n_corr_alerts: int,
    portfolio_value: float,
    max_dd: float,
    volatility: float,
) -> list[dict]:
    """Generate key insight bullets from portfolio data."""
    findings: list[dict] = []
    top_symbol = max(positions, key=lambda p: p.get("equity", 0)).get("symbol", "?")

    # Concentration findings
    if top1_pct > 25:
        findings.append({
            "type": "critical",
            "text": f"{top_symbol} alone is {top1_pct:.0f}% of your portfolio. "
                    f"That's ${portfolio_value * top1_pct / 100:,.0f} riding on one stock.",
        })

    if tech_weight > 50:
        findings.append({
            "type": "critical",
            "text": f"{tech_weight:.0f}% of your money is in tech. "
                    f"That's a big bet on one sector.",
        })
    elif tech_weight > 30:
        findings.append({
            "type": "warning",
            "text": f"{tech_weight:.0f}% technology sector concentration. "
                    f"Above the 15-20% typical for a balanced portfolio.",
        })

    if n_sectors <= 2:
        findings.append({
            "type": "critical",
            "text": f"Only {n_sectors} sector{'s' if n_sectors > 1 else ''} represented. "
                    f"A balanced portfolio typically spans 6-8 sectors.",
        })

    if top3_pct > 60:
        findings.append({
            "type": "warning",
            "text": f"Your top 3 positions make up {top3_pct:.0f}% of the portfolio. "
                    f"This amplifies single-stock risk.",
        })

    # Risk findings
    if market_beta > 1.3:
        findings.append({
            "type": "warning",
            "text": f"Portfolio beta of {market_beta:.2f}x the market. "
                    f"When the market drops 10%, you'd drop ~{market_beta * 10:.0f}%.",
        })

    if max_dd > 25:
        dollar_loss = portfolio_value * max_dd / 100
        findings.append({
            "type": "critical",
            "text": f"Max drawdown of {max_dd:.1f}% in the last 90 days — "
                    f"that's ${dollar_loss:,.0f} from peak to trough.",
        })

    if n_corr_alerts > 3:
        findings.append({
            "type": "warning",
            "text": f"{n_corr_alerts} highly correlated stock pairs. "
                    f"Your stocks move together — you may have less diversification than you think.",
        })

    if n_holdings < 5:
        findings.append({
            "type": "warning",
            "text": f"Only {n_holdings} holdings. Research shows 10-20 stocks across "
                    f"sectors eliminates most stock-specific risk.",
        })

    # Positive findings
    if n_sectors >= 5:
        findings.append({
            "type": "positive",
            "text": f"Good sector spread — {n_sectors} sectors represented in your portfolio.",
        })

    if market_beta < 1.0:
        findings.append({
            "type": "positive",
            "text": f"Portfolio beta of {market_beta:.2f} — less volatile than the overall market.",
        })

    if volatility < 0.18:
        findings.append({
            "type": "positive",
            "text": f"Annualized volatility of {volatility * 100:.1f}% is within the normal range.",
        })

    return findings[:8]  # Cap at 8 findings


def _compute_suggestions(
    positions: list[dict],
    sector_weights: list[dict],
    portfolio_value: float,
    stress_tests: list[dict],
) -> list[dict]:
    """
    Gap-fill algorithm: compare user's sectors to reference allocation,
    identify biggest gaps, suggest best ETFs for each gap.
    """
    # Current sector map
    current_sectors: dict[str, float] = {}
    for sw in sector_weights:
        current_sectors[sw["sector"]] = sw["weight"]

    # Check what the portfolio is missing
    has_healthcare = any(
        "health" in sw.get("sector", "").lower() for sw in sector_weights
        if sw.get("weight", 0) > 3
    )
    has_energy = any(
        "energy" in sw.get("sector", "").lower() for sw in sector_weights
        if sw.get("weight", 0) > 3
    )
    has_staples = any(
        "non-durable" in sw.get("sector", "").lower()
        or "staple" in sw.get("sector", "").lower()
        for sw in sector_weights
        if sw.get("weight", 0) > 3
    )
    has_utilities = any(
        "util" in sw.get("sector", "").lower() for sw in sector_weights
        if sw.get("weight", 0) > 3
    )
    has_international = False  # Robinhood is primarily US equities
    has_bonds = False  # Stock portfolio — no fixed income

    # Score each ETF candidate by relevance to this portfolio
    scored: list[dict] = []
    for etf in ETF_CANDIDATES:
        relevance = 0.0

        # Higher relevance if portfolio is missing the sector
        if etf["category"] == "Healthcare" and not has_healthcare:
            relevance += 40
        elif etf["category"] == "Energy" and not has_energy:
            relevance += 35
        elif etf["category"] == "Consumer Staples" and not has_staples:
            relevance += 30
        elif etf["category"] == "Utilities" and not has_utilities:
            relevance += 30
        elif etf["category"] == "Bonds" and not has_bonds:
            relevance += 35
        elif etf["category"] == "International" and not has_international:
            relevance += 25
        elif etf["category"] == "Gold":
            relevance += 20  # Always somewhat relevant
        elif etf["category"] == "Value":
            # More relevant for growth-heavy portfolios
            tech_weight = sum(
                sw["weight"] for sw in sector_weights
                if "tech" in sw.get("sector", "").lower()
            )
            if tech_weight > 40:
                relevance += 30

        # Bonus for low tech correlation (more diversifying)
        relevance += (1.0 - etf["tech_correlation"]) * 20

        # Bonus for strong 2022 performance (proves crash resilience)
        if etf["return_2022"] > 0:
            relevance += 30
        elif etf["return_2022"] > -5:
            relevance += 15

        if relevance > 0:
            # Estimate drawdown improvement if 10% allocated across all scenarios
            impact_data: dict[str, dict] = {}
            etf_returns = {
                "2022": etf["return_2022"],
                "2020": etf["return_2020"],
                "2008": etf["return_2008"],
            }
            best_savings = 0.0
            for sc_key, sc in _CRASH_SCENARIOS.items():
                current_impact = _estimate_scenario_impact(sector_weights, sc["returns"])
                new_impact = current_impact * 0.90 + etf_returns[sc_key] * 0.10
                improvement = abs(current_impact) - abs(new_impact)
                savings = portfolio_value * improvement / 100
                impact_data[sc_key] = {
                    "improvement_pct": round(improvement, 1),
                    "savings": round(savings, 0),
                }
                best_savings = max(best_savings, savings)

            scored.append({
                "symbol": etf["symbol"],
                "name": etf["name"],
                "category": etf["category"],
                "expense_ratio": etf["expense_ratio"],
                "reason": etf["reason"],
                "suggested_allocation_pct": 10,
                "suggested_allocation_dollar": round(portfolio_value * 0.10, 2),
                "impact": {
                    "drawdown_improvement_pct": impact_data["2022"]["improvement_pct"],
                    "crash_savings_2022": impact_data["2022"]["savings"],
                    "crash_savings_2020": impact_data["2020"]["savings"],
                    "crash_savings_2008": impact_data["2008"]["savings"],
                    "annual_cost": round(portfolio_value * 0.10 * etf["expense_ratio"] / 100, 2),
                },
                "_relevance": relevance,
                "_return_2022": etf["return_2022"],
            })

    # Sort by relevance, take top 3
    scored.sort(key=lambda x: x["_relevance"], reverse=True)
    suggestions = []
    for s in scored[:3]:
        # Clean internal scoring fields
        s.pop("_relevance", None)
        s.pop("_return_2022", None)
        suggestions.append(s)

    return suggestions


def _estimate_scenario_impact(
    sector_weights: list[dict],
    scenario_returns: dict[str, float],
) -> float:
    """Estimate portfolio return in a given crash scenario based on sector weights."""
    impact = 0.0
    default = sum(scenario_returns.values()) / max(len(scenario_returns), 1)
    for sw in sector_weights:
        sector = sw.get("sector", "Unknown")
        weight = sw.get("weight", 0) / 100
        sector_return = scenario_returns.get(sector, default)
        impact += weight * sector_return
    return impact


def _compute_before_after(
    positions: list[dict],
    sector_weights: list[dict],
    portfolio_value: float,
    behavioral_score: int,
    max_dd: float,
    n_sectors: int,
    sector_hhi: float,
    suggestions: list[dict],
) -> dict:
    """Compute before/after comparison if all suggestions are applied."""
    # Effective positions: use POSITION-LEVEL HHI (1/Σwᵢ²), not sector HHI
    total_equity = sum(p.get("equity", 0) for p in positions)
    if total_equity > 0:
        position_hhi = sum((p.get("equity", 0) / total_equity) ** 2 for p in positions)
        effective_positions = round(1.0 / position_hhi, 1) if position_hhi > 0 else len(positions)
    else:
        effective_positions = 0

    # Projected state with suggestions applied
    total_suggestion_pct = sum(s["suggested_allocation_pct"] for s in suggestions)
    scale_factor = (100 - total_suggestion_pct) / 100

    # New sector count + effective positions
    new_sectors = n_sectors + len(suggestions)
    if total_equity > 0:
        new_pos_hhi = sum(
            ((p.get("equity", 0) / total_equity) * scale_factor) ** 2 for p in positions
        )
        for s in suggestions:
            new_pos_hhi += (s["suggested_allocation_pct"] / 100) ** 2
        new_effective = round(1.0 / new_pos_hhi, 1) if new_pos_hhi > 0 else 0
    else:
        new_effective = 0

    # Compute crash impacts for all 3 scenarios
    scenario_results: dict[str, dict] = {}
    for sc_key, sc in _CRASH_SCENARIOS.items():
        current_impact = _estimate_scenario_impact(sector_weights, sc["returns"])
        new_impact = current_impact * scale_factor
        for s in suggestions:
            etf = next((e for e in ETF_CANDIDATES if e["symbol"] == s["symbol"]), None)
            if etf:
                ret_key = f"return_{sc_key}"
                new_impact += etf.get(ret_key, -20.0) * s["suggested_allocation_pct"] / 100
        scenario_results[sc_key] = {
            "current_pct": round(current_impact, 1),
            "current_dollar": round(portfolio_value * current_impact / 100, 0),
            "suggested_pct": round(new_impact, 1),
            "suggested_dollar": round(portfolio_value * new_impact / 100, 0),
            "savings_dollar": round(
                abs(portfolio_value * current_impact / 100)
                - abs(portfolio_value * new_impact / 100),
                0,
            ),
        }

    # Estimate new max drawdown using 2022 crash ratio as proxy
    r2022 = scenario_results["2022"]
    current_2022 = r2022["current_pct"]
    new_2022 = r2022["suggested_pct"]
    if abs(current_2022) > 0:
        crash_reduction_ratio = abs(new_2022) / abs(current_2022)
    else:
        crash_reduction_ratio = 0.7
    new_max_dd = max_dd * crash_reduction_ratio

    # Health score
    current_health = max(0, 100 - behavioral_score)
    score_improvement = min(30, len(suggestions) * 10)
    new_score = max(15, behavioral_score - score_improvement)
    new_health = max(0, 100 - new_score)

    return {
        "current": {
            "crash_2022_pct": r2022["current_pct"],
            "crash_2022_dollar": r2022["current_dollar"],
            "crash_2020_pct": scenario_results["2020"]["current_pct"],
            "crash_2020_dollar": scenario_results["2020"]["current_dollar"],
            "crash_2008_pct": scenario_results["2008"]["current_pct"],
            "crash_2008_dollar": scenario_results["2008"]["current_dollar"],
            "health_score": current_health,
            "sectors_count": n_sectors,
            "effective_positions": effective_positions,
            "max_drawdown_pct": round(max_dd, 1),
        },
        "suggested": {
            "crash_2022_pct": r2022["suggested_pct"],
            "crash_2022_dollar": r2022["suggested_dollar"],
            "crash_2020_pct": scenario_results["2020"]["suggested_pct"],
            "crash_2020_dollar": scenario_results["2020"]["suggested_dollar"],
            "crash_2008_pct": scenario_results["2008"]["suggested_pct"],
            "crash_2008_dollar": scenario_results["2008"]["suggested_dollar"],
            "health_score": new_health,
            "sectors_count": new_sectors,
            "effective_positions": new_effective,
            "max_drawdown_pct": round(new_max_dd, 1),
        },
        "improvement": {
            "crash_savings_dollar": r2022["savings_dollar"],
            "crash_savings_2020_dollar": scenario_results["2020"]["savings_dollar"],
            "crash_savings_2008_dollar": scenario_results["2008"]["savings_dollar"],
            "health_score_gain": new_health - current_health,
            "new_sectors_added": len(suggestions),
        },
    }


def _empty_profile() -> dict:
    """Return empty profile when no data is available."""
    return {
        "behavioral_score": 0,
        "persona": {
            "name": "Unknown",
            "description": "Connect your portfolio to see your risk profile.",
            "emoji": "shield",
        },
        "factor_breakdown": {
            "composition": {"score": 0, "weight": 0.40, "details": {}},
            "concentration": {"score": 0, "weight": 0.30, "details": {}},
            "volatility": {"score": 0, "weight": 0.20, "details": {}},
            "correlation": {"score": 0, "weight": 0.10, "details": {}},
        },
        "key_findings": [],
        "diversification_suggestions": [],
        "before_after": {
            "current": {
                "crash_2022_pct": 0, "crash_2022_dollar": 0,
                "crash_2020_pct": 0, "crash_2020_dollar": 0,
                "crash_2008_pct": 0, "crash_2008_dollar": 0,
                "health_score": 0, "sectors_count": 0,
                "effective_positions": 0, "max_drawdown_pct": 0,
            },
            "suggested": {
                "crash_2022_pct": 0, "crash_2022_dollar": 0,
                "crash_2020_pct": 0, "crash_2020_dollar": 0,
                "crash_2008_pct": 0, "crash_2008_dollar": 0,
                "health_score": 0, "sectors_count": 0,
                "effective_positions": 0, "max_drawdown_pct": 0,
            },
            "improvement": {
                "crash_savings_dollar": 0,
                "crash_savings_2020_dollar": 0,
                "crash_savings_2008_dollar": 0,
                "health_score_gain": 0,
                "new_sectors_added": 0,
            },
        },
        "portfolio_value": 0,
    }
