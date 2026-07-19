# Handoff: Emouva — Agentic Trading Platform (Risk + Autonomous Trading)

## Overview

Emouva is an agentic trading platform with two concerns only: **risk** and **automated agentic trading**. An LLM-driven harness ("**The Partner**") screens stocks, executes trades under a user-defined mandate, and explains every action. The trading psychology is Charlie Munger's: inversion, circle of competence, margin of safety, sit-on-your-ass investing. The principle system is branded "**The Latticework**."

The design deliberately reads like a private bank, not a trading terminal: warm charcoal surfaces, champagne-gold agent accents, serif numerals, de-saturated gain/loss colors. The goal is calm, auditable trust — not dopamine.

## About the Design Files

The files in this bundle are **design references created in HTML** — working prototypes showing intended look and behavior. They are **not production code to copy directly**. The task is to **recreate these designs in the target codebase** (`emouva/frontend`: Vite + React 18 + TypeScript + Tailwind 3 + react-router-dom v6 + recharts + lucide-react) using its established patterns: `src/pages/*` for routed screens, `src/components/*`, `src/hooks/use*Store.ts` for state, `src/data/mockData.ts` for mock data.

- **`Emouva Prototype.dc.html`** — THE canonical reference. Fully interactive, all 7 screens, desktop + mobile. Open it in a browser (keep `support.js` in the same folder). All copy, colors, spacing, and behavior come from here.
- **`Trading Platform Directions.dc.html`** — earlier static explorations (directions 1a/1b/1c and per-screen mockups 2a–2f). Reference only, for context on rejected alternatives.
- **`support.js`** — runtime for the prototypes. Ignore; not part of the design.

## Fidelity

**High-fidelity.** Recreate the UI pixel-perfectly: exact hex values, fonts, sizes, and copy below. The written copy (Munger voice: "Mostly, the job is sitting", "few, by design") is part of the design — preserve it verbatim from the prototype.

---

## Design Tokens

### Colors
Surfaces
- App background: `#14120E`
- Raised strip / right rail / section footer: `#171410`
- Card: `#1B1915`
- Emphasis card (gold-tinted, e.g. pending approval rail, editing): `#1D1A14`
- Mobile bottom nav: `#12100C` at 98% opacity
- Toast: `#221E16`
- Input / inner well: `#14120E`

Text
- Primary (headings, key numbers): `#ECE5D8`
- Body: `#D8D1C2`
- Secondary: `#A69E8C`
- Muted: `#8A8272`
- Faint (labels, timestamps): `#6E675A`
- Disabled: `#4A453B`

Accents
- Gold (agent voice, primary actions, active states): `#C6A15B` (hover: `#D4B06A`)
- Light gold (wordmark, fair-value figures, slider thumb): `#E3CD9E`
- Gain green (muted on purpose): `#7CA982`
- Loss red (muted on purpose): `#C4756A`
- Loss badge background (SELL-at-loss): `#8A4A40`
- Warning amber (paused, above-fair-value): `#D0A048`

Borders
- Default card border: `rgba(214,190,140,0.12)`; section dividers `0.10`; table header `0.08`; row dividers `0.06`
- Gold emphasis borders: `rgba(198,161,91,0.25–0.40)`
- Green receipt border: `rgba(124,169,130,0.28)`; red pause card border: `rgba(196,117,106,0.3)`
- Gold tint fills: `rgba(198,161,91,0.05–0.14)`

### Typography (Google Fonts)
- **EB Garamond** (400, 500, 600 + italics) — display headings (20–24px), hero numerals (38px), stat values (15–26px), principle text (italic 15px), Munger quotes (italic, gold)
- **IBM Plex Mono** (400, 500) — all market data, timestamps, tickers, badges' companion text (10–13px), `font-variant-numeric: tabular-nums` everywhere numbers align
- **Instrument Sans** (400, 500, 600) — all UI chrome, body copy (9.5–14px)
- Label style: 9.5–10px, weight 500, `letter-spacing: .13em`, uppercase, color `#6E675A`
- Status badges: 9.5px, weight 600, `letter-spacing: .11em`, uppercase, 3px 8px padding, radius 4px
- Wordmark: EMOUVA, 13px, weight 500, `letter-spacing: .22em`, color `#E3CD9E`

