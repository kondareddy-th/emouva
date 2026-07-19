"""Polytrade — allocation execution + reconciliation (M2).

Per-user capital lives in a ThemeAllocation: the user sweeps cash from their paper
account into the allocation, which holds its OWN cash plus a separate ThemeHolding book
(isolated from the discretionary account_positions, so the trading engine never sees
theme shares and every lot is attributable to one allocation). A version-driven
reconciler moves each allocation toward the theme's target basket:

  pending                          → invest committed_usd at target weights
  active & applied < target_ver    → rebalance to the (changed) basket
  unwinding / theme is breaking     → sell everything, return cash, close

Idempotent: after a successful reconcile, applied_version = target_version, so a re-run
is a no-op.

LIVE execution: when a theme allocation is on the agentic account and the real-money gate is
armed (themes_live_active), the reconciler places REAL Robinhood orders (split under the
per-order cap) and books the actual fills into ThemeHolding. The money is RESERVED out of the
account (no sweep); the discretionary brain's pool = total − theme (see engine + brain_exclusions),
so the two coexist on one account without stepping on each other. Paper allocations (grandfathered)
still fill synthetically. Gate is OFF by default — see config.themes_live_enabled + docs/POLYTRADE.md §7.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.models.db import (Theme, ThemeConstituent, ThemeAllocation, ThemeHolding, Account)
from app.services.agent import themes as themes_svc

logger = logging.getLogger(__name__)

_EPS = 0.01          # ignore sub-cent deltas (avoids churn on rounding)
_OPEN_STATUSES = ("pending", "active", "unwinding")


def themes_live_active() -> bool:
    """Real-money theme execution is armed only when ALL gates agree — the Polytrade
    switch, the platform live-execution switch, and no trading halt. Default OFF, so
    theme allocations are paper-only. See config.themes_live_enabled + docs/POLYTRADE.md §7."""
    return bool(settings.themes_live_enabled and settings.live_execution_enabled and not settings.trading_halt)


# ── live execution on the agentic account (real Robinhood orders) ────────────

_LIVE_MIN_ORDER = 1.0     # skip sub-$1 order chunks


def _market_open() -> bool:
    """Regular US market hours (holiday- and early-close-aware). Live orders only place when
    open — off-hours, a live reconcile DEFERS (the allocation stays pending and executes at the
    next market-open reconcile) rather than firing a market order into a closed/illiquid book."""
    try:
        from app.services.market_hours import status
        return bool(status().get("open"))
    except Exception:
        return False          # fail-closed: if we can't tell, don't place live orders


async def _live_context(db, alloc: "ThemeAllocation") -> tuple[str, str] | None:
    """(token, agentic_account) for a live allocation, or None when it must NOT execute
    live (paper account, gate off, or no valid Robinhood token) — reconcile then no-ops
    rather than paper-filling a real account."""
    from app.services.accounts import is_paper_number
    if is_paper_number(alloc.account) or not themes_live_active():
        return None
    from app.services import robinhood_store
    token = await robinhood_store.get_valid_access_token(db, alloc.user_id)
    return (token, alloc.account) if token else None


async def _live_fill(token: str, account: str, symbol: str, side: str, qty: float, price: float) -> tuple[float, float]:
    """Place REAL market order(s) on the agentic account for ~`qty` shares, splitting into
    chunks under the per-order notional cap (live_max_notional_usd). Returns (filled_qty,
    avg_price). Fails closed — a failed/blocked chunk stops the loop, keeping partial fills."""
    from app.services.agent import broker
    cap = float(settings.live_max_notional_usd or 250.0)
    remaining, tot_qty, tot_cost, guard = qty, 0.0, 0.0, 0
    while remaining * price > _LIVE_MIN_ORDER and guard < 25:
        guard += 1
        chunk = remaining if remaining * price <= cap else round(cap / price, 4)
        if chunk <= 0:
            break
        res = await broker.execute("live", symbol, side, chunk, price, token=token, account=account,
                                   order_type="market", ref_id=str(uuid.uuid4()))
        if res.get("status") != "filled":
            logger.warning("theme live %s %s x%.4f failed: %s", side, symbol, chunk, res.get("error"))
            break
        fq = float(res.get("filled_qty") or 0.0)
        if fq <= 0:
            break
        tot_qty += fq
        tot_cost += fq * float(res.get("fill_price") or price)
        remaining -= fq
    return round(tot_qty, 6), round((tot_cost / tot_qty) if tot_qty else price, 4)


# ── pure planning (unit-tested without a DB) ─────────────────────────────────

def _plan(base: float, cons: dict, cur_qty: dict, prices: dict):
    """Given a target dollar base, the target weights (cons), current share quantities and
    prices, return (sells, buys): sells=[(sym, qty, px)], buys=[(sym, dollars, px)]. A name
    dropped from the basket (weight 0) is fully sold; a name with no price is skipped."""
    sells, buys = [], []
    for sym in set(cons) | set(cur_qty):
        px = prices.get(sym)
        if not px:
            continue
        cur = cur_qty.get(sym, 0.0) * px
        tgt = base * cons.get(sym, 0.0)
        d = tgt - cur
        if d < -_EPS:
            sells.append((sym, min(cur_qty.get(sym, 0.0), (-d) / px), px))
        elif d > _EPS:
            buys.append((sym, d, px))
    return sells, buys


# ── data helpers ─────────────────────────────────────────────────────────────

async def _prices(symbols: list[str]) -> dict:
    if not symbols:
        return {}
    try:
        from app.services.market_data import get_batch_quotes
        quotes = await asyncio.to_thread(get_batch_quotes, list(set(symbols)))
        return {q["symbol"]: q["price"] for q in quotes if q.get("price")}
    except Exception as e:
        logger.warning("theme_exec prices failed: %s", e)
        return {}


async def _holdings(db, alloc_id) -> list[ThemeHolding]:
    return list((await db.execute(select(ThemeHolding).where(ThemeHolding.allocation_id == alloc_id))).scalars().all())


async def _active_constituents(db, theme_id) -> dict:
    rows = (await db.execute(select(ThemeConstituent).where(
        ThemeConstituent.theme_id == theme_id, ThemeConstituent.status == "active"))).scalars().all()
    return {c.symbol: (c.target_weight or 0.0) for c in rows}


# ── paper fills on the isolated theme book ───────────────────────────────────

def _buy(db, alloc: ThemeAllocation, holds: dict, symbol: str, qty: float, price: float) -> None:
    cost = qty * price
    alloc.cash -= cost
    alloc.invested_usd += cost
    h = holds.get(symbol)
    if h:
        nq = h.quantity + qty
        h.avg_cost = (h.quantity * h.avg_cost + cost) / nq if nq else price
        h.quantity = nq
        h.last_price = price
    else:
        h = ThemeHolding(allocation_id=alloc.id, symbol=symbol, quantity=qty, avg_cost=price, last_price=price)
        db.add(h)
        holds[symbol] = h


def _sell(alloc: ThemeAllocation, h: ThemeHolding, qty: float, price: float) -> None:
    qty = min(qty, h.quantity)
    if qty <= 0:
        return
    alloc.cash += qty * price
    alloc.invested_usd -= qty * h.avg_cost
    alloc.realized_pnl += qty * (price - h.avg_cost)
    h.quantity -= qty
    h.last_price = price


def _mark(alloc: ThemeAllocation, holds, prices: dict) -> None:
    holdings_mv = sum(h.quantity * (prices.get(h.symbol) or h.last_price or h.avg_cost) for h in holds)
    alloc.market_value = round(alloc.cash + holdings_mv, 2)
    alloc.unrealized_pnl = round(holdings_mv - alloc.invested_usd, 2)


async def _return_cash(db, alloc: ThemeAllocation, live: bool) -> None:
    """Release the allocation's residual cash. Paper: credit the source paper account.
    Live: the real cash already sits in the agentic account (the sells credited it) — we
    just zero the reservation so the brain's pool sees it again."""
    if live:
        alloc.cash = 0.0
        return
    acct = (await db.execute(select(Account).where(Account.account_number == alloc.account))).scalar_one_or_none()
    if acct:
        acct.cash = (acct.cash or 0.0) + alloc.cash
    alloc.cash = 0.0


