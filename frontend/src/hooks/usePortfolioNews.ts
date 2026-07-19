import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api/client'
import { getCache, setCache } from './useLocalCache'

export interface NewsArticle {
  symbol: string
  title: string
  summary: string
  impact: 'positive' | 'negative' | 'neutral'
  urgency: 'high' | 'medium' | 'low'
}

interface UsePortfolioNewsResult {
  articles: NewsArticle[]
  loading: boolean
  refetch: () => void
  lastUpdated: number | null
}

const NEWS_CACHE_KEY = 'portfolio_news'
const NEWS_CACHE_TTL = 24 * 60 * 60 * 1000 // 24 hours

export default function usePortfolioNews(): UsePortfolioNewsResult {
  const [articles, setArticles] = useState<NewsArticle[]>(() => {
    // Restore from localStorage on init
    return getCache<NewsArticle[]>(NEWS_CACHE_KEY) || []
  })
  const [loading, setLoading] = useState(true)
  const [lastUpdated, setLastUpdated] = useState<number | null>(null)

  const fetchNews = useCallback((refresh = false) => {
    // If we have cached articles and this isn't a forced refresh, skip the fetch
    if (!refresh) {
      const cached = getCache<NewsArticle[]>(NEWS_CACHE_KEY)
      if (cached && cached.length > 0) {
        setArticles(cached)
        setLoading(false)
        return
      }
    }

    setLoading(true)
    const url = refresh ? '/api/news/portfolio?refresh=true' : '/api/news/portfolio'
    apiFetch<{ articles: NewsArticle[]; source: string }>(url)
      .then((res) => {
        if (res.articles?.length) {
          setArticles(res.articles)
          setLastUpdated(Date.now())
          setCache(NEWS_CACHE_KEY, res.articles, NEWS_CACHE_TTL)
        }
      })
      .catch(() => {
        // Silently fail — keep cached articles if available
      })
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    fetchNews()
  }, [fetchNews])

  const refetch = useCallback(() => fetchNews(true), [fetchNews])

  return { articles, loading, refetch, lastUpdated }
}
