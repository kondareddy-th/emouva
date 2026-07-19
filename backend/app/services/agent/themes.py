"""Polytrade — the Themes engine (see docs/POLYTRADE.md).

M0: originate a theme's Living Thesis (narrative + hero stat + falsifiers + 4-lens
red-team, researched with web_search), then pick its basket from the vetted Opportunity
pool with conviction-weighted, capped target weights.

M1 (monitoring): a daily pass re-scores each live theme's conviction against fresh
constituent data, headlines and earnings, trips falsifiers, drives the health/status
state machine (strong→watching→breaking; a break is M2's unwind trigger) and refreshes
the basket's performance snapshot — every change appended to the ThemeEvent stream.

Constituents come ONLY from the central Opportunity pool: a name can enter a theme
only if we've already reasoned about the business. Weights are computed HERE in Python
(not by the LLM) so the concentration caps are guaranteed, not merely requested.
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.db import Theme, ThemeConstituent, ThemeEvent, Opportunity
from app.services.agent import research

logger = logging.getLogger(__name__)

# Concentration guardrails (deterministic — enforced in _compute_weights, never left to the LLM).
PER_NAME_CAP = 0.35        # no single name may exceed 35% of a basket
SPEC_SLEEVE_CAP = 0.20     # the whole speculative (multibagger) sleeve is capped at 20%
MIN_NAMES, MAX_NAMES = 4, 8


# ── slug + health helpers ────────────────────────────────────────────────────

def _slugify(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    return s[:70] or "theme"


async def _unique_slug(db, title: str) -> str:
    base = _slugify(title)
    taken = set((await db.execute(select(Theme.slug).where(Theme.slug.like(base + "%")))).scalars().all())
    if base not in taken:
        return base
    i = 2
    while f"{base}-{i}" in taken:
        i += 1
    return f"{base}-{i}"


def _health(conviction: int, survives: bool = True) -> str:
    """Map conviction → the health pill users see. A failed red-team can't read 'strong'."""
    if not survives or conviction < 40:
        return "breaking" if conviction < 40 else "watching"
    if conviction < 60:
        return "watching"
    return "strong"


# ── the ThemeEvent stream (admin timeline + the addictive reasoning feed) ─────

async def log_event(db, theme_id, kind: str, summary: str, detail: dict | None = None) -> None:
    db.add(ThemeEvent(theme_id=theme_id, kind=kind, summary=summary, detail=detail))
    await db.flush()


# ── notifications (in-app; part of the caller's transaction, no separate commit) ──

def notify(db, user_id, type_: str, title: str, message: str) -> None:
    from app.models.db import Notification
    db.add(Notification(user_id=user_id, type=type_, title=title, message=message))


async def notify_theme_users(db, theme_id, type_: str, title: str, message: str) -> int:
    """Notify every user with an OPEN allocation in a theme (dedup'd). For thesis
    break/weaken alerts — the retention loop."""
    from app.models.db import ThemeAllocation
    uids = (await db.execute(select(ThemeAllocation.user_id).where(
        ThemeAllocation.theme_id == theme_id,
        ThemeAllocation.status.in_(("pending", "active", "unwinding"))))).scalars().all()
    seen = set()
    for uid in uids:
        if uid in seen:
            continue
        seen.add(uid)
        notify(db, uid, type_, title, message)
    return len(seen)


# ── capped, conviction-weighted basket weights ───────────────────────────────

def _compute_weights(picks: list[dict]) -> list[dict]:
    """picks: [{symbol, role, conviction}]. Returns the same list with a target_weight
    per name (summing to 1.0). Weights start ∝ conviction; then two caps are enforced:

      • per-name ≤35%  — the HARD invariant (single-name concentration is the worst risk);
      • speculative sleeve ≤20% — best-effort. The two can be jointly infeasible (e.g. a
        single anchor can hold ≤35%, forcing the rest into the sleeve); when so, we keep
        the per-name cap and let the sleeve overflow, logging it. In practice the LLM is
        told to favor a few anchors, so a feasible basket holds both."""
    picks = [p for p in picks if isinstance(p, dict) and p.get("symbol")]
    if not picks:
        return []
    conv = {p["symbol"]: max(1.0, float(p.get("conviction") or 1)) for p in picks}
    role = {p["symbol"]: (p.get("role") or "satellite") for p in picks}
    total = sum(conv.values()) or 1.0
    w = {s: conv[s] / total for s in conv}

    spec = [s for s in w if role[s] == "speculative"]
    nonspec = [s for s in w if role[s] != "speculative"]
    # 1) sleeve cap (best-effort): scale spec down, hand the freed weight to non-spec ∝ weight
    if spec and nonspec:
        s_spec = sum(w[s] for s in spec)
        if s_spec > SPEC_SLEEVE_CAP:
            freed = s_spec - SPEC_SLEEVE_CAP
            for s in spec:
                w[s] *= SPEC_SLEEVE_CAP / s_spec
            base = sum(w[s] for s in nonspec) or 1.0
            for s in nonspec:
                w[s] += freed * (w[s] / base)
    # 2) per-name cap (HARD): cap overflow, redistribute to under-cap names — preferring
    #    non-spec first so the sleeve is disturbed only when the anchors are saturated
    for _ in range(24):
        over = [s for s in w if w[s] > PER_NAME_CAP + 1e-9]
        if not over:
            break
        excess = sum(w[s] - PER_NAME_CAP for s in over)
        for s in over:
            w[s] = PER_NAME_CAP
        under = [s for s in nonspec if w[s] < PER_NAME_CAP - 1e-9]
        if not under:                                         # anchors saturated — spill into the sleeve
            under = [s for s in w if w[s] < PER_NAME_CAP - 1e-9]
        base = sum(w[s] for s in under)
        if not under or base <= 0:
            break
        for s in under:
            w[s] += excess * (w[s] / base)
    if spec and sum(w[s] for s in spec) > SPEC_SLEEVE_CAP + 1e-6:
        logger.warning("theme basket: speculative sleeve %.0f%% exceeds cap — too few anchors to absorb it",
                       100 * sum(w[s] for s in spec))
    tot = sum(w.values()) or 1.0
    res = [{"symbol": s, "role": role[s], "conviction": int(conv[s]),
            "target_weight": round(w[s] / tot, 4)} for s in w]
    # absorb 4-dp rounding residual into the largest weight so the basket sums to exactly 1.0
    drift = round(1.0 - sum(x["target_weight"] for x in res), 4)
    if res and abs(drift) >= 1e-4:
        big = max(res, key=lambda x: x["target_weight"])
        big["target_weight"] = round(big["target_weight"] + drift, 4)
    return res


# ── origination: the theme Living Thesis ─────────────────────────────────────

