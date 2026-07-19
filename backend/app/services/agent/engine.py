"""The agent review tick — productionized from the harness vertical slice.

One tick = wake → refresh positions from Robinhood (source of truth) → load the
last trades we've done (our DB) → build the cached context → brain proposes →
SafetyGate decides → persist everything (audit) → advance next_tick_at.

P1 runs DRY-RUN: it records what the agent WOULD do (agent_orders + ledger +
ticks) but places no real orders. The Anthropic brain is used only when
`dry_run=False`; dry-run uses the harness's deterministic stub (free) so the loop
can run continuously without cost. Reuses app.harness.{state,brain,safety}.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func

from app.config import settings
from app.services.market_data import get_company_info, get_batch_quotes
from app.database import async_session
from app.services import robinhood_store as store, robinhood_portfolio as rp
from app.services import accounts as paper_svc
from app.services.agent import broker
from app.models.db import AgentMandate, AgentOrder, AgentTick, AgentLedgerEntry, Thesis, Opportunity
from app.harness.state import (
    Action, OrderType, Policy, StrategySpec, PortfolioSnapshot, Position, Quote,
)
from app.harness.brain import build_context, decide
from app.harness.safety import SafetyGate

logger = logging.getLogger(__name__)

CADENCE_MIN = {"5m": 5, "15m": 15, "30m": 30, "1h": 60, "Daily": 1440}
RETRY_BACKOFF_MIN = 5    # a failed/timed-out tick retries soon — not a full cadence later
MIN_BUY_USD = 10.0       # below this, buying power is treated as "can't open a position"
CATASTROPHIC_DD_DEFAULT = 0.30   # platform default: −30% from cost forces a thesis re-review (NOT a stop-loss)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def next_tick_at(cadence: str, frm: datetime | None = None) -> datetime:
    """Next wake. Intraday cadences are anchored to the agent's :50 review slots
    (9:50 AM → 3:50 PM ET) rather than 'now + interval', so reviews land mid-hour —
    past the open, with a real cushion before the close. A small jitter spreads load
    at scale. 'Daily' keeps a rolling interval."""
    from app.services import market_hours
    now = frm or _utcnow()
    if cadence == "Daily":
        return now + timedelta(minutes=CADENCE_MIN["Daily"])
    slot = market_hours.next_agent_slot(now)
    return slot + timedelta(seconds=random.uniform(0, 60))   # :50:00–:50:60, spread for the herd


# ── account fencing ───────────────────────────────────────────────────
async def _agentic_account(token: str) -> str | None:
    """The fenced agentic account number (nickname 'Agentic' / agentic_allowed), or None."""
    try:
        accts = await rp.get_accounts(token)
    except Exception:
        return None
    return next((a["account_number"] for a in accts if a.get("is_agentic")), None)


async def assert_agentic(token: str, account: str) -> bool:
    """Guard for EVERY order path — the agent may only ever touch the fenced
    agentic account, never the user's main portfolio."""
    return bool(account) and await _agentic_account(token) == account


# ── seeding ───────────────────────────────────────────────────────────
async def get_or_create_mandate(db, user_id, token: str | None = None) -> AgentMandate | None:
    m = (await db.execute(select(AgentMandate).where(AgentMandate.user_id == user_id))).scalar_one_or_none()
    agentic = await _agentic_account(token) if token else None
    if m:
        if agentic and m.account != agentic:  # self-heal: pin to the fenced agentic account
            logger.info("Migrating mandate for %s to agentic account %s", user_id, agentic)
            m.account = agentic
            await db.commit()
        return m
    if not agentic:
        return None  # no agentic account -> the agent can't operate
    m = AgentMandate(
        user_id=user_id, account=agentic,
        toggles={"new_pos_approval": True, "loss_sale_approval": True, "earnings_days": True,
                 "after_hours": False, "phone": True, "queue": True, "daily_push": False,
                 "double_check": False},
        next_tick_at=_utcnow(),
    )
    db.add(m)
    await db.commit()
    await db.refresh(m)
    await _seed_principles(db, user_id)
    return m


async def _seed_principles(db, user_id) -> None:
    from app.models.db import AgentPrinciple
    existing = (await db.execute(select(AgentPrinciple.id).where(AgentPrinciple.user_id == user_id))).first()
    if existing:
        return
    seed = [
        ("Temperament", "Invert, always invert — kill the idea before it kills capital.", "CORE · MUNGER"),
        ("Temperament", "Sit on your ass. Activity is not achievement.", "CORE · MUNGER · caps trading at 3 orders/week"),
        ("Selection", "Never buy without a margin of safety — at least the discount set in your mandate.", "CORE · MUNGER · uses your margin-of-safety setting"),
        ("Selection", "Never buy outside the circle of competence.", "CORE · MUNGER"),
        ("Sizing & Selling", "Sell only when the thesis breaks, a ceiling is crossed, or capital has a clearly better home.", "CORE"),
    ]
    for i, (sec, text, meta) in enumerate(seed):
        db.add(AgentPrinciple(user_id=user_id, section=sec, text=text, meta=meta, source="core", order_idx=i))
    await db.commit()


# ── snapshot ──────────────────────────────────────────────────────────
def _subtract_theme_holdings(positions: list[dict], theme_qty: dict) -> list[dict]:
    """Remove theme-attributed shares from the brain's position view. A position held partly
    by a theme is scaled down to the brain's remaining share; a fully theme-owned one is hidden."""
    if not theme_qty:
        return positions
    out = []
    for p in positions:
        sym = str(p.get("symbol", "")).upper()
        tq = float(theme_qty.get(sym, 0.0) or 0.0)
        shares = float(p.get("shares") or 0.0)
        if tq <= 0 or shares <= 0:
            out.append(p)
            continue
        rem = shares - tq
        if rem <= 1e-6:                     # entirely theme-owned → brain sees none of it
            continue
        frac = rem / shares
        np = dict(p)
        np["shares"] = round(rem, 6)
        if p.get("equity") is not None:
            np["equity"] = round(float(p["equity"]) * frac, 2)
        out.append(np)
    return out


