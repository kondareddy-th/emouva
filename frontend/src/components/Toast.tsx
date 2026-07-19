/**
 * Lightweight toast notification system.
 * Usage: import { showToast } from './Toast' then call showToast('message', 'success')
 * Renders via portal to document.body.
 */

import { createPortal } from 'react-dom'
import { useEffect, useState, useSyncExternalStore } from 'react'
import { CheckCircle2, XCircle, Info } from 'lucide-react'
import clsx from 'clsx'

type ToastType = 'success' | 'error' | 'info'

interface ToastItem {
  id: number
  message: string
  type: ToastType
}

let nextId = 0
let toasts: ToastItem[] = []
const listeners = new Set<() => void>()

function emit() { listeners.forEach((fn) => fn()) }

export function showToast(message: string, type: ToastType = 'success') {
  const id = nextId++
  toasts = [...toasts, { id, message, type }]
  emit()
  setTimeout(() => {
    toasts = toasts.filter((t) => t.id !== id)
    emit()
  }, 3000)
}

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

function getSnapshot() { return toasts }

const ICONS = {
  success: CheckCircle2,
  error: XCircle,
  info: Info,
}

const COLORS = {
  success: 'bg-gain/10 border-gain/20 text-gain',
  error: 'bg-loss/10 border-loss/20 text-loss',
  info: 'bg-accent/10 border-accent/20 text-accent',
}

function ToastItem({ toast }: { toast: ToastItem }) {
  const [visible, setVisible] = useState(false)
  const Icon = ICONS[toast.type]

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
    const timer = setTimeout(() => setVisible(false), 2600)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div
      className={clsx(
        'flex items-center gap-2.5 px-4 py-3 rounded-lg border backdrop-blur-xl shadow-lg transition-all duration-300',
        COLORS[toast.type],
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-2'
      )}
    >
      <Icon className="w-4 h-4 flex-shrink-0" strokeWidth={1.5} />
      <span className="text-[13px] font-medium text-text-primary">{toast.message}</span>
    </div>
  )
}

export default function ToastContainer() {
  const items = useSyncExternalStore(subscribe, getSnapshot)

  if (items.length === 0) return null

  return createPortal(
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col gap-2">
      {items.map((t) => <ToastItem key={t.id} toast={t} />)}
    </div>,
    document.body
  )
}
