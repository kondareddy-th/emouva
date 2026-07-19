/**
 * LocalStorage cache with TTL support.
 * Used to persist research results and news feed across page navigations.
 */

const DEFAULT_TTL = 24 * 60 * 60 * 1000 // 24 hours

interface CacheEntry<T> {
  data: T
  timestamp: number
  ttl: number
}

export function getCache<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(`emouva_${key}`)
    if (!raw) return null
    const entry: CacheEntry<T> = JSON.parse(raw)
    if (Date.now() - entry.timestamp > entry.ttl) {
      localStorage.removeItem(`emouva_${key}`)
      return null
    }
    return entry.data
  } catch {
    return null
  }
}

export function setCache<T>(key: string, data: T, ttl: number = DEFAULT_TTL): void {
  try {
    const entry: CacheEntry<T> = { data, timestamp: Date.now(), ttl }
    localStorage.setItem(`emouva_${key}`, JSON.stringify(entry))
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

export function clearCache(key: string): void {
  try {
    localStorage.removeItem(`emouva_${key}`)
  } catch {
    // ignore
  }
}
