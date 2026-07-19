

"""
Demo access — email-gated, no signup required.
"""

import logging
import re
from datetime import date

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import WaitlistEmail, DemoUsage
from app.services.auth import create_demo_token, decode_demo_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/demo", tags=["demo"])

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

DEMO_RATE_LIMITS = {
    "analysis": 15,  # ~5 endpoints per analysis x 3 analyses/day
    "advisor": 5,
    "brief": 1,
}


class DemoStartRequest(BaseModel):
    email: str


class DemoStartResponse(BaseModel):
    token: str
    email: str
    message: str


class DemoUsageResponse(BaseModel):
    email: str
    used: int
    limit: int
    remaining: int


@router.post("/start", response_model=DemoStartResponse)
async def start_demo(
    req: DemoStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Accept email, store it, return a demo JWT."""
    email = req.email.strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    # Store in waitlist_emails (idempotent)
    result = await db.execute(
        select(WaitlistEmail).where(WaitlistEmail.email == email)
    )
    existing = result.scalar_one_or_none()

    if not existing:
        db.add(WaitlistEmail(email=email, source="demo"))
        await db.commit()
        logger.info("Demo signup: %s", email)
    elif existing.source == "landing":
        existing.source = "demo"
        await db.commit()

    token = create_demo_token(email)
    return DemoStartResponse(
        token=token,
        email=email,
        message="Welcome! You have 3 free AI analyses today.",
    )


@router.get("/usage", response_model=DemoUsageResponse)
async def get_demo_usage(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Check how many analysis endpoint calls the demo user has used today."""
    demo_header = request.headers.get("X-Demo-Token", "")
    if not demo_header:
        raise HTTPException(status_code=401, detail="Demo token required.")

    payload = decode_demo_token(demo_header)
    if not payload:
        raise HTTPException(status_code=401, detail="Demo session expired. Please enter your email again.")

    email = payload["email"]
    endpoint_type = "analysis"
    today = date.today().isoformat()
    limit = DEMO_RATE_LIMITS.get(endpoint_type, 15)

    result = await db.execute(
        select(DemoUsage).where(
            DemoUsage.email == email,
            DemoUsage.endpoint_type == endpoint_type,
            DemoUsage.usage_date == today,
        )
    )
    usage = result.scalar_one_or_none()
    used = usage.count if usage else 0

    return DemoUsageResponse(
        email=email,
        used=used,
        limit=limit,
        remaining=max(0, limit - used),
    )