def _build_snapshot(positions: list[dict], summary: dict, spent_today: float,
                    sector_map: dict | None = None, orders_week: int = 0) -> PortfolioSnapshot:
    equity = float(summary.get("total_value") or 0.0)
    bp = float(summary.get("buying_power") or 0.0)
    pos_mv = sum(float(p.get("equity") or 0.0) for p in positions)
    cash = max(0.0, equity - pos_mv)
    sm = sector_map or {}
    return PortfolioSnapshot(
        cash=cash, buying_power=bp, equity=equity, spent_today_usd=spent_today, orders_this_week=orders_week,
        positions=[Position(symbol=p["symbol"], qty=float(p.get("shares") or 0),
                            avg_price=float(p.get("avg_cost") or 0),
                            market_value=float(p.get("equity") or 0),
                            sector=sm.get(str(p["symbol"]).upper())) for p in positions],
        quotes=[Quote(symbol=p["symbol"], price=float(p.get("current_price") or 0)) for p in positions],
    )


async def _spent_today(db, user_id, account) -> float:
    """Real buy spend today (placed/filled). Dry-run proposals don't count."""
    start = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    rows = (await db.execute(
        select(AgentOrder.est_notional).where(
            AgentOrder.user_id == user_id, AgentOrder.account == account,
            AgentOrder.side == "buy", AgentOrder.status.in_(("placed", "filled")),
            AgentOrder.created_at >= start,
        )
    )).scalars().all()
    return float(sum(rows))


async def _recent_orders_recap(db, user_id, account, n: int = 6) -> str:
    rows = (await db.execute(
        select(AgentOrder).where(AgentOrder.user_id == user_id, AgentOrder.account == account)
        .order_by(AgentOrder.created_at.desc()).limit(n)
    )).scalars().all()
    if not rows:
        return "No prior agent trades on this account."
    lines = [f"  {o.created_at:%b %d} {o.side.upper()} {o.qty:g} {o.symbol} ~${o.est_notional:,.0f} [{o.status}]" for o in reversed(rows)]
    return "Recent agent orders (most recent last):\n" + "\n".join(lines)


async def _render_principles(db, user_id) -> str:
    """The user's active (non-paused) Latticework, grouped by section, for the
    brain's system prompt. This is what makes editing principles actually change
    the agent's behavior."""
    from app.models.db import AgentPrinciple
    rows = (await db.execute(
        select(AgentPrinciple).where(AgentPrinciple.user_id == user_id, AgentPrinciple.paused.is_(False))
        .order_by(AgentPrinciple.section, AgentPrinciple.order_idx)
    )).scalars().all()
    if not rows:
        return ""
    by_sec: dict[str, list[str]] = {}
    for p in rows:
        by_sec.setdefault(p.section, []).append(p.text)
    return "\n".join(f"[{sec}]\n" + "\n".join(f"  · {t}" for t in texts) for sec, texts in by_sec.items())


def _circle_line(m: AgentMandate) -> str:
    inc = m.circle_include or []
    exc = m.circle_exclude or []
    if not inc and not exc:
        return ""
    parts = []
    if inc:
        parts.append("only act within these sectors: " + ", ".join(inc))
    if exc:
        parts.append("never act in these sectors: " + ", ".join(exc))
    return "CIRCLE OF COMPETENCE — " + "; ".join(parts) + "."


def _policy(m: AgentMandate) -> Policy:
    return Policy(
        user_id=str(m.user_id), approval_threshold_usd=m.approval_threshold_usd,
        per_trade_cap_usd=m.per_trade_cap_usd, daily_spend_cap_usd=m.daily_spend_cap_usd,
        max_position_pct=m.max_position_pct, cash_floor_pct=m.cash_floor_pct,
        sector_cap_pct=m.sector_cap_pct, max_orders_week=m.max_orders_week,
        margin_of_safety_pct=m.margin_of_safety_pct,
        cadence_minutes=CADENCE_MIN.get(m.cadence, 30), kill_switch=m.paused,
    )


async def _orders_this_week(db, user_id, account) -> int:
    """Buy orders actually placed/filled in the trailing 7 days (for max_orders_week)."""
    start = _utcnow() - timedelta(days=7)
    n = (await db.execute(select(func.count()).select_from(AgentOrder).where(
        AgentOrder.user_id == user_id, AgentOrder.account == account,
        AgentOrder.side == "buy", AgentOrder.status.in_(("placed", "filled")),
        AgentOrder.created_at >= start))).scalar()
    return int(n or 0)


async def _sectors_for(db, symbols) -> dict:
    """symbol → sector, from the central pool first (cheap, no network), then
    company info for anything not in the pool. Used by the sector-cap check."""
    syms = {s.upper() for s in symbols if s}
    if not syms:
        return {}
    rows = (await db.execute(select(Opportunity.symbol, Opportunity.sector)
                             .where(Opportunity.symbol.in_(syms)))).all()
    out = {sym: sec for sym, sec in rows if sec}
    for s in syms - set(out):
        try:
            info = await asyncio.to_thread(get_company_info, s)
            if info and info.get("sector"):
                out[s] = info["sector"]
        except Exception:  # noqa: BLE001 — sector is best-effort; unknown → not counted
            pass
    return out


