/**
 * Hook to fetch cached stock metrics from the server.
 * Returns cached AI analysis + freshness status for a ticker.
 */

import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client'

interface FieldInfo {
  data: Record<string, unknown> | unknown[] | null
  status: 'fresh' | 'stale' | 'missing'
  updated_at: string | null
}

export interface MetricsCache {
  ticker: string
  fields: {
    market_data: FieldInfo
    company_info: FieldInfo
    earnings: FieldInfo
    news: FieldInfo
    ai_analysis: FieldInfo
    ai_bear_case: FieldInfo
    ai_sentiment: FieldInfo
  }
  freshness_summary: Record<string, string>
}

export function useStockMetrics(ticker: string) {
  const [cache, setCache] = useState<MetricsCache | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchMetrics = useCallback(async (t: string) => {
    if (!t) return
    setLoading(true)
    try {
      const res = await apiFetch<MetricsCache>(`/api/metrics/${t.toUpperCase()}`)
      setCache(res)
    } catch {
      // Silent fail — cache miss is expected for new tickers
      setCache(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (ticker) {
      fetchMetrics(ticker)
    } else {
      setCache(null)
    }
  }, [ticker, fetchMetrics])

  const hasCachedAnalysis = cache?.fields?.ai_analysis?.status !== 'missing' &&
    cache?.fields?.ai_analysis?.data !== null

  return { cache, loading, hasCachedAnalysis, refetch: fetchMetrics }
}
