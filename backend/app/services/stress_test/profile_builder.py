
"""Build stock sensitivity profiles from yfinance data.

Profiles are used by the impact calculator to adjust sector-level impacts
per stock. Cached in the stock_sensitivity_profiles table with 24h TTL.
"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import StockSensitivityProfile

logger = logging.getLogger(__name__)


# ── Public API ──────────────────────────────────────────────────


async def get_profiles(
    symbols: list[str],
    db: AsyncSession,
) -> dict[str, dict]:
    """Get sensitivity profiles for symbols. Build on-demand if missing."""
    result = await _load_from_db(symbols, db)

    # Build any missing profiles
    missing = [s for s in symbols if s not in result]
    if missing:
        built = await _build_profiles(missing)
        for symbol, profile in built.items():
            result[symbol] = profile
            await _upsert_profile(symbol, profile, db)

    return result


async def refresh_profiles(
    symbols: list[str],
    db: AsyncSession,
) -> None:
    """Force-refresh profiles for given symbols (background job)."""
    built = await _build_profiles(symbols)
    for symbol, profile in built.items():
        await _upsert_profile(symbol, profile, db)
    logger.info("Refreshed %d stress test profiles", len(built))


# ── Profile Builder ─────────────────────────────────────────────


async def _build_profiles(symbols: list[str]) -> dict[str, dict]:
    """Build sensitivity profiles from yfinance. Runs in thread (sync I/O)."""
    import asyncio
    return await asyncio.to_thread(_build_profiles_sync, symbols)


def _build_profiles_sync(symbols: list[str]) -> dict[str, dict]:
    """Sync profile builder — uses yfinance (blocking I/O)."""
    from app.services.market_data import get_company_info

    profiles: dict[str, dict] = {}

    for symbol in symbols:
        try:
            info = get_company_info(symbol)
            if not info or info.get("sector") is None:
                # Minimal fallback profile
                profiles[symbol] = _fallback_profile(symbol)
                continue

            profiles[symbol] = {
                "symbol": symbol,
                "name": info.get("name", symbol),
                "sector": info.get("sector", "Unknown"),
                "industry": info.get("industry", "Unknown"),
                "size_tier": _mcap_tier(info.get("market_cap")),
                "primary_region": _country_to_region(info.get("country")),
                "beta": info.get("beta"),
                "quality_score": _compute_quality_score(info),
                "fundamentals": {
                    "profit_margins": info.get("profit_margins"),
                    "debt_to_equity": info.get("debt_to_equity"),
                    "current_ratio": info.get("current_ratio"),
                    "free_cash_flow": info.get("free_cash_flow"),
                    "revenue_growth": info.get("revenue_growth"),
                    "return_on_equity": info.get("return_on_equity"),
                    "pe_ratio": info.get("pe_ratio"),
                    "forward_pe": info.get("forward_pe"),
                },
                "factor_exposures": _compute_factor_exposures(info),
                "revenue_exposure": _estimate_revenue_exposure(info),
            }
        except Exception:
            logger.warning("Failed to build profile for %s", symbol, exc_info=True)
            profiles[symbol] = _fallback_profile(symbol)

    return profiles


def _fallback_profile(symbol: str) -> dict:
    return {
        "symbol": symbol,
        "name": symbol,
        "sector": "Unknown",
        "industry": "Unknown",
        "size_tier": "unknown",
        "primary_region": "Unknown",
        "beta": 1.0,
        "quality_score": 50,
        "fundamentals": {},
        "factor_exposures": {},
        "revenue_exposure": {"US": 0.6},
    }


# ── Quality Score ───────────────────────────────────────────────


def _compute_quality_score(info: dict) -> int:
    """0-100 quality score from fundamentals. Higher = stronger company."""
    score = 50

    # Profitability (+/- 15)
    margins = info.get("profit_margins")
    if margins is not None:
        if margins > 0.20:
            score += 15
        elif margins > 0.10:
            score += 8
        elif margins > 0:
            score += 3
        else:
            score -= 10

    # Leverage (+/- 15)
    dte = info.get("debt_to_equity")
    if dte is not None:
        if dte < 30:
            score += 15
        elif dte < 80:
            score += 5
        elif dte > 200:
            score -= 15
        else:
            score -= 5

    # Cash flow (+/- 10)
    fcf = info.get("free_cash_flow")
    if fcf is not None:
        if fcf > 0:
            score += 10
        else:
            score -= 10

    # Growth (+/- 10)
    growth = info.get("revenue_growth")
    if growth is not None:
        if growth > 0.20:
            score += 10
        elif growth > 0.05:
            score += 5
        elif growth < -0.05:
            score -= 10

    return max(0, min(100, score))


# ── Factor Exposures ────────────────────────────────────────────


def _compute_factor_exposures(info: dict) -> dict[str, float]:
    """Estimate factor exposures from fundamentals."""
    exposures: dict[str, float] = {}

    # Leverage exposure (0-1)
    dte = info.get("debt_to_equity")
    if dte is not None:
        exposures["leverage"] = min(1.0, max(0.0, dte / 200))

    # Rate sensitivity — high for growth stocks
    pe = info.get("pe_ratio") or info.get("forward_pe")
    if pe and pe > 40:
        exposures["rate_sensitivity"] = 0.8
    elif pe and pe > 25:
        exposures["rate_sensitivity"] = 0.5
    else:
        exposures["rate_sensitivity"] = 0.2

    # PE ratio premium (for bubble scenarios)
    if pe and pe > 50:
        exposures["pe_ratio_premium"] = 0.9
    elif pe and pe > 30:
        exposures["pe_ratio_premium"] = 0.5
    else:
        exposures["pe_ratio_premium"] = 0.1

    # Semiconductor exposure (by industry)
    industry = (info.get("industry") or "").lower()
    if "semiconductor" in industry:
        exposures["semiconductor"] = 1.0
        exposures["taiwan_supply_chain"] = 0.7
    elif "electronic" in industry or "hardware" in industry:
        exposures["semiconductor"] = 0.4
        exposures["taiwan_supply_chain"] = 0.3

    # AI revenue exposure (heuristic)
    sector = (info.get("sector") or "").lower()
    if "technology" in sector:
        if "semiconductor" in industry or "software" in industry:
            exposures["ai_revenue_pct"] = 0.5
            exposures["cloud_infrastructure"] = 0.4

    # Consumer cyclical
    if sector in ("consumer cyclical", "retail trade", "consumer services"):
        exposures["consumer_cyclical"] = 0.8

    # Defense
    if "defense" in industry or "aerospace" in industry:
        exposures["defense_contractor"] = 0.8

    # Energy
    if "energy" in sector or "oil" in industry or "gas" in industry:
        exposures["energy_producer"] = 0.8

    # Travel / hospitality
    if any(kw in industry for kw in ("airline", "hotel", "travel", "cruise", "restaurant")):
        exposures["travel_exposure"] = 0.8

    # Dividend yield
    div_yield = info.get("dividend_yield")
    if div_yield and div_yield > 0.03:
        exposures["dividend_yield_high"] = 0.7

    # International revenue (heuristic based on size)
    mcap = info.get("market_cap")
    if mcap and mcap > 100_000_000_000:  # >$100B likely significant international
        exposures["international_revenue"] = 0.5

    return exposures


# ── Revenue Exposure (Geographic) ───────────────────────────────


def _estimate_revenue_exposure(info: dict) -> dict[str, float]:
    """Estimate geographic revenue breakdown. Heuristic until we have SEC data."""
    country = (info.get("country") or "Unknown").lower()

    if country in ("united states", "us", "usa"):
        return {"US": 0.6, "Europe": 0.15, "Asia-Pacific": 0.15, "Other": 0.1}
    elif country in ("china", "hong kong"):
        return {"China": 0.7, "Asia-Pacific": 0.15, "US": 0.1, "Other": 0.05}
    elif country in ("japan", "south korea", "taiwan"):
        return {"Asia-Pacific": 0.6, "US": 0.2, "Europe": 0.1, "Other": 0.1}
    elif country in ("united kingdom", "germany", "france", "switzerland", "netherlands"):
        return {"Europe": 0.6, "US": 0.2, "Asia-Pacific": 0.1, "Other": 0.1}
    else:
        return {"US": 0.4, "Other": 0.6}


# ── Helpers ─────────────────────────────────────────────────────


def _mcap_tier(market_cap: float | None) -> str:
    if not market_cap:
        return "unknown"
    if market_cap > 200_000_000_000:
        return "mega_cap"
    if market_cap > 10_000_000_000:
        return "large_cap"
    if market_cap > 2_000_000_000:
        return "mid_cap"
    if market_cap > 300_000_000:
        return "small_cap"
    return "micro_cap"


def _country_to_region(country: str | None) -> str:
    if not country:
        return "Unknown"
    c = country.lower()
    if c in ("united states", "us", "usa", "canada"):
        return "US"
    if c in ("china", "hong kong", "macau"):
        return "China"
    if c in ("japan", "south korea", "taiwan", "india", "singapore", "australia"):
        return "Asia-Pacific"
    if c in ("united kingdom", "germany", "france", "switzerland", "netherlands",
             "ireland", "sweden", "denmark", "norway", "spain", "italy"):
        return "Europe"
    if c in ("brazil", "mexico", "argentina", "chile", "colombia"):
        return "Latin America"
    if c in ("saudi arabia", "uae", "israel", "turkey"):
        return "Middle East"
    return "Other"


# ── Database Operations ─────────────────────────────────────────


async def _load_from_db(
    symbols: list[str],
    db: AsyncSession,
) -> dict[str, dict]:
    """Load cached profiles from DB."""
    result: dict[str, dict] = {}
    try:
        stmt = select(StockSensitivityProfile).where(
            StockSensitivityProfile.symbol.in_(symbols)
        )
        rows = (await db.execute(stmt)).scalars().all()
        for row in rows:
            # Check freshness (24h TTL)
            age = (datetime.utcnow() - row.updated_at).total_seconds()
            if age > 86400:  # stale, but still usable
                continue
            result[row.symbol] = {
                "symbol": row.symbol,
                "name": row.symbol,  # DB doesn't store name; use symbol
                "sector": row.sector,
                "industry": row.industry,
                "size_tier": row.size_tier,
                "primary_region": row.primary_region,
                "beta": row.beta,
                "quality_score": row.quality_score,
                "fundamentals": row.fundamentals or {},
                "factor_exposures": row.factor_exposures or {},
                "revenue_exposure": row.revenue_exposure or {},
            }
    except Exception:
        logger.warning("Failed to load profiles from DB", exc_info=True)
    return result


async def _upsert_profile(
    symbol: str,
    profile: dict,
    db: AsyncSession,
) -> None:
    """Insert or update a sensitivity profile."""
    try:
        stmt = select(StockSensitivityProfile).where(
            StockSensitivityProfile.symbol == symbol
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            existing.sector = profile.get("sector", "Unknown")
            existing.industry = profile.get("industry", "Unknown")
            existing.size_tier = profile.get("size_tier", "unknown")
            existing.primary_region = profile.get("primary_region", "Unknown")
            existing.beta = profile.get("beta")
            existing.quality_score = profile.get("quality_score")
            existing.fundamentals = profile.get("fundamentals")
            existing.factor_exposures = profile.get("factor_exposures")
            existing.revenue_exposure = profile.get("revenue_exposure")
            existing.updated_at = datetime.utcnow()
        else:
            import uuid
            db.add(StockSensitivityProfile(
                id=uuid.uuid4(),
                symbol=symbol,
                sector=profile.get("sector", "Unknown"),
                industry=profile.get("industry", "Unknown"),
                size_tier=profile.get("size_tier", "unknown"),
                primary_region=profile.get("primary_region", "Unknown"),
                beta=profile.get("beta"),
                quality_score=profile.get("quality_score"),
                fundamentals=profile.get("fundamentals"),
                factor_exposures=profile.get("factor_exposures"),
                revenue_exposure=profile.get("revenue_exposure"),
                updated_at=datetime.utcnow(),
            ))

        await db.commit()
    except Exception:
        await db.rollback()
        logger.warning("Failed to upsert profile for %s", symbol, exc_info=True)
