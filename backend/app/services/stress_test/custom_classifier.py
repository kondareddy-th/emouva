

"""LLM-based custom scenario classifier.

Classifies free-text scenarios into the nearest pre-built scenario(s)
and generates adjustments. LLM ONLY classifies — never generates numbers.
"""

import hashlib
import json
import logging
import time

from anthropic import AsyncAnthropic

from app.services.stress_test.scenarios import SCENARIOS, SCENARIO_VERSION

logger = logging.getLogger(__name__)


CLASSIFICATION_PROMPT = """You are a financial stress test classifier. Given a user's scenario description,
map it to the most relevant pre-built scenario(s) and provide adjustments.

Available pre-built scenarios:
{scenario_list}

User's scenario: "{user_input}"

Respond in JSON only (no markdown, no explanation outside JSON):
{{
    "primary_scenario_id": "closest matching scenario ID from the list above",
    "secondary_scenario_ids": ["optional additional scenario IDs for blending"],
    "blend_weights": [0.7, 0.3],
    "severity_override": null,
    "custom_sector_adjustments": {{}},
    "custom_factor_adjustments": {{}},
    "reasoning": "Brief explanation of classification"
}}

Rules:
- primary_scenario_id MUST be an exact ID from the list above
- severity_override: only set if user implies specific severity (1-10), else null
- custom_sector_adjustments: only add if user's scenario meaningfully differs from the pre-built
- Keep reasoning under 100 words"""


# ── Classification Cache ────────────────────────────────────────

_classification_cache: dict[str, tuple[float, dict]] = {}
_CLASSIFICATION_TTL = 86400  # 24 hours


# ── Public API ──────────────────────────────────────────────────


async def classify_custom_scenario(
    user_input: str,
    api_key: str,
    model: str = "claude-sonnet-4-5-20250929",
) -> dict:
    """Classify free-text scenario to nearest pre-built + adjustments.

    Returns a dict that can be used by the impact calculator
    identically to a pre-built scenario's attributes.
    """
    cache_key = _cache_key(user_input)
    cached = _get_cached(cache_key)
    if cached:
        return cached

    scenario_list = "\n".join(
        f"- {s.id}: {s.name} — {s.description} (severity={s.severity})"
        for s in SCENARIOS.values()
    )

    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model=model,
        max_tokens=1000,
        messages=[{
            "role": "user",
            "content": CLASSIFICATION_PROMPT.format(
                scenario_list=scenario_list,
                user_input=user_input,
            ),
        }],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    classification = json.loads(raw)

    resolved = _blend_scenarios(classification)
    resolved["custom_input"] = user_input
    resolved["classification"] = classification
    resolved["methodology"] = "llm_estimated"

    _set_cached(cache_key, resolved)
    return resolved


# ── Scenario Blending ───────────────────────────────────────────


def _blend_scenarios(classification: dict) -> dict:
    """Blend primary + secondary scenarios using weights."""
    primary_id = classification["primary_scenario_id"]
    primary = SCENARIOS.get(primary_id)
    if not primary:
        # Fallback: pick the first scenario
        primary_id = next(iter(SCENARIOS))
        primary = SCENARIOS[primary_id]
        logger.warning("Unknown scenario ID from LLM: %s, falling back to %s",
                        classification["primary_scenario_id"], primary_id)

    secondary_ids = classification.get("secondary_scenario_ids", [])
    weights = classification.get("blend_weights", [1.0])

    # Start with primary scenario's sector impacts
    blended_sectors = dict(primary.sector_impacts)
    blended_factors = dict(primary.factor_adjustments)

    # Blend with secondary scenarios
    if secondary_ids and len(weights) > 1:
        primary_weight = weights[0]
        for i, sec_id in enumerate(secondary_ids):
            sec = SCENARIOS.get(sec_id)
            if sec and i + 1 < len(weights):
                sec_weight = weights[i + 1]
                for sector, impact in sec.sector_impacts.items():
                    if sector in blended_sectors:
                        blended_sectors[sector] = (
                            blended_sectors[sector] * primary_weight
                            + impact * sec_weight
                        )
                    else:
                        blended_sectors[sector] = impact * sec_weight

                for factor, adj in sec.factor_adjustments.items():
                    if factor in blended_factors:
                        blended_factors[factor] = (
                            blended_factors[factor] * primary_weight
                            + adj * sec_weight
                        )
                    else:
                        blended_factors[factor] = adj * sec_weight

    # Apply custom adjustments from LLM
    for sector, delta in classification.get("custom_sector_adjustments", {}).items():
        blended_sectors[sector] = blended_sectors.get(sector, -15) + delta

    blended_factors.update(classification.get("custom_factor_adjustments", {}))

    # Severity override
    severity = classification.get("severity_override") or primary.severity

    return {
        "id": f"custom_{hashlib.md5(str(classification).encode()).hexdigest()[:8]}",
        "name": classification.get("reasoning", "Custom scenario")[:80],
        "description": f"Custom: {classification.get('reasoning', '')}",
        "category": "custom",
        "severity": severity,
        "sector_impacts": blended_sectors,
        "factor_adjustments": blended_factors,
        "affected_regions": tuple(primary.affected_regions),
        "correlation_stress_multiplier": primary.correlation_stress_multiplier,
        "sp500_impact": primary.sp500_impact * (severity / primary.severity) if primary.severity else primary.sp500_impact,
        "duration_months": primary.duration_months,
        "tags": list(primary.tags) + ["custom"],
        "actual_stock_impacts": {},
        "version": SCENARIO_VERSION,
    }


# ── Cache Helpers ───────────────────────────────────────────────


def _cache_key(user_input: str) -> str:
    normalized = user_input.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()


def _get_cached(key: str) -> dict | None:
    if key in _classification_cache:
        ts, data = _classification_cache[key]
        if time.time() - ts < _CLASSIFICATION_TTL:
            return data
        del _classification_cache[key]
    return None


def _set_cached(key: str, data: dict) -> None:
    _classification_cache[key] = (time.time(), data)
