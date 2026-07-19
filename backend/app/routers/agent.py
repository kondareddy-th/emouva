"""Agentic trading API ("The Partner") — P1: mandate, ledger, positions, manual
tick, pause/resume, principles. Everything is per-user, scoped to the agentic
account. Orders are dry-run in P1 (recorded, never placed)."""
import logging

from fastapi import APIRouter, Depends, Body, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_optional_user
from app.services import robinhood_store as store, robinhood_portfolio as rp
from app.services import accounts as acct_svc
from app.services import agreements
from app.services.agent import engine, research
from app.models.db import (
    AgentMandate, AgentOrder, AgentTick, AgentLedgerEntry, AgentScreen, AgentPrinciple, Opportunity, Thesis,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/agent", tags=["agent"])

_DISCONNECTED = {"source": "disconnected"}


def _mandate_dict(m: AgentMandate, paper_account: str | None = None) -> dict:
    return {
        "source": "connected", "account": m.account,
        # execution target (the paper↔live toggle) + which accounts it maps to
        "mode": m.mode, "live_max_notional_usd": m.live_max_notional_usd,
        "margin_of_safety_pct": m.margin_of_safety_pct,
        "circle_include": m.circle_include or [], "circle_exclude": m.circle_exclude or [],
        "agentic_account": m.account, "paper_account": paper_account,
        # platform-level live gates (UI shows/greys the live toggle accordingly)
        "live_execution_enabled": settings.live_execution_enabled,
        "trading_halt": settings.trading_halt,
        "approval_threshold_usd": m.approval_threshold_usd,
        "per_trade_cap_usd": m.per_trade_cap_usd, "daily_spend_cap_usd": m.daily_spend_cap_usd,
        "max_position_pct": m.max_position_pct, "cash_floor_pct": m.cash_floor_pct,
        "sector_cap_pct": m.sector_cap_pct, "max_orders_week": m.max_orders_week,
        "catastrophic_stop_pct": m.catastrophic_stop_pct,
        "cadence": m.cadence, "paused": m.paused, "toggles": m.toggles or {},
        "strategy": {"name": m.strategy_name, "objective": m.strategy_objective, "rules": m.strategy_rules},
        "next_tick_at": m.next_tick_at.isoformat() if m.next_tick_at else None,
        "last_tick_at": m.last_tick_at.isoformat() if m.last_tick_at else None,
    }


async def _load_mandate(db: AsyncSession, user_id) -> AgentMandate | None:
    return (await db.execute(select(AgentMandate).where(AgentMandate.user_id == user_id))).scalar_one_or_none()


async def _paper_number(db, user_id) -> str | None:
    accts = await acct_svc.list_for_user(db, user_id)
    return accts[0].account_number if accts else None


async def _enrich_fv(positions: list[dict], mos_threshold: float) -> list[dict]:
    """Add conservative fair value + margin of safety + status to each position."""
    from app.services import fair_value as fv_svc
    syms = [p["symbol"] for p in positions if p.get("symbol")]
    if not syms:
        return positions
    fvs = await fv_svc.batch_fair_values(syms)
    for p in positions:
        f = fvs.get(p["symbol"], {})
        price = float(p.get("current_price") or f.get("current_price") or 0)
        cons = f.get("conservative")
        margin = round((cons - price) / cons * 100, 1) if (cons and price) else None
        p["fair_value"] = cons
        p["fv_base"], p["fv_low"], p["fv_high"] = f.get("base"), f.get("low"), f.get("high")
        p["fv_confident"] = f.get("confident", False)
        p["margin_pct"] = margin
        p["mos_status"] = fv_svc.mos_status(margin, mos_threshold, f.get("confident", False))
    return positions


async def _active_account(db, m: AgentMandate) -> str | None:
    """The account the agent view reflects for the current mode — paper mode →
    the paper account, else the fenced agentic account. This is what makes the
    paper↔live toggle change positions/ledger/orders across the whole UI."""
    if m.mode == "paper":
        return await _paper_number(db, m.user_id)
    return m.account


@router.get("/mandate")
async def get_mandate(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return _DISCONNECTED
    # Fast path: existing mandate is returned WITHOUT the Robinhood MCP round-trip
    # (self-heal/fencing happens on ticks + at order time). Only a first-time
    # mandate creation pays the MCP cost.
    m = await _load_mandate(db, user.id)
    if m is None:
        token = await store.get_valid_access_token(db, user.id)
        m = await engine.get_or_create_mandate(db, user.id, token)
    if not m:
        return _DISCONNECTED
    return _mandate_dict(m, paper_account=await _paper_number(db, user.id))


_EDITABLE = {"approval_threshold_usd", "per_trade_cap_usd", "daily_spend_cap_usd", "max_position_pct",
             "cash_floor_pct", "sector_cap_pct", "max_orders_week", "cadence", "toggles",
             "live_max_notional_usd", "margin_of_safety_pct", "circle_include", "circle_exclude",
             "catastrophic_stop_pct"}

_MODES = {"paper", "live", "dry_run"}


@router.post("/mode")
async def set_mode(payload: dict = Body(...), user=Depends(get_optional_user),
                   db: AsyncSession = Depends(get_db)):
    """Fast paper↔live toggle — which account the agent trades. Switching to live
    requires the platform live gate to be enabled and trading not halted."""
    if not user:
        raise HTTPException(401, "Authentication required")
    mode = (payload.get("mode") or "").strip()
    if mode not in _MODES:
        raise HTTPException(400, f"mode must be one of {sorted(_MODES)}")
    m = await _load_mandate(db, user.id)
    if not m:
        raise HTTPException(404, "No mandate")
    if mode == "live":
        if settings.trading_halt:
            raise HTTPException(409, "Live trading is halted platform-wide right now.")
        if not settings.live_execution_enabled:
            raise HTTPException(409, "Live execution isn't enabled yet (pending order-schema verification).")
        if not await agreements.has_accepted(db, user.id, agreements.LIVE_TC_DOC, agreements.LIVE_TC_VERSION):
            raise HTTPException(status_code=409, detail={
                "code": "tc_required", "version": agreements.LIVE_TC_VERSION,
                "message": "Accept the live-trading terms to continue."})
    m.mode = mode
    await db.commit()
    return {"mode": m.mode, "paper_account": await _paper_number(db, user.id), "agentic_account": m.account}


@router.get("/agreements/live_trading")
async def get_live_tc(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """The current live-trading T&C + whether this user has accepted this version."""
    if not user:
        return agreements.live_tc_payload(False)
    accepted = await agreements.has_accepted(db, user.id, agreements.LIVE_TC_DOC, agreements.LIVE_TC_VERSION)
    return agreements.live_tc_payload(accepted)


@router.post("/agreements")
async def post_agreement(payload: dict = Body(...), user=Depends(get_optional_user),
                         db: AsyncSession = Depends(get_db)):
    """Record a user's accept/reject of a versioned agreement (audit trail)."""
    if not user:
        raise HTTPException(401, "Authentication required")
    doc = payload.get("doc") or agreements.LIVE_TC_DOC
    version = payload.get("version") or agreements.LIVE_TC_VERSION
    accepted = payload.get("status") == "accepted" or bool(payload.get("accepted"))
    ag = await agreements.record(db, user.id, doc, version, "accepted" if accepted else "rejected")
    return {"doc": ag.doc, "version": ag.version, "status": ag.status, "at": ag.created_at.isoformat()}


@router.put("/mandate")
async def update_mandate(payload: dict = Body(...), user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    m = await _load_mandate(db, user.id)
    if not m:
        raise HTTPException(404, "No mandate — connect Robinhood first")
    for k, v in payload.items():
        if k in _EDITABLE:
            setattr(m, k, v)
    if payload.get("strategy"):
        s = payload["strategy"]
        if "name" in s: m.strategy_name = s["name"]
        if "objective" in s: m.strategy_objective = s["objective"]
        if "rules" in s: m.strategy_rules = s["rules"]
    if "cadence" in payload:  # reschedule the next wake to the new cadence
        m.next_tick_at = engine.next_tick_at(m.cadence)
    await db.commit()
    return _mandate_dict(m)


@router.post("/pause")
async def pause(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    m = await _load_mandate(db, user.id)
    if not m:
        raise HTTPException(404, "No mandate")
    m.paused = True
    # Kill-switch hardening: expire any orders awaiting approval so a queued order
    # can't be placed after the user hits pause.
    pending = (await db.execute(
        select(AgentOrder).where(AgentOrder.user_id == user.id, AgentOrder.status == "pending_approval")
    )).scalars().all()
    for o in pending:
        o.status = "expired"
        o.error_message = "cancelled — agent paused"
    await db.commit()
    return {"paused": True, "cancelled_pending": len(pending)}


@router.post("/resume")
async def resume(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    m = await _load_mandate(db, user.id)
    if not m:
        raise HTTPException(404, "No mandate")
    m.paused = False
    m.next_tick_at = engine.next_tick_at(m.cadence)
    await db.commit()
    return {"paused": False}


@router.get("/ledger")
async def ledger(limit: int = 40, type: str | None = None, user=Depends(get_optional_user),
                 db: AsyncSession = Depends(get_db)):
    if not user:
        return {"entries": [], "source": "disconnected"}
    q = select(AgentLedgerEntry).where(AgentLedgerEntry.user_id == user.id)
    m = await _load_mandate(db, user.id)   # scope to the active mode's account
    if m:
        acct = await _active_account(db, m)
        if acct:
            q = q.where(AgentLedgerEntry.account == acct)
    if type and type != "all":
        q = q.where(AgentLedgerEntry.type == type)
    rows = (await db.execute(q.order_by(AgentLedgerEntry.ts.desc()).limit(limit))).scalars().all()
    return {"entries": [{
        "id": str(e.id), "type": e.type, "ts": e.ts.isoformat() + "Z", "title": e.title, "body": e.body,
        "meta": e.meta, "order_id": str(e.order_id) if e.order_id else None,
        "screen_id": str(e.screen_id) if e.screen_id else None,
    } for e in rows], "source": "connected"}


@router.get("/memory")
async def memory(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """The active account's memory — long-term knowledge + this week's daily logs."""
    if not user:
        return {"long_term": None, "days": []}
    m = await _load_mandate(db, user.id)
    if not m:
        return {"long_term": None, "days": []}
    acct = await _active_account(db, m)
    from app.models.db import AgentMemory, AgentMemoryDay
    from datetime import datetime, timedelta
    lt = (await db.execute(select(AgentMemory).where(AgentMemory.account == acct))).scalar_one_or_none()
    since = datetime.utcnow().date() - timedelta(days=7)
    days = (await db.execute(select(AgentMemoryDay).where(
        AgentMemoryDay.account == acct, AgentMemoryDay.day >= since
    ).order_by(AgentMemoryDay.day.desc()))).scalars().all()
    return {
        "long_term": lt.long_term if lt else None,
        "updated_at": lt.updated_at.isoformat() + "Z" if (lt and lt.updated_at) else None,
        "days": [{"day": d.day.isoformat(), "summary": d.summary} for d in days],
    }


@router.get("/positions")
async def positions(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Positions for the account the agent is currently trading — paper mode →
    the paper book (our DB); live/dry_run → the fenced agentic account (Robinhood)."""
    if not user:
        return {"positions": [], "source": "disconnected"}
    m = await _load_mandate(db, user.id)
    if not m:
        return {"positions": [], "source": "disconnected"}
    acct = await _active_account(db, m)
    if not acct:
        return {"positions": [], "source": "disconnected", "mode": m.mode}
    try:
        if m.mode == "paper":
            pos = await acct_svc.get_positions(db, acct)
            summary = await acct_svc.get_summary(db, acct)
        else:
            token = await store.get_valid_access_token(db, user.id)
            if not token:
                return {"positions": [], "source": "disconnected", "mode": m.mode}
            pos = await rp.get_positions(token, acct)
            summary = await rp.get_summary(token, acct)
        pos = await _enrich_fv(pos, m.margin_of_safety_pct)
        return {"positions": pos, "summary": summary, "account": acct, "mode": m.mode, "source": "connected"}
    except Exception as e:
        logger.warning("agent positions failed: %s", e)
        return {"positions": [], "source": "disconnected", "mode": m.mode}


@router.get("/history")
async def history(limit: int = 50, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return {"orders": []}
    q = select(AgentOrder).where(AgentOrder.user_id == user.id, AgentOrder.status.in_(("placed", "filled")))
    m = await _load_mandate(db, user.id)
    if m and (acct := await _active_account(db, m)):
        q = q.where(AgentOrder.account == acct)
    rows = (await db.execute(q.order_by(AgentOrder.created_at.desc()).limit(limit))).scalars().all()
    return {"orders": [_order_dict(o) for o in rows]}


@router.get("/orders")
async def orders(limit: int = 50, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return {"orders": []}
    q = select(AgentOrder).where(AgentOrder.user_id == user.id)
    m = await _load_mandate(db, user.id)
    if m and (acct := await _active_account(db, m)):
        q = q.where(AgentOrder.account == acct)
    rows = (await db.execute(q.order_by(AgentOrder.created_at.desc()).limit(limit))).scalars().all()
    return {"orders": [_order_dict(o) for o in rows]}


def _order_dict(o: AgentOrder) -> dict:
    return {"id": str(o.id), "symbol": o.symbol, "side": o.side, "qty": o.qty, "order_type": o.order_type,
            "est_price": o.est_price, "est_notional": o.est_notional, "rationale": o.rationale,
            "confidence": o.confidence, "status": o.status, "approval_required": o.approval_required,
            "expires_at": o.expires_at.isoformat() if o.expires_at else None,
            "fill_price": o.fill_price, "dry_run": o.dry_run, "created_at": o.created_at.isoformat()}


@router.post("/orders/{order_id}/approve")
async def approve_order(order_id: str, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """P1: records the approval + ledger receipt (no real placement yet — P2)."""
    if not user:
        raise HTTPException(401, "Authentication required")
    o = await _load_order(db, user.id, order_id)
    if not o or o.status != "pending_approval":
        raise HTTPException(404, "No pending order")
    await engine.execute_approved(db, o)  # places under the configured mode (paper/alpaca/live); dry-run just logs
    return _order_dict(o)


@router.post("/orders/{order_id}/decline")
async def decline_order(order_id: str, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    o = await _load_order(db, user.id, order_id)
    if not o or o.status != "pending_approval":
        raise HTTPException(404, "No pending order")
    o.status = "declined"
    o.declined_at = engine._utcnow()
    engine._ledger(db, user.id, o.account, o.tick_id, "declined", "Declined by you",
                   f"You declined the {o.side} of {o.qty:g} {o.symbol}. Won't resubmit for 30 days.", order_id=o.id)
    await db.commit()
    return _order_dict(o)


async def _load_order(db, user_id, order_id) -> AgentOrder | None:
    import uuid
    try:
        oid = uuid.UUID(order_id)
    except (ValueError, TypeError):
        return None
    return (await db.execute(select(AgentOrder).where(AgentOrder.id == oid, AgentOrder.user_id == user_id))).scalar_one_or_none()


@router.get("/screens/{screen_id}")
async def screen(screen_id: str, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    import uuid
    try:
        sid = uuid.UUID(screen_id)
    except (ValueError, TypeError):
        raise HTTPException(404, "Not found")
    s = (await db.execute(select(AgentScreen).where(AgentScreen.id == sid, AgentScreen.user_id == user.id))).scalar_one_or_none()
    if not s:
        raise HTTPException(404, "Not found")
    return {"id": str(s.id), "universe_count": s.universe_count, "stages": s.stages,
            "survivor": s.survivor, "verdict": s.verdict, "created_at": s.created_at.isoformat()}


@router.get("/principles")
async def principles(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return {"principles": []}
    rows = (await db.execute(
        select(AgentPrinciple).where(AgentPrinciple.user_id == user.id).order_by(AgentPrinciple.order_idx)
    )).scalars().all()
    return {"principles": [_principle_dict(p) for p in rows]}


def _principle_dict(p: AgentPrinciple) -> dict:
    return {"id": str(p.id), "section": p.section, "text": p.text, "meta": p.meta,
            "source": p.source, "paused": p.paused, "version": p.version}


async def _load_principle(db, user_id, pid: str) -> AgentPrinciple | None:
    import uuid
    try:
        u = uuid.UUID(pid)
    except (ValueError, TypeError):
        return None
    return (await db.execute(select(AgentPrinciple).where(
        AgentPrinciple.id == u, AgentPrinciple.user_id == user_id))).scalar_one_or_none()


_SECTIONS = {"Temperament", "Selection", "Sizing & Selling"}


@router.post("/principles")
async def add_principle(payload: dict = Body(...), user=Depends(get_optional_user),
                        db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text required")
    section = payload.get("section") if payload.get("section") in _SECTIONS else "Selection"
    n = (await db.execute(select(AgentPrinciple).where(AgentPrinciple.user_id == user.id))).scalars().all()
    p = AgentPrinciple(user_id=user.id, section=section, text=text,
                       meta=payload.get("meta") or "YOURS · adopted today", source="yours",
                       order_idx=len(n))
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return _principle_dict(p)


@router.put("/principles/{pid}")
async def edit_principle(pid: str, payload: dict = Body(...), user=Depends(get_optional_user),
                         db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    p = await _load_principle(db, user.id, pid)
    if not p:
        raise HTTPException(404, "No such principle")
    if "text" in payload and payload["text"].strip():
        p.text = payload["text"].strip()
        p.version = (p.version or 1) + 1
    if payload.get("section") in _SECTIONS:
        p.section = payload["section"]
    if "paused" in payload:
        p.paused = bool(payload["paused"])
    await db.commit()
    return _principle_dict(p)


@router.post("/principles/{pid}/toggle")
async def toggle_principle(pid: str, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    p = await _load_principle(db, user.id, pid)
    if not p:
        raise HTTPException(404, "No such principle")
    p.paused = not p.paused
    await db.commit()
    return _principle_dict(p)


@router.delete("/principles/{pid}")
async def delete_principle(pid: str, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    p = await _load_principle(db, user.id, pid)
    if not p:
        raise HTTPException(404, "No such principle")
    await db.delete(p)
    await db.commit()
    return {"deleted": pid}


@router.post("/principles/backtest")
async def backtest_principle(payload: dict = Body(...), user=Depends(get_optional_user),
                             db: AsyncSession = Depends(get_db)):
    """Estimate a proposed principle's effect against recent orders (Sonnet 5)."""
    if not user:
        raise HTTPException(401, "Authentication required")
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text required")
    section = payload.get("section") if payload.get("section") in _SECTIONS else "Selection"
    return await research.backtest_principle(db, user.id, text, section)


# ── research: morning screen + distillation ────────────────────────────────

@router.post("/screens/run")
async def run_screen(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Run a morning screen over the watchlist (or default universe) → AgentScreen."""
    if not user:
        raise HTTPException(401, "Authentication required")
    m = await _load_mandate(db, user.id)
    account = (await _active_account(db, m) if m else None) or "—"
    token = await store.get_valid_access_token(db, user.id)
    mos = m.margin_of_safety_pct if m else 30.0
    s = await research.run_screen(db, user, token, account, mos_floor=mos, mandate=m)
    return {"id": str(s.id), "universe_count": s.universe_count, "stages": s.stages,
            "survivor": s.survivor, "verdict": s.verdict, "created_at": s.created_at.isoformat()}


@router.get("/screens")
async def list_screens(limit: int = 10, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return {"screens": []}
    rows = (await db.execute(
        select(AgentScreen).where(AgentScreen.user_id == user.id)
        .order_by(AgentScreen.created_at.desc()).limit(limit)
    )).scalars().all()
    return {"screens": [{"id": str(s.id), "universe_count": s.universe_count, "survivor": s.survivor,
                         "verdict": s.verdict, "stages": s.stages,
                         "created_at": s.created_at.isoformat()} for s in rows]}


@router.post("/research/distill")
async def research_distill(payload: dict = Body(...), user=Depends(get_optional_user)):
    """Distill a paper/idea (URL or pasted text) into a summary + candidate principle."""
    if not user:
        raise HTTPException(401, "Authentication required")
    source = (payload.get("source") or payload.get("url") or payload.get("text") or "").strip()
    if not source:
        raise HTTPException(400, "source (url or text) required")
    return await research.distill(source)


# ── living theses ───────────────────────────────────────────────────────────

@router.get("/theses")
async def theses(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Living theses for the active account (holdings + tracked)."""
    if not user:
        return {"theses": []}
    from app.services.agent import thesis as th
    m = await _load_mandate(db, user.id)
    acct = await _active_account(db, m) if m else None
    q = select(Thesis).where(Thesis.user_id == user.id, Thesis.status != "closed")
    if acct:
        q = q.where(Thesis.account == acct)
    rows = (await db.execute(q.order_by(Thesis.created_at.desc()))).scalars().all()
    return {"theses": [th.thesis_dict(t) for t in rows]}


@router.post("/theses/arm")
async def arm_thesis(payload: dict = Body(...), user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Write a Living Thesis for a symbol (falsifiers + red-team) — for a held name or on demand."""
    if not user:
        raise HTTPException(401, "Authentication required")
    from app.services.agent import thesis as th
    sym = (payload.get("symbol") or "").strip().upper()
    if not sym:
        raise HTTPException(400, "symbol required")
    m = await _load_mandate(db, user.id)
    acct = (await _active_account(db, m) if m else None) or "—"
    t, survives = await th.arm(db, user.id, acct, sym, kind="holding")
    await db.commit()
    return {**th.thesis_dict(t), "survives": survives}


@router.post("/theses/sweep")
async def sweep_theses(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Evaluate every active thesis's falsifiers now (also runs daily on the scheduler)."""
    if not user:
        raise HTTPException(401, "Authentication required")
    from app.services.agent import thesis as th
    token = await store.get_valid_access_token(db, user.id)
    return await th.daily_sweep(db, user.id, token)


# ── opportunity pool (shared discovery) ────────────────────────────────────

@router.get("/opportunities")
async def opportunities(limit: int = 40, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    from app.services.agent import discovery
    rows = (await db.execute(
        select(Opportunity).where(Opportunity.status == "candidate")
        .order_by(Opportunity.margin_pct.desc().nullslast()).limit(limit)
    )).scalars().all()
    return {"opportunities": [discovery.opp_dict(o) for o in rows]}


@router.post("/opportunities/run")
async def run_opportunities(scope: str = "losers", user=Depends(get_optional_user),
                            db: AsyncSession = Depends(get_db)):
    """Populate the pool. scope='losers' (daily fear scan) | 'top15' | 'adr' | 'sp500' (market-cap seed)."""
    if not user:
        raise HTTPException(401, "Authentication required")
    from app.services.agent import discovery
    if scope in ("top15", "adr", "sp500"):
        return await discovery.seed_discovery(db, universe=scope)
    res = await discovery.run_discovery(db)
    await discovery.refresh_prices(db)
    return res


# ── track list (watch-only, max 3) ─────────────────────────────────────────

@router.get("/track")
async def get_track(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return {"tracks": [], "max": 3}
    from app.services.agent import tracking
    return {"tracks": [tracking.track_dict(t) for t in await tracking.list_tracks(db, user.id)],
            "max": tracking.MAX_TRACK}


@router.post("/track")
async def add_track(payload: dict = Body(...), user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    from app.services.agent import tracking
    t, err = await tracking.add_track(db, user.id, payload.get("symbol", ""))
    if err:
        raise HTTPException(400, err)
    return tracking.track_dict(t)


@router.delete("/track/{symbol}")
async def remove_track(symbol: str, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        raise HTTPException(401, "Authentication required")
    from app.services.agent import tracking
    if not await tracking.remove_track(db, user.id, symbol):
        raise HTTPException(404, "Not tracked")
    return {"removed": symbol.upper()}


@router.post("/track/check")
async def check_track(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Run the tracked-name math check now (also runs daily on the scheduler)."""
    if not user:
        raise HTTPException(401, "Authentication required")
    from app.services.agent import tracking
    token = await store.get_valid_access_token(db, user.id)
    return await tracking.daily_check(db, user.id, token)


@router.get("/ticks")
async def ticks(limit: int = 20, user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    if not user:
        return {"ticks": []}
    rows = (await db.execute(
        select(AgentTick).where(AgentTick.user_id == user.id).order_by(AgentTick.created_at.desc()).limit(limit)
    )).scalars().all()
    return {"ticks": [{"id": str(t.id), "reason": t.reason, "action": t.decision_action, "gate": t.gate_status,
                       "rationale": t.decision_rationale, "dry_run": t.dry_run,
                       "created_at": t.created_at.isoformat()} for t in rows]}


@router.post("/tick/run")
async def run_now(user=Depends(get_optional_user), db: AsyncSession = Depends(get_db)):
    """Manual 'run now' — one review tick immediately. While the market is CLOSED a
    live mandate runs as a PREVIEW (dry-run) so a click can't fire a real order
    pre-market / after-hours; paper always simulates, and during market hours a live
    run executes normally."""
    if not user:
        raise HTTPException(401, "Authentication required")
    from app.services import market_hours
    m = await _load_mandate(db, user.id)
    preview = bool(m) and m.mode == "live" and not market_hours.status()["open"]
    res = await engine.run_tick(user.id, reason="manual", mode="dry_run" if preview else None)
    if preview:
        res["preview"] = True
        res["note"] = "Market is closed — this was a preview. No live order was placed."
    return res
