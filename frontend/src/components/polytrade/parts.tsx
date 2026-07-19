import type { CSSProperties, ReactNode } from 'react'
import { C, SANS, SERIF, MONO } from '../../data/agentMockData'
import { Dia } from '../trading/primitives'

export { C, SANS, SERIF, MONO, Dia }

// ── formatters ────────────────────────────────────────────────────────────
export const money = (v: number | null | undefined) =>
  v == null ? '—' : `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
export const money2 = (v: number | null | undefined) =>
  v == null ? '—' : `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
export const pct = (v: number | null | undefined) =>
  v == null ? '—' : `${v >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`
export const pctColor = (v: number | null | undefined) => (v == null ? C.muted : v >= 0 ? C.gain : C.loss)

// ── health / status ───────────────────────────────────────────────────────
export const HEALTH: Record<string, { c: string; dot: string; label: string }> = {
  strong: { c: C.gain, dot: '●', label: 'Strong' },
  watching: { c: C.warning, dot: '●', label: 'Watching' },
  breaking: { c: C.loss, dot: '●', label: 'Breaking' },
}
const STATUS_LABEL: Record<string, string> = { live: 'Live', weakening: 'Weakening', breaking: 'Breaking' }

export function HealthPill({ h }: { h: string }) {
  const u = HEALTH[h] || HEALTH.watching
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, font: `500 10px ${MONO}`, letterSpacing: '.08em',
      textTransform: 'uppercase', color: u.c, border: `1px solid ${u.c}44`, background: `${u.c}12`, borderRadius: 999, padding: '2px 8px' }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: u.c }} />{u.label}
    </span>
  )
}

export function StatusChip({ s }: { s: string }) {
  if (s === 'live') return null
  const col = s === 'breaking' ? C.loss : C.warning
  return <span style={{ font: `500 9.5px ${MONO}`, letterSpacing: '.1em', textTransform: 'uppercase', color: col }}>{STATUS_LABEL[s] || s}</span>
}

// ── conviction gauge ────────────────────────────────────────────────────────
export function Gauge({ v, showNum = true }: { v: number; showNum?: boolean }) {
  const col = v >= 60 ? C.gain : v >= 40 ? C.warning : C.loss
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 5, borderRadius: 999, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${Math.max(3, Math.min(100, v))}%`, background: col, borderRadius: 999, transition: 'width .5s ease' }} />
      </div>
      {showNum && <span style={{ font: `500 12px ${MONO}`, color: C.body, width: 26, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{v}</span>}
    </div>
  )
}

export const roleColor = (r: string) => (r === 'anchor' ? C.lightGold : r === 'speculative' ? C.warning : C.secondary)

export function Tag({ children }: { children: ReactNode }) {
  return <span style={{ font: `400 9.5px ${MONO}`, letterSpacing: '.06em', textTransform: 'uppercase', color: C.muted,
    background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.borderDim}`, borderRadius: 4, padding: '2px 6px' }}>{children}</span>
}

export function Card({ children, style, onClick, hover }: { children: ReactNode; style?: CSSProperties; onClick?: () => void; hover?: boolean }) {
  return (
    <div onClick={onClick} className={hover ? 'pt-card' : undefined}
      style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 14, padding: 18, cursor: onClick ? 'pointer' : 'default', ...style }}>
      {children}
    </div>
  )
}

// kind → feed glyph/color for the activity stream
export const EVENT_UI: Record<string, { c: string; label: string }> = {
  originated: { c: C.gold, label: 'Originated' },
  thesis_update: { c: C.secondary, label: 'Update' },
  rebalance: { c: C.lightGold, label: 'Rebalance' },
  earnings: { c: C.warning, label: 'Earnings' },
  news: { c: C.warning, label: 'News' },
  weaken: { c: C.warning, label: 'Weakening' },
  break: { c: C.loss, label: 'Broke' },
  exit: { c: C.loss, label: 'Exit' },
}
