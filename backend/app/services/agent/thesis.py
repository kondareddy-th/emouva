"""The Living Thesis — Phase 5.

On entry the harness writes the reason to own a name, ARMS machine-checkable
downward triggers (falsifiers), and runs a 4-lens adversarial red-team (a buy
proceeds only if it survives ≥3). Daily, each thesis's falsifiers are evaluated
against fresh data; the moment one trips the agent reviews whether the name still
earns its place and — if the thesis broke — proposes the exit through the normal
gate (never an auto-sell) and distills the lesson into the Latticework.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select

from app.models.db import Thesis, AgentOrder, AgentPrinciple, AgentMandate
from app.services.market_data import get_company_info
from app.services import fair_value as fv_svc
from app.services.agent import engine, research

logger = logging.getLogger(__name__)

# Falsifier metrics the LLM may use — each is machine-checkable from one source.
FUNDAMENTAL_METRICS = [
    "pe_ratio", "forward_pe", "peg_ratio", "gross_margins", "operating_margins",
    "profit_margins", "return_on_equity", "return_on_assets", "debt_to_equity",
    "current_ratio", "revenue_growth", "earnings_growth",
]
DERIVED_METRICS = ["margin_of_safety_pct", "price"]
ALLOWED_METRICS = FUNDAMENTAL_METRICS + DERIVED_METRICS

# Fundamentals don't change intraday. A fundamental falsifier that trips within the
# first few days of arming means its THRESHOLD was mis-set (sitting on the wrong side
# of today's value) — not that the business broke. Such triggers are muted for a grace
# window so a fresh thesis can never force a same-day churn exit. Price/valuation
# triggers (margin_of_safety_pct, price) are NOT graced — a falling knife is real risk.
_FALSIFIER_GRACE_DAYS = 3
_GRACE_METRICS = set(FUNDAMENTAL_METRICS)   # slow-moving; exempt price & margin-of-safety


def _metric_values(symbol: str, fv: dict | None = None) -> dict:
    info = get_company_info(symbol) or {}
    vals = {k: info.get(k) for k in FUNDAMENTAL_METRICS}
    fv = fv or fv_svc.fair_value(symbol)
    vals["margin_of_safety_pct"] = fv.get("margin_pct")
    vals["price"] = fv.get("current_price")
    return vals


def _cmp(v: float, comparator: str, thr: float) -> bool:
    if comparator == "<":  return v < thr
    if comparator == ">":  return v > thr
    if comparator == "<=": return v <= thr
    if comparator == ">=": return v >= thr
    return False


_THESIS_TOOL = {
    "name": "living_thesis",
    "description": "The written thesis, its falsifiers (downward triggers), and the red-team it faced.",
    "input_schema": {
        "type": "object",
        "properties": {
            "thesis": {"type": "string", "description": "one paragraph: why own this business"},
            "falsifiers": {
                "type": "array", "description": "2–5 machine-checkable downward triggers",
                "items": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "enum": ALLOWED_METRICS},
                        "comparator": {"type": "string", "enum": ["<", ">", "<=", ">="]},
                        "threshold": {"type": "number"},
                        "source": {"type": "string"},
                        "label": {"type": "string", "description": "plain-language, e.g. 'gross margin falls below 35%'"},
                    },
                    "required": ["metric", "comparator", "threshold", "label"],
                },
            },
            "red_team": {
                "type": "array", "description": "exactly 4 bear lenses, each trying to kill the thesis",
                "items": {
                    "type": "object",
                    "properties": {
                        "lens": {"type": "string", "enum": ["accounting", "moat", "leverage", "disruption"]},
                        "attack": {"type": "string", "description": "the strongest bear case from this lens"},
                        "verdict": {"type": "string", "enum": ["survives", "kills"]},
                    },
                    "required": ["lens", "attack", "verdict"],
                },
            },
        },
        "required": ["thesis", "falsifiers", "red_team"],
    },
}


async def generate(symbol: str, fv: dict, principles_block: str) -> dict:
    """LLM: write the thesis, arm falsifiers (constrained metrics), run the 4-lens
    red-team. Returns the raw dict plus `survives` (≥3 lenses don't kill)."""
    vals = await asyncio.to_thread(_metric_values, symbol, fv)
    system = ("You are 'the Partner', a patient Munger-style value investor entering (or vetting) a position. "
              "Write the thesis, then ARM 2–5 falsifiers — machine-checkable downward triggers using ONLY the "
              "allowed metrics — that would each mean the reason to own it has broken. Then run a red-team of "
              "EXACTLY 4 lenses (accounting, moat, leverage, valuation); each states its strongest bear case and "
              "a verdict. Honor the Latticework. Call living_thesis.")
    user = (f"SYMBOL: {symbol}\nCURRENT METRICS: {vals}\n"
            f"FAIR VALUE: conservative ${fv.get('conservative')}, margin {fv.get('margin_pct')}%.\n\n"
            f"THE LATTICEWORK:\n{principles_block or '(none)'}\n\nWrite the Living Thesis.")
    out = await asyncio.to_thread(research._llm_json, system, user, _THESIS_TOOL, 3000, 0.0)
    if not out:
        return {"thesis": "", "falsifiers": [], "red_team": [], "survives": True, "stub": True}
    rt = [r for r in (out.get("red_team") or []) if isinstance(r, dict)]
    out["red_team"] = rt
    # survive only if we actually ran the red-team and ≥3 lenses didn't kill it
    out["survives"] = (len(rt) >= 3 and sum(1 for r in rt if r.get("verdict") == "survives") >= 3) if rt else True
    return out


async def arm(db, user_id, account: str, symbol: str, kind: str = "holding",
              order_id=None, principles_block: str | None = None) -> tuple[Thesis, bool]:
    """Persist a Living Thesis. REUSES the central analysis (thesis + falsifiers +
    red-team) when the symbol is in the shared directory — no per-account LLM call;
    only falls back to generating when there's no central analysis."""
    from app.models.db import Opportunity
    fv = await asyncio.to_thread(fv_svc.fair_value, symbol)
    o = (await db.execute(select(Opportunity).where(Opportunity.symbol == symbol.upper()))).scalar_one_or_none()
    if o and o.central_thesis and o.falsifiers:                     # reuse the shared reasoning
        rt = o.red_team or []
        gen = {"thesis": o.central_thesis, "falsifiers": o.falsifiers, "red_team": rt,
               "survives": len(rt) >= 3 and sum(1 for r in rt if r.get("verdict") == "survives") >= 3}
    else:
        principles_block = principles_block if principles_block is not None else await engine._render_principles(db, user_id)
        gen = await generate(symbol, fv, principles_block)
    # A thesis must never be born already-falsified. Drop any downside trigger whose
    # condition is ALREADY met by today's data (e.g. "operating_margins < 35%" armed on
    # a name whose margin is 27% — the threshold sits on the wrong side of reality). Left
    # in, it would trip on the next sweep and force a spurious same-day exit (churn).
    raw = gen.get("falsifiers") or []
    if raw:
        cur = await asyncio.to_thread(_metric_values, symbol, fv)
        kept, born_broken = [], []
        for f in raw:
            if not isinstance(f, dict):
                continue
            v = cur.get(f.get("metric")); thr = f.get("threshold")
            try:
                already = v is not None and thr is not None and _cmp(float(v), f.get("comparator", "<"), float(thr))
            except (TypeError, ValueError):
                already = False
            (born_broken if already else kept).append(f)
        if born_broken:
            logger.warning("thesis.arm %s: dropped %d already-tripped falsifier(s) at entry: %s",
                           symbol, len(born_broken), [b.get("label") or b.get("metric") for b in born_broken])
        gen["falsifiers"] = kept
    # replace any prior thesis for this (user, account, symbol)
    old = (await db.execute(select(Thesis).where(
        Thesis.user_id == user_id, Thesis.account == account, Thesis.symbol == symbol,
        Thesis.status.in_(("active", "flashed"))))).scalars().all()
    for o in old:
        o.status = "closed"
    t = Thesis(user_id=user_id, account=account, symbol=symbol, kind=kind,
               thesis_text=gen.get("thesis", ""), falsifiers=gen.get("falsifiers", []),
               red_team=gen.get("red_team", []), fv_snapshot=fv, order_id=order_id, status="active")
    db.add(t)
    await db.flush()
    return t, bool(gen.get("survives", True))


def evaluate(thesis: Thesis) -> list[dict]:
    """Which falsifiers are currently tripped (downside condition met).

    Fundamental triggers are muted for the first ``_FALSIFIER_GRACE_DAYS`` after
    arming: fundamentals don't move intraday, so an early fundamental trip means the
    threshold was mis-calibrated, not that the thesis broke — muting it prevents a
    same-day buy→sell churn. Price/valuation triggers fire immediately (real risk)."""
    vals = _metric_values(thesis.symbol, None)
    try:
        age_days = (datetime.utcnow() - thesis.created_at).total_seconds() / 86400.0
    except Exception:
        age_days = None
    in_grace = age_days is not None and age_days < _FALSIFIER_GRACE_DAYS
    tripped = []
    for f in (thesis.falsifiers or []):
        if not isinstance(f, dict):
            continue
        metric = f.get("metric")
        if in_grace and metric in _GRACE_METRICS:      # fundamental trigger, thesis still fresh — hold
            continue
        v = vals.get(metric)
        thr = f.get("threshold")
        if v is None or thr is None:
            continue
        try:
            if _cmp(float(v), f.get("comparator", "<"), float(thr)):
                tripped.append({**f, "current": v})
        except (TypeError, ValueError):
            continue
    return tripped


_REVIEW_TOOL = {
    "name": "thesis_review",
    "description": "Given a tripped falsifier, decide whether the position still earns its place.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {"type": "string", "enum": ["hold", "trim", "sell"]},
            "broken": {"type": "boolean", "description": "true if the core thesis has broken"},
            "rationale": {"type": "string"},
        },
        "required": ["verdict", "broken", "rationale"],
    },
}