async def _do_buy(db, alloc: ThemeAllocation, holds: dict, symbol: str, dollars: float, price: float,
                  live: tuple[str, str] | None) -> None:
    """Book a buy — real order(s) on the agentic account when live, else a synthetic paper fill."""
    if live:
        fq, fp = await _live_fill(live[0], live[1], symbol, "buy", dollars / price, price)
        if fq > 0:
            _buy(db, alloc, holds, symbol, fq, fp)
    else:
        _buy(db, alloc, holds, symbol, dollars / price, price)


async def _do_sell(db, alloc: ThemeAllocation, holds: dict, symbol: str, qty: float, price: float,
                   live: tuple[str, str] | None) -> None:
    h = holds.get(symbol)
    if not h:
        return
    qty = min(qty, h.quantity)
    if live:
        fq, fp = await _live_fill(live[0], live[1], symbol, "sell", qty, price)
        if fq > 0:
            _sell(alloc, h, fq, fp)
    else:
        _sell(alloc, h, qty, price)
    if h.quantity <= 1e-9:
        await db.delete(h)
        holds.pop(symbol, None)


# ── the reconciler ───────────────────────────────────────────────────────────

async def reconcile_allocation(db, alloc: ThemeAllocation, theme: Theme, prices: dict | None = None) -> dict:
    """Move one allocation toward the theme's target basket (or fully unwind it). Idempotent.
    Live allocations (on an agentic account, gate armed) place REAL orders; paper allocations
    fill synthetically."""
    if alloc.status == "closed":
        return {"noop": True}
    live = await _live_context(db, alloc)          # (token, account) → real orders, else None → paper
    if live and not _market_open():
        # defer: keep the allocation in its current state; the market-open reconcile executes it
        logger.info("theme reconcile deferred (market closed): allocation %s", alloc.id)
        return {"deferred": "market closed"}
    cons = await _active_constituents(db, theme.id)
    holds = {h.symbol: h for h in await _holdings(db, alloc.id)}
    prices = prices or await _prices(list(set(cons) | set(holds)))
    for s, h in holds.items():
        if prices.get(s):
            h.last_price = prices[s]

    unwinding = alloc.status == "unwinding" or theme.status == "breaking"
    if unwinding:
        for sym in list(holds.keys()):
            px = prices.get(sym) or holds[sym].last_price or holds[sym].avg_cost
            await _do_sell(db, alloc, holds, sym, holds[sym].quantity, px, live)
        await _return_cash(db, alloc, bool(live))
        _mark(alloc, holds.values(), prices)
        alloc.status = "closed"
        alloc.closed_at = datetime.utcnow()
        alloc.applied_version = theme.target_version
        await db.flush()
        pnl = (alloc.market_value or 0.0) - alloc.committed_usd
        themes_svc.notify(db, alloc.user_id, "order_executed", f"“{theme.title}” closed",
                          f"Exited — {'sold the basket, ' if live else ''}returned ${alloc.market_value:,.2f} "
                          f"({'+' if pnl >= 0 else ''}${pnl:,.2f}).")
        return {"unwound": True, "market_value": alloc.market_value, "realized_pnl": round(alloc.realized_pnl, 2)}

    # invest (pending) or rebalance (active, version bumped)
    holdings_mv = sum(h.quantity * (prices.get(s) or h.avg_cost) for s, h in holds.items())
    base = alloc.committed_usd if alloc.status == "pending" else (alloc.cash + holdings_mv)
    cur_qty = {s: h.quantity for s, h in holds.items()}
    sells, buys = _plan(base, cons, cur_qty, prices)

    for sym, qty, px in sells:                 # sells first — frees cash for the buys
        await _do_sell(db, alloc, holds, sym, qty, px, live)
    for sym, dollars, px in buys:
        dollars = min(dollars, max(0.0, alloc.cash))    # never overspend the allocation's reserved cash
        if dollars <= _EPS:
            continue
        await _do_buy(db, alloc, holds, sym, dollars, px, live)

    _mark(alloc, holds.values(), prices)
    was = alloc.status
    alloc.status = "active"
    alloc.applied_version = theme.target_version
    await db.flush()
    if was == "pending":
        themes_svc.notify(db, alloc.user_id, "order_executed", f"“{theme.title}” is live",
                          f"Invested ${alloc.committed_usd:,.0f} across {len(holds)} names — we'll manage it from here.")
    return {"invested" if was == "pending" else "rebalanced": True,
            "n_holdings": len(holds), "cash": round(alloc.cash, 2), "market_value": alloc.market_value}


