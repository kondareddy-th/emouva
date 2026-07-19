# Handoff: Emouva — Marketing Landing Page (Agentic Trading)

## Overview

A complete replacement for the current risk-only landing page (`src/pages/Landing.tsx`). It repositions Emouva around the agentic trading product: an AI "**Partner**" that screens the market, trades under a user-written "**Mandate**," and explains every action in a "**Ledger**." Risk appears as *control* (approval threshold, hard limits, pause switch), not as analytics. Conversion goal: drive account signups ("Open an account") with a zero-risk paper-trading entry point and an interactive product demo embedded in the hero.

Visual language matches the trading product exactly (see the sibling `design_handoff_agentic_trading` bundle): private-bank calm — warm charcoal, champagne gold, serif numerals, mono market data, no icon library, no confetti.

## About the Design Files

The files in this bundle are **design references created in HTML** — a working prototype showing intended look and behavior. They are **not production code to copy directly**. The task is to **recreate this design in the target codebase** (`emouva/frontend`: Vite + React 18 + TypeScript + Tailwind 3 + react-router-dom v6 + lucide-react) using its established patterns: this page replaces `src/pages/Landing.tsx` on the `/` route.

- **`Emouva Landing.dc.html`** — THE canonical reference. Fully interactive. Open it in a browser (keep `support.js` in the same folder). All copy, colors, spacing, timing, and behavior come from here.
- **`support.js`** — runtime for the prototype. Ignore; not part of the design.

## Fidelity

**High-fidelity.** Recreate pixel-perfectly: exact hex values, fonts, sizes, and copy below. The written copy (Munger voice) is part of the design — preserve it verbatim. **Do not use lucide icons on this page** — the only motif is the gold rotated-square "diamond" (`div` with `transform: rotate(45deg)`).

---

## Design Tokens

Identical to the trading-platform handoff. Summary:

### Colors
- App background `#14120E` · raised strip `#171410` · card `#1B1915` · emphasis card `#1D1A14` · toast `#221E16` · input well `#14120E`
- Text: primary `#ECE5D8` · body `#D8D1C2` · secondary `#A69E8C` · muted `#8A8272` · faint `#6E675A` · disabled `#4A453B`
- Gold `#C6A15B` (hover `#D4B06A`) · light gold `#E3CD9E` · gain green `#7CA982` · loss red `#C4756A` · warning amber `#D0A048`
- Borders: default `rgba(214,190,140,0.12)`; dividers `0.10`; row hairlines `0.06`; gold emphasis `rgba(198,161,91,0.25–0.40)`; green receipt `rgba(124,169,130,0.28)`; red pause `rgba(196,117,106,0.3)`; gold tint fills `rgba(198,161,91,0.05–0.14)`
- Badge fills: gold-tint `rgba(198,161,91,0.14)` text gold · plain `rgba(255,255,255,0.05)` text `#A69E8C` · green `rgba(124,169,130,0.16)` text `#7CA982` · solid gold badge `#C6A15B` with `#14120E` text (AWAITING APPROVAL only)

### Typography (Google Fonts)
- **EB Garamond** 400/500/600 + italics — h1/h2 display, stat numerals, principle text, quotes
- **IBM Plex Mono** 400/500 — timestamps, tickers, overlines, badges' companions, footnotes; `font-variant-numeric: tabular-nums` on all numbers
- **Instrument Sans** 400/500/600 — UI chrome and body copy
- Overline style: mono 11px, `letter-spacing: .16em`, gold, preceded by a 6px diamond
- Label style: mono 10px, `letter-spacing: .13em`, `#6E675A`, uppercase
- Status badges: 9.5px / 600 / `.11em` / uppercase / 3px 8px padding / radius 4px
- Wordmark: EMOUVA, 13px, 500, `.22em`, `#E3CD9E` (footer: 12px)

