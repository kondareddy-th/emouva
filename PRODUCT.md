# Aegis — AI Investment Portfolio Intelligence

## One-liner
Aegis tells you what your broker won't — what's actually wrong with your portfolio and what to do about it.

## Target User (v1)
US-based retail investors using Robinhood (expand to other brokers later) who:
- Are not financially sophisticated (no finance degree, no advisor)
- Have $5k-$100k invested
- Make their own decisions but don't have the tools or time to analyze deeply
- Want clarity, not more data

## Long-term Vision
Bring investment intelligence to the 600M+ Indians with zero investment literacy. Start US, prove it, then expand.

---

## Core Features

### Feature 1: AI Stock Research
- Deep analysis on any ticker with valuation range (bear/fair/bull), investment thesis, bear case stress test, sentiment analysis, and metrics to watch
- Sample NVDA analysis pre-loaded for first-time users (static sample with banner: "Sample analysis — search any ticker above to run your own")
- Trending tickers for quick access (NVDA, TSLA, PLTR, SMCI, ARM)
- Actions: Add to Watchlist, Copy, PDF export, Full Report, Refresh
- Custom bear case scenario input ("What if their CEO resigns?")
- Tabs: Investment Thesis, Bear Case, Financials
- Sentiment Analysis: News, Filings, Insider, Analyst scores → Composite score out of 100
- Metrics to Watch: key indicators with pass/fail thresholds
- **Status:** Live. Sample analysis functional. Custom analyses require API key in Settings.

### Feature 2: Live Portfolio
- Real-time positions with company logos, share count, current price, today's change, 1-week sparkline chart
- Summary cards: Total Value, Cost Basis, Total Return (% and $), Position Count, Sector Count
- Sector Allocation horizontal bar chart (9 sectors represented)
- Per-stock columns: Fair Value (with upside %), Rating (out of 10), Sentiment score
- Inline action buttons per stock: Research (opens AI Research), Upgrade (opens Position Review)
- Stocks without cached metrics show "Analyze" button to generate them
- Filter and Export buttons in header
- **Status:** Fully live with Robinhood connection. 28 positions loaded, real-time prices, P&L per holding.

### Feature 3: Risk Center
- **Risk Score:** Composite score out of 100 with severity label (e.g., "61 — Moderate-High")
- **Daily VaR (95%):** Maximum expected daily loss in dollars and percentage
- **Annualized Volatility:** Portfolio-level volatility with normal range indicator
- **Max Drawdown:** Worst peak-to-trough decline in dollars and percentage
- **Concentration Risk (3-panel):**
  - Sector breakdown with HHI index (3499 = Concentrated)
  - Market Cap breakdown with HHI index (5586 = Concentrated)
  - Geography breakdown with HHI index (5357 = Moderate)
  - Each panel shows dollar amounts, percentages, and HIGH/Moderate labels
- **Drawdown History:** 90-day chart showing portfolio drawdown over time
- **Sector Concentration:** Detailed sector weights with HHI and "Top 5 Sectors = X%" summary
- **Correlation Alerts:** Pairwise Pearson + Spearman correlations above 0.65 threshold (20 pairs found)
- **Stress Tests (8 predefined scenarios):** 2008 Financial Crisis (-45%), COVID Crash (-24.8%), Rate Hike +200bps (-19.1%), Tech Selloff (-26.9%), Stagflation (-14.6%), AI Bubble Burst (-35.7%), Trade War (-19.6%), Sovereign Debt Crisis (-17.6%) — all show dollar impact
- **Factor Exposure:** Market Beta (68%), Growth/Tech (82%), Size/Small Cap (16%), Momentum (37%), Volatility (38%), Rate Sensitivity (65%) — via OLS regression vs SPY + sector-derived
- **CTA:** "Reduce your risk with 3 simple changes" → links to Diversify page
- **Status:** Fully live. All metrics computed from real portfolio data.

