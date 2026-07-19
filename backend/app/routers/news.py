

"""
LLM-curated news endpoints.
Fetches raw headlines via yfinance, sends to Claude for curation.
API key managed server-side.
"""

import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Depends

from app.dependencies import get_api_key, get_claude_model, rate_limit
from app.models.portfolio import CuratedNewsResponse, SectorAnalysisResponse
from app.services import robinhood
from app.services.market_data import get_news as get_raw_news
from app.services.claude import _call_claude, _strip_json_fences

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/news", tags=["news"])

_cache: dict[str, tuple[float, Any]] = {}
NEWS_CACHE_6H = 21600
NEWS_CACHE_24H = 86400


def _get_cached(key: str, ttl: float) -> Any | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < ttl:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: Any) -> None:
    _cache[key] = (time.time(), data)


@router.get("/market")
async def market_news():
    """Major-market-news brief, generated 3x/day by the scheduler and served from
    cache (no Claude call on the request path)."""
    from app.services.market_news import get_latest
    return get_latest()


@router.get("/portfolio", response_model=CuratedNewsResponse)
async def portfolio_news(
    refresh: bool = False,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """
    LLM-curated news for held stocks.
    6-hour cache, ?refresh=true to force re-curation.
    """
    cache_key = "curated_portfolio_news"
    if not refresh:
        cached = _get_cached(cache_key, NEWS_CACHE_6H)
        if cached is not None:
            return cached

    # Gather symbols from portfolio
    symbols = []
    if robinhood.is_connected():
        positions = robinhood.get_positions()
        symbols = [p["symbol"] for p in positions[:15]]

    if not symbols:
        return {"articles": [], "source": "none"}

    # Fetch raw news for all symbols
    all_headlines = []
    for symbol in symbols:
        raw = get_raw_news(symbol)
        for article in raw[:5]:
            article["symbol"] = symbol
            all_headlines.append(article)

    if not all_headlines:
        return {"articles": [], "source": "no_news"}

    # Format headlines for Claude
    headlines_text = "\n".join(
        f"- [{h['symbol']}] {h['title']} (via {h['publisher']})"
        for h in all_headlines
        if h.get("title")
    )

    system = """You are a financial news curator for a personal investment portfolio.
Your job is to select the 5-8 most material news items from the raw headlines provided.
Focus on news that could impact the user's holdings.
Prioritize: earnings, regulatory changes, major partnerships, competitive threats, macro shifts.
Skip: generic market commentary, clickbait, trivial price movements.
NEVER use gambling language (no "win rates", "streaks", "bets")."""

    prompt = f"""Here are recent headlines for stocks in the user's portfolio:

{headlines_text}

Select the 5-8 most important headlines and return JSON:
{{
  "articles": [
    {{
      "symbol": "TICKER",
      "title": "Headline text",
      "summary": "1-sentence explanation of why this matters for the portfolio",
      "impact": "positive" | "negative" | "neutral",
      "urgency": "high" | "medium" | "low"
    }}
  ]
}}

Order by urgency (high first), then impact magnitude.
Return ONLY valid JSON — no markdown, no code fences."""

    try:
        raw_text = await _call_claude(system, prompt, api_key, max_tokens=2048, model=claude_model)
        parsed = json.loads(_strip_json_fences(raw_text))
        result = {
            "articles": parsed.get("articles", []),
            "source": "claude_curated",
            "symbols_scanned": len(symbols),
            "raw_headlines_count": len(all_headlines),
        }
        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to curate portfolio news")
        fallback = [
            {
                "symbol": h["symbol"],
                "title": h["title"],
                "summary": "",
                "impact": "neutral",
                "urgency": "low",
            }
            for h in all_headlines[:8]
            if h.get("title")
        ]
        return {"articles": fallback, "source": "raw_fallback"}


@router.get("/sectors", response_model=SectorAnalysisResponse)
async def sector_news(
    refresh: bool = False,
    api_key: str = Depends(get_api_key),
    claude_model: str = Depends(get_claude_model),
    _rate: None = Depends(rate_limit("analysis")),
):
    """
    LLM-curated sector opportunity scanning.
    24-hour cache, ?refresh=true to force refresh.
    """
    cache_key = "curated_sector_news"
    if not refresh:
        cached = _get_cached(cache_key, NEWS_CACHE_24H)
        if cached is not None:
            return cached

    # Get sectors from portfolio
    sectors = set()
    if robinhood.is_connected():
        positions = robinhood.get_positions()
        for p in positions:
            s = p.get("sector", "Unknown")
            if s and s != "Unknown":
                sectors.add(s)

    if not sectors:
        sectors = {"Technology", "Finance", "Health Technology"}

    system = """You are a sector analyst looking for investment opportunities.
Identify emerging trends, undervalued sectors, and notable shifts.
NEVER use gambling language. Focus on analytical insights."""

    prompt = f"""The user is invested in these sectors: {', '.join(sectors)}

Analyze current market conditions and provide sector opportunities.
Return JSON:
{{
  "opportunities": [
    {{
      "sector": "Sector name",
      "trend": "Brief trend description",
      "outlook": "positive" | "cautious" | "negative",
      "reasoning": "2-3 sentence analysis",
      "timeframe": "Short-term" | "Medium-term" | "Long-term"
    }}
  ],
  "market_regime": "Brief description of current market regime"
}}

Provide 3-5 sector insights. Return ONLY valid JSON."""

    try:
        raw_text = await _call_claude(system, prompt, api_key, max_tokens=2048, model=claude_model)
        parsed = json.loads(_strip_json_fences(raw_text))
        result = {
            "opportunities": parsed.get("opportunities", []),
            "market_regime": parsed.get("market_regime", ""),
            "source": "claude_analysis",
        }
        _set_cached(cache_key, result)
        return result

    except Exception:
        logger.exception("Failed to generate sector analysis")
        return {"opportunities": [], "market_regime": "", "source": "error"}
