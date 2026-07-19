/**
 * Trading-side ("The Partner") design tokens + mock data.
 * Ported from design_handoff_agentic_trading/Emouva Prototype.dc.html.
 * This product area has its OWN banker's-green / champagne-gold (Greenroom)
 * visual system — do not reuse the navy/emerald risk-side theme here.
 */

// ── Palette (Greenroom — deep banker's-green surfaces, bright text) ────
export const C = {
  // surfaces
  bg: '#0C110E',
  raised: '#0F1511',
  card: '#131B16',
  emphasis: '#151E18',
  toast: '#1A241D',
  mobileNav: 'rgba(11,16,13,0.98)',
  topBar: 'rgba(12,17,14,0.98)',
  // text  (each level lifted ~2 steps brighter — this is the readability fix)
  textPrimary: '#F7FAF6',
  body: '#E7EDE5',
  secondary: '#C4CEC1',
  muted: '#A6B2A3',
  faint: '#93A08F',
  disabled: '#4E5A50',
  // accents
  gold: '#CFAE62',
  goldHover: '#DBBC72',
  lightGold: '#E9D6A2',
  gain: '#7FE3A9',        // phosphor mint
  loss: '#F2937F',
  lossBadge: '#96503F',
  warning: '#DFB65A',
  // borders
  border: 'rgba(180,220,190,0.13)',
  borderDim: 'rgba(180,220,190,0.11)',
  borderHeader: 'rgba(180,220,190,0.09)',
  borderRow: 'rgba(180,220,190,0.07)',
  goldBorder: 'rgba(207,174,98,0.25)',
  goldBorderStrong: 'rgba(207,174,98,0.40)',
  goldTint: 'rgba(207,174,98,0.07)',
  goldTintRow: 'rgba(207,174,98,0.06)',
  goldHoverRow: 'rgba(207,174,98,0.04)',
  greenBorder: 'rgba(127,227,169,0.28)',
  redBorder: 'rgba(242,147,127,0.3)',
  redTint: 'rgba(242,147,127,0.05)',
  amberBorder: 'rgba(223,182,90,0.3)',
  amberTint: 'rgba(223,182,90,0.08)',
}

// ── Fonts ─────────────────────────────────────────────────────────────
export const SERIF = "'EB Garamond',serif"
export const MONO = "'IBM Plex Mono',monospace"
export const SANS = "'Instrument Sans',sans-serif"

/** uppercase micro-label style shared everywhere */
export const label = (mb = 5): React.CSSProperties => ({
  font: `500 9.5px ${SANS}`,
  letterSpacing: '.13em',
  color: C.faint,
  textTransform: 'uppercase',
  marginBottom: mb,
})

// ── Navigation ────────────────────────────────────────────────────────
export const NAV: { id: string; label: string; path: string }[] = [
  { id: 'ledger', label: 'Ledger', path: '/trading' },
  { id: 'positions', label: 'Positions', path: '/trading/positions' },
  { id: 'history', label: 'History', path: '/trading/history' },
  { id: 'principles', label: 'Principles', path: '/trading/principles' },
  { id: 'research', label: 'Research', path: '/trading/research' },
  { id: 'settings', label: 'Settings', path: '/trading/settings' },
]

// ── Charts (svg polyline points per range, 860×120 viewbox) ──────────
export const CHART_PTS: Record<string, string> = {
  '1D': '0,70 86,72 172,66 258,74 344,60 430,64 516,58 602,62 688,54 774,58 860,50',
  '1W': '0,84 123,78 246,86 369,70 492,74 615,60 738,66 860,52',
  '1M': '0,94 62,90 124,96 186,82 248,86 310,70 372,76 434,62 496,67 558,51 620,58 682,42 744,46 806,30 860,24',
  '1Y': '0,108 66,100 132,104 198,90 264,96 330,78 396,84 462,66 528,74 594,54 660,62 726,40 792,46 860,20',
  ALL: '0,116 86,112 172,106 258,108 344,98 430,92 516,94 602,78 688,66 774,44 860,16',
}
export const CHART_DELTA: Record<string, string> = {
  '1D': '+$3,214 · +0.66% today',
  '1W': '+$5,891 · +1.22% this week',
  '1M': '+$14,210 · +3.0% this month',
  '1Y': '+$61,480 · +14.4% past year',
  ALL: '+$187,320 · +62.4% all time',
}
export const RANGES = ['1D', '1W', '1M', '1Y', 'ALL'] as const

