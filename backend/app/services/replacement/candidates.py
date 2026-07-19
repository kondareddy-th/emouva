"""
Stage 4: Replacement Candidate Filtering

Finds potential replacement stocks using GICS sector/industry matching.
Filters from a curated universe of ~400 quality stocks (S&P 500 core).

Pipeline: Universe → GICS match → Batch fetch info → Market cap + Quality gate

Uses concurrent yfinance fetching to stay under nginx timeout.

100% deterministic — no LLM involvement.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# Max workers for concurrent yfinance fetches
_MAX_WORKERS = 8

# ── Curated Universe by GICS Sector ─────────────────────────────────
# Top quality stocks per sector. Organized by industry for tiered matching.

UNIVERSE: dict[str, dict[str, list[str]]] = {
    "Technology": {
        "Semiconductors": ["NVDA", "AMD", "AVGO", "TXN", "QCOM", "INTC", "MU", "ADI", "MRVL", "ON", "NXPI", "KLAC", "LRCX", "AMAT", "ASML"],
        "Software—Application": ["CRM", "ADBE", "INTU", "NOW", "WDAY", "PLTR", "SNPS", "CDNS", "PANW", "CRWD", "DDOG", "ZS", "HUBS", "TEAM"],
        "Software—Infrastructure": ["MSFT", "ORCL", "SNOW", "MDB", "NET", "ESTC", "PATH", "SPLK"],
        "Hardware": ["AAPL", "DELL", "HPE", "KEYS", "TER", "ZBRA"],
        "IT Services": ["ACN", "IBM", "FI", "FISV", "GPN", "IT", "GDDY"],
    },
    "Healthcare": {
        "Drug Manufacturers": ["LLY", "JNJ", "ABBV", "MRK", "PFE", "BMY", "AZN", "NVO", "AMGN"],
        "Biotechnology": ["VRTX", "GILD", "REGN", "MRNA", "BIIB", "SGEN", "ALNY", "BMRN", "EXAS"],
        "Medical Devices": ["ABT", "TMO", "SYK", "ISRG", "MDT", "BSX", "EW", "ZBH", "HOLX"],
        "Health Insurance": ["UNH", "ELV", "CI", "HUM", "CNC", "MOH"],
        "Health Services": ["MCK", "CAH", "ABC", "VEEV", "HIMS"],
    },
    "Financial Services": {
        "Banks—Diversified": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
        "Banks—Regional": ["USB", "PNC", "TFC", "CFG", "FITB", "RF", "KEY", "HBAN", "MTB"],
        "Insurance": ["BRK-B", "PGR", "CB", "AIG", "MET", "AFL", "TRV", "ALL"],
        "Capital Markets": ["SCHW", "BLK", "SPGI", "ICE", "CME", "MSCI", "NDAQ"],
        "Fintech": ["V", "MA", "PYPL", "SQ", "COIN", "AFRM", "SOFI"],
    },
    "Financials": {
        "Banks—Diversified": ["JPM", "BAC", "WFC", "C", "GS", "MS"],
        "Insurance": ["BRK-B", "PGR", "CB", "MET", "AFL", "TRV"],
        "Fintech": ["V", "MA", "PYPL", "SQ"],
    },
    "Consumer Cyclical": {
        "Internet Retail": ["AMZN", "BABA", "JD", "MELI", "SE", "SHOP", "ETSY"],
        "Auto Manufacturers": ["TSLA", "TM", "GM", "F", "RIVN"],
        "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "DPZ", "QSR"],
        "Specialty Retail": ["HD", "LOW", "TJX", "ROST", "ORLY", "AZO", "ULTA"],
        "Apparel": ["NKE", "LULU", "TKR", "TPR", "RL"],
        "Hotels & Travel": ["MAR", "HLT", "BKNG", "ABNB", "EXPE"],
    },
    "Consumer Defensive": {
        "Beverages": ["KO", "PEP", "STZ", "MNST", "BUD"],
        "Household Products": ["PG", "CL", "CHD", "CLX", "EPC"],
        "Food & Staples Retail": ["COST", "WMT", "KR", "TGT", "SYY"],
        "Packaged Foods": ["MDLZ", "GIS", "K", "HSY", "CAG", "SJM"],
        "Tobacco": ["PM", "MO", "BTI"],
    },
    "Communication Services": {
        "Internet Content": ["GOOGL", "META", "SNAP", "PINS", "RDDT"],
        "Entertainment": ["NFLX", "DIS", "CMCSA", "WBD", "PARA"],
        "Telecom": ["TMUS", "VZ", "T"],
        "Gaming": ["EA", "TTWO", "RBLX", "U"],
        "Advertising": ["TTD", "MGNI", "DV"],
    },
    "Industrials": {
        "Aerospace & Defense": ["RTX", "BA", "LMT", "GD", "NOC", "HII", "LHX", "TDG"],
        "Industrial Conglomerates": ["GE", "HON", "MMM", "ITW", "EMR"],
        "Railroads": ["UNP", "CSX", "NSC"],
        "Machinery": ["CAT", "DE", "PH", "ETN", "ROK", "AME"],
        "Waste Management": ["WM", "RSG", "CWST"],
        "Electrical Equipment": ["APH", "TEL", "GNRC", "HUBB"],
    },
    "Energy": {
        "Oil & Gas Integrated": ["XOM", "CVX", "SHEL", "BP", "TTE"],
        "Oil & Gas E&P": ["COP", "EOG", "DVN", "PXD", "FANG", "OXY", "APA"],
        "Oil & Gas Midstream": ["WMB", "KMI", "OKE", "ET"],
        "Oil & Gas Services": ["SLB", "HAL", "BKR", "FTI"],
    },
    "Utilities": {
        "Electric Utilities": ["NEE", "SO", "DUK", "CEG", "SRE", "AEP", "D", "EXC", "XEL", "WEC"],
        "Water Utilities": ["AWK", "WTRG"],
        "Gas Utilities": ["ATO", "NI"],
    },
    "Real Estate": {
        "REITs": ["PLD", "AMT", "EQIX", "SPG", "PSA", "O", "WELL", "DLR", "CCI", "AVB"],
        "Real Estate Services": ["CBRE", "JLL"],
    },
    "Basic Materials": {
        "Chemicals": ["LIN", "APD", "SHW", "ECL", "DD", "PPG", "CE"],
        "Mining": ["FCX", "NEM", "GOLD"],
        "Steel": ["NUE", "STLD", "RS"],
        "Paper & Forest": ["IP", "PKG", "WRK"],
    },
}


def _get_candidates_from_gics(
    sector: str,
    industry: str,
    exclude_ticker: str,
    min_candidates: int = 5,
) -> list[str]:
    """Tiered GICS matching: sub-industry → industry-group → sector.

    Returns list of candidate tickers (excluding the original).
    """
    sector_dict = UNIVERSE.get(sector, {})
    if not sector_dict:
        # Fallback: try all sectors
        for s in UNIVERSE.values():
            for ind, tickers in s.items():
                if industry.lower() in ind.lower():
                    candidates = [t for t in tickers if t != exclude_ticker]
                    if len(candidates) >= min_candidates:
                        return candidates
        return []

    # Try exact industry match first
    for ind_name, tickers in sector_dict.items():
        if _industry_match(industry, ind_name):
            candidates = [t for t in tickers if t != exclude_ticker]
            if len(candidates) >= min_candidates:
                return candidates

    # Fall back to sector level (all industries)
    all_tickers: list[str] = []
    for tickers in sector_dict.values():
        all_tickers.extend(tickers)
    return [t for t in all_tickers if t != exclude_ticker]


def _industry_match(actual: str, category: str) -> bool:
    """Fuzzy match industry names."""
    a = actual.lower().replace("—", " ").replace("-", " ")
    c = category.lower().replace("—", " ").replace("-", " ")
    # Check if key words overlap
    a_words = set(a.split())
    c_words = set(c.split())
    return bool(a_words & c_words) or c in a or a in c


def _fetch_info(ticker: str) -> tuple[str, dict[str, Any] | None]:
    """Fetch yfinance info for a single ticker (for concurrent use)."""
    try:
        info = yf.Ticker(ticker).info or {}
        name = info.get("longName") or info.get("shortName")
        if not name:
            return ticker, None
        return ticker, info
    except Exception:
        logger.debug("Failed to fetch info for %s", ticker)
        return ticker, None


def _batch_fetch_info(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch yfinance info for multiple tickers concurrently."""
    results: dict[str, dict[str, Any]] = {}

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        futures = {executor.submit(_fetch_info, t): t for t in tickers}
        for future in as_completed(futures):
            try:
                ticker, info = future.result(timeout=15)
                if info is not None:
                    results[ticker] = info
            except Exception:
                pass

    return results