_THEME_TOOL = {
    "name": "theme_thesis",
    "description": "The theme's Living Thesis: narrative, a punchy hero stat, conviction, downward triggers, and a 4-lens red-team.",
    "input_schema": {"type": "object", "properties": {
        "narrative": {"type": "string", "description": "2–4 sentences: the core bet and why now"},
        "hero_stat": {"type": "string", "description": "one punchy quantified claim, e.g. 'TSMC: ~50% revenue growth through 2029'"},
        "conviction": {"type": "integer", "description": "0–100 conviction in the theme right now, given the evidence"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "2–4 short tags, e.g. AI, semis, memory"},
        "falsifiers": {
            "type": "array", "description": "3–7 downward triggers that would weaken or break the theme",
            "items": {"type": "object", "properties": {
                "label": {"type": "string", "description": "plain-language signal, e.g. 'HBM ASPs fall quarter-over-quarter'"},
                "breaks_if": {"type": "string", "description": "the specific condition that trips it"},
                "kind": {"type": "string", "enum": ["metric", "narrative"],
                         "description": "metric = checkable from constituent fundamentals; narrative = watched via news/earnings"}},
                "required": ["label", "breaks_if", "kind"]}},
        "red_team": {
            "type": "array", "description": "exactly 4 lenses each trying to KILL the theme",
            "items": {"type": "object", "properties": {
                "lens": {"type": "string", "enum": ["demand", "supply", "valuation", "catalyst"]},
                "attack": {"type": "string", "description": "the strongest bear case from this lens"},
                "verdict": {"type": "string", "enum": ["survives", "kills"]}},
                "required": ["lens", "attack", "verdict"]}},
    }, "required": ["narrative", "hero_stat", "conviction", "falsifiers", "red_team"]},
}

_ORIGINATE_SYSTEM = (
    "You are 'the Partner', a skeptical value-driven strategist building a CENTRAL repository of "
    "investable THEMES — multi-year narratives backed by a basket of quality businesses. Use web_search "
    "for the QUALITATIVE state of the world (industry cycles, demand/supply, catalysts, capex) and the "
    "get_stock_data tool for any hard number. Write a tight narrative, a single punchy hero stat, and "
    "ARM 3–7 falsifiers — the downward triggers that would weaken or break the theme (mark each 'metric' "
    "if checkable from a company's fundamentals, else 'narrative'). Then run a 4-lens red-team (demand, "
    "supply/competition, valuation, catalyst/timing), marking each survives or kills. Set conviction "
    "0–100 honestly — reserve 80+ for themes with strong, corroborated evidence. Be concrete and "
    "skeptical; do not hype. Call theme_thesis.")


async def _fill_from_llm(db, theme: Theme) -> Theme:
    """Run the origination LLM (web_search + trusted-data loop, degrading gracefully) and
    write the narrative / hero stat / falsifiers / red-team / conviction onto ``theme``."""
    user = (f"THEME TITLE: {theme.title}\n"
            f"SEED IDEA: {theme.seed_narrative or '(none — develop the strongest version of this theme)'}\n\n"
            "Research the theme and write its thesis, hero stat, falsifiers and red-team.")
    out = None
    try:                                                    # preferred: web_search + trusted-data tool loop
        out = await asyncio.to_thread(research._llm_toolloop, _ORIGINATE_SYSTEM, user, _THEME_TOOL, True, 2200, 5)
    except Exception as e:
        logger.info("theme originate: web-search loop unavailable (%s) — data-only", e)
    if out is None:
        try:
            out = await asyncio.to_thread(research._llm_toolloop, _ORIGINATE_SYSTEM, user, _THEME_TOOL, False, 2200, 4)
        except Exception as e:
            logger.warning("theme originate data-loop failed: %s", e)
    if out is None:
        out = await asyncio.to_thread(research._llm_json, _ORIGINATE_SYSTEM, user, _THEME_TOOL, 2200)
    out = out or {}

    rt = [r for r in (out.get("red_team") or []) if isinstance(r, dict)]
    fal = [f for f in (out.get("falsifiers") or []) if isinstance(f, dict)]   # guard: LLM occasionally returns a malformed non-list
    survives = len(rt) >= 3 and sum(1 for r in rt if r.get("verdict") == "survives") >= 3
    conviction = max(0, min(100, int(out.get("conviction") or 50)))
    hero = out.get("hero_stat")
    theme.tags = theme.tags or out.get("tags") or []
    theme.narrative = out.get("narrative", "") or ""
    theme.hero_stat = (hero[:500] if isinstance(hero, str) else hero)         # column is TEXT; keep it sane
    theme.falsifiers = fal
    theme.red_team = rt
    theme.conviction = conviction
    theme.health = _health(conviction, survives)
    theme.last_thesis_run_at = datetime.utcnow()
    theme.meta = {**(theme.meta or {}), "status": "ready", "survives_red_team": survives, "generated": bool(out)}
    await db.flush()
    await log_event(db, theme.id, "originated",
                    f"Theme originated — conviction {conviction}, red-team {'survived' if survives else 'FAILED (needs work)'}.",
                    {"survives": survives, "conviction": conviction})
    return theme


async def create_stub(db, title: str, seed_narrative: str = "", tags=None, created_by=None) -> Theme:
    """Persist a placeholder theme immediately (so the UI has something to show) — the
    thesis is filled in asynchronously by run_origination()."""
    theme = Theme(slug=await _unique_slug(db, title), title=title, tags=(tags or []),
                  narrative="", status="draft", conviction=50, health="watching",
                  seed_narrative=seed_narrative or None, created_by=created_by,
                  meta={"status": "generating"})
    db.add(theme)
    await db.flush()
    return theme


async def originate(db, title: str, seed_narrative: str = "", tags=None, created_by=None) -> Theme:
    """Inline create + generate (for scripts/schedulers). The API path uses create_stub +
    run_origination so the request returns instantly."""
    theme = await create_stub(db, title, seed_narrative, tags, created_by)
    return await _fill_from_llm(db, theme)


async def run_origination(theme_id, *_ignore) -> None:
    """Background entrypoint: own session, load the stub, fill it from the LLM. Never raises."""
    from app.database import async_session
    async with async_session() as db:
        theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
        if not theme:
            return
        try:
            await _fill_from_llm(db, theme)
            await db.commit()
        except Exception as e:
            logger.exception("theme origination failed for %s: %s", theme_id, e)
            await db.rollback()                                   # the failed txn must be cleared before we can record the error
            theme.meta = {**(theme.meta or {}), "status": "error", "error": str(e)[:200]}
            await db.commit()


# ── basket: pick constituents from the vetted pool, compute capped weights ────

