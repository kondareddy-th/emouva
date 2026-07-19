"""Admin API — dedicated admin accounts (compliance/audit) + the central
opportunity directory ("the secret engine"). Admins sign up as pending and are
approved by an existing active admin. Directory + reasoning + chat are added in
the central-intelligence layer; this file owns accounts + the directory reads.
"""
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.db import Admin, Opportunity, Theme, ThemeConstituent, ThemeEvent, ThemeAllocation
from app.services.auth import hash_password, verify_password
from app.services import admin_auth
from app.services.admin_auth import get_current_admin, admin_dict

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── accounts ────────────────────────────────────────────────────────────────

@router.post("/signup")
async def signup(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """Request an admin account — created as 'pending' until an active admin approves.

    Self-host bootstrap: when NO active admin exists yet (a fresh install), the
    first signup becomes the active root admin automatically — otherwise a new
    deployment could never approve anyone."""
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    if not email or len(password) < 8:
        raise HTTPException(400, "email and an 8+ char password required")
    if (await db.execute(select(Admin).where(Admin.email == email))).scalar_one_or_none():
        raise HTTPException(409, "An admin request with that email already exists")
    has_active = (await db.execute(
        select(func.count()).select_from(Admin).where(Admin.status == "active"))).scalar() or 0
    if has_active:
        a = Admin(email=email, name=payload.get("name") or "",
                  password_hash=hash_password(password), status="pending")
        db.add(a)
        await db.commit()
        return {"status": "pending", "message": "Your admin request awaits approval by an existing admin."}
    a = Admin(email=email, name=payload.get("name") or "",
              password_hash=hash_password(password), status="active",
              is_root=True, approved_at=datetime.utcnow())
    db.add(a)
    await db.commit()
    logger.info("bootstrap: first admin %s auto-activated as root", email)
    return {"status": "active", "message": "You are the first admin — your account is active (root)."}


@router.post("/login")
async def login(payload: dict = Body(...), db: AsyncSession = Depends(get_db)):
    email = (payload.get("email") or "").strip().lower()
    a = (await db.execute(select(Admin).where(Admin.email == email))).scalar_one_or_none()
    if not a or not verify_password(payload.get("password") or "", a.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if a.status == "pending":
        raise HTTPException(403, "Your admin account is still pending approval")
    if a.status != "active":
        raise HTTPException(403, "Your admin account is not active")
    return {"token": admin_auth.create_admin_token(str(a.id), a.email), "admin": admin_dict(a)}


@router.get("/me")
async def me(admin=Depends(get_current_admin)):
    return admin_dict(admin)


@router.get("/admins")
async def list_admins(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Admin).order_by(Admin.created_at))).scalars().all()
    return {"admins": [admin_dict(a) for a in rows]}