# ── allocation lifecycle (sweep in / unwind out) ─────────────────────────────

class AllocError(Exception):
    pass


async def allocate(db, user, theme: Theme, account_number: str, amount: float) -> ThemeAllocation:
    """Commit `amount` to a new allocation (status pending); the reconciler invests it.
    LIVE (agentic account): real money — no sweep; the amount is RESERVED out of the account's
    buying power (the discretionary brain's pool = total − theme). PAPER: grandfathered sweep.
    Raises AllocError on a bad request."""
    from app.services.accounts import is_paper_number
    if theme.status not in ("live", "weakening"):
        raise AllocError("This theme isn't open for new capital right now.")
    acct = (await db.execute(select(Account).where(Account.account_number == account_number))).scalar_one_or_none()
    if not acct or acct.user_id != user.id:
        raise AllocError("Account not found.")
    amount = round(float(amount or 0), 2)
    if amount < 1:
        raise AllocError("Enter an amount of at least $1.")

    if is_paper_number(account_number):
        if amount > (acct.cash or 0) + 1e-6:                 # legacy paper — sweep from paper cash
            raise AllocError(f"Not enough cash — available ${acct.cash:,.2f}.")
        acct.cash -= amount
    else:
        if not themes_live_active():
            raise AllocError("Real-money theme investing isn't enabled yet.")
        if acct.kind != "agentic":
            raise AllocError("Themes trade on your connected agentic account.")
        # available = real buying power − cash already reserved to other theme allocations
        excl = await brain_exclusions(db, user.id, account_number)
        bp = (acct.buying_power if acct.buying_power is not None else acct.cash) or 0.0
        avail = max(0.0, bp) - excl["reserved_cash"]
        if amount > avail + 1e-6:
            raise AllocError(f"Not enough available buying power (${avail:,.2f}) after theme reservations.")
        # NO sweep — the money stays in the real account; the brain excludes it via alloc.cash

    alloc = ThemeAllocation(user_id=user.id, account=account_number, theme_id=theme.id,
                            committed_usd=amount, cash=amount, invested_usd=0.0, status="pending",
                            applied_version=0)
    db.add(alloc)
    await db.flush()
    logger.info("theme allocate: user=%s theme=%s $%.2f account=%s live=%s",
                user.id, theme.slug, amount, account_number, not is_paper_number(account_number))
    return alloc