_PROPOSE_TOOL = {
    "name": "theme_candidates",
    "description": "Propose the best US-listed common stocks or ADRs (traded on NYSE/Nasdaq — real, liquid, currently tradeable) that most directly express the theme.",
    "input_schema": {"type": "object", "properties": {
        "candidates": {
            "type": "array", "description": "8–14 tickers — clearest pure-plays / category leaders first, plus a couple higher-upside names",
            "items": {"type": "object", "properties": {
                "symbol": {"type": "string", "description": "ticker as traded on NYSE/Nasdaq (e.g. TSM for TSMC, ASML, NVDA)"},
                "role": {"type": "string", "enum": ["anchor", "satellite", "speculative"]},
                "why": {"type": "string", "description": "one line: why it fits the theme"}},
                "required": ["symbol", "role"]}},
    }, "required": ["candidates"]},
}

_BASKET_TOOL = {
    "name": "theme_basket",
    "description": "Select the final 4–8 constituents and assign each a target weight (%), using OUR metrics. Choose ONLY from the provided candidates.",
    "input_schema": {"type": "object", "properties": {
        "constituents": {
            "type": "array", "description": "4–8 picks — a few strong anchors beat many weak names",
            "items": {"type": "object", "properties": {
                "symbol": {"type": "string", "description": "must be one of the provided candidates"},
                "role": {"type": "string", "enum": ["anchor", "satellite", "speculative"],
                         "description": "anchor = core/highest conviction; satellite = supporting; speculative = small, higher-risk multibagger"},
                "target_weight_pct": {"type": "number", "description": "suggested % of the basket (0–100); the set should sum to ~100"},
                "conviction": {"type": "integer", "description": "0–100 — how strongly this name expresses the theme"},
                "rationale": {"type": "string", "description": "one line grounded in the metrics (quality, valuation, trend)"}},
                "required": ["symbol", "role", "target_weight_pct", "rationale"]}},
    }, "required": ["constituents"]},
}


async def _propose_universe(theme: Theme, hint: str | None = None) -> list[dict]:
    """Stage 1 — the AI proposes the candidate universe (US-listed + ADRs), NOT limited to our
    pool. Web search so it doesn't miss key names or include a delisted/renamed ticker. An
    optional admin `hint` (e.g. 'also consider SK Hynix') is honored — the model resolves the
    correct US-traded ticker via search and includes it."""
    system = ("You are assembling the candidate universe for an investment THEME. Propose 8–14 of the BEST "
              "US-listed common stocks or ADRs (traded on NYSE/Nasdaq — real, liquid, currently tradeable) that "
              "most directly express the theme: the clearest pure-plays and category leaders, plus a couple of "
              "higher-upside names. Use web_search so you don't miss a key name or include a delisted/renamed "
              "ticker. Return tickers as traded on US exchanges (e.g. TSM for TSMC, ASML, NVDA). Give each a "
              "role. Call theme_candidates.")
    guide = (f"\n\nADMIN GUIDANCE — you MUST also consider (resolve each to its correct US-traded ticker "
             f"via web_search, and include it if it's genuinely tradeable): {hint}" if hint else "")
    user = (f"THEME: {theme.title}\nNARRATIVE: {theme.narrative}\nHERO STAT: {theme.hero_stat or '—'}\n\n"
            "List the strongest US-listed / ADR names for this theme." + guide)
    out = None
    try:
        out = await asyncio.to_thread(research._llm_toolloop, system, user, _PROPOSE_TOOL, True, 1800, 4)
    except Exception as e:
        logger.info("theme propose: web-search unavailable (%s) — knowledge-only", e)
    if out is None:
        out = await asyncio.to_thread(research._llm_json, system, user, _PROPOSE_TOOL, 1800)
    seen, uniq = set(), []
    for c in ((out or {}).get("candidates") or []):
        if not isinstance(c, dict) or not c.get("symbol"):
            continue
        s = c["symbol"].upper().strip()
        if s and s not in seen:
            seen.add(s)
            c["symbol"] = s
            uniq.append(c)
    return uniq[:14]


def _enrich(symbols: list[str]) -> list[dict]:
    """Stage 2 — OUR metrics for each proposed ticker (price, fundamentals, fair value + margin
    of safety, trend). Drops tickers we can't price (invalid / untradeable). Runs in a thread."""
    out = []
    for s in symbols:
        try:
            d = research.get_stock_data(s)
        except Exception:
            continue
        if d and d.get("price"):
            out.append(d)
    return out


def _metrics_line(d: dict) -> str:
    f = d.get("fundamentals") or {}
    knife = " (FALLING KNIFE)" if d.get("falling_knife") else ""
    return (f"{d['symbol']} | price {d.get('price')} | margin_of_safety {d.get('margin_of_safety_pct')}% "
            f"| trend {d.get('trend')}{knife} | ROE {f.get('return_on_equity')} "
            f"| op_margin {f.get('operating_margins')} | rev_growth {f.get('revenue_growth')} "
            f"| P/E {f.get('pe_ratio')} | fwd_P/E {f.get('forward_pe')}")


