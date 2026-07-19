/**
 * In-memory prefetch cache. Used to bridge prefetched data
 * from Settings into Dashboard hooks on first load.
 * Each key is consumed once (read-and-delete).
 */
const cache = new Map<string, { data: unknown; timestamp: number }>()
const MAX_AGE = 60_000 // 60 seconds

export function setPrefetch(key: string, data: unknown): void {
  cache.set(key, { data, timestamp: Date.now() })
}

export function consumePrefetch<T>(key: string): T | null {
  const entry = cache.get(key)
  if (!entry) return null
  cache.delete(key)
  if (Date.now() - entry.timestamp > MAX_AGE) return null
  return entry.data as T
}
