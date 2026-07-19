/**
 * Central portfolio state store — module-level singleton.
 * Portfolio data only refreshes on explicit user sync (no auto-fetch).
 * Stock prices update every 60s via yfinance (lightweight, no Robinhood needed).
 * Persists to localStorage so data survives page navigation + browser refresh.
 */

import { useSyncExternalStore } from 'react'
import { apiFetch } from '../api/client'
import {
  type Position,
  type WatchlistItem,
  type PortfolioHistory,
  type RiskData,
  EMPTY_RISK_DATA,
} from '../data/mockData'

// ── Types ──────────────────────────────────────────────────

export interface PortfolioSummary {
  totalValue: number
  dailyChange: number
  dailyChangePct: number
  totalGain: number
  totalGainPct: number
  buyingPower: number
  riskScore: number
  source: string
}

export interface Quote {
  symbol: string
  price: number
  previous_close: number
  change_pct: number
}

export type QuoteMap = Record<string, Quote>

interface PortfolioStoreState {
  // Synced from Robinhood (manual refresh only)
  summary: PortfolioSummary
  positions: Position[]
  watchlist: WatchlistItem[]
  riskData: RiskData
  history: Record<number, PortfolioHistory[]>
  lastSyncedAt: number | null
  isSyncing: boolean
  source: 'robinhood' | 'disconnected'

  // yfinance price layer (60s auto-refresh)
  quotes: QuoteMap
  lastQuoteUpdate: number | null
}

const EMPTY_SUMMARY: PortfolioSummary = {
  totalValue: 0, dailyChange: 0, dailyChangePct: 0,
  totalGain: 0, totalGainPct: 0, buyingPower: 0, riskScore: 0,
  source: 'disconnected',
}

const STORAGE_KEY = 'emouva_portfolio_sync'
const QUOTE_INTERVAL = 60_000 // 60 seconds

// ── Persistence ────────────────────────────────────────────

interface PersistedData {
  summary: PortfolioSummary
  positions: Position[]
  watchlist: WatchlistItem[]
  riskData: RiskData
  lastSyncedAt: number | null
  source: 'robinhood' | 'disconnected'
}

function loadPersisted(): PersistedData | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw)
  } catch { return null }
}

function savePersisted(data: PersistedData): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
  } catch { /* localStorage full */ }
}

// ── Initial state ──────────────────────────────────────────

const persisted = loadPersisted()

let state: PortfolioStoreState = {
  summary: persisted?.summary ?? EMPTY_SUMMARY,
  positions: persisted?.positions ?? [],
  watchlist: persisted?.watchlist ?? [],
  riskData: persisted?.riskData ?? EMPTY_RISK_DATA,
  history: {},
  lastSyncedAt: persisted?.lastSyncedAt ?? null,
  isSyncing: false,
  source: persisted?.source ?? 'disconnected',
  quotes: {},
  lastQuoteUpdate: null,
}

// ── Reactive plumbing ──────────────────────────────────────

const listeners = new Set<() => void>()
function emit() { listeners.forEach((fn) => fn()) }
function setState(updates: Partial<PortfolioStoreState>) {
  state = { ...state, ...updates }
  emit()
}

// ── Transform helpers (snake_case → camelCase) ─────────────

function transformPosition(p: Record<string, unknown>): Position {
  return {
    symbol: p.symbol as string,
    name: p.name as string,
    shares: p.shares as number,
    avgCost: p.avg_cost as number,
    currentPrice: p.current_price as number,
    previousClose: p.previous_close as number,
    sector: (p.sector as string) || 'Unknown',
    conviction: (p.conviction as number) || 3,
    thesisStatus: (p.thesis_status as 'intact' | 'watch' | 'breaking') || 'intact',
    sparkline: (p.sparkline as number[]) || [],
  }
}

function transformWatchlist(w: Record<string, unknown>): WatchlistItem {
  return {
    symbol: w.symbol as string,
    name: w.name as string,
    price: w.price as number,
    change: (w.price as number) * ((w.change_pct as number) / 100),
    changePct: w.change_pct as number,
    aiScore: 50,
    sparkline: (w.sparkline as number[]) || [],
  }
}

