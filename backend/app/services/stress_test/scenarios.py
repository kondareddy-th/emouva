"""Pre-built stress test scenario library.

Stored as Python code (not DB) for version control, fast loading, and
determinism. Each scenario defines sector-level impacts, factor adjustments,
and historical calibration data.

Version bumps invalidate caches.
"""

from dataclasses import dataclass

SCENARIO_VERSION = "2026.1"


@dataclass(frozen=True)
class ScenarioDefinition:
    id: str
    name: str
    category: str  # historical | macro | geopolitical | sector | black_swan
    severity: int  # 1-10
    description: str
    sp500_impact: float  # estimated S&P 500 % change
    duration_months: int  # typical duration
    tags: tuple[str, ...]

    # Core impact model
    sector_impacts: dict[str, float]  # sector → % change
    factor_adjustments: dict[str, float]  # factor → additional adjustment
    affected_regions: tuple[str, ...]  # regions with amplified impact
    correlation_stress_multiplier: float  # how much correlations spike (1.0-2.5)

    # Historical validation (for blending with actual data)
    historical_date_range: str | None = None  # "2007-10 to 2009-03"
    actual_stock_impacts: dict[str, float] | None = None  # symbol → actual %

    version: str = SCENARIO_VERSION


# ── Helpers ─────────────────────────────────────────────────────

# Default sector impact used when a scenario doesn't specify a sector
_DEFAULT_KEY = "_default"


# ── SCENARIOS ───────────────────────────────────────────────────