### Type scale (this page)
- h1 hero: Garamond 500, `clamp(42px, 4.8vw, 58px)`, line-height 1.06, `min-height: 2.24em` (reserves 2 lines during the typing cycle), `letter-spacing: -0.01em`. **Cap is 58px** — the longest headline variant must fit one line in the 620px column.
- h2 section: Garamond 500, `clamp(30px, 3.4vw, 42px)`, line-height 1.12
- Final CTA quote: Garamond 500 italic, `clamp(34px, 4.2vw, 54px)`
- Hero sub 16.5px `#A69E8C` · section sub 15.5px · body 13–13.5px · ledger body 12.5px `#8A8272`
- Stat numerals: Garamond 34px (proof strip), 44px (funnel), 30px (step numbers 01/02/03)

### Shape & spacing
- Radii: cards 10px, inner cards/inputs 8px, buttons/chips 6px, badges 4–5px
- Section padding: `clamp(64px, 8vw, 104px)` vertical, 24px gutters; hero `clamp(56px,7vw,96px)` top
- Content max-width 1240px centered; top bar 54px sticky `rgba(20,18,14,0.98)` + bottom hairline
- Buttons: gold solid = gold bg, `#14120E` text, 600; outline = transparent, border `rgba(214,190,140,0.28)` (hover `0.5`), text `#D8D1C2`. Transitions 0.15s background/border only.
- Section separators: 1px `rgba(214,190,140,0.10)` bottom borders; alternate band sections use `#171410` background (proof strip, contrast section, footer)

---

## Page Structure (top to bottom)

1. **Top bar** (sticky): diamond + EMOUVA · right: market-status chip (green pulsing dot + mono `MARKET OPEN · 11:04 ET`), "The demo" link, "Sign in" link, gold CTA button.
2. **Hero** — two columns (flex-wrap; left `1 1 460px` max 620px, right `1 1 440px` max 600px, gap 56px):
   - Overline: ◆ `AGENTIC TRADING · UNDER A HUMAN MANDATE`
   - **Typing headline** (see Interactions): line 1 cream, line 2 gold
   - Sub: "Emouva runs your portfolio the way the best investors actually work: screen everything, buy rarely, explain every move. The Partner checks the market every 30 minutes — and asks your permission for anything over your limit."
   - CTAs: gold "Open an account →" + outline "Watch it work — the live demo"
   - Mono note: "Starts on paper money. Fund it only when it has earned your trust."
   - Divider, then Munger quote block: *"The big money is not in the buying and the selling, but in the waiting."* / `— CHARLIE MUNGER, THE PARTNER'S TEMPERAMENT`
   - **Live Ledger card** (right; see Interactions): header strip (`THE LEDGER` + green `LIVE` badge · right `NET LIQ $487,320 · DAY +0.66%`), feed area (`min-height: 430px`, padding 4px 18px 14px), footer strip (dynamic left/right text). Card: `#1B1915`, radius 10, shadow `0 24px 60px rgba(0,0,0,0.35)`. Caption below, right-aligned mono: "A real morning from the demo portfolio — open the full product →"
3. **Proof strip** (`#171410` band): 4 stats (Garamond 34px value / mono label / one-line note): **214** stocks screened this morning · **11** trades year to date (*"Few, by design."* italic gold) · **71%** win rate · 14-month median hold · **0** unexplained actions. Right-aligned footnote: `LIVE DEMO PORTFOLIO · YTD 2026`.
4. **How it decides** — overline `HOW IT DECIDES`, h2 "An elimination, every morning at 09:42.", sub "The Partner doesn't hunt for reasons to buy. It hunts for reasons not to — and acts only on what survives. Four gates, in order:"
   - **Funnel**: wrapper `display:flex; flex-wrap:wrap; gap:1px` with hairline background + border, radius 10, overflow hidden; each cell `flex:1 1 220px; min-width:0; background:#14120E; padding:24px 22px`. (Flex, NOT grid — on a 3+1 wrap the fourth cell must stretch full-width rather than orphan.) Cells: **214** THE UNIVERSE · **12** INSIDE THE CIRCLE (+ mono kill list: NVDA semis capex cycle / LLY pipeline risk / TSLA narrative-priced) · **4** MARGIN OF SAFETY ≥ 30% (+ `COST +34 · F +41 · KHC +38 · T +33`, red line "F, KHC, T — killed by inversion") · **1** THE SURVIVOR — COST (bg `#171410`, inset 1px gold ring `rgba(198,161,91,0.30)`, gold numeral, link "Walk through the real screen →").
   - Centered closing quote: *"An idea isn't yours until you can state the other side better than they can."*
