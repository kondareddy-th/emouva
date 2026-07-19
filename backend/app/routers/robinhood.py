"""Robinhood agentic-MCP OAuth connect flow (replaces robin_stocks login).

    GET  /api/robinhood/connect     -> {authorize_url}  (frontend redirects there)
    GET  /api/robinhood/callback    -> exchange code, store tokens, redirect to app
    GET  /api/robinhood/status      -> {connected, scope, expires_at}
    POST /api/robinhood/disconnect  -> revoke locally
    GET  /api/robinhood/portfolio   -> live read via the agentic MCP (per-user token)
"""
from __future__ import annotations

import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.services import crypto, robinhood_oauth as oauth, robinhood_store as store
from app.services import robinhood_portfolio as rp
from app.services.robinhood_mcp import MCPError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/robinhood", tags=["robinhood"])

FRONTEND_URL = os.getenv("EMOUVA_FRONTEND_URL", "http://localhost:5174")


@router.get("/connect")
async def connect(user=Depends(get_current_user)):
    """Start the OAuth flow. Returns the Robinhood authorize URL for the frontend to open."""
    client_id = await oauth.register_client()
    verifier, challenge = oauth.make_pkce()
    # Encrypted state carries the user id + PKCE verifier; opaque to Robinhood/browser.
    state = crypto.encrypt(json.dumps({"uid": str(user.id), "v": verifier}))
    return {"authorize_url": oauth.build_authorize_url(client_id, state, challenge)}


@router.get("/callback")
async def callback(code: str = "", state: str = "", error: str = "",
                   db: AsyncSession = Depends(get_db)):
    """OAuth redirect target. Exchanges the code and stores the user's tokens."""
    if error:
        logger.warning("Robinhood OAuth error: %s", error)
        return RedirectResponse(f"{FRONTEND_URL}/settings?robinhood=error")
    try:
        data = json.loads(crypto.decrypt(state))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    client_id = await oauth.register_client()
    try:
        tok = await oauth.exchange_code(code, data["v"], client_id)
    except Exception as e:
        logger.exception("Token exchange failed")
        return RedirectResponse(f"{FRONTEND_URL}/settings?robinhood=error")

    await store.save_tokens(db, data["uid"], client_id, tok)
    logger.info("Robinhood connected for user %s", data["uid"])
    return RedirectResponse(f"{FRONTEND_URL}/settings?robinhood=connected")


@router.get("/status")
async def status(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conn = await store.get_connection(db, user.id)
    return {
        "connected": conn is not None,
        "scope": conn.scope if conn else None,
        "expires_at": conn.expires_at.isoformat() if conn and conn.expires_at else None,
    }


@router.post("/disconnect")
async def disconnect(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await store.disconnect(db, user.id)
    return {"connected": False}


@router.get("/accounts")
async def accounts(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Active accounts for the dashboard account switcher — real Robinhood
    accounts plus the user's paper account(s) (marked is_paper). Paper accounts
    show even when Robinhood is disconnected."""
    from app.services import accounts as paper_svc

    real: list[dict] = []
    token = await store.get_valid_access_token(db, user.id)
    if token:
        try:
            real = await rp.get_accounts(token)
        except MCPError as e:
            logger.warning("accounts: Robinhood MCP error: %s", e)
    paper_accts = await paper_svc.list_for_switcher(db, user.id)
    return {"accounts": real + paper_accts}


@router.post("/sync")
async def sync_account(account: str | None = None, user=Depends(get_current_user),
                       db: AsyncSession = Depends(get_db)):
    """Reconcile a real Robinhood account's positions + cash into our store
    (source of truth = Robinhood). Defaults to the fenced agentic account. The
    agent also does this every cadence tick; this is the manual/on-demand path."""
    from app.services import accounts as acct_svc

    token = await store.get_valid_access_token(db, user.id)
    if not token:
        raise HTTPException(status_code=409, detail="Robinhood not connected")
    number = await rp.resolve_account_number(token, account or "agentic")
    if not number:
        raise HTTPException(status_code=404, detail="No such account")
    accts = await rp.get_accounts(token)
    is_ag = any(a["account_number"] == number and a.get("is_agentic") for a in accts)
    positions, summary = await acct_svc.sync_from_robinhood(
        db, user.id, token, number, kind="agentic" if is_ag else "robinhood",
        nickname="Agentic" if is_ag else "")
    acct = await acct_svc._load(db, number)
    return {"account_number": number, "kind": acct.kind, "positions_synced": len(positions),
            "summary": summary, "synced_at": acct.last_synced_at.isoformat() if acct.last_synced_at else None}


@router.get("/portfolio")
async def portfolio(account: str | None = None, user=Depends(get_current_user),
                    db: AsyncSession = Depends(get_db)):
    """Summary + positions for one account via the agentic MCP (per-user token).
    `account` may be a number, 'default', 'agentic', or omitted (-> default)."""
    token = await store.get_valid_access_token(db, user.id)
    if not token:
        raise HTTPException(status_code=409, detail="Robinhood not connected")
    try:
        acct = await rp.resolve_account_number(token, account)
        summary = await rp.get_summary(token, acct)
        positions = await rp.get_positions(token, acct)
    except MCPError as e:
        raise HTTPException(status_code=502, detail=f"Robinhood MCP error: {e}")
    return {"account_number": acct, "summary": summary, "positions": positions}
