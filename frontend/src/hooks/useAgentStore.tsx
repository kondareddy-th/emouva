/**
 * Scoped state for the trading side ("The Partner"). A Context provided by
 * TradingLayout. P1: real data from /api/agent/* (mandate, ledger, positions,
 * principles, orders); actions call the API. Research + principle-editing +
 * screen-funnel remain client-side mock until P2/P3 wire their backends.
 */
import { createContext, useContext, useEffect, useMemo, useRef, useState, useCallback, type ReactNode } from 'react'
import { apiFetch } from '../api/client'
import { C, CADENCE_LABEL, type Principle, type Position } from '../data/agentMockData'

type Range = '1D' | '1W' | '1M' | '1Y' | 'ALL'
type Toggles = { newPos: boolean; lossSales: boolean; earnDays: boolean; afterHours: boolean; phone: boolean; queue: boolean; daily: boolean; doubleCheck: boolean }
const TOGGLE_MAP: Record<keyof Toggles, string> = {
  newPos: 'new_pos_approval', lossSales: 'loss_sale_approval', earnDays: 'earnings_days',
  afterHours: 'after_hours', phone: 'phone', queue: 'queue', daily: 'daily_push', doubleCheck: 'double_check',
}

export interface LedgerEntry { id: string; type: string; ts: string; title: string; body: string; meta: Record<string, unknown> | null; order_id: string | null; screen_id: string | null }
interface Mandate {
  source: string; account?: string; approval_threshold_usd: number; per_trade_cap_usd: number
  daily_spend_cap_usd: number; max_position_pct: number; cash_floor_pct: number; sector_cap_pct: number
  max_orders_week: number; cadence: string; paused: boolean; toggles: Record<string, boolean>
  catastrophic_stop_pct: number | null
  next_tick_at: string | null
  mode: string; live_max_notional_usd: number; margin_of_safety_pct: number
  circle_include: string[]; circle_exclude: string[]
  agentic_account: string | null; paper_account: string | null
  live_execution_enabled: boolean; trading_halt: boolean
}
export interface TrackItem { id: string; symbol: string; status: string; last_price: number | null; last_margin_pct: number | null; note: string | null; order_id: string | null }
export interface Falsifier { metric: string; comparator: string; threshold: number; label: string; source?: string }
export interface RedTeamLens { lens: string; attack: string; verdict: string }
export interface Thesis { id: string; symbol: string; kind: string; status: string; thesis: string; falsifiers: Falsifier[]; red_team: RedTeamLens[]; tripped: Falsifier[]; created_at: string }
export interface Memory { long_term: string | null; updated_at?: string; days: { day: string; summary: string }[] }
interface AgentOrder { id: string; symbol: string; side: string; qty: number; est_price: number; est_notional: number; status: string; rationale: string; confidence: number; approval_required: boolean; expires_at: string | null; fill_price: number | null; created_at: string; dry_run?: boolean }
export interface ScreenStage { label: string; count: number; tickers: string[]; exclusions?: string[] }
export interface Screen { id: string; universe_count: number; survivor: string | null; verdict: string; stages: ScreenStage[]; created_at: string }
export interface BacktestResult { trades_reviewed: number; would_block: number; pnl_effect?: string; drawdown_effect?: string; restate?: string; verdict: string; recommend_adopt: boolean }
export interface Distilled { title: string | null; gist: string; inversion?: string; principle: string; section: string }
export interface TcPayload { doc: string; version: string; title: string; text: string; accepted: boolean }

const money = (n: number) => (n >= 1000 ? '$' + Math.round(n / 1000) + 'k' : '$' + n)
const commas = (n: number, d = 0) => n.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })

