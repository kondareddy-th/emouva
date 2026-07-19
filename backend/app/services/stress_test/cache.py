"""Two-tier cache for stress test results.

Tier 1: In-memory dict with LRU eviction (500 entries, 15-min TTL)
Tier 2: PostgreSQL stress_test_results table (1-4 hour TTL)
"""

import hashlib
import json
import logging
import time
import uuid
from collections import OrderedDict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import StressTestResultDB

logger = logging.getLogger(__name__)

# ── Cache Key ───────────────────────────────────────────────────


def build_cache_key(
    holdings: list[dict],
    scenario_id: str,
    scenario_version: str,
    confidence_level: str,
    include_correlation: bool,
) -> str:
    """Deterministic cache key from inputs."""
    normalized = sorted(holdings, key=lambda h: h["symbol"])
    for h in normalized:
        h["shares"] = round(h["shares"], 4)

    payload = {
        "h": normalized,
        "s": scenario_id,
        "v": scenario_version,
        "c": confidence_level,
        "corr": include_correlation,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def build_portfolio_hash(holdings: list[dict]) -> str:
    """Hash of sorted holdings for result metadata."""
    normalized = sorted(holdings, key=lambda h: h["symbol"])
    return hashlib.md5(json.dumps(normalized, sort_keys=True).encode()).hexdigest()


# ── Tier 1: In-Memory Cache ────────────────────────────────────

_MEMORY_MAX_SIZE = 500
_MEMORY_TTL = 900  # 15 minutes


class _MemoryCache:
    """Simple LRU cache with TTL."""

    def __init__(self, max_size: int = _MEMORY_MAX_SIZE, ttl: int = _MEMORY_TTL):
        self._store: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl

    def get(self, key: str) -> dict | None:
        if key not in self._store:
            return None
        ts, data = self._store[key]
        if time.time() - ts > self._ttl:
            del self._store[key]
            return None
        self._store.move_to_end(key)
        return data

    def set(self, key: str, data: dict, ttl: int | None = None) -> None:
        actual_ttl = ttl or self._ttl
        self._store[key] = (time.time(), data)
        self._store.move_to_end(key)
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)


_memory_cache = _MemoryCache()


# ── Tier 2: Database Cache ──────────────────────────────────────


async def get_cached_result(
    cache_key: str,
    db: AsyncSession,
) -> dict | None:
    """Look up a cached result by cache_key. Returns None if expired."""
    # Tier 1
    mem_result = _memory_cache.get(cache_key)
    if mem_result:
        return mem_result

    # Tier 2
    try:
        stmt = select(StressTestResultDB).where(
            StressTestResultDB.cache_key == cache_key
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None

        if row.expires_at < datetime.utcnow():
            return None  # expired

        result = row.result_data
        _memory_cache.set(cache_key, result)
        return result

    except Exception:
        logger.warning("Failed to read cache for key %s", cache_key[:12], exc_info=True)
        return None


async def get_cached_result_by_id(
    result_id: str,
    db: AsyncSession,
) -> dict | None:
    """Retrieve a cached result by its result_id."""
    try:
        stmt = select(StressTestResultDB).where(
            StressTestResultDB.result_data["result_id"].astext == result_id
        )
        row = (await db.execute(stmt)).scalar_one_or_none()
        if not row:
            return None
        if row.expires_at < datetime.utcnow():
            return None
        return row.result_data
    except Exception:
        logger.warning("Failed to read result %s", result_id[:12], exc_info=True)
        return None


async def store_result(
    cache_key: str,
    result: dict,
    scenario_id: str,
    scenario_version: str,
    portfolio_hash: str,
    portfolio_size: int,
    methodology: str,
    confidence_level: str,
    computation_ms: int,
    custom_input: str | None,
    db: AsyncSession,
    ttl_hours: int = 1,
) -> None:
    """Persist a stress test result to both cache tiers."""
    _memory_cache.set(cache_key, result)

    try:
        # Check for existing entry
        stmt = select(StressTestResultDB).where(
            StressTestResultDB.cache_key == cache_key
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        now = datetime.utcnow()
        expires = now + timedelta(hours=ttl_hours)

        if existing:
            existing.result_data = result
            existing.computation_ms = computation_ms
            existing.expires_at = expires
        else:
            db.add(StressTestResultDB(
                id=uuid.uuid4(),
                cache_key=cache_key,
                scenario_id=scenario_id,
                scenario_version=scenario_version,
                custom_input=custom_input,
                result_data=result,
                portfolio_hash=portfolio_hash,
                portfolio_size=portfolio_size,
                methodology=methodology,
                confidence_level=confidence_level,
                computation_ms=computation_ms,
                created_at=now,
                expires_at=expires,
            ))

        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning("Failed to persist result for key %s", cache_key[:12], exc_info=True)


async def cleanup_expired(db: AsyncSession) -> int:
    """Delete expired results from the database. Returns count deleted."""
    try:
        from sqlalchemy import delete as sa_delete
        stmt = sa_delete(StressTestResultDB).where(
            StressTestResultDB.expires_at < datetime.utcnow()
        )
        result = await db.execute(stmt)
        await db.commit()
        count = result.rowcount
        if count:
            logger.info("Cleaned up %d expired stress test results", count)
        return count
    except Exception:
        await db.rollback()
        logger.warning("Failed to cleanup expired results", exc_info=True)
        return 0
