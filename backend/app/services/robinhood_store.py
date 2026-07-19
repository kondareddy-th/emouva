"""Per-user Robinhood OAuth token vault (encrypted) with auto-refresh."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import RobinhoodConnection, User
from app.services import crypto, robinhood_oauth


def _uid(user_id) -> uuid.UUID:
    return user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))


async def save_tokens(db: AsyncSession, user_id, client_id: str, tok: dict) -> None:
    uid = _uid(user_id)
    access = tok["access_token"]
    refresh = tok.get("refresh_token")
    expires_at = datetime.utcnow() + timedelta(seconds=int(tok.get("expires_in", 3600)))

    conn = await db.get(RobinhoodConnection, uid)
    if conn is None:
        conn = RobinhoodConnection(user_id=uid)
        db.add(conn)
    conn.client_id = client_id
    conn.access_token_enc = crypto.encrypt(access)
    conn.refresh_token_enc = crypto.encrypt(refresh) if refresh else None
    conn.scope = tok.get("scope")
    conn.expires_at = expires_at

    user = await db.get(User, uid)
    if user:
        user.robinhood_connected = True
    await db.commit()


async def get_connection(db: AsyncSession, user_id) -> RobinhoodConnection | None:
    return await db.get(RobinhoodConnection, _uid(user_id))


async def get_valid_access_token(db: AsyncSession, user_id) -> str | None:
    conn = await db.get(RobinhoodConnection, _uid(user_id))
    if conn is None:
        return None
    # Refresh if expired / about to expire and we have a refresh token.
    soon = datetime.utcnow() + timedelta(seconds=60)
    if conn.expires_at and conn.expires_at <= soon and conn.refresh_token_enc:
        tok = await robinhood_oauth.refresh(crypto.decrypt(conn.refresh_token_enc), conn.client_id)
        await save_tokens(db, user_id, conn.client_id, tok)
        return tok["access_token"]
    return crypto.decrypt(conn.access_token_enc)


async def disconnect(db: AsyncSession, user_id) -> None:
    uid = _uid(user_id)
    conn = await db.get(RobinhoodConnection, uid)
    if conn:
        await db.delete(conn)
    user = await db.get(User, uid)
    if user:
        user.robinhood_connected = False
    await db.commit()
