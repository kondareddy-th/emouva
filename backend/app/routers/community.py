"""
Community — one public channel where users chat and share Spotify-Wrapped-style P&L cards.

Read is PUBLIC (logged-out visitors see the feed); posting requires sign-in. This lives on
the hosted emouva.com backend; local trading instances post to it via the emouva.com API.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_optional_user
from app.models.db import CommunityPost, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/community", tags=["community"])

MAX_BODY = 2000
VALID_KINDS = ("message", "pnl_card")


class PostOut(BaseModel):
    id: str
    kind: str
    author_name: str
    author_handle: str | None
    body: str | None
    stats: dict | None
    created_at: str
    is_mine: bool = False


class PostIn(BaseModel):
    kind: str = "message"           # "message" | "pnl_card"
    body: str | None = None
    stats: dict | None = None


def _to_out(p: CommunityPost, me_id=None) -> PostOut:
    return PostOut(
        id=str(p.id),
        kind=p.kind,
        author_name=p.author_name,
        author_handle=p.author_handle,
        body=p.body,
        stats=p.stats,
        created_at=p.created_at.isoformat(),
        is_mine=(me_id is not None and str(p.user_id) == str(me_id)),
    )


@router.get("/feed", response_model=list[PostOut])
async def feed(
    limit: int = 100,
    user=Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    """Public: newest-first slice of the single channel."""
    limit = max(1, min(limit, 200))
    res = await db.execute(
        select(CommunityPost).order_by(CommunityPost.created_at.desc()).limit(limit)
    )
    rows = list(res.scalars().all())
    me_id = user.id if user else None
    return [_to_out(p, me_id) for p in rows]


@router.post("/post", response_model=PostOut)
async def create_post(
    payload: PostIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kind = payload.kind if payload.kind in VALID_KINDS else "message"
    body = (payload.body or "").strip()[:MAX_BODY] or None
    if kind == "message" and not body:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    if kind == "pnl_card" and not payload.stats:
        raise HTTPException(status_code=400, detail="Missing P&L stats for the card.")
    post = CommunityPost(
        user_id=user.id,
        author_name=(user.display_name or user.username)[:100],
        author_handle=(user.public_id or user.username),
        kind=kind,
        body=body,
        stats=payload.stats if kind == "pnl_card" else None,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return _to_out(post, user.id)


@router.delete("/post/{post_id}")
async def delete_post(
    post_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(select(CommunityPost).where(CommunityPost.id == post_id))
    post = res.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found.")
    if str(post.user_id) != str(user.id):
        raise HTTPException(status_code=403, detail="You can only delete your own posts.")
    await db.delete(post)
    await db.commit()
    return {"ok": True}
