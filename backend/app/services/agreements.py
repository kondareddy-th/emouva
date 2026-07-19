"""Versioned user agreements — currently the live-trading T&C that must be
accepted before a user can switch the agent to live (real-money) execution.

Every accept/reject is stored (doc, version, user, time, status) in
`user_agreements` for audit. Bump LIVE_TC_VERSION when the terms change — users
must re-accept the new version before live continues.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import UserAgreement

LIVE_TC_DOC = "live_trading"
LIVE_TC_VERSION = "1.0"
LIVE_TC_TITLE = "Live trading — terms you must accept"
LIVE_TC_TEXT = """\
By enabling LIVE trading you authorize Emouva's agent ("the Partner") to place \
REAL orders using REAL money in your dedicated Robinhood agentic account.

1. AUTOMATIC APPROVAL UNDER YOUR CAP. You authorize the Partner to place orders \
automatically — without asking you each time — whenever the order's notional is \
at or below the per-order cap you set ("Max per live order"). You can change this \
cap or turn it to $0 at any time.

2. LARGER ORDERS STILL ASK. Any order above your approval threshold is held for \
your explicit approval in the Ledger before it is placed.

3. YOU STAY IN CONTROL. You can pause the Partner or switch back to paper at any \
time; pausing cancels any pending orders. The agent only ever trades the fenced \
agentic account, never your other accounts.

4. RISK. Trading involves the risk of loss, including loss of principal. Past and \
simulated (paper) performance does not guarantee future results. Emouva is a tool, \
not a broker or investment adviser; execution is through Robinhood under its terms, \
and you are solely responsible for your account and decisions.

Accepting records your consent (version, identity, and time). Declining leaves the \
agent in paper mode.
"""


async def has_accepted(db: AsyncSession, user_id, doc: str, version: str) -> bool:
    row = (await db.execute(
        select(UserAgreement.id).where(
            UserAgreement.user_id == user_id, UserAgreement.doc == doc,
            UserAgreement.version == version, UserAgreement.status == "accepted",
        )
    )).first()
    return row is not None


async def record(db: AsyncSession, user_id, doc: str, version: str, status: str) -> UserAgreement:
    ag = UserAgreement(user_id=user_id, doc=doc, version=version,
                       status="accepted" if status == "accepted" else "rejected")
    db.add(ag)
    await db.commit()
    await db.refresh(ag)
    return ag


def live_tc_payload(accepted: bool) -> dict:
    return {"doc": LIVE_TC_DOC, "version": LIVE_TC_VERSION, "title": LIVE_TC_TITLE,
            "text": LIVE_TC_TEXT, "accepted": accepted}
