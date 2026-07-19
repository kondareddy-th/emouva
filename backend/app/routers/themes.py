"""Polytrade — user-facing themes API (M2).

Browse live themes, allocate capital (a cash sweep from the paper account, invested by
the reconciler), watch 'My Themes' with live P&L, and unwind. All theme execution is
paper-only for now (see docs/POLYTRADE.md §7). Admin origination/monitoring lives in
routers/admin.py; this router is the user surface the M3 UI builds on.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models.db import (Theme, ThemeConstituent, ThemeEvent, ThemeAllocation,
                           ThemeFollow, ThemeComment, ThemeCommentLike, User)
from app.services.agent import themes as themes_svc
from app.services.agent import theme_exec

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/themes", tags=["themes"])

# Themes users can see + fund. Draft (unpublished) and closed are hidden.
_PUBLIC_STATUSES = ("live", "weakening", "breaking")


async def _social(db, theme_id, user_id=None) -> dict:
    """Aggregate social proof — # investors + committed, follower count, comment count."""
    inv = (await db.execute(select(func.count(), func.coalesce(func.sum(ThemeAllocation.committed_usd), 0.0))
           .where(ThemeAllocation.theme_id == theme_id,
                  ThemeAllocation.status.in_(("pending", "active", "unwinding"))))).one()
    n_followers = (await db.execute(select(func.count()).select_from(ThemeFollow)
                   .where(ThemeFollow.theme_id == theme_id))).scalar() or 0
    n_comments = (await db.execute(select(func.count()).select_from(ThemeComment)
                  .where(ThemeComment.theme_id == theme_id))).scalar() or 0
    i_follow = False
    if user_id is not None:
        i_follow = bool((await db.execute(select(ThemeFollow.id).where(
            ThemeFollow.theme_id == theme_id, ThemeFollow.user_id == user_id))).first())
    return {"n_investors": int(inv[0] or 0), "total_committed": round(float(inv[1] or 0.0), 2),
            "n_followers": int(n_followers), "n_comments": int(n_comments), "i_follow": i_follow}


async def _load_public(db, id_or_slug: str) -> Theme:
    q = select(Theme).where(Theme.slug == id_or_slug)
    t = (await db.execute(q)).scalar_one_or_none()
    if not t:
        try:
            t = (await db.execute(select(Theme).where(Theme.id == id_or_slug))).scalar_one_or_none()
        except Exception:
            t = None
    if not t or t.status not in _PUBLIC_STATUSES:
        raise HTTPException(404, "Theme not found")
    return t


