import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.dependencies import require_full_access
from app.routers import watchlist as watchlist_router
from app.services import robinhood
from app.routers import advisor, analysis, auth, brief, demo, health, market_data, market_macro, news, notifications, portfolio, replacement, risk_profile, rules, scores, stock_metrics, stress_test, users, waitlist
from app.routers import robinhood as robinhood_router
from app.routers import key_stats as key_stats_router
from app.routers import agent as agent_router
from app.routers import paper as paper_router
from app.routers import admin as admin_router
from app.routers import themes as themes_router
from app.routers import community as community_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database tables
    try:
        from app.database import engine
        from app.models.db import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created")
    except Exception as e:
        logger.warning("DB table creation skipped: %s", e)

    # Startup: start scheduler for dip-buying automation
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
        logger.info("Scheduler started")
    except Exception as e:
        logger.warning("Scheduler failed to start: %s", e)

    # Populate the market-news brief on startup if nothing is cached yet.
    try:
        import asyncio
        from app.services.market_news import get_latest, generate_market_news
        if not get_latest().get("articles"):
            asyncio.create_task(generate_market_news())
    except Exception as e:
        logger.warning("Market news startup populate failed: %s", e)

    # Startup: try to restore Robinhood session from pickle
    try:
        if robinhood.try_restore_from_pickle():
            logger.info("Robinhood session auto-restored on startup")
        else:
            logger.info("No valid Robinhood session found (user will connect manually)")
    except Exception as e:
        logger.warning("Robinhood session restore skipped: %s", e)

    logger.info("Emouva API started (v%s)", settings.app_version)
    yield

    # Shutdown: stop scheduler
    try:
        from app.services.scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass

    # Shutdown: disconnect Robinhood but preserve session pickle
    if robinhood.is_connected():
        robinhood.disconnect()


app = FastAPI(
    title="Emouva API",
    version=settings.app_version,
    description="AI-powered investment intelligence backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Existing routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(portfolio.router)
# Personal-mode: on a hosted instance with RESTRICT_TRADING_TO set, these
# trading surfaces are owner-only; with it unset (self-host) the guard is a no-op.
app.include_router(robinhood_router.router, dependencies=[Depends(require_full_access)])
app.include_router(key_stats_router.router)
app.include_router(agent_router.router, dependencies=[Depends(require_full_access)])
app.include_router(paper_router.router, dependencies=[Depends(require_full_access)])
app.include_router(admin_router.router)
app.include_router(themes_router.router, dependencies=[Depends(require_full_access)])
app.include_router(community_router.router)
app.include_router(analysis.router)
app.include_router(brief.router)
app.include_router(market_data.router)
app.include_router(news.router)

# New routers: user auth, buy rules, notifications
app.include_router(users.router)
app.include_router(rules.router)
app.include_router(notifications.router)

# Stock validity scores
app.include_router(scores.router)

# Conversational portfolio advisor
app.include_router(advisor.router)

# Waitlist (public, no auth)
app.include_router(waitlist.router)

# Demo access (email-gated, no auth)
app.include_router(demo.router)

# Stock metrics cache (public read, auth for refresh/stream)
app.include_router(stock_metrics.router)

# Risk profiling & diversification suggestions
app.include_router(risk_profile.router)

# Portfolio stress testing
app.include_router(stress_test.router)

# Underperformer replacement suggestions
app.include_router(replacement.router)

# User watchlist (DB-backed)
app.include_router(watchlist_router.router)

# Market macro indicators (Real Earnings Yield)
app.include_router(market_macro.router)
