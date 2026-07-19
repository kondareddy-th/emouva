"""Generic per-account position store.

Every account we track — paper (we own it) or a real Robinhood account (the
broker owns it) — is an ``accounts`` row with its holdings in ``account_positions``.
Adding a new account type later is just a new ``kind``; none of the storage,
reads, or valuation below is paper- or Robinhood-specific.

Source of truth:
  • paper   → internal. Fills (apply_fill) mutate cash + positions here directly.
  • broker  → Robinhood. We reconcile (sync_from_robinhood) on a cadence because
              the user may trade there directly; the broker always wins.

Reads mirror the Robinhood shapes (robinhood_portfolio.py) so the same
portfolio/risk UI works for any account. Stored positions are valued at live
quotes (yfinance, 60s cache) at read time.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Account, AccountPosition, AccountDeposit, User
from app.services.market_data import get_batch_quotes

logger = logging.getLogger(__name__)

PAPER_SUFFIX = "-paper"
STARTING_CASH = 100_000.0


def is_paper_number(account: str | None) -> bool:
    """Cheap syntactic check — paper account numbers end in ``-paper``."""
    return bool(account) and account.endswith(PAPER_SUFFIX)


async def _load(db: AsyncSession, account_number: str) -> Account | None:
    return (await db.execute(
        select(Account).where(Account.account_number == account_number)
    )).scalar_one_or_none()


async def _rows(db: AsyncSession, account_id, held_only: bool = True) -> list[AccountPosition]:
    q = select(AccountPosition).where(AccountPosition.account_id == account_id)
    if held_only:
        q = q.where(AccountPosition.quantity > 0)
    return list((await db.execute(q)).scalars().all())


# ── paper accounts ────────────────────────────────────────────────────────

async def list_for_user(db: AsyncSession, user_id) -> list[Account]:
    """The user's active PAPER accounts (one today; model is multi-capable)."""
    return list((await db.execute(
        select(Account).where(Account.user_id == user_id, Account.kind == "paper",
                              Account.active.is_(True)).order_by(Account.created_at)
    )).scalars().all())


async def list_for_switcher(db: AsyncSession, user_id) -> list[dict]:
    """Account-switcher dicts for the user's paper accounts (Robinhood-account shape + is_paper)."""
    return [{
        "account_number": a.account_number, "type": "paper", "nickname": a.nickname or "Paper",
        "is_default": False, "is_agentic": False, "is_paper": True,
    } for a in await list_for_user(db, user_id)]


async def create(db: AsyncSession, user: User, starting_cash: float = STARTING_CASH) -> Account:
    """Create the user's paper account — one active per user today. account_number
    is ``{username}-paper`` (suffixed -2, -3… if we ever allow more)."""
    existing = await list_for_user(db, user.id)
    if existing:
        return existing[0]
    base = f"{user.username}{PAPER_SUFFIX}"
    number, n = base, 2
    while await _load(db, number) is not None:
        number, n = f"{base}-{n}", n + 1
    acct = Account(
        user_id=user.id, account_number=number, kind="paper", source_of_truth="internal",
        nickname="Paper", cash=starting_cash, starting_cash=starting_cash, buying_power=starting_cash,
    )
    db.add(acct)
    await db.commit()
    await db.refresh(acct)
    logger.info("Created paper account %s for user %s", number, user.id)
    return acct


async def reset(db: AsyncSession, account_number: str) -> Account | None:
    """Wipe positions and restore starting cash — a fresh paper run."""
    acct = await _load(db, account_number)
    if not acct or acct.kind != "paper":
        return None
    for pos in await _rows(db, acct.id, held_only=False):
        await db.delete(pos)
    acct.cash = acct.starting_cash or STARTING_CASH
    acct.realized_pnl = 0.0
    await db.commit()
    await db.refresh(acct)
    return acct