function mapPositions(raw: { positions?: Record<string, unknown>[]; summary?: Record<string, number> } | null): Position[] {
  const pos = raw?.positions ?? []
  const total = Number(raw?.summary?.total_value) || pos.reduce((s, p) => s + (Number(p.equity) || 0), 0)
  return pos.map((p) => {
    const day = Number(p.percent_change) || 0
    const shares = Number(p.shares) || 0
    const pl = (Number(p.equity) || 0) - shares * (Number(p.avg_cost) || 0)
    const w = total > 0 ? (Number(p.equity) / total) * 100 : 0
    const status = String(p.mos_status || 'unvaluable')
    const margin = p.margin_pct
    const mc = status === 'margin' ? C.gain : status === 'fair' ? C.gold : status === 'rich' ? C.loss : C.muted
    return {
      t: String(p.symbol), n: String(p.symbol), q: shares % 1 === 0 ? String(shares) : shares.toFixed(3),
      a: commas(Number(p.avg_cost) || 0, 2), p: commas(Number(p.current_price) || 0, 2),
      d: (day >= 0 ? '+' : '−') + Math.abs(day).toFixed(1) + '%', dc: day >= 0 ? C.gain : C.loss,
      pl: (pl >= 0 ? '+' : '−') + commas(Math.abs(pl)), plc: pl >= 0 ? C.gain : C.loss,
      fv: p.fair_value ? '$' + commas(Number(p.fair_value), 0) : '—',
      m: (status === 'unvaluable' || margin == null) ? 'n/a' : ((Number(margin) >= 0 ? '+' : '−') + Math.abs(Number(margin)).toFixed(0) + '%'),
      mc, w: w.toFixed(1) + '%',
    }
  })
}