function transformSummary(res: Record<string, unknown>): PortfolioSummary {
  return {
    totalValue: res.total_value as number,
    dailyChange: res.daily_change as number,
    dailyChangePct: res.daily_change_pct as number,
    totalGain: res.total_gain as number,
    totalGainPct: res.total_gain_pct as number,
    buyingPower: res.buying_power as number,
    riskScore: res.risk_score as number,
    source: (res.source as string) || 'disconnected',
  }
}

function transformDimension(d: Record<string, unknown> | undefined): RiskData['concentrationRisk']['dimensions']['sector'] {
  if (!d) return { breakdown: [], hhi: 0, topHoldingPct: 0, rating: 'green' }
  return {
    breakdown: ((d.breakdown as Array<Record<string, unknown>>) ?? []).map((b) => ({
      label: b.label as string, value: b.value as number, weight: b.weight as number,
    })),
    hhi: (d.hhi as number) ?? 0,
    topHoldingPct: (d.top_holding_pct as number) ?? 0,
    rating: (d.rating as 'green' | 'yellow' | 'red') ?? 'green',
  }
}

function transformRisk(res: Record<string, unknown>): RiskData {
  const cr = res.concentration_risk as Record<string, unknown> | undefined
  const dims = cr?.dimensions as Record<string, Record<string, unknown>> | undefined
  const conc = res.concentration as Record<string, unknown> | undefined

  return {
    score: (res.score as number) ?? 0,
    dailyVaR95: (res.daily_var_95 as number) ?? 0,
    monthlyCVaR95: (res.monthly_cvar_95 as number) ?? 0,
    riskBudgetUsed: (res.risk_budget_used as number) ?? 0,
    portfolioVolatility: (res.portfolio_volatility as number) ?? 0,
    maxDrawdown: (res.max_drawdown as number) ?? 0,
    drawdownSeries: (res.drawdown_series as RiskData['drawdownSeries']) ?? [],
    sectorWeights: ((res.sector_weights as Array<Record<string, unknown>>) ?? []).map((s) => ({
      sector: s.sector as string, value: s.value as number, weight: s.weight as number,
    })),
    concentration: conc
      ? { hhi: (conc.hhi as number) ?? 0, top5Pct: (conc.top5_pct as number) ?? 0 }
      : { hhi: 0, top5Pct: 0 },
    factors: ((res.factors as Array<Record<string, unknown>>) ?? []).map((f) => ({
      name: f.name as string, exposure: f.exposure as number, status: (f.status as 'ok' | 'high' | 'low') ?? 'ok', detail: f.detail as string | undefined,
    })),
    stressTests: ((res.stress_tests as Array<Record<string, unknown>>) ?? []).map((t) => ({
      scenario: t.scenario as string, impact: t.impact as number,
    })),
    correlationAlerts: ((res.correlation_alerts as Array<Record<string, unknown>>) ?? []).map((a) => ({
      pair: a.pair as [string, string], correlation: a.correlation as number, method: a.method as 'pearson' | 'spearman' | undefined,
    })),
    concentrationRisk: cr ? {
      score: (cr.score as number) ?? 0,
      rating: (cr.rating as 'green' | 'yellow' | 'red') ?? 'green',
      dimensions: {
        sector: transformDimension(dims?.sector),
        market_cap: transformDimension(dims?.market_cap),
        geography: transformDimension(dims?.geography),
      },
    } : EMPTY_RISK_DATA.concentrationRisk,
  }
}

// ── Selected Robinhood account (account switcher) ──────────
const ACCOUNT_KEY = 'emouva_rh_account'
export function getSelectedAccount(): string | null {
  return localStorage.getItem(ACCOUNT_KEY)
}
export function setSelectedAccount(account: string | null): void {
  if (account) localStorage.setItem(ACCOUNT_KEY, account)
  else localStorage.removeItem(ACCOUNT_KEY)
  setState({ history: {}, riskData: EMPTY_RISK_DATA }) // per-account; clear so they refetch
}

// ── Sync (manual, user-triggered) ──────────────────────────

