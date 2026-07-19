/**
 * Hook to batch-fetch cached AI metrics for portfolio tickers.
 * Calls POST /api/metrics/batch with all position tickers.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { apiFetch } from '../api/client'

interface FairValue {
  bear: number | null
  base: number | null
  bull: number | null
}

export interface TickerMetrics {
  fair_value: FairValue | null
  verdict: number | null
  sentiment_composite: number | null
  quality_score: Record<string, unknown> | null
  freshness: 'fresh' | 'stale' | 'missing'
}

export function usePortfolioMetrics(tickers: string[]) {
  const [metrics, setMetrics] = useState<Record<string, TickerMetrics>>({})
  const [loading, setLoading] = useState(false)
  const prevKey = useRef('')

  const fetchBatch = useCallback(async (tickerList: string[]) => {
    if (tickerList.length === 0) return
    setLoading(true)
    try {
      const res = await apiFetch<{ results: Record<string, TickerMetrics> }>('/api/metrics/batch', {
        method: 'POST',
        body: JSON.stringify({ tickers: tickerList }),
      })
      setMetrics(res.results || {})
    } catch {
      // Silent fail — metrics are optional enrichment
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const key = tickers.sort().join(',')
    if (key === prevKey.current || tickers.length === 0) return
    prevKey.current = key
    fetchBatch(tickers)
  }, [tickers, fetchBatch])

  return { metrics, loading }
}
