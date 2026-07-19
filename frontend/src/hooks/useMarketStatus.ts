import { useEffect, useState } from 'react'
import { apiFetch } from '../api/client'

export interface MarketStatus {
  open: boolean
  session: 'open' | 'pre' | 'after' | 'closed' | 'holiday' | 'weekend'
  is_holiday: boolean
  is_early_close: boolean
  et: string
  label: string
  close_time: string | null
}

/** Live US-equities market status (holiday/half-day aware) from /api/market/status.
 *  Public endpoint — works on the landing page too. Polls every `pollMs`. */
export function useMarketStatus(pollMs = 60_000): MarketStatus | null {
  const [status, setStatus] = useState<MarketStatus | null>(null)
  useEffect(() => {
    let alive = true
    const load = () =>
      apiFetch<MarketStatus>('/api/market/status')
        .then((s) => { if (alive) setStatus(s) })
        .catch(() => {})
    load()
    const t = setInterval(load, pollMs)
    return () => { alive = false; clearInterval(t) }
  }, [pollMs])
  return status
}
