/**
 * Global portfolio sync button — appears in every page's header.
 * Shows last sync time with status dot. On click, triggers a full Robinhood sync.
 * Only renders when user has connected Robinhood (hidden otherwise).
 */

import { RefreshCw } from 'lucide-react'
import clsx from 'clsx'
import { usePortfolioStore, syncPortfolio } from '../hooks/usePortfolioStore'

function timeAgo(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000)
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

type StatusColor = 'green' | 'yellow' | 'red'

function getStatus(lastSyncedAt: number | null): { color: StatusColor; label: string } {
  if (!lastSyncedAt) return { color: 'red', label: 'Not synced' }
  const ageMs = Date.now() - lastSyncedAt
  if (ageMs < 30 * 60_000) return { color: 'green', label: timeAgo(lastSyncedAt) }
  if (ageMs < 2 * 60 * 60_000) return { color: 'yellow', label: timeAgo(lastSyncedAt) }
  return { color: 'red', label: timeAgo(lastSyncedAt) }
}

const dotColors: Record<StatusColor, string> = {
  green: 'bg-gain',
  yellow: 'bg-warning',
  red: 'bg-loss',
}

const dotGlow: Record<StatusColor, string> = {
  green: 'shadow-[0_0_6px_rgba(207,174,98,0.5)]',
  yellow: 'shadow-[0_0_6px_rgba(245,158,11,0.5)]',
  red: 'shadow-[0_0_6px_rgba(242,147,127,0.4)]',
}

export default function SyncButton() {
  const { lastSyncedAt, isSyncing, source } = usePortfolioStore()

  // Don't render if user hasn't connected Robinhood yet
  if (source === 'disconnected' && !lastSyncedAt) return null

  const { color, label } = getStatus(lastSyncedAt)

  return (
    <button
      onClick={() => syncPortfolio()}
      disabled={isSyncing}
      className={clsx(
        'flex items-center gap-2 px-3 py-1.5 rounded-lg text-[12px] font-medium transition-all duration-200',
        'bg-white/[0.04] backdrop-blur border border-[rgba(255,255,255,0.08)]',
        'hover:bg-white/[0.07] hover:border-[rgba(255,255,255,0.12)]',
        'active:scale-[0.97]',
        isSyncing && 'opacity-80 cursor-wait'
      )}
      title={lastSyncedAt ? `Last synced: ${new Date(lastSyncedAt).toLocaleTimeString()}` : 'Sync portfolio from Robinhood'}
    >
      {/* Status dot */}
      <span className={clsx(
        'w-[6px] h-[6px] rounded-full flex-shrink-0 transition-colors',
        isSyncing ? 'bg-accent animate-pulse' : dotColors[color],
        !isSyncing && dotGlow[color],
      )} />

      {/* Label */}
      <span className="text-text-secondary whitespace-nowrap">
        {isSyncing ? 'Syncing...' : label}
      </span>

      {/* Refresh icon */}
      <RefreshCw className={clsx(
        'w-3 h-3 text-text-tertiary flex-shrink-0 transition-transform',
        isSyncing && 'animate-spin',
      )} strokeWidth={1.5} />
    </button>
  )
}
