import { useState, useEffect, useCallback, useRef } from 'react'
import { Bell, Check, CheckCheck, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { apiFetch } from '../api/client'
import { getAuthToken } from '../hooks/useAuth'

interface Notification {
  id: string
  type: string
  title: string
  message: string
  rule_id: string | null
  is_read: boolean
  created_at: string
}

const typeColors: Record<string, string> = {
  order_executed: 'text-gain',
  order_failed: 'text-loss',
  rule_triggered: 'text-warning',
  rule_check: 'text-text-tertiary',
  system: 'text-accent',
}

export default function NotificationsBell() {
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const fetchCount = useCallback(async () => {
    if (!getAuthToken()) return
    try {
      const data = await apiFetch<{ count: number }>('/api/notifications/unread-count')
      setUnreadCount(data.count)
    } catch {
      // ignore
    }
  }, [])

  const fetchNotifications = useCallback(async () => {
    if (!getAuthToken()) return
    setLoading(true)
    try {
      const data = await apiFetch<Notification[]>('/api/notifications')
      setNotifications(data)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [])

  // Poll unread count every 60s
  useEffect(() => {
    fetchCount()
    const id = setInterval(fetchCount, 60000)
    return () => clearInterval(id)
  }, [fetchCount])

  // Fetch full list when dropdown opens
  useEffect(() => {
    if (open) fetchNotifications()
  }, [open, fetchNotifications])

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const markRead = async (id: string) => {
    await apiFetch(`/api/notifications/${id}/read`, { method: 'PUT' })
    setNotifications((prev) => prev.map((n) => n.id === id ? { ...n, is_read: true } : n))
    setUnreadCount((c) => Math.max(0, c - 1))
  }

  const markAllRead = async () => {
    await apiFetch('/api/notifications/read-all', { method: 'PUT' })
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
    setUnreadCount(0)
  }

  const formatTime = (iso: string) => {
    const d = new Date(iso)
    const now = new Date()
    const diffMs = now.getTime() - d.getTime()
    const diffMin = Math.floor(diffMs / 60000)
    if (diffMin < 60) return `${diffMin}m ago`
    const diffHrs = Math.floor(diffMin / 60)
    if (diffHrs < 24) return `${diffHrs}h ago`
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  // Don't render if not authenticated
  if (!getAuthToken()) return null

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-[6px] hover:bg-[rgba(207,174,98,0.04)] transition-colors text-text-tertiary hover:text-accent"
      >
        <Bell className="w-4 h-4" strokeWidth={1.5} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-accent text-base text-[9px] font-mono font-bold rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] shadow-xl z-50 overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[rgba(180,220,190,0.10)]">
            <span className="text-[11px] font-mono uppercase tracking-[0.13em] text-text-tertiary">Notifications</span>
            {unreadCount > 0 && (
              <button
                onClick={markAllRead}
                className="text-[11px] text-accent hover:text-accent-hover transition-colors flex items-center gap-1"
              >
                <CheckCheck className="w-3 h-3" />
                Mark all read
              </button>
            )}
          </div>

          <div className="max-h-80 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="w-5 h-5 text-text-tertiary animate-spin" />
              </div>
            ) : notifications.length === 0 ? (
              <div className="py-8 text-center">
                <p className="text-[12px] text-text-tertiary">No notifications yet</p>
              </div>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.id}
                  onClick={() => !n.is_read && markRead(n.id)}
                  className={clsx(
                    'px-4 py-3 border-b border-[rgba(180,220,190,0.06)] transition-colors',
                    !n.is_read && 'bg-[rgba(207,174,98,0.05)] cursor-pointer hover:bg-[rgba(207,174,98,0.08)]'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className={clsx(
                        'text-[12px] font-medium truncate',
                        typeColors[n.type] || 'text-text-primary'
                      )}>
                        {n.title}
                      </p>
                      <p className="text-[11px] text-text-tertiary mt-0.5 line-clamp-2">{n.message}</p>
                    </div>
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <span className="text-[10px] font-mono tabular-nums text-text-tertiary">{formatTime(n.created_at)}</span>
                      {!n.is_read && <div className="w-1.5 h-1.5 rotate-45 bg-accent" />}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