async def daily_sweep(db, user_id, token: str | None = None) -> dict:
    """Evaluate every active thesis; on a tripped trigger, review it and — if the
    thesis broke — propose the exit through the gate (never auto-sell)."""
    m = (await db.execute(select(AgentMandate).where(AgentMandate.user_id == user_id))).scalar_one_or_none()
    theses = (await db.execute(select(Thesis).where(
        Thesis.user_id == user_id, Thesis.status.in_(("active", "flashed"))))).scalars().all()
    if not theses:
        return {"evaluated": 0}
    principles = await engine._render_principles(db, user_id)
    flashed = proposed = 0
    for t in theses:
        tripped = await asyncio.to_thread(evaluate, t)
        t.last_eval_at = engine._utcnow()
        if not tripped:
            if t.status == "flashed":
                t.status = "active"
            continue
        t.status = "flashed"
        t.tripped = tripped
        flashed += 1
        labels = "; ".join(f.get("label", f.get("metric")) for f in tripped)
        review = await asyncio.to_thread(
            research._llm_json,
            "You are the Partner reviewing a holding whose thesis just flashed a downward trigger. "
            "Decide honestly whether it still earns its place. Sell only if the core thesis has broken.",
            f"SYMBOL {t.symbol}\nTHESIS: {t.thesis_text}\nTRIPPED: {tripped}\nLATTICEWORK:\n{principles}",
            _REVIEW_TOOL, 900,
        )
        review = review or {"verdict": "hold", "broken": False, "rationale": "Review unavailable; holding."}
        if review.get("verdict") in ("sell", "trim"):
            qty = await _held_qty(db, t, token)
            if qty > 0:
                sell_qty = qty if review["verdict"] == "sell" else max(1.0, float(int(qty * 0.5)))
                price = (t.fv_snapshot or {}).get("current_price") or 0
                order = AgentOrder(
                    user_id=user_id, account=t.account, symbol=t.symbol, side="sell", qty=sell_qty,
                    order_type="market", est_price=price, est_notional=round(sell_qty * price, 2),
                    rationale=review.get("rationale", ""), status="pending_approval", approval_required=True,
                    expires_at=engine._utcnow() + timedelta(days=3), dry_run=(m.mode == "dry_run") if m else True,
                )
                db.add(order)
                await db.flush()
                t.order_id = order.id
                proposed += 1
                engine._ledger(db, user_id, t.account, None, "awaiting",
                               f"{t.symbol} — a downward trigger flashed; exit awaits your call",
                               f"{labels}. {review.get('rationale','')}", order_id=order.id,
                               meta={"symbol": t.symbol, "order_line": f"Sell {sell_qty:g} {t.symbol}", "thesis_break": True})
            if review.get("broken"):
                t.status = "broken"
                await _distill_lesson(db, user_id, t, labels, review.get("rationale", ""))
        else:
            engine._ledger(db, user_id, t.account, None, "check", f"{t.symbol} — trigger flashed, thesis intact",
                           f"{labels}. {review.get('rationale','')}", meta={"symbol": t.symbol})
    await db.commit()
    return {"evaluated": len(theses), "flashed": flashed, "proposed": proposed}


