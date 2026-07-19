"""
Stage 7: ETF Alternative Mapping

Static GICS sector → ETF mapping. Always provides an ETF option.
Sub-industry ETFs offered when available with AUM > $1B and ER < 0.50%.

100% deterministic — no LLM involvement.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.replacement import ETFAlternative


@dataclass(frozen=True)
class ETFEntry:
    ticker: str
    name: str
    expense_ratio: float
    top_holdings: tuple[str, ...]  # top ~5 tickers


# ── Sector SPDRs (11 GICS sectors) ──────────────────────────────────

SECTOR_ETFS: dict[str, ETFEntry] = {
    "Technology": ETFEntry("XLK", "Technology Select Sector SPDR", 0.0008, ("AAPL", "MSFT", "NVDA", "AVGO", "CRM")),
    "Healthcare": ETFEntry("XLV", "Health Care Select Sector SPDR", 0.0008, ("UNH", "JNJ", "LLY", "ABBV", "MRK")),
    "Financial Services": ETFEntry("XLF", "Financial Select Sector SPDR", 0.0008, ("BRK-B", "JPM", "V", "MA", "BAC")),
    "Financials": ETFEntry("XLF", "Financial Select Sector SPDR", 0.0008, ("BRK-B", "JPM", "V", "MA", "BAC")),
    "Consumer Cyclical": ETFEntry("XLY", "Consumer Discretionary Select SPDR", 0.0008, ("AMZN", "TSLA", "HD", "MCD", "NKE")),
    "Consumer Defensive": ETFEntry("XLP", "Consumer Staples Select Sector SPDR", 0.0008, ("PG", "KO", "PEP", "COST", "WMT")),
    "Communication Services": ETFEntry("XLC", "Communication Services Select SPDR", 0.0008, ("META", "GOOGL", "NFLX", "TMUS", "DIS")),
    "Industrials": ETFEntry("XLI", "Industrial Select Sector SPDR", 0.0008, ("GE", "CAT", "RTX", "UNP", "HON")),
    "Energy": ETFEntry("XLE", "Energy Select Sector SPDR", 0.0008, ("XOM", "CVX", "COP", "EOG", "SLB")),
    "Utilities": ETFEntry("XLU", "Utilities Select Sector SPDR", 0.0008, ("NEE", "SO", "DUK", "CEG", "SRE")),
    "Real Estate": ETFEntry("XLRE", "Real Estate Select Sector SPDR", 0.0008, ("PLD", "AMT", "EQIX", "SPG", "PSA")),
    "Basic Materials": ETFEntry("XLB", "Materials Select Sector SPDR", 0.0008, ("LIN", "APD", "SHW", "FCX", "ECL")),
}

# ── Sub-Industry ETFs (higher specificity when available) ────────────

SUB_INDUSTRY_ETFS: dict[str, ETFEntry] = {
    "Semiconductors": ETFEntry("SOXX", "iShares Semiconductor ETF", 0.0035, ("NVDA", "AVGO", "AMD", "TXN", "QCOM")),
    "Semiconductor Equipment": ETFEntry("SOXX", "iShares Semiconductor ETF", 0.0035, ("NVDA", "AVGO", "AMD", "TXN", "QCOM")),
    "Biotechnology": ETFEntry("IBB", "iShares Biotechnology ETF", 0.0044, ("VRTX", "GILD", "AMGN", "REGN", "MRNA")),
    "Software": ETFEntry("IGV", "iShares Expanded Tech-Software ETF", 0.0040, ("MSFT", "CRM", "ORCL", "ADBE", "INTU")),
    "Software—Application": ETFEntry("IGV", "iShares Expanded Tech-Software ETF", 0.0040, ("MSFT", "CRM", "ORCL", "ADBE", "INTU")),
    "Software—Infrastructure": ETFEntry("IGV", "iShares Expanded Tech-Software ETF", 0.0040, ("MSFT", "CRM", "ORCL", "ADBE", "INTU")),
    "Banks—Diversified": ETFEntry("KBE", "SPDR S&P Bank ETF", 0.0035, ("JPM", "BAC", "WFC", "C", "USB")),
    "Banks—Regional": ETFEntry("KRE", "SPDR S&P Regional Banking ETF", 0.0035, ("CFG", "RF", "HBAN", "KEY", "MTB")),
    "Oil & Gas E&P": ETFEntry("XOP", "SPDR S&P Oil & Gas Exploration ETF", 0.0035, ("DVN", "COP", "EOG", "MPC", "VLO")),
    "Oil & Gas Integrated": ETFEntry("XLE", "Energy Select Sector SPDR", 0.0008, ("XOM", "CVX", "COP", "EOG", "SLB")),
    "Internet Content & Information": ETFEntry("SKYY", "First Trust Cloud Computing ETF", 0.0060, ("GOOGL", "META", "AMZN", "MSFT", "CRM")),
    "Aerospace & Defense": ETFEntry("ITA", "iShares U.S. Aerospace & Defense ETF", 0.0040, ("RTX", "BA", "LMT", "GD", "NOC")),
    "Medical Devices": ETFEntry("IHI", "iShares U.S. Medical Devices ETF", 0.0040, ("ABT", "TMO", "SYK", "ISRG", "MDT")),
    "Drug Manufacturers": ETFEntry("XLV", "Health Care Select Sector SPDR", 0.0008, ("UNH", "JNJ", "LLY", "ABBV", "MRK")),
    "Residential Construction": ETFEntry("XHB", "SPDR S&P Homebuilders ETF", 0.0035, ("DHI", "LEN", "NVR", "PHM", "TOL")),
    "REITs": ETFEntry("VNQ", "Vanguard Real Estate ETF", 0.0012, ("PLD", "AMT", "EQIX", "SPG", "PSA")),
}


def get_sector_etf(sector: str) -> str:
    """Get the sector SPDR ticker for a given sector name."""
    entry = SECTOR_ETFS.get(sector)
    return entry.ticker if entry else "SPY"


def get_etf_alternative(
    sector: str,
    industry: str,
    position_value: float | None = None,
) -> ETFAlternative:
    """Build the ETF alternative for Stage 7.

    Prefers sub-industry ETF when available, falls back to sector SPDR.
    """
    # Try sub-industry match first
    sub = SUB_INDUSTRY_ETFS.get(industry)
    sec = SECTOR_ETFS.get(sector)

    if sub:
        entry = sub
        is_sub = True
    elif sec:
        entry = sec
        is_sub = False
    else:
        # Fallback to SPY
        entry = ETFEntry("SPY", "SPDR S&P 500 ETF", 0.0003, ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL"))
        is_sub = False

    annual_cost = None
    if position_value and position_value > 0:
        annual_cost = round(position_value * entry.expense_ratio, 2)

    return ETFAlternative(
        ticker=entry.ticker,
        name=entry.name,
        expense_ratio=entry.expense_ratio,
        top_holdings=list(entry.top_holdings),
        is_sub_industry=is_sub,
        annual_cost_on_position=annual_cost,
    )
