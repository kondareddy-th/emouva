/**
 * Module-level watchlist store backed by the API (PostgreSQL).
 * Falls back to localStorage for offline/unauthenticated users.
 * Persists user-curated watchlist items from AI Research analysis.
 */

import { useSyncExternalStore } from 'react'
import { showToast } from '../components/Toast'
import { apiFetch } from '../api/client'
import { getAuthToken } from './useAuth'

const STORAGE_KEY = 'emouva_watchlist_items'

export interface WatchlistEntry {
  symbol: string
  name: string
  fairValue: { bear: number; base: number; bull: number }
  lastPrice: number
  thesis: string
  addedAt: string
  lastAnalyzedAt: string
}

let items: WatchlistEntry[] = []
let hasFetched = false

// Restore from localStorage as initial cache while API loads
try {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (raw) items = JSON.parse(raw)
} catch { /* ignore */ }

const listeners = new Set<() => void>()
function emit() { listeners.forEach((fn) => fn()) }

function persistLocal() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  } catch { /* ignore */ }
}

interface ApiWatchlistItem {
  symbol: string
  name: string
  thesis: string
  fair_value: { bear: number; base: number; bull: number } | null
  last_price: number | null
  last_analyzed_at: string | null
  added_at: string
}

function apiToEntry(item: ApiWatchlistItem): WatchlistEntry {
  return {
    symbol: item.symbol,
    name: item.name,
    thesis: item.thesis,
    fairValue: item.fair_value ?? { bear: 0, base: 0, bull: 0 },
    lastPrice: item.last_price ?? 0,
    addedAt: item.added_at,
    lastAnalyzedAt: item.last_analyzed_at ?? '',
  }
}

/** Fetch watchlist from API and sync local state */
export async function fetchWatchlist(): Promise<void> {
  if (!getAuthToken()) return
  try {
    const data = await apiFetch<ApiWatchlistItem[]>('/api/watchlist')
    items = data.map(apiToEntry)
    persistLocal()
    hasFetched = true
    emit()
  } catch {
    // API failed — keep localStorage data
  }
}

export async function addToWatchlist(entry: WatchlistEntry) {
  // Optimistic update
  const idx = items.findIndex((i) => i.symbol === entry.symbol)
  if (idx >= 0) {
    items = [...items]
    items[idx] = entry
  } else {
    items = [...items, entry]
  }
  persistLocal()
  emit()
  showToast(`${entry.symbol} added to watchlist`, 'success')

  // Persist to API
  if (getAuthToken()) {
    try {
      await apiFetch('/api/watchlist', {
        method: 'POST',
        body: JSON.stringify({
          symbol: entry.symbol,
          name: entry.name,
          thesis: entry.thesis,
          fair_value: entry.fairValue,
          last_price: entry.lastPrice,
        }),
      })
    } catch {
      // API failed — local state is still correct
    }
  }
}

export async function removeFromWatchlist(symbol: string) {
  // Optimistic update
  items = items.filter((i) => i.symbol !== symbol)
  persistLocal()
  emit()
  showToast(`${symbol} removed from watchlist`, 'info')

  // Persist to API
  if (getAuthToken()) {
    try {
      await apiFetch(`/api/watchlist/${symbol}`, { method: 'DELETE' })
    } catch {
      // API failed — local state is still correct
    }
  }
}

export interface StockSearchResult { symbol: string; name: string; exchange: string }
export interface WatchlistNews { title: string; site: string; date: string; url: string }
export interface WatchlistDetail {
  symbol: string; name: string; last_price: number | null; added_at: string
  meta: { metrics?: Record<string, number | string | null>; news?: WatchlistNews[]; populated_at?: string } | null
}

/** US-listed ticker/name search for the add box. */
export async function searchStocks(q: string): Promise<StockSearchResult[]> {
  if (!q.trim() || !getAuthToken()) return []
  try { return await apiFetch<StockSearchResult[]>(`/api/watchlist/search?q=${encodeURIComponent(q.trim())}`) }
  catch { return [] }
}

/** Full detail for one item (FMP metrics + 30d news, populated in the background on add). */
export async function getWatchlistDetail(symbol: string): Promise<WatchlistDetail | null> {
  try { return await apiFetch<WatchlistDetail>(`/api/watchlist/${symbol}`) }
  catch { return null }
}

/** Lightweight add from search (metrics/news fill in server-side). */
export async function addSymbol(symbol: string, name = '') {
  await addToWatchlist({ symbol: symbol.toUpperCase(), name, fairValue: { bear: 0, base: 0, bull: 0 },
    lastPrice: 0, thesis: '', addedAt: new Date().toISOString(), lastAnalyzedAt: '' })
}

export function isInWatchlist(symbol: string): boolean {
  return items.some((i) => i.symbol === symbol)
}

function getSnapshot(): WatchlistEntry[] {
  return items
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  // Fetch from API on first subscriber if not yet fetched
  if (!hasFetched && getAuthToken()) {
    fetchWatchlist()
  }
  return () => { listeners.delete(listener) }
}

export function useWatchlistStore() {
  const entries = useSyncExternalStore(subscribe, getSnapshot)
  return {
    items: entries,
    addToWatchlist,
    addSymbol,
    searchStocks,
    getWatchlistDetail,
    removeFromWatchlist,
    isInWatchlist,
  }
}
