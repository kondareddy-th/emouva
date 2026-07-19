import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client'
import { getCache, setCache } from './useLocalCache'
import type { NewsArticle } from './usePortfolioNews'

interface UseMarketNewsResult {
  articles: NewsArticle[]
  summary: string
  loading: boolean
  refetch: () => void
}

interface RawArticle {
  symbol?: string
  title: string
  summary?: string
  impact?: 'positive' | 'negative' | 'neutral'
}

const CACHE_KEY = 'market_news'
const CACHE_TTL = 4 * 60 * 60 * 1000 // 4h — refreshed server-side 3x/day

/** Major-market news brief, curated by Claude 3x/day and served from the
 *  backend cache. */
export default function useMarketNews(): UseMarketNewsResult {
  const [articles, setArticles] = useState<NewsArticle[]>(() => getCache<NewsArticle[]>(CACHE_KEY) || [])
  const [summary, setSummary] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchNews = useCallback(() => {
    setLoading(true)
    apiFetch<{ articles: RawArticle[]; summary: string }>('/api/news/market')
      .then((res) => {
        const arts: NewsArticle[] = (res.articles || []).map((a) => ({
          symbol: a.symbol || 'MKT',
          title: a.title,
          summary: a.summary || '',
          impact: a.impact || 'neutral',
          urgency: 'medium',
        }))
        if (arts.length) {
          setArticles(arts)
          setCache(CACHE_KEY, arts, CACHE_TTL)
        }
        setSummary(res.summary || '')
      })
      .catch(() => {
        /* keep cached */
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchNews()
  }, [fetchNews])

  return { articles, summary, loading, refetch: fetchNews }
}