### Feature 4: Diversify (Behavioral Risk Profiling & Diversification)
- **Behavioral Risk Score:** 52/100 with label ("Balanced") and plain-English description
- **Score Drivers (weighted bars):** Composition 40% (53), Concentration 30% (49), Volatility 20% (34), Correlation 10% (100) — each expandable
- **Key Findings (4 insight cards):**
  - "82% of your money is in tech. That's a big bet on one sector."
  - "Portfolio beta of 1.38x the market. When the market drops 10%, you'd drop ~14%."
  - "20 highly correlated stock pairs. Your stocks move together."
  - "Good sector spread — 5 sectors represented."
- **AI Risk Analysis:** On-demand button to generate personalized narrative interpretation (requires LLM call)
- **Before vs After comparison table:**
  - "$807.00 protected in a 2022-style crash with these 3 changes"
  - Rows: 2022 Rate Shock, COVID 2020, 2008 Financial Crisis, Max Drawdown, Health Score (48→78), Sectors (5→8), Effective Positions (10.4→13)
- **Suggested Additions (3 ETFs, 10% allocation each):**
  - XLE (Energy) — Best Crash Savings +$544, Drawdown Reduction +8.8pp
  - XLV (Healthcare) — Best Crash Savings +$166, Drawdown Reduction +2.7pp
  - BND (Bonds) — Best Crash Savings +$291, Drawdown Reduction +1.6pp
  - Each with plain-English reasoning and expandable details
- **Legal disclaimer** at bottom
- **Status:** Fully live. All computations from portfolio data — no LLM call required for base analysis.

### Feature 5: Portfolio Stress Test (Event-Based Scenarios)
- **30 pre-built scenarios** across 5 categories:
  - Historical (8): 2008 Financial Crisis, COVID, Dot-com, 2022 Rate Hike, Black Monday, SVB, EU Debt, Oil Crash
  - Macro (7): Rate Hike +200bps, Mild Recession, Stagflation, Dollar Collapse, Inflation Surge, Credit Spread, Debt Downgrade
  - Geopolitical (6): China-Taiwan Conflict, US-China Trade War, Middle East Oil Shock, Russia-NATO, Iran/Hormuz, Contested Election
  - Sector (6): AI Bubble Burst, EV Bubble, Crypto Contagion, Bank Run, Big Tech Crackdown, Semiconductor Shortage
  - Black Swan (3): Novel Pandemic, Global Internet Outage, Catastrophic Climate Event
- Each scenario card shows: severity (1-10), S&P impact, description, estimated duration
- **Scenario detail view:**
  - Portfolio Today → After Scenario → Estimated Impact → Percentage
  - Recovery time estimate and correlation spike adjustment
  - Impact Cascade: horizontal bar chart showing dollar loss per stock, sorted by magnitude
  - Per-Stock Impact table: every holding with current value, estimated %, dollar loss, portfolio weight
  - "Protect My Portfolio" CTA → links to Diversify page
- **Search and filter** by category or keyword
- **Custom scenario input:** "Or describe your own scenario..."
- **Status:** Fully live. Sector factor model with beta, size, and quality adjustments. 100% holding coverage.

### Feature 6: Position Review (Upgrade / Holding Review)
- Select any portfolio holding from dropdown (shows ticker, company name, shares, cost basis)
- "Review Position" button triggers AI-powered analysis with:
  - Current position performance evaluation
  - Same-sector alternative suggestions
  - ETF alternative for diversified exposure
  - Structured comparison (not just "sell X buy Y")
- **Status:** Live. UI functional with stock selector. Requires LLM call for analysis.

### Feature 7: Conversational Portfolio Advisor
- Chat interface with 6 suggested prompts:
  - "How is my portfolio positioned right now?"
  - "Which stocks should I consider trimming?"
  - "Am I too concentrated in any sector?"
  - "What are my biggest risk exposures?"
  - "Any tax-loss harvesting opportunities?"
  - "What stocks should I add more of?"
- File upload support (PDF, TXT, MD, CSV) for research documents
- Shift+Enter for new line
- Powered by Claude AI
- **Status:** Live. Chat UI functional. Uses portfolio data for personalized answers.

### Feature 8: Watchlist
- Track stocks analyzed via AI Research
- Add from research results with one click
- **Status:** Live. Empty state guides users to AI Research.