// ── Positions (COST varies with approval state — resolved in the store) ─
export interface Position {
  t: string; n: string; q: string; a: string; p: string
  d: string; dc: string; pl: string; plc: string
  fv: string; m: string; mc: string; w: string
  diamond?: boolean; hl?: boolean
}

// ── History / trades ─────────────────────────────────────────────────
export interface Trade {
  id: string; date: string; act: 'BUY' | 'SELL'
  bb: string; bc: string; order: string; trig: string
  auth: string; authC: string; real: string; realC: string; red: boolean
  d1l: string; d1: string; d2l: string; d2: string; lesson: string | null
}
export const HISTORY: Trade[] = [
  { id: 'oxy', date: 'Jul 2', act: 'SELL', bb: C.gain, bc: '#0C110E', order: '60 OXY @ 71.22 · $4,273', trig: 'Weight ceiling crossed', auth: 'Auto', authC: C.muted, real: '+$1,842', realC: C.gain, red: false,
    d1l: 'Entry thesis · Aug 2024', d1: 'Bought at a 38% margin on disciplined capex and best-in-basin Permian acreage; oil above $65 keeps free cash flow covering the dividend twice over.',
    d2l: 'Why it sold · Jul 2', d2: 'The crude rally pushed OXY past its 8% weight ceiling. Trimmed back to 6.5% — a sizing rule, not a view change. Thesis intact.', lesson: null },
  { id: 'axp', date: 'Jun 20', act: 'BUY', bb: C.lightGold, bc: '#0C110E', order: '80 AXP @ 288.10 · $23,048', trig: 'Add · drift below target', auth: 'Auto · under limit', authC: C.muted, real: 'open', realC: C.faint, red: false,
    d1l: 'Thesis', d1: 'Closed-loop network with an affluent cardholder base; fee income compounds without credit risk doing the heavy lifting.',
    d2l: 'Why it was allowed', d2: 'An add to an existing name on drift below target weight. Adds require a 15% margin rather than the 30% new-idea gate — cleared at 19%.', lesson: null },
  { id: 'mco', date: 'Jun 12', act: 'BUY', bb: C.lightGold, bc: '#0C110E', order: '32 MCO @ 462.55 · $14,802', trig: 'Morning screen', auth: 'Auto · under limit', authC: C.muted, real: 'open', realC: C.faint, red: false,
    d1l: 'Entry thesis · Jun 12', d1: 'Ratings duopoly with pricing power; bought at a 32% margin to a then-fair-value of $685.',
    d2l: 'Fair value since', d2: 'Trimmed to $560 after debt-issuance volumes slowed. Still comfortably above cost — no action warranted.', lesson: null },
  { id: 'para', date: 'May 29', act: 'SELL', bb: C.lossBadge, bc: C.textPrimary, order: '200 PARA @ 11.02 · $2,204', trig: 'Thesis broke', auth: 'Auto', authC: C.muted, real: '−$1,306', realC: C.loss, red: true,
    d1l: 'Entry thesis · Aug 2025', d1: 'Streaming consolidation would rationalize content spend; bought at 42% margin to a $19 fair value.',
    d2l: 'What broke', d2: 'Q1 direct-to-consumer losses widened while linear declined faster than modeled. Fair value cut below cost basis → thesis invalid, exit per principle: sell when the thesis breaks.',
    lesson: 'Lesson added to the Latticework (v12): ad-supported streaming economics are outside our circle of competence.' },
  { id: 'ko', date: 'May 6', act: 'BUY', bb: C.lightGold, bc: '#0C110E', order: '300 KO @ 58.90 · $17,670', trig: 'Morning screen', auth: 'Approved by you', authC: C.gold, real: 'open', realC: C.faint, red: false,
    d1l: 'Entry thesis · May 6', d1: 'A century of pricing power and distribution no one can replicate; bought on a broad staples selloff.',
    d2l: 'Why you were asked', d2: 'A brand-new position — your mandate requires approval for first buys regardless of size. You approved within the hour.', lesson: null },
  { id: 'brk', date: 'Apr 14', act: 'BUY', bb: C.lightGold, bc: '#0C110E', order: '45 BRK.B @ 388.20 · $17,469', trig: 'Drift below target', auth: 'Auto · under limit', authC: C.muted, real: 'open', realC: C.faint, red: false,
    d1l: 'Thesis', d1: 'The reference compounder itself — added when drift took the weight 1.5pp under target.',
    d2l: 'Authorization', d2: 'Rebalancing within declared bands requires no approval; logged and auditable like everything else.', lesson: null },
]
export const HIST_FILTERS = ['All', 'Buys', 'Sells', 'Auto-executed', 'Approved by you']