### Shape & spacing
- Radii: cards 10px, inner cards/inputs 8px, buttons 6px, chips/segments 5–7px, filter pills 14px, toggle track 11px
- Card padding: 16–18px (desktop), 13–14px (mobile). Page gutters: 24px desktop / 16px mobile
- Brand motif: a rotated square ("diamond") — a `div` with `transform: rotate(45deg)`, gold. Sizes: 10px (logo), 6–8px (bullets), 5px (mobile nav active dot). **No icon library needed** — the design is intentionally icon-free; do not add lucide icons to these screens.
- Toggles: 38×21px track (radius 11), 15px knob, 3px inset; ON = gold track + `#14120E` knob, OFF = `rgba(255,255,255,0.08)` track + `#4A453B` knob; animate `left`/`background` 0.2s
- Top bar: 54px, sticky, `rgba(20,18,14,0.98)`, bottom border. Content max-width 1440px centered.

---

## Information Architecture

Six tabs + one drill-in. Suggested routes:

| Tab | Route | Purpose |
|---|---|---|
| Ledger (home) | `/trading` | Agent's journal: every action or non-action, timestamped, with reasoning |
| Positions | `/trading/positions` | Net liquidity, chart, holdings with agent's fair value & margin |
| History | `/trading/history` | Every executed trade, expandable reasoning, lessons |
| Principles | `/trading/principles` | The Latticework: view/edit/pause principles, propose new ones |
| Research | `/trading/research` | Papers → gist → inversion → backtest → adopt as principle |
| Settings | `/trading/settings` | The Mandate: autonomy, cadence, hard limits, notifications, pause |
| Screen detail | `/trading/screen/:id` | Transparency drill-in: the 214→12→4→1 elimination funnel |

Market status chip in the top bar: green dot + `MARKET OPEN · 11:04 ET` (mono 11px). Paused state swaps to amber pulsing dot + `PAUSED`.

---

## Screens

### 1. Ledger (home)
- **Metric strip** (raised `#171410`, collapsible): 5-column grid — Net Liquidity `$487,320.18` (serif 24px, cents in 16px muted), Day P&L `+$3,214 +0.66%` (green), Open P&L `+$41,608`, Cash `18.2%`, Risk Temperature `Cool` + 4 ascending mini-bars (2 gold lit). "Collapse ▲" bordered chip on the right; collapsed state is a single row: value · day change · `Cash 18.2% · Risk Cool` · "Expand ▼".
- **Feed** (left column, 1fr): title "The Ledger" (serif 20px) + filter tabs `All / Trades / Passes / Screens / Checks` (11px, active = gold text + 1.5px gold underline). Entries are rows: 44px mono timestamp column + content, separated by `rgba(214,190,140,0.10)` top borders. Entry types:
  - **AWAITING APPROVAL** (gold-tinted card `rgba(198,161,91,0.06)` + gold border): badge (gold bg, dark text, subtle opacity pulse), `order #1847`, order line "Buy 40 COST · Costco Wholesale @ $912.40 ≈ $36,496" (14px), reasoning paragraph naming the threshold and all four gates, link "See the full screen →", buttons **Approve** (gold) / **Decline** (outline) + note "Also sent to your phone · expires 15:55 ET".
  - **PASSED** (badge: white 5% bg): NVDA momentum pass, reason + italic serif gold Munger quote.
  - **EXECUTED** (green badge): `SELL 60 OXY @ $71.22` + `realized +$1,842` green mono + one-line reasoning.
  - **MORNING SCREEN** (gold-tint badge): funnel summary 214 screened → 12 in circle → 4 margin ≥30% → 1 passed inversion (numbers stacked over labels, joined by 30px hairlines; final stage gold) + underlined link "See who fell out, and why →" → screen detail.
  - **PORTFOLIO CHECK** (white 5% badge): "…Mostly, the job is sitting."
  - Footer row: "Tuesday's ledger · 6 entries · older activity lives in History" (link → History).