5. **The Mandate** — two columns. Left: overline `THE MANDATE`, h2 "It can act alone. Only as far as you allow.", sub, hard-limit mono chips (`Max position 9.0%` · `Cash floor 10%` · `Max 3 orders / week` · `Sector cap 30%` · amber `Options & leverage — OUTSIDE MANDATE`), note "Limits are constitutional. The Partner cannot cross them — *even with your approval on a single order.* Changing one requires a backtest, like a principle." Right: **threshold slider card** + **pause card** (see Interactions).
6. **The Latticework** — overline, h2 "Twelve principles govern every decision.", sub "The Partner must cite one for anything it does — or declines to do. Edit them in your own words. Nothing applies until it survives a backtest against your actual history."
   - 3 principle cards (grid auto-fit minmax(270px,1fr)): gold diamond + italic Garamond 16px + mono meta. ① "Never interrupt compounding unnecessarily." / `CORE · MUNGER · invoked 34× this quarter · killed 9 ideas` ② "If the business is outside the circle of competence, the price doesn't matter." / `CORE · SELECTION · the gate that removed 202 of 214 this morning` ③ gold-bordered: "Prefer quality: gross profitability, low leverage, stable margins. Junk rallies are rented, not owned." / gold meta `FROM RESEARCH · Quality Minus Junk (2014) · backtest +1.6pp CAGR, −6pp drawdown`
   - Row of 2 cards: **WRITE YOUR OWN** (`#1D1A14` + gold border; inner well with sample italic principle "Never buy anything the week before its earnings call."; body ends `2 of 11 trades · +$310 avoided`) and **FEED IT RESEARCH** (QMJ became principle 13; momentum rejected — *40 trades a year violates "sit on your ass."*; link "See a paper get distilled →").
7. **Not a casino** (`#171410` band; behind a `showContrast` flag): centered h2 "Trading apps are paid when you trade. / **The Partner is paid to sit.**" Two cards: THE AVERAGE TRADING APP (muted: Confetti on your first options trade. / Streaks, badges, and a push alert at 6:12 a.m. / A feed engineered to make you act. / "Free" trades — your churn is the product.) vs EMOUVA (gold border: A ledger, not a feed. / Passes recorded with the same care as trades. / Four checks a day. One action a fortnight. / Flat subscription — we earn nothing when you churn.)
8. **How you start** — h2 "Three steps. The third one is waiting." Steps 01 Write the mandate / 02 Watch it on paper / 03 Fund it when convinced (copy in prototype).
9. **Final CTA** (`id="open"`, centered): giant italic quote *"Mostly, the job is sitting."* + "The rest is knowing when not to. Open an account and watch the Partner work a real morning — on paper money, at your limits." + gold CTA + outline "Tour the live demo" + mono "No card. No minimums on paper. Cancel like an adult — one click."
10. **Footer** (`#171410`): diamond + EMOUVA · mono disclaimer "© 2026 EMOUVA · Emouva is a technology platform, not a registered investment adviser. Paper trading is simulated. Live markets involve risk, including loss of principal. Demo-portfolio figures are illustrative."
11. **Toast** — fixed bottom-center pill (`#221E16`, gold border `rgba(198,161,91,0.4)`, diamond + 12.5px text), one at a time, auto-dismiss 3.8s.

---

## Interactions & Behavior

### 1. Typing headline (hero)
Cycles through three headline pairs forever (line A cream / line B gold):
1. `The Partner trades.` / `You hold the mandate.`
2. `Most days it does nothing.` / `That is the point.`
3. `Hire a partner,` / `not another app.`

Mechanics: first pair renders **fully typed on load** (no blank hero). Hold 3.8s → delete char-by-char at 12ms → 380ms gap → type next pair at 34–76ms/char (jittered) → hold 3.8s → repeat. A `|` cursor trails the active character while typing/deleting and hides during holds. The `<h1>` reserves two lines (`min-height:2.24em`) so layout never shifts. Implement with `setTimeout` state ticks (a `useTypingAnimation`-style hook exists in the old Landing.tsx to adapt).

