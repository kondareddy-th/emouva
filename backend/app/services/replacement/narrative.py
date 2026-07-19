
"""
Stage 8: Constrained LLM Narrative Layer

The LLM NEVER picks stocks — it only explains the algorithm's picks.
Uses temperature=0, structured JSON output, and whitelist enforcement.

What the LLM does:
  1. Narrative synthesis — explain WHY in plain English
  2. Qualitative context — management changes, competitive dynamics
  3. Comparison generation — human-readable comparison
  4. Risk framing — explain tradeoffs

What the LLM does NOT do:
  - Pick stocks (already picked by algorithm)
  - Generate financial numbers (all from data packet)
  - Suggest tickers not in the pre-filtered list
  - Make price predictions
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.models.replacement import (
    ReplacementNarrative,
    ScoredCandidate,
    ETFAlternative,
    ThesisHealthResult,
    UnderperformanceResult,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial analyst assistant for Emouva, an AI investment intelligence platform.

CRITICAL RULES:
1. You ONLY explain decisions that were ALREADY MADE by the algorithm. You do NOT pick stocks.
2. Every number you cite MUST come from the data packet provided. NEVER invent numbers.
3. You may ONLY mention tickers that appear in the allowed_tickers list. No exceptions.
4. NEVER make price predictions or say "will go up/down."
5. Use "upgrade" framing, never "sell." Present swaps as ONE positive action.
6. Temperature is 0. Be deterministic and factual.
7. Write for a retail investor with $10,000-$100,000 in the market. No jargon.
8. Be concise. Each field has a word limit.

LANGUAGE RULES (regulatory):
- Never say "you should sell X" → say "Data suggests Y shows stronger metrics than X"
- Never say "X is a bad investment" → say "X's thesis signals have shifted"
- Never say "this stock will underperform" → say "stocks with these signals underperform 70% of the time historically"
- Never say "we recommend" → say "based on current data, you may want to consider"
"""


def _build_data_packet(
    ticker: str,
    underperformance: UnderperformanceResult,
    thesis_health: ThesisHealthResult,
    replacements: list[ScoredCandidate],
    etf: ETFAlternative | None,
    position_value: float | None = None,
) -> dict[str, Any]:
    """Build the structured data packet for the LLM.

    All numbers come from the deterministic pipeline.
    """
    return {
        "original_stock": {
            "ticker": ticker,
            "sector": underperformance.sector,
            "underperformance_summary": underperformance.summary,
            "thesis_health_score": thesis_health.composite_score,
            "thesis_verdict": thesis_health.verdict,
            "negative_signals": thesis_health.negative_count,
            "total_signals": thesis_health.total_count,
            "signals": [
                {
                    "name": s.name,
                    "status": s.status,
                    "detail": s.detail,
                }
                for s in thesis_health.signals
            ],
            "f_score": thesis_health.f_score,
            "user_pnl_pct": underperformance.user_pnl_pct,
            "user_pnl_dollar": underperformance.user_pnl_dollar,
        },
        "replacements": [
            {
                "ticker": c.ticker,
                "name": c.name,
                "composite_score": c.composite_score,
                "sector": c.sector,
                "industry": c.industry,
                "factors": {
                    "momentum": c.factors.momentum,
                    "quality": c.factors.quality,
                    "growth": c.factors.growth,
                    "value": c.factors.value,
                    "risk": c.factors.risk,
                    "analyst": c.factors.analyst,
                },
                "revenue_yoy": c.revenue_yoy,
                "eps_growth": c.eps_growth,
                "return_6m": c.return_6m,
                "forward_pe": c.forward_pe,
                "beta": c.beta,
                "dividend_yield": c.dividend_yield,
            }
            for c in replacements
        ],
        "etf": {
            "ticker": etf.ticker,
            "name": etf.name,
            "expense_ratio": etf.expense_ratio,
            "top_holdings": etf.top_holdings,
            "is_sub_industry": etf.is_sub_industry,
            "annual_cost": etf.annual_cost_on_position,
        } if etf else None,
        "allowed_tickers": [c.ticker for c in replacements] + ([etf.ticker] if etf else []),
        "position_value": position_value,
    }


USER_PROMPT_TEMPLATE = """Based on the following data packet, generate a narrative explanation.

DATA PACKET:
{data_packet}

Respond with a JSON object matching this exact schema:
{{
  "current_assessment": "2-3 sentence assessment of the original stock's situation. Max 150 words. Reference specific signals from the data.",
  "why_better": {{
    "<replacement_ticker_1>": "Why this is a better option. Max 80 words. Reference specific metrics from the data.",
    "<replacement_ticker_2>": "...",
    "<replacement_ticker_3>": "..."
  }},
  "etf_case": "Why the ETF is a good option. Mention top holdings. Frame as 'the diversified play.' Max 80 words.",
  "key_risks": {{
    "<replacement_ticker_1>": "Key risk of this replacement. Max 40 words.",
    "<replacement_ticker_2>": "...",
    "<replacement_ticker_3>": "..."
  }},
  "confidence": "high" or "medium" or "low",
  "fresh_money_test": "The 'fresh money test' question for this specific stock and position value. One sentence."
}}

IMPORTANT:
- Only use tickers from the allowed_tickers list: {allowed_tickers}
- Only cite numbers from the data packet above
- Use "upgrade" framing, never "sell"
- Frame the ETF positively, not as "the safe/boring option"
"""


