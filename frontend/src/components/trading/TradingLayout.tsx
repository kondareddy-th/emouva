import { Outlet, Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import useAuth from '../../hooks/useAuth'
import { AgentProvider, useAgent } from '../../hooks/useAgentStore'
import { C, SANS, MONO, NAV } from '../../data/agentMockData'
import { Dia } from './primitives'
import ModeToggle from '../ModeToggle'
import { useMarketStatus } from '../../hooks/useMarketStatus'

export default function TradingLayout() {
  return (
    <AgentProvider>
      <TradingShell />
    </AgentProvider>
  )
}

function TradingShell() {
  const a = useAgent()
  const loc = useLocation()
  const nav = useNavigate()
  const activeId = NAV.find((n) => n.path === loc.pathname)?.id

  // Personal hosted instance: community-only members can't open the trading side.
  const { user } = useAuth()
  if (user?.full_access === false) return <Navigate to="/community" replace />

  const mkt = useMarketStatus()
  const statusDot = a.paused ? C.warning : (mkt?.open ? C.gain : C.muted)
  const statusText = a.paused
    ? (a.isMobile ? 'PAUSED' : `PAUSED · ${mkt?.et ?? ''}`)
    : a.isMobile
      ? (mkt ? `${mkt.open ? 'OPEN' : 'CLOSED'} · ${mkt.et}` : '—')
      : (mkt ? `${mkt.label} · ${mkt.et}`.toUpperCase() : '—')

  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.textPrimary, fontFamily: SANS, WebkitFontSmoothing: 'antialiased' }}>
      {/* ── TOP BAR ── */}
      <div style={{ position: 'sticky', top: 0, zIndex: 40, background: C.topBar, borderBottom: `1px solid ${C.border}`, backdropFilter: 'blur(6px)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', height: 54, padding: '0 20px', maxWidth: 1440, margin: '0 auto' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 26, minWidth: 0 }}>
            <Link to="/trading" style={{ display: 'flex', alignItems: 'center', gap: 9, textDecoration: 'none', flex: 'none' }}>
              <Dia size={10} />
              <span style={{ font: `500 13px ${SANS}`, letterSpacing: '.22em', color: C.lightGold }}>EMOUVA</span>
              <span style={{ font: `500 8.5px ${MONO}`, letterSpacing: '.12em', color: C.gold, border: `1px solid ${C.goldBorder}`, borderRadius: 3, padding: '1px 4px', lineHeight: 1 }}>BETA</span>
            </Link>
            {!a.isMobile && (
              <div style={{ display: 'flex', gap: 2 }}>
                {NAV.map((n) => {
                  const on = activeId === n.id
                  return (
                    <Link key={n.id} to={n.path} style={{
                      font: `${on ? 500 : 400} 12px ${SANS}`, color: on ? C.textPrimary : C.muted,
                      padding: '6px 12px', background: on ? 'rgba(207,174,98,0.10)' : 'transparent',
                      borderRadius: 6, textDecoration: 'none', whiteSpace: 'nowrap', transition: 'color .15s',
                    }}>{n.label}</Link>
                  )
                })}
              </div>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, flex: 'none' }}>
            <ModeToggle active="trading" variant="gold" />
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <div className={a.paused ? 'em-pulse-dot' : undefined} style={{ width: 6, height: 6, borderRadius: '50%', flex: 'none', background: statusDot }} />
              <span style={{ font: `400 11px ${MONO}`, color: C.muted, whiteSpace: 'nowrap' }}>{statusText}</span>
            </div>
            <div style={{ width: 28, height: 28, borderRadius: '50%', background: '#1D2721', border: `1px solid rgba(180,220,190,0.2)`, display: 'flex', alignItems: 'center', justifyContent: 'center', font: `500 11px 'EB Garamond',serif`, color: C.gold, cursor: 'pointer', flex: 'none' }}>R</div>
          </div>
        </div>
      </div>

      {/* ── PAUSED BANNER ── */}
      {a.paused && (
        <div style={{ background: C.amberTint, borderBottom: `1px solid ${C.amberBorder}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 20px', maxWidth: 1440, margin: '0 auto' }}>
            <Dia size={6} color={C.warning} />
            <span style={{ font: `400 12px ${SANS}`, color: '#D8C39A' }}>The Partner is paused — watching and writing to the Ledger, but not trading.</span>
            <span onClick={a.resume} style={{ font: `500 12px ${SANS}`, color: C.lightGold, cursor: 'pointer', textDecoration: 'underline', textUnderlineOffset: 3, marginLeft: 'auto' }}>Resume</span>
          </div>
        </div>
      )}

      {/* ── SCREEN ── */}
      <div style={{ maxWidth: 1440, margin: '0 auto' }} className="em-fade" key={loc.pathname}>
        <Outlet />
      </div>

      {/* ── MOBILE BOTTOM NAV ── */}
      {a.isMobile && (
        <>
          <div style={{ height: 88 }} />
          <div style={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 50, background: C.mobileNav, borderTop: `1px solid ${C.goldBorder}`, display: 'flex', paddingBottom: 'env(safe-area-inset-bottom)' }}>
            {NAV.map((n) => {
              const on = activeId === n.id
              return (
                <div key={n.id} onClick={() => nav(n.path)} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 5, height: 60, cursor: 'pointer' }}>
                  <div style={{ width: 5, height: 5, transform: 'rotate(45deg)', transition: 'background .2s', background: on ? C.gold : 'transparent' }} />
                  <span style={{ font: `${on ? 500 : 400} 9.5px ${SANS}`, letterSpacing: '.04em', color: on ? C.lightGold : C.faint }}>{n.label}</span>
                </div>
              )
            })}
          </div>
        </>
      )}

      {/* ── TOAST ── */}
      {a.toast && (
        <div className="em-toast" style={{ position: 'fixed', left: '50%', transform: 'translateX(-50%)', zIndex: 95, display: 'flex', alignItems: 'center', gap: 10, background: C.toast, border: `1px solid rgba(207,174,98,0.45)`, borderRadius: 10, padding: '12px 18px', font: `400 12.5px ${SANS}`, color: C.textPrimary, boxShadow: '0 12px 40px rgba(0,0,0,0.6)', maxWidth: 'calc(100vw - 32px)', bottom: a.isMobile ? 94 : 28 }}>
          <Dia size={7} />
          <span>{a.toast}</span>
        </div>
      )}
    </div>
  )
}
