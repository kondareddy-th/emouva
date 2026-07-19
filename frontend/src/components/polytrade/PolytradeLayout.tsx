import { Outlet, Link, Navigate, useLocation } from 'react-router-dom'
import { C, SANS, MONO, Dia } from './parts'
import ModeToggle from '../ModeToggle'
import useAuth from '../../hooks/useAuth'

const NAV = [
  { label: 'Discover', path: '/polytrade' },
  { label: 'My Themes', path: '/polytrade/mine' },
]

export default function PolytradeLayout() {
  const loc = useLocation()
  const active = (p: string) => (p === '/polytrade' ? loc.pathname === p : loc.pathname.startsWith(p))

  // Personal hosted instance: community-only members can't open Polytrade.
  const { user } = useAuth()
  if (user?.full_access === false) return <Navigate to="/community" replace />
  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.textPrimary, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      <div style={{ position: 'sticky', top: 0, zIndex: 40, background: C.topBar, borderBottom: `1px solid ${C.border}`, backdropFilter: 'blur(6px)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 54, padding: '0 20px', maxWidth: 1200, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 26, minWidth: 0 }}>
            <Link to="/polytrade" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none', flex: 'none' }}>
              <Dia size={10} />
              <span style={{ font: `600 13px ${SANS}`, letterSpacing: '.22em', color: C.lightGold }}>POLYTRADE</span>
              <span style={{ font: `500 8.5px ${MONO}`, letterSpacing: '.12em', color: C.gold, border: `1px solid ${C.goldBorder}`, borderRadius: 3, padding: '1px 4px', lineHeight: 1 }}>BETA</span>
            </Link>
            <div style={{ display: 'flex', gap: 2 }}>
              {NAV.map((n) => {
                const on = active(n.path)
                return (
                  <Link key={n.path} to={n.path} style={{
                    font: `${on ? 600 : 400} 12px ${SANS}`, color: on ? C.textPrimary : C.muted,
                    padding: '6px 12px', background: on ? 'rgba(207,174,98,0.10)' : 'transparent',
                    borderRadius: 6, textDecoration: 'none', whiteSpace: 'nowrap',
                  }}>{n.label}</Link>
                )
              })}
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <span style={{ font: `400 10px ${MONO}`, letterSpacing: '.1em', color: C.faint, textTransform: 'uppercase' }} className="hidden sm:inline">AI-managed · live</span>
            <ModeToggle active="polytrade" variant="gold" />
          </div>
        </div>
      </div>
      <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 20px 80px' }} className="em-fade" key={loc.pathname}>
        <Outlet />
      </div>
    </div>
  )
}