- **Right rail** (340px, `#171410`): three cards —
  - **Approvals**: gold-bordered when pending, count pill "1", order summary, Approve / Review buttons. Resolved state: plain border, single sentence (e.g. "Nothing pending. The COST buy was approved at 11:06…").
  - **Guiding Principles**: 3 italic serif principles with gold diamond bullets, "Edit →" (→ Principles), footer "12 principles · 3 shown · last edited Jun 28".
  - **Cadence**: "Every 30 min" (serif 20px) + "market hours", mono "Next check 11:30 ET · 26 min", divider, "Checked 4× today · acted once. Low activity is the design, not a defect." + "Adjust →" (→ Settings).

### 2. Screen detail (drill-in)
Breadcrumb bar: "← Ledger / Morning screen · Wednesday, July 2 · 09:42 ET" + right-aligned "archived · immutable". Four columns (200px / 250px / 290px / 1fr, right-borders; the survivor column on `#171410`):
1. **214 Universe** — description + faded ticker chips (NVDA, LLY, JPM, XOM, PG, TSLA, +207 at 45% opacity)
2. **12 Inside the circle** — surviving chips + "Notable exclusions" with per-ticker reasons (NVDA semis capex; LLY pipeline risk; TSLA narrative-priced)
3. **4 Margin of safety ≥ 30%** — ticker/margin rows (COST +34, F +41, KHC +38, T +33) + "Killed by inversion" reasons for F, KHC, T
4. **COST — the survivor** — five ✓ rows (circle, fair value $1,380 w/ DCF assumptions, margin 34%, inversion attempts, sizing → 8.5% weight), gold **Verdict** card (text varies with approval state; Approve/Decline buttons if still pending), closing italic quote: *"An idea isn't yours until you can state the other side better than they can."*

### 3. Positions
- Header: Net Liquidity `$487,320.18` (serif 38px) + green delta caption + range switcher `1D 1W 1M 1Y ALL` (mono 11px chips, active = gold bg dark text). Below: gold area line chart (120px tall, 1.8px stroke `#C6A15B`, fill = vertical gradient gold 22% → 0%, hairline baseline). Delta text and curve change per range.
- Right stat stack (300px): Cash reserve `$88,692 · 18.2%`, Open P&L `+$41,608`, YTD `+11.4%`, Risk temperature `Cool · 31/100` — label + serif value cards.
- **Table** (10 columns): Ticker · Company · Qty · Avg Cost · Price · Day · Open P&L · Fair Value · Margin · Weight. Mono 12px tabular; company in sans muted; Fair Value column in light gold `#E3CD9E`; margins green (positive) or amber (negative = above fair value); header 9.5px uppercase. Row hover: `rgba(198,161,91,0.04)`. COST row: gold ◆ marker + gold 5% row tint + "buy pending your approval" while pending.
- Data: BRK.B 120@360.55→412.36 FV 480 +14% w10.2 · AAPL 150@197.70→228.44 FV 205 −10% w7.0 · OXY 150@74.14→71.22 FV 92 +23% w6.5 · AXP 80@271.68→301.75 FV 355 +15% w5.0 · KO 300@59.45→63.18 FV 74 +15% w3.9 · COST 20@861.20→912.40 FV 1,380 +34% w3.7 · MCO 32@429.52→488.02 FV 560 +13% w3.2.
- Table footer strip (`#171410`): amber diamond + "AAPL trades 10% above my fair value. Watching, not selling — *never interrupt compounding unnecessarily.* I'll flag it if the gap exceeds 25%."
- Rail: **Allocation** (5 label+% rows with 5px progress bars in descending golds `#C6A15B → #B08F53 → #8A7443 → #6B5A34 → #4E4227`), **Position Bands** (Weight ceiling 9.0%, Cash floor 10.0%, Drift ±1.5pp + note about BRK.B auto-trim linking to Ledger).

