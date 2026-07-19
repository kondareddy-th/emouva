import { useState, useEffect } from 'react'
import { apiFetch } from '../api/client'

export interface KeyStatItem {
  label: string
  value: string
  context: string
  tone: 'good' | 'warn' | 'bad' | 'neutral'
}

export interface KeyStatsData {
  symbol: string
  name: string
  sector?: string
  industry?: string
  price?: number
  scores: { quality: number; health: number; growth: number; value: number; overall: number }
  insights: string[]
  sections: Record<string, KeyStatItem[]>
  trends: Record<string, number[]>
  dividend?: { yield: string; rate: string; payout_ratio: string } | null
}

/** Rich fundamentals + insights for a ticker. Ticker is the only input — the
 *  server fetches a fresh live price itself (no lagged client quotes). */
export function useKeyStats(ticker: string) {
  const [data, setData] = useState<KeyStatsData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!ticker) return
    setLoading(true)
    apiFetch<KeyStatsData>(`/api/stocks/${ticker}/key-stats`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [ticker])

  return { data, loading }
}
