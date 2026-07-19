# Polytrade — Thematic Auto-Managed Baskets

> **Living design doc.** Plan for the Polytrade concept: AI-curated, thesis-driven thematic
> baskets that users fund with one tap and that the harness invests, monitors, rebalances and
> auto-exits on their behalf.
> **Status:** v0.1 (plan — not yet built) · Depends on the existing agentic-trading harness.

---

## 1. The concept

**Polytrade** turns emouva's per-name research engine into **themes** — curated, narrative-driven
baskets a user can back with capital in one tap, and that trade themselves.

A *theme* is a legible bet with a story: *"HBM memory supercycle"*, *"Software stocks recovering
off 52-week lows"*, *"Physical-AI multibaggers"*, *"Chip winners — TSMC 50% growth through 2029"*.
Each theme carries a **living thesis** (narrative + machine-checkable falsifiers + red-team) and a
**basket** of the best vetted names with **target weights**.

The loop:

1. We **research + originate** themes daily — a compelling narrative and the best stocks for it.
2. A user **allocates capital** to a theme from their available cash (a cash sweep).
3. We **auto-invest** that capital across the basket at target weights.
4. We **monitor** the thesis (daily refresh + news + earnings) and **rebalance** as it evolves.
5. When the thesis **weakens** we trim; when it **breaks** we **auto-exit every user** and sweep
   proceeds back to cash — turning the sell into a *story*, not a churn.

It's a self-driving thematic ETF that talks to you. Polymarket makes a *narrative + a live number*
addictive; Polytrade does the same — but the number is a **conviction score that moves on real
earnings/news**, and an AI portfolio manager is *doing something for you between visits*.

---

## 2. Build on what already exists (compose, don't rebuild)

Polytrade is a new **Themes** layer over the primitives we already run:

| Existing primitive | Reused for Polytrade |
|---|---|
| **Central Opportunity Pool** (`opportunities`) — vetted businesses w/ thesis, falsifiers, red-team, stats, category | Constituent **candidate universe**. A stock can only enter a theme if it's already vetted + tradeable. |
| **Living Thesis** (`theses`) — falsifiers, 4-lens red-team, `evaluate()`, grace period | The **theme-level thesis**: narrative + theme falsifiers + red-team, evaluated daily. |
| **Tick engine** (`engine.run_tick`) + **SafetyGate** + **broker** (`broker.py`) | Per-account order execution: cash-floor, $250/order cap, fractional handling, `EQUITY_SUITABILITY` acks, ledger. |
| **Earnings re-thesis** (`earnings.py`) + **news_check** / **premarket_refresh** (`central.py`) | Theme monitoring cadence: daily refresh, 8am news flags, earnings-triggered re-thesis. |
| **Falling-knife guard / catastrophic review** (`trend.py`) | Applies to constituents inside a basket. |
| **LLM tool-loop + web_search** (`research._llm_toolloop`, `claude._call_claude`) | Theme origination + weekly deep re-validation. |
| **Mandate + human-approval threshold + LegalDocs disclaimers** | Opt-in, per-theme pause, total-loss disclosure. |

Net new surface is a **Themes domain** (4 tables + a reconciler) — not a parallel trading system.

---

## 3. Data model (new tables)

```text
themes                         -- central, shared repo (global; one row per theme)
  id, slug, title, tags[]
  narrative (thesis_text), hero_stat            -- "TSMC 50% growth through 2029"
  status         enum: draft | live | weakening | breaking | closed
  conviction     int 0..100                     -- the "price" users watch; moves daily
  health         enum: strong | watching | breaking
  falsifiers     jsonb  -- machine-checkable theme triggers (reuse Living-Thesis shape)
  red_team       jsonb  -- 4-lens: demand, supply/competition, valuation, catalyst/timing
  target_version int    -- bumped on every basket change (constituents or weights)
  perf_snapshot  jsonb  -- since-inception %, 30d %, drawdown
  created_by, created_at, updated_at, last_thesis_run_at

theme_constituents             -- the basket + weights (children of a theme; global)
  id, theme_id, symbol
  target_weight  float 0..1     -- weights within a theme sum to 1.0
  role           enum: anchor | satellite | speculative
  rationale      text
  opportunity_id -> opportunities.id            -- provenance: must be a vetted name
  status         enum: active | exited
  added_at, exited_at

theme_allocations              -- per-user capital committed to a theme
  id, user_id, account, theme_id
  committed_usd, invested_usd
  status         enum: pending | active | unwinding | closed
  applied_version int           -- last theme.target_version this allocation was reconciled to
  cost_basis, market_value, realized_pnl, unrealized_pnl
  created_at, closed_at, close_reason

theme_events                   -- audit + the live user feed (one stream, two consumers)
  id, theme_id, kind  enum: originated | thesis_update | rebalance | earnings
                            | news | weaken | break | exit
  summary, detail jsonb, created_at
```