@router.post("/admins/{admin_id}/approve")
async def approve_admin(admin_id: str, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    a = (await db.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "No such admin request")
    a.status = "active"
    a.approved_by = admin.id
    a.approved_at = datetime.utcnow()
    await db.commit()
    return admin_dict(a)


@router.post("/admins/{admin_id}/reject")
async def reject_admin(admin_id: str, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    a = (await db.execute(select(Admin).where(Admin.id == admin_id))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, "No such admin request")
    if a.is_root:
        raise HTTPException(400, "Cannot reject the root admin")
    a.status = "rejected"
    await db.commit()
    return admin_dict(a)


# ── central opportunity directory (reasoning) ────────────────────────────────

def _opp_admin_dict(o: Opportunity) -> dict:
    return {"symbol": o.symbol, "name": o.name, "sector": o.sector, "source": o.source,
            "last_price": o.last_price, "market_cap": o.market_cap, "margin_pct": o.margin_pct,
            "fair_value": o.fv_conservative, "fv_base": o.fv_base, "fv_low": o.fv_low, "fv_high": o.fv_high,
            "confident": o.fv_confident, "stats": o.stats, "stats_pass": o.stats_pass,
            "thesis": o.central_thesis, "falsifiers": o.falsifiers or [], "red_team": o.red_team or [],
            "growth": o.growth, "future_growth": o.future_growth, "growth_exception": o.growth_exception,
            "understood": o.understood, "category": o.category,
            "score": o.score, "sector_rank": o.sector_rank,
            "score_breakdown": (o.meta or {}).get("score_breakdown"),
            "trend": (o.meta or {}).get("trend"),
            "admin_notes": o.admin_notes, "analysis_status": o.analysis_status,
            "news": (o.meta or {}).get("news"),
            "last_analyzed_at": o.last_analyzed_at.isoformat() if o.last_analyzed_at else None}


@router.get("/opportunities")
async def opportunities(category: int | None = None, limit: int = 500,
                        admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """The full central directory with reasoning — admin-only."""
    q = select(Opportunity)
    if category is not None:
        q = q.where(Opportunity.category == category)
    # best-rated first (score), then margin as a fallback for un-scored rows
    rows = (await db.execute(q.order_by(
        Opportunity.score.desc().nullslast(),
        Opportunity.margin_pct.desc().nullslast()).limit(limit))).scalars().all()
    counts = {}
    for c, in await db.execute(select(Opportunity.category)):
        counts[str(c)] = counts.get(str(c), 0) + 1
    return {"opportunities": [_opp_admin_dict(o) for o in rows], "counts": counts}


@router.get("/opportunities/{symbol}")
async def opportunity(symbol: str, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    o = (await db.execute(select(Opportunity).where(Opportunity.symbol == symbol.upper()))).scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Not in the directory")
    return _opp_admin_dict(o)


@router.post("/opportunities/{symbol}/chat")
async def chat_opportunity(symbol: str, payload: dict = Body(...), admin=Depends(get_current_admin),
                           db: AsyncSession = Depends(get_db)):
    """Feed the harness info about a (usually category-2) stock, then re-analyze:
    the harness may drop it, promote it to category 1, or keep it in category 2."""
    from app.services.agent import central
    o = (await db.execute(select(Opportunity).where(Opportunity.symbol == symbol.upper()))).scalar_one_or_none()
    if not o:
        raise HTTPException(404, "Not in the directory")
    info = (payload.get("message") or payload.get("info") or "").strip()
    if not info:
        raise HTTPException(400, "message required")
    result = await central.reanalyze_with_info(db, o, info)
    return {**_opp_admin_dict(o), "reply": result.get("reply")}


# ── Polytrade: themes (admin-only) — see docs/POLYTRADE.md ──────────────────

async def _load_theme(db, theme_id: str) -> Theme:
    t = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
    if not t:
        raise HTTPException(404, "Theme not found")
    return t


async def _theme_counts(db, theme_id) -> dict:
    n_con = (await db.execute(select(func.count()).select_from(ThemeConstituent)
             .where(ThemeConstituent.theme_id == theme_id, ThemeConstituent.status == "active"))).scalar() or 0
    n_alloc = (await db.execute(select(func.count()).select_from(ThemeAllocation)
               .where(ThemeAllocation.theme_id == theme_id, ThemeAllocation.status.in_(("active", "pending", "unwinding"))))).scalar() or 0
    return {"n_constituents": int(n_con), "n_allocations": int(n_alloc)}


@router.get("/themes")
async def list_themes(admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.services.agent import themes as themes_svc
    rows = (await db.execute(select(Theme).order_by(Theme.created_at.desc()))).scalars().all()
    out = []
    for t in rows:
        out.append({**themes_svc.theme_dict(t), **(await _theme_counts(db, t.id))})
    return {"themes": out}


@router.post("/themes")
async def create_theme(background: BackgroundTasks, payload: dict = Body(...),
                       admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Create a theme and kick off AI origination (narrative + falsifiers + red-team) in the
    background. Returns the placeholder immediately; poll GET /themes/{id} for meta.status=ready."""
    from app.services.agent import themes as themes_svc
    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title required")
    seed = (payload.get("seed_narrative") or payload.get("seed") or "").strip()
    tags = payload.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    theme = await themes_svc.create_stub(db, title, seed, tags, created_by=admin.email)
    tid = str(theme.id)
    await db.commit()
    background.add_task(themes_svc.run_origination, tid)
    return {"theme": {**themes_svc.theme_dict(theme), "n_constituents": 0, "n_allocations": 0}, "generating": True}


@router.get("/themes/{theme_id}")
async def get_theme(theme_id: str, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    from app.services.agent import themes as themes_svc
    t = await _load_theme(db, theme_id)
    cons = (await db.execute(select(ThemeConstituent).where(ThemeConstituent.theme_id == t.id)
            .order_by(ThemeConstituent.target_weight.desc()))).scalars().all()
    events = (await db.execute(select(ThemeEvent).where(ThemeEvent.theme_id == t.id)
              .order_by(ThemeEvent.created_at.desc()).limit(40))).scalars().all()
    return {**themes_svc.theme_dict(t, constituents=cons, events=events), **(await _theme_counts(db, t.id))}


@router.post("/themes/{theme_id}/regenerate")
async def regenerate_theme(theme_id: str, background: BackgroundTasks,
                           admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Re-run the origination thesis (e.g. after editing the seed)."""
    from app.services.agent import themes as themes_svc
    t = await _load_theme(db, theme_id)
    t.meta = {**(t.meta or {}), "status": "generating"}
    await db.commit()
    background.add_task(themes_svc.run_origination, theme_id)
    return {"generating": True}


@router.post("/themes/{theme_id}/pick")
async def pick_theme_basket(theme_id: str, background: BackgroundTasks, payload: dict | None = Body(None),
                            admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """(Re)pick the basket — the AI proposes the US/ADR universe, scored on our metrics, then
    weights it. Optional `hint` forces specific names in (e.g. 'also consider SK Hynix')."""
    from app.services.agent import themes as themes_svc
    t = await _load_theme(db, theme_id)
    hint = ((payload or {}).get("hint") or "").strip() or None
    t.meta = {**(t.meta or {}), "basket_status": "picking"}
    await db.commit()
    background.add_task(themes_svc.run_pick_constituents, theme_id, hint)
    return {"picking": True}


@router.post("/themes/{theme_id}/report")
async def generate_theme_report(theme_id: str, background: BackgroundTasks,
                                admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """(Re)generate the analyst research report (sections + chart data) for a theme."""
    from app.services.agent import themes as themes_svc
    t = await _load_theme(db, theme_id)
    t.meta = {**(t.meta or {}), "report_status": "generating"}
    await db.commit()
    background.add_task(themes_svc.run_generate_report, theme_id)
    return {"generating": True}


@router.post("/themes/{theme_id}/refresh")
async def refresh_theme(theme_id: str, background: BackgroundTasks,
                        admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Run the monitoring re-thesis now (re-score conviction, trip falsifiers, refresh perf)."""
    from app.services.agent import themes as themes_svc
    t = await _load_theme(db, theme_id)
    t.meta = {**(t.meta or {}), "monitor_status": "running"}
    await db.commit()
    background.add_task(themes_svc.run_monitor_one, theme_id)
    return {"refreshing": True}


@router.post("/themes/{theme_id}/status")
async def set_theme_status(theme_id: str, payload: dict = Body(...),
                           admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    """Transition a theme (draft→live to publish, live→closed to retire, etc.)."""
    from app.services.agent import themes as themes_svc
    t = await _load_theme(db, theme_id)
    status = (payload.get("status") or "").lower()
    try:
        await themes_svc.set_status(db, t, status)
    except ValueError as e:
        raise HTTPException(400, str(e))
    await db.commit()
    return {**themes_svc.theme_dict(t), **(await _theme_counts(db, t.id))}


@router.delete("/themes/{theme_id}")
async def delete_theme(theme_id: str, admin=Depends(get_current_admin), db: AsyncSession = Depends(get_db)):
    t = await _load_theme(db, theme_id)
    n_alloc = (await db.execute(select(func.count()).select_from(ThemeAllocation)
               .where(ThemeAllocation.theme_id == t.id, ThemeAllocation.status.in_(("active", "pending", "unwinding"))))).scalar() or 0
    if n_alloc:
        raise HTTPException(409, f"Theme has {n_alloc} live allocation(s) — unwind them before deleting")
    await db.delete(t)          # constituents + events cascade
    await db.commit()
    return {"deleted": True}