async def _held_qty(db, t: Thesis, token: str | None) -> float:
    try:
        if t.account.endswith("-paper"):
            from app.services import accounts as acct_svc
            pos = await acct_svc.get_positions(db, t.account)
        elif token:
            from app.services import robinhood_portfolio as rp
            pos = await rp.get_positions(token, t.account)
        else:
            return 0.0
        return next((float(p.get("shares") or 0) for p in pos if p.get("symbol") == t.symbol), 0.0)
    except Exception:
        return 0.0


async def _distill_lesson(db, user_id, t: Thesis, labels: str, rationale: str) -> None:
    """A broken thesis → a lesson → a proposed principle in the Latticework."""
    out = await asyncio.to_thread(
        research._llm_json,
        "A thesis just broke. Distill ONE durable, generalizable lesson (not about this ticker) to add to the "
        "user's investing Latticework so the mistake is structurally avoided next time.",
        f"SYMBOL {t.symbol}\nTHESIS: {t.thesis_text}\nWHAT BROKE: {labels}. {rationale}",
        {"name": "lesson", "input_schema": {"type": "object", "properties": {
            "principle": {"type": "string"}, "section": {"type": "string", "enum": ["Temperament", "Selection", "Sizing & Selling"]}},
            "required": ["principle", "section"]}}, 700)
    if out and out.get("principle"):
        n = (await db.execute(select(AgentPrinciple).where(AgentPrinciple.user_id == user_id))).scalars().all()
        db.add(AgentPrinciple(user_id=user_id, section=out.get("section", "Selection"), text=out["principle"],
                              meta=f"LESSON · {t.symbol} thesis broke", source="lesson", order_idx=len(n)))
        engine._ledger(db, user_id, t.account, None, "note", "A lesson entered the Latticework",
                       out["principle"], meta={"symbol": t.symbol})


def thesis_dict(t: Thesis) -> dict:
    return {"id": str(t.id), "symbol": t.symbol, "kind": t.kind, "status": t.status,
            "thesis": t.thesis_text, "falsifiers": t.falsifiers or [], "red_team": t.red_team or [],
            "tripped": t.tripped or [], "created_at": t.created_at.isoformat()}
