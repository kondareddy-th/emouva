import type { CSSProperties } from 'react'
import { C } from '../../data/agentMockData'

/** The brand motif — a rotated square ("diamond"). No icon library on this side. */
export function Dia({ size = 7, color = C.gold, style }: { size?: number; color?: string; style?: CSSProperties }) {
  return <div style={{ width: size, height: size, background: color, transform: 'rotate(45deg)', flex: 'none', ...style }} />
}

/** 38×21 track + 15px knob toggle. */
export function Toggle({ on, onClick, disabled }: { on: boolean; onClick?: () => void; disabled?: boolean }) {
  if (disabled) {
    return (
      <div style={{ width: 38, height: 21, background: 'rgba(255,255,255,0.05)', borderRadius: 11, position: 'relative', flex: 'none', opacity: 0.5 }}>
        <div style={{ position: 'absolute', top: 3, left: 3, width: 15, height: 15, background: C.disabled, borderRadius: '50%' }} />
      </div>
    )
  }
  return (
    <div
      onClick={onClick}
      style={{ width: 38, height: 21, borderRadius: 11, position: 'relative', cursor: 'pointer', flex: 'none', transition: 'background .2s', background: on ? C.gold : 'rgba(255,255,255,0.08)' }}
    >
      <div style={{ position: 'absolute', top: 3, width: 15, height: 15, borderRadius: '50%', transition: 'left .2s, background .2s', left: on ? 20 : 3, background: on ? C.bg : C.disabled }} />
    </div>
  )
}

/** A row: label (left, secondary) + toggle (right). */
export function ToggleRow({ label, on, onClick, sub, disabled, chip }: { label: string; on?: boolean; onClick?: () => void; sub?: string; disabled?: boolean; chip?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '9px 0' }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ font: `400 12.5px 'Instrument Sans',sans-serif`, color: disabled ? C.disabled : C.body }}>{label}</div>
        {sub && <div style={{ font: `italic 400 12px 'EB Garamond',serif`, color: C.muted, marginTop: 2 }}>— {sub}</div>}
      </div>
      {chip ? (
        <span style={{ font: `600 9px 'Instrument Sans',sans-serif`, letterSpacing: '.1em', color: C.muted, background: 'rgba(255,255,255,0.05)', padding: '3px 8px', borderRadius: 4, flex: 'none' }}>{chip}</span>
      ) : (
        <Toggle on={!!on} onClick={onClick} disabled={disabled} />
      )}
    </div>
  )
}
