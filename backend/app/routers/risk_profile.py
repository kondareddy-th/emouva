

"""
Risk Profile & Diversification endpoint.
Computes behavioral risk score, persona, diversification suggestions,
and optionally streams a Claude-generated narrative.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.dependencies import get_api_key, get_claude_model, rate_limit
from app.services import robinhood
from app.services.risk import compute_risk_metrics
from app.services.diversification import compute_risk_profile
from app.prompts import RISK_PROFILE_NARRATIVE_SYSTEM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["risk-profile"])


_DISCONNECTED_PROFILE = {
    "behavioral_score": 0,
    "persona": {"name": "Unknown", "description": "Connect your portfolio to see your risk profile.", "emoji": "shield"},
    "factor_breakdown": {},
    "key_findings": [],
    "diversification_suggestions": [],
    "before_after": {"current": {}, "suggested": {}, "improvement": {}},
    "portfolio_value": 0,
    "source": "disconnected",
}


@router.get("/risk-profile")
async def risk_profile(request: Request, account: str | None = None):
    """Behavioral risk profile + diversification suggestions via the agentic MCP
    (per-user). Pure math — no AI. The DB is touched only briefly (token lookup)
    and released before the slow MCP+compute work."""
    import asyncio
    from datetime import datetime, timedelta, timezone
    from app.services.auth import decode_token
    from app.database import async_session
    from app.services import robinhood_store as store, robinhood_portfolio as rp

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return _DISCONNECTED_PROFILE
    payload = decode_token(auth[7:])
    uid = payload.get("sub") if payload else None
    if not uid:
        return _DISCONNECTED_PROFILE

    try:
        async with async_session() as db:  # short scope — released before compute
            token = await store.get_valid_access_token(db, uid)
        if not token:
            return _DISCONNECTED_PROFILE
        acct = await rp.resolve_account_number(token, account)
        positions = await rp.get_positions(token, acct)
        if not positions:
            return _DISCONNECTED_PROFILE
        summary = await rp.get_summary(token, acct)
        portfolio_value = summary.get("total_value", 0) if summary else 0
        top = sorted(positions, key=lambda p: p.get("equity", 0), reverse=True)[:25]
        start = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hist = await rp.fetch_historicals(token, [p["symbol"] for p in top] + ["SPY"], "day", start)

        def _compute():
            risk_metrics = compute_risk_metrics(positions, hist, f"riskprofile:{acct}")
            profile = compute_risk_profile(positions, risk_metrics, portfolio_value)
            profile["source"] = "computed"
            return profile

        return await asyncio.to_thread(_compute)
    except Exception as e:
        logger.warning("MCP risk-profile failed: %s", e)
        return _DISCONNECTED_PROFILE


@router.get("/risk-profile/narrative")
async def risk_profile_narrative(
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """
    Stream a Claude-generated narrative interpreting the risk profile.
    SSE endpoint — streams text deltas.
    """
    if not robinhood.is_connected():
        raise HTTPException(status_code=400, detail="Portfolio not connected")

    try:
        # Compute the risk profile data first
        positions = robinhood.get_positions()
        if not positions:
            raise HTTPException(status_code=400, detail="No positions found")

        summary = robinhood.get_portfolio_summary()
        portfolio_value = summary.get("total_value", 0) if summary else 0
        risk_metrics = compute_risk_metrics(positions)
        profile = compute_risk_profile(positions, risk_metrics, portfolio_value)

        # Build user message with all computed data
        user_message = _build_narrative_context(profile, positions)

        # Stream the narrative
        from anthropic import AsyncAnthropic
        from app.config import settings

        client = AsyncAnthropic(api_key=api_key)

        async def event_generator():
            try:
                yield f"event: status\ndata: {json.dumps({'message': 'Analyzing your risk profile...'})}\n\n"

                async with client.messages.stream(
                    model=claude_model or settings.claude_model,
                    max_tokens=2048,
                    system=RISK_PROFILE_NARRATIVE_SYSTEM,
                    messages=[{"role": "user", "content": user_message}],
                ) as stream:
                    async for text in stream.text_stream:
                        yield f"event: delta\ndata: {json.dumps({'text': text})}\n\n"

                yield f"event: done\ndata: {json.dumps({'status': 'complete'})}\n\n"

            except Exception as e:
                logger.exception("Narrative streaming failed")
                yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Narrative generation failed")
        raise HTTPException(status_code=502, detail=f"Narrative generation failed: {e}") from e


def _build_narrative_context(profile: dict, positions: list[dict]) -> str:
    """Build the user message with all computed data for Claude to interpret."""
    # Top holdings summary
    sorted_positions = sorted(positions, key=lambda p: p.get("equity", 0), reverse=True)
    holdings_summary = []
    total_eq = sum(p.get("equity", 0) for p in positions)
    for p in sorted_positions[:10]:
        eq = p.get("equity", 0)
        pct = (eq / total_eq * 100) if total_eq > 0 else 0
        holdings_summary.append(
            f"  {p['symbol']}: ${eq:,.0f} ({pct:.1f}%) — {p.get('sector', 'Unknown')}"
        )

    suggestions_text = []
    for s in profile.get("diversification_suggestions", []):
        impact = s.get("impact", {})
        suggestions_text.append(
            f"  {s['symbol']} ({s['name']}): {s['category']}\n"
            f"    Allocate: ${s.get('suggested_allocation_dollar', 0):,.0f} (10%)\n"
            f"    2022 crash savings: ${impact.get('crash_savings_2022', 0):,.0f}\n"
            f"    Reason: {s.get('reason', '')}"
        )

    ba = profile.get("before_after", {})
    current = ba.get("current", {})
    suggested = ba.get("suggested", {})
    improvement = ba.get("improvement", {})

    return f"""PORTFOLIO RISK PROFILE DATA
