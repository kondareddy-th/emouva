/**
 * Portfolio data hooks — thin wrappers around usePortfolioStore.
 * These maintain the same API surface so consumer pages don't need to change.
 * Portfolio data comes from the central store (manual sync + yfinance prices).
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch } from '../api/client'
import {
  EMPTY_RISK_DATA,
  type Position,
  type PortfolioHistory,
  type WatchlistItem,
  type RiskData,
} from '../data/mockData'
import {
  usePortfolioStore,
  syncPortfolio,
  fetchHistory,
  fetchRiskData,
  getSelectedAccount,
  type PortfolioSummary,
} from './usePortfolioStore'

interface UseDataResult<T> {
  data: T
  loading: boolean
  source: 'robinhood' | 'disconnected'
  refetch: () => void
}

const EMPTY_SUMMARY: PortfolioSummary = {
  totalValue: 0, dailyChange: 0, dailyChangePct: 0,
  totalGain: 0, totalGainPct: 0, buyingPower: 0, riskScore: 0,
  source: 'disconnected',
}

export type { PortfolioSummary }

export function usePortfolioSummary(): UseDataResult<PortfolioSummary> {
  const store = usePortfolioStore()
  return {
    // Use the live summary whenever connected — an account can have cash but no
    // positions (e.g. the Agentic account), so don't gate on positions.length.
    data: store.source === 'robinhood' ? store.computedSummary : EMPTY_SUMMARY,
    loading: store.isSyncing,
    source: store.source,
    refetch: syncPortfolio,
  }
}

export interface YtdData {
  ytd_gain: number
  ytd_gain_pct: number
  baseline: string
  covered: number
  total_positions: number
  source: 'robinhood' | 'disconnected'
}

/** Year-to-date return of current holdings (server-computed vs Jan-1 close).
 *  Refetches once per account; the all-time number lives on the store. */
export function usePortfolioYtd(): { data: YtdData | null; loading: boolean } {
  const store = usePortfolioStore()
  const [data, setData] = useState<YtdData | null>(null)
  const [loading, setLoading] = useState(false)
  const triedRef = useRef<string>('')

  useEffect(() => {
    if (store.source !== 'robinhood' || store.positions.length === 0) {
      setData(null)
      triedRef.current = ''
      return
    }
    if (store.isSyncing) return
    const acct = getSelectedAccount() ?? 'default'
    if (triedRef.current === acct) return
    triedRef.current = acct
    setLoading(true)
    const q = acct !== 'default' ? `?account=${encodeURIComponent(acct)}` : ''
    apiFetch<YtdData>(`/api/portfolio/ytd${q}`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [store.source, store.positions.length, store.isSyncing])

  return { data, loading }
}

export function usePositions(): UseDataResult<Position[]> {
  const store = usePortfolioStore()
  return {
    data: store.computedPositions,
    loading: store.isSyncing,
    source: store.source,
    refetch: syncPortfolio,
  }
}

export function usePortfolioHistory(days = 90): UseDataResult<PortfolioHistory[]> {
  const store = usePortfolioStore()
  const [loading, setLoading] = useState(false)

  const fetch_ = useCallback(() => {
    setLoading(true)
    fetchHistory(days).finally(() => setLoading(false))
  }, [days])

  // Fetch history once per range when positions first load.
  // Do NOT depend on `store.history`: fetchHistory setState's a new history
  // object, and for empty ranges the guard stays true -> infinite refetch loop
  // (page-freezing) once positions are non-empty. triedRef makes each range
  // fetch at most once regardless of whether it returned data.
  const triedRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const key = `${getSelectedAccount() ?? 'default'}:${days}`
    if (store.positions.length > 0 && !store.history[days]?.length && !triedRef.current.has(key)) {
      triedRef.current.add(key)
      fetch_()
    }
  }, [store.positions.length, days, fetch_])

  return {
    data: store.history[days] ?? [],
    loading,
    source: store.source,
    refetch: fetch_,
  }
}

export function useWatchlist(): UseDataResult<WatchlistItem[]> {
  const store = usePortfolioStore()
  return {
    data: store.watchlist,
    loading: store.isSyncing,
    source: store.source,
    refetch: syncPortfolio,
  }
}

export function useRiskData(): UseDataResult<RiskData> {
  const store = usePortfolioStore()
  const hasData = store.positions.length > 0
  const [loading, setLoading] = useState(false)
  // Risk is decoupled from the main sync (it's heavy); load it once per account
  // when a risk view mounts. triedRef avoids refetch loops.
  const triedRef = useRef<Set<string>>(new Set())
  useEffect(() => {
    const key = getSelectedAccount() ?? 'default'
    if (store.source === 'robinhood' && store.positions.length > 0 && !triedRef.current.has(key)) {
      triedRef.current.add(key)
      setLoading(true)
      fetchRiskData().finally(() => setLoading(false))
    }
  }, [store.source, store.positions.length])
  return {
    data: hasData ? store.riskData : EMPTY_RISK_DATA,
    loading: loading || store.isSyncing,
    source: hasData ? 'robinhood' : store.source,
    refetch: () => { triedRef.current.clear(); fetchRiskData() },
  }
}

export function useAuthStatus() {
  const [connected, setConnected] = useState(false)
  const [source, setSource] = useState<'robinhood' | 'disconnected'>('disconnected')
  const [loading, setLoading] = useState(true)

  const fetch_ = useCallback(() => {
    setLoading(true)
    apiFetch<{ connected: boolean; source: string }>('/api/auth/status')
      .then((res) => {
        setConnected(res.connected)
        setSource(res.source === 'robinhood' ? 'robinhood' : 'disconnected')
      })
      .catch(() => {
        setConnected(false)
        setSource('disconnected')
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => { fetch_() }, [fetch_])
  return { connected, source, loading, refetch: fetch_ }
}