function useAgentState() {
  // ── local UI-only state ──
  const [stripCollapsed, setStripCollapsed] = useState(false)
  const [chartRange, setChartRange] = useState<Range>('1M')
  const [ledgerFilter, setLedgerFilter] = useState('All')
  const [histFilter, setHistFilter] = useState('All')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})
  const [pauseConfirm, setPauseConfirm] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [isMobile, setIsMobile] = useState(typeof window !== 'undefined' ? window.innerWidth < 800 : false)
  // ── principle editing / proposal (proposal carries the real Sonnet-5 backtest) ──
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftText, setDraftText] = useState('')
  const [newPrinciple, setNewPrinciple] = useState('')
  const [proposed, setProposed] = useState<{ text: string; progress: number; done: boolean; result?: BacktestResult } | null>(null)

  // ── server data ──
  const [mandate, setMandate] = useState<Mandate | null>(null)
  const [positionsRaw, setPositionsRaw] = useState<{ positions?: Record<string, unknown>[]; summary?: Record<string, number> } | null>(null)
  const [memory, setMemory] = useState<Memory>({ long_term: null, days: [] })
  const [ledgerEntries, setLedgerEntries] = useState<LedgerEntry[]>([])
  const [principlesRaw, setPrinciplesRaw] = useState<{ id: string; section: string; text: string; meta: string; source: string; paused: boolean }[]>([])
  const [orders, setOrders] = useState<AgentOrder[]>([])
  const [screens, setScreens] = useState<Screen[]>([])
  const [tracks, setTracks] = useState<TrackItem[]>([])
  const [theses, setTheses] = useState<Thesis[]>([])
  const [arming, setArming] = useState<string | null>(null)
  const [tradeHistory, setTradeHistory] = useState<AgentOrder[]>([])
  const [chartSeries, setChartSeries] = useState<{ date: string; value: number }[]>([])
  const [distilled, setDistilled] = useState<Distilled | null>(null)
  const [screening, setScreening] = useState(false)
  const [distilling, setDistilling] = useState(false)
  const [tcModal, setTcModal] = useState<TcPayload | null>(null)

  const toastT = useRef<ReturnType<typeof setTimeout>>()
  const progT = useRef<ReturnType<typeof setInterval>>()
  const putT = useRef<ReturnType<typeof setTimeout>>()
  const writeSeq = useRef(0)   // last-write-wins guard for mandate PUTs (see putMandate)
  const fieldT = useRef<Record<string, ReturnType<typeof setTimeout>>>({})   // per-field debounce (no cross-field cancellation)
  const pop = useCallback((msg: string) => {
    clearTimeout(toastT.current)
    setToast(msg)
    toastT.current = setTimeout(() => setToast(null), 3800)
  }, [])

  const refreshMandate = useCallback(() => apiFetch<Mandate>('/api/agent/mandate').then(setMandate).catch(() => {}), [])
  const refreshMemory = useCallback(() => apiFetch<Memory>('/api/agent/memory').then(setMemory).catch(() => {}), [])
  const refreshLedger = useCallback(() => apiFetch<{ entries: LedgerEntry[] }>('/api/agent/ledger').then((r) => setLedgerEntries(r.entries || [])).catch(() => {}), [])
  const refreshPositions = useCallback(() => apiFetch<{ positions: Record<string, unknown>[] }>('/api/agent/positions').then(setPositionsRaw).catch(() => {}), [])
  const refreshPrinciples = useCallback(() => apiFetch<{ principles: typeof principlesRaw }>('/api/agent/principles').then((r) => setPrinciplesRaw(r.principles || [])).catch(() => {}), [])
  const refreshOrders = useCallback(() => apiFetch<{ orders: AgentOrder[] }>('/api/agent/orders').then((r) => setOrders(r.orders || [])).catch(() => {}), [])
  const refreshScreens = useCallback(() => apiFetch<{ screens: Screen[] }>('/api/agent/screens').then((r) => setScreens(r.screens || [])).catch(() => {}), [])
  const refreshHistory = useCallback(() => apiFetch<{ orders: AgentOrder[] }>('/api/agent/history').then((r) => setTradeHistory(r.orders || [])).catch(() => {}), [])
  const refreshTracks = useCallback(() => apiFetch<{ tracks: TrackItem[] }>('/api/agent/track').then((r) => setTracks(r.tracks || [])).catch(() => {}), [])
  const refreshTheses = useCallback(() => apiFetch<{ theses: Thesis[] }>('/api/agent/theses').then((r) => setTheses(r.theses || [])).catch(() => {}), [])

  useEffect(() => {
    refreshMandate(); refreshLedger(); refreshPositions(); refreshPrinciples(); refreshOrders(); refreshScreens(); refreshHistory(); refreshTracks(); refreshTheses(); refreshMemory()
    const onR = () => setIsMobile(window.innerWidth < 800)
    window.addEventListener('resize', onR)
    return () => { window.removeEventListener('resize', onR); clearInterval(progT.current); clearTimeout(toastT.current); clearTimeout(putT.current) }
  }, [refreshMandate, refreshLedger, refreshPositions, refreshPrinciples, refreshOrders, refreshScreens, refreshHistory, refreshTracks, refreshTheses, refreshMemory])

  // Net-liquidity chart for the active account (real; paper has no snapshots → flat headline).
  const RANGE_DAYS: Record<Range, number> = { '1D': 1, '1W': 7, '1M': 30, '1Y': 365, 'ALL': 999 }
  useEffect(() => {
    const acct = mandate?.mode === 'paper' ? mandate?.paper_account : (mandate?.agentic_account || mandate?.account)
    if (!acct) { setChartSeries([]); return }
    apiFetch<{ date: string; value: number }[]>(`/api/portfolio/history?days=${RANGE_DAYS[chartRange]}&account=${encodeURIComponent(acct)}`)
      .then((r) => setChartSeries(Array.isArray(r) ? r : []))
      .catch(() => setChartSeries([]))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chartRange, mandate?.mode, mandate?.paper_account, mandate?.agentic_account, mandate?.account])

  // The PUT already returns the full updated mandate, so apply THAT directly — no
  // extra refetch GET. A write sequence guarantees last-write-wins: if the user
  // cycles a sector quickly, an earlier PUT's (possibly reordered) response can't
  // clobber a newer optimistic state. Fixes the circle-of-competence UI revert.
  const putMandate = useCallback((body: Record<string, unknown>) => {
    const seq = ++writeSeq.current
    apiFetch<Mandate>('/api/agent/mandate', { method: 'PUT', body: JSON.stringify(body) })
      .then((res) => { if (seq === writeSeq.current && res) setMandate(res) })
      .catch(() => { refreshMandate() })   // on failure, resync UI to the server truth
  }, [refreshMandate])

  // ── derived: mandate ──
  const threshold = mandate?.approval_threshold_usd ?? 25000
  const cadence = mandate?.cadence ?? '1h'
  const paused = mandate?.paused ?? false
  const bt = mandate?.toggles ?? {}
  const toggles: Toggles = {
    newPos: bt.new_pos_approval ?? true, lossSales: bt.loss_sale_approval ?? true, earnDays: bt.earnings_days ?? true,
    afterHours: bt.after_hours ?? false, phone: bt.phone ?? true, queue: bt.queue ?? true, daily: bt.daily_push ?? false,
    doubleCheck: bt.double_check ?? false,
  }
  const thresholdFmt = '$' + threshold.toLocaleString('en-US')
  const thresholdShort = money(threshold)
  const cadenceLabel = CADENCE_LABEL[cadence] ?? cadence
  // ── execution target (paper↔live toggle) + live cap + hard limits ──
  const mode = mandate?.mode ?? 'paper'
  const liveMaxNotional = mandate?.live_max_notional_usd ?? 100
  const marginOfSafety = mandate?.margin_of_safety_pct ?? 30
  const circleInclude = mandate?.circle_include ?? []
  const circleExclude = mandate?.circle_exclude ?? []
  const realizedPnlN = Number(positionsRaw?.summary?.realized_pnl) || 0
  const paperAccount = mandate?.paper_account ?? null
  const agenticAccount = mandate?.agentic_account ?? mandate?.account ?? null
  const liveEnabled = mandate?.live_execution_enabled ?? false
  const tradingHalt = mandate?.trading_halt ?? false
  const limits = {
    maxPositionPct: ((mandate?.max_position_pct ?? 0.09) * 100).toFixed(1) + '%',
    cashFloorPct: Math.round((mandate?.cash_floor_pct ?? 0.10) * 100) + '%',
    maxOrdersWeek: String(mandate?.max_orders_week ?? 3),
    dailyCap: '$' + commas(mandate?.daily_spend_cap_usd ?? 50000),
    sectorCapPct: Math.round((mandate?.sector_cap_pct ?? 0.30) * 100) + '%',
  }
  // raw numeric hard limits for the editable inputs (fractions for the % fields)
  const hardLimits = {
    maxPositionPct: mandate?.max_position_pct ?? 0.09,
    cashFloorPct: mandate?.cash_floor_pct ?? 0.10,
    sectorCapPct: mandate?.sector_cap_pct ?? 0.30,
    maxOrdersWeek: mandate?.max_orders_week ?? 3,
    dailyCap: mandate?.daily_spend_cap_usd ?? 50000,
    catastrophicStopPct: mandate?.catastrophic_stop_pct ?? 0.30,   // null → platform default (30%)
  }
  const nextCheckText = paused ? 'paused — no checks scheduled'
    : mandate?.next_tick_at ? 'Next check ' + new Date(mandate.next_tick_at).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    : 'Next check —'

  // ── derived: approval (from real orders) ──
  const pendingOrder = orders.find((o) => o.status === 'pending_approval') || null
  const apprPending = !!pendingOrder
  const apprApproved = !apprPending && orders.some((o) => o.status === 'approved')
  const apprDeclined = !apprPending && orders.some((o) => o.status === 'declined')

  // ── derived: positions ──
  const positions = useMemo(() => mapPositions(positionsRaw), [positionsRaw])
  const cash = useMemo(() => {
    const total = Number(positionsRaw?.summary?.total_value) || 0
    const invested = (positionsRaw?.positions ?? []).reduce((s, p) => s + (Number(p.equity) || 0), 0)
    const c = Math.max(0, total - invested)
    const dayChange = (positionsRaw?.positions ?? []).reduce((s, p) => s + (Number(p.equity_change) || 0), 0)
    const dayPct = total > 0 ? (dayChange / total) * 100 : 0
    const openPnlN = (positionsRaw?.positions ?? []).reduce((s, p) => s + ((Number(p.equity) || 0) - (Number(p.shares) || 0) * (Number(p.avg_cost) || 0)), 0)
    // Real risk temperature: how deployed the book is + how concentrated (largest weight).
    const maxEquity = (positionsRaw?.positions ?? []).reduce((m, p) => Math.max(m, Number(p.equity) || 0), 0)
    const investedFrac = total > 0 ? invested / total : 0
    const maxWeight = total > 0 ? maxEquity / total : 0
    const rLevel = Math.min(1, investedFrac * 0.7 + maxWeight * 1.2)
    const riskTemp = {
      level: rLevel,
      label: total <= 0 ? 'Idle' : rLevel < 0.4 ? 'Cool' : rLevel < 0.7 ? 'Warm' : 'Hot',
      color: total <= 0 ? C.muted : rLevel < 0.4 ? C.gain : rLevel < 0.7 ? C.gold : C.loss,
    }
    return {
      openPnl: (openPnlN >= 0 ? '+' : '−') + '$' + commas(Math.abs(openPnlN)),
      openPnlColor: openPnlN >= 0 ? C.gain : C.loss,
      cashRow: '$' + commas(c) + ' · ' + (total > 0 ? (c / total * 100).toFixed(1) : '0') + '%',
      cashAlloc: (total > 0 ? Math.round(c / total * 100) : 0) + '%',
      netLiq: '$' + commas(total, 2),
      cashPct: (total > 0 ? (c / total * 100).toFixed(1) : '0') + '%',
      dayPnl: (dayChange >= 0 ? '+' : '−') + '$' + commas(Math.abs(dayChange)),
      dayPct: (dayChange >= 0 ? '+' : '') + dayPct.toFixed(2) + '%',
      dayPnlColor: dayChange >= 0 ? C.gain : C.loss,
      hasAccount: total > 0, riskTemp,
    }
  }, [positionsRaw])

  // ── derived: net-liquidity chart (real series → 860×120 polyline) ──
  const chart = useMemo(() => {
    const s = chartSeries
    if (s.length < 2) return { points: '', delta: '', has: false }
    const vals = s.map((p) => p.value)
    const min = Math.min(...vals), max = Math.max(...vals), range = (max - min) || 1
    const W = 860, H = 120, pad = 10
    const points = s.map((p, i) => {
      const x = (i / (s.length - 1)) * W
      const y = H - pad - ((p.value - min) / range) * (H - 2 * pad)
      return `${x.toFixed(0)},${y.toFixed(0)}`
    }).join(' ')
    const chg = vals[vals.length - 1] - vals[0]
    const pct = vals[0] ? (chg / vals[0]) * 100 : 0
    const span = ({ '1D': 'today', '1W': 'this week', '1M': 'this month', '1Y': 'past year', 'ALL': 'all time' } as Record<Range, string>)[chartRange]
    const delta = `${chg >= 0 ? '+' : '−'}$${Math.abs(Math.round(chg)).toLocaleString()} · ${chg >= 0 ? '+' : ''}${pct.toFixed(2)}% ${span}`
    return { points, delta, has: true, up: chg >= 0 }
  }, [chartSeries, chartRange])

  // ── derived: trade history (real placed/filled orders → display rows) ──
  const trades = useMemo(() => tradeHistory.map((o) => {
    const px = o.fill_price || o.est_price || 0
    const notional = (o.fill_price ? o.fill_price * o.qty : o.est_notional) || 0
    return {
      id: o.id, date: new Date(o.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      act: o.side.toUpperCase() as 'BUY' | 'SELL',
      order: `${o.qty % 1 === 0 ? o.qty : o.qty.toFixed(3)} ${o.symbol}` + (px ? ` @ ${px.toFixed(2)}` : '') + (notional ? ` · $${commas(notional)}` : ''),
      auth: o.approval_required ? 'Approved by you' : 'Auto',
      status: o.status, rationale: o.rationale || '', confidence: o.confidence,
    }
  }), [tradeHistory])

  // ── derived: principles (all real, from /api/agent/principles) ──
  const derived = useMemo(() => {
    const allP: Principle[] = principlesRaw.map((p) => ({
      id: p.id, sec: p.section, text: p.text, meta: p.meta, restate: '',
      gold: p.source === 'research', paused: p.paused,
    }))
    return {
      allP, principleCount: allP.length, shownCount: allP.filter((p) => !p.paused).length,
      railPrinciples: allP.filter((p) => !p.paused).slice(0, 3),
      lastEdited: 'the Latticework',
    }
  }, [principlesRaw])

  // ── actions ──
  const patchExpanded = (id: string) => setExpanded((e) => ({ ...e, [id]: !e[id] }))
  const applyMode = (next: string, prev: string) => {
    setMandate((m) => (m ? { ...m, mode: next } : m))
    apiFetch('/api/agent/mode', { method: 'POST', body: JSON.stringify({ mode: next }) })
      .then(() => { refreshPositions(); refreshLedger(); refreshOrders(); pop(next === 'live' ? 'Now trading the live Robinhood agentic account.' : 'Now trading paper money.') })
      .catch((e) => { setMandate((m) => (m ? { ...m, mode: prev } : m)); pop(String(e?.message || 'Could not switch mode.').replace(/^\d+:\s*/, '')) })
  }
  const actions = {
    toggleStrip: () => setStripCollapsed((v) => !v),
    setChartRange, setLedgerFilter, setHistFilter,
    toggleExpanded: patchExpanded,
    // approval → real order
    approve: () => {
      if (!pendingOrder) return
      apiFetch(`/api/agent/orders/${pendingOrder.id}/approve`, { method: 'POST' })
        .then(() => { refreshLedger(); refreshOrders(); refreshPositions() }).catch(() => {})
      pop('Approved. (Placement begins in P2 — dry run for now.)')
    },
    decline: () => {
      if (!pendingOrder) return
      apiFetch(`/api/agent/orders/${pendingOrder.id}/decline`, { method: 'POST' })
        .then(() => { refreshLedger(); refreshOrders() }).catch(() => {})
      pop('Declined. The Partner logged your veto — no questions asked.')
    },
    runNow: () => {
      pop('Running a review…')
      apiFetch<{ note?: string; skipped?: string }>('/api/agent/tick/run', { method: 'POST' })
        .then((r) => {
          refreshLedger(); refreshOrders(); refreshPositions(); refreshMandate(); refreshMemory()
          if (r?.note) pop(r.note)
          else if (r?.skipped === 'idle') pop('Reviewed — nothing to do (no positions and no buying power).')
        }).catch(() => {})
    },
    // mandate
    setThreshold: (v: number) => {
      setMandate((m) => (m ? { ...m, approval_threshold_usd: v } : m))
      clearTimeout(putT.current)
      putT.current = setTimeout(() => putMandate({ approval_threshold_usd: v }), 400)
    },
    setCadence: (c: string) => { setMandate((m) => (m ? { ...m, cadence: c } : m)); putMandate({ cadence: c }) },
    // ── execution target: paper↔live. Switching to live first requires the
    // live-trading T&C (shown as a modal on first enable). Optimistic otherwise.
    setMode: (next: string) => {
      const prev = mandate?.mode ?? 'paper'
      if (next === prev) return
      if (next === 'live') {
        apiFetch<TcPayload>('/api/agent/agreements/live_trading')
          .then((tc) => { if (tc.accepted) applyMode('live', prev); else setTcModal(tc) })
          .catch(() => applyMode('live', prev))   // fall back to the server-side gate
        return
      }
      applyMode(next, prev)
    },
    acceptTc: () => {
      const tc = tcModal
      if (!tc) return
      apiFetch('/api/agent/agreements', { method: 'POST', body: JSON.stringify({ doc: tc.doc, version: tc.version, status: 'accepted' }) })
        .then(() => { setTcModal(null); applyMode('live', mandate?.mode ?? 'paper') })
        .catch(() => pop('Could not record your acceptance.'))
    },
    declineTc: () => {
      const tc = tcModal
      if (tc) apiFetch('/api/agent/agreements', { method: 'POST', body: JSON.stringify({ doc: tc.doc, version: tc.version, status: 'rejected' }) }).catch(() => {})
      setTcModal(null); pop('Left in paper mode.')
    },
    setLiveMaxNotional: (v: number) => {
      setMandate((m) => (m ? { ...m, live_max_notional_usd: v } : m))
      clearTimeout(putT.current)
      putT.current = setTimeout(() => putMandate({ live_max_notional_usd: v }), 400)
    },
    setMarginOfSafety: (v: number) => {
      setMandate((m) => (m ? { ...m, margin_of_safety_pct: v } : m))
      clearTimeout(putT.current)
      putT.current = setTimeout(() => putMandate({ margin_of_safety_pct: v }), 400)
    },
    // ── editable hard limits (per-field debounce so editing one never drops another) ──
    setHardLimit: (field: string, value: number) => {
      setMandate((m) => (m ? { ...m, [field]: value } : m))
      clearTimeout(fieldT.current[field])
      fieldT.current[field] = setTimeout(() => putMandate({ [field]: value }), 400)
    },
    setCircle: (include: string[], exclude: string[]) => {
      setMandate((m) => (m ? { ...m, circle_include: include, circle_exclude: exclude } : m))
      putMandate({ circle_include: include, circle_exclude: exclude })
    },
    // ── track list (watch-only, ≤3) ──
    addTrack: (symbol: string) => {
      const s = symbol.trim().toUpperCase()
      if (!s) return
      apiFetch('/api/agent/track', { method: 'POST', body: JSON.stringify({ symbol: s }) })
        .then(() => { refreshTracks(); pop(`Watching ${s}. Checked daily — I'll bring it to you if a margin opens.`) })
        .catch((e) => pop(String(e?.message || 'Could not add.').replace(/^\d+:\s*/, '')))
    },
    removeTrack: (symbol: string) => {
      apiFetch(`/api/agent/track/${encodeURIComponent(symbol)}`, { method: 'DELETE' }).then(refreshTracks).catch(() => {})
    },
    checkTrack: () => {
      pop('Re-valuing your watch list…')
      apiFetch('/api/agent/track/check', { method: 'POST' }).then(() => { refreshTracks(); refreshLedger(); refreshOrders() }).catch(() => {})
    },
    // ── living theses ──
    armThesis: (symbol: string) => {
      setArming(symbol); pop(`Writing ${symbol}'s thesis + running the red-team…`)
      apiFetch('/api/agent/theses/arm', { method: 'POST', body: JSON.stringify({ symbol }) })
        .then(() => refreshTheses()).catch(() => pop('Could not write the thesis.')).finally(() => setArming(null))
    },
    sweepTheses: () => {
      pop('Checking every thesis for a tripped trigger…')
      apiFetch('/api/agent/theses/sweep', { method: 'POST' }).then(() => { refreshTheses(); refreshLedger(); refreshOrders() }).catch(() => {})
    },
    setToggle: (k: keyof Toggles) => {
      const next = { ...bt, [TOGGLE_MAP[k]]: !toggles[k] }
      setMandate((m) => (m ? { ...m, toggles: next } : m))
      putMandate({ toggles: next })
    },
    askPause: () => setPauseConfirm(true),
    cancelPause: () => setPauseConfirm(false),
    confirmPause: () => {
      setPauseConfirm(false)
      apiFetch('/api/agent/pause', { method: 'POST' }).then(refreshMandate).catch(() => {})
      pop('The Partner is paused — watching, not trading.')
    },
    resume: () => {
      setPauseConfirm(false)
      apiFetch('/api/agent/resume', { method: 'POST' }).then(refreshMandate).catch(() => {})
      pop('Resumed. It will keep writing to the Ledger.')
    },
    // ── principles: real CRUD + Sonnet-5 backtest ──
    edit: (id: string, text: string) => { setEditingId(id); setDraftText(text) },
    setDraft: setDraftText,
    cancelEdit: () => setEditingId(null),
    saveEdit: () => {
      const id = editingId, txt = draftText.trim()
      setEditingId(null)
      if (!id || !txt) return
      apiFetch(`/api/agent/principles/${id}`, { method: 'PUT', body: JSON.stringify({ text: txt }) })
        .then(() => { refreshPrinciples(); pop('Saved — the Partner now reasons against it.') }).catch(() => pop('Could not save.'))
    },
    pausePrinciple: (id: string) => {
      apiFetch<{ paused: boolean }>(`/api/agent/principles/${id}/toggle`, { method: 'POST' })
        .then((r) => { refreshPrinciples(); pop(r.paused ? 'Paused. Not consulted until resumed.' : 'Resumed — back in the Latticework.') })
        .catch(() => pop('Could not update.'))
    },
    deletePrinciple: (id: string) => {
      apiFetch(`/api/agent/principles/${id}`, { method: 'DELETE' }).then(() => { refreshPrinciples(); pop('Removed from the Latticework.') }).catch(() => {})
    },
    setNewPrinciple,
    propose: async () => {
      const txt = newPrinciple.trim()
      if (!txt) { pop('Write the principle in your own words first.'); return }
      setProposed({ text: txt, progress: 40, done: false })
      pop('Backtesting against your recent trades…')
      try {
        const r = await apiFetch<BacktestResult>('/api/agent/principles/backtest', { method: 'POST', body: JSON.stringify({ text: txt, section: 'Selection' }) })
        setProposed({ text: txt, progress: 100, done: true, result: r }); setNewPrinciple('')
      } catch { setProposed({ text: txt, progress: 100, done: true, result: { trades_reviewed: 0, would_block: 0, verdict: 'Backtest unavailable.', recommend_adopt: true } as BacktestResult }) }
    },
    adoptProposed: () => {
      const pr = proposed
      if (!pr) return
      apiFetch('/api/agent/principles', { method: 'POST', body: JSON.stringify({ text: pr.text, section: 'Selection' }) })
        .then(() => refreshPrinciples()).catch(() => {})
      setProposed(null); pop('Adopted into the Latticework.')
    },
    discardProposed: () => setProposed(null),
    // ── research: real distillation + morning screen ──
    adoptQmj: () => {
      const p = distilled
      if (p?.principle) apiFetch('/api/agent/principles', { method: 'POST', body: JSON.stringify({ text: p.principle, section: p.section }) }).then(() => refreshPrinciples()).catch(() => {})
      setDistilled(null); pop('Added to the Latticework.')
    },
    reviseQmj: () => { if (distilled?.principle) { setNewPrinciple(distilled.principle) } pop('Copied to the proposal box for revision.') },
    discardQmj: () => { setDistilled(null); pop('Kept in the library, not adopted.') },
    distill: async (source: string) => {
      if (!source.trim()) { pop('Paste a link or some text first.'); return }
      setDistilling(true); pop('Distilling with Sonnet 5…')
      try { const d = await apiFetch<Distilled>('/api/agent/research/distill', { method: 'POST', body: JSON.stringify({ source }) }); setDistilled(d); pop('Distilled. Review the proposal.') }
      catch { pop('Distillation failed.') } finally { setDistilling(false) }
    },
    runScreen: async () => {
      setScreening(true); pop('Running the morning screen…')
      try { await apiFetch('/api/agent/screens/run', { method: 'POST' }); await refreshScreens(); pop('Screen complete.') }
      catch { pop('Screen failed.') } finally { setScreening(false) }
    },
    dropHint: () => pop('Paste a link or text and I\'ll distill it.'),
    pop,
  }

  return {
    // local ui
    stripCollapsed, chartRange, ledgerFilter, histFilter, expanded, editingId, draftText, newPrinciple,
    proposed, pauseConfirm, toast, isMobile,
    // mandate-derived
    threshold, cadence, paused, toggles, thresholdFmt, thresholdShort, cadenceLabel, nextCheckText,
    mode, liveMaxNotional, marginOfSafety, circleInclude, circleExclude, paperAccount, agenticAccount, liveEnabled, tradingHalt, limits, hardLimits, memory,
    tracks, trackMax: 3, theses, arming,
    // approval
    apprPending, apprApproved, apprDeclined, pendingOrder,
    // data
    positions, cashRow: cash.cashRow, cashAlloc: cash.cashAlloc,
    netLiq: cash.netLiq, cashPct: cash.cashPct, dayPnl: cash.dayPnl, dayPct: cash.dayPct, riskTemp: cash.riskTemp,
    dayPnlColor: cash.dayPnlColor, openPnl: cash.openPnl, openPnlColor: cash.openPnlColor,
    hasAccount: cash.hasAccount, ledgerEntries,
    // research (real)
    screens, latestScreen: screens[0] ?? null, distilled, screening, distilling,
    // chart + trade history (real)
    chart, trades, realizedPnl: realizedPnlN,
    // live-trading T&C modal
    tcModal,
    ...derived, ...actions,
  }
}

type AgentCtx = ReturnType<typeof useAgentState>
const Ctx = createContext<AgentCtx | null>(null)

export function AgentProvider({ children }: { children: ReactNode }) {
  return <Ctx.Provider value={useAgentState()}>{children}</Ctx.Provider>
}

export function useAgent(): AgentCtx {
  const v = useContext(Ctx)
  if (!v) throw new Error('useAgent must be used within AgentProvider')
  return v
}