### 4. History
- Stat strip: Realized P&L YTD `+$28,411` (green serif 22px) · Win rate `71%` · Median hold `14 months` · Trades YTD `11` + italic gold "few, by design".
- Filter pills: All / Buys / Sells / Auto-executed / Approved by you (active = gold bg pill).
- **Table**: Date · Action badge (BUY = light-gold bg, SELL = green bg, SELL-at-loss = `#8A4A40` bg cream text) · Order · Trigger · Authorized (gold text when "Approved by you") · Realized (green/red/`open`) · caret. Whole row clickable → expands.
- **Expanded detail**: two side-by-side dark cards — entry thesis + outcome ("Why it sold" / "What broke" — red-tinted border + red label for losses) — plus, for PARA, a gold **lesson strip**: "Lesson added to the Latticework (v12): ad-supported streaming economics are outside our circle of competence." PARA row starts expanded; loss rows get a faint red row tint when open.
- Six trades: OXY Jul 2 (ceiling trim, +$1,842), AXP Jun 20 (add on drift; adds need 15% not 30%), MCO Jun 12 (screen; FV cut 685→560 later), PARA May 29 (thesis broke, −$1,306, lesson), KO May 6 (new position → needed your approval), BRK.B Apr 14 (drift rebalance).
- Footer: "Every row links back to its Ledger entry and the screen that produced it. Nothing is untraceable."

### 5. Principles — The Latticework
- Header: "The Latticework" (serif 24px) + "12 principles govern every decision. The Partner must cite one for anything it does — or declines to do."
- Sections **Temperament / Selection / Sizing & Selling**. Principle card: gold diamond · italic serif 15px principle text · mono 11px meta line (`CORE · MUNGER · invoked 34× this quarter · killed 9 ideas`) · Edit / Pause outline chips. Research-derived principles: gold border + gold meta (`FROM RESEARCH · Quality Minus Junk … · backtest: +1.6pp CAGR, −6pp drawdown`). Paused: 55% opacity + amber meta "PAUSED — not consulted until resumed", button reads Resume.
- **Editing state** (replaces card): `#1D1A14` + strong gold border, "EDITING" label, textarea with the principle text (italic serif), agent restatement box ("How I'll apply this: I will reject any buy where the price exceeds 70%…"), **Save & backtest** / Cancel + "Changes apply only after backtest review".
- Rail: **Add a principle** (textarea "Write it in your own words…", explanation, gold **Propose**) → **Your proposal** card with animated backtest progress bar → results (Trades blocked 2 of 11 · P&L effect +$310 avoided · Drawdown −0.4pp) + Adopt/Discard. **Pending change · backtested** card ("Raise margin of safety gate from 30% to 35%" · blocked 3 of 11 · −$2,140 missed · −1.1pp drawdown) + Adopt/Discard. **Version history** (mono version + description rows; v14 Jun 28 raised gate 25→30; v13 Jun 12 PARA lesson; v12 May 30 averaging-down rule).

### 6. Research
- Paper header: "Quality Minus Junk" (serif 24px) + status badge DISTILLED (light gold) → ADOPTED (green), byline "Asness, Frazzini & Pedersen · 2014 · uploaded by you, Jun 11 · read in 4 min by the Partner".
- **The gist** card (2–3 sentences). **The inversion — how does this fail?** gold-bordered card: "I tried to kill it three ways. It survives two:" + rows labeled `SURVIVES`/`SURVIVES`/`FAILS` (mono green/red 60px column) with reasons.
- **Backtest** card: 4 stats (CAGR 11.8% vs 10.2 · Max DD −18% vs −24 · Sharpe 0.81 vs 0.66 · Worst stretch Q2 2020 in red) + dual-line chart (gold solid = with quality gate; dashed 30% cream = baseline) + legend.
- **Draft principle** (gold-tinted card): italic serif draft + **Add to the Latticework** / Revise / Discard. After adopting: green confirmation card "Adopted into the Latticework · today" + link to Principles.
- Rail: dashed-gold **dropzone** ("Drop a paper, or paste a link" + "I'll read it, distill it, invert it, and backtest it…"), **In progress** (Momentum Crashes — "inverting · 62%" gold progress bar animating; Superinvestors — "queued"), **Library** list with badges: ADOPTED (green) / REJECTED (white 6% bg) + rejection reasons ("factor rotation needs 40×/yr turnover — violates 'sit on your ass'", "outside circle of competence — we don't do intraday").

