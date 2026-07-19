"""Admin authentication — dedicated admin accounts, separate from user accounts.
Same JWT secret, but tokens carry typ='admin' and resolve against the `admins`
table; only status='active' admins are authorized. New admins are 'pending' until
an active admin approves them."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.db import Admin

ALGO = "HS256"


def create_admin_token(admin_id: str, email: str) -> str:
    payload = {"sub": admin_id, "email": email, "typ": "admin",
               "exp": datetime.utcnow() + timedelta(days=7)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)


def decode_admin_token(token: str) -> dict | None:
    try:
        p = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
        return p if p.get("typ") == "admin" else None
    except JWTError:
        return None


async def get_current_admin(request: Request, db: AsyncSession = Depends(get_db)) -> Admin:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Admin authentication required")
    p = decode_admin_token(auth[7:])
    if not p or not p.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid or expired admin token")
    admin = (await db.execute(select(Admin).where(Admin.id == p["sub"]))).scalar_one_or_none()
    if not admin or admin.status != "active":
        raise HTTPException(status_code=403, detail="Admin account is not active")
    return admin


def admin_dict(a: Admin) -> dict:
    return {"id": str(a.id), "email": a.email, "name": a.name, "status": a.status,
            "is_root": a.is_root, "created_at": a.created_at.isoformat()}
