"""Central opportunity pool — SHARED discovery (compute-once, O(universe)).

For a margin-of-safety agent, fear is the source of opportunity, so the discovery
scan is Robinhood's DAILY_LOSERS (beaten-down names) filtered to real companies.
Each survivor is enriched once with a conservative fair value; the pool is
re-priced daily. The per-user morning screen (Phase 4) filters this global pool
by each user's margin of safety + circle — analysis is never repeated per user.

Scans are market-wide (not account-specific), so we run them under any connected
user's token.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select, text

from app.database import async_session
from app.models.db import Opportunity, RobinhoodConnection
from app.services import robinhood_store as store, fair_value as fv_svc
from app.services.market_data import get_company_info, get_batch_quotes
from app.services.robinhood_mcp import RobinhoodMCP
from app.services.agent import engine

logger = logging.getLogger(__name__)

MIN_MARKET_CAP = 2e9      # skip micro-caps / penny stocks
MIN_PRICE = 5.0
MAX_ENRICH = 18          # cap the expensive fair-value work per run
SCAN_PRESET = "DAILY_LOSERS"

# Top US names by market cap — the always-available seed universe (fear-driven
# DAILY_LOSERS is thin on quiet/closed days). MEGACAP_15 ≈ the top 15; SP500 is
# the broad ~500-name starting point. Both are roughly cap-ordered.
MEGACAP_15 = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "LLY", "AVGO",
              "TSLA", "JPM", "WMT", "V", "XOM", "UNH"]

SP500 = MEGACAP_15 + [
    "MA", "JNJ", "COST", "HD", "PG", "ORCL", "BAC", "ABBV", "NFLX", "KO", "CVX", "CRM",
    "MRK", "TMUS", "AMD", "PEP", "ADBE", "LIN", "ACN", "CSCO", "MCD", "WFC", "ABT", "TMO",
    "GE", "DHR", "DIS", "IBM", "QCOM", "TXN", "INTU", "CAT", "AXP", "VZ", "AMGN", "PM",
    "ISRG", "NOW", "GS", "PFE", "NEE", "SPGI", "UBER", "RTX", "T", "LOW", "MS", "HON",
    "UNP", "BKNG", "COP", "PGR", "BLK", "SCHW", "C", "SYK", "ETN", "BSX", "TJX", "ADP",
    "MDT", "VRTX", "BMY", "MU", "GILD", "LMT", "PLD", "MMC", "CB", "ADI", "DE", "AMT",
    "SBUX", "FI", "BX", "REGN", "PANW", "CI", "KLAC", "SO", "MO", "ELV", "DUK", "ICE",
    "SHW", "APH", "PYPL", "ZTS", "CME", "SNPS", "AON", "WM", "CDNS", "EQIX", "PH", "MSI",
    "ITW", "MCK", "CVS", "USB", "CL", "TDG", "GD", "NOC", "CMG", "MCO", "EOG", "TT",
    "PNC", "FCX", "ORLY", "MMM", "APD", "MAR", "BDX", "CTAS", "ECL", "EMR", "CSX", "SLB",
    "ROP", "WELL", "AJG", "NXPI", "HCA", "COF", "MRVL", "AZO", "OKE", "TFC", "TGT", "CARR",
    "PCAR", "GM", "AFL", "SPG", "TRV", "FDX", "PSA", "MET", "SRE", "NSC", "AEP", "GWW",
    "ROST", "URI", "O", "KMB", "DHI", "PSX", "AIG", "MPC", "COR", "D", "FIS", "PAYX",
    "F", "HLT", "OXY", "AMP", "KMI", "LHX", "MSCI", "DAL", "EW", "KVUE", "BK", "ALL",
    "FAST", "VLO", "CMI", "PRU", "CCI", "AME", "CTVA", "IQV", "ODFL", "GEHC", "STZ", "IR",
    "PWR", "EXC", "VRSK", "DXCM", "GIS", "KR", "ACGL", "OTIS", "CHTR", "HES", "IT", "MNST",
    "LULU", "XEL", "YUM", "CBRE", "GLW", "A", "HSY", "IDXX", "PEG", "CTSH", "RSG", "MLM",
    "DD", "VMC", "EA", "HUM", "NUE", "EFX", "WAB", "ROK", "KDP", "NDAQ", "WEC", "VICI",
    "ED", "MTB", "FANG", "TSCO", "AVB", "GPN", "XYL", "DFS", "KHC", "ANSS", "DOW", "FTV",
    "EL", "MPWR", "EQR", "ON", "TROW", "CAH", "WTW", "CDW", "CSGP", "STT", "BR", "SYY",
    "HPQ", "GRMN", "VLTO", "ADM", "DVN", "PPG", "HAL", "AWK", "ES", "EIX", "BIIB", "KEYS",
    "CNC", "MTD", "DLR", "TER", "FITB", "IFF", "HIG", "NVR", "WST", "ZBH", "PHM", "RCL",
    "GPC", "DECK", "WY", "STE", "EBAY", "TDY", "CHD", "NTAP", "BALL", "LYB", "HPE", "INVH",
    "TTWO", "RJF", "WDC", "AEE", "STX", "MKC", "FE", "PPL", "COO", "DTE", "K", "CMS",
    "WBD", "CBOE", "HUBB", "SBAC", "DRI", "WAT", "LDOS", "ATO", "EXR", "VTR", "ULTA", "MOH",
    "HOLX", "TSN", "CTRA", "BAX", "CINF", "OMC", "PKG", "AVY", "LH", "TYL", "NRG", "J",
    "IEX", "CNP", "CLX", "SWKS", "MAA", "EG", "AKAM", "DGX", "TXT", "L", "DPZ", "ALGN",
    "JBHT", "VRSN", "POOL", "EXPD", "SNA", "UAL", "AMCR", "GEN", "NDSN", "BG", "ROL", "FDS",
    "APTV", "RF", "SWK", "PFG", "MRO", "KEY", "HBAN", "CE", "JKHY", "WRB", "DOC", "IP",
    "KIM", "MGM", "TAP", "TFX", "EMN", "SYF", "ZBRA", "CFG", "LNT", "UDR", "NI", "PNR",
    "EVRG", "BBY", "CPT", "JNPR", "HST", "WRK", "GL", "MAS", "INCY", "REG", "FFIV", "CAG",
    "SJM", "AES", "LKQ", "TRMB", "MKTX", "PODD", "VTRS", "BEN", "ALLE", "MTCH", "AOS", "CHRW",
    "NWSA", "SOLV", "DAY", "APA", "HII", "PAYC", "UHS", "HRL", "CPB", "FMC", "WYNN", "BXP",
    "HAS", "TPR", "CRL", "AIZ", "RVTY", "MOS", "DVA", "GNRC", "IPG", "FRT", "NCLH", "BWA",
    "TECH", "PNW", "CTLT", "WBA", "PARA", "ETSY", "MHK", "BIO", "IVZ", "CZR", "RL", "HSIC",
]

# Top US-traded ADRs — foreign large-caps investable from a US brokerage, so the central
# repo covers quality businesses beyond the S&P 500 (TSM, ASML, Alibaba, HDFC, ICICI…).
# NYSE/NASDAQ-listed and confirmed Robinhood-tradeable (2026-07-08) EXCEPT BYDDY (BYD),
# which trades OTC — kept for research coverage; the execution layer fails closed anyway if
# a name can't actually be traded. OTC mega-caps (Tencent/Nestlé/Roche/LVMH) are excluded.
ADRS = [
    "TSM", "BABA", "ASML", "NVO", "SAP", "TM", "AZN", "NVS", "HSBC", "SHEL",
    "TTE", "SNY", "UL", "BUD", "PDD", "RIO", "BHP", "SONY", "MUFG", "TD",
    "JD", "INFY", "GSK", "DEO", "BYDDY",
    # added 2026-07-08 — top-by-market-cap gaps, all verified Robinhood-active:
    "HDB", "IBN", "UBS", "SAN", "BTI", "SMFG",   # HDFC, ICICI, UBS, Santander, Brit Am Tobacco, Sumitomo
]


async def _pick_token(db) -> str | None:
    uid = (await db.execute(select(RobinhoodConnection.user_id).order_by(RobinhoodConnection.updated_at.desc()))).scalars().first()
    return await store.get_valid_access_token(db, uid) if uid else None


async def _run_scan(mcp: RobinhoodMCP) -> dict:
    """Reuse an existing losers scan if present (avoid piling up artifacts), else create one."""
    try:
        scans = ((await mcp.call_tool("get_scans")).get("data") or {}).get("scans") or []
        sid = next((s.get("id") or s.get("scan_id") for s in scans
                    if "loser" in (s.get("title") or s.get("scan_title") or "").lower()), None)
        if sid:
            return await mcp.call_tool("run_scan", {"scan_id": sid})
    except Exception as e:
        logger.debug("get_scans/run_scan fell through: %s", e)
    return await mcp.call_tool("create_scan", {"preset": SCAN_PRESET})


def _scan_symbols(result: dict) -> list[dict]:
    data = (result or {}).get("data", result) if isinstance(result, dict) else {}
    res = data.get("result") or data or {}
    items = res.get("results") or []
    out = []
    for it in items:
        cols = it.get("columns") or {}
        sym = it.get("ticker") or cols.get("Symbol")
        if not sym:
            continue
        try:
            price = float(cols.get("Last") or 0)
            cap = float(cols.get("Market cap") or 0)
            pct = round(float(cols.get("% Change") or 0) * 100, 2)   # fraction → percent
        except (TypeError, ValueError):
            continue
        if cap >= MIN_MARKET_CAP and price >= MIN_PRICE:
            out.append({"symbol": sym.upper(), "name": cols.get("Name"), "price": price,
                        "market_cap": cap, "pct_change": pct})
    return out


async def run_discovery(db=None) -> dict:
    """Scan → filter → enrich the most-beaten survivors → upsert the pool."""
    own = db is None
    db = db or async_session()
    try:
        token = await _pick_token(db)
        if not token:
            return {"skipped": "no_connected_user"}
        result = await _run_scan(RobinhoodMCP(token))
        cands = _scan_symbols(result)
        cands.sort(key=lambda c: c["pct_change"])            # most beaten down first
        cands = cands[:MAX_ENRICH]
        now = engine._utcnow()
        upserted = 0
        for c in cands:
            sym = c["symbol"]
            fv = await asyncio.to_thread(fv_svc.fair_value, sym, c["price"])
            info = await asyncio.to_thread(get_company_info, sym)
            row = (await db.execute(select(Opportunity).where(Opportunity.symbol == sym))).scalar_one_or_none()
            if row is None:
                row = Opportunity(symbol=sym, surfaced_at=now)
                db.add(row)
            row.name = c["name"] or (info or {}).get("name") or sym
            row.sector = (info or {}).get("sector")
            row.source = "scan_losers"
            row.last_price = c["price"]
            row.market_cap = c["market_cap"]
            row.pct_change = c["pct_change"]
            row.fv_low, row.fv_base, row.fv_high = fv.get("low"), fv.get("base"), fv.get("high")
            row.fv_conservative = fv.get("conservative")
            row.fv_confident = bool(fv.get("confident"))
            row.margin_pct = fv.get("margin_pct")
            row.status = "candidate"
            row.last_analyzed_at = now
            row.last_priced_at = now
            upserted += 1
        await db.commit()
        logger.info("Discovery: scanned %d, upserted %d opportunities", len(cands), upserted)
        return {"scanned": len(cands), "upserted": upserted}
    finally:
        if own:
            await db.close()


async def seed_discovery(db=None, universe: str = "top15", limit: int | None = None) -> dict:
    """Seed the pool from a market-cap universe (always-available, unlike the
    fear-driven losers scan). universe: 'top15' (quick test), 'adr' (top US-traded
    ADRs), or 'sp500' (broad starting point — S&P 500 PLUS the top ADRs). Enriches
    each with a conservative fair value; commits incrementally so a long run persists
    progress and skips names it can't fetch."""
    own = db is None
    db = db or async_session()
    try:
        if universe == "top15":
            syms = MEGACAP_15
        elif universe == "adr":
            syms = ADRS
        else:  # 'sp500' broad seed now folds in the top ADRs (dedup, order preserved)
            syms = SP500 + [s for s in ADRS if s not in set(SP500)]
        if limit:
            syms = syms[:limit]
        now = engine._utcnow()
        upserted = skipped = 0
        for sym in syms:
            try:
                fv = await asyncio.to_thread(fv_svc.fair_value, sym)
                info = await asyncio.to_thread(get_company_info, sym) or {}
            except Exception as e:
                logger.debug("seed enrich failed %s: %s", sym, e)
                skipped += 1
                continue
            row = (await db.execute(select(Opportunity).where(Opportunity.symbol == sym))).scalar_one_or_none()
            if row is None:
                row = Opportunity(symbol=sym, surfaced_at=now)
                db.add(row)
            row.name = info.get("name") or sym
            row.sector = info.get("sector")
            row.source = "seed_marketcap"
            row.last_price = fv.get("current_price")
            row.market_cap = info.get("market_cap")
            row.fv_low, row.fv_base, row.fv_high = fv.get("low"), fv.get("base"), fv.get("high")
            row.fv_conservative = fv.get("conservative")
            row.fv_confident = bool(fv.get("confident"))
            row.margin_pct = fv.get("margin_pct")
            row.status = "candidate"
            row.last_analyzed_at = now
            row.last_priced_at = now
            upserted += 1
            await db.commit()      # persist per-symbol so a long run doesn't lose progress
        logger.info("Seed discovery (%s): upserted %d, skipped %d", universe, upserted, skipped)
        return {"universe": universe, "count": len(syms), "upserted": upserted, "skipped": skipped}
    finally:
        if own:
            await db.close()