async def brain_exclusions(db, user_id, account: str) -> dict:
    """What the discretionary brain must NOT count as its own on this account:
      • theme-held shares (attribution) — so it never sells or re-counts them, and
      • theme cash reserved-but-not-yet-deployed — carved out of its buying power.
    Returns {"holdings": {SYMBOL: qty}, "reserved_cash": float}. Its money pool = total − theme."""
    allocs = (await db.execute(select(ThemeAllocation).where(
        ThemeAllocation.user_id == user_id, ThemeAllocation.account == account,
        ThemeAllocation.status.in_(("pending", "active", "unwinding"))))).scalars().all()
    if not allocs:
        return {"holdings": {}, "reserved_cash": 0.0}
    reserved = sum(max(0.0, a.cash or 0.0) for a in allocs)
    rows = (await db.execute(select(ThemeHolding).where(
        ThemeHolding.allocation_id.in_([a.id for a in allocs])))).scalars().all()
    holdings: dict[str, float] = {}
    for h in rows:
        holdings[h.symbol.upper()] = holdings.get(h.symbol.upper(), 0.0) + (h.quantity or 0.0)
    return {"holdings": holdings, "reserved_cash": round(reserved, 2)}


async def unwind_allocation(db, alloc: ThemeAllocation, reason: str = "user exit") -> dict:
    """Mark an allocation unwinding and sell it out immediately (returns cash to the account)."""
    if alloc.status in ("closed",):
        return {"noop": True}
    theme = (await db.execute(select(Theme).where(Theme.id == alloc.theme_id))).scalar_one_or_none()
    alloc.status = "unwinding"
    alloc.close_reason = reason
    return await reconcile_allocation(db, alloc, theme) if theme else {"error": "theme missing"}


# ── background + scheduled passes ────────────────────────────────────────────

