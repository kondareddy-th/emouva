"""Earnings-triggered FOUNDATIONAL re-thesis.

When a Confident/Watch name reports, ratios alone miss the story — the beat/miss, the
guidance, strategy shifts, how analysts reacted. This detects reporters from the FMP
earnings calendar and, for each, RE-GENERATES the central thesis from the fresh quarter +
surprise + forward estimates + analyst-grade changes + news + (via web search) the
earnings-call highlights. The verdict reuses central's `_ANALYSIS_TOOL`/`_finalize`, so it
updates the SAME central repo every user's agent reads (compute-once).

Runs in the pre-market (before the first live tick); calendar-gated, so it's bounded to
names that actually reported — a handful/day, more in earnings season. Transcripts are
gated on our FMP tier, so the qualitative call color comes from the brain's web_search;
if a structured transcript feed is added later, drop it into `_context()`.
"""
from __future__ import annotations

import asyncio
import datetime
import logging

from sqlalchemy import select

from app.database import async_session
from app.models.db import Opportunity
from app.services import market_providers as mp
from app.services.agent import central, research

logger = logging.getLogger(__name__)


def _surprise(row: dict) -> dict:
    """A calendar row → {date, eps_actual, eps_est, rev_actual, rev_est, eps_surprise_pct}."""
    ea, ee = row.get("epsActual"), row.get("epsEstimated")
    sp = None
    try:
        if ea is not None and ee not in (None, 0):
            sp = round((float(ea) - float(ee)) / abs(float(ee)) * 100, 1)
    except Exception:  # noqa: BLE001
        sp = None
    return {"date": row.get("date"), "eps_actual": ea, "eps_est": ee,
            "rev_actual": row.get("revenueActual"), "rev_est": row.get("revenueEstimated"),
            "eps_surprise_pct": sp}


async def recent_reporters(db, days: int = 4) -> dict:
    """{SYMBOL: surprise} for ACTIONABLE (Confident/Watch) names that actually reported in
    the last `days`. ONE calendar call for the window, intersected with our pool."""
    today = datetime.date.today()
    cal = await asyncio.to_thread(mp.fmp_earnings_calendar,
                                  (today - datetime.timedelta(days=days)).isoformat(), today.isoformat())
    reported = {str(r.get("symbol", "")).upper(): r for r in cal if r.get("epsActual") is not None}
    if not reported:
        return {}
    syms = (await db.execute(select(Opportunity.symbol).where(
        Opportunity.category.in_((1, 3)), Opportunity.symbol.in_(list(reported))))).scalars().all()
    return {s: _surprise(reported[s]) for s in syms}


def _ratio(a, b) -> str:
    try:
        return f"{float(a) / float(b) * 100:.0f}%" if a and b else "n/a"
    except Exception:  # noqa: BLE001
        return "n/a"


def _context(o: Opportunity, surprise: dict) -> str:
    """The earnings evidence block fed to the LLM (fresh quarter + surprise + grades + news)."""
    inc = mp.fmp_income_quarter(o.symbol, 2)
    grades = mp.fmp_grades(o.symbol, 8)
    news = mp.fmp_news(o.symbol, 6)
    lines = [f"JUST REPORTED ({surprise.get('date')}):",
             f"  EPS actual {surprise.get('eps_actual')} vs est {surprise.get('eps_est')} "
             f"(surprise {surprise.get('eps_surprise_pct')}%); revenue {surprise.get('rev_actual')} "
             f"vs est {surprise.get('rev_est')}."]
    if inc:
        q = inc[0]
        lines.append(f"  Latest quarter {q.get('period')} {q.get('date')}: revenue {q.get('revenue')}, "
                     f"net income {q.get('netIncome')}, EPS {q.get('eps')}, gross margin "
                     f"{_ratio(q.get('grossProfit'), q.get('revenue'))}, operating margin "
                     f"{_ratio(q.get('operatingIncome'), q.get('revenue'))}.")
        if len(inc) > 1:
            p = inc[1]
            lines.append(f"  Prior quarter: revenue {p.get('revenue')}, net income {p.get('netIncome')}, EPS {p.get('eps')}.")
    if grades:
        gs = "; ".join(f"{g.get('gradingCompany')}: {g.get('previousGrade')}→{g.get('newGrade')}" for g in grades[:5])
        lines.append(f"  Recent analyst grade actions: {gs}")
    if news:
        ns = " | ".join((n.get("title") or "")[:90] for n in news[:5])
        lines.append(f"  Recent headlines: {ns}")
    return "\n".join(lines)


def _rethesis_sync(o: Opportunity, stats: dict, ctx: str) -> dict | None:
    """One web-search-augmented LLM pass → the central_analysis verdict (blocking)."""
    base_sys, base_user = central._prompts(o, stats)
    system = base_sys + (
        "\n\nThis is a POST-EARNINGS re-judgement. Weigh the just-reported quarter heavily: did it CONFIRM, "
        "IMPROVE, or BREAK the long-term thesis? You MAY web_search for the earnings-call HIGHLIGHTS and forward "
        "GUIDANCE (qualitative context only — take every NUMBER from get_stock_data or the data below, never from "
        "search). Re-arm the falsifiers and re-run the 4-lens red-team in light of the new quarter.")
    user = base_user + "\n\n" + ctx + "\n\nRe-judge the business foundationally, then call central_analysis."
    return research._llm_toolloop(system, user, central._ANALYSIS_TOOL, use_search=True, max_tokens=3400)


async def _one(symbol: str, surprise: dict) -> dict | None:
    """Foundational re-thesis for one reporter, in its OWN session (concurrency-safe)."""
    stats = await asyncio.to_thread(central._stats, symbol)
    async with async_session() as sdb:
        o = (await sdb.execute(select(Opportunity).where(Opportunity.symbol == symbol))).scalar_one_or_none()
        if o is None:
            return None
        ctx = await asyncio.to_thread(_context, o, surprise)
        out = await asyncio.to_thread(_rethesis_sync, o, stats, ctx)
        cat = central._finalize(o, out)          # updates thesis/falsifiers/red-team/category (or leaves pending)
        o.meta = {**(o.meta or {}), "earnings_rethesis": {"date": surprise.get("date"),
                  "surprise_pct": surprise.get("eps_surprise_pct")}}
        await sdb.commit()
        return {"symbol": symbol, "category": cat, "surprise_pct": surprise.get("eps_surprise_pct")}


async def run_earnings_theses(db=None, days: int = 4, max_names: int = 30) -> dict:
    """Pre-market entry: foundational re-thesis for actionable names that just reported.
    Does NOT re-rank (the caller/premarket scores once at the end)."""
    own = db is None
    db = db or async_session()
    try:
        reporters = await recent_reporters(db, days)
    finally:
        if own:
            await db.close()
    if not reporters:
        return {"reporters": 0, "rethesized": []}
    items = list(reporters.items())[:max_names]
    sem = asyncio.Semaphore(3)

    async def _guard(sym, sp):
        async with sem:
            try:
                return await _one(sym, sp)
            except Exception:  # noqa: BLE001
                logger.exception("earnings re-thesis failed for %s", sym)
                return None

    done = [r for r in await asyncio.gather(*[_guard(s, sp) for s, sp in items]) if r]
    logger.info("Earnings re-thesis: %d reporters → %s", len(done), [d["symbol"] for d in done])
    return {"reporters": len(items), "rethesized": done}
