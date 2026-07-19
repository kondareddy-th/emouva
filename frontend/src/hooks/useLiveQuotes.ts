import { useState, useCallback } from 'react'
import { apiFetch } from '../api/client'
import useInterval from './useInterval'

export interface Quote {
  symbol: string
  price: number
  previous_close: number
  change_pct: number
}

export type QuoteMap = Record<string, Quote>

interface UseLiveQuotesResult {
  quotes: QuoteMap
  lastUpdated: number | null
}

/**
 * Polls /api/portfolio/quotes every 5 seconds when enabled.
 * Returns a map of symbol → {price, previous_close, change_pct}.
 */
export default function useLiveQuotes(enabled: boolean): UseLiveQuotesResult {
  const [quotes, setQuotes] = useState<QuoteMap>({})
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)

  const fetchQuotes = useCallback(() => {
    apiFetch<{ quotes: Quote[]; source: string }>('/api/portfolio/quotes')
      .then((res) => {
        if (res.source === 'robinhood' && res.quotes?.length) {
          const map: QuoteMap = {}
          for (const q of res.quotes) {
            map[q.symbol] = q
          }
          setQuotes(map)
          setLastUpdated(Date.now())
        }
      })
      .catch(() => {
        // Silently fail — prices stay stale
      })
  }, [])

  useInterval(fetchQuotes, enabled ? 5000 : null)

  return { quotes, lastUpdated }
}