async def run_reconcile_one(alloc_id, *_ignore) -> None:
    """Background: reconcile a single allocation now (e.g. right after allocate). Own session."""
    from app.database import async_session
    async with async_session() as db:
        alloc = (await db.execute(select(ThemeAllocation).where(ThemeAllocation.id == alloc_id))).scalar_one_or_none()
        if not alloc or alloc.status == "closed":
            return
        theme = (await db.execute(select(Theme).where(Theme.id == alloc.theme_id))).scalar_one_or_none()
        if not theme:
            return
        try:
            await reconcile_allocation(db, alloc, theme)
            await db.commit()
        except Exception as e:
            logger.exception("reconcile_one failed for %s: %s", alloc_id, e)
            await db.rollback()


async def reconcile(db=None) -> dict:
    """Scheduled pass: reconcile every open allocation that needs it (new, basket-changed,
    unwinding, or whose theme is breaking → cross-user unwind). Own session if none given."""
    if db is None:
        from app.database import async_session
        async with async_session() as s:
            return await reconcile(s)
    allocs = (await db.execute(select(ThemeAllocation).where(ThemeAllocation.status.in_(_OPEN_STATUSES)))).scalars().all()
    if not allocs:
        return {"reconciled": 0}
    theme_ids = {a.theme_id for a in allocs}
    themes = {t.id: t for t in (await db.execute(select(Theme).where(Theme.id.in_(theme_ids)))).scalars().all()}
    done = 0
    for a in allocs:
        theme = themes.get(a.theme_id)
        if not theme:
            continue
        needs = (a.status in ("pending", "unwinding") or theme.status == "breaking"
                 or a.applied_version < theme.target_version)
        if not needs:
            continue
        try:
            await reconcile_allocation(db, a, theme)
            await db.commit()
            done += 1
        except Exception as e:
            logger.exception("reconcile failed for allocation %s: %s", a.id, e)
            await db.rollback()
    logger.info("theme reconcile: processed %d allocations", done)
    return {"reconciled": done}


async def revalue(db, alloc: ThemeAllocation) -> list[ThemeHolding]:
    """Re-price an allocation's holdings and refresh its market_value / unrealized_pnl
    (for a live 'My Themes' read). Caller commits. Returns the holdings."""
    holds = await _holdings(db, alloc.id)
    if holds:
        prices = await _prices([h.symbol for h in holds])
        for h in holds:
            if prices.get(h.symbol):
                h.last_price = prices[h.symbol]
        _mark(alloc, holds, prices)
    else:
        _mark(alloc, [], {})
    return holds


# ── serializers ───────────────────────────────────────────────────────────────

def holding_dict(h: ThemeHolding) -> dict:
    px = h.last_price or h.avg_cost
    return {"symbol": h.symbol, "quantity": round(h.quantity, 4), "avg_cost": round(h.avg_cost, 2),
            "last_price": round(px, 2) if px else None,
            "market_value": round(h.quantity * px, 2) if px else None,
            "unrealized_pnl": round(h.quantity * (px - h.avg_cost), 2) if px else None}


def allocation_dict(alloc: ThemeAllocation, theme: Theme | None = None, holdings=None) -> dict:
    total_pnl = (alloc.market_value - alloc.committed_usd) if alloc.market_value is not None else None
    d = {
        "id": str(alloc.id), "theme_id": str(alloc.theme_id), "account": alloc.account,
        "status": alloc.status, "committed_usd": round(alloc.committed_usd, 2), "cash": round(alloc.cash, 2),
        "invested_usd": round(alloc.invested_usd, 2), "market_value": alloc.market_value,
        "realized_pnl": round(alloc.realized_pnl, 2), "unrealized_pnl": alloc.unrealized_pnl,
        "total_pnl": round(total_pnl, 2) if total_pnl is not None else None,
        "total_pnl_pct": round(total_pnl / alloc.committed_usd * 100, 2) if (total_pnl is not None and alloc.committed_usd) else None,
        "applied_version": alloc.applied_version,
        "created_at": alloc.created_at.isoformat() if alloc.created_at else None,
        "closed_at": alloc.closed_at.isoformat() if alloc.closed_at else None,
        "close_reason": alloc.close_reason,
    }
    if theme is not None:
        d["theme"] = {"title": theme.title, "slug": theme.slug, "status": theme.status,
                      "health": theme.health, "conviction": theme.conviction, "hero_stat": theme.hero_stat}
    if holdings is not None:
        d["holdings"] = [holding_dict(h) for h in holdings]
    return d