### Feature 9: Dashboard (Home)
- "Good evening" greeting with LIVE badge
- **Portfolio Value chart** with time range toggles (1D, 1W, 1M, 3M, ALL)
- **Summary cards:** Buying Power ($67.53), Total Return (-2.2% / -$136.88), Risk Score (61/100 Mod-High)
- **Positions list** with company logos, shares, price, daily change, sparkline charts, P&L
- **Right sidebar:**
  - Watchlist panel
  - News Feed with ticker tags, URGENT badges, and summaries (SOFI, MSFT, SNOW, CRM)
- **Quick analyze** search bar in top-right corner
- **Status:** Fully live with connected portfolio.

---

## Settings
- **Account:** Username display, sign out
- **AI API Key:** Anthropic API key management with SAVED indicator, model selector (Claude Sonnet 4.5, Sonnet 4.6, Opus 4.6), key visibility toggle, remove button
- **Brokerage:** Robinhood connection form (email, password, MFA code), "Remember credentials" option, "More Brokerages coming soon" (Interactive Brokers, Schwab, Fidelity)
- **Data & Privacy:** Browser cache count, "Clear Cache" and "Clear All Data" buttons, transparency section ("Your data stays in your browser" — no analytics, no tracking, credentials direct to Robinhood)

---

## Sidebar Navigation (9 items)
Dashboard, AI Research, Watchlist, Portfolio, Risk Center, Diversify, Stress Test, Upgrade, Advisor

---

## What Aegis is NOT (v1)
- Not a trading platform (no buy/sell execution)
- Not a robo-advisor (no auto-rebalancing)
- Not financial advice (legally — it's "educational insights")
- Not targeting sophisticated traders or institutions

## Differentiator
Every competitor gives you data. Aegis gives you **judgment** — in plain language, personalized to your actual portfolio. Full advisory loop: "Here's your risk → here's what could go wrong → here's what to do about it." No consumer app does this today.

---

## Architecture: Stock Metrics Cache

Shared intelligence cache with per-metric TTLs so any user searching a ticker gets instant results from pre-computed data.

- **Price:** 1 min TTL (external market API)
- **News/Sentiment:** 24 hour TTL
- **Earnings:** 90 day TTL (quarterly cycle)
- **Fair Value / Rating / Thesis / Risks / Bear Case:** 7 day TTL (AI-generated)

Pattern: stale-while-revalidate — serve cached data instantly, refresh stale metrics in background. Progressive loading UI for cache misses (new tickers).

Currently used in: Portfolio table (Fair Value, Rating, Sentiment columns), Dashboard positions.

---

## Pricing Model
- **Free tier:** 3 AI analyses/day, basic portfolio view
- **Pro ($8/mo):** Unlimited analyses, full risk center, advisor, position review, event scenarios

---

## Known Issues (as of Mar 24, 2026)
- [ ] API key visible in plaintext in Settings (security concern for investor demos)
- [ ] No working demo without API key — sample analysis is static, "Analyze" button requires key
- [ ] Nav item "Upgrade" is confusing — the page is "Position Review" but sidebar says "Upgrade"
- [ ] 9 sidebar items is borderline too many — consider grouping Risk Center + Diversify + Stress Test under a "Risk" parent
- [ ] Stocks without cached metrics show "Analyze" button in Fair Value/Rating/Sentiment columns — inconsistent with cached stocks
- [ ] Custom stress test scenario ("Or describe your own scenario...") UI exists but functionality unclear
- [ ] News Feed in dashboard shows URGENT badges — unclear what triggers URGENT vs normal

## Open Questions
- [ ] Regulatory: Do we need SEC/FINRA registration for "educational insights"? Where's the line?
- [ ] Robinhood API: Official API vs Plaid for portfolio access? Rate limits?
- [ ] Legal entity: Structure given visa constraints — need founder-friendly immigration lawyer input
- [ ] Server-side AI proxy: Move API key off client before any investor demo
- [ ] Pre-cache trending tickers (NVDA, AAPL, TSLA, PLTR, SMCI) for instant demo experience
- [ ] Position Review: What happens after AI generates the review? Can user act on it?