export async function syncPortfolio(): Promise<void> {
  if (state.isSyncing) return
  setState({ isSyncing: true })

  try {
    // Selected account from the switcher (default account if unset).
    const acct = getSelectedAccount()
    const q = acct ? `?account=${encodeURIComponent(acct)}` : ''
    // Core portfolio data in parallel. Risk is fetched separately (heavy), and
    // the watchlist is our own (useWatchlistStore) — not Robinhood's.
    const [summaryRes, positionsRes] = await Promise.all([
      apiFetch<Record<string, unknown>>(`/api/portfolio/summary${q}`),
      apiFetch<{ positions: Record<string, unknown>[]; source: string }>(`/api/portfolio/positions${q}`),
    ])

    const source: 'robinhood' | 'disconnected' = positionsRes.source === 'robinhood' ? 'robinhood' : 'disconnected'
    const summary = transformSummary(summaryRes)
    const positions = positionsRes.positions?.map(transformPosition) ?? []

    setState({
      summary, positions,
      source,
      lastSyncedAt: Date.now(),
      isSyncing: false,
    })

    // Persist to localStorage
    savePersisted({ summary, positions, watchlist: state.watchlist, riskData: state.riskData, lastSyncedAt: Date.now(), source })

    // Kick off first yfinance quote refresh immediately
    refreshQuotes()
    // Risk in the background — non-blocking.
    if (source === 'robinhood') fetchRiskData().catch(() => {})
  } catch (err) {
    setState({ isSyncing: false })
    throw err
  }
}

let _riskInflight: { key: string; promise: Promise<void> } | null = null

export async function fetchRiskData(): Promise<void> {
  const acct = getSelectedAccount() ?? 'default'
  // De-dupe: the dashboard's background prefetch and the Risk Center mount both
  // call this — share one in-flight request per account instead of running the
  // (heavy) risk compute twice.
  if (_riskInflight && _riskInflight.key === acct) return _riskInflight.promise
  const promise = (async () => {
    try {
      const q = acct !== 'default' ? `?account=${encodeURIComponent(acct)}` : ''
      const riskRes = await apiFetch<Record<string, unknown>>(`/api/portfolio/risk${q}`)
      setState({ riskData: transformRisk(riskRes) })
    } catch {
      /* keep existing riskData */
    } finally {
      _riskInflight = null
    }
  })()
  _riskInflight = { key: acct, promise }
  return promise
}

// ── History (fetched on demand, not persisted) ─────────────

export async function fetchHistory(days: number): Promise<PortfolioHistory[]> {
  // Return cached even if empty (undefined = never fetched) to avoid refetch loops.
  if (state.history[days] !== undefined) return state.history[days]

  try {
    const acct = getSelectedAccount()
    const q = acct ? `&account=${encodeURIComponent(acct)}` : ''
    const data = await apiFetch<PortfolioHistory[]>(`/api/portfolio/history?days=${days}${q}`)
    const newHistory = { ...state.history, [days]: data || [] }
    setState({ history: newHistory })
    return data || []
  } catch {
    return []
  }
}

// ── yfinance Quotes (60s auto-refresh) ─────────────────────

async function refreshQuotes(): Promise<void> {
  const symbols = [
    ...state.positions.map((p) => p.symbol),
    ...state.watchlist.map((w) => w.symbol),
  ]
  const unique = [...new Set(symbols)]
  if (unique.length === 0) return

  try {
    const res = await apiFetch<{ quotes: Quote[]; source: string }>(
      `/api/portfolio/quotes?symbols=${unique.join(',')}`
    )
    if (res.quotes?.length) {
      const map: QuoteMap = {}
      for (const q of res.quotes) {
        map[q.symbol] = q
      }
      setState({ quotes: map, lastQuoteUpdate: Date.now() })
    }
  } catch {
    // Silently fail — prices stay stale
  }
}

// Start 60s quote polling when positions exist
let quoteInterval: ReturnType<typeof setInterval> | null = null

function startQuotePolling() {
  if (quoteInterval) return
  if (state.positions.length === 0) return
  refreshQuotes()
  quoteInterval = setInterval(refreshQuotes, QUOTE_INTERVAL)
}