### 7. Settings — The Mandate
Header: "The Mandate" + "What the Partner may do alone, when it must ask, and how often it looks." 2×2 card grid:
- **Autonomy**: "Ask my approval above **$25,000**" (serif light-gold value) + custom slider (3px track, gold fill, 16px light-gold thumb; range $1k–$100k, step $500; endpoint labels "$1k · ask always" / "$100k · fully autonomous"); toggles "Always ask for brand-new positions" (ON), "Always ask before selling at a loss" (ON); disabled row "Options & leverage" + `OUTSIDE MANDATE` chip; gold note box repeating the current threshold.
- **Cadence**: segmented `5m 15m 30m 1h Daily` (mono chips, active gold); mono "Next check 11:30 ET · 26 min" (updates per selection: 11:09/11:19/11:30/12:04/"tomorrow · 09:30 ET"); psychology note "Checking more often doesn't earn more — it just finds more reasons to act. 30 minutes is for risk, not for trading."; toggles "Intraday checks on portfolio earnings days" (ON), "After-hours monitoring" (OFF).
- **Hard limits**: read-only mono value chips — Max position weight 9.0% · Cash floor 10% · Max orders/week 3 · Single-day deployment cap $50,000 · Sector cap 30% + footnote "Limits are constitutional — the Partner cannot cross them even with your approval on a single order. Changing one requires a backtest, like a principle."
- **Notifications**: "Message to phone for approvals" (ON), "In-app approvals queue" (ON), "Daily P&L push" (OFF + italic serif aside "— off by default; watching daily P&L breeds twitchiness").
- **Pause** (red-bordered card): explanation ("…Liquidation requires a typed confirmation and a 24-hour cooling-off period — panic is not a strategy.") → red outline **Pause the Partner** → inline confirm ("Yes, pause trading" dark-red solid / "Keep trading") → paused state ("Paused since 11:06 ET…") with gold **Resume the Partner**.

---

## Interactions & Cross-Screen Behavior

The prototype's defining quality: **actions ripple everywhere**. Recreate these exactly:

1. **Approve COST** (Ledger card, rail, or Screen-detail verdict) → approval entry becomes a green EXECUTED receipt ("Approved by you at 11:06. Filled in two lots… Cash reserve now 10.7%."); rail card clears; Positions: COST qty 20→60, avg 861.20→895.49, weight 3.7%→8.5%, row moves to 2nd (after BRK.B), ◆ removed; cash stat $88,692·18.2% → $52,187·10.7%; allocation Cash bar 18%→11%; screen-detail verdict updates; toast "Order placed — bought 40 COST at $912.63 avg."
2. **Decline** → muted DECLINED entry ("…I won't resubmit for 30 days… vetoes are part of the mandate."); rail clears; toast.
3. **Adopt pending change** (Principles) → margin gate 30→35% everywhere the number appears (principle text, meta, editing restatement, funnel column header); version history gains "v15 · today"; toast.
4. **Adopt QMJ draft** (Research) → badge flips to ADOPTED, draft card becomes green confirmation, principle #13 appears in Principles › Selection with gold border, ledger-rail count and "Showing x of y" update, version history entry added; toast "Added to the Latticework — principle 13 of 13."
5. **Propose principle** → empty input pops toast "Write the principle in your own words first."; otherwise proposal card with progress bar animating ~350ms ticks to 100%, then backtest results + Adopt/Discard; Adopt appends a `YOURS` principle.
6. **Edit principle** → inline editor with restatement; Save & backtest → toast "Backtesting your change — review it in the pending card before it applies."
7. **Pause a principle** → card dims, meta goes amber, toast.
8. **Threshold slider** → live-updates the approval-card copy ("Order exceeds your $X auto-execution limit"), rail ("Over $Xk limit"), autonomy note.
9. **Cadence** → updates ledger-rail cadence card + "Next check" copy.
10. **Pause the Partner** → confirm step → amber pulsing status dot, `PAUSED` status text, full-width amber banner under the top bar ("The Partner is paused — watching and writing to the Ledger, but not trading." + Resume link), cadence copy "paused — no checks scheduled". Resume restores everything + toast.
11. **Ledger filters** show/hide entry types; History filters filter rows; chart range switches curve + delta caption.
12. **Toast**: bottom-center pill (dark, gold border, gold diamond + 12.5px text), auto-dismiss ~3.8s, one at a time.

