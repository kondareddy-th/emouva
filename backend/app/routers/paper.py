"""Paper ("paper money") account management.

    GET   /api/paper/accounts                         -> list the user's paper accounts
    POST  /api/paper/accounts                         -> create one ({username}-paper)
    POST  /api/paper/accounts/{number}/reset          -> wipe positions, restore cash

One active paper account per user today; the backend model is multi-capable for
the future. The agent trades this account when agent_mode=paper.
"""
import logging

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.services import accounts as paper

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/paper", tags=["paper"])


@router.get("/accounts")
async def list_accounts(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    accts = await paper.list_for_user(db, user.id)
    return {"accounts": [paper.account_dict(a) for a in accts]}


@router.post("/accounts")
async def create_account(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create the user's paper account (idempotent — returns the existing one if
    already created)."""
    acct = await paper.create(db, user)
    return paper.account_dict(acct)


@router.post("/accounts/{account_number}/reset")
async def reset_account(account_number: str, user=Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    # Ownership check: the number must belong to this user.
    owned = {a.account_number for a in await paper.list_for_user(db, user.id)}
    if account_number not in owned:
        raise HTTPException(404, "No such paper account")
    acct = await paper.reset(db, account_number)
    return paper.account_dict(acct)


@router.post("/accounts/{account_number}/deposit")
async def deposit(account_number: str, payload: dict = Body(...), user=Depends(get_current_user),
                  db: AsyncSession = Depends(get_db)):
    """Add paper money (a simulated deposit). Live accounts fund via Robinhood."""
    owned = {a.account_number for a in await paper.list_for_user(db, user.id)}
    if account_number not in owned:
        raise HTTPException(404, "No such paper account")
    try:
        amount = float(payload.get("amount") or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount <= 0:
        raise HTTPException(400, "amount must be a positive number")
    acct = await paper.deposit(db, account_number, amount)
    return paper.account_dict(acct)