async def pick_constituents(db, theme: Theme, hint: str | None = None) -> tuple[Theme, list[ThemeConstituent]]:
    """Build the basket: (1) the AI proposes the US/ADR universe for the theme (not limited to our
    pool), (2) we ground each candidate in OUR metrics, (3) the AI selects the final 4–8 + target
    weights from those metrics, (4) we enforce the concentration caps. Bumps target_version.
    Optional admin `hint` (e.g. 'also consider SK Hynix') forces specific names into the mix."""
    hint = (hint or "").strip() or None
    proposed = await _propose_universe(theme, hint)
    if not proposed:
        logger.warning("theme %s: AI proposed no candidates", theme.slug)
        return theme, []
    role_by = {c["symbol"]: c.get("role", "satellite") for c in proposed}
    enriched = await asyncio.to_thread(_enrich, [c["symbol"] for c in proposed])
    # names the AI proposed (incl. any from the admin hint) that no provider could price → excluded
    dropped = sorted({c["symbol"].upper() for c in proposed} - {d["symbol"].upper() for d in enriched})
    if not enriched:
        logger.warning("theme %s: none of the proposed candidates could be priced", theme.slug)
        return theme, []
    priced = {d["symbol"].upper() for d in enriched}

    system = ("You are the Partner finalizing a thematic basket. From the CANDIDATES — each shown with OUR "
              "metrics (price, margin of safety vs our fair value, price trend, and key fundamentals) — select "
              "the final 4–8 that best express the theme and assign each a target weight (%). Weight toward the "
              "highest-conviction, best-quality names with a margin of safety; keep speculative names small; "
              "AVOID any name whose trend is 'falling' (a falling knife). Target weights should sum to ~100. "
              "Choose ONLY from the candidates. Call theme_basket.")
    guide = (f"\n\nADMIN GUIDANCE: {hint} — include the requested name(s) if they appear in the candidates "
             "below and reasonably fit the theme." if hint else "")
    user = (f"THEME: {theme.title}\nNARRATIVE: {theme.narrative}\nHERO STAT: {theme.hero_stat or '—'}\n\n"
            "CANDIDATES WITH OUR METRICS:\n" + "\n".join(_metrics_line(d) for d in enriched) + guide)
    # Stage 3 — retry a few times: Sonnet-5 occasionally emits a malformed/empty tool call,
    # which would otherwise yield an empty basket. Retry until we get valid picks.
    raw: list[dict] = []
    for attempt in range(3):
        out = await asyncio.to_thread(research._llm_json, system, user, _BASKET_TOOL, 1800)
        raw = [p for p in ((out or {}).get("constituents") or [])
               if isinstance(p, dict) and (p.get("symbol") or "").upper() in priced]
        if raw:
            break
        logger.info("theme %s: basket selection returned no valid picks (attempt %d) — retrying", theme.slug, attempt + 1)
    if not raw:
        logger.warning("theme %s: basket selection failed after retries", theme.slug)
        return theme, []
    conv_by: dict[str, int | None] = {}
    for p in raw:
        p["symbol"] = p["symbol"].upper()
        conv_by[p["symbol"]] = int(p["conviction"]) if isinstance(p.get("conviction"), (int, float)) else None
        p["role"] = p.get("role") or role_by.get(p["symbol"], "satellite")
        # weighting base = the AI's suggested target weight (fall back to conviction); caps applied below
        p["conviction"] = float(p.get("target_weight_pct") or p.get("conviction") or 1)
    # de-dupe by symbol (keep the larger weight), clamp to MAX_NAMES
    dedup: dict[str, dict] = {}
    for p in raw:
        s = p["symbol"]
        if s not in dedup or p["conviction"] > dedup[s]["conviction"]:
            dedup[s] = p
    picks = sorted(dedup.values(), key=lambda p: p["conviction"], reverse=True)[:MAX_NAMES]
    if not picks:
        logger.warning("theme %s: final basket empty after validation", theme.slug)
        return theme, []
    weighted = _compute_weights(picks)

    # provenance: link to an Opportunity row if we happen to already track the name
    opp_rows = (await db.execute(select(Opportunity).where(
        Opportunity.symbol.in_([w["symbol"] for w in weighted])))).scalars().all()
    opp_by = {o.symbol.upper(): o for o in opp_rows}
    rationale_by = {p["symbol"]: p.get("rationale") for p in picks}

    # replace the basket
    old = (await db.execute(select(ThemeConstituent).where(ThemeConstituent.theme_id == theme.id))).scalars().all()
    for c in old:
        await db.delete(c)
    await db.flush()
    made: list[ThemeConstituent] = []
    for w in weighted:
        opp = opp_by.get(w["symbol"])
        c = ThemeConstituent(theme_id=theme.id, symbol=w["symbol"], target_weight=w["target_weight"],
                             role=w["role"], conviction=conv_by.get(w["symbol"]), rationale=rationale_by.get(w["symbol"]),
                             opportunity_id=opp.id if opp else None, status="active")
        db.add(c)
        made.append(c)
    theme.target_version = (theme.target_version or 0) + 1
    theme.updated_at = datetime.utcnow()
    # snapshot entry prices so performance is measured from when the basket was set
    baseline = await _entry_prices([w["symbol"] for w in weighted])
    risk = await asyncio.to_thread(_managed_downside, made)
    theme.meta = {**(theme.meta or {}), "baseline_prices": baseline,
                  "baseline_at": datetime.utcnow().isoformat(),
                  "pick_note": ("Considered but excluded — our data providers can't quote: "
                                + ", ".join(dropped)) if dropped else None,
                  **({"risk": risk} if risk else {})}
    await db.flush()
    await log_event(db, theme.id, "rebalance", f"Basket set — {len(made)} names (v{theme.target_version}).",
                    {"weights": [{"symbol": w["symbol"], "weight": w["target_weight"], "role": w["role"]} for w in weighted]})
    return theme, made


async def _entry_prices(symbols: list[str]) -> dict:
    """Current prices for the basket, used as the performance baseline. Best-effort."""
    if not symbols:
        return {}
    try:
        from app.services.market_data import get_batch_quotes
        quotes = await asyncio.to_thread(get_batch_quotes, symbols)
        return {q["symbol"]: q["price"] for q in quotes if q.get("price")}
    except Exception as e:
        logger.warning("theme baseline prices failed: %s", e)
        return {}


async def run_pick_constituents(theme_id, hint: str | None = None, *_ignore) -> None:
    """Background entrypoint for basket selection. Own session; never raises."""
    from app.database import async_session
    async with async_session() as db:
        theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
        if not theme:
            return
        theme.meta = {**(theme.meta or {}), "basket_status": "picking"}
        await db.flush()
        try:
            await pick_constituents(db, theme, hint=hint)
            theme.meta = {**(theme.meta or {}), "basket_status": "ready", "report_status": "generating"}
            await db.commit()
        except Exception as e:
            logger.exception("theme basket pick failed for %s: %s", theme_id, e)
            await db.rollback()
            theme.meta = {**(theme.meta or {}), "basket_status": "error", "basket_error": str(e)[:200]}
            await db.commit()
            return
        # chain the research report so a freshly-picked theme comes with its report
        try:
            await build_report(db, theme)
            theme.meta = {**(theme.meta or {}), "report_status": "ready"}
            await db.commit()
        except Exception as e:
            logger.exception("theme report (post-pick) failed for %s: %s", theme_id, e)
            await db.rollback()
            theme.meta = {**(theme.meta or {}), "report_status": "error"}
            await db.commit()


# ── status transitions ───────────────────────────────────────────────────────

_STATUSES = {"draft", "live", "weakening", "breaking", "closed"}


async def set_status(db, theme: Theme, status: str) -> Theme:
    status = (status or "").lower()
    if status not in _STATUSES:
        raise ValueError(f"invalid status {status!r}")
    prev, theme.status = theme.status, status
    theme.updated_at = datetime.utcnow()
    await db.flush()
    await log_event(db, theme.id, "thesis_update", f"Status {prev} → {status}.", {"from": prev, "to": status})
    return theme


# ── M1: monitoring — daily re-thesis, conviction/health, state machine, perf ──

# The published-theme lifecycle the daily monitor drives (draft/closed are excluded —
# publishing and retiring are admin actions, not automatic).
_ACTIVE_STATUSES = ("live", "weakening", "breaking")
# Conviction bands. A theme is "breaking" (→ M2 unwind) below BREAK; "weakening" below WEAKEN.
CONVICTION_BREAK = 35
CONVICTION_WEAKEN = 55


