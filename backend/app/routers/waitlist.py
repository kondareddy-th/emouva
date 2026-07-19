

"""Waitlist email collection — no auth required."""

import logging
import re

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import WaitlistEmail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/waitlist", tags=["waitlist"])

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


class WaitlistRequest(BaseModel):
    email: str
    source: str = "landing"


@router.post("/")
async def join_waitlist(
    req: WaitlistRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add an email to the waitlist. Idempotent — duplicate emails return success."""
    email = req.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Invalid email address.")

    # Check if already exists
    result = await db.execute(
        select(WaitlistEmail).where(WaitlistEmail.email == email)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return {"message": "You're already on the list!", "status": "exists"}

    db.add(WaitlistEmail(email=email, source=req.source[:50]))
    await db.commit()
    logger.info("Waitlist signup: %s (source=%s)", email, req.source)

    return {"message": "You're on the list!", "status": "created"}