Hovers: gold buttons lighten to `#D4B06A`; outline buttons/chips brighten border to `rgba(214,190,140,0.4–0.5)`; nav items brighten text; table rows tint gold 4%. All transitions 0.15–0.2s on background/border/color only.

**Animation caution:** entrance fades were removed from the prototype for environment reasons — in production, subtle 150–250ms opacity/translate-Y entrances on tab switch are welcome. Keep the AWAITING APPROVAL badge's slow opacity pulse (2.6s) and the paused status dot pulse (1.8s).

## Responsive (breakpoint: 800px)

Mobile (<800px):
- Top bar: logo + status dot with short text (`OPEN · 11:04`) + avatar; tab nav moves to a **fixed bottom bar** (60px + safe-area inset, `#12100C`, gold top border): 6 equal text-only items (9.5px), active = light-gold text + 5px gold diamond dot above.
- Metric strip → 2-column grid; ledger rail stacks below feed; funnel columns stack vertically with bottom borders.
- Positions table → **cards**: ticker + P&L header row, muted company line, then `qty sh · $price / day% / FV · margin / weight` row. History rows → cards: date + badge + realized + caret, order line, trigger·auth line; expansion stacks the two detail cards.
- Settings grid, Principles/Research two-column layouts → single column. Toast sits above the bottom nav (bottom: 94px vs 28px desktop).
- Hit targets ≥44px on interactive rows/buttons.

## State Management

One store (e.g. `useAgentStore` following the existing `usePortfolioStore` pattern):

```ts
tab; stripCollapsed; chartRange: '1D'|'1W'|'1M'|'1Y'|'ALL';
approvalState: 'pending'|'approved'|'declined';
ledgerFilter; histFilter; expandedTrades: Record<string,boolean>;
editingPrincipleId; draftText; newPrincipleText;
proposal: {text, progress, done} | null;
pendingChange: boolean; marginGate: 30|35; qmjAdopted: boolean;
customPrinciples: Principle[]; pausedPrinciples: Record<string,boolean>;
threshold: number (1000–100000, step 500); cadence: '5m'|'15m'|'30m'|'1h'|'Daily';
toggles: {newPos, lossSales, earnDays, afterHours, phone, queue, daily};
paused: boolean; pauseConfirm: boolean; toast: string|null;
```

Suggested API surface when wiring the real harness (backend is FastAPI): `GET /agent/ledger`, `POST /agent/orders/{id}/approve|decline`, `GET /agent/screens/{id}` (funnel), `GET/PUT /agent/principles` (+ `POST /agent/principles/backtest`), `POST /agent/research` (paper upload), `GET/PUT /agent/mandate`, `POST /agent/pause|resume`. Phone approval notifications are a later companion app — for now the settings toggle + "Also sent to your phone" copy are the only surface.

## Implementation Notes for This Codebase

- Extend `tailwind.config.js` with the token palette above (e.g. `emouva-gold`, `emouva-ink`, surface scale) and `fontFamily: { serif: ['"EB Garamond"'], mono: ['"IBM Plex Mono"'], sans: ['"Instrument Sans"'] }` scoped to this area. Add the Google Fonts `<link>` (weights: Garamond 400/500/600 + italic, Plex Mono 400/500, Instrument Sans 400/500/600).
- This product area has its **own visual system** — do not reuse the existing navy/emerald dashboard theme, sidebar, or lucide icons inside these screens. Simplest integration: a `/trading` route group with its own `TradingLayout` (top bar + tabs + mobile bottom nav) instead of the existing `Layout`/`Sidebar`.
- Charts: recharts `AreaChart` (gold stroke 1.8, gradient fill 22%→0, no grid, hairline baseline) and `LineChart` for the backtest comparison (dashed baseline). Tabular-nums on all numeric cells.
- Tables are CSS grid rows (not `<table>`), matching the column specs above.
- Mock data: port the exact positions/trades/ledger entries into `src/data/agentMockData.ts`.

## Assets

None required. No images or icon fonts — the diamond motif is CSS, charts are drawn, fonts come from Google Fonts.

## Files

- `Emouva Prototype.dc.html` — canonical interactive prototype (open with `support.js` alongside)
- `Trading Platform Directions.dc.html` — earlier explorations/mockups (context only)
- `support.js` — prototype runtime (ignore)