def _resolve_state(prev_status: str, conviction: int, verdict: str) -> tuple[str, str]:
    """(status, health) from the latest conviction + the LLM's verdict. Recovery is allowed:
    a weakening/breaking theme whose conviction returns climbs back toward live."""
    broken = verdict == "broken" or conviction < CONVICTION_BREAK
    weak = verdict == "weakening" or conviction < CONVICTION_WEAKEN
    if broken:
        return "breaking", "breaking"
    if weak:
        return "weakening", "watching"
    return "live", "strong"          # healthy → live (recovers a previously weak/broken theme)


_REASSESS_TOOL = {
    "name": "theme_reassessment",
    "description": "Re-score the theme's conviction and flag tripping falsifiers, given the freshest data, headlines and earnings.",
    "input_schema": {"type": "object", "properties": {
        "conviction": {"type": "integer", "description": "0–100 updated conviction given the latest evidence"},
        "verdict": {"type": "string", "enum": ["intact", "weakening", "broken"],
                    "description": "intact = thesis holds; weakening = real cracks; broken = a core falsifier has tripped"},
        "tripped": {"type": "array", "items": {"type": "string"},
                    "description": "labels of falsifiers now tripping (empty if none)"},
        "summary": {"type": "string", "description": "1–2 sentences: what changed and why conviction moved"}},
        "required": ["conviction", "verdict", "summary"]},
}

_REASSESS_SYSTEM = (
    "You are 'the Partner' MONITORING a live investment THEME. Re-score its conviction (0–100) against "
    "the freshest evidence: use get_stock_data for any hard number on a constituent, and web_search for "
    "qualitative developments (industry data, guidance, catalysts). Weigh the theme's own falsifiers — flag "
    "any that are genuinely tripping. Be steady, not trigger-happy: a single soft headline must NOT break a "
    "multi-year thesis, but a real structural change — a core falsifier tripping, an earnings print that "
    "undercuts the narrative, a catalyst that failed — SHOULD cut conviction hard and can mark it broken. \n"
    "CRUCIAL — separate PROFIT-TAKING from thesis WEAKNESS. A price pullback AFTER a strong run-up, with "
    "fundamentals and the narrative still intact, is normal profit-taking — it is NOT weakness and is NOT a "
    "reason to cut conviction (a name up big that gives back some is healthy). Only cut conviction when the "
    "decline is driven by GENUINE DETERIORATION: falling fundamentals, cut guidance, a failed catalyst, a "
    "tripped falsifier, or a broken competitive position. Price softness alone — especially after gains — is "
    "not thesis weakness. Judge the BUSINESS, not the ticker's wiggles. "
    "Set verdict intact / weakening / broken accordingly. Call theme_reassessment.")


def _reassess_context(theme: Theme, constituents: list[ThemeConstituent],
                      headlines: dict, reporters: dict, perf_by: dict | None = None) -> str:
    perf_by = perf_by or {}
    fal = "\n".join(f"  - {f.get('label')} (breaks if: {f.get('breaks_if')})" for f in (theme.falsifiers or []))
    rows = []
    for c in constituents:
        bits = [f"{c.symbol} ({c.role}, {round((c.target_weight or 0) * 100)}%)"]
        p = perf_by.get(c.symbol) or {}
        if p.get("since_pct") is not None or p.get("day_pct") is not None:
            # run-up context so a healthy pullback isn't misread as weakness
            bits.append(f"since basket {p.get('since_pct')}% (today {p.get('day_pct')}%)")
        if c.symbol in reporters:
            s = reporters[c.symbol] or {}
            sp = s.get("eps_surprise_pct")
            bits.append(f"JUST REPORTED — EPS {s.get('eps_actual', '?')} vs est {s.get('eps_est', '?')}"
                        + (f" ({sp:+.0f}% surprise)" if isinstance(sp, (int, float)) else ""))
        heads = headlines.get(c.symbol) or []
        if heads:
            bits.append("news: " + " | ".join(heads[:3]))
        rows.append("  - " + "; ".join(bits))
    return (f"THEME: {theme.title}\nNARRATIVE: {theme.narrative}\nHERO STAT: {theme.hero_stat or '—'}\n"
            f"CURRENT CONVICTION: {theme.conviction}\n\nFALSIFIERS:\n{fal or '  (none)'}\n\n"
            f"CONSTITUENTS + FRESH SIGNALS (a big 'since basket' gain with only a small dip = profit-taking, "
            f"not weakness):\n" + "\n".join(rows) +
            "\n\nVerify the key numbers with get_stock_data, distinguish profit-taking from real "
            "deterioration, then re-score.")


_DEEP_SUFFIX = (
    "\n\nThis is a WEEKLY DEEP RE-VALIDATION — don't just react to the last day. Re-examine the WHOLE "
    "narrative from scratch: is the multi-year thesis still the best read of the world? Search broadly "
    "for anything that would confirm or overturn it (industry cycle, competitive shifts, demand signals, "
    "the setup for each anchor). Be willing to meaningfully move conviction up or down.")


async def _reassess(theme: Theme, constituents: list[ThemeConstituent],
                    headlines: dict, reporters: dict, perf_by: dict | None = None, deep: bool = False) -> dict | None:
    user = _reassess_context(theme, constituents, headlines, reporters, perf_by)
    system = _REASSESS_SYSTEM + (_DEEP_SUFFIX if deep else "")
    iters = 7 if deep else 5
    tokens = 2000 if deep else 1600
    try:
        out = await asyncio.to_thread(research._llm_toolloop, system, user, _REASSESS_TOOL, True, tokens, iters)
        if out is not None:
            return out
    except Exception as e:
        logger.info("theme reassess: web-search unavailable (%s) — data-only", e)
    try:
        out = await asyncio.to_thread(research._llm_toolloop, system, user, _REASSESS_TOOL, False, tokens, max(4, iters - 1))
        if out is not None:
            return out
    except Exception as e:
        logger.warning("theme reassess data-loop failed: %s", e)
    return await asyncio.to_thread(research._llm_json, system, user, _REASSESS_TOOL, tokens)


