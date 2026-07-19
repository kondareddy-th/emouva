


"""
User authentication endpoints — signup, login, profile.
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import User
from app.services.auth import hash_password, verify_password, create_token
from app.services.ids import gen_public_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


# ── Request / Response schemas ───────────────────────────────

class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(min_length=5, max_length=255, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    password: str = Field(min_length=6, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: dict


class UserProfile(BaseModel):
    id: str
    public_id: str | None = None
    username: str
    display_name: str
    robinhood_connected: bool
    tier: str = "free"


async def _unique_public_id(db: AsyncSession) -> str:
    """A public id not already taken (retry covers the rare collision)."""
    for _ in range(5):
        pid = gen_public_id()
        if (await db.execute(select(User).where(User.public_id == pid))).scalar_one_or_none() is None:
            return pid
    return gen_public_id()  # astronomically unlikely to reach here


def _user_dict(user: User) -> dict:
    from app.dependencies import has_full_access
    return {
        "id": str(user.id),
        "public_id": user.public_id,
        "username": user.username,
        "display_name": user.display_name,
        "robinhood_connected": user.robinhood_connected,
        "tier": user.tier,
        # False only on a personal hosted instance (RESTRICT_TRADING_TO set) for
        # non-owner accounts — the frontend then routes them to the community.
        "full_access": has_full_access(user),
    }


# ── Endpoints ────────────────────────────────────────────────

@router.post("/signup", response_model=AuthResponse)
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    """Create a new user account."""
    # Check if username taken
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already taken")

    # Check if email taken
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        public_id=await _unique_public_id(db),
        username=req.username,
        email=req.email,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_token(str(user.id), user.username)
    logger.info("User created: %s (%s)", user.username, user.public_id)
    return AuthResponse(token=token, user=_user_dict(user))


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate and return JWT token."""
    result = await db.execute(select(User).where(User.username == req.username))
    user = result.scalar_one_or_none()

    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    # Backfill a public id for legacy accounts created before the column existed.
    if not user.public_id:
        user.public_id = await _unique_public_id(db)
        await db.commit()
        await db.refresh(user)

    token = create_token(str(user.id), user.username)
    logger.info("User logged in: %s", user.username)
    return AuthResponse(token=token, user=_user_dict(user))


@router.get("/me", response_model=UserProfile)
async def get_profile(user: User = Depends(get_current_user)):
    """Get the current user's profile."""
    return UserProfile(
        id=str(user.id),
        public_id=user.public_id,
        username=user.username,
        display_name=user.display_name,
        robinhood_connected=user.robinhood_connected,
        tier=user.tier,
    )


@router.get("/verify")
async def verify_token(user: User = Depends(get_current_user)):
    """Lightweight token verification. Returns 200 if valid, 401 if expired/invalid."""
    return {"valid": True, "user": _user_dict(user)}