===========================

Portfolio Value: ${profile.get('portfolio_value', 0):,.0f}
Behavioral Risk Score: {profile.get('behavioral_score', 0)}/100
Persona: {profile.get('persona', {}).get('name', 'Unknown')}

HOLDINGS (top 10):
{chr(10).join(holdings_summary)}

KEY FINDINGS:
{chr(10).join(f"  [{f['type'].upper()}] {f['text']}" for f in profile.get('key_findings', []))}

FACTOR BREAKDOWN:
  Composition: {profile.get('factor_breakdown', {}).get('composition', {}).get('score', 0)}/100
  Concentration: {profile.get('factor_breakdown', {}).get('concentration', {}).get('score', 0)}/100
  Volatility: {profile.get('factor_breakdown', {}).get('volatility', {}).get('score', 0)}/100
  Correlation: {profile.get('factor_breakdown', {}).get('correlation', {}).get('score', 0)}/100

HISTORICAL CRASH SIMULATIONS:
  2022 Rate Shock:
    Current portfolio: {current.get('crash_2022_pct', 0)}% (${current.get('crash_2022_dollar', 0):,.0f})
    With suggestions: {suggested.get('crash_2022_pct', 0)}% (${suggested.get('crash_2022_dollar', 0):,.0f})
    Money protected: ${improvement.get('crash_savings_dollar', 0):,.0f}
  COVID 2020:
    Current portfolio: {current.get('crash_2020_pct', 0)}% (${current.get('crash_2020_dollar', 0):,.0f})
    With suggestions: {suggested.get('crash_2020_pct', 0)}% (${suggested.get('crash_2020_dollar', 0):,.0f})
    Money protected: ${improvement.get('crash_savings_2020_dollar', 0):,.0f}
  2008 Financial Crisis:
    Current portfolio: {current.get('crash_2008_pct', 0)}% (${current.get('crash_2008_dollar', 0):,.0f})
    With suggestions: {suggested.get('crash_2008_pct', 0)}% (${suggested.get('crash_2008_dollar', 0):,.0f})
    Money protected: ${improvement.get('crash_savings_2008_dollar', 0):,.0f}

DIVERSIFICATION SUGGESTIONS:
{chr(10).join(suggestions_text)}

Write a 4-phase narrative (Mirror → Reveal → Context → Path) interpreting this data for the investor.
Reference all 3 crash scenarios with actual dollar amounts. Use the worst scenario to anchor the risk message.
Be specific and personal."""
