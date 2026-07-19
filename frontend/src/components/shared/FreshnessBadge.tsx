import { RefreshCw } from 'lucide-react'

export function FreshnessBadge({ freshness, refreshing }: { freshness: string | null; refreshing?: boolean }) {
  if (!freshness) return null

  if (refreshing) {
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-accent/10 text-accent font-medium flex items-center gap-1">
        <RefreshCw className="w-2.5 h-2.5 animate-spin" />
        Updating
      </span>
    )
  }

  if (freshness === 'fresh') {
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-gain/10 text-gain font-medium">
        Live
      </span>
    )
  }

  if (freshness === 'stale') {
    return (
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-warning/10 text-warning font-medium">
        Cached
      </span>
    )
  }

  return null
}