async def weekly_refresh(db=None) -> dict:
    """The single Sunday job: re-seed the top-500 universe (refresh fair values +
    surface new names), analyze the newly-discovered, then re-review the existing
    Confident + Watch theses so they stay current — i.e. "look at every live thesis
    and change it if it should change." Replaces the separate seed + review jobs."""
    from app.services.agent import central
    seeded = await seed_discovery(universe="sp500")
    new = await central.analyze_pool(only_unanalyzed=True)             # analyze anything just discovered
    reviewed = await central.analyze_pool(only_unanalyzed=False, categories=(1, 3))  # re-check live theses
    logger.info("Weekly refresh: seed=%s new=%s review=%s", seeded, new, reviewed)
    return {"seed": seeded, "new": new, "review": reviewed}


async def refresh_prices(db=None) -> dict:
    """Daily: re-price the pool and recompute margins vs the stored conservative FV."""
    own = db is None
    db = db or async_session()
    try:
        rows = (await db.execute(select(Opportunity).where(Opportunity.status == "candidate"))).scalars().all()
        if not rows:
            return {"repriced": 0}
        from app.services.agent.central import FAIR_FLOOR
        quotes = {q["symbol"]: q for q in await asyncio.to_thread(get_batch_quotes, [r.symbol for r in rows])}
        now = engine._utcnow()
        switched = 0
        for r in rows:
            px = quotes.get(r.symbol, {}).get("price")
            if px and r.fv_conservative:
                r.last_price = float(px)
                r.margin_pct = round((r.fv_conservative - float(px)) / r.fv_conservative * 100, 1)
                r.last_priced_at = now
                # promote/demote Confident (1) ↔ Overpriced-watch (3) as the margin crosses fair value
                if r.category == 3 and r.margin_pct >= FAIR_FLOOR:
                    r.category = 1; switched += 1
                elif r.category == 1 and not r.growth_exception and r.margin_pct < FAIR_FLOOR:
                    r.category = 3; switched += 1
        # Price-trend read (falling/basing/stable/rising) for the ACTIONABLE set
        # (Confident + Watch) — stored in meta so the admin directory shows which names
        # are falling vs basing. Bounded concurrency; cached 6h so it's cheap.
        from app.services.agent import trend as trend_svc
        actionable = [r for r in rows if r.category in (1, 3)]
        sem = asyncio.Semaphore(8)

        async def _tr(sym):
            async with sem:
                return await asyncio.to_thread(trend_svc.assess_trend, sym)

        tres = await asyncio.gather(*[_tr(r.symbol) for r in actionable]) if actionable else []
        for r, t in zip(actionable, tres):
            if t and t.get("status") not in (None, "unknown"):
                meta = dict(r.meta or {})
                meta["trend"] = {"status": t.get("status"), "score": t.get("trend_score"),
                                 "summary": t.get("summary"), "at": now.isoformat()}
                r.meta = meta
        await db.commit()
        from app.services.agent import central
        await central.score_pool()      # margins moved → re-rate + re-rank the confident set
        return {"repriced": len(rows), "bucket_switched": switched}
    finally:
        if own:
            await db.close()


