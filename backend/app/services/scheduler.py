"""
APScheduler setup for background jobs:
- Dip-buying rule checks (every 48h)
- Stock metrics cache refresh (every 6h)
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


# Dispatcher scale/resilience knobs. The claim uses SELECT … FOR UPDATE SKIP
# LOCKED, so these bound ONE worker per cycle; run more workers to scale out and
# their leased batches stay disjoint (no double-ticking, no double orders).
_TICK_BATCH = 300          # max mandates leased per 60s cycle (backpressure)
_TICK_CONCURRENCY = 12     # concurrent ticks within a cycle (comfortable for 100+ users w/ jitter + idle-skip)
_TICK_TIMEOUT_S = 90       # hard per-tick timeout; a hung MCP/LLM call can't wedge a slot
_LEASE_MIN = 5             # a claimed tick must finish within this or it re-dispatches (crash fallback)
_CLOSED_DEFER_MIN = 20     # intraday mandate due while market closed → look again later


async def _run_agent_ticks():
    """Claim-based review dispatcher — safe at scale and across instances.

    • Leases a batch with SELECT … FOR UPDATE SKIP LOCKED: two cycles/workers never
      grab the same mandate, so an account is never ticked (or ordered) twice. The
      lease (next_tick_at pushed forward) also means a crashed worker's tick simply
      re-dispatches after the lease — automatic fallback.
    • Intraday cadences run only inside the agent window (8:30 ET → close); Daily
      runs whenever due; anything intraday-but-closed is deferred, not spun on.
    • Each tick has a hard timeout; failures/timeouts retry on the short lease/backoff
      rather than a full cadence later.
    Horizontal scale for 10k+ users = run more workers; the SKIP LOCKED claim keeps
    their batches disjoint."""
    import asyncio
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select
    from app.database import async_session
    from app.models.db import AgentMandate
    from app.services.agent import engine
    from app.services import market_hours

    now_aware = datetime.now(timezone.utc)
    now = now_aware.replace(tzinfo=None)
    active = market_hours.agent_active(now_aware)

    to_run: list = []
    async with async_session() as db:
        rows = (await db.execute(
            select(AgentMandate)
            .where(AgentMandate.paused.is_(False),
                   AgentMandate.next_tick_at.isnot(None),
                   AgentMandate.next_tick_at <= now)
            .order_by(AgentMandate.next_tick_at)
            .limit(_TICK_BATCH)
            .with_for_update(skip_locked=True)      # claim: other cycles/workers skip these rows
        )).scalars().all()
        for m in rows:
            if m.cadence == "Daily" or active:
                m.next_tick_at = now + timedelta(minutes=_LEASE_MIN)   # lease → prevents re-claim; crash-safe
                to_run.append(m.user_id)
            else:
                m.next_tick_at = market_hours.next_agent_slot(now_aware)  # outside the window → jump to the next :55 slot
        await db.commit()                            # persist leases + release row locks

    if not to_run:
        return

    sem = asyncio.Semaphore(_TICK_CONCURRENCY)

    async def _one(uid):
        async with sem:
            try:
                await asyncio.wait_for(engine.run_tick(uid, reason="cadence"), timeout=_TICK_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.warning("Agent dispatcher: tick timed out for %s (lease will retry)", uid)
            except Exception:
                logger.exception("Agent dispatcher: tick failed for %s", uid)

    await asyncio.gather(*[_one(u) for u in to_run])
    logger.info("Agent dispatcher: dispatched %d tick(s) (agent_window=%s)", len(to_run), active)


async def _run_track_checks():
    """Daily: re-value every user's tracked names; propose the interesting ones.
    Each UNIQUE symbol is valued once for the whole run (central.value_symbols) and
    its central record refreshed — so a name on many users' watchlists costs a single
    compute, not one per user."""
    import asyncio
    from sqlalchemy import select, distinct
    from app.database import async_session
    from app.models.db import TrackItem
    from app.services import robinhood_store as store
    from app.services.agent import tracking, central

    async with async_session() as db:
        uids = (await db.execute(select(distinct(TrackItem.user_id)).where(TrackItem.status != "archived"))).scalars().all()
        symbols = (await db.execute(select(distinct(TrackItem.symbol)).where(TrackItem.status != "archived"))).scalars().all()
    if not uids:
        return
    async with async_session() as db:
        valuations = await central.value_symbols(db, symbols)   # compute-once, shared across all users
    sem = asyncio.Semaphore(3)

    async def _one(uid):
        async with sem:
            try:
                async with async_session() as db:
                    token = await store.get_valid_access_token(db, uid)
                    await tracking.daily_check(db, uid, token, valuations=valuations)
            except Exception:
                logger.exception("Track check failed for %s", uid)

    await asyncio.gather(*[_one(u) for u in uids])
    logger.info("Track checks: ran for %d user(s), %d unique symbol(s) valued once", len(uids), len(symbols))


async def _run_morning_preview():
    """Pre-market DRY-RUN preview (8:30 ET, trading days): show live users what the
    agent intends to do today — logged to the Ledger, no real orders. Real trading
    is the 9:50–3:50 window."""
    import asyncio
    from datetime import datetime, timezone
    from sqlalchemy import select
    from app.database import async_session
    from app.models.db import AgentMandate
    from app.services.agent import engine
    from app.services import market_hours

    if market_hours.status()["session"] in ("weekend", "holiday"):
        return
    async with async_session() as db:
        uids = (await db.execute(select(AgentMandate.user_id).where(
            AgentMandate.mode == "live", AgentMandate.paused.is_(False)))).scalars().all()
    if not uids:
        return
    sem = asyncio.Semaphore(4)

    async def _one(uid):
        async with sem:
            try:
                await engine.run_tick(uid, reason="preview", mode="dry_run")   # dry-run: previews, never places
            except Exception:
                logger.exception("Morning preview failed for %s", uid)

    await asyncio.gather(*[_one(u) for u in uids])
    logger.info("Morning preview: dry-run for %d live mandate(s)", len(uids))


def start_scheduler() -> None:
    """Start the background scheduler."""
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler()
    from app.services.agent import discovery, central
    from app.services.agent import themes as themes_svc

    # Major-market-news brief via Claude, 3x/day (ET).
    from app.services.market_news import generate_market_news
    for _hour in (8, 11, 14):
        _scheduler.add_job(
            generate_market_news, "cron", hour=_hour, minute=5,
            timezone="America/New_York", id=f"market_news_{_hour}", replace_existing=True,
        )

    # Agentic-trading dispatcher — per-user cadence ticks. max_instances>1 lets a
    # slow cycle overlap the next for more throughput; SKIP LOCKED keeps the
    # overlapping cycles' leased batches disjoint. coalesce collapses missed runs.
    # (The hourly tick now also runs the Living-Thesis falsifier check, so there is
    # no separate daily thesis sweep.)
    _scheduler.add_job(
        _run_agent_ticks, "interval", seconds=60, id="agent_dispatch", replace_existing=True,
        max_instances=3, coalesce=True,
    )
    # Pre-market refresh (7:00 ET — BEFORE the 9:50 first live tick): recompute FV + stats
    # for the actionable set (Confident + Watch) from fresh fundamentals (no LLM) so margins
    # are honest at the open, then LLM-re-analyze only the names whose fundamentals materially
    # moved overnight (earnings / big FV swing / trend flip). Finishes with hours of runway
    # before 9:50 — new discoveries stay on the 10:20 pass.
    _scheduler.add_job(central.premarket_refresh, "cron", hour=7, minute=0,
                       timezone="America/New_York", id="premarket_refresh", replace_existing=True)
    # Confident bucket — morning news watch (8:00 ET) so the day opens with fresh
    # thesis-relevant news flagged on the tradeable set.
    _scheduler.add_job(central.news_check, "cron", hour=8, minute=0,
                       timezone="America/New_York", id="confident_news_check", replace_existing=True)
    # Polytrade — daily theme monitor (8:15 ET): after premarket refresh (7:00) has
    # updated constituent stats/earnings and the news watch (8:00) has flagged headlines,
    # re-thesis every live theme — re-score conviction, trip falsifiers, drive the
    # health/status state machine, refresh performance. A break here is M2's unwind trigger.
    _scheduler.add_job(themes_svc.monitor, "cron", hour=8, minute=15,
                       timezone="America/New_York", id="theme_monitor", replace_existing=True)
    # Polytrade — allocation reconciler (8:20 ET, right after the monitor): invest new
    # allocations, rebalance basket changes, and unwind every allocation of any theme that
    # just broke (cross-user exit). New allocations also reconcile immediately on creation.
    from app.services.agent import theme_exec
    _scheduler.add_job(theme_exec.reconcile, "cron", hour=8, minute=20,
                       timezone="America/New_York", id="theme_reconcile", replace_existing=True)
    # Market-open reconcile (9:35 ET): LIVE theme orders only place during regular hours, so the
    # 8:20 pass DEFERS them — this pass executes deferred invests/rebalances/break-unwinds at the
    # open (paper allocations already ran at 8:20; this is idempotent for them).
    _scheduler.add_job(theme_exec.reconcile, "cron", hour=9, minute=35,
                       timezone="America/New_York", id="theme_reconcile_open", replace_existing=True)
    # Polytrade — weekly DEEP re-validation (Sun 6:30 ET): re-examine each live theme's
    # whole narrative from scratch with heavier web search, beyond the daily light monitor.
    _scheduler.add_job(themes_svc.weekly_revalidate, "cron", day_of_week="sun", hour=6, minute=30,
                       timezone="America/New_York", id="theme_weekly_revalidate", replace_existing=True)
    # Pre-market DRY-RUN preview (8:30 ET) — live users see the day's intended moves
    # in the Ledger before real trading opens at 9:50. No orders are placed.
    _scheduler.add_job(_run_morning_preview, "cron", hour=8, minute=30,
                       timezone="America/New_York", id="morning_preview", replace_existing=True)
    # Track List — daily math re-value of watched names (9:45 ET, after the open).
    _scheduler.add_job(
        _run_track_checks, "cron", hour=9, minute=45,
        timezone="America/New_York", id="track_check", replace_existing=True,
    )
    # Opportunity pool — discover (scan+enrich) at 9:50 ET, re-price at 16:10 ET.
    _scheduler.add_job(discovery.run_discovery, "cron", hour=9, minute=50,
                       timezone="America/New_York", id="pool_discovery", replace_existing=True)
    _scheduler.add_job(discovery.refresh_prices, "cron", hour=16, minute=10,
                       timezone="America/New_York", id="pool_reprice", replace_existing=True)
    # Account memory — deterministic end-of-day daily log (16:15 ET, after the close).
    from app.services.agent import memory as agent_memory
    _scheduler.add_job(agent_memory.record_daily, "cron", hour=16, minute=15,
                       timezone="America/New_York", id="daily_memory", replace_existing=True)
    # Central intelligence — analyze NEWLY-DISCOVERED candidates only (only_unanalyzed:
    # category IS NULL / pending) at 10:20 ET. Changed EXISTING names are re-analyzed
    # pre-open by premarket_refresh, since they're tradeable at 9:50; new discoveries
    # aren't tradeable until categorized, so 10:20 is fine for them.
    _scheduler.add_job(central.analyze_pool, "cron", hour=10, minute=20,
                       timezone="America/New_York", id="central_analysis", replace_existing=True)
    # Weekly refresh (Sunday 06:00 ET) — ONE job: re-seed the top-500, analyze new
    # names, and re-review every live Confident/Watch thesis (seed + review merged).
    _scheduler.add_job(discovery.weekly_refresh, "cron", day_of_week="sun", hour=6, minute=0,
                       timezone="America/New_York", id="weekly_refresh", replace_existing=True)
    # Account memory — weekly 'librarian' compaction (Sunday 05:00 ET): fold the
    # week's daily logs into each account's compact long-term memory.
    _scheduler.add_job(agent_memory.compact_weekly, "cron", day_of_week="sun", hour=5, minute=0,
                       timezone="America/New_York", id="weekly_memory", replace_existing=True)

    _scheduler.start()
    logger.info("Scheduler started: premarket refresh 7:00, news 8:00, preview 8:30 (dry-run), agent live "
                "9:50–3:50 ET (hourly :50), tracks 9:45, discovery 9:50, new-name analysis 10:20, reprice 16:10, "
                "weekly refresh Sun 6:00")


def stop_scheduler() -> None:
    """Stop the background scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")