// ── Principles ("The Latticework") ────────────────────────────────────
export interface Principle {
  id: string; sec: string; text: string; meta: string; restate: string; gold?: boolean; paused?: boolean
}
export const P_SECTIONS = ['Temperament', 'Selection', 'Sizing & Selling']

/** core principles — the margin one is parameterised by the current gate */
export const corePrinciples = (mg: number): Principle[] => [
  { id: 'invert', sec: 'Temperament', text: 'Invert, always invert — kill the idea before it kills capital.', meta: 'CORE · MUNGER · invoked 34× this quarter · killed 9 ideas', restate: 'Before any buy or sell, I construct the strongest case for permanent capital loss. If I cannot defeat that case with evidence, I do not act.' },
  { id: 'sit', sec: 'Temperament', text: 'Sit on your ass. Activity is not achievement.', meta: 'CORE · MUNGER · caps trading at 3 orders/week · blocked 2 rebalances in May', restate: 'I cap trading at three orders per week and treat every proposed trade as guilty until proven necessary.' },
  { id: 'margin', sec: 'Selection', text: `Demand a margin of safety of at least ${mg}%.`, meta: `CORE · MUNGER · rejects buys above ${100 - mg}% of fair value`, restate: `I will reject any buy where the price exceeds ${100 - mg}% of my conservative fair-value estimate. Currently this gate removes 8 of the 12 names inside our circle.` },
  { id: 'circle', sec: 'Selection', text: 'Never buy outside the circle of competence.', meta: 'CORE · MUNGER · circle: staples, financials, energy, franchise tech · excluded 202 of 214 today', restate: 'I only act on businesses whose ten-year economics I can explain in four plain sentences. Everything else is excluded, whatever the price.' },
]
export const qmjPrinciple: Principle = { id: 'qmj', sec: 'Selection', gold: true, text: 'Prefer high gross profitability and low leverage; treat cheap junk as outside the circle.', meta: 'FROM RESEARCH · Quality Minus Junk (Asness et al., 2014) · adopted today · backtest: +1.6pp CAGR, −6pp drawdown', restate: 'I add a quality screen ahead of valuation: gross profits over assets in the top half of the circle, net debt under 2× EBITDA.' }
export const sellPrinciple: Principle = { id: 'sell', sec: 'Sizing & Selling', text: 'Sell only when the thesis breaks, a ceiling is crossed, or capital has a clearly better home.', meta: 'CORE · invoked 3× this quarter · last: OXY trim, Jul 2', restate: 'I never sell on price movement alone. Every sell must cite a broken thesis, a band violation, or a superior use of the same capital.' }

// ── Research library ──────────────────────────────────────────────────
export interface LibItem { name: string; status: string; on: boolean; note: string | null }
export const LIBRARY_BASE: LibItem[] = [
  { name: 'Quality Minus Junk (2014)', status: 'DISTILLED', on: true, note: null },
  { name: "Buffett's Alpha (2018)", status: 'ADOPTED', on: true, note: null },
  { name: 'A Five-Factor Model (2015)', status: 'REJECTED', on: false, note: 'factor rotation needs 40×/yr turnover — violates "sit on your ass"' },
  { name: 'Intraday Momentum (2019)', status: 'REJECTED', on: false, note: 'outside circle of competence — we don’t do intraday' },
]

export const NEXT_CHECK: Record<string, string> = { '5m': '11:09 ET · 5 min', '15m': '11:19 ET · 15 min', '30m': '11:30 ET · 26 min', '1h': '12:04 ET · 60 min', Daily: 'tomorrow · 09:30 ET' }
export const CADENCE_LABEL: Record<string, string> = { '5m': 'Every 5 min', '15m': 'Every 15 min', '30m': 'Every 30 min', '1h': 'Every hour', Daily: 'Once daily' }
export const CADENCES = ['5m', '15m', '30m', '1h', 'Daily']