async def list_pool(db, min_margin: float | None = None, confident_only: bool = True,
                    exclude_symbols: set[str] | None = None, sectors_in: list[str] | None = None,
                    sectors_out: list[str] | None = None, limit: int = 50) -> list[Opportunity]:
    """The tradeable universe for a user's morning screen — Category 1 (confident)
    names only, filtered by margin/circle. Growth-exceptions (fairly-valued
    exceptional growers with no classic margin) are included for the user's call."""
    q = select(Opportunity).where(Opportunity.category == 1)
    rows = (await db.execute(q.order_by(Opportunity.margin_pct.desc().nullslast()))).scalars().all()
    exclude_symbols = exclude_symbols or set()
    out = []
    for r in rows:
        if r.symbol in exclude_symbols:
            continue
        if confident_only and not r.fv_confident:
            continue
        margin_ok = (min_margin is None) or (r.margin_pct is not None and r.margin_pct >= min_margin)
        if not (margin_ok or r.growth_exception):     # cheap OR a flagged growth exception
            continue
        if sectors_in and (r.sector not in sectors_in):
            continue
        if sectors_out and (r.sector in sectors_out):
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def opp_dict(o: Opportunity) -> dict:
    return {"symbol": o.symbol, "name": o.name, "sector": o.sector, "source": o.source,
            "last_price": o.last_price, "market_cap": o.market_cap, "pct_change": o.pct_change,
            "fair_value": o.fv_conservative, "fv_base": o.fv_base, "fv_low": o.fv_low, "fv_high": o.fv_high,
            "margin_pct": o.margin_pct, "confident": o.fv_confident, "status": o.status,
            "surfaced_at": o.surfaced_at.isoformat() if o.surfaced_at else None}
