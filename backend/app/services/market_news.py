"""Scheduled major-market-news brief, curated by Claude.

Generated 3x/day (8:05, 11:05, 14:05 ET) by the scheduler and served from cache
the rest of the day — Claude is NOT called on the request path. Raw headlines
come from yfinance for major market ETFs + mega-caps; Claude curates the most
material market-wide stories.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Pull raw headlines from these for a market-wide view (ETFs + bellwethers).
_MARKET_SYMBOLS = ["SPY", "QQQ", "DIA", "IWM", "NVDA", "AAPL", "MSFT", "TSLA", "AMZN", "JPM"]

_CACHE_FILE = Path(os.getenv(
    "EMOUVA_MARKET_NEWS_FILE",
    Path(__file__).resolve().parents[2] / ".harness_data" / "market_news.json",
))
_latest: dict = {}


def get_latest() -> dict:
    """Return the most recent brief (load from disk on first call)."""
    global _latest
    if not _latest and _CACHE_FILE.is_file():
        try:
            _latest = json.loads(_CACHE_FILE.read_text())
        except Exception:
            _latest = {}
    return _latest or {"articles": [], "summary": "", "source": "pending", "generated_at": None}


def _persist(data: dict) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data))
    except Exception:
        logger.warning("Could not persist market news")


def _api_key() -> str:
    from app.config import settings
    return settings.anthropic_api_key or getattr(settings, "anthropic_key", "") or os.getenv("ANTHROPIC_KEY", "")


async def generate_market_news() -> dict:
    """Fetch raw market headlines + curate via Claude. Stores + returns the brief."""
    from app.config import settings
    from app.services.market_data import get_news
    from app.services.claude import _call_claude, _strip_json_fences

    api_key = _api_key()
    if not api_key:
        logger.warning("market news: no Anthropic key configured")
        return get_latest()

    seen: set[str] = set()
    headlines: list[str] = []
    for sym in _MARKET_SYMBOLS:
        try:
            for a in (get_news(sym) or [])[:6]:
                t = (a.get("title") or "").strip()
                if t and t not in seen:
                    seen.add(t)
                    headlines.append(t)
        except Exception:
            continue
    if not headlines:
        logger.warning("market news: no raw headlines available")
        return get_latest()

    system = (
        "You are a markets editor writing a concise major-market-news brief for retail "
        "investors. Select the most material MARKET-WIDE stories (macro, rates, big-tech, "
        "earnings season, sectors) — not single-stock trivia. Be factual and neutral. "
        "NEVER use gambling language (no 'bets', 'win rates', 'streaks')."
    )
    prompt = (
        "Recent market headlines:\n\n"
        + "\n".join("- " + h for h in headlines[:40])
        + "\n\nReturn ONLY valid JSON (no code fences):\n"
        '{\n'
        '  "summary": "2-3 sentence overview of today\'s market tone",\n'
        '  "articles": [\n'
        '    {"symbol": "<2-6 char tag e.g. MACRO/TECH/RATES/ENERGY>", "title": "Headline",\n'
        '     "summary": "1 sentence on why it matters", "impact": "positive|negative|neutral"}\n'
        '  ]\n'
        "}\n\nPick the 6-10 most important market-wide stories, ordered by importance."
    )

    try:
        raw = await _call_claude(system, prompt, api_key, max_tokens=2048, model=settings.claude_model)
        parsed = json.loads(_strip_json_fences(raw))
        data = {
            "summary": parsed.get("summary", ""),
            "articles": parsed.get("articles", []),
            "source": "claude_curated",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        global _latest
        _latest = data
        _persist(data)
        logger.info("Market news refreshed: %d stories", len(data["articles"]))
        return data
    except Exception:
        logger.exception("Failed to generate market news")
        return get_latest()
