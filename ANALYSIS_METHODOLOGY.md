# Aegis — Analysis Methodology & Algorithms

Every metric, score, and prediction in Aegis. What we compute, how we compute it, and where to improve.

---

## Data Sources

| Source | What We Get | Cache TTL | Library |
|--------|-------------|-----------|---------|
| Robinhood API | Live positions, shares, cost basis, 90-day daily prices | 30 seconds | `robin_stocks` |
| yfinance | Sector, market cap, P/E, beta, earnings, margins, analyst consensus, news | 24 hours | `yfinance` |
| Anthropic Claude | Thesis, fair value, sentiment, bear case, scoring, narrative analysis | Per-request | `anthropic` SDK |

---

## 1. Risk Score (0-100)

**What users see:** "61 — Moderate-High" on the Risk Center dashboard.

**Formula:** Weighted composite of 5 sub-scores, each normalized to 0-100.

```
risk_score = (
    VaR_score      × 0.25    # Value at Risk
  + Drawdown_score × 0.20    # Max Drawdown
  + Conc_score     × 0.20    # Concentration (HHI)
  + Vol_score      × 0.20    # Annualized Volatility
  + Corr_score     × 0.15    # Correlation Alerts
)
```

**Sub-score normalization:**

| Sub-score | Formula | 0 = | 100 = |
|-----------|---------|-----|-------|
| VaR | `abs(daily_var_95) × 100 / 5 × 100` | 0% daily VaR | 5% daily VaR |
| Drawdown | `abs(max_drawdown) × 100 / 30 × 100` | 0% drawdown | 30% drawdown |
| Concentration | `HHI × 100 / 0.3 × 100` | HHI = 0 | HHI = 0.30 |
| Volatility | `annualized_vol / 0.4 × 100` | 0% vol | 40% vol |
| Correlation | `num_alerts × 15` | 0 correlated pairs | 7+ pairs |

**Where to improve:**
- Weights are static — consider making them adaptive based on market regime (risk-off markets should weight VaR higher)
- No tail-risk adjustment — a portfolio with fat-tailed returns should score higher than one with normal distribution
- No time-decay — recent drawdowns should matter more than 90-day-old ones

---

## 2. Value at Risk (VaR) — 95% Confidence

**What users see:** "Daily VaR (95%): -2.08% — Max daily loss: $128.99"

**Method:** Historical simulation (non-parametric).

```python
daily_var_95 = np.percentile(portfolio_returns, 5)
# → 5th percentile of actual daily portfolio returns over 90 days
```

**Conditional VaR (Expected Shortfall):**
```python
tail_returns = returns[returns <= var_threshold]
daily_cvar = mean(tail_returns)
monthly_cvar = daily_cvar × √21    # Scale to monthly
```

**Data:** 90 days of daily close prices from Robinhood, top 25 positions by equity.

**Where to improve:**
- 90 days is short — misses tail events like COVID, 2022 rate shock. Consider blending with parametric VaR using longer-horizon volatility estimates
- No GARCH or EWMA for volatility clustering — recent vol should weigh more
- √21 scaling for monthly assumes i.i.d. returns — not true in crisis periods
- Could add Monte Carlo VaR with correlated draws for better tail estimation

---

## 3. Volatility (Annualized)

**What users see:** "Annualized Volatility: 19.3% — Within normal range"

**Formula:**
```
daily_vol = std(daily_portfolio_returns)
annualized_vol = daily_vol × √252
```

**Where to improve:**
- Simple standard deviation treats upside and downside equally — consider downside deviation (Sortino-style) since investors care about losses, not gains
- No regime detection — vol changes character in bull vs bear markets
- Could add realized vol vs implied vol comparison (if options data available)

---

## 4. Max Drawdown

**What users see:** "Max Drawdown: -9.6% — Worst peak-to-trough: $597.82"

**Formula:**
```python
portfolio_values = price_matrix @ weights
running_max = np.maximum.accumulate(portfolio_values)
drawdowns = (portfolio_values - running_max) / running_max
max_drawdown = min(drawdowns)
```