function stopQuotePolling() {
  if (quoteInterval) {
    clearInterval(quoteInterval)
    quoteInterval = null
  }
}

// Auto-start polling if we loaded persisted positions
if (state.positions.length > 0) {
  startQuotePolling()
}

// ── Auto-init: check if Robinhood is connected on startup ──
// If we have no persisted data OR source is 'disconnected', check the backend.
// If Robinhood is actually connected (session pickle exists), auto-sync.
let _hasCheckedAuth = false

async function _checkAuthAndSync(): Promise<void> {
  if (_hasCheckedAuth) return

  // If we already have fresh persisted data, skip the check
  if (state.source === 'robinhood' && state.positions.length > 0) {
    _hasCheckedAuth = true
    return
  }

  try {
    const { getAuthToken } = await import('./useAuth')
    const token = getAuthToken()
    if (!token) return // Not logged in yet — leave flag unset so we retry after login

    // User is logged in — mark checked and look up Robinhood status
    _hasCheckedAuth = true

    const res = await fetch('/api/auth/status', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) return
    const data = await res.json()

    if (data.connected && data.source === 'robinhood') {
      // Robinhood is connected on the server but store is empty — auto-sync
      syncPortfolio().catch(() => {})
    } else {
      // Backend says disconnected — reflect that in store + clear stale data
      setState({
        source: 'disconnected',
        positions: [],
        summary: EMPTY_SUMMARY,
        watchlist: [],
        riskData: EMPTY_RISK_DATA,
      })
    }
  } catch {
    // Non-critical — user can always click Sync manually
  }
}

/** Reset the auth-check guard. Call this right after a user logs in. */
export function resetAuthCheck(): void {
  _hasCheckedAuth = false
  _checkAuthAndSync()
}

// ── Computed values (merge yfinance prices into synced data) ─

export function getComputedPositions(): Position[] {
  if (Object.keys(state.quotes).length === 0) return state.positions
  return state.positions.map((p) => {
    const q = state.quotes[p.symbol]
    if (!q) return p
    return { ...p, currentPrice: q.price, previousClose: q.previous_close }
  })
}

export function getComputedSummary(): PortfolioSummary {
  if (Object.keys(state.quotes).length === 0 || state.positions.length === 0) return state.summary
  const positions = getComputedPositions()
  // Net account value comes from the broker's total_value (already excludes
  // margin debt and includes cash/crypto). Do NOT re-sum positions — that's
  // gross holdings and counts margin-funded shares, overstating "real money".
  const totalValue = state.summary.totalValue
  const totalCost = positions.reduce((s, p) => s + p.shares * p.avgCost, 0)
  const holdingsValue = positions.reduce((s, p) => s + p.shares * p.currentPrice, 0)
  const dailyChange = positions.reduce(
    (s, p) => s + p.shares * (p.currentPrice - p.previousClose), 0
  )
  return {
    ...state.summary,
    totalValue,
    dailyChange: Math.round(dailyChange * 100) / 100,
    dailyChangePct: totalValue > 0 ? Math.round((dailyChange / (totalValue - dailyChange)) * 10000) / 100 : 0,
    totalGain: Math.round((holdingsValue - totalCost) * 100) / 100,
    totalGainPct: totalCost > 0 ? Math.round(((holdingsValue - totalCost) / totalCost) * 10000) / 100 : 0,
  }
}

// ── React hook ─────────────────────────────────────────────

function getSnapshot(): PortfolioStoreState { return state }

function subscribe(listener: () => void) {
  listeners.add(listener)
  // Start quote polling on first subscriber if positions exist
  if (state.positions.length > 0) startQuotePolling()
  // Auto-check auth on first subscriber (triggers sync if Robinhood is connected)
  _checkAuthAndSync()
  return () => {
    listeners.delete(listener)
    if (listeners.size === 0) stopQuotePolling()
  }
}

export function usePortfolioStore() {
  const snap = useSyncExternalStore(subscribe, getSnapshot)
  return {
    ...snap,
    computedPositions: getComputedPositions(),
    computedSummary: getComputedSummary(),
    syncPortfolio,
    fetchHistory,
  }
}