### 2. Live Ledger feed (hero)
A scripted stream, chronological, oldest at top, `tail -f` feel. Entry anatomy: 44px mono timestamp column · badge · optional bold order line (13.5px `#ECE5D8` + green mono note) · optional mono line · body 12.5px `#8A8272` · optional italic gold Garamond quote · optional underlined link. Rows separated by `rgba(214,190,140,0.06)` hairlines.

**Pre-approval script** (arrival gaps after load: 0.5s, 1.2s, 1.4s, 1.5s, 1.9s, 2.1s):
1. `09:31 PORTFOLIO CHECK` — "Pre-market review. Futures are noisy; the theses are quiet. No action."
2. `09:42 MORNING SCREEN` — mono `214 screened → 12 in circle → 4 margin ≥30% → 1 passed inversion` — "Costco survived every attempt to kill it. Order drafted — it exceeds your limit, so it waits for you below." — link "See who fell out, and why →"
3. `09:58 PASSED` — "Ford at margin +41% — killed by inversion. One union negotiation away from a broken thesis."
4. `10:12 PASSED` — "NVDA up 4.1% on momentum. No thesis has changed — chasing strength is not in the mandate." — quote *"Envy of a rising ticker is a terrible reason to own it."*
5. `10:31 EXECUTED` — order `SELL 60 OXY @ $71.22` + green `realized +$1,842` — "Position crossed the 9% ceiling. Trimmed back to size — the thesis stands; the sizing rule stands taller."
6. `10:47 PORTFOLIO CHECK` — "Checked all 214 names. Touched nothing."

**Approval card** arrives 2.2s later (`11:02`, `order #1847`): gold-tint card `rgba(198,161,91,0.06)` + gold border; solid-gold pulsing badge `AWAITING YOUR APPROVAL` (2.6s opacity pulse); "Buy 40 COST · Costco Wholesale @ $912.40 ≈ $36,496"; reasoning "Exceeds your $25,000 limit, so I'm asking. Inside the circle, fair value $1,380, margin 34%, survived inversion. Sized at 8.5% — under your 9% ceiling."; **Approve** (gold) / **Decline** (outline) + mono aside "try it — this one is live". **The stream pauses here until the visitor decides.**

**Decision:**
- Approve → card becomes green-bordered **EXECUTED** receipt: "Bought 40 COST @ $912.63 avg — filled in two lots · Approved by you. Cash reserve now 10.7% — above your 10% floor. The thesis, sizing math, and exit triggers are written down. Nothing about this trade is a mystery." Toast: "Order placed — bought 40 COST at $912.63 avg."
- Decline → muted **DECLINED** card: "Understood. I won't resubmit COST for 30 days unless the thesis materially improves. Vetoes are part of the mandate — you never owe me a reason." Toast: "Declined. The Partner logged your veto — no questions asked."

**Post-decision script** (1.7s, 5.6s, 10.4s after decision):
1. `11:30 PORTFOLIO CHECK` — "Prices moved. Theses didn't. No action." — quote *"Mostly, the job is sitting."*
2. `12:04 PASSED` — "AAPL trades 10% above my fair value. Watching, not selling — never interrupt compounding unnecessarily."
3. `12:34 PORTFOLIO CHECK` — "Cash above the floor, drift inside the bands. Nothing to do, so nothing was done."

**Windowing:** keep the visible list ≤ ~6 rows by dropping the oldest pre-approval entries as new ones arrive: pre-entries kept = 6 before the approval appears, then `max(2, 5 − postCount)`. Never drop the approval card while pending.

**Card footer (cross-rippling):**
- Left (mono): "Next check 11:30 ET · every 30 min" → while pending: "Waiting on your approval · order #1847 · expires 15:55 ET" → after decision advances with post entries (`12:04`, `12:34`, `13:04`) → if the Mandate-section Pause is active: "Paused — watching, not trading".
- Right: live tally "Checked N× today · acted once/N×" (checks = PORTFOLIO CHECK + MORNING SCREEN entries arrived; acted = EXECUTED entries + 1 if approved).