@router.get("")
async def list_themes(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The live theme feed — best conviction first."""
    rows = (await db.execute(select(Theme).where(Theme.status.in_(_PUBLIC_STATUSES))
            .order_by(Theme.conviction.desc(), Theme.updated_at.desc()))).scalars().all()
    out = []
    for t in rows:
        n_con = (await db.execute(select(func.count()).select_from(ThemeConstituent)
                 .where(ThemeConstituent.theme_id == t.id, ThemeConstituent.status == "active"))).scalar() or 0
        out.append({**themes_svc.theme_dict(t), **(await _social(db, t.id, user.id)), "n_constituents": int(n_con)})
    return {"themes": out}


@router.get("/allocations/mine")
async def my_allocations(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """My Themes — active allocations (live-revalued) + recently closed ones."""
    allocs = (await db.execute(select(ThemeAllocation).where(ThemeAllocation.user_id == user.id)
              .order_by(ThemeAllocation.created_at.desc()))).scalars().all()
    theme_ids = {a.theme_id for a in allocs}
    themes = {t.id: t for t in (await db.execute(select(Theme).where(Theme.id.in_(theme_ids)))).scalars().all()} if theme_ids else {}
    out = []
    for a in allocs:
        holds = None
        if a.status in ("pending", "active", "unwinding"):
            holds = await theme_exec.revalue(db, a)
        out.append(theme_exec.allocation_dict(a, theme=themes.get(a.theme_id), holdings=holds))
    await db.commit()
    return {"allocations": out}


@router.get("/{id_or_slug}")
async def get_theme(id_or_slug: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Full theme card — thesis, basket, performance, activity feed + my stake if any."""
    t = await _load_public(db, id_or_slug)
    cons = (await db.execute(select(ThemeConstituent).where(ThemeConstituent.theme_id == t.id,
            ThemeConstituent.status == "active").order_by(ThemeConstituent.target_weight.desc()))).scalars().all()
    events = (await db.execute(select(ThemeEvent).where(ThemeEvent.theme_id == t.id)
              .order_by(ThemeEvent.created_at.desc()).limit(30))).scalars().all()
    mine = (await db.execute(select(ThemeAllocation).where(
        ThemeAllocation.theme_id == t.id, ThemeAllocation.user_id == user.id,
        ThemeAllocation.status.in_(("pending", "active", "unwinding"))))).scalars().first()
    d = {**themes_svc.theme_dict(t, constituents=cons, events=events), **(await _social(db, t.id, user.id))}
    if mine:
        holds = await theme_exec.revalue(db, mine)
        await db.commit()
        d["my_allocation"] = theme_exec.allocation_dict(mine, holdings=holds)
    return d


@router.get("/account/summary")
async def account_summary(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The account themes trade on (the connected agentic/Robinhood account) + the buying power
    available for a new allocation (real buying power minus cash already reserved to themes)."""
    from app.models.db import Account
    ag = (await db.execute(select(Account).where(
        Account.user_id == user.id, Account.kind == "agentic", Account.active.is_(True))
        .order_by(Account.created_at))).scalars().first()
    live = theme_exec.themes_live_active()
    if not ag:
        return {"connected": False, "live": live, "buying_power": 0.0, "available": 0.0}
    excl = await theme_exec.brain_exclusions(db, user.id, ag.account_number)
    bp = max(0.0, float((ag.buying_power if ag.buying_power is not None else ag.cash) or 0.0))
    return {"connected": True, "live": live, "account": ag.account_number,
            "buying_power": round(bp, 2), "available": round(max(0.0, bp - excl["reserved_cash"]), 2)}


@router.post("/{id_or_slug}/allocate")
async def allocate(id_or_slug: str, background: BackgroundTasks, payload: dict = Body(...),
                   user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Fund a theme; the reconciler invests it at target weights on your agentic account."""
    from app.models.db import Account
    t = await _load_public(db, id_or_slug)
    amount = payload.get("amount")
    account = payload.get("account")
    if not account:
        # Themes trade real money on the connected agentic (Robinhood) account — no paper.
        ag = (await db.execute(select(Account).where(
            Account.user_id == user.id, Account.kind == "agentic", Account.active.is_(True))
            .order_by(Account.created_at))).scalars().first()
        if not ag:
            raise HTTPException(400, "Connect your Robinhood account to invest in themes.")
        account = ag.account_number
    try:
        alloc = await theme_exec.allocate(db, user, t, account, amount)
    except theme_exec.AllocError as e:
        raise HTTPException(400, str(e))
    await db.commit()
    background.add_task(theme_exec.run_reconcile_one, str(alloc.id))
    return {"allocation": theme_exec.allocation_dict(alloc, theme=t), "investing": True}


@router.post("/allocations/{alloc_id}/unwind")
async def unwind(alloc_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Exit a theme now — sell the basket and return cash to the account."""
    alloc = (await db.execute(select(ThemeAllocation).where(ThemeAllocation.id == alloc_id))).scalar_one_or_none()
    if not alloc or alloc.user_id != user.id:
        raise HTTPException(404, "Allocation not found")
    if alloc.status == "closed":
        raise HTTPException(409, "Already closed")
    res = await theme_exec.unwind_allocation(db, alloc, reason="user exit")
    await db.commit()
    return {"unwound": True, "result": res, "allocation": theme_exec.allocation_dict(alloc)}


# ── social: follow + comments ────────────────────────────────────────────────

@router.post("/{id_or_slug}/follow")
async def follow(id_or_slug: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Toggle following a theme (watch without funding). Returns the new state + count."""
    t = await _load_public(db, id_or_slug)
    existing = (await db.execute(select(ThemeFollow).where(
        ThemeFollow.theme_id == t.id, ThemeFollow.user_id == user.id))).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        following = False
    else:
        db.add(ThemeFollow(theme_id=t.id, user_id=user.id))
        following = True
    await db.commit()
    n = (await db.execute(select(func.count()).select_from(ThemeFollow).where(ThemeFollow.theme_id == t.id))).scalar() or 0
    return {"following": following, "n_followers": int(n)}


@router.get("/{id_or_slug}/comments")
async def list_comments(id_or_slug: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """The theme's discussion wall — newest first, with author + like counts."""
    t = await _load_public(db, id_or_slug)
    rows = (await db.execute(select(ThemeComment, User.display_name, User.username)
            .join(User, User.id == ThemeComment.user_id)
            .where(ThemeComment.theme_id == t.id)
            .order_by(ThemeComment.created_at.desc()).limit(100))).all()
    ids = [c.id for c, _, _ in rows]
    likes: dict = {}
    mine: set = set()
    if ids:
        for cid, cnt in (await db.execute(select(ThemeCommentLike.comment_id, func.count())
                         .where(ThemeCommentLike.comment_id.in_(ids)).group_by(ThemeCommentLike.comment_id))).all():
            likes[cid] = int(cnt)
        mine = {r[0] for r in (await db.execute(select(ThemeCommentLike.comment_id).where(
            ThemeCommentLike.comment_id.in_(ids), ThemeCommentLike.user_id == user.id))).all()}
    return {"comments": [{
        "id": str(c.id), "body": c.body, "author": dname or uname, "mine": c.user_id == user.id,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "likes": likes.get(c.id, 0), "i_liked": c.id in mine,
    } for c, dname, uname in rows]}


@router.post("/{id_or_slug}/comments")
async def post_comment(id_or_slug: str, payload: dict = Body(...),
                       user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    t = await _load_public(db, id_or_slug)
    body = (payload.get("body") or "").strip()[:1000]
    if not body:
        raise HTTPException(400, "Comment can't be empty")
    c = ThemeComment(theme_id=t.id, user_id=user.id, body=body)
    db.add(c)
    await db.commit()
    return {"id": str(c.id), "body": c.body, "author": user.display_name or user.username,
            "mine": True, "created_at": c.created_at.isoformat() if c.created_at else None, "likes": 0, "i_liked": False}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = (await db.execute(select(ThemeComment).where(ThemeComment.id == comment_id))).scalar_one_or_none()
    if not c or c.user_id != user.id:
        raise HTTPException(404, "Comment not found")
    await db.delete(c)
    await db.commit()
    return {"deleted": True}


@router.post("/comments/{comment_id}/like")
async def like_comment(comment_id: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = (await db.execute(select(ThemeComment).where(ThemeComment.id == comment_id))).scalar_one_or_none()
    if not c:
        raise HTTPException(404, "Comment not found")
    existing = (await db.execute(select(ThemeCommentLike).where(
        ThemeCommentLike.comment_id == c.id, ThemeCommentLike.user_id == user.id))).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        liked = False
    else:
        db.add(ThemeCommentLike(comment_id=c.id, user_id=user.id))
        liked = True
    await db.commit()
    n = (await db.execute(select(func.count()).select_from(ThemeCommentLike).where(ThemeCommentLike.comment_id == c.id))).scalar() or 0
    return {"liked": liked, "likes": int(n)}