def _strategy(m: AgentMandate) -> StrategySpec:
    return StrategySpec(name=m.strategy_name, objective=m.strategy_objective, rules=m.strategy_rules or "Follow the creed and the Latticework.")


async def _thesis_alerts(db, user_id, account, held: set[str]) -> str:
    """The Living-Thesis falsifier check, folded INTO the hourly tick (so a broken
    thesis is caught every hour, not once a day). Any held name whose downside
    trigger has tripped is returned as a strong sell-signal for the brain; the
    thesis is marked 'flashed'."""
    if not held:
        return ""
    from app.services.agent import thesis as th
    rows = (await db.execute(select(Thesis).where(
        Thesis.user_id == user_id, Thesis.account == account,
        Thesis.status.in_(("active", "flashed")), Thesis.symbol.in_(held)))).scalars().all()
    lines = []
    for t in rows:
        tripped = await asyncio.to_thread(th.evaluate, t)
        if tripped:
            t.status = "flashed"
            desc = "; ".join(f"{x.get('label')} (now {x.get('current')})" for x in tripped)
            lines.append(f"- {t.symbol}: {desc}")
    if not lines:
        return ""
    return ("THESIS ALERTS — these holdings tripped their downside triggers; propose SELL or TRIM unless you "
            "have a compelling reason to hold, and name the trigger in your rationale:\n" + "\n".join(lines))


async def _catastrophic_alerts(snap, m: AgentMandate) -> str:
    """Catastrophic-drawdown backstop — NOT a stop-loss. Any holding down more than the
    threshold from cost forces a THESIS RE-REVIEW this tick (reaffirm or propose exit,
    always through the gate — never a silent auto-sell). Wide by design: a large paper
    loss is not itself a sell reason, but a broken thesis is. Threshold = the mandate's
    `catastrophic_stop_pct` (fraction) else the platform default; ≤0 disables it."""
    thr = m.catastrophic_stop_pct if m.catastrophic_stop_pct is not None else CATASTROPHIC_DD_DEFAULT
    if thr is None or thr <= 0:
        return ""
    if thr > 1:                                   # tolerate a percent (30) as well as a fraction (0.30)
        thr = thr / 100.0
    from app.services.agent import trend as trend_svc
    hits = []
    for p in snap.positions:
        if p.avg_price and p.avg_price > 0 and p.qty:
            px = p.market_value / p.qty
            dd = px / p.avg_price - 1
            if dd <= -thr:
                status = (await asyncio.to_thread(trend_svc.assess_trend, p.symbol)).get("status")
                hits.append((p.symbol, dd, status))
    if not hits:
        return ""
    lines = [f"- {s}: down {dd * 100:.0f}% from cost" + (f", trend {st}" if st and st != "unknown" else "")
             for s, dd, st in hits]
    return ("CATASTROPHIC DRAWDOWN — these holdings breached your review backstop. This is NOT an automatic sell: "
            "a large paper loss is not itself a reason to sell. It forces a THESIS RE-REVIEW right now — pull fresh "
            "data (get_stock_data) and, for each, PROPOSE SELL unless you can specifically REAFFIRM the thesis still "
            "holds (name the reason it's intact). Broken story → exit; just price → hold:\n" + "\n".join(lines))


def _max_buy_usd(m: AgentMandate, snap, held_mv: float = 0.0) -> float:
    """Largest dollar buy that fits EVERY size cap — position weight, cash floor,
    per-trade, daily spend, buying power. The ceiling the brain should size to (and
    the level we trim an oversized proposal down to)."""
    eq = snap.equity or 0.0
    caps = [snap.buying_power, m.per_trade_cap_usd, max(0.0, m.daily_spend_cap_usd - snap.spent_today_usd)]
    if eq > 0 and m.max_position_pct > 0:
        caps.append(max(0.0, m.max_position_pct * eq - held_mv))
    if eq > 0 and m.cash_floor_pct > 0:
        caps.append(max(0.0, snap.cash - m.cash_floor_pct * eq))
    return round(max(0.0, min(caps)), 2)