**90-day drawdown series** rendered as a line chart on Risk Center.

**Where to improve:**
- Only captures the worst point — could also show recovery time, average drawdown, and drawdown duration
- No comparison to benchmark (SPY) drawdown in same period
- Could estimate expected max drawdown using Calmar ratio: `annualized_return / max_drawdown`

---

## 5. Concentration Risk — HHI (Herfindahl-Hirschman Index)

**What users see:** Three panels — Sector (HHI 3499), Market Cap (HHI 5586), Geography (HHI 5357).

**Formula:**
```
HHI = Σ (weight_i / 100)²
```
where `weight_i` is the percentage allocation to sector/cap tier/geography.

**Interpretation:**
| HHI | Label |
|-----|-------|
| < 0.15 | Low concentration (diversified) |
| 0.15 - 0.25 | Moderate concentration |
| > 0.25 | High concentration |

**3-Dimensional Composite Rating:**
```
composite = sector_rating × 0.45 + mcap_rating × 0.30 + geo_rating × 0.25
```
Where each rating maps to: green=0, yellow=50, red=100.

**Where to improve:**
- HHI treats all sectors as equally different — NVDA in "Electronic Technology" and MSFT in "Technology Services" are treated as diversified, but they're both tech
- Could use GICS sector hierarchy (11 sectors → 24 industry groups → 69 industries) for finer granularity
- Weight by risk contribution (volatility-weighted) not just dollar amount — a 10% position in a volatile stock contributes more risk than 10% in a stable one

---

## 6. Correlation Alerts — Hybrid Model

**What users see:** "SNOW — ORCL: 0.84" with threshold 0.65 (Pearson + Spearman).

**Method:** Two-pass hybrid correlation.

**Pass 1: Full-period Pearson (90 days)**
```python
pearson_corr = np.corrcoef(returns.T)
```

**Pass 2: Rolling 30-day Spearman Rank**
```python
for each 30-day window (step=3 days):
    spearman_rho = scipy.stats.spearmanr(window_i, window_j)
    spearman_max[i,j] = max(spearman_max[i,j], rho)
```

**Combined:**
```python
combined = max(pearson_val, spearman_val)
if combined >= 0.65:  # Alert threshold
    flag_pair()
```

**Why hybrid:** Pearson catches linear relationships over full period. Rolling Spearman catches non-linear tail dependencies that spike during stress periods but average out over 90 days. Taking the max of both catches the strongest signal.

**Where to improve:**
- No conditional correlation (correlation during down-markets vs up-markets) — assets that seem uncorrelated in calm markets often spike to 0.9+ correlation during crashes
- Could add Dynamic Conditional Correlation (DCC-GARCH) model for time-varying correlation estimates
- Rolling window step=3 is an efficiency hack — step=1 would be more accurate for tail detection
- No visualization of correlation over time (just the max) — a correlation heatmap or time-series would help users understand the structure

---

## 7. Factor Exposure

**What users see:** Market Beta 68%, Growth/Tech 82%, Size 16%, Momentum 37%, Volatility 38%, Rate Sensitivity 65%.

### Market Beta (OLS Regression)
```python
slope, _, r_val, _, _ = linregress(SPY_returns, portfolio_returns)
market_beta = slope
beta_exposure = beta × 50  # beta=1.0→50%, beta=2.0→100%
```

### Other Factors (Heuristic)
```
Growth/Tech = tech_sector_weight%
Size = 30 - (num_positions × 0.5)
Momentum = 50 + (5d_avg_return - 30d_avg_return) × 2000
Volatility = annualized_vol × 200
Rate Sensitivity = tech_weight × 0.8
```

