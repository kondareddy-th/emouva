"""Central intelligence — analyze each opportunity ONCE (shared across all users).

Cheap STATS gate first (no point spending an LLM on a company with declining
revenue or losses); only survivors get the harness analysis: thesis + falsifiers
+ 4-lens red-team + growth potential + "do we understand the business with
available info?". The result categorizes the stock:
  category 1 — looks good AND understood → the tradeable universe.
  category 2 — looks good but not understood → admins feed it info via chat.
  category 0 — rejected (weak stats, or didn't survive the analysis).

The stored reasoning is reused by every user's Living Thesis (no per-account
re-derivation)."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_

from app.database import async_session
from app.models.db import Opportunity
from app.services.market_data import get_company_info, get_news
from app.services import fair_value as fv_svc
from app.services.agent import engine, research
from app.services.agent.thesis import ALLOWED_METRICS

logger = logging.getLogger(__name__)

_STAT_KEYS = ["revenue_growth", "earnings_growth", "gross_margins", "operating_margins",
              "profit_margins", "return_on_equity", "return_on_assets", "debt_to_equity",
              "current_ratio", "pe_ratio", "forward_pe", "peg_ratio",
              # forward-looking enrichment — every thesis now sees Street forward estimates + grade trend
              "forward_eps_est", "forward_revenue_est", "grade_trend"]


def _stats(symbol: str) -> dict:
    info = get_company_info(symbol) or {}
    return {k: info.get(k) for k in _STAT_KEYS}


# ROE (and other net-income returns) understate FFO-based businesses — don't
# gate these sectors on returns.
_RETURNS_EXEMPT = {"Real Estate"}


def _stats_gate(s: dict, sector: str | None = None) -> tuple[bool, list[str]]:
    """Cheap quality floor — eliminate clearly-weak businesses BEFORE any LLM spend.

    Calibrated against the harness's own verdicts so it never drops a business the
    harness would rate Confident/Watch (0 tradeable false-kills in backtest): it
    fires only on unambiguous weakness (unprofitable, shrinking, poor returns) or a
    'triple-weakness' combo — low returns AND no growth AND thin margins together.
    It deliberately does NOT try to reproduce the harness's *qualitative* rejects
    (moat erosion, disruption, accounting) — those don't show in ratios and are
    exactly what the harness is for."""
    reasons = []
    rg = s.get("revenue_growth"); pm = s.get("profit_margins")
    om = s.get("operating_margins"); roe = s.get("return_on_equity")
    returns_ok = sector not in _RETURNS_EXEMPT
    # (1) unambiguous, sector-agnostic disqualifiers
    if pm is not None and pm < 0.005:
        reasons.append(f"unprofitable (net margin {pm:.0%})")
    if rg is not None and rg < -0.03:
        reasons.append(f"revenue shrinking ({rg:.0%})")
    if roe is not None and roe < 0.04 and returns_ok:
        reasons.append(f"weak returns on equity ({roe:.0%})")
    if reasons:
        return False, reasons
    # (2) triple-weakness: mediocre on returns AND growth AND margins simultaneously
    weak_ret = roe is not None and roe < 0.10 and returns_ok
    weak_grow = rg is not None and rg < 0.025
    weak_marg = (om is not None and om < 0.12) or (pm is not None and pm < 0.06)
    if weak_ret and weak_grow and weak_marg:
        return False, ["mediocre business — low returns, no growth, thin margins"]
    return True, []


_ANALYSIS_TOOL = {
    "name": "central_analysis",
    "description": "The one-time central verdict on a stock, reused by every user's agent.",
    "input_schema": {
        "type": "object",
        "properties": {
            "looks_good": {"type": "boolean", "description": "a genuinely attractive LONG-TERM business (durable, not a value trap)?"},
            "understood": {"type": "boolean", "description": "can we understand and model this business well with the available info? (circle of competence)"},
            "thesis": {"type": "string", "description": "one paragraph: why own it"},
            "growth": {"type": "string", "description": "near-term growth-potential assessment"},
            "future_growth": {"type": "string", "description": "5–10 year durability: do the company AND its industry have the scope + staying power to stay relevant and ideally dominate?"},
            "falsifiers": {
                "type": "array", "description": (
                    "2–5 machine-checkable downward triggers that mark a MATERIAL DETERIORATION from where the "
                    "business is TODAY. Each threshold MUST sit on the not-yet-tripped side of the CURRENT value "
                    "in STATS — set it as a meaningful worsening (a real break), never at/beyond today's level. "
                    "e.g. if operating_margins is 0.27 now, a valid trigger is '< 0.20' (margin collapses), NOT "
                    "'< 0.35' (already true today — that fires instantly and is invalid). Sanity-check every "
                    "threshold against STATS before emitting it."),
                "items": {"type": "object", "properties": {
                    "metric": {"type": "string", "enum": ALLOWED_METRICS},
                    "comparator": {"type": "string", "enum": ["<", ">", "<=", ">="]},
                    "threshold": {"type": "number"}, "label": {"type": "string"}},
                    "required": ["metric", "comparator", "threshold", "label"]},
            },
            "red_team": {
                "type": "array", "description": "exactly 4 BUSINESS-QUALITY lenses trying to kill it (NOT valuation — price is handled separately)",
                "items": {"type": "object", "properties": {
                    "lens": {"type": "string", "enum": ["accounting", "moat", "leverage", "disruption"]},
                    "attack": {"type": "string"}, "verdict": {"type": "string", "enum": ["survives", "kills"]},
                    "severity": {"type": "string", "enum": ["minor", "major"], "description": "on a kill: 'major' = a genuine dealbreaker, veto even if 3 others survive"}},
                    "required": ["lens", "attack", "verdict"]},
            },
            "growth_exception": {"type": "boolean", "description": "true ONLY for a fairly-valued (NOT overvalued) business with exceptional, near-certain durable growth (e.g. 20%+ with a dominant multi-year runway, TSMC-like) that lacks a classic margin of safety but is worth surfacing to the user for a judgment call. Never for overvalued names. Rare."},
            "reasoning": {"type": "string", "description": "1–2 sentences: the categorization decision and why"},
        },
        "required": ["looks_good", "understood", "thesis", "growth", "future_growth", "falsifiers", "red_team", "growth_exception", "reasoning"],
    },
}


# Categories: 1 Confident (good + understood + fairly-priced/cheap) · 3 Watch (good but
# overpriced) · 2 Hard to understand · 0 Rejected (business-quality failure).
CAT_CONFIDENT, CAT_WATCH_PRICE, CAT_HARD, CAT_REJECT = 1, 3, 2, 0
FAIR_FLOOR = -12.0        # margin at/above this = "fairly valued" → tradeable; below → overpriced watch
GROWTH_EXC_FLOOR = -30.0  # a growth-exception can stretch to here, but never deeply-overvalued names


def _quality_survives(out: dict) -> bool:
    """Business-quality survival — the 4 red-team lenses are all quality (no valuation)."""
    rt = [r for r in (out.get("red_team") or []) if isinstance(r, dict)]
    survive_ct = sum(1 for r in rt if r.get("verdict") == "survives")
    major_kill = any(r.get("verdict") == "kills" and r.get("severity") == "major" for r in rt)
    return len(rt) >= 3 and survive_ct >= 3 and not major_kill


def _derive_category(out: dict, margin_pct: float | None, growth_exception: bool) -> int:
    if not out.get("looks_good") or not _quality_survives(out):
        return CAT_REJECT                       # fails on business quality/durability
    if not out.get("understood"):
        return CAT_HARD                          # good, but a black box
    # good + understood → split by PRICE (deterministic, no LLM drift)
    fairly_priced = (margin_pct is not None and margin_pct >= FAIR_FLOOR) or growth_exception
    return CAT_CONFIDENT if fairly_priced else CAT_WATCH_PRICE


# ── rating: a quality-first composite score, computed once & reused by every agent ──
# Philosophy (the user's): a great business at a fair price beats a fair business at
# a great price — so quality + durability dominate; margin of safety is supportive,
# not decisive. Pure math on already-stored signals ⇒ deterministic, no drift.

def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _score_one(o: Opportunity) -> tuple[float, dict]:
    """Return (total 0–100, breakdown). The breakdown records each component's 0–100
    sub-score AND the exact inputs that produced it — so the rating is fully
    auditable ('reasoning' = the transparent math, no LLM, no drift)."""
    s = o.stats or {}
    roe_v, roa_v = s.get("return_on_equity"), s.get("return_on_assets")
    pm_v, om_v = s.get("profit_margins"), s.get("operating_margins")
    rg_v, eg_v = s.get("revenue_growth"), s.get("earnings_growth")
    # Quality (0..1) — returns on capital, margins, red-team strength
    roe = _clamp01((roe_v or 0) / 0.30)
    roa = _clamp01((roa_v or 0) / 0.15)
    pm = _clamp01((pm_v or 0) / 0.25)
    om = _clamp01((om_v or 0) / 0.30)
    rt = [r for r in (o.red_team or []) if isinstance(r, dict)]
    surv = sum(1 for r in rt if r.get("verdict") == "survives")
    rt_q = (surv / len(rt)) if rt else 0.5
    major = any(r.get("verdict") == "kills" and r.get("severity") == "major" for r in rt)
    if major:
        rt_q *= 0.4
    quality = 0.30 * roe + 0.15 * roa + 0.20 * pm + 0.15 * om + 0.20 * rt_q
    # Durability (0..1) — growth trend + a real 5–10yr durability write-up
    rg = _clamp01((rg_v or 0) / 0.20)
    eg = _clamp01((eg_v or 0) / 0.25)
    dur_txt = bool(o.future_growth and len(o.future_growth) > 40)
    durability = _clamp01(0.55 * rg + 0.30 * eg + (0.15 if dur_txt else 0.0))
    # Margin of safety (0..1) — supportive, deliberately NOT dominant
    m = o.margin_pct
    margin = 0.5 if m is None else _clamp01((m + 12) / 52)      # -12%→0, 0%→0.23, +40%→1
    base = 100 * (0.45 * quality + 0.30 * durability + 0.25 * margin)
    # Risk overlay — a very weak single component isn't worth the risk, so it drags
    # the whole score down (compounding: multiple weak spots hurt more). Balanced
    # names (every component ≥ the floor) are untouched.
    floor, pmax = 25.0, 0.5
    comps = {"quality": quality * 100, "durability": durability * 100, "margin": margin * 100}
    factor, weak = 1.0, []
    for cname, sc in comps.items():
        if sc < floor:
            factor *= 1 - pmax * ((floor - sc) / floor)        # sc=0 → ×0.5 · sc=floor → ×1.0
            weak.append(cname)
    total = round(base * factor, 1)
    breakdown = {
        "total": total, "base": round(base, 1),
        "penalty": {"factor": round(factor, 3), "weak": weak, "floor": floor},
        "weights": {"quality": 0.45, "durability": 0.30, "margin": 0.25},
        "quality": {"score": round(quality * 100, 1), "inputs": {
            "return_on_equity": roe_v, "return_on_assets": roa_v,
            "profit_margin": pm_v, "operating_margin": om_v,
            "red_team": f"{surv}/{len(rt)} lenses survived" + (" · MAJOR kill (×0.4)" if major else "")}},
        "durability": {"score": round(durability * 100, 1), "inputs": {
            "revenue_growth": rg_v, "earnings_growth": eg_v, "durability_writeup": dur_txt}},
        "margin": {"score": round(margin * 100, 1), "inputs": {"margin_of_safety_pct": m}},
    }
    return total, breakdown


async def score_pool(db=None, categories=(1, 3)) -> dict:
    """Rate the confident (+ watch) names: overall score + per-sector rank among the
    tradeable (Confident) set. Cheap and deterministic; run after every analysis and
    reprice so the ranking tracks fresh margins."""
    own = db is None
    db = db or async_session()
    try:
        rows = (await db.execute(select(Opportunity).where(Opportunity.category.in_(categories)))).scalars().all()
        for o in rows:
            o.score, breakdown = _score_one(o)
            o.meta = {**(o.meta or {}), "score_breakdown": breakdown}
        # rank within each (category, sector) group — so Confident names rank among
        # Confident, and Watch names rank among Watch, in their sector.
        by_group = {}
        for o in rows:
            if o.score is not None:
                by_group.setdefault((o.category, o.sector or "Unknown"), []).append(o)
            else:
                o.sector_rank = None
        ranked = 0
        for lst in by_group.values():
            lst.sort(key=lambda x: x.score, reverse=True)
            for i, o in enumerate(lst, 1):
                o.sector_rank = i
                ranked += 1
        await db.commit()
        logger.info("Scored pool: %d names · %d ranked across %d (category,sector) groups", len(rows), ranked, len(by_group))
        return {"scored": len(rows), "ranked": ranked, "groups": len(by_group)}
    finally:
        if own:
            await db.close()


def _prompts(o: Opportunity, stats: dict) -> tuple[str, str]:
    """The (system, user) pair for one stock — shared by the single-call and batch paths."""
    system = ("You are 'the Partner', a patient Munger-style value investor building a CENTRAL, shared "
              "repository of vetted businesses for LONG-TERM (5–10 year) investing. Judge the BUSINESS on its "
              "merits, INDEPENDENT OF THE CURRENT PRICE — valuation is handled separately by us, so do NOT let "
              "price affect looks_good or the red-team. \n"
              "looks_good = is this a genuinely durable, high-quality business, weighing FUTURE growth heavily: "
              "do the company AND its industry have the scope and staying power to stay relevant and ideally "
              "dominate over the next 5–10 years? (A structurally declining or disrupted franchise is NOT "
              "looks_good, however cheap.) \n"
              "understood = can we understand and model it with the available info (circle of competence)? \n"
              "Write the thesis, near-term growth, and the 5–10yr durability view; ARM 2–5 machine-checkable "
              "falsifiers (allowed metrics only); run a 4-lens BUSINESS-QUALITY red-team (accounting, moat, "
              "leverage, disruption — NOT valuation), marking a kill 'major' only if it's a genuine dealbreaker. \n"
              "growth_exception = true ONLY for an exceptional, near-certain durable grower (TSMC-like) that "
              "would be worth owning even without a classic margin of safety. Be consistent and skeptical; do "
              "not be optimistic. Call central_analysis.")
    user = (f"SYMBOL {o.symbol} ({o.name}, {o.sector})\n"
            f"VALUATION: conservative FV ${o.fv_conservative}, margin {o.margin_pct}%, confident={o.fv_confident}.\n"
            f"STATS: {json.dumps(stats, default=str)}\n"
            + (f"ADMIN-PROVIDED INFO (weigh this):\n{o.admin_notes}\n" if o.admin_notes else "")
            + "\nAnalyze and categorize.")
    return system, user


async def _analyze_llm(o: Opportunity, stats: dict) -> dict | None:
    system, user = _prompts(o, stats)
    return await asyncio.to_thread(research._llm_json, system, user, _ANALYSIS_TOOL, 3400)


def _apply_stats_gate(o: Opportunity, stats: dict) -> tuple[bool, list[str]]:
    """Store stats + gate result. On failure, finalize as rejected_stats (no LLM)."""
    o.stats = stats
    o.last_analyzed_at = engine._utcnow()
    passed, reasons = _stats_gate(stats, o.sector)
    o.stats_pass = passed
    if not passed:
        o.analysis_status = "rejected_stats"
        o.category = 0
        o.central_thesis = None
        o.falsifiers, o.red_team, o.growth, o.understood = [], [], None, None
        o.meta = {**(o.meta or {}), "reject_reasons": reasons}
    return passed, reasons


def _finalize(o: Opportunity, out: dict | None) -> int | None:
    """Turn a raw LLM verdict into stored reasoning + a category. None = incomplete
    (truncated/no-key) → leave pending for a retry, never reject on incomplete data."""
    rt = [r for r in ((out or {}).get("red_team") or []) if isinstance(r, dict)]
    if not out or len(rt) < 3:
        o.analysis_status = "pending"
        return None
    o.central_thesis = out.get("thesis")
    o.falsifiers = out.get("falsifiers") or []
    o.red_team = rt
    o.growth = out.get("growth")
    o.future_growth = out.get("future_growth")
    o.understood = bool(out.get("understood"))
    ge = bool(out.get("growth_exception")) and o.margin_pct is not None and o.margin_pct >= GROWTH_EXC_FLOOR
    o.category = _derive_category(out, o.margin_pct, ge)
    o.growth_exception = ge and o.category == CAT_CONFIDENT
    o.analysis_status = "analyzed"
    o.meta = {**(o.meta or {}), "reasoning": out.get("reasoning")}
    return o.category


async def analyze(db, o: Opportunity) -> dict:
    """Single-stock: stats gate → (if good) one harness call → category. Used
    interactively (admin re-analyze chat). Bulk runs use analyze_pool (batched)."""
    stats = await asyncio.to_thread(_stats, o.symbol)
    passed, reasons = _apply_stats_gate(o, stats)
    if not passed:
        return {"category": 0, "stats_pass": False, "reasons": reasons}
    out = await _analyze_llm(o, stats)
    cat = _finalize(o, out)
    if cat is None:
        return {"category": None, "stats_pass": True, "incomplete": True}
    return {"category": cat, "stats_pass": True, "understood": o.understood,
            "growth_exception": o.growth_exception}


async def _gate_one_id(opp_id) -> dict | None:
    """Own short-lived session: fetch stats + gate. Reject-on-stats is finalized
    here (no LLM). Survivors return their (id, symbol, system, user) for the batch."""
    db = async_session()
    try:
        o = await db.get(Opportunity, opp_id)
        if o is None:
            return None
        stats = await asyncio.to_thread(_stats, o.symbol)
        passed, _ = _apply_stats_gate(o, stats)
        payload = None if not passed else {
            "id": str(opp_id), "symbol": o.symbol, **dict(zip(("system", "user"), _prompts(o, stats)))}
        await db.commit()
        return {"gated": not passed, "payload": payload}
    except Exception as e:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:
            pass
        logger.warning("stats gate failed for %s: %s", opp_id, e)
        return None
    finally:
        await db.close()


async def _apply_one_id(opp_id, out: dict | None) -> int | None:
    """Own short-lived session: write the batch verdict for one stock."""
    db = async_session()
    try:
        o = await db.get(Opportunity, opp_id)
        if o is None:
            return None
        cat = _finalize(o, out)
        await db.commit()
        return cat
    except Exception as e:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:
            pass
        logger.warning("apply result failed for %s: %s", opp_id, e)
        return None
    finally:
        await db.close()


async def analyze_pool(db=None, limit: int = 600, only_unanalyzed: bool = True,
                       categories: tuple | None = None,
                       poll_interval: int = 20, timeout: int = 5400) -> dict:
    """Analyze the pool via the Message Batches API — cheap (~50% off) and scalable.
    Cheap STATS gate runs first (no LLM for weak businesses); survivors go into ONE
    batch. Stats fetch + result write each use a fresh short-lived session so a slow
    step can't leave a DB connection idle long enough to be dropped.

    only_unanalyzed=True  → the daily job: analyze only new/pending discoveries.
    categories=(1, 3)     → the weekly job: fully re-review those buckets regardless
                            of status (keeps Confident/Watch theses fresh)."""
    idb = async_session()
    try:
        q = select(Opportunity.id)
        if categories:
            q = q.where(Opportunity.category.in_(categories))
        elif only_unanalyzed:
            q = q.where(or_(Opportunity.analysis_status == "pending", Opportunity.category.is_(None)))
        ids = [r[0] for r in (await idb.execute(q.limit(limit))).all()]
    finally:
        await idb.close()

    # 1) stats gate (bounded concurrency) — reject weak businesses without an LLM
    sem = asyncio.Semaphore(8)
    async def _g(i):
        async with sem:
            try:   # a stalled yfinance socket in the stats gate must never hang the batch
                return await asyncio.wait_for(_gate_one_id(i), timeout=30)
            except asyncio.TimeoutError:
                return None
    gated = [g for g in await asyncio.gather(*[_g(i) for i in ids]) if g]
    survivors = [g["payload"] for g in gated if not g["gated"] and g["payload"]]
    rejected_stats = sum(1 for g in gated if g["gated"])
    logger.info("stats gate: %d survivors / %d rejected (of %d)", len(survivors), rejected_stats, len(ids))

    # 2) one batch for all survivors (half price)
    items = [(p["id"], p["system"], p["user"]) for p in survivors]
    results = await research.run_batch_json(items, _ANALYSIS_TOOL, 3400, poll_interval, timeout)
    batch_id = results.pop("__batch_id__", None)

    # 3) apply verdicts (fresh session per name)
    by_id = {p["id"]: p for p in survivors}
    applied = await asyncio.gather(*[
        _apply_one_id(uuid.UUID(cid), results.get(cid)) for cid in by_id])
    cat1 = sum(1 for c in applied if c == 1)
    cat2 = sum(1 for c in applied if c == 2)
    cat3 = sum(1 for c in applied if c == 3)
    rej_llm = sum(1 for c in applied if c == 0)
    incomplete = sum(1 for c in applied if c is None)
    logger.info("Central batch %s: %d survivors · cat1=%d cat2=%d cat3=%d rej(llm)=%d incomplete=%d · rejected_stats=%d",
                batch_id, len(survivors), cat1, cat2, cat3, rej_llm, incomplete, rejected_stats)
    await score_pool()      # (re)rate the confident/watch set so the ranking is fresh
    return {"analyzed": len(ids), "batch_id": batch_id, "survivors": len(survivors),
            "rejected_stats": rejected_stats, "category_1": cat1, "category_2": cat2,
            "category_3": cat3, "rejected_llm": rej_llm, "incomplete": incomplete}


async def value_symbols(db, symbols) -> dict:
    """Value a set of symbols ONCE — deduped across every user who tracks them —
    and refresh the shared central record. Returns {SYMBOL: fair_value dict}.
    (fair_value is 24h-cached per symbol, so this is one compute per symbol per day
    no matter how many users track it — the compute-once principle for watchlists.)"""
    syms = sorted({s.upper() for s in symbols if s})
    if not syms:
        return {}
    rows = {r.symbol: r for r in (await db.execute(
        select(Opportunity).where(Opportunity.symbol.in_(syms)))).scalars().all()}
    out = {}
    for s in syms:
        try:
            fv = await asyncio.to_thread(fv_svc.fair_value, s)
        except Exception as e:  # noqa: BLE001
            logger.warning("valuation failed for %s: %s", s, e)
            fv = None
        out[s] = fv
        r = rows.get(s)
        if r is not None and fv and fv.get("conservative"):     # keep the central record fresh
            r.last_price = fv.get("current_price")
            r.margin_pct = fv.get("margin_pct")
            r.fv_conservative = fv.get("conservative")
            r.fv_confident = bool(fv.get("confident"))
            r.fv_low, r.fv_base, r.fv_high = fv.get("low"), fv.get("base"), fv.get("high")
            r.last_priced_at = engine._utcnow()
    await db.commit()
    return out


# ── Pre-market refresh (before the first live tick) ─────────────────────────
_PREMARKET_FV_MOVE = 0.15    # |ΔFV_conservative| ≥ 15% since last stored → re-analyze
_PREMARKET_STAT_MOVE = 0.02  # a key TTM fundamental moved ≥ 2pp → fresh financials likely landed


def _material_stat_change(old: dict | None, new: dict | None) -> bool:
    """A fresh earnings report shows up as a jump in the TTM fundamentals."""
    if not old or not new:
        return False
    for k in ("revenue_growth", "earnings_growth", "profit_margins", "return_on_equity"):
        a, b = old.get(k), new.get(k)
        if a is not None and b is not None and abs(float(b) - float(a)) >= _PREMARKET_STAT_MOVE:
            return True
    return False


async def premarket_refresh(db=None) -> dict:
    """Run BEFORE the 9:50 first live tick. For the ACTIONABLE set (Confident + Watch):
    recompute FV + stats + trend from fresh fundamentals — NO LLM — so margins are honest
    at the open; then flag any name whose fundamentals materially moved (earnings, a big FV
    swing, or a trend flip to falling) and LLM-re-analyze THOSE right now — not at 10:20,
    which is after the first trade. New discoveries stay on the 10:20 pass; weekly is the
    full backstop. Cheap on quiet days (no LLM unless something actually changed)."""
    own = db is None
    db = db or async_session()
    try:
        rows = (await db.execute(select(Opportunity).where(
            Opportunity.category.in_((1, 3)), Opportunity.status == "candidate"))).scalars().all()
        if not rows:
            return {"refreshed": 0, "changed": []}
        from app.services.agent import trend as trend_svc
        now = engine._utcnow()
        sem = asyncio.Semaphore(4)   # gentle on yfinance — 3 fundamentals fetches per name

        def _pull_sync(sym):
            return fv_svc.fair_value(sym), _stats(sym), trend_svc.assess_trend(sym)

        async def _pull(r):
            async with sem:
                try:   # hard per-name timeout — a stalled yfinance socket must never hang the job
                    fv, stats, tr = await asyncio.wait_for(asyncio.to_thread(_pull_sync, r.symbol), timeout=30)
                except Exception:  # noqa: BLE001 — timeout/fetch error → fail-open, keep last-known
                    fv, stats, tr = {}, {}, {}
            return r, fv, stats, tr

        changed = []
        for r, fv, stats, tr in await asyncio.gather(*[_pull(r) for r in rows]):
            reasons = []
            if _material_stat_change(r.stats, stats):
                reasons.append("earnings")
            if fv and fv.get("conservative") and r.fv_conservative:
                if abs(fv["conservative"] - r.fv_conservative) / r.fv_conservative >= _PREMARKET_FV_MOVE:
                    reasons.append("fv_move")
            if tr and tr.get("status") == "falling":
                reasons.append("falling")
            # write the fresh numbers (this is what makes the 9:50 margins honest)
            if fv and fv.get("conservative"):
                r.last_price = fv.get("current_price"); r.margin_pct = fv.get("margin_pct")
                r.fv_conservative = fv.get("conservative"); r.fv_confident = bool(fv.get("confident"))
                r.fv_low, r.fv_base, r.fv_high = fv.get("low"), fv.get("base"), fv.get("high")
                r.last_priced_at = now
            if stats and any(v is not None for v in stats.values()):   # don't wipe good stats on a failed fetch
                r.stats = stats
            if tr and tr.get("status") not in (None, "unknown"):
                meta = dict(r.meta or {})
                meta["trend"] = {"status": tr.get("status"), "score": tr.get("trend_score"),
                                 "summary": tr.get("summary"), "at": now.isoformat()}
                r.meta = meta
            # promote/demote on the fresh margin (same rule as the daily reprice)
            if r.margin_pct is not None:
                if r.category == 3 and r.margin_pct >= FAIR_FLOOR:
                    r.category = 1
                elif r.category == 1 and not r.growth_exception and r.margin_pct < FAIR_FLOOR:
                    r.category = 3
            if reasons:
                r.analysis_status = "pending"    # queue for the immediate re-analysis below
                changed.append((r.symbol, reasons))
        await db.commit()
        # Names that actually REPORTED earnings get a FOUNDATIONAL, transcript-grade re-thesis
        # (fresh quarter + surprise + grades + news + web-searched call highlights) — richer than
        # the ratio-only re-analysis below, and it clears them from the pending set.
        from app.services.agent import earnings as earn
        try:
            earned = await earn.run_earnings_theses(db)
        except Exception:  # noqa: BLE001
            logger.exception("earnings re-thesis pass failed")
            earned = {"reporters": 0}
        # Re-analyze the REMAINING changed set (analyze_pool picks up pending rows) — done before 9:50.
        reanalyzed = await analyze_pool(only_unanalyzed=True) if changed else {"analyzed": 0}
        await score_pool()   # margins + categories moved → re-rate + re-rank
        logger.info("Pre-market refresh: %d actionable, %d changed %s → reanalyzed %s, earnings %s",
                    len(rows), len(changed), [s for s, _ in changed], reanalyzed, earned)
        return {"refreshed": len(rows), "changed": [{"symbol": s, "why": w} for s, w in changed],
                "reanalyzed": reanalyzed, "earnings": earned}
    finally:
        if own:
            await db.close()


async def reanalyze_with_info(db, o: Opportunity, info: str) -> dict:
    """Admin chat: append the admin's info and re-run the analysis — the harness
    may drop it, promote it to category 1, or keep it in category 2."""
    o.admin_notes = ((o.admin_notes + "\n\n") if o.admin_notes else "") + info.strip()
    before = o.category
    res = await analyze(db, o)
    await db.commit()
    reply = (o.meta or {}).get("reasoning") or "Re-analyzed."
    move = "kept in category 2" if o.category == before else (
        "promoted to category 1" if o.category == 1 else "dropped" if o.category == 0 else "updated")
    return {"reply": f"Re-analyzed with your info → {move}. {reply}", "category": o.category}


# ── end-of-day news watch (Confident names) ─────────────────────────────────
# The Confident bucket is the tradeable set — after the close we scan it for fresh
# news and flag anything that could move the long-term thesis. Compute-once on the
# shared pool (~one classification per Confident name that actually had news), so
# every user holding it inherits the flag. Cheap: batched, and only names WITH
# recent headlines hit the LLM.

_NEWS_TOOL = {
    "name": "news_materiality",
    "description": "Whether recent headlines are material to a 5–10 year investment thesis.",
    "input_schema": {
        "type": "object",
        "properties": {
            "material": {"type": "boolean", "description": "true only if this could change a long-term thesis (not routine noise/price chatter)"},
            "sentiment": {"type": "string", "enum": ["positive", "neutral", "negative"]},
            "severity": {"type": "string", "enum": ["minor", "major"], "description": "major = could meaningfully impair or strengthen the thesis"},
            "note": {"type": "string", "description": "one sentence: what happened and why it does or doesn't matter"},
        },
        "required": ["material", "sentiment", "severity", "note"],
    },
}


def _fresh_headlines(symbol: str, cutoff) -> list[str]:
    """Recent (within cutoff) headline titles for a symbol, newest first."""
    out = []
    for a in (get_news(symbol) or []):
        pub, title = a.get("published"), (a.get("title") or "").strip()
        if not title:
            continue
        ts = None
        try:
            if isinstance(pub, (int, float)) or (isinstance(pub, str) and pub.isdigit()):
                ts = datetime.fromtimestamp(int(pub), tz=timezone.utc).replace(tzinfo=None)
            elif isinstance(pub, str) and pub:
                ts = datetime.fromisoformat(pub.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
        except Exception:
            ts = None
        if ts is None or ts >= cutoff:      # keep if fresh, or if the date is unparseable
            out.append(title)
    return out[:6]


async def _news_one_id(opp_id, cutoff) -> dict | None:
    """Own session: fetch fresh headlines for one Confident name → prompt payload
    (or None if it had no recent news)."""
    db = async_session()
    try:
        o = await db.get(Opportunity, opp_id)
        if o is None:
            return None
        heads = await asyncio.to_thread(_fresh_headlines, o.symbol, cutoff)
        if not heads:
            return None
        user = (f"HOLDING {o.symbol} ({o.name}).\nTHESIS: {o.central_thesis or 'n/a'}\n"
                f"RECENT HEADLINES:\n- " + "\n- ".join(heads) + "\n\nAssess materiality to the long-term thesis.")
        return {"id": str(opp_id), "symbol": o.symbol, "heads": heads, "user": user}
    except Exception as e:  # noqa: BLE001
        logger.warning("news fetch failed for %s: %s", opp_id, e)
        return None
    finally:
        await db.close()


async def _apply_news_one(opp_id, heads: list[str], out: dict | None) -> bool:
    """Own session: store the news snapshot + flag major-negative for review."""
    db = async_session()
    try:
        o = await db.get(Opportunity, opp_id)
        if o is None:
            return False
        flagged = bool(out) and out.get("severity") == "major" and out.get("sentiment") == "negative"
        o.meta = {**(o.meta or {}), "news": {
            "checked_at": engine._utcnow().isoformat(), "headlines": heads,
            "material": bool(out and out.get("material")), "sentiment": (out or {}).get("sentiment"),
            "severity": (out or {}).get("severity"), "note": (out or {}).get("note"),
            "needs_review": flagged}}
        await db.commit()
        return flagged
    except Exception as e:  # noqa: BLE001
        try:
            await db.rollback()
        except Exception:
            pass
        logger.warning("news apply failed for %s: %s", opp_id, e)
        return False
    finally:
        await db.close()


async def news_check(db=None, categories: tuple = (1,), lookback_hours: int = 30,
                     poll_interval: int = 15, timeout: int = 1800) -> dict:
    """End-of-day: scan the Confident bucket for fresh, thesis-relevant news.
    Only names that actually have recent headlines hit the (batched) harness."""
    cutoff = engine._utcnow() - timedelta(hours=lookback_hours)
    idb = async_session()
    try:
        ids = [r[0] for r in (await idb.execute(
            select(Opportunity.id).where(Opportunity.category.in_(categories)))).all()]
    finally:
        await idb.close()

    sem = asyncio.Semaphore(8)
    async def _n(i):
        async with sem:
            return await _news_one_id(i, cutoff)
    with_news = [p for p in await asyncio.gather(*[_n(i) for i in ids]) if p]
    if not with_news:
        logger.info("EOD news check: %d Confident names, none with fresh news", len(ids))
        return {"scanned": len(ids), "with_news": 0, "flagged": 0}

    system = ("You are the Partner monitoring long-term holdings. Given recent headlines for a stock and its "
              "thesis, judge whether the news is MATERIAL to a 5–10 year thesis — ignore routine price moves, "
              "analyst rating noise, and puff pieces. Flag severity 'major' only for genuine thesis-movers "
              "(guidance cuts, regulation, litigation, accounting issues, competitive/secular shifts, M&A). "
              "Be consistent and skeptical. Call news_materiality.")
    results = await research.run_batch_json(
        [(p["id"], system, p["user"]) for p in with_news], _NEWS_TOOL, 600, poll_interval, timeout)
    results.pop("__batch_id__", None)

    flags = await asyncio.gather(*[
        _apply_news_one(uuid.UUID(p["id"]), p["heads"], results.get(p["id"])) for p in with_news])
    flagged = sum(1 for f in flags if f)
    logger.info("EOD news check: %d Confident · %d with news · %d flagged for review",
                len(ids), len(with_news), flagged)
    return {"scanned": len(ids), "with_news": len(with_news), "flagged": flagged}