### 3. Threshold slider (Mandate section)
Custom div slider (NOT `<input type=range>`): 28px-tall hit area, 3px track `rgba(255,255,255,0.08)`, gold fill, 16px `#E3CD9E` thumb with shadow. Range $1,000–$100,000, step $500. Pointer-capture drag (wrap `setPointerCapture` in try/catch). Endpoint labels mono: "$1k · ask always" / "$100k · fully autonomous". Value renders inline: "Ask my approval above **$25,000**" (Garamond 22px light gold, tabular).
Below, a gold-tint note box live-flips at **$36,500**: below → "At $X, this morning's $36,496 Costco buy waits for you. Anything smaller, the Partner handles alone — and still shows its work."; at/above → "At $X, this morning's $36,496 Costco buy would have executed on its own — you'd have read about it in the Ledger, not approved it."

### 4. Pause card (Mandate section)
Red-bordered card, label `THE OFF SWITCH`, copy "One click. The Partner keeps watching and writing to the Ledger, but stops trading. No confirmation maze, no retention flow." Red-outline button **Pause the Partner** → replaced by amber chip (pulsing dot + mono `PAUSED — watching, not trading`) + gold **Resume the Partner**. Toasts: "The Partner is paused. It will keep writing to the Ledger." / "Resumed. Next check in 26 minutes." Pausing also flips the hero Ledger footer (see above).

### 5. Links
- "Open an account" (nav, hero, final CTA) → `/signup`
- "The demo" / "Watch it work — the live demo" / "Tour the live demo" / all ledger + funnel + research links → the trading product (`/trading` route from the agentic-trading handoff). In the prototype these point at `Emouva Prototype.dc.html`.
- "Sign in" → `/login`

### Animation notes for production
Entrance animations were removed from the prototype for environment reasons. In production: add subtle 200ms opacity/translate-Y(6px) entrances on each arriving ledger entry, keep the AWAITING APPROVAL badge pulse (2.6s) and status-dot pulses (1.8s), optionally blink the typing cursor (500ms). Respect `prefers-reduced-motion`. All hover transitions 0.15–0.2s on background/border/color only.

## State Management

```ts
// headline
hIdx: 0|1|2; hChars: number; hPhase: 'typing'|'pausing'|'deleting';
// ledger feed
arrivedPre: 0–6; approvalShown: boolean;
approval: 'pending'|'approved'|'declined'; arrivedPost: 0–3;
// controls
threshold: number (1000–100000, step 500); paused: boolean;
toast: string | null; // one at a time, 3.8s
```

All timers cleared on unmount. Config flags worth keeping (were tweakable props in the prototype): `heroHeadline: 'cycle'|static-variant`, `ctaVariant: 'account' ("Open an account") | 'paper' ("Start paper trading")`, `showContrast: boolean` — useful for A/B tests.

## Responsive

The prototype is fluid (flex-wrap + `clamp()` + auto-fit grids) with no breakpoints: hero stacks when the right column can't fit 440px; funnel cells wrap with the survivor stretching full-width; stat/step grids reflow via auto-fit. In production, verify at 375px: 24px→16px gutters, nav "The demo"/"Sign in" may collapse, ledger timestamp column stays 44px, hit targets ≥44px (Approve/Decline, slider, pause). Keep the h1 clamp cap at 58px.

## Design Tokens → Tailwind

Reuse the token extension from `design_handoff_agentic_trading/README.md` (`emouva-gold`, surface scale, `fontFamily: { serif: EB Garamond, mono: IBM Plex Mono, sans: Instrument Sans }`) and the same Google Fonts link (Garamond 400/500/600 + italics, Plex Mono 400/500, Instrument Sans 400/500/600).

## Assets

None. No images, no icon fonts. The diamond motif is CSS; every visual is typography, hairlines, and tint fills.

## Files

- `Emouva Landing.dc.html` — canonical interactive prototype (open with `support.js` alongside)
- `support.js` — prototype runtime (ignore)
- Sibling bundle `design_handoff_agentic_trading/` — the product the landing links into (tokens shared)
