import { useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { C, SANS } from '../data/agentMockData'

/** Risk ↔ Trading ↔ Polytrade mode switch. `variant` themes it to the side it sits on. */
export default function ModeToggle({ active, variant }: { active: 'risk' | 'trading' | 'polytrade' | 'community'; variant: 'gold' | 'navy' }) {
  const nav = useNavigate()

  if (variant === 'gold') {
    const seg = (label: string, isActive: boolean, to: string) => (
      <span
        onClick={() => !isActive && nav(to)}
        style={{
          font: `500 11px ${SANS}`, letterSpacing: '.02em', padding: '4px 11px', borderRadius: 5, cursor: isActive ? 'default' : 'pointer',
          userSelect: 'none', transition: 'color .15s, background .15s', whiteSpace: 'nowrap',
          color: isActive ? C.bg : C.muted, background: isActive ? C.gold : 'transparent',
        }}
      >{label}</span>
    )
    return (
      <div style={{ display: 'flex', gap: 2, padding: 2, borderRadius: 7, background: 'rgba(255,255,255,0.04)', border: `1px solid ${C.border}` }}>
        {seg('Risk', active === 'risk', '/')}
        {seg('Trading', active === 'trading', '/trading')}
        {seg('Polytrade', active === 'polytrade', '/polytrade')}
        {seg('Community', active === 'community', '/community')}
      </div>
    )
  }

  // navy (risk side) — matches the existing dashboard theme
  const seg = (label: string, isActive: boolean, to: string) => (
    <button
      onClick={() => !isActive && nav(to)}
      className={clsx(
        'px-3 py-1 rounded-md text-[12px] font-medium transition-colors whitespace-nowrap',
        isActive ? 'bg-accent/15 text-accent cursor-default' : 'text-text-tertiary hover:text-text-secondary'
      )}
    >{label}</button>
  )
  return (
    <div className="flex gap-1 p-1 rounded-lg bg-surface-2 border border-[rgba(255,255,255,0.06)]">
      {seg('Risk', active === 'risk', '/')}
      {seg('Trading', active === 'trading', '/trading')}
      {seg('Polytrade', active === 'polytrade', '/polytrade')}
      {seg('Community', active === 'community', '/community')}
    </div>
  )
}