def _filter_and_gate(
    all_info: dict[str, dict[str, Any]],
    original_mcap: float | None,
) -> list[tuple[str, dict[str, Any]]]:
    """Apply market cap filter + quality gate to pre-fetched info.

    Combines what used to be _market_cap_filter + _quality_gate into one pass.
    """
    min_cap = original_mcap * 0.25 if original_mcap and original_mcap > 0 else 0
    max_cap = original_mcap * 4.0 if original_mcap and original_mcap > 0 else float("inf")

    passed: list[tuple[str, dict[str, Any]]] = []

    for ticker, info in all_info.items():
        # Market cap filter
        mcap = info.get("marketCap")
        if mcap is not None and original_mcap and original_mcap > 0:
            if mcap < min_cap or mcap > max_cap:
                continue

        # Quality gate: positive revenue
        revenue = info.get("totalRevenue")
        if revenue is not None and revenue <= 0:
            continue

        # Quality gate: operating margins not deeply negative
        op_margin = info.get("operatingMargins")
        if op_margin is not None and op_margin < -0.20:
            continue

        # Quality gate: debt-to-equity (relax for financials)
        d2e = info.get("debtToEquity")
        sector = info.get("sector", "")
        if d2e is not None and d2e > 500 and "Financial" not in sector:
            continue

        passed.append((ticker, info))

    return passed


def find_candidates(
    ticker: str,
    sector: str,
    industry: str,
    market_cap: float | None = None,
    max_candidates: int = 12,
) -> list[tuple[str, dict[str, Any]]]:
    """Run Stage 4: find replacement candidates.

    Uses concurrent yfinance fetching — a single batch call replaces
    the previous sequential market_cap_filter + quality_gate.
    """
    # Step 1: GICS matching
    raw = _get_candidates_from_gics(sector, industry, ticker)
    logger.info("Stage 4: %d raw GICS candidates for %s (%s / %s)", len(raw), ticker, sector, industry)

    # Limit to a reasonable number before fetching
    to_fetch = raw[:max_candidates + 5]

    # Step 2: Batch fetch all info concurrently (~3-5s instead of 30-60s sequential)
    logger.info("Stage 4: batch-fetching info for %d candidates", len(to_fetch))
    all_info = _batch_fetch_info(to_fetch)
    logger.info("Stage 4: got info for %d candidates", len(all_info))

    # Step 3: Market cap + quality gate in single pass
    qualified = _filter_and_gate(all_info, market_cap)
    logger.info("Stage 4: %d passed market cap + quality gate", len(qualified))

    return qualified[:max_candidates]