async def _candidate_shortlist(db, m: AgentMandate, held: set[str], max_buy: float,
                               limit: int = 8) -> tuple[str, list[tuple[str, float]]]:
    """The ranked BUY menu for this tick: the central pool's Confident names, filtered
    to the user's circle of competence and ranked by the quality-first score, minus
    what they already hold. Returns (prompt block, [(symbol, price), …]) — the prices
    are added to the snapshot so both the brain AND the SafetyGate can size in dollars.
    This is how the vetted pool actually reaches the brain."""
    inc = set(m.circle_include or [])
    exc = set(m.circle_exclude or [])
    rows = (await db.execute(
        select(Opportunity).where(Opportunity.category == 1)
        .order_by(Opportunity.score.desc().nullslast()).limit(80))).scalars().all()
    picks = []
    for o in rows:
        if o.symbol in held:                       # already own it → not a new-buy candidate
            continue
        if inc and (o.sector not in inc):          # circle: only-here
            continue
        if o.sector in exc:                        # circle: never-here
            continue
        picks.append(o)
        if len(picks) >= limit:
            break
    if not picks:
        return "", []
    # ── Falling-knife pre-check ──────────────────────────────────────────────
    # "Don't catch a falling knife": never open a new position in a name that's
    # actively falling, however large the margin of safety. Hold those back and
    # buy only from what's stable/basing/rising; surface the held-back names so the
    # brain knows they're on watch (they can be bought once they base). Cached 6h.
    from app.services.agent import trend as trend_svc
    trends = await asyncio.gather(*[asyncio.to_thread(trend_svc.assess_trend, o.symbol) for o in picks])
    tmap = {o.symbol: (t or {}) for o, t in zip(picks, trends)}
    buyable = [o for o in picks if not tmap[o.symbol].get("falling_knife")]
    held_back = [o for o in picks if tmap[o.symbol].get("falling_knife")]

    if not buyable:
        knives = "; ".join(f"{o.symbol} ({tmap[o.symbol].get('summary', 'falling')})" for o in held_back)
        return (f"NO BUY CANDIDATES this tick — every vetted name in your circle is a FALLING KNIFE (still "
                f"declining; a large margin of safety does NOT make a falling knife a buy — wait for it to base). "
                f"HOLD. On watch: {knives}", [])

    quotes = [(o.symbol, float(o.last_price)) for o in buyable if o.last_price]
    lines = [f"  {i}. {o.symbol} ({o.sector}) @ {(f'${o.last_price:,.2f}') if o.last_price else 'n/a'} — score {o.score:.0f}"
             f", margin {('%+.0f%%' % o.margin_pct) if o.margin_pct is not None else 'n/a'}"
             f", trend {tmap[o.symbol].get('status', '?')}"
             f", #{o.sector_rank or '-'} in sector: {(o.central_thesis or '')[:110]}"
             for i, o in enumerate(buyable, 1)]
    block = (f"VETTED CANDIDATES — from our central research pool (each already cleared the quality falsifiers + "
             f"4-lens red-team), ranked by a quality-first score, filtered to your circle, and PRE-SCREENED so "
             f"none is a falling knife. Size ANY single new position to AT MOST ${max_buy:,.0f} — this dollar "
             f"ceiling ALREADY accounts for your position cap, cash floor, per-trade cap, and buying power, so do "
             f"NOT exceed it. FRACTIONAL shares are allowed: qty = dollars ÷ price. These are ELIGIBLE names, "
             f"NOT buy signals — open a new position ONLY if one is a clearly compelling, high-conviction standout "
             f"that clearly beats holding cash; otherwise HOLD. Most ticks should be HOLD:\n"
             + "\n".join(lines))
    if held_back:
        knives = "; ".join(f"{o.symbol} ({tmap[o.symbol].get('summary', 'falling')})" for o in held_back)
        block += ("\n\nON HOLD — falling knives (great business + margin, but the price is still falling; do NOT "
                  f"buy yet, wait for a base): {knives}")
    return block, quotes


