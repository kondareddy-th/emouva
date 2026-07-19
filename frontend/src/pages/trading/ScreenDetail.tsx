import { Link, useParams } from 'react-router-dom'
import { useAgent } from '../../hooks/useAgentStore'
import { C, SERIF, MONO, SANS } from '../../data/agentMockData'
import { Dia } from '../../components/trading/primitives'

function Chip({ t, dim }: { t: string; dim?: boolean }) {
  return <span style={{ font: `400 10.5px ${MONO}`, color: dim ? C.muted : C.body, border: `1px solid ${dim ? 'rgba(255,255,255,0.08)' : 'rgba(180,220,190,0.2)'}`, padding: '2px 7px', borderRadius: 4 }}>{t}</span>
}
const subLabel: React.CSSProperties = { font: `500 9.5px ${SANS}`, letterSpacing: '.11em', color: C.faint, textTransform: 'uppercase', marginBottom: 8 }
const colLabel: React.CSSProperties = { font: `500 10px ${SANS}`, letterSpacing: '.12em', color: C.faint, textTransform: 'uppercase', marginBottom: 12 }
const bigNum = (color: string): React.CSSProperties => ({ font: `500 26px ${SERIF}`, color, marginBottom: 2 })

function Breadcrumb({ label, right }: { label: string; right?: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: `1px solid ${C.border}`, gap: 12, flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0, flexWrap: 'wrap' }}>
        <Link to="/trading" style={{ font: `400 12px ${SANS}`, color: C.muted, textDecoration: 'none' }}>← Ledger</Link>
        <span style={{ color: C.disabled }}>/</span>
        <span style={{ font: `500 13px ${SANS}`, color: C.textPrimary }}>{label}</span>
      </div>
      {right}
    </div>
  )
}

/** The morning screen — the real elimination funnel from /api/agent/screens. */
export default function ScreenDetail() {
  const a = useAgent()
  const mob = a.isMobile
  const { id } = useParams()
  const s = a.screens.find((x) => x.id === id) || a.latestScreen

  const runBtn = (label: string) => (
    <span onClick={() => { if (!a.screening) a.runScreen() }} style={{ display: 'inline-block', font: `500 13px ${SANS}`, color: C.bg, background: a.screening ? C.muted : C.gold, padding: '10px 20px', borderRadius: 7, cursor: a.screening ? 'default' : 'pointer' }}>{a.screening ? 'Running the screen…' : label}</span>
  )

  if (!s) {
    return (
      <div style={{ maxWidth: 1440, margin: '0 auto' }}>
        <Breadcrumb label="Morning screen" />
        <div style={{ padding: mob ? '48px 16px' : '72px 24px', textAlign: 'center' }}>
          <div style={{ font: `400 14px/1.6 ${SERIF}`, color: C.secondary, marginBottom: 6 }}>No screen has run yet.</div>
          <div style={{ font: `400 12px ${SANS}`, color: C.muted, marginBottom: 20 }}>The Partner funnels your watchlist through the circle of competence, margin of safety, and inversion.</div>
          {runBtn('Run the morning screen')}
        </div>
      </div>
    )
  }

  const stages = s.stages || []
  const grid: React.CSSProperties = mob
    ? { display: 'flex', flexDirection: 'column' }
    : { display: 'grid', gridTemplateColumns: `repeat(${Math.max(stages.length, 1)}, minmax(170px, 1fr)) 1.3fr` }
  const colB: React.CSSProperties = mob ? { padding: '18px 16px', borderBottom: `1px solid ${C.borderDim}` } : { padding: 20, borderRight: `1px solid ${C.borderDim}` }
  const col4: React.CSSProperties = mob ? { padding: '18px 16px', background: C.raised } : { padding: 20, background: C.raised }
  const when = new Date(s.created_at).toLocaleString('en-US', { weekday: 'long', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
  const survivorPending = a.apprPending && a.pendingOrder && s.survivor && a.pendingOrder.symbol === s.survivor

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto' }}>
      <Breadcrumb label={`Morning screen · ${when}`} right={<span style={{ font: `400 11px ${MONO}`, color: C.faint }}>{s.universe_count} in universe · archived</span>} />
      <div style={grid}>
        {stages.map((st, i) => {
          const first = i === 0
          return (
            <div key={i} style={colB}>
              <div style={bigNum(first ? C.muted : C.body)}>{st.count}</div>
              <div style={colLabel}>{st.label}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: st.exclusions?.length ? 14 : 0, opacity: first ? 0.5 : 1 }}>
                {(st.tickers || []).map((t) => <Chip key={t} t={t} dim={first} />)}
              </div>
              {!!st.exclusions?.length && (
                <>
                  <div style={subLabel}>Why some fell out</div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 7, font: `400 11px/1.45 ${SANS}`, color: C.muted }}>
                    {st.exclusions.map((ex, j) => <div key={j}>{ex}</div>)}
                  </div>
                </>
              )}
            </div>
          )
        })}

        {/* survivor + verdict */}
        <div style={col4}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <Dia size={8} color={C.gold} style={{ transform: 'rotate(45deg)' }} />
            <span style={{ font: `500 18px ${SERIF}`, color: C.textPrimary }}>{s.survivor ? `${s.survivor} — the survivor` : 'No survivor this run'}</span>
          </div>
          <div style={{ background: 'rgba(207,174,98,0.07)', border: '1px solid rgba(207,174,98,0.3)', borderRadius: 8, padding: '12px 14px', marginBottom: 12 }}>
            <div style={{ font: `500 9.5px ${SANS}`, letterSpacing: '.12em', color: C.gold, textTransform: 'uppercase', marginBottom: 5 }}>Verdict</div>
            <div style={{ font: `400 12.5px/1.55 ${SANS}`, color: C.body, marginBottom: survivorPending ? 10 : 0 }}>{s.verdict}</div>
            {survivorPending && (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <span onClick={a.approve} style={{ font: `500 12px ${SANS}`, color: C.bg, background: C.gold, padding: '8px 18px', borderRadius: 6, cursor: 'pointer' }}>Approve buy</span>
                <span onClick={a.decline} style={{ font: `500 12px ${SANS}`, color: C.secondary, border: `1px solid ${C.goldBorder}`, padding: '8px 18px', borderRadius: 6, cursor: 'pointer' }}>Decline</span>
              </div>
            )}
          </div>
          <div style={{ font: `italic 400 12.5px ${SERIF}`, color: C.muted, marginBottom: 16 }}>"An idea isn't yours until you can state the other side better than they can."</div>
          <span onClick={() => { if (!a.screening) a.runScreen() }} style={{ font: `500 12px ${SANS}`, color: C.secondary, border: `1px solid ${C.goldBorder}`, padding: '8px 16px', borderRadius: 6, cursor: a.screening ? 'default' : 'pointer' }}>{a.screening ? 'Running…' : 'Run a fresh screen'}</span>
        </div>
      </div>
    </div>
  )
}