**Where to improve (HIGHEST PRIORITY for industry credibility):**
- Only Market Beta uses actual regression. All other factors are sector-weight heuristics, not actual factor loadings.
- **Should implement:** Fama-French 3-factor (Market, SMB, HML) or 5-factor model via regression against factor returns (available from Ken French's data library)
- Size factor should use actual market cap of holdings, not just "30 - position_count"
- Momentum should use standard 12-1 month return (skip most recent month to avoid reversal)
- Rate sensitivity should use actual duration proxy (regress portfolio against 10Y yield changes)
- Missing factors: Quality (ROE, low accruals), Profitability, Investment factor

---

## 8. Stress Tests — Sector Factor Model

**What users see:** 30 scenarios across 5 categories. E.g., "AI Bubble Burst: -$2,322 (-37.4%)".

### Per-Stock Impact Formula
```
impact = base_sector_impact
       × beta_multiplier        # dampened: 0.5 + 0.5 × clamp(beta, 0.2, 3.0)
       × size_multiplier        # mega_cap=0.85, large=0.95, mid=1.05, small=1.20, micro=1.35
       × quality_multiplier     # 1.15 - (quality/100 × 0.30)
       × geo_multiplier         # 1.2 if in affected region
       + factor_adjustment      # capped to ±50% of base
```

If historical data available: `final = 50% model + 50% historical`.

### Correlation Adjustment (Portfolio-Level)
```python
normal_corr = min(0.95, 0.2 + HHI × 0.6)
stressed_corr = min(1.0, normal_corr × 1.5)
additional_impact = -(stressed_corr - normal_corr) × (severity/10) × 3.0
# Capped at -8% additional impact
```

### Scenario Database
8 scenarios with hand-coded sector impact maps in the backend. 30 scenarios total on frontend (22 use the same engine with frontend-defined parameters).

**Where to improve:**
- Hand-coded sector impacts are educated guesses, not calibrated to historical data — should backtest against actual 2008, 2020, 2022 outcomes
- No Monte Carlo — deterministic model always gives same output. Adding randomness with confidence intervals (e.g., "30-45% drop" instead of "37.4%") would be more honest
- Could calibrate using actual sector ETF drawdowns in each historical scenario (SPY, XLK, XLF, XLE actual max drawdowns)
- Recovery time estimates are static labels — could estimate based on historical recovery patterns
- Missing: second-order effects (e.g., AI bubble burst → reduced enterprise spending → SaaS companies hit harder than pure-play AI)

---

## 9. Behavioral Risk Score (0-100)

**What users see:** "52/100 — Balanced" on Diversify page, with 4-factor breakdown.

**Formula:**
```
behavioral_score = (
    Composition   × 0.40    # What you own
  + Concentration × 0.30    # How concentrated
  + Volatility    × 0.20    # How bumpy the ride
  + Correlation   × 0.10    # How correlated
)
```

**Category A — Composition (40% weight):**
```
beta_score     = linear(market_beta, 0.7→0, 2.0→100)     × 0.35
holdings_score = linear(15 - n_holdings, 0→0, 12→100)     × 0.30
tech_score     = linear(tech_weight, 15→0, 80→100)        × 0.35
```

**Category B — Concentration (30% weight):**
```
top1_score = linear(top_position%, 10→0, 50→100)          × 0.35
hhi_score  = linear(sector_HHI, 0.08→0, 0.40→100)        × 0.35
top3_score = linear(top3_positions%, 25→0, 80→100)        × 0.30
```

**Category C — Volatility (20% weight):**
```
vol_score    = linear(annualized_vol, 12%→0, 40%→100)     × 0.40
dd_score     = linear(max_drawdown, 8%→0, 40%→100)        × 0.35
stress_score = linear(worst_stress_impact, 12%→0, 50%→100) × 0.25
```

**Category D — Correlation (10% weight):**
```
corr_score = linear(n_corr_alerts, 0→0, 8→100)
```

**Linear scoring function:**
```python
def _score_linear(value, low, high):
    return clamp((value - low) / (high - low) × 100, 0, 100)
```

**Persona mapping:**
| Score | Persona | Description |
|-------|---------|-------------|
| 0-20 | Guardian | Capital preservation |
| 21-40 | Steady | Conservative growth |
| 41-60 | Balanced | Mix of growth and stability |
| 61-80 | Growth Seeker | Growth-oriented |
| 81-100 | Thrill Rider | Aggressive/speculative |

**Where to improve:**
- Persona is catchy but could be backed by actual behavioral finance research (loss aversion, disposition effect, herding indicators)
- Thresholds (0.7 beta = 0, 2.0 = 100) are somewhat arbitrary — should calibrate against a distribution of real retail portfolios
- Missing: turnover (frequent traders vs buy-and-hold), position sizing patterns, recency bias (chasing recent winners)

---

## 10. Diversification Suggestions — Gap-Fill Algorithm

**What users see:** "XLE (Energy) — +$544 crash savings, +8.8pp drawdown reduction"

**Algorithm: Relevance scoring for ETF candidates.**

```python
for each ETF_candidate:
    relevance = 0

    # 1. Missing sector bonus
    if category == "Healthcare" and not has_healthcare: relevance += 40
    if category == "Energy" and not has_energy:         relevance += 35
    if category == "Bonds" and not has_bonds:           relevance += 30

    # 2. Low tech correlation bonus
    relevance += (1.0 - tech_correlation) × 20

    # 3. 2022 crash resilience bonus
    if return_2022 > 0:    relevance += 30     # Positive during 2022 crash
    elif return_2022 > -5: relevance += 15     # Mild loss

    # 4. Crash impact improvement
    for each crash_scenario:
        current_impact = weighted_sector_impact(current_portfolio)
        new_impact = current_impact × 0.90 + etf_return × 0.10    # 10% allocation
        savings = portfolio_value × (abs(current) - abs(new)) / 100

    return top_3_by_relevance
```

**Before/After Simulation:**
```python
# Effective positions (inverse HHI)
position_hhi = Σ(equity_i / total_equity)²
effective_positions = 1 / position_hhi

# Scale existing positions down by suggestion allocation
scale_factor = (100 - total_suggestion_pct) / 100
new_hhi = Σ(old_weight_i × scale_factor)² + Σ(suggestion_weight_j)²
```

**Crash scenarios used:** 2022 Rate Shock, COVID 2020, 2008 Financial Crisis.

**Where to improve:**
- ETF candidate list is hardcoded — should expand dynamically based on what sectors/factors are actually missing
- Assumes 10% allocation per suggestion — should optimize allocation weights (mean-variance optimization or risk parity)
- No consideration of tax implications (adding bonds in taxable vs. tax-advantaged)
- Could use actual cross-asset correlations instead of sector-based proxies
- Before/after projections are linear — should model the full covariance matrix with new positions included

---

## 11. Stock Scoring (Weekly Validity Score)

**What users see:** "9.5/10" rating and "BUY" verdict in the Portfolio table.

**Method:** LLM-generated (Claude) across 4 dimensions.

**Composite formula:**
```
validity_score = (
    fundamental_score × 0.30
  + valuation_score   × 0.25
  + thesis_score      × 0.30
  + momentum_score    × 0.15
)
```

**Each dimension (0-100):**

| Dimension | Inputs | 80+ = | <40 = |
|-----------|--------|-------|-------|
| Fundamental | Margins, revenue growth, cash flow, balance sheet | Excellent quality | Deteriorating |
| Valuation | P/E vs 5yr avg, PEG, EV/EBITDA, analyst targets | Attractive | Overvalued |
| Thesis | Growth drivers intact? Competitive position? | Strengthening | Breaking |
| Momentum | Price vs 50/200 MA, analyst revisions, insider activity | Strong positive | Negative |

**Verdict mapping:**
| Score | Verdict |
|-------|---------|
| ≥75 | Strong Buy |
| 55-74 | Hold |
| 40-54 | Watch |
| 25-39 | Trim |
| <25 | Sell |

**Persisted weekly** with `week_label` (ISO format: "2026-W12"). Prior week's score included in prompt for week-over-week comparison.

**Where to improve:**
- Entirely LLM-generated — no quantitative model backing the scores. Could use a hybrid: quantitative base score + LLM qualitative adjustment
- "9.5/10" display is confusing — it's derived from 0-100 internal score but displayed as /10. Standardize.
- No backtesting — we don't know if stocks scored 80+ actually outperformed
- Could add a "model vs actual" tracker: "Last month we rated NVDA 9/10, it returned +12%. Accuracy: tracking."
- Should weight recent quarters more heavily for fundamental score

---

## 12. Replacement Recommendations — Multi-Factor Composite

**What users see:** Position Review with alternative stock suggestions.

**5-Stage Pipeline:**
1. Identify same-sector/industry peers
2. Fetch fundamentals for each peer via yfinance
3. Compute factor scores
4. Apply multi-factor composite ranking
5. Generate LLM comparison narrative

**Composite scoring:**
```
composite = (
    momentum × 0.25     # 12-1mo return (40%), 6-1mo return (30%), revision trend (30%)
  + quality  × 0.25     # ROE (30%), gross margin (25%), FCF yield (25%), current ratio (20%)
  + growth   × 0.20     # Revenue YoY (40%), EPS growth (30%), forward EPS growth (30%)
  + value    × 0.15     # Forward P/E (35%), EV/EBITDA (35%), PEG (30%) — INVERTED
  + risk     × 0.10     # Beta (40%), volatility (30%), max drawdown (30%) — INVERTED
  + analyst  × 0.05     # Consensus rating (50%), price target upside (50%)
)
```

**Guardrails:**
- Reject if forward P/E > 1.5× sector median
- Reject if PEG > 2.0
- If too aggressive (fewer than 3 candidates remain), relax constraints

**Where to improve:**
- No portfolio-level consideration — suggests best individual stock, not the one that improves portfolio characteristics
- Should factor in correlation with existing holdings (a great stock that correlates 0.95 with your existing positions adds no diversification)
- No tax-loss harvesting optimization (if the position is at a loss, suggest a wash-sale-safe alternative)
- Could add "conviction level" from institutional holders (13F filing analysis)

---

## 13. Fair Value Estimation (Bear / Fair / Bull)

**What users see:** Valuation range bar — "Bear $95 / Fair $155 / Bull $210" for NVDA.

**Method:** Entirely LLM-generated (Claude).

**Data injected into prompt:**
- Current stock price (real-time from yfinance)
- Market cap, P/E, beta, dividend yield, 52-week range
- Last 2 quarters of earnings (revenue, net income, EPS)
- Recent news headlines (last 6)

**Claude is instructed to use:** DCF with explicit discount rate and growth assumptions, comparable company analysis, sum-of-parts if applicable.

**Where to improve (CRITICAL):**
- No quantitative model at all — entirely Claude's judgment. Should build a quantitative DCF engine as the base, then let Claude adjust for qualitative factors
- No confidence intervals — "$155 fair value" implies false precision. Should show "$140-170 range with 60% confidence"
- No backtesting of prior fair value estimates vs actual price movement
- Could implement: Residual Income Model, reverse DCF (what growth rate is priced in?), or earnings-yield vs bond-yield comparison
- Should track fair value drift over time per ticker (is it improving or deteriorating?)

---

## 14. Sentiment Analysis

**What users see:** News 72, Filings 68, Insider 45, Analyst 82, Composite 67/100.

**Method:** LLM-generated (Claude).

**4 Dimensions:**
| Dimension | What Claude evaluates | Weight |
|-----------|----------------------|--------|
| News | Tone of recent headlines + positive/negative split | 25% |
| Filings | SEC filing language, risk factor changes, guidance tone | 30% |
| Insider | Insider buying/selling patterns, institutional flow | 20% |
| Analyst | Rating distribution, price target changes, revision trend | 25% |

**Composite:**
```
composite = news × 0.25 + filings × 0.30 + insider × 0.20 + analyst × 0.25
```

**Scale:** 0-30 = Very Bearish, 30-45 = Bearish, 45-55 = Neutral, 55-70 = Bullish, 70-100 = Very Bullish.

**Where to improve:**
- No actual NLP sentiment analysis on filings text — Claude estimates from its training data, not real-time SEC Edgar parsing
- No actual insider transaction data (Form 4) — should pull from SEC EDGAR API or OpenInsider
- Analyst data from yfinance is limited — could integrate TipRanks, Refinitiv, or S&P Capital IQ for richer consensus data
- Should add social sentiment (Reddit/StockTwits volume and tone) as a contrarian indicator
- No time-series of sentiment — a score of 67 is meaningless without knowing if it was 80 last week (declining) or 50 (improving)

---

## 15. LLM Prompts — System Templates

All prompts in `/apps/aegis/backend/app/prompts/__init__.py`.

| Prompt | Purpose | Key Instructions |
|--------|---------|-----------------|
| `STOCK_ANALYZER_SYSTEM` | Full equity research report | DCF valuation, bear/base/bull targets, thesis, risks ranked by probability × severity |
| `BEAR_CASE_SYSTEM` | Adversarial stress test of bull thesis | Must include `estimated_impact_pct`, `stressed_price`, `scenario_name` |
| `THESIS_GENERATOR_SYSTEM` | Monitorable investment thesis | Every claim maps to a measurable metric with threshold |
| `DAILY_BRIEF_SYSTEM` | Portfolio deep analysis | Per-stock thesis evaluation, actionable recommendations ranked by urgency |
| `SENTIMENT_SYSTEM` | Market sentiment scoring | 4-dimension scoring with composite |
| `ADVISOR_SYSTEM` | Portfolio Q&A chatbot | Real-time portfolio context injected, data-driven advice |
| `FULL_REPORT_SYSTEM` | Publishable investment report | DCF with explicit assumptions, executive summary, verdict with confidence |
| `RISK_PROFILE_NARRATIVE_SYSTEM` | Personalized risk narrative | 4-phase: Mirror → Reveal → Context → Path. 200-350 words, 6-8th grade reading level |
| `STOCK_SCORER_SYSTEM` | Weekly validity scoring | 4-dimension scoring, week-over-week comparison, verdict mapping |

---

## Priority Improvements for Industry Leadership

### Tier 1 — Credibility (do these first)
1. **Quantitative fair value model** — Build a DCF/multiples engine. Use Claude to adjust, not generate from scratch. Backtest estimates vs actual price.
2. **Factor model upgrade** — Replace heuristic factor scores with Fama-French regression. Use Ken French's factor return data.
3. **Calibrate stress tests** — Backtest sector impact maps against actual 2008/2020/2022 sector ETF drawdowns. Show model accuracy.

### Tier 2 — Differentiation (competitive edge)
4. **Conditional correlation** — Show how portfolio correlation changes in crisis vs calm markets. This is institutional-grade insight most retail tools don't provide.
5. **Real-time sentiment pipeline** — Parse SEC EDGAR filings, pull Form 4 insider transactions, scrape analyst revision data. Replace LLM estimates with real data + LLM interpretation.
6. **Portfolio optimization engine** — Mean-variance optimization or risk parity for diversification suggestions instead of gap-fill heuristic.

### Tier 3 — Polish (nice to have)
7. **Backtest everything** — Track every prediction/score vs outcomes. Show users "our accuracy last quarter."
8. **GARCH volatility** — Time-varying volatility model for better VaR estimates.
9. **Monte Carlo stress tests** — Add confidence intervals to stress test results instead of point estimates.
10. **Tax-aware recommendations** — Consider wash sale rules, long-term vs short-term capital gains in replacement suggestions.

---

## Architecture Note

**All computation happens on the backend** (Python/FastAPI). The frontend (React) is display-only — it calls API endpoints and renders the results. No math in the browser.

Backend location: `/Users/mac/Projects/kondareddy-platform/apps/aegis/backend/app/services/`
- `risk.py` — VaR, volatility, drawdown, HHI, correlations, factor exposure, stress tests
- `diversification.py` — Behavioral risk score, ETF suggestions, before/after simulation
- `stock_scorer.py` — Weekly validity scoring via Claude
- `stress_test/impact_calculator.py` — Per-stock stress test engine
- `replacement/scoring.py` — Multi-factor replacement ranking
- `claude.py` — All Claude API calls (analysis, sentiment, thesis, bear case)
- `prompts/__init__.py` — All system prompt templates