def _perf_snapshot(theme: Theme, constituents: list[ThemeConstituent], quotes: list[dict]) -> dict:
    """Target-weight-weighted basket return: since the basket was set (vs baseline) and today."""
    baseline = (theme.meta or {}).get("baseline_prices") or {}
    qmap = {q["symbol"]: q for q in quotes}
    since = day = wsum = 0.0
    have_baseline = False
    per = []
    for c in constituents:
        q = qmap.get(c.symbol)
        if not q or not q.get("price"):
            continue
        w = c.target_weight or 0.0
        wsum += w
        px = q["price"]
        b = baseline.get(c.symbol)
        r = (px / b - 1.0) if b else None
        dc = q.get("change_pct")
        if r is not None:
            since += w * r
            have_baseline = True
        if dc is not None:
            day += w * (dc / 100.0)
        per.append({"symbol": c.symbol, "since_pct": round(r * 100, 2) if r is not None else None,
                    "day_pct": round(dc, 2) if dc is not None else None})
    if wsum > 0:
        since /= wsum
        day /= wsum
    return {"since_inception_pct": round(since * 100, 2) if have_baseline else None,
            "day_pct": round(day * 100, 2), "updated_at": datetime.utcnow().isoformat(), "per_name": per}


# Because we EXIT on weakness (not a full break), the realized loss is roughly the adverse
# move that unfolds before we act — on the order of one monthly move of the basket. K_EXIT
# scales the basket's monthly volatility into that "downside if we exit" estimate.
_K_EXIT = 1.3          # ~1.3 monthly σ before our exit discipline kicks in
_K_UNMANAGED = 2.6     # rough "if nobody managed it" reference, for contrast


def _managed_downside(constituents: list["ThemeConstituent"]) -> dict | None:
    """Estimate the % of capital at risk IF the thesis weakens and we exit early. Built from
    the basket's own recent volatility (weighted daily returns → monthly σ, which captures the
    real correlation inside a themed basket), then scaled by our early-exit discipline. Network
    (price history) — call inside a worker thread. None if there isn't enough history."""
    from app.services.agent.trend import _fetch_closes
    series: list[tuple[float, list[float]]] = []      # (weight, daily log-returns)
    for c in constituents:
        try:
            closes = _fetch_closes(c.symbol)
        except Exception:
            continue
        closes = (closes or [])[-90:]
        if len(closes) < 30:
            continue
        rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
        if len(rets) >= 20:
            series.append((c.target_weight or 0.0, rets))
    if not series:
        return None
    wsum = sum(w for w, _ in series) or 1.0
    minlen = min(len(r) for _, r in series)
    # weighted basket daily-return series (aligned to the most-recent minlen days)
    basket = []
    for i in range(minlen):
        r = sum(w * rets[len(rets) - minlen + i] for w, rets in series) / wsum
        basket.append(r)
    mean = sum(basket) / len(basket)
    var = sum((r - mean) ** 2 for r in basket) / max(1, len(basket) - 1)
    sigma_month = (var ** 0.5) * (21 ** 0.5)          # daily σ → ~monthly σ (21 trading days)
    managed = max(0.03, min(0.25, _K_EXIT * sigma_month))
    unmanaged = min(0.65, _K_UNMANAGED * sigma_month)
    return {"managed_downside_pct": round(managed * 100, 1),
            "unmanaged_ref_pct": round(unmanaged * 100, 1),
            "monthly_vol_pct": round(sigma_month * 100, 1),
            "n_names": len(series),
            "basis": "basket volatility (last ~90d) scaled by our early-exit discipline",
            "computed_at": datetime.utcnow().isoformat()}


# ── research report: AI-written analyst narrative + our chart data ────────────

def _basket_history(constituents: list["ThemeConstituent"], days: int = 180) -> dict:
    """A weighted basket index (normalized to 100 at the window start) from constituent daily
    closes — the data behind the performance chart. Network; call in a worker thread."""
    from app.services.agent.trend import _fetch_closes
    series = []
    for c in constituents:
        try:
            closes = _fetch_closes(c.symbol)
        except Exception:
            continue
        closes = (closes or [])[-days:]
        if len(closes) >= 30:
            series.append((c.target_weight or 0.0, closes))
    if not series:
        return {}
    wsum = sum(w for w, _ in series) or 1.0
    minlen = min(len(cl) for _, cl in series)
    values = []
    for i in range(minlen):
        v = 0.0
        for w, cl in series:
            base = cl[len(cl) - minlen]
            if base > 0:
                v += w * (cl[len(cl) - minlen + i] / base)
        values.append(round(v / wsum * 100, 2))
    return {"values": values, "points": len(values)}


_REPORT_TOOL = {
    "name": "theme_report",
    "description": "A professional equity-research report for the theme.",
    "input_schema": {"type": "object", "properties": {
        "summary": {"type": "string", "description": "2–4 sentence executive summary of the investment case"},
        "key_takeaways": {"type": "array", "items": {"type": "string"}, "description": "3–5 punchy takeaway bullets"},
        "sections": {
            "type": "array", "description": "5–7 report sections, in order",
            "items": {"type": "object", "properties": {
                "heading": {"type": "string", "description": "section title, e.g. 'Market Backdrop — Why Now'"},
                "body": {"type": "string", "description": "2–4 paragraphs; concise markdown allowed (bold, bullets, sub-headers). Cite specific numbers."}},
                "required": ["heading", "body"]}}},
        "required": ["summary", "key_takeaways", "sections"]},
}

_REPORT_SYSTEM = (
    "You are a senior equity-research analyst writing an institutional research report for an investment "
    "THEME (a curated basket of stocks). Use web_search for market/industry data (TAM, growth, cycle, "
    "competitive dynamics, catalysts) and get_stock_data for any hard number on a constituent. Write it like "
    "a real research report, in this order: an Executive Summary, then sections covering — the Market & "
    "Industry Backdrop (why now), the Structural Drivers / Bull Case, Portfolio Construction (how the basket "
    "is built and why these names and weights), Constituent Highlights (the key holdings, grounded in their "
    "numbers), Valuation & Upside, Risks & Mitigants, and Catalysts to Watch. Be specific and quantitative, "
    "professional and balanced but constructive. Ground every claim you can in the provided metrics or "
    "web_search — cite real figures. Do your research FIRST (web_search + get_stock_data), then call "
    "theme_report ONCE at the end. The `sections` array is the heart of the report — it MUST contain 5–7 "
    "FULL sections, each 2–4 substantive paragraphs; never return an empty or one-line sections list.")


