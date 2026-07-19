

"""Deterministic per-stock impact calculator.

Every function here is a PURE FUNCTION of its inputs. No randomness,
no LLM calls, no network I/O. Same inputs = same outputs. Always.

The formula:
  impact = base_sector_impact
         × beta_multiplier
         × size_multiplier
         × quality_multiplier
         × geographic_multiplier
         + factor_adjustments
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.stress_test.scenarios import ScenarioDefinition


# ── Size Multipliers ────────────────────────────────────────────

SIZE_MULTIPLIERS: dict[str, float] = {
    "mega_cap": 0.85,   # >$200B — flight to quality
    "large_cap": 0.95,
    "mid_cap": 1.05,
    "small_cap": 1.20,
    "micro_cap": 1.35,
}

# ── Recovery Time Estimates ─────────────────────────────────────

RECOVERY_MONTHS: dict[int, int] = {
    1: 1, 2: 2, 3: 3, 4: 4, 5: 6,
    6: 8, 7: 12, 8: 15, 9: 18, 10: 24,
}


# ── Core Calculator ─────────────────────────────────────────────


def compute_stock_impact(
    profile: dict,
    scenario: ScenarioDefinition | dict,
    confidence: str = "medium",
) -> float:
    """Compute expected % change for a single stock under a scenario.

    Returns a float in range [-99, 50] representing estimated % change.
    Negative = loss, positive = gain.
    """
    # Unpack scenario (supports both dataclass and dict from custom classifier)
    sector_impacts = _get_attr(scenario, "sector_impacts", {})
    factor_adjustments = _get_attr(scenario, "factor_adjustments", {})
    affected_regions = _get_attr(scenario, "affected_regions", ())
    actual_stock_impacts = _get_attr(scenario, "actual_stock_impacts", {}) or {}

    stock_sector = profile.get("sector", "Unknown")
    stock_symbol = profile.get("symbol", "")

    # 1. Check for historical actual data (50/50 blend if available)
    has_historical = stock_symbol in actual_stock_impacts
    historical_impact = actual_stock_impacts.get(stock_symbol, 0.0)

    # 2. Base impact from scenario's sector map
    base = sector_impacts.get(stock_sector, sector_impacts.get("_default", -15.0))

    # 3. Beta adjustment — dampened: beta=1.0 → 1.0x, beta=1.5 → ~1.25x
    beta = profile.get("beta") or 1.0
    beta_mult = 0.5 + 0.5 * max(0.2, min(3.0, beta))

    # 4. Size factor — small caps drop more
    size_tier = profile.get("size_tier", "unknown")
    size_mult = SIZE_MULTIPLIERS.get(size_tier, 1.0)

    # 5. Quality factor — strong balance sheets hold up better
    quality = profile.get("quality_score") or 50
    # quality=100 → 0.85x (resilient), quality=0 → 1.15x (fragile)
    quality_mult = 1.15 - (quality / 100) * 0.30

    # 6. Geographic adjustment
    geo_mult = 1.0
    if affected_regions:
        primary_region = profile.get("primary_region", "Unknown")
        revenue_exposure = profile.get("revenue_exposure", {})

        if primary_region in affected_regions:
            geo_mult = 1.2
        else:
            # Check revenue exposure to affected regions
            for region in affected_regions:
                exposure = revenue_exposure.get(region, 0)
                if exposure > 0.3:
                    geo_mult = max(geo_mult, 1.1)
                elif exposure > 0.15:
                    geo_mult = max(geo_mult, 1.05)

    # 7. Factor-specific adjustments (capped to prevent extreme stacking)
    factor_adj = 0.0
    stock_exposures = profile.get("factor_exposures", {})
    for factor, sensitivity in factor_adjustments.items():
        stock_exposure = stock_exposures.get(factor, 0.0)
        factor_adj += sensitivity * stock_exposure

    # Cap factor adjustment to ±50% of the base impact to prevent
    # unrealistic extremes when multiple factors stack
    if base != 0:
        max_factor_adj = abs(base) * 0.5
        factor_adj = max(-max_factor_adj, min(max_factor_adj, factor_adj))

    # Combine model-based impact
    model_impact = base * beta_mult * size_mult * quality_mult * geo_mult + factor_adj

    # 8. Blend with historical if available (50% model + 50% actual)
    if has_historical:
        impact = model_impact * 0.5 + historical_impact * 0.5
    else:
        impact = model_impact

    # 9. Confidence adjustment
    if confidence == "high":  # conservative — assume worse
        impact *= 1.15
    elif confidence == "low":  # optimistic
        impact *= 0.85

    # Clamp to reasonable range
    return round(max(-99.0, min(50.0, impact)), 1)


def compute_correlation_adjustment(
    per_stock_impacts: list[dict],
    scenario: ScenarioDefinition | dict,
    total_portfolio_value: float,
) -> dict:
    """Compute the additional portfolio-level impact from correlation spikes.

    In a crisis, correlations spike toward 1.0, meaning diversification
    benefit disappears. This adjustment captures that effect.
    """
    if not per_stock_impacts or total_portfolio_value <= 0:
        return {
            "applied": False,
            "normal_portfolio_correlation": 0.0,
            "stressed_portfolio_correlation": 0.0,
            "additional_impact_pct": 0.0,
        }

    stress_mult = _get_attr(scenario, "correlation_stress_multiplier", 1.5)
    severity = _get_attr(scenario, "severity", 5)

    # Estimate normal portfolio correlation from sector concentration
    sectors: dict[str, float] = {}
    for stock in per_stock_impacts:
        sector = stock.get("sector", "Unknown")
        value = stock.get("current_value", 0)
        sectors[sector] = sectors.get(sector, 0) + value

    if total_portfolio_value > 0:
        weights = [v / total_portfolio_value for v in sectors.values()]
    else:
        weights = [1.0]

    # HHI of sector weights as proxy for correlation
    hhi = sum(w ** 2 for w in weights)
    n_sectors = len(sectors)

    # Normal correlation estimate: concentrated = higher correlation
    normal_corr = min(0.95, 0.2 + hhi * 0.6)

    # Stressed correlation
    stressed_corr = min(1.0, normal_corr * stress_mult)

    # Additional impact from correlation spike
    # The idea: when correlations increase, portfolio volatility increases
    # beyond what per-stock impacts capture
    corr_delta = stressed_corr - normal_corr
    severity_factor = severity / 10.0

    # Scale by how concentrated + how severe the scenario is
    additional_impact_pct = -corr_delta * severity_factor * 3.0

    # Cap the additional impact
    additional_impact_pct = max(-8.0, min(0.0, additional_impact_pct))

    return {
        "applied": True,
        "normal_portfolio_correlation": round(normal_corr, 3),
        "stressed_portfolio_correlation": round(stressed_corr, 3),
        "additional_impact_pct": round(additional_impact_pct, 2),
    }


def get_sensitivity_factors(
    profile: dict,
    scenario: ScenarioDefinition | dict,
) -> list[str]:
    """Get human-readable list of sensitivity factors for a stock."""
    factors: list[str] = []
    stock_exposures = profile.get("factor_exposures", {})
    scenario_factors = _get_attr(scenario, "factor_adjustments", {})

    for factor in scenario_factors:
        exposure = stock_exposures.get(factor, 0)
        if exposure > 0.5:
            factors.append(_factor_label(factor, "high"))
        elif exposure > 0.2:
            factors.append(_factor_label(factor, "moderate"))

    # Beta
    beta = profile.get("beta") or 1.0
    if beta > 1.5:
        factors.append("High beta (volatile)")
    elif beta < 0.7:
        factors.append("Low beta (defensive)")

    # Size
    size = profile.get("size_tier", "")
    if size == "micro_cap":
        factors.append("Micro-cap (higher crash risk)")
    elif size == "small_cap":
        factors.append("Small-cap (elevated risk)")

    # Quality
    quality = profile.get("quality_score", 50)
    if quality < 30:
        factors.append("Weak fundamentals")
    elif quality > 80:
        factors.append("Strong balance sheet")

    return factors[:5]  # Max 5 factors


def estimate_recovery_months(severity: int) -> int | None:
    return RECOVERY_MONTHS.get(severity)


# ── Helpers ─────────────────────────────────────────────────────


def _get_attr(obj: object | dict, key: str, default: object = None) -> object:
    """Get attribute from dataclass or dict."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


_FACTOR_LABELS: dict[str, str] = {
    "leverage": "High debt exposure",
    "rate_sensitivity": "Rate sensitive",
    "pe_ratio_premium": "High valuation premium",
    "semiconductor": "Semiconductor exposure",
    "taiwan_supply_chain": "Taiwan supply chain",
    "china_revenue": "China revenue exposure",
    "ai_revenue_pct": "AI revenue dependent",
    "cloud_infrastructure": "Cloud infrastructure",
    "consumer_cyclical": "Consumer cyclical",
    "defense_contractor": "Defense/aerospace",
    "energy_producer": "Energy producer",
    "travel_exposure": "Travel/hospitality",
    "digital_revenue": "Digital revenue",
    "dividend_yield_high": "High dividend yield",
    "crypto_exposure": "Crypto exposure",
    "ev_exposure": "EV sector exposure",
    "international_revenue": "International revenue",
    "commodity_producer": "Commodity producer",
}


def _factor_label(factor: str, level: str) -> str:
    base = _FACTOR_LABELS.get(factor, factor.replace("_", " ").title())
    return f"{base} ({level})"