async def generate_narrative(
    ticker: str,
    underperformance: UnderperformanceResult,
    thesis_health: ThesisHealthResult,
    replacements: list[ScoredCandidate],
    etf: ETFAlternative | None,
    api_key: str,
    model: str = "claude-sonnet-4-5-20250514",
    position_value: float | None = None,
) -> ReplacementNarrative:
    """Run Stage 8: generate constrained LLM narrative.

    The LLM explains the algorithm's picks — it NEVER picks stocks.
    Temperature=0 for deterministic output.
    """
    data_packet = _build_data_packet(
        ticker, underperformance, thesis_health, replacements, etf, position_value,
    )

    allowed = data_packet["allowed_tickers"]
    prompt = USER_PROMPT_TEMPLATE.format(
        data_packet=json.dumps(data_packet, indent=2, default=str),
        allowed_tickers=json.dumps(allowed),
    )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = response.content[0].text.strip()

        # Extract JSON from response (handle markdown code blocks)
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            json_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    json_lines.append(line)
            raw_text = "\n".join(json_lines)

        parsed = json.loads(raw_text)

        # Whitelist enforcement: verify all mentioned tickers are allowed
        for key in ["why_better", "key_risks"]:
            if key in parsed:
                for t in list(parsed[key].keys()):
                    if t not in allowed:
                        logger.warning("Narrative: removing unauthorized ticker %s", t)
                        del parsed[key][t]

        # Determine confidence from thesis health
        if thesis_health.negative_count >= 5:
            default_confidence = "high"
        elif thesis_health.negative_count >= 3:
            default_confidence = "medium"
        else:
            default_confidence = "low"

        return ReplacementNarrative(
            current_assessment=parsed.get("current_assessment", "Analysis complete."),
            why_better=parsed.get("why_better", {}),
            etf_case=parsed.get("etf_case", "Consider the sector ETF for diversified exposure."),
            key_risks=parsed.get("key_risks", {}),
            confidence=parsed.get("confidence", default_confidence),
            fresh_money_test=parsed.get(
                "fresh_money_test",
                f"If you had cash instead of {ticker}, would you buy it today at the current price?",
            ),
        )

    except json.JSONDecodeError:
        logger.warning("Narrative: failed to parse LLM JSON response")
        return _fallback_narrative(ticker, thesis_health, replacements, etf, position_value)
    except Exception:
        logger.exception("Narrative: LLM call failed")
        return _fallback_narrative(ticker, thesis_health, replacements, etf, position_value)


def _fallback_narrative(
    ticker: str,
    thesis_health: ThesisHealthResult,
    replacements: list[ScoredCandidate],
    etf: ETFAlternative | None,
    position_value: float | None = None,
) -> ReplacementNarrative:
    """Deterministic fallback when LLM fails — uses template strings."""
    neg = thesis_health.negative_count
    total = thesis_health.total_count

    assessment = (
        f"{ticker}'s thesis health shows {neg} of {total} signals negative "
        f"(score: {thesis_health.composite_score}/10). "
        f"Current verdict: {thesis_health.verdict}."
    )

    why_better: dict[str, str] = {}
    key_risks: dict[str, str] = {}
    for c in replacements:
        why_better[c.ticker] = (
            f"{c.name} scores {c.composite_score:.0f}/100 on our multi-factor model. "
            f"Strongest factors: momentum ({c.factors.momentum:.0f}), quality ({c.factors.quality:.0f})."
        )
        key_risks[c.ticker] = (
            f"Forward P/E: {c.forward_pe:.1f}x. Beta: {c.beta:.2f}."
            if c.forward_pe and c.beta else "Standard market risk applies."
        )

    etf_case = ""
    if etf:
        etf_case = (
            f"{etf.name} ({etf.ticker}) provides diversified {thesis_health.ticker} sector exposure "
            f"across {', '.join(etf.top_holdings[:3])} and more. Expense ratio: {etf.expense_ratio*100:.2f}%/yr."
        )

    val_str = f"${position_value:,.0f}" if position_value else "your current position"
    fresh = f"If you had {val_str} in cash right now, would you buy {ticker} at today's price?"

    confidence = "high" if neg >= 5 else "medium" if neg >= 3 else "low"

    return ReplacementNarrative(
        current_assessment=assessment,
        why_better=why_better,
        etf_case=etf_case,
        key_risks=key_risks,
        confidence=confidence,
        fresh_money_test=fresh,
    )