async def build_report(db, theme: Theme) -> dict | None:
    """Generate the analyst report: AI-written sections (web_search + our metrics) plus the chart
    data we compute from our own numbers. Stores it on theme.meta['report']."""
    cons = (await db.execute(select(ThemeConstituent).where(
        ThemeConstituent.theme_id == theme.id, ThemeConstituent.status == "active")
        .order_by(ThemeConstituent.target_weight.desc()))).scalars().all()
    if not cons:
        return None
    enriched = await asyncio.to_thread(_enrich, [c.symbol for c in cons])
    emap = {d["symbol"].upper(): d for d in enriched}

    user = (f"THEME: {theme.title}\nNARRATIVE: {theme.narrative}\nHERO STAT: {theme.hero_stat or '—'}\n"
            f"OUR CONVICTION: {theme.conviction}/100\n\nDOWNSIDE TRIGGERS (falsifiers):\n"
            + "\n".join(f"  - {f.get('label')}: {f.get('breaks_if')}" for f in (theme.falsifiers or []))
            + "\n\nTHE BASKET (with OUR metrics):\n"
            + "\n".join("  - " + _metrics_line(emap.get(c.symbol.upper(), {"symbol": c.symbol}))
                        + f" | role {c.role} | weight {round((c.target_weight or 0)*100)}%"
                        + (f" | note: {c.rationale}" if c.rationale else "") for c in cons)
            + "\n\nWrite the full institutional research report for this theme.")
    async def _gen():
        try:
            o = await asyncio.to_thread(research._llm_toolloop, _REPORT_SYSTEM, user, _REPORT_TOOL, True, 8000, 6)
            if o is not None:
                return o
        except Exception as e:
            logger.info("theme report: web-search unavailable (%s) — data-only", e)
        try:
            o = await asyncio.to_thread(research._llm_toolloop, _REPORT_SYSTEM, user, _REPORT_TOOL, False, 8000, 5)
            if o is not None:
                return o
        except Exception as e:
            logger.warning("theme report data-loop failed: %s", e)
        return await asyncio.to_thread(research._llm_json, _REPORT_SYSTEM, user, _REPORT_TOOL, 8000)

    # Retry if the model returns without real sections (Sonnet-5 sometimes calls the tool early/short).
    out = {}
    for attempt in range(3):
        out = await _gen() or {}
        if out.get("sections"):
            break
        logger.info("theme report %s: empty sections (attempt %d) — retrying", theme.slug, attempt + 1)

    history = await asyncio.to_thread(_basket_history, cons)

    def _cm(c: ThemeConstituent) -> dict:
        d = emap.get(c.symbol.upper(), {})
        f = d.get("fundamentals") or {}
        return {"symbol": c.symbol, "role": c.role, "weight": round(c.target_weight or 0, 4),
                "rationale": c.rationale, "price": d.get("price"),
                "margin_of_safety_pct": d.get("margin_of_safety_pct"), "trend": d.get("trend"),
                "rev_growth": f.get("revenue_growth"), "roe": f.get("return_on_equity"),
                "op_margin": f.get("operating_margins"), "forward_pe": f.get("forward_pe"), "pe": f.get("pe_ratio")}

    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": out.get("summary") or "",
        "key_takeaways": [t for t in (out.get("key_takeaways") or []) if isinstance(t, str)],
        "sections": [s for s in (out.get("sections") or []) if isinstance(s, dict) and s.get("heading")],
        "charts": {
            "basket_history": history,
            "allocation": [{"symbol": c.symbol, "weight": round(c.target_weight or 0, 4), "role": c.role} for c in cons],
            "constituents": [_cm(c) for c in cons],
        },
    }
    theme.meta = {**(theme.meta or {}), "report": report}
    await db.flush()
    await log_event(db, theme.id, "thesis_update", "Research report generated.", {"sections": len(report["sections"])})
    return report


async def run_generate_report(theme_id, *_ignore) -> None:
    """Background entrypoint: generate the analyst report. Own session; never raises."""
    from app.database import async_session
    async with async_session() as db:
        theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
        if not theme:
            return
        theme.meta = {**(theme.meta or {}), "report_status": "generating"}
        await db.flush()
        try:
            await build_report(db, theme)
            theme.meta = {**(theme.meta or {}), "report_status": "ready"}
            await db.commit()
        except Exception as e:
            logger.exception("theme report failed for %s: %s", theme_id, e)
            await db.rollback()
            theme.meta = {**(theme.meta or {}), "report_status": "error"}
            await db.commit()


async def monitor_theme(db, theme: Theme, allow_status_change: bool = True, deep: bool = False) -> dict:
    """Re-thesis one theme: gather fresh signals, re-score conviction, drive the state
    machine, refresh performance, and log the change. `deep` runs the weekly full
    narrative re-validation. Returns a small summary dict."""
    cons = (await db.execute(select(ThemeConstituent).where(
        ThemeConstituent.theme_id == theme.id, ThemeConstituent.status == "active")
        .order_by(ThemeConstituent.target_weight.desc()))).scalars().all()
    syms = [c.symbol for c in cons]

    # fresh signals: quotes (perf), headlines (news), earnings (who just reported)
    quotes, headlines, reporters = [], {}, {}
    if syms:
        try:
            from app.services.market_data import get_batch_quotes
            quotes = await asyncio.to_thread(get_batch_quotes, syms)
        except Exception as e:
            logger.warning("theme monitor quotes failed: %s", e)
        cutoff = datetime.utcnow() - timedelta(days=2)
        from app.services.agent.central import _fresh_headlines
        for s in syms:
            try:
                heads = await asyncio.to_thread(_fresh_headlines, s, cutoff)
                if heads:
                    headlines[s] = heads
            except Exception:
                pass
        try:
            from app.services.agent import earnings
            allrep = await earnings.recent_reporters(db, days=4)
            reporters = {s: allrep[s] for s in syms if s in allrep}
        except Exception as e:
            logger.info("theme monitor earnings lookup skipped: %s", e)

    # per-name run-up context (since basket + today) so the monitor can tell a healthy
    # pullback (profit-taking) from genuine thesis deterioration
    baseline = (theme.meta or {}).get("baseline_prices") or {}
    qmap = {q["symbol"]: q for q in quotes}
    perf_by = {}
    for c in cons:
        q = qmap.get(c.symbol)
        if not q:
            continue
        px, b, dc = q.get("price"), baseline.get(c.symbol), q.get("change_pct")
        perf_by[c.symbol] = {"since_pct": round((px / b - 1) * 100, 1) if (px and b) else None,
                             "day_pct": round(dc, 1) if dc is not None else None}

    prev_conv, prev_status = theme.conviction, theme.status
    out = await _reassess(theme, cons, headlines, reporters, perf_by=perf_by, deep=deep) if syms else None
    if out:
        conviction = max(0, min(100, int(out.get("conviction") or prev_conv)))
        verdict = (out.get("verdict") or "intact").lower()
        summary = out.get("summary") or ""
        tripped = out.get("tripped") or []
    else:                                     # no basket or LLM unavailable — perf-only refresh
        conviction, verdict, summary, tripped = prev_conv, "intact", "", []

    if allow_status_change and prev_status in _ACTIVE_STATUSES:
        new_status, new_health = _resolve_state(prev_status, conviction, verdict)
    else:                                     # draft / closed / manual: refresh numbers, keep status
        new_status = prev_status
        new_health = _resolve_state("live", conviction, verdict)[1]

    theme.conviction = conviction
    theme.health = new_health
    theme.status = new_status
    theme.perf_snapshot = _perf_snapshot(theme, cons, quotes)
    risk = await asyncio.to_thread(_managed_downside, cons)
    if risk:
        theme.meta = {**(theme.meta or {}), "risk": risk}
    theme.last_thesis_run_at = datetime.utcnow()
    theme.updated_at = datetime.utcnow()
    await db.flush()

    delta = conviction - (prev_conv or 0)
    reported = [s for s in reporters]
    detail = {"conviction": conviction, "delta": delta, "verdict": verdict,
              "tripped": tripped, "reported": reported}
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "→")
    kind = "earnings" if reported else "thesis_update"
    prefix = "Weekly deep review — " if deep else ""
    await log_event(db, theme.id, kind,
                    f"{prefix}Conviction {prev_conv}{arrow}{conviction}. {summary}".strip(), detail)
    if new_status != prev_status:
        if new_status == "breaking":
            await log_event(db, theme.id, "break",
                            f"Thesis BROKE — {summary or 'conviction collapsed'}.",
                            {"tripped": tripped, "conviction": conviction})
            await notify_theme_users(db, theme.id, "system", f"🧩 “{theme.title}” — thesis broke",
                                     "We're exiting your position and returning the cash to your account.")
        elif new_status == "weakening":
            await log_event(db, theme.id, "weaken", f"Thesis weakening — {summary}.", {"conviction": conviction})
            await notify_theme_users(db, theme.id, "system", f"⚠️ “{theme.title}” downgraded to Watching",
                                     summary or f"Conviction slipped to {conviction}.")
        elif new_status == "live":
            await log_event(db, theme.id, "thesis_update", f"Thesis recovered → live ({conviction}).", {"conviction": conviction})
            await notify_theme_users(db, theme.id, "system", f"“{theme.title}” recovered → Live",
                                     f"Conviction back up to {conviction}.")
    return {"slug": theme.slug, "conviction": conviction, "delta": delta,
            "status": new_status, "verdict": verdict, "tripped": tripped}


