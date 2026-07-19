"""Track List — up to 3 stocks the user asked to WATCH (not auto-trade).

Each is checked daily on math (price vs conservative fair value → margin). When a
name enters an interesting range (margin ≥ the user's threshold, valued with
confidence) the harness does a deep dive and — if it genuinely fits — creates a
proposal that waits for the user's approval. Watch-only until then; a user may
just want to watch and never buy.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from app.models.db import AgentMandate, AgentOrder, TrackItem
from app.services import accounts as acct_svc, fair_value as fv_svc
from app.services.agent import engine, research

logger = logging.getLogger(__name__)

MAX_TRACK = 3


async def list_tracks(db, user_id) -> list[TrackItem]:
    return list((await db.execute(
        select(TrackItem).where(TrackItem.user_id == user_id, TrackItem.status != "archived")
        .order_by(TrackItem.created_at)
    )).scalars().all())


def track_dict(t: TrackItem) -> dict:
    return {"id": str(t.id), "symbol": t.symbol, "status": t.status,
            "last_price": t.last_price, "last_margin_pct": t.last_margin_pct,
            "note": t.note, "order_id": str(t.order_id) if t.order_id else None,
            "last_check_at": t.last_check_at.isoformat() if t.last_check_at else None}


async def add_track(db, user_id, symbol: str) -> tuple[TrackItem | None, str | None]:
    symbol = symbol.strip().upper()
    if not symbol:
        return None, "symbol required"
    existing = await list_tracks(db, user_id)
    if any(t.symbol == symbol for t in existing):
        return next(t for t in existing if t.symbol == symbol), None
    if len(existing) >= MAX_TRACK:
        return None, f"track list is full (max {MAX_TRACK})"
    t = TrackItem(user_id=user_id, symbol=symbol, status="watching")
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t, None


async def remove_track(db, user_id, symbol: str) -> bool:
    t = (await db.execute(select(TrackItem).where(
        TrackItem.user_id == user_id, TrackItem.symbol == symbol.strip().upper()))).scalar_one_or_none()
    if not t:
        return False
    await db.delete(t)
    await db.commit()
    return True


async def daily_check(db, user_id, token: str | None = None, valuations: dict | None = None) -> dict:
    """Re-value each tracked name; on an interesting range, deep-dive → propose for
    approval. Returns a small summary. Watch-only: proposals always need approval.

    `valuations` is an optional {SYMBOL: fair_value} map computed ONCE for the whole
    run (central.value_symbols) so a name tracked by many users is valued a single
    time; falls back to a live compute for anything not in the map."""
    m = (await db.execute(select(AgentMandate).where(AgentMandate.user_id == user_id))).scalar_one_or_none()
    if not m:
        return {"skipped": "no_mandate"}
    tracks = await list_tracks(db, user_id)
    if not tracks:
        return {"checked": 0}
    account = (await acct_svc.list_for_user(db, user_id))
    account = account[0].account_number if (m.mode == "paper" and account) else m.account
    principles = await engine._render_principles(db, user_id)
    valuations = valuations or {}
    proposed = 0
    for t in tracks:
        fv = valuations.get(t.symbol.upper()) or await asyncio.to_thread(fv_svc.fair_value, t.symbol)
        if not fv:
            continue
        t.last_check_at = engine._utcnow()
        t.last_price = fv.get("current_price")
        t.last_margin_pct = fv.get("margin_pct")
        interesting = bool(fv.get("confident")) and fv.get("margin_pct") is not None and fv["margin_pct"] >= m.margin_of_safety_pct
        if not interesting:
            if t.status not in ("proposed",):
                t.status = "watching"
            continue
        if t.status == "proposed":          # already awaiting approval — don't duplicate
            continue
        assessment = await research.assess_track(t.symbol, fv, principles)
        if not assessment.get("recommend"):
            t.status = "interesting"
            t.note = assessment.get("rationale", "")
            engine._ledger(db, user_id, account, None, "note", f"{t.symbol} — in range, not proposed",
                           assessment.get("rationale", ""), meta={"symbol": t.symbol})
            continue
        # a genuine fit → a watch-only proposal awaiting approval
        price = float(fv.get("current_price") or 0)
        target = m.live_max_notional_usd if m.mode == "live" else min(m.per_trade_cap_usd, 2000.0)
        qty = max(1.0, float(int(target / price))) if price else 1.0
        order = AgentOrder(
            user_id=user_id, account=account, symbol=t.symbol, side="buy", qty=qty, order_type="market",
            est_price=price, est_notional=round(qty * price, 2), rationale=assessment.get("rationale", ""),
            confidence=float(assessment.get("confidence") or 0), status="pending_approval",
            approval_required=True, expires_at=engine._utcnow() + timedelta(days=7),
            dry_run=(m.mode == "dry_run"),
        )
        db.add(order)
        await db.flush()
        t.status = "proposed"
        t.order_id = order.id
        t.note = assessment.get("thesis") or assessment.get("rationale", "")
        try:                                     # arm a Living Thesis for the tracked idea
            from app.services.agent import thesis as th
            await th.arm(db, user_id, account, t.symbol, kind="track", order_id=order.id, principles_block=principles)
        except Exception:
            logger.exception("thesis arm (track) failed for %s", t.symbol)
        engine._ledger(db, user_id, account, None, "awaiting", f"{t.symbol} — a tracked idea is ready for your call",
                       assessment.get("rationale", ""), order_id=order.id,
                       meta={"symbol": t.symbol, "order_line": f"Buy {qty:g} {t.symbol} ≈ ${qty*price:,.0f}", "tracked": True})
        proposed += 1
    await db.commit()
    return {"checked": len(tracks), "proposed": proposed}