_VERIFY_TOOL = {
    "name": "verify_decision",
    "description": "Final skeptical verdict on whether to proceed with the proposed buy.",
    "input_schema": {
        "type": "object",
        "properties": {
            "proceed": {"type": "boolean", "description": "true ONLY if the buy clearly holds up under scrutiny"},
            "confidence": {"type": "number"},
            "reason": {"type": "string", "description": "1–2 sentences — the deciding factor"},
            "key_risks": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["proceed", "reason"],
    },
}

_VERIFY_STATS = ["revenue_growth", "earnings_growth", "gross_margins", "operating_margins", "profit_margins",
                 "return_on_equity", "return_on_assets", "debt_to_equity", "current_ratio", "pe_ratio", "forward_pe"]


async def _double_check(db, account, proposal, snap, notional: float) -> dict:
    """Skeptical second pass before an auto-execute BUY: OUR live trusted numbers +
    a critical web read of the company/analysts (QUALITATIVE only) + this account's
    memory. Returns {proceed, reason, ...}. Fails OPEN (the hard gates already passed)."""
    from app.services.agent import research
    from app.services.agent import memory as mem
    sym = proposal.symbol
    data = await asyncio.to_thread(research.get_stock_data, sym)   # live price + fundamentals + FV from OUR endpoints
    o = (await db.execute(select(Opportunity).where(Opportunity.symbol == sym))).scalar_one_or_none()
    thesis = o.central_thesis if o else None
    memblock = await mem.build_block(db, account)
    system = ("You are the FINAL due-diligence gate before REAL money moves on a BUY the same agent just "
              "proposed. Be SKEPTICAL — the bar to proceed is HIGH; only clear the trade if it genuinely holds up.\n"
              "CRITICAL — DATA RULES: EVERY number (price, valuation, fundamentals) MUST come from OUR data below "
              "or the get_stock_data tool (trusted, live, yfinance-backed). NEVER take a price or statistic from "
              "web search — those are frequently stale/wrong; if a search result shows a different number, IGNORE "
              "it. Use web search ONLY for QUALITATIVE context — recent news, events, and the latest analyst "
              "opinions — and treat analysts as unreliable/biased; weigh them critically, never defer. Watch for: "
              "deteriorating fundamentals, a broken story, imminent earnings/known bad news, valuation that only "
              "works on hope. Decide proceed or veto. Call verify_decision.")
    user = (f"PROPOSED BUY: {proposal.qty:g} {sym} ≈ ${notional:,.0f}. Agent's rationale: {proposal.rationale}\n\n"
            f"OUR TRUSTED LIVE DATA ({sym}): {json.dumps(data, default=str)}\n\n"
            f"CENTRAL THESIS: {thesis or 'n/a'}\n\n"
            f"THIS ACCOUNT'S MEMORY (what we've done/learned):\n{memblock}\n\n"
            f"Verify against our data (call get_stock_data for anything more). Then search the web ONLY for "
            f"{sym}'s qualitative situation + latest analyst sentiment, weigh it critically, and give your verdict.")
    out = await asyncio.to_thread(research._llm_verify, system, user, _VERIFY_TOOL, 1500)
    if not out:
        return {"proceed": True, "reason": "double-check unavailable — proceeding under the hard gates"}
    # A veto MUST justify itself — an empty-reason 'no' is inconclusive, not a real
    # objection, so it must never block a buy the hard gates already cleared.
    if not out.get("proceed") and not str(out.get("reason") or "").strip():
        logger.info("double-check: empty-reason veto → inconclusive, proceeding")
        return {"proceed": True, "reason": "double-check inconclusive (no reason given) — proceeding under the hard gates"}
    return out


# ── the tick ──────────────────────────────────────────────────────────
async def run_tick(user_id, reason: str = "cadence", mode: str | None = None) -> dict:
    async with async_session() as db:
        token = await store.get_valid_access_token(db, user_id)
        if not token:
            return {"skipped": "not_connected"}
        m = await get_or_create_mandate(db, user_id, token)
        if m is None:
            return {"skipped": "no_account"}
        if m.paused:
            return {"skipped": "paused"}
        # Execution target is the user's own toggle (mandate.mode): paper|live|dry_run.
        mode = mode or m.mode or "paper"
        dry_run = mode == "dry_run"

        # Which account this tick trades: paper mode -> the user's paper account
        # (our DB); every other mode -> the fenced Robinhood agentic account.
        if mode == "paper":
            paper_accts = await paper_svc.list_for_user(db, user_id)
            if not paper_accts:
                return {"skipped": "no_paper_account"}
            account = paper_accts[0].account_number
        else:
            account = m.account

        tick = AgentTick(user_id=user_id, account=account, reason=reason, dry_run=dry_run)
        db.add(tick)
        await db.flush()  # get tick.id

        try:
            if mode == "paper":
                positions = await paper_svc.get_positions(db, account)
                summary = await paper_svc.get_summary(db, account)
            else:
                # Reconcile the fenced agentic account from Robinhood into our
                # store (the user may have traded there directly), then use the
                # freshly-synced snapshot. This keeps stored agentic positions
                # in sync every cadence tick.
                positions, summary = await paper_svc.sync_from_robinhood(
                    db, user_id, token, account, kind="agentic", nickname="Agentic")
                # Carve out Polytrade money — theme-held shares + reserved cash are NOT the
                # brain's to spend or sell; its pool = total − theme (shown in total portfolio,
                # excluded from what the brain acts on).
                try:
                    from app.services.agent.theme_exec import brain_exclusions
                    excl = await brain_exclusions(db, user_id, account)
                    if excl["holdings"] or excl["reserved_cash"]:
                        positions = _subtract_theme_holdings(positions, excl["holdings"])
                        summary = {**summary, "buying_power": max(0.0, float(summary.get("buying_power") or 0.0) - excl["reserved_cash"])}
                except Exception as e:  # never block a tick on the exclusion lookup
                    logger.warning("theme exclusion lookup failed for %s: %s", user_id, e)
            spent = await _spent_today(db, user_id, account)
            orders_week = await _orders_this_week(db, user_id, account)
            sector_map = await _sectors_for(db, [p["symbol"] for p in positions])
            snap = _build_snapshot(positions, summary, spent, sector_map, orders_week)

            # Be intelligent about what's worth a review this tick (saves an LLM call
            # and keeps the ledger clean):
            #   • no positions AND no buying power → genuinely idle, nothing to do.
            #   • positions but ~$0 buying power → we can't open/add, so only manage
            #     what we hold (exit a broken thesis, or swap into something better).
            has_positions = len(snap.positions) > 0
            can_buy = snap.buying_power >= MIN_BUY_USD
            if not has_positions and not can_buy:
                tick.decision_action = "hold"
                tick.decision_rationale = "Idle — no positions and no buying power; nothing to review."
                tick.gate_status = "noop"
                tick.finished_at = _utcnow()
                m.last_tick_at = _utcnow()
                m.next_tick_at = next_tick_at(m.cadence)
                await db.commit()
                return {"skipped": "idle", "tick_id": str(tick.id)}   # no ledger entry — keeps the log clean

            constraints = ""
            if not can_buy:      # has positions but no cash to deploy
                constraints = (
                    f"BUYING POWER IS ${snap.buying_power:,.0f} — you cannot open or add to positions this tick, "
                    "so do NOT propose a BUY. Review only the current holdings: SELL if a thesis has broken or a "
                    "hard risk trips; otherwise HOLD. You may propose SELLING a weaker holding only if you would "
                    "clearly redeploy into a materially better opportunity (a swap) — say so in the rationale.")

            # Fold the Living-Thesis falsifier check into this tick (replaces the old
            # once-a-day sweep): tripped downside triggers become a strong sell-signal.
            alerts = await _thesis_alerts(db, user_id, account, {p.symbol for p in snap.positions})
            if alerts:
                constraints = (constraints + "\n\n" + alerts) if constraints else alerts

            # Catastrophic-drawdown backstop: a holding down beyond the review threshold
            # forces a thesis re-review (reaffirm or propose exit) — the "smart stop".
            crisis = await _catastrophic_alerts(snap, m)
            if crisis:
                constraints = (constraints + "\n\n" + crisis) if constraints else crisis

            # The ranked, in-circle BUY menu from the central pool — only when there's
            # cash to deploy (no point surfacing candidates we can't act on). Their
            # prices go INTO the snapshot so the brain sizes correctly AND the gate can
            # enforce dollar limits on a new buy (a candidate isn't in the held quotes).
            candidates = ""
            if can_buy:
                # exclude what we hold AND anything the double-check already vetoed
                # today — so the brain moves on to a name that can clear, instead of
                # re-proposing the same reject every tick.
                day0 = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                vmeta = (await db.execute(select(AgentLedgerEntry.meta).where(
                    AgentLedgerEntry.account == account, AgentLedgerEntry.type == "veto",
                    AgentLedgerEntry.ts >= day0))).scalars().all()
                exclude = ({p.symbol for p in snap.positions}
                           | {(vm or {}).get("symbol") for vm in vmeta if vm and vm.get("symbol")})
                candidates, cand_quotes = await _candidate_shortlist(db, m, exclude, _max_buy_usd(m, snap))
                for sym, px in cand_quotes:
                    if px and snap.price_of(sym) is None:
                        snap.quotes.append(Quote(symbol=sym, price=px))

            from app.services.agent import memory as mem
            recap = await mem.build_block(db, account)   # continuous account memory (was the 6-line recap)
            policy, strat = _policy(m), _strategy(m)
            principles_block = await _render_principles(db, user_id)
            circle = _circle_line(m)
            if circle:
                principles_block = (circle + "\n\n" + principles_block).strip()
            bundle = build_context(policy, strat, snap, recap, principles_block,
                                   constraints=constraints, candidates=candidates)
            from app.services.agent import research as _research
            proposal, usage = await asyncio.to_thread(decide, bundle, snap, strat, None, dry_run,
                                                      _research.get_stock_data)   # brain can pull trusted data
            # Safety: the gate enforces dollar limits via notional = qty × price, so a
            # BUY must have a price in the snapshot. If the brain named a symbol we
            # don't hold and isn't in the candidate quotes, fetch a live quote — else
            # notional would be $0 and the caps wouldn't bite.
            if proposal.action is Action.BUY and proposal.symbol and snap.price_of(proposal.symbol) is None:
                try:
                    q = await asyncio.to_thread(get_batch_quotes, [proposal.symbol])
                    px = float(q[0]["price"]) if (q and q[0].get("price")) else None
                    if px:
                        snap.quotes.append(Quote(symbol=proposal.symbol, price=px))
                except Exception:  # noqa: BLE001
                    logger.warning("could not price %s for the gate", proposal.symbol)
            # Right-size a BUY to fit every dollar cap (fractional) so a good idea
            # isn't lost to an oversize — the brain proposes, we trim DOWN to the max.
            if proposal.action is Action.BUY and proposal.symbol:
                px = snap.price_of(proposal.symbol)
                if px and px > 0:
                    held_mv = next((p.market_value for p in snap.positions if p.symbol == proposal.symbol), 0.0)
                    cap = _max_buy_usd(m, snap, held_mv)
                    if proposal.qty * px > cap + 0.01:
                        trimmed = int((cap / px) * 10000) / 10000   # floor to 4dp so qty×price can NEVER exceed the cap (was round(), which rounded up and self-tripped the cash floor)
                        logger.info("Trimming BUY %s %s→%s sh to fit $%.0f cap", proposal.symbol, proposal.qty, trimmed, cap)
                        proposal.qty = trimmed

            # Robinhood allows fractional shares ONLY on MARKET orders — a fractional
            # LIMIT is rejected. Force any fractional buy/sell to a market order.
            if proposal.symbol and proposal.qty and proposal.qty != int(proposal.qty):
                if proposal.order_type is not OrderType.MARKET:
                    logger.info("Fractional %s qty %s → forcing MARKET order", proposal.symbol, proposal.qty)
                proposal.order_type = OrderType.MARKET
                proposal.limit_price = None

            # resolve the proposed symbol's sector for the sector-cap check (reuse the
            # held-position map; look it up if it's a brand-new name)
            proposed_sector = None
            if proposal.symbol:
                sym = proposal.symbol.upper()
                proposed_sector = sector_map.get(sym) or (await _sectors_for(db, [sym])).get(sym)
            gate = SafetyGate(policy).evaluate(proposal, snap, proposed_sector=proposed_sector)

            tick.snapshot = {"equity": snap.equity, "cash": snap.cash, "buying_power": snap.buying_power,
                             "positions": [p.model_dump() for p in snap.positions]}
            tick.decision_action = proposal.action.value
            tick.decision_rationale = proposal.rationale
            tick.confidence = proposal.confidence
            tick.usage = usage
            tick.finished_at = _utcnow()

            order_id = None
            if proposal.action is Action.HOLD:
                tick.gate_status = "noop"
                _ledger(db, user_id, account, tick.id, "check", "Portfolio check",
                        proposal.rationale or "No position crossed its band. Nothing to do.",
                        meta={"confidence": round(proposal.confidence, 2)})
            elif not gate.allowed:
                tick.gate_status = "rejected"
                line = f"{proposal.action.value.title()} {proposal.qty:g} {proposal.symbol} ≈ ${gate.notional_usd:,.0f}"
                _ledger(db, user_id, account, tick.id, "note", f"Blocked — wanted to {line}",
                        f"Why the Partner wanted it: {proposal.rationale or '—'}\n\n"
                        f"Blocked by (hard limits, cannot be crossed): " + "; ".join(gate.reasons),
                        meta={"symbol": proposal.symbol, "order_line": line})
            else:
                order = _record_order(user_id, account, tick.id, proposal, gate, snap, dry_run)
                db.add(order)
                await db.flush()
                order_id = order.id
                tick.order_id = order.id

                # Decide whether this must wait for human approval. Base rule is
                # the mandate threshold (gate.requires_approval); live mode adds a
                # fail-closed agentic check + small-cap + rollout-approval layer.
                needs_approval = gate.requires_approval
                block_reason = None

                # Living Thesis: a BUY arms a thesis + faces the red-team on entry.
                # If it doesn't survive ≥3 lenses, don't auto-buy — bring it to the user.
                if proposal.action is Action.BUY:
                    try:
                        from app.services.agent import thesis as thesis_mod
                        _, survives = await thesis_mod.arm(db, user_id, account, proposal.symbol,
                                                           kind="holding", order_id=order.id,
                                                           principles_block=principles_block)
                        if not survives:
                            needs_approval = True
                            _ledger(db, user_id, account, tick.id, "note",
                                    f"{proposal.symbol} — the red-team flagged the thesis",
                                    "It didn't clear the 4-lens red-team, so I'm bringing it to you rather than buying automatically.",
                                    order_id=order.id, meta={"symbol": proposal.symbol})
                    except Exception:
                        logger.exception("thesis arming (buy) failed")
                if mode == "live":
                    if settings.trading_halt:
                        block_reason = "trading halted (global kill switch)"
                    elif not await assert_agentic(token, account):
                        block_reason = "target is not the fenced agentic account"
                    elif settings.live_require_approval or gate.notional_usd > m.live_max_notional_usd:
                        needs_approval = True

                if block_reason:
                    tick.gate_status = "rejected"
                    order.status = "rejected"
                    order.error_message = block_reason
                    _ledger(db, user_id, account, tick.id, "note", "Live order blocked",
                            block_reason, order_id=order.id, meta={"symbol": proposal.symbol})
                elif needs_approval:
                    tick.gate_status = "pending_approval"
                    order.status = "pending_approval"
                    order.approval_required = True
                    order.expires_at = _utcnow() + timedelta(hours=4)
                    _ledger(db, user_id, account, tick.id, "awaiting", "Awaiting your approval",
                            proposal.rationale, order_id=order.id,
                            meta=_order_meta(proposal, gate, over_threshold=True, threshold=policy.approval_threshold_usd))
                else:
                    # Double-check before buying (opt-in): a skeptical second pass on
                    # an auto-execute BUY (our fundamentals + a critical web read). A
                    # veto cancels the buy and is recorded — and surfaced back to the
                    # brain next tick via account memory ("you proposed X, veto said Y").
                    veto = None
                    if proposal.action is Action.BUY and (m.toggles or {}).get("double_check") and not dry_run:
                        v = await _double_check(db, account, proposal, snap, gate.notional_usd)
                        if not v.get("proceed"):
                            veto = v
                    if veto:
                        tick.gate_status = "vetoed"
                        order.status = "vetoed"
                        _ledger(db, user_id, account, tick.id, "veto",
                                f"Double-check vetoed BUY {proposal.qty:g} {proposal.symbol} ≈ ${gate.notional_usd:,.0f}",
                                veto.get("reason", ""), order_id=order.id, meta={"symbol": proposal.symbol})
                    else:
                        tick.gate_status = "executed"
                        if proposal.action is Action.BUY and (m.toggles or {}).get("double_check") and not dry_run:
                            _ledger(db, user_id, account, tick.id, "note", "Double-check cleared the buy",
                                    f"Why the Partner wants it: {proposal.rationale or '—'}", order_id=order.id,
                                    meta={"symbol": proposal.symbol,
                                          "order_line": f"Buy {proposal.qty:g} {proposal.symbol} ≈ ${gate.notional_usd:,.0f}"})
                        await _execute_order(db, order, mode, snap, token=token)

            m.last_tick_at = _utcnow()
            m.next_tick_at = next_tick_at(m.cadence)
            await db.commit()
            return {"ok": True, "tick_id": str(tick.id), "action": proposal.action.value,
                    "gate": tick.gate_status, "order_id": str(order_id) if order_id else None, "dry_run": dry_run}
        except Exception as e:
            logger.exception("Agent tick failed for user %s", user_id)
            tick.finished_at = _utcnow()
            tick.gate_status = "error"
            _ledger(db, user_id, account, tick.id, "error", "Review failed", str(e))
            m.last_tick_at = _utcnow()
            m.next_tick_at = _utcnow() + timedelta(minutes=RETRY_BACKOFF_MIN)   # retry soon, not next cadence
            await db.commit()
            return {"error": str(e)}


async def _execute_order(db, order: AgentOrder, mode: str, snap: PortfolioSnapshot,
                         token: str | None = None) -> None:
    """Place (or, in dry-run, record intent for) an under-threshold order."""
    if mode == "dry_run":
        order.status = "proposed"
        _ledger(db, order.user_id, order.account, order.tick_id, "note",
                f"Would {order.side} {order.qty:g} {order.symbol} (dry run)", order.rationale,
                order_id=order.id, meta={"order_line": f"{order.side.title()} {order.qty:g} {order.symbol} ≈ ${order.est_notional:,.0f}"})
        return
    px = order.est_price or snap.price_of(order.symbol) or 0.0
    fill = await _place(db, order, mode, px, token)
    _apply_fill(db, order, fill)
    await _settle_paper(db, order, fill, mode)
    await _reconcile_after_live(db, order, mode, fill, token)


async def _place(db, order: AgentOrder, mode: str, px: float, token: str | None) -> dict:
    """Route to the broker. For live, fetch the token if needed and re-assert the
    agentic fence right before sending (fail-closed)."""
    if mode == "live":
        token = token or await store.get_valid_access_token(db, order.user_id)
        if not token or not await assert_agentic(token, order.account):
            return {"status": "failed", "error": "live guard failed — no token or non-agentic account"}
        return await broker.execute(mode, order.symbol, order.side, order.qty, px,
                                    token=token, account=order.account,
                                    order_type=order.order_type, limit_price=order.limit_price,
                                    ref_id=str(order.id))
    return await broker.execute(mode, order.symbol, order.side, order.qty, px)


async def _reconcile_after_live(db, order: AgentOrder, mode: str, fill: dict, token: str | None) -> None:
    """After a live order is placed/filled, reconcile the agentic account from
    Robinhood so the store reflects the broker's truth (real fill qty/price)."""
    if mode != "live" or fill.get("status") not in ("placed", "filled"):
        return
    token = token or await store.get_valid_access_token(db, order.user_id)
    if token:
        try:
            await paper_svc.sync_from_robinhood(db, order.user_id, token, order.account,
                                                kind="agentic", nickname="Agentic")
        except Exception as e:
            logger.warning("post-trade reconcile failed for %s: %s", order.account, e)


async def _settle_paper(db, order: AgentOrder, fill: dict, mode: str) -> None:
    """When trading paper money, reflect the fill in the paper book (cash +
    positions). No-op for every other mode."""
    if mode == "paper" and fill.get("status") == "filled" and paper_svc.is_paper_number(order.account):
        await paper_svc.apply_fill(
            db, order.account, order.symbol, order.side,
            float(fill.get("filled_qty") or order.qty), float(fill.get("fill_price") or 0.0),
        )


def _apply_fill(db, order: AgentOrder, fill: dict) -> None:
    st = fill.get("status")
    if st in ("filled", "placed"):
        order.status = st
        order.fill_price = fill.get("fill_price")
        order.filled_qty = fill.get("filled_qty")
        order.filled_notional = fill.get("filled_notional")
        order.robinhood_order_id = fill.get("broker_order_id")
        order.dry_run = False
        fq = order.filled_qty or order.qty
        fp = order.fill_price or 0.0
        line = f"{order.side.upper()} {fq:g} {order.symbol}" + (f" @ ${fp:.2f}" if fp else "")
        meta = {"order_line": line, "notional": order.filled_notional}
        if fill.get("disclosure"):   # Robinhood compliance quote disclosure — surfaced verbatim
            meta["disclosure"] = fill["disclosure"]
        if fill.get("order_check_ack"):   # informational pre-trade disclosure we placed past (audit trail)
            meta["order_check"] = fill["order_check_ack"]
        if fill.get("broker_order_id"):
            meta["broker_order_id"] = fill["broker_order_id"]
        _ledger(db, order.user_id, order.account, order.tick_id, "executed", line,
                "Placed on the agentic account and recorded in the Ledger — thesis, sizing, and exit triggers are written down.",
                order_id=order.id, meta=meta)
    elif fill.get("needs_investor_profile"):
        # A setup block only the USER can clear — surface as an actionable item (type
        # 'action' → the UI renders it prominently with a one-tap link), not a buried error.
        order.status = "failed"
        order.error_message = fill.get("error")
        meta = {"action_label": "Finish Robinhood setup"}
        if fill.get("action_url"):
            meta["action_url"] = fill["action_url"]
        _ledger(db, order.user_id, order.account, order.tick_id, "action",
                "Action needed — complete your Robinhood investor profile",
                fill.get("error", ""), order_id=order.id, meta=meta)
    else:
        order.status = "failed"
        order.error_message = fill.get("error")
        _ledger(db, order.user_id, order.account, order.tick_id, "error", "Order failed",
                fill.get("error", ""), order_id=order.id)


async def execute_approved(db, order: AgentOrder) -> dict:
    """Place an order the user just approved (paper/alpaca/live); dry-run just logs."""
    m = (await db.execute(select(AgentMandate).where(AgentMandate.user_id == order.user_id))).scalar_one_or_none()
    mode = (m.mode if m else None) or settings.agent_mode
    # Kill switch: a paused mandate never places, even for an already-approved order.
    if m and m.paused:
        order.status = "rejected"
        order.error_message = "agent paused (kill switch)"
        _ledger(db, order.user_id, order.account, order.tick_id, "note", "Order blocked — agent paused",
                "You approved this order but the agent is paused, so nothing was placed.", order_id=order.id)
        await db.commit()
        return {"status": order.status}
    order.status = "approved"
    order.approved_at = _utcnow()
    if mode == "dry_run":
        _ledger(db, order.user_id, order.account, order.tick_id, "approved", "Approved by you",
                f"You approved the {order.side} of {order.qty:g} {order.symbol}. Placement begins when the agent mode is 'paper' or 'live'.",
                order_id=order.id)
    elif mode == "live" and settings.trading_halt:
        order.status = "rejected"
        order.error_message = "trading halted (global kill switch)"
        _ledger(db, order.user_id, order.account, order.tick_id, "note", "Live order blocked",
                "Approved, but trading is halted by the global kill switch.", order_id=order.id)
    else:
        px = order.est_price or 0.0
        fill = await _place(db, order, mode, px, None)
        _apply_fill(db, order, fill)
        await _settle_paper(db, order, fill, mode)
        await _reconcile_after_live(db, order, mode, fill, None)
    await db.commit()
    return {"status": order.status}


def _record_order(user_id, account, tick_id, proposal, gate, snap, dry_run) -> AgentOrder:
    px = proposal.limit_price or snap.price_of(proposal.symbol) or 0.0
    return AgentOrder(
        user_id=user_id, account=account, tick_id=tick_id, symbol=proposal.symbol,
        side=proposal.action.value, qty=proposal.qty, order_type=proposal.order_type.value,
        limit_price=proposal.limit_price, est_price=px, est_notional=gate.notional_usd,
        rationale=proposal.rationale, confidence=proposal.confidence, dry_run=dry_run,
    )


def _order_meta(proposal, gate, over_threshold=False, threshold=0.0) -> dict:
    m = {"order_line": f"{proposal.action.value.title()} {proposal.qty:g} {proposal.symbol} ≈ ${gate.notional_usd:,.0f}",
         "notional": gate.notional_usd, "confidence": proposal.confidence}
    if over_threshold:
        m["threshold"] = threshold
    return m


def _ledger(db, user_id, account, tick_id, type_, title, body, order_id=None, screen_id=None, meta=None) -> None:
    db.add(AgentLedgerEntry(user_id=user_id, account=account, tick_id=tick_id, order_id=order_id,
                            screen_id=screen_id, type=type_, title=title, body=body or "", meta=meta))
