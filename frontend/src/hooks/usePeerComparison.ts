import { useState, useEffect } from 'react'
import { apiFetch } from '../api/client'

export interface PeerMetric {
  symbol: string
  name: string
  market_cap: number | null
  revenue: number | null
  rev_growth: number | null
  gross_margin: number | null
  net_margin: number | null
  roe: number | null
  pe: number | null
}

export interface PeerRank {
  rank: number
  of: number
  percentile: number
  label: string
  fmt: string
}

export interface PeerData {
  symbol: string
  peer_group: string
  metrics: { key: string; label: string; fmt: string; higher_better: boolean }[]
  peers: PeerMetric[]
  ranks: Record<string, PeerRank>
}

/** Industry peer comparison for a ticker (loads separately from key-stats since
 *  fetching peer fundamentals is slower). */
export function usePeerComparison(ticker: string) {
  const [data, setData] = useState<PeerData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!ticker) return
    setLoading(true)
    apiFetch<PeerData>(`/api/stocks/${ticker}/peers`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [ticker])

  return { data, loading }
}
