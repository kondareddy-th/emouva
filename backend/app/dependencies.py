"""
Shared FastAPI dependencies.
"""

from datetime import date

from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services.auth import decode_token, decode_demo_token

ALLOWED_MODELS = {
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-6-20250929",
    "claude-opus-4-6-20250929",
}

# Rate limits for free-tier users (per day)
# NOTE: One "analysis" in the UI fires ~5 API calls (stock, thesis, bear-case,
# sentiment, report), so limit=15 ≈ 3 full analyses/day.
RATE_LIMITS = {
    "analysis": 15,  # ~5 endpoints per analysis × 3 analyses/day
    "advisor": 10,   # advisor chat messages
    "brief": 3,      # daily brief generation
}

# Demo (unauthenticated) rate limits — lower than signed-in users
DEMO_RATE_LIMITS = {
    "analysis": 15,  # ~5 endpoints per analysis × 3 analyses/day
    "advisor": 5,
    "brief": 1,
}


def has_full_access(user) -> bool:
    """Personal-mode gate: with RESTRICT_TRADING_TO unset (self-host default),
    everyone has full access; otherwise only the listed usernames do."""
    allowed = [u.strip() for u in settings.restrict_trading_to.split(",") if u.strip()]
    return not allowed or (user is not None and user.username in allowed)


async def require_full_access(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Router-level guard for trading/agent/themes on a personal hosted instance.
    Community + auth stay open to everyone."""
    # The Robinhood OAuth redirect arrives with no Authorization header — it is
    # authenticated by the encrypted `state` payload inside the endpoint itself.
    if request.url.path.endswith("/robinhood/callback"):
        return None
    user = await get_current_user(request, db)
    if not has_full_access(user):
        raise HTTPException(
            status_code=403,
            detail="This hosted instance is personal — trading features are limited to its owner. "
                   "Run Emouva locally (it's open source) to trade with your own account.",
        )
    return user


def get_api_key(request: Request) -> str:
    """Bring-your-own-key: prefer the user's Anthropic key sent per-request via the
    X-Anthropic-Key header (Settings → AI Token). Fall back to a server-side key if one
    is configured (hosted deployments); the open-source/local build ships without one."""
    header_key = request.headers.get("X-Anthropic-Key", "").strip()
    key = header_key or settings.anthropic_api_key or settings.anthropic_key
    if key:
        return key
    raise HTTPException(
        status_code=503,
        detail="No Anthropic API key found. Add your own key in Settings → AI Token to enable AI features.",
    )


def get_claude_model(request: Request) -> str:
    """Extract and validate the Claude model from the X-Claude-Model header."""
    model = request.headers.get("X-Claude-Model", "")
    if model and model in ALLOWED_MODELS:
        return model
    return settings.claude_model


def rate_limit(endpoint_type: str):
    """Factory returning a dependency that enforces daily rate limits.
    Free-tier users have daily limits. Premium users (future) will be unlimited.
    """
    async def _check(
        request: Request,
        db: AsyncSession = Depends(get_db),
    ) -> None:
        # No server key configured → service unavailable
        if not settings.anthropic_api_key:
            return

        # ── Path A: Authenticated user (Bearer JWT) ──
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            payload = decode_token(auth_header[7:])
            if not payload or not payload.get("sub"):
                raise HTTPException(status_code=401, detail="Invalid or expired token.")

            user_id = payload["sub"]

            # Premium users bypass rate limits
            from app.models.db import User, ApiUsage

            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()
            if user and user.tier == "premium":
                return

            today = date.today().isoformat()
            limit = RATE_LIMITS.get(endpoint_type, 3)

            result = await db.execute(
                select(ApiUsage).where(
                    ApiUsage.user_id == user_id,
                    ApiUsage.endpoint_type == endpoint_type,
                    ApiUsage.usage_date == today,
                )
            )
            usage = result.scalar_one_or_none()

            if usage and usage.count >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="Daily free-tier limit reached. Upgrade to Premium for unlimited access.",
                )

            if usage:
                usage.count += 1
            else:
                db.add(ApiUsage(
                    user_id=user_id,
                    endpoint_type=endpoint_type,
                    usage_date=today,
                    count=1,
                ))
            await db.commit()
            return

        # ── Path B: Demo user (X-Demo-Token) ──
        demo_header = request.headers.get("X-Demo-Token", "")
        if demo_header:
            payload = decode_demo_token(demo_header)
            if not payload:
                raise HTTPException(
                    status_code=401,
                    detail="Demo session expired. Please enter your email again.",
                )

            email = payload["email"]
            today = date.today().isoformat()
            limit = DEMO_RATE_LIMITS.get(endpoint_type, 3)

            from app.models.db import DemoUsage

            result = await db.execute(
                select(DemoUsage).where(
                    DemoUsage.email == email,
                    DemoUsage.endpoint_type == endpoint_type,
                    DemoUsage.usage_date == today,
                )
            )
            usage = result.scalar_one_or_none()

            if usage and usage.count >= limit:
                raise HTTPException(
                    status_code=429,
                    detail="You've used all 3 free analyses today. Create a free account for more!",
                )

            if usage:
                usage.count += 1
            else:
                db.add(DemoUsage(
                    email=email,
                    endpoint_type=endpoint_type,
                    usage_date=today,
                    count=1,
                ))
            await db.commit()
            return

        # ── No auth at all ──
        raise HTTPException(status_code=401, detail="Sign in required for free AI access.")

    return _check


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Extract and validate JWT from Authorization header. Returns User ORM object."""
    from app.models.db import User

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_optional_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Same as get_current_user but returns None if no token (backward compat)."""
    from app.models.db import User

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header[7:]
    payload = decode_token(token)
    if payload is None:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