async def deposit(db: AsyncSession, account_number: str, amount: float) -> Account | None:
    """Add paper money to a paper account. Raises both cash AND the funded
    baseline (starting_cash) so a deposit never reads as a gain; records the
    deposit for audit. Live accounts are funded through Robinhood, not here."""
    acct = await _load(db, account_number)
    if not acct or acct.kind != "paper" or amount <= 0:
        return None
    acct.cash += amount
    acct.starting_cash = (acct.starting_cash or 0.0) + amount
    db.add(AccountDeposit(account_id=acct.id, user_id=acct.user_id, amount=amount, kind="paper"))
    await db.commit()
    await db.refresh(acct)
    logger.info("Paper deposit $%.2f into %s", amount, account_number)
    return acct


def account_dict(acct: Account) -> dict:
    return {
        "account_number": acct.account_number, "nickname": acct.nickname or "Paper",
        "kind": acct.kind, "starting_cash": acct.starting_cash, "cash": round(acct.cash, 2),
        "realized_pnl": round(acct.realized_pnl, 2), "active": acct.active,
        "is_paper": acct.kind == "paper", "created_at": acct.created_at.isoformat(),
        "last_synced_at": acct.last_synced_at.isoformat() if acct.last_synced_at else None,
    }


# ── reads (any account kind) ───────────────────────────────────────────────

async def get_positions(db: AsyncSession, account_number: str) -> list[dict]:
    """Stored positions, valued at live quotes — dashboard Position shape."""
    acct = await _load(db, account_number)
    if not acct:
        return []
    rows = await _rows(db, acct.id)
    if not rows:
        return []
    quotes = await asyncio.to_thread(get_batch_quotes, [r.symbol for r in rows])
    qmap = {q["symbol"]: q for q in quotes}
    out: list[dict] = []
    for r in rows:
        q = qmap.get(r.symbol, {})
        price = float(q.get("price") or r.last_price or r.avg_cost)
        prev = float(q.get("previous_close") or price)
        out.append({
            "symbol": r.symbol, "name": r.symbol, "shares": r.quantity, "avg_cost": r.avg_cost,
            "current_price": price, "previous_close": prev, "sector": "Unknown",
            "sparkline": [], "conviction": 3,
            "equity": round(r.quantity * price, 2),
            "percent_change": round(((price - prev) / prev * 100) if prev else 0.0, 2),
            "equity_change": round(r.quantity * (price - prev), 2),
        })
    return out


async def get_summary(db: AsyncSession, account_number: str) -> dict:
    acct = await _load(db, account_number)
    if not acct:
        return {"total_value": 0, "daily_change": 0, "daily_change_pct": 0, "total_gain": 0,
                "total_gain_pct": 0, "buying_power": 0, "risk_score": 0, "source": "paper"}
    positions = await get_positions(db, account_number)
    holdings = sum(p["equity"] for p in positions)
    day_change = sum(p["equity_change"] for p in positions)
    total_value = acct.cash + holdings
    prev_value = total_value - day_change
    base = acct.starting_cash if acct.starting_cash is not None else total_value
    total_gain = total_value - base
    return {
        "total_value": round(total_value, 2),
        "daily_change": round(day_change, 2),
        "daily_change_pct": round((day_change / prev_value * 100) if prev_value else 0.0, 2),
        "total_gain": round(total_gain, 2),
        "total_gain_pct": round((total_gain / base * 100) if base else 0.0, 2),
        "buying_power": round(acct.cash, 2),
        "realized_pnl": round(acct.realized_pnl, 2),
        "risk_score": 0,
        "source": "paper" if acct.kind == "paper" else "stored",
    }


# ── writes: paper fills ─────────────────────────────────────────────────────