SCENARIOS: dict[str, ScenarioDefinition] = {

    # ═══════════════════════════════════════════════════════════
    # HISTORICAL (8 scenarios)
    # ═══════════════════════════════════════════════════════════

    "2008_financial_crisis": ScenarioDefinition(
        id="2008_financial_crisis",
        name="2008 Financial Crisis",
        category="historical",
        severity=9,
        description="Lehman collapse, credit freeze, global deleveraging",
        sp500_impact=-56.8,
        duration_months=17,
        tags=("recession", "credit", "banking", "housing"),
        sector_impacts={
            "Technology": -50, "Electronic Technology": -50,
            "Technology Services": -45, "Finance": -60,
            "Retail Trade": -40, "Health Technology": -20,
            "Utilities": -15, "Consumer Non-Durables": -25,
            "Energy Minerals": -55, "Non-Energy Minerals": -45,
            "Producer Manufacturing": -40, "Commercial Services": -35,
            "Health Services": -18, "Transportation": -45,
            "Consumer Services": -35, "Communications": -40,
            "Industrial Services": -42, "Distribution Services": -38,
            "Process Industries": -40,
            _DEFAULT_KEY: -38,
        },
        factor_adjustments={
            "leverage": -8.0,
            "rate_sensitivity": -5.0,
            "consumer_cyclical": -6.0,
        },
        affected_regions=("US", "Europe"),
        correlation_stress_multiplier=2.2,
        historical_date_range="2007-10 to 2009-03",
        actual_stock_impacts={
            "AAPL": -57, "MSFT": -46, "GOOG": -56, "AMZN": -55,
            "JPM": -68, "BAC": -90, "GS": -70, "C": -95,
            "XOM": -25, "JNJ": -10, "PG": -15, "KO": -25,
            "GE": -82, "F": -80, "GM": -95,
        },
    ),

    "covid_crash": ScenarioDefinition(
        id="covid_crash",
        name="COVID Crash (Mar 2020)",
        category="historical",
        severity=7,
        description="Pandemic lockdowns, supply chain collapse, demand evaporation — fastest 30%+ drop in history",
        sp500_impact=-33.9,
        duration_months=2,
        tags=("pandemic", "lockdown", "supply_chain", "v_recovery"),
        sector_impacts={
            "Technology": -25, "Electronic Technology": -30,
            "Technology Services": -20, "Finance": -35,
            "Retail Trade": -30, "Health Technology": -10,
            "Utilities": -20, "Consumer Services": -45,
            "Energy Minerals": -60, "Transportation": -50,
            "Communications": -18, "Consumer Non-Durables": -15,
            "Health Services": -12, "Producer Manufacturing": -30,
            _DEFAULT_KEY: -28,
        },
        factor_adjustments={
            "travel_exposure": -15.0,
            "digital_revenue": 5.0,
            "leverage": -5.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=2.0,
        historical_date_range="2020-02 to 2020-03",
        actual_stock_impacts={
            "AAPL": -31, "MSFT": -26, "AMZN": -16, "GOOG": -30,
            "ZM": 40, "NFLX": 5, "BA": -72, "DAL": -62,
            "XOM": -55, "JPM": -38, "DIS": -35, "TSLA": -60,
        },
    ),

    "dot_com_crash": ScenarioDefinition(
        id="dot_com_crash",
        name="Dot-com Bubble Burst (2000)",
        category="historical",
        severity=8,
        description="Internet bubble pops — NASDAQ falls 78%, unprofitable tech wiped out",
        sp500_impact=-49.0,
        duration_months=30,
        tags=("tech", "bubble", "valuation", "nasdaq"),
        sector_impacts={
            "Technology": -70, "Electronic Technology": -75,
            "Technology Services": -65, "Finance": -25,
            "Retail Trade": -20, "Health Technology": -30,
            "Utilities": -5, "Consumer Non-Durables": -10,
            "Energy Minerals": 15, "Communications": -60,
            _DEFAULT_KEY: -25,
        },
        factor_adjustments={
            "pe_ratio_premium": -15.0,
            "rate_sensitivity": -3.0,
            "dividend_yield_high": 5.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.8,
        historical_date_range="2000-03 to 2002-10",
        actual_stock_impacts={
            "MSFT": -65, "INTC": -82, "CSCO": -89, "ORCL": -84,
            "AMZN": -93, "AAPL": -80, "JNJ": 10, "PG": 5,
        },
    ),

    "2022_rate_hike_cycle": ScenarioDefinition(
        id="2022_rate_hike_cycle",
        name="2022 Rate Hike Cycle",
        category="historical",
        severity=6,
        description="Fed raises rates from 0% to 5.25% — growth stocks repriced, value outperforms by 33pp",
        sp500_impact=-25.0,
        duration_months=10,
        tags=("rates", "fed", "growth", "duration"),
        sector_impacts={
            "Technology": -30, "Electronic Technology": -40,
            "Technology Services": -28, "Finance": -5,
            "Retail Trade": -15, "Health Technology": -15,
            "Utilities": -10, "Consumer Non-Durables": -5,
            "Energy Minerals": 45, "Communications": -35,
            _DEFAULT_KEY: -18,
        },
        factor_adjustments={
            "pe_ratio_premium": -10.0,
            "rate_sensitivity": -8.0,
            "dividend_yield_high": 5.0,
            "energy_producer": 12.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.5,
        historical_date_range="2022-01 to 2022-10",
        actual_stock_impacts={
            "TSLA": -73, "NVDA": -66, "META": -76, "AMZN": -51,
            "AAPL": -28, "MSFT": -32, "XOM": 59, "CVX": 40,
            "JNJ": -3, "KO": -5,
        },
    ),

    "1987_black_monday": ScenarioDefinition(
        id="1987_black_monday",
        name="1987 Black Monday",
        category="historical",
        severity=8,
        description="S&P drops 20% in one day — the fastest single-day crash in modern history",
        sp500_impact=-33.5,
        duration_months=3,
        tags=("crash", "single_day", "liquidity", "panic"),
        sector_impacts={
            "Technology": -35, "Electronic Technology": -38,
            "Technology Services": -30, "Finance": -40,
            "Retail Trade": -25, "Health Technology": -20,
            "Utilities": -15, "Energy Minerals": -30,
            _DEFAULT_KEY: -30,
        },
        factor_adjustments={
            "leverage": -6.0,
        },
        affected_regions=("US", "Europe", "Asia-Pacific"),
        correlation_stress_multiplier=2.5,
        historical_date_range="1987-10 to 1987-12",
        actual_stock_impacts={},
    ),

    "svb_banking_crisis": ScenarioDefinition(
        id="svb_banking_crisis",
        name="SVB Banking Crisis (2023)",
        category="historical",
        severity=4,
        description="Regional bank failures trigger flight to safety — contained by Fed backstop",
        sp500_impact=-8.0,
        duration_months=2,
        tags=("banking", "regional_banks", "contagion", "deposit_flight"),
        sector_impacts={
            "Technology": -5, "Finance": -25,
            "Health Technology": -3, "Utilities": 2,
            "Energy Minerals": -5, "Consumer Non-Durables": -2,
            _DEFAULT_KEY: -6,
        },
        factor_adjustments={
            "leverage": -5.0,
            "rate_sensitivity": -3.0,
        },
        affected_regions=("US",),
        correlation_stress_multiplier=1.3,
        historical_date_range="2023-03 to 2023-05",
        actual_stock_impacts={
            "SIVB": -100, "FRC": -97, "SCHW": -35, "JPM": -5,
            "AAPL": 2, "MSFT": 5, "GOOG": 3,
        },
    ),

    "european_debt_crisis": ScenarioDefinition(
        id="european_debt_crisis",
        name="European Debt Crisis (2011)",
        category="historical",
        severity=5,
        description="Greek debt crisis threatens eurozone breakup — global risk-off",
        sp500_impact=-19.0,
        duration_months=5,
        tags=("sovereign_debt", "europe", "contagion", "euro"),
        sector_impacts={
            "Technology": -15, "Finance": -25,
            "Health Technology": -8, "Utilities": -5,
            "Energy Minerals": -20, "Consumer Non-Durables": -8,
            _DEFAULT_KEY: -15,
        },
        factor_adjustments={
            "leverage": -4.0,
        },
        affected_regions=("Europe",),
        correlation_stress_multiplier=1.5,
        historical_date_range="2011-07 to 2011-11",
        actual_stock_impacts={},
    ),

    "oil_crash_2014": ScenarioDefinition(
        id="oil_crash_2014",
        name="Oil Crash (2014-2016)",
        category="historical",
        severity=5,
        description="OPEC floods market — oil drops from $115 to $26, energy sector decimated",
        sp500_impact=-14.0,
        duration_months=18,
        tags=("oil", "energy", "commodity", "opec"),
        sector_impacts={
            "Technology": -5, "Finance": -10,
            "Energy Minerals": -55, "Utilities": -5,
            "Transportation": 10, "Consumer Services": 5,
            "Consumer Non-Durables": 3,
            _DEFAULT_KEY: -8,
        },
        factor_adjustments={
            "energy_producer": -30.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.2,
        historical_date_range="2014-06 to 2016-02",
        actual_stock_impacts={
            "XOM": -35, "CVX": -40, "COP": -55, "SLB": -60,
            "AAPL": 15, "AMZN": 80, "DAL": 40,
        },
    ),

    # ═══════════════════════════════════════════════════════════
    # MACRO (7 scenarios)
    # ═══════════════════════════════════════════════════════════

    "rate_hike_200bps": ScenarioDefinition(
        id="rate_hike_200bps",
        name="Rate Hike +200bps",
        category="macro",
        severity=5,
        description="Fed raises rates 200 basis points over 6 months — growth stocks reprice, housing slows",
        sp500_impact=-15.0,
        duration_months=6,
        tags=("rates", "fed", "duration", "growth"),
        sector_impacts={
            "Technology": -20, "Electronic Technology": -25,
            "Technology Services": -18, "Finance": 5,
            "Retail Trade": -10, "Health Technology": -12,
            "Utilities": -15, "Energy Minerals": 0,
            _DEFAULT_KEY: -12,
        },
        factor_adjustments={
            "rate_sensitivity": -8.0,
            "pe_ratio_premium": -6.0,
            "dividend_yield_high": 3.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.3,
    ),

    "recession_mild": ScenarioDefinition(
        id="recession_mild",
        name="Mild Recession",
        category="macro",
        severity=5,
        description="GDP contracts 1-2%, unemployment rises to 6%, consumer spending slows",
        sp500_impact=-20.0,
        duration_months=8,
        tags=("recession", "gdp", "unemployment", "consumer"),
        sector_impacts={
            "Technology": -18, "Electronic Technology": -22,
            "Technology Services": -15, "Finance": -20,
            "Retail Trade": -25, "Health Technology": -8,
            "Utilities": -5, "Consumer Non-Durables": -8,
            "Consumer Services": -28, "Energy Minerals": -15,
            _DEFAULT_KEY: -16,
        },
        factor_adjustments={
            "consumer_cyclical": -6.0,
            "leverage": -4.0,
        },
        affected_regions=("US",),
        correlation_stress_multiplier=1.5,
    ),

    "stagflation": ScenarioDefinition(
        id="stagflation",
        name="Stagflation (Inflation + Stagnation)",
        category="macro",
        severity=7,
        description="Inflation stays above 6% while GDP stagnates — worst of both worlds, 1970s replay",
        sp500_impact=-28.0,
        duration_months=14,
        tags=("inflation", "stagnation", "rates", "commodity"),
        sector_impacts={
            "Technology": -30, "Electronic Technology": -35,
            "Technology Services": -25, "Finance": -15,
            "Retail Trade": -25, "Health Technology": -12,
            "Utilities": -8, "Consumer Non-Durables": -10,
            "Energy Minerals": 20, "Non-Energy Minerals": 10,
            _DEFAULT_KEY: -20,
        },
        factor_adjustments={
            "pe_ratio_premium": -8.0,
            "rate_sensitivity": -6.0,
            "energy_producer": 8.0,
            "commodity_producer": 5.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.6,
    ),

    "dollar_collapse": ScenarioDefinition(
        id="dollar_collapse",
        name="US Dollar Collapse (-20%)",
        category="macro",
        severity=6,
        description="Dollar index drops 20% — import inflation surges, foreign earnings boost, gold spikes",
        sp500_impact=-12.0,
        duration_months=12,
        tags=("currency", "dollar", "forex", "inflation"),
        sector_impacts={
            "Technology": -5, "Finance": -15,
            "Consumer Non-Durables": -8, "Health Technology": -5,
            "Energy Minerals": 15, "Non-Energy Minerals": 20,
            "Retail Trade": -12,
            _DEFAULT_KEY: -8,
        },
        factor_adjustments={
            "international_revenue": 5.0,
            "commodity_producer": 8.0,
        },
        affected_regions=("US",),
        correlation_stress_multiplier=1.3,
    ),

    "inflation_surge": ScenarioDefinition(
        id="inflation_surge",
        name="Inflation Surge to 8%+",
        category="macro",
        severity=5,
        description="CPI surges past 8% — Fed forced to hike aggressively, consumer spending plummets",
        sp500_impact=-18.0,
        duration_months=8,
        tags=("inflation", "cpi", "consumer", "rates"),
        sector_impacts={
            "Technology": -22, "Electronic Technology": -25,
            "Technology Services": -18, "Finance": -8,
            "Retail Trade": -20, "Health Technology": -10,
            "Utilities": -8, "Consumer Services": -25,
            "Energy Minerals": 12, "Consumer Non-Durables": -12,
            _DEFAULT_KEY: -14,
        },
        factor_adjustments={
            "rate_sensitivity": -6.0,
            "consumer_cyclical": -5.0,
            "energy_producer": 5.0,
        },
        affected_regions=("US",),
        correlation_stress_multiplier=1.4,
    ),

    "credit_spread_blowout": ScenarioDefinition(
        id="credit_spread_blowout",
        name="Credit Spread Blowout",
        category="macro",
        severity=6,
        description="Investment-grade spreads widen 200bps, high-yield 500bps — corporate borrowing freezes",
        sp500_impact=-22.0,
        duration_months=6,
        tags=("credit", "bonds", "spreads", "corporate_debt"),
        sector_impacts={
            "Technology": -15, "Finance": -30,
            "Retail Trade": -20, "Health Technology": -8,
            "Utilities": -12, "Energy Minerals": -18,
            "Consumer Services": -22,
            _DEFAULT_KEY: -16,
        },
        factor_adjustments={
            "leverage": -10.0,
            "rate_sensitivity": -5.0,
        },
        affected_regions=("US", "Europe"),
        correlation_stress_multiplier=1.7,
    ),

    "us_debt_downgrade": ScenarioDefinition(
        id="us_debt_downgrade",
        name="US Debt Downgrade",
        category="macro",
        severity=4,
        description="Another US credit downgrade — treasury yields spike, dollar weakens, risk-off",
        sp500_impact=-10.0,
        duration_months=3,
        tags=("sovereign", "treasury", "downgrade", "fiscal"),
        sector_impacts={
            "Technology": -8, "Finance": -15,
            "Utilities": -5, "Health Technology": -5,
            _DEFAULT_KEY: -8,
        },
        factor_adjustments={
            "rate_sensitivity": -3.0,
        },
        affected_regions=("US",),
        correlation_stress_multiplier=1.2,
    ),

    # ═══════════════════════════════════════════════════════════
    # GEOPOLITICAL (6 scenarios)
    # ═══════════════════════════════════════════════════════════

    "china_taiwan_conflict": ScenarioDefinition(
        id="china_taiwan_conflict",
        name="China-Taiwan Military Conflict",
        category="geopolitical",
        severity=10,
        description="Military blockade or invasion of Taiwan — semiconductor supply severed, trade sanctions",
        sp500_impact=-30.0,
        duration_months=12,
        tags=("geopolitical", "semiconductor", "china", "taiwan", "supply_chain"),
        sector_impacts={
            "Technology": -35, "Electronic Technology": -55,
            "Technology Services": -25, "Finance": -20,
            "Retail Trade": -18, "Health Technology": -12,
            "Utilities": -8, "Energy Minerals": 15,
            "Producer Manufacturing": -30,
            _DEFAULT_KEY: -20,
        },
        factor_adjustments={
            "taiwan_supply_chain": -25.0,
            "china_revenue": -20.0,
            "semiconductor": -20.0,
            "defense_contractor": 8.0,
            "energy_producer": 5.0,
        },
        affected_regions=("China", "Asia-Pacific"),
        correlation_stress_multiplier=2.0,
    ),

    "us_china_trade_war_max": ScenarioDefinition(
        id="us_china_trade_war_max",
        name="US-China Trade War Escalation",
        category="geopolitical",
        severity=7,
        description="Full decoupling — 50%+ tariffs on all goods, tech export ban, rare earth restrictions",
        sp500_impact=-22.0,
        duration_months=10,
        tags=("trade_war", "tariffs", "china", "decoupling"),
        sector_impacts={
            "Technology": -30, "Electronic Technology": -40,
            "Technology Services": -22, "Finance": -12,
            "Retail Trade": -20, "Health Technology": -8,
            "Utilities": -3, "Consumer Non-Durables": -15,
            "Energy Minerals": -5, "Producer Manufacturing": -25,
            _DEFAULT_KEY: -15,
        },
        factor_adjustments={
            "china_revenue": -15.0,
            "semiconductor": -12.0,
            "taiwan_supply_chain": -10.0,
        },
        affected_regions=("China", "Asia-Pacific"),
        correlation_stress_multiplier=1.6,
        actual_stock_impacts={
            "NVDA": -56, "AAPL": -38, "BA": -15,
        },
    ),

    "middle_east_oil_shock": ScenarioDefinition(
        id="middle_east_oil_shock",
        name="Middle East Oil Shock",
        category="geopolitical",
        severity=7,
        description="Strait of Hormuz blocked — oil spikes to $150+, global supply chain disrupted",
        sp500_impact=-18.0,
        duration_months=6,
        tags=("oil", "geopolitical", "middle_east", "energy"),
        sector_impacts={
            "Technology": -12, "Finance": -15,
            "Retail Trade": -18, "Health Technology": -5,
            "Utilities": -10, "Consumer Services": -22,
            "Energy Minerals": 35, "Transportation": -30,
            "Consumer Non-Durables": -10,
            _DEFAULT_KEY: -12,
        },
        factor_adjustments={
            "energy_producer": 15.0,
            "travel_exposure": -10.0,
        },
        affected_regions=("Middle East",),
        correlation_stress_multiplier=1.5,
    ),

    "russia_nato_escalation": ScenarioDefinition(
        id="russia_nato_escalation",
        name="Russia-NATO Escalation",
        category="geopolitical",
        severity=8,
        description="Direct NATO-Russia military confrontation — European energy crisis, defense surge",
        sp500_impact=-22.0,
        duration_months=8,
        tags=("geopolitical", "russia", "nato", "europe", "energy"),
        sector_impacts={
            "Technology": -15, "Finance": -20,
            "Energy Minerals": 25, "Utilities": -15,
            "Consumer Services": -20, "Transportation": -25,
            _DEFAULT_KEY: -15,
        },
        factor_adjustments={
            "defense_contractor": 12.0,
            "energy_producer": 10.0,
        },
        affected_regions=("Europe", "Russia"),
        correlation_stress_multiplier=1.8,
    ),

    "iran_strait_closure": ScenarioDefinition(
        id="iran_strait_closure",
        name="Iran Closes Strait of Hormuz",
        category="geopolitical",
        severity=6,
        description="Iran mines the strait — 20% of global oil supply disrupted, shipping rates spike",
        sp500_impact=-15.0,
        duration_months=4,
        tags=("iran", "oil", "shipping", "geopolitical"),
        sector_impacts={
            "Technology": -8, "Finance": -10,
            "Energy Minerals": 30, "Transportation": -25,
            "Consumer Services": -15, "Retail Trade": -12,
            _DEFAULT_KEY: -10,
        },
        factor_adjustments={
            "energy_producer": 12.0,
            "travel_exposure": -8.0,
        },
        affected_regions=("Middle East",),
        correlation_stress_multiplier=1.4,
    ),

    "election_contested": ScenarioDefinition(
        id="election_contested",
        name="Contested US Election",
        category="geopolitical",
        severity=5,
        description="Election results disputed — constitutional crisis, institutional uncertainty",
        sp500_impact=-12.0,
        duration_months=3,
        tags=("election", "politics", "uncertainty", "institutional"),
        sector_impacts={
            "Technology": -10, "Finance": -15,
            "Health Technology": -8, "Utilities": -5,
            "Energy Minerals": -8,
            _DEFAULT_KEY: -10,
        },
        factor_adjustments={},
        affected_regions=("US",),
        correlation_stress_multiplier=1.3,
    ),

    # ═══════════════════════════════════════════════════════════
    # SECTOR (6 scenarios)
    # ═══════════════════════════════════════════════════════════

    "ai_bubble_burst": ScenarioDefinition(
        id="ai_bubble_burst",
        name="AI Bubble Burst",
        category="sector",
        severity=7,
        description="AI hype cycle peaks — earnings disappoint, capex pullback, multiple compression for AI plays",
        sp500_impact=-22.0,
        duration_months=8,
        tags=("ai", "tech", "bubble", "valuation"),
        sector_impacts={
            "Technology": -40, "Electronic Technology": -50,
            "Technology Services": -38, "Finance": -12,
            "Retail Trade": -10, "Health Technology": -8,
            "Utilities": 5, "Energy Minerals": -8,
            _DEFAULT_KEY: -12,
        },
        factor_adjustments={
            "ai_revenue_pct": -20.0,
            "semiconductor": -15.0,
            "cloud_infrastructure": -12.0,
            "pe_ratio_premium": -8.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.6,
    ),

    "ev_bubble_burst": ScenarioDefinition(
        id="ev_bubble_burst",
        name="EV Bubble Burst",
        category="sector",
        severity=6,
        description="EV demand plateau, Chinese competition, subsidy cuts — legacy auto rebounds",
        sp500_impact=-8.0,
        duration_months=10,
        tags=("ev", "auto", "clean_energy", "competition"),
        sector_impacts={
            "Technology": -8, "Electronic Technology": -15,
            "Producer Manufacturing": -20, "Energy Minerals": 5,
            "Consumer Non-Durables": -3,
            _DEFAULT_KEY: -5,
        },
        factor_adjustments={
            "ev_exposure": -25.0,
            "semiconductor": -5.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.2,
    ),

    "crypto_contagion": ScenarioDefinition(
        id="crypto_contagion",
        name="Crypto Contagion",
        category="sector",
        severity=5,
        description="Major crypto exchange collapse — contagion to fintech, regulatory crackdown",
        sp500_impact=-8.0,
        duration_months=4,
        tags=("crypto", "fintech", "contagion", "regulation"),
        sector_impacts={
            "Technology": -10, "Finance": -15,
            "Technology Services": -12,
            _DEFAULT_KEY: -5,
        },
        factor_adjustments={
            "crypto_exposure": -30.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.2,
    ),

    "bank_run_contagion": ScenarioDefinition(
        id="bank_run_contagion",
        name="Systemic Bank Run",
        category="sector",
        severity=8,
        description="Multiple large banks face deposit flight — credit markets freeze, lending stops",
        sp500_impact=-30.0,
        duration_months=8,
        tags=("banking", "contagion", "credit", "liquidity"),
        sector_impacts={
            "Technology": -20, "Finance": -50,
            "Retail Trade": -25, "Health Technology": -10,
            "Utilities": -8, "Consumer Services": -30,
            "Energy Minerals": -15,
            _DEFAULT_KEY: -22,
        },
        factor_adjustments={
            "leverage": -12.0,
        },
        affected_regions=("US", "Europe"),
        correlation_stress_multiplier=2.0,
    ),

    "tech_regulation_crackdown": ScenarioDefinition(
        id="tech_regulation_crackdown",
        name="Big Tech Regulatory Crackdown",
        category="sector",
        severity=5,
        description="Antitrust breakups, Section 230 repeal, EU Digital Markets Act enforcement — big tech reprices",
        sp500_impact=-12.0,
        duration_months=12,
        tags=("regulation", "antitrust", "big_tech", "platform"),
        sector_impacts={
            "Technology": -25, "Technology Services": -30,
            "Communications": -28, "Finance": -5,
            _DEFAULT_KEY: -5,
        },
        factor_adjustments={
            "pe_ratio_premium": -5.0,
        },
        affected_regions=("US", "Europe"),
        correlation_stress_multiplier=1.2,
    ),

    "semiconductor_shortage_extreme": ScenarioDefinition(
        id="semiconductor_shortage_extreme",
        name="Extreme Semiconductor Shortage",
        category="sector",
        severity=6,
        description="Major fab disruption (earthquake, fire) — 6-12 month chip shortage, auto & electronics impacted",
        sp500_impact=-10.0,
        duration_months=8,
        tags=("semiconductor", "supply_chain", "manufacturing"),
        sector_impacts={
            "Technology": -15, "Electronic Technology": -8,  # chip makers rally
            "Producer Manufacturing": -20, "Retail Trade": -12,
            "Transportation": -10,
            _DEFAULT_KEY: -8,
        },
        factor_adjustments={
            "semiconductor": 5.0,  # chip companies with inventory benefit
            "taiwan_supply_chain": -15.0,
        },
        affected_regions=("Asia-Pacific",),
        correlation_stress_multiplier=1.3,
    ),

    # ═══════════════════════════════════════════════════════════
    # BLACK SWAN (3 scenarios)
    # ═══════════════════════════════════════════════════════════

    "pandemic_novel": ScenarioDefinition(
        id="pandemic_novel",
        name="Novel Pandemic (Worse than COVID)",
        category="black_swan",
        severity=9,
        description="New pathogen with higher fatality rate — extended lockdowns, supply chain collapse",
        sp500_impact=-40.0,
        duration_months=6,
        tags=("pandemic", "lockdown", "supply_chain", "global"),
        sector_impacts={
            "Technology": -20, "Electronic Technology": -25,
            "Technology Services": -15, "Finance": -35,
            "Retail Trade": -40, "Health Technology": 10,
            "Utilities": -15, "Consumer Services": -55,
            "Energy Minerals": -50, "Transportation": -60,
            _DEFAULT_KEY: -30,
        },
        factor_adjustments={
            "travel_exposure": -20.0,
            "digital_revenue": 8.0,
            "leverage": -8.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=2.3,
    ),

    "global_internet_outage": ScenarioDefinition(
        id="global_internet_outage",
        name="Global Internet Outage (72h)",
        category="black_swan",
        severity=8,
        description="Major undersea cable damage + BGP failure — 72h global internet disruption",
        sp500_impact=-15.0,
        duration_months=2,
        tags=("infrastructure", "internet", "cyber", "disruption"),
        sector_impacts={
            "Technology": -25, "Technology Services": -30,
            "Finance": -20, "Retail Trade": -15,
            "Communications": -35, "Health Technology": -10,
            "Utilities": -3, "Energy Minerals": -5,
            _DEFAULT_KEY: -10,
        },
        factor_adjustments={
            "digital_revenue": -15.0,
            "cloud_infrastructure": -20.0,
        },
        affected_regions=(),
        correlation_stress_multiplier=1.8,
    ),

    "climate_event_catastrophic": ScenarioDefinition(
        id="climate_event_catastrophic",
        name="Catastrophic Climate Event",
        category="black_swan",
        severity=7,
        description="Category 6 hurricane hits major financial center, or multi-year drought devastates agriculture",
        sp500_impact=-15.0,
        duration_months=6,
        tags=("climate", "natural_disaster", "insurance", "agriculture"),
        sector_impacts={
            "Technology": -8, "Finance": -20,
            "Retail Trade": -15, "Health Technology": -5,
            "Utilities": -15, "Energy Minerals": 10,
            "Consumer Non-Durables": -10,
            _DEFAULT_KEY: -10,
        },
        factor_adjustments={
            "energy_producer": 5.0,
        },
        affected_regions=("US",),
        correlation_stress_multiplier=1.4,
    ),
}


# ── Helpers ─────────────────────────────────────────────────────


def get_scenario(scenario_id: str) -> ScenarioDefinition | None:
    return SCENARIOS.get(scenario_id)


def list_categories() -> list[str]:
    return sorted(set(s.category for s in SCENARIOS.values()))


def list_scenarios_by_category(category: str | None = None) -> list[ScenarioDefinition]:
    scenarios = list(SCENARIOS.values())
    if category:
        scenarios = [s for s in scenarios if s.category == category]
    return scenarios