async def monitor(db=None) -> dict:
    """Daily monitoring pass over every published theme. Own session if none given."""
    if db is None:
        from app.database import async_session
        async with async_session() as s:
            return await monitor(s)
    themes = (await db.execute(select(Theme).where(Theme.status.in_(_ACTIVE_STATUSES)))).scalars().all()
    results = []
    for t in themes:
        try:
            results.append(await monitor_theme(db, t, allow_status_change=True))
            await db.commit()
        except Exception as e:
            logger.exception("theme monitor failed for %s: %s", t.slug, e)
            await db.rollback()
    logger.info("theme monitor: reassessed %d themes", len(results))
    return {"monitored": len(results), "results": results}


async def weekly_revalidate(db=None) -> dict:
    """Weekly DEEP re-validation — re-examine each live theme's whole narrative from
    scratch (heavier web search), beyond the daily light monitor. Own session if none."""
    if db is None:
        from app.database import async_session
        async with async_session() as s:
            return await weekly_revalidate(s)
    themes = (await db.execute(select(Theme).where(Theme.status.in_(_ACTIVE_STATUSES)))).scalars().all()
    n = 0
    for t in themes:
        try:
            await monitor_theme(db, t, allow_status_change=True, deep=True)
            await db.commit()
            n += 1
        except Exception as e:
            logger.exception("weekly revalidate failed for %s: %s", t.slug, e)
            await db.rollback()
    logger.info("theme weekly deep re-validation: %d themes", n)
    return {"revalidated": n}


async def run_monitor_one(theme_id, *_ignore) -> None:
    """Background entrypoint: re-thesis a single theme now (admin 'Refresh'). Own session."""
    from app.database import async_session
    async with async_session() as db:
        theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
        if not theme:
            return
        theme.meta = {**(theme.meta or {}), "monitor_status": "running"}
        await db.flush()
        try:
            await monitor_theme(db, theme, allow_status_change=(theme.status in _ACTIVE_STATUSES))
            theme.meta = {**(theme.meta or {}), "monitor_status": "ready"}
            await db.commit()
        except Exception as e:
            logger.exception("theme manual refresh failed for %s: %s", theme_id, e)
            await db.rollback()
            theme.meta = {**(theme.meta or {}), "monitor_status": "error"}
            await db.commit()


# ── serializers ───────────────────────────────────────────────────────────────

def constituent_dict(c: ThemeConstituent) -> dict:
    return {"symbol": c.symbol, "target_weight": c.target_weight, "role": c.role,
            "conviction": c.conviction, "rationale": c.rationale, "status": c.status}


def event_dict(e: ThemeEvent) -> dict:
    return {"kind": e.kind, "summary": e.summary, "detail": e.detail,
            "created_at": e.created_at.isoformat() if e.created_at else None}


def theme_dict(theme: Theme, constituents=None, events=None, n_allocations: int | None = None) -> dict:
    d = {
        "id": str(theme.id), "slug": theme.slug, "title": theme.title, "tags": theme.tags or [],
        "narrative": theme.narrative, "hero_stat": theme.hero_stat, "status": theme.status,
        "conviction": theme.conviction, "health": theme.health,
        "falsifiers": theme.falsifiers or [], "red_team": theme.red_team or [],
        "target_version": theme.target_version, "perf_snapshot": theme.perf_snapshot,
        "risk": (theme.meta or {}).get("risk"),
        "survives_red_team": (theme.meta or {}).get("survives_red_team"),
        "gen_status": (theme.meta or {}).get("status"),          # generating | ready | error
        "basket_status": (theme.meta or {}).get("basket_status"),  # picking | ready | error
        "pick_note": (theme.meta or {}).get("pick_note"),          # names dropped for lack of price
        "monitor_status": (theme.meta or {}).get("monitor_status"),  # running | ready | error
        "report_status": (theme.meta or {}).get("report_status"),  # generating | ready | error
        "report": (theme.meta or {}).get("report"),
        "created_by": theme.created_by,
        "created_at": theme.created_at.isoformat() if theme.created_at else None,
        "updated_at": theme.updated_at.isoformat() if theme.updated_at else None,
        "last_thesis_run_at": theme.last_thesis_run_at.isoformat() if theme.last_thesis_run_at else None,
    }
    if constituents is not None:
        d["constituents"] = [constituent_dict(c) for c in constituents]
    if events is not None:
        d["events"] = [event_dict(e) for e in events]
    if n_allocations is not None:
        d["n_allocations"] = n_allocations
    return d