async def apply_fill(db: AsyncSession, account_number: str, symbol: str, side: str,
                     qty: float, price: float, source: str = "agent_fill") -> bool:
    """Apply a simulated (paper) fill: adjust cash, realized P&L, and the open
    lot. Commits. Returns True on success."""
    acct = await _load(db, account_number)
    if not acct or qty <= 0:
        return False
    pos = (await db.execute(select(AccountPosition).where(
        AccountPosition.account_id == acct.id, AccountPosition.symbol == symbol
    ))).scalar_one_or_none()
    if side == "buy":
        acct.cash -= qty * price
        if pos:
            new_q = pos.quantity + qty
            pos.avg_cost = (pos.quantity * pos.avg_cost + qty * price) / new_q if new_q else price
            pos.quantity = new_q
            pos.last_price = price
            pos.source = source
        else:
            db.add(AccountPosition(account_id=acct.id, user_id=acct.user_id, symbol=symbol,
                                   quantity=qty, avg_cost=price, last_price=price, source=source))
    else:  # sell
        sell_qty = min(qty, pos.quantity) if pos else 0.0
        if sell_qty <= 0:
            return False
        acct.cash += sell_qty * price
        acct.realized_pnl += sell_qty * (price - (pos.avg_cost if pos else price))
        pos.quantity -= sell_qty
        pos.last_price = price
        if pos.quantity <= 1e-9:
            await db.delete(pos)
    await db.commit()
    return True


# ── writes: broker reconciliation (Robinhood is source of truth) ────────────

async def get_or_create_broker_account(db: AsyncSession, user_id, account_number: str,
                                        kind: str, nickname: str = "") -> Account:
    acct = await _load(db, account_number)
    if acct is None:
        acct = Account(user_id=user_id, account_number=account_number, kind=kind,
                       source_of_truth="broker", nickname=nickname, cash=0.0)
        db.add(acct)
        await db.flush()
    elif acct.kind != kind or acct.nickname != (nickname or acct.nickname):
        acct.kind, acct.nickname = kind, nickname or acct.nickname
    return acct


async def sync_from_robinhood(db: AsyncSession, user_id, token: str, account_number: str,
                              kind: str = "robinhood", nickname: str = "") -> tuple[list[dict], dict]:
    """Reconcile a real Robinhood account into the store: overwrite stored
    positions + cash/equity from the live broker snapshot (the broker wins, since
    the user may have traded there directly). Returns the fresh (positions, summary).
    Best-effort: on any Robinhood error, returns the last stored snapshot."""
    from datetime import datetime, timezone
    from app.services import robinhood_portfolio as rp

    try:
        positions = await rp.get_positions(token, account_number)
        summary = await rp.get_summary(token, account_number)
    except Exception as e:
        logger.warning("sync_from_robinhood(%s) failed, using stored: %s", account_number, e)
        return await get_positions(db, account_number), await get_summary(db, account_number)

    acct = await get_or_create_broker_account(db, user_id, account_number, kind, nickname)
    # Reconcile cash/equity: cash = total_value - market value of holdings.
    pos_mv = sum(float(p.get("equity") or 0.0) for p in positions)
    equity = float(summary.get("total_value") or 0.0)
    acct.equity = equity
    acct.buying_power = float(summary.get("buying_power") or 0.0)
    acct.cash = max(0.0, equity - pos_mv)
    acct.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)

    # Overwrite the stored lots to match the broker exactly.
    existing = {p.symbol: p for p in await _rows(db, acct.id, held_only=False)}
    live_syms = set()
    for p in positions:
        sym = p["symbol"]
        live_syms.add(sym)
        row = existing.get(sym)
        qty = float(p.get("shares") or 0.0)
        avg = float(p.get("avg_cost") or 0.0)
        px = float(p.get("current_price") or 0.0)
        if row:
            row.quantity, row.avg_cost, row.last_price, row.source = qty, avg, px, "broker_sync"
        else:
            db.add(AccountPosition(account_id=acct.id, user_id=user_id, symbol=sym,
                                   quantity=qty, avg_cost=avg, last_price=px, source="broker_sync"))
    for sym, row in existing.items():           # positions closed on the broker
        if sym not in live_syms:
            await db.delete(row)
    await db.commit()
    return positions, summary