Per-user positions still live in `account_positions`, but theme-driven lots get a nullable
**`theme_allocation_id`** so they're attributable and can be unwound as a unit **without touching
the discretionary agent book**. Same for `executions` (ledger tag).

**Target-versioning is the propagation contract.** The central `themes.target_version` is the
source of truth for *what the basket should be*; each `theme_allocation.applied_version` records
where that user is. The reconciler's only job is to move allocations from `applied_version` →
`target_version`. This makes cross-user propagation crash-safe, idempotent, and auditable (a "git
for the basket").

---

## 4. The five pipelines

### A. Theme thesis pipeline (origination + daily refresh)
- **Originate**: an admin (or an AI "theme scout") seeds a title + rough narrative. An LLM
  tool-loop (reuse `research._llm_toolloop` + `web_search`) validates the narrative, gathers
  evidence (capex cycles, ASP trends, unit economics), and drafts: `narrative`, a `hero_stat`,
  **3–7 machine-checkable theme falsifiers**, and a **4-lens red-team** (demand, supply/competition,
  valuation-of-basket, catalyst/timing). Survives ≥3 lenses → `status=live`.
- **Daily refresh** (rides `premarket_refresh`, 7am): light falsifier check → update `conviction`
  + `health`; append a `theme_events` row. A tripped falsifier → `weakening`/`breaking`.
- **Weekly deep re-thesis**: heavier `web_search` re-validation of the whole narrative.

### B. Constituent pick + weights (the investment ratios)
- Candidate universe = `opportunities` names that (i) fit the theme (LLM tags/matches),
  (ii) are Robinhood-tradeable (already verified), (iii) pass the stats gate.
- LLM picks **4–8** names with **roles + target weights summing to 1.0**:
  - **Anchor** — highest conviction, largest weight (e.g. TSMC, NVDA).
  - **Satellite** — mid weight.
  - **Speculative** — the multibagger sleeve, small + **capped**.
- Guardrails: **per-name cap** (≤35%), **speculative-sleeve cap** (≤20% total) so one moonshot
  can't dominate. Weights are conviction-weighted, re-derived on each refresh, but only applied
  when drift exceeds a **±5-pt band** (avoids daily churn). Every weight change bumps `target_version`.

### C. Monitoring cadence
- **Daily 7am** — theme thesis refresh (falsifier check + conviction).
- **Intraday news** (reuse 8am `news_check` + FMP news) — scan constituent + theme-keyword news;
  a *material* item flags the theme and can trigger an off-cycle re-thesis (materiality-gated, same
  pattern as `_material_stat_change` — not every tick).
- **Weekly** — deep narrative re-validation.
- Every update appends to `theme_events` → the live feed.

### D. Earnings triggers (highest signal — where theses break)
- Reuse `earnings.recent_reporters` (FMP earnings-calendar ∩ theme constituents). When a
  constituent reports, run a **theme-scoped re-thesis**: does the print confirm or threaten the
  narrative (HBM ASP guide, hyperscaler capex commentary, etc.)? → update conviction, re-weight,
  or trip a falsifier.

### E. Propagation (central → all accounts) + cross-user execution
A **theme reconciler** (new lightweight tick, or folded into the per-account tick) walks every
`active`/`pending`/`unwinding` allocation whose `applied_version < theme.target_version` and, per
allocation, computes the delta between the user's current theme holdings and the **target basket
scaled to their `committed_usd`**, then enqueues orders through the **existing broker + SafetyGate +
ledger** (tagged `theme_allocation_id`):
- **New allocation** → sweep `committed_usd` → buy basket at target weights (split to respect the
  $250/order cap; fractional handling already solved).
- **Rebalance** (weights/constituents changed) → buy/sell the deltas.
- **Weaken** → trim (scale the speculative sleeve down, or reduce the whole allocation by X%).
- **Break** → **full unwind across ALL users**, mark allocation `closed`, sweep proceeds to cash.

Idempotency key = `(allocation_id, target_version)` so a reconciler re-run never double-trades.
Cross-user execution is a **rate-limited fan-out** over allocations (respects Robinhood + the fenced
live account). Because it's version-driven, a crash mid-fan-out just resumes.

---

## 5. Capital flow

1. User taps **Add to theme**, picks an amount ≤ available cash.
2. We create a `theme_allocation` (`pending`), **reserve/sweep** the cash.
3. Reconciler invests at target weights → `active` (with a satisfying "Sweeping $500 → buying 6
   names…" animation).
4. Auto-exit returns proceeds to cash + fires a P&L card: *"HBM theme closed: +14.2% over 38 days —
   thesis broke on Micron's ASP guide-down."*

State machines — **theme**: `draft → live → (weakening ⇄ live) → breaking → closed`;
**allocation**: `pending → active → (unwinding) → closed`.

---

## 6. The addictive UI (the headline — must beat Polymarket)

**Why Polymarket is addictive:** a crisp narrative + a live probability + a chart + social proof
(volume, holders, comments) + one-tap action. **Polytrade keeps all of that and adds an AI that
works for you between visits and narrates its reasoning.**

**Theme cards are the feed** — a vertical, swipeable, mobile-first feed ("TikTok for investing
themes"). Each card:
- Bold **title** + one-line narrative + **`hero_stat`** ("TSMC: 50% growth through 2029").
- A live **conviction gauge (0–100, animated)** + a **health pill** (🟢 Strong / 🟡 Watching /
  🔴 Breaking) — the emotional hook Polymarket gets from its probability %.
- A **return curve since inception** with a big green/red %, Robinhood-style.
- **Constituent preview** — ticker chips with weight rings; tap to expand the full basket + per-name
  weight + rationale.
- **Social proof** — "$X invested · N investors · ▲ momentum this week" + a top-movers ticker.
- **One-tap "Add capital"** — amount slider bound to available cash + a delightful sweep animation.
- **Live AI reasoning feed** on the card back (the `theme_events` stream): *"Why we still hold"*,
  *"Trimmed NVDA 3% — valuation stretched vs thesis"*. **This is the retention loop** — you come
  back to see what your AI did and why.

**Conviction is the "price".** Where Polymarket shows a moving probability, Polytrade shows a moving
**conviction + health** driven by real falsifier telemetry — legible, and it visibly reacts to
earnings/news. Push notifications on moves: *"⚠️ HBM theme → Watching: Micron guided ASPs flat."*

**The "break" is an event, not a loss.** A broken thesis becomes a dramatic, shareable card —
*"🧩 Thesis broke — we exited everyone at +14%."* Turns the sell into a story (retention, not churn).

**Discovery & retention:**
- **Leaderboard** — themes ranked by momentum / conviction / 30-day return / # investors; filter by
  tag (AI, semis, software).
- **"New today" rail** — daily-originated themes = a reason to open the app every day.
- **My Themes** — live P&L, health, and the **next catalyst** ("Next: NVDA earnings in 6d").
- **Notifications** — daily "your themes today" digest, event pushes, "a new theme dropped".
- **Micro-interactions** — haptics on add, animated weight rings, count-up numbers, hold-streaks
  ("held through 3 earnings"), confetti on a winning exit.
- **Optional social** — per-theme comments/reactions (Polymarket's wall), "follow" a theme without
  investing, share cards.

**Why it beats Polymarket:** Polymarket is zero-sum binary betting with no ongoing management;
Polytrade is a self-driving basket with **real upside** that an AI actively manages and *explains
every day* — the same legible-narrative + live-number dopamine, plus a portfolio manager working on
your behalf and a daily stream of new themes and moving conviction. A stronger open-the-app loop
than a static probability that only resolves once.

---

## 7. Safety & compliance

- **Approval model = opt-in is consent (decision #4).** Funding a theme *is* the approval; all
  resulting buys/sells auto-execute regardless of size — no per-trade prompt. This is the smooth
  one-tap feel, but it moves the human-control surface off the individual trade, so the
  compensating controls become **load-bearing**: an explicit consent + disclosure at the
  allocation moment, a **per-theme pause**, a **global "Themes off" kill switch**, and a clear
  cap on how much of the user's cash a single theme can hold.
- **$250/order cap + fenced live account** already enforced in `broker.py`.
- **Concentration caps** (per-name ≤35%, speculative sleeve ≤20%) + the existing falling-knife /
  catastrophic-review guard on constituents.
- **Disclosure**: reuse `LegalDocs` total-loss + no-liability language; frame themes as *automated
  model portfolios you opt into*, human-mandate framing intact.
- ⚠️ **Compliance flag**: auto-investing a curated basket across many users leans harder toward
  *discretionary management / model-portfolio* territory than the single-user agent — carry this to
  the RIA track ([[emouva-agentic-trading-pivot]]).

---

## 8. Build phases

- **M0 — Central theme repo** ✅ *built*: `themes/theme_constituents/theme_allocations/theme_events`
  tables; admin create-theme + AI thesis pipeline (`services/agent/themes.py`, reuses the `research`
  tool-loop + web_search); constituent pick with capped conviction weights; admin Themes UI.
- **M1 — Monitoring** ✅ *built*: daily `monitor()` (8:15 ET) re-scores conviction from fresh
  constituent stats/news/earnings, drives the health/status state machine (a break is M2's unwind
  trigger), refreshes `perf_snapshot`; admin "Refresh now". All → `theme_events`.
- **M2 — Allocation + propagation (paper)** ✅ *built*: `theme_holdings` (isolated per-allocation
  book) + `allocation.cash`; `services/agent/theme_exec.py` — cash sweep, version-driven idempotent
  `reconcile()` (invest / rebalance / unwind), cross-user break-unwind, reconciler job (8:20 ET);
  user API `routers/themes.py` (list / allocate / mine / unwind). Paper-only; live still gated.
- **M3 — The addictive UI** ✅ *built*: `/polytrade` immersive surface — Discover feed of theme
  cards (conviction gauge, health pill, hero stat, perf, social proof), theme detail (thesis, basket
  weights, "what would break this", **live AI-reasoning feed**, one-tap add-capital modal), My Themes
  (live P&L + holdings + unwind); sidebar + mobile nav entries.
- **M4 — Live-path + social** ✅ *built + deployed (paper)*: real-money execution behind a dedicated
  `themes_live_enabled` gate (default OFF — themes stay paper even when platform live is on);
  notifications (break/weaken/recover + fill/exit) via the existing Notification model; social —
  follow-a-theme, comments + likes, ranked discovery rails, share link; weekly deep re-validation
  (Sun 6:30 ET). **Shipped to emouva.com paper-only.** Remaining for true real-money: build the live
  broker-routing branch in `reconcile_allocation` (map the per-allocation book to a Robinhood
  account) and flip `THEMES_LIVE_ENABLED` — gated behind the P3 live-execution verification.

---

## 9. Locked decisions (2026-07-09)

1. **Origination — Admin + AI assist.** Admin seeds a title + rough narrative; the AI tool-loop
   researches, drafts thesis/falsifiers/red-team, and picks the basket. Quality + compliance first.
2. **Packaging — Included in Pro ($8/mo).** No new billing surface; maximizes adoption.
3. **Weighting — Conviction-weighted + caps.** Per-name ≤35%, speculative sleeve ≤20%.
4. **Approval — Opt-in is consent.** Funding a theme auto-executes all buys/sells at any size; no
   per-trade prompt. Compensating controls (see §7) are therefore load-bearing: allocation-time
   consent + disclosure, per-theme pause, global kill switch, per-theme cash cap.
```
