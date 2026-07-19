import { useAgent } from '../../hooks/useAgentStore'
import { C, SANS, MONO, SERIF, label, P_SECTIONS, type Principle } from '../../data/agentMockData'
import { Dia } from '../../components/trading/primitives'

const goldBtn: React.CSSProperties = { font: `500 12px ${SANS}`, color: C.bg, background: C.gold, padding: '8px 16px', borderRadius: 6, cursor: 'pointer', transition: 'background .15s' }
const outlineBtn: React.CSSProperties = { font: `500 12px ${SANS}`, color: C.secondary, border: `1px solid ${C.goldBorder}`, padding: '8px 16px', borderRadius: 6, cursor: 'pointer' }
const chip: React.CSSProperties = { border: `1px solid rgba(180,220,190,0.15)`, padding: '5px 11px', borderRadius: 6, cursor: 'pointer', transition: 'border-color .15s' }
const railLabel: React.CSSProperties = { font: `500 10px ${SANS}`, letterSpacing: '.13em', color: C.faint, textTransform: 'uppercase', marginBottom: 10 }
const railGoldLabel: React.CSSProperties = { font: `500 10px ${SANS}`, letterSpacing: '.13em', color: C.gold, textTransform: 'uppercase', marginBottom: 10 }
const statRow = (name: string, value: React.ReactNode, valColor: string) => (
  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
    <span>{name}</span>
    <span style={{ fontFamily: MONO, color: valColor }}>{value}</span>
  </div>
)

function PrincipleCard({ p, a }: { p: Principle; a: ReturnType<typeof useAgent> }) {
  const paused = !!p.paused
  const cardStyle: React.CSSProperties = {
    background: C.card,
    border: `1px solid ${p.gold ? 'rgba(207,174,98,0.3)' : C.border}`,
    borderRadius: 10,
    padding: '16px 18px',
    marginBottom: 10,
    display: 'flex',
    gap: 14,
    alignItems: 'flex-start',
    ...(paused ? { opacity: 0.55 } : {}),
  }
  const metaColor = paused ? C.warning : p.gold ? C.gold : C.faint
  return (
    <div style={cardStyle}>
      <Dia size={7} color={p.gold ? C.lightGold : C.gold} style={{ marginTop: 6 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ font: `italic 400 15px/1.5 ${SERIF}`, color: C.textPrimary, marginBottom: 6 }}>{p.text}</div>
        <div style={{ font: `400 11px ${MONO}`, color: metaColor }}>{paused ? 'PAUSED — not consulted until resumed' : p.meta}</div>
      </div>
      <div style={{ display: 'flex', gap: 6, font: `400 11px ${SANS}`, color: C.faint, flex: 'none' }}>
        <span style={chip} onClick={() => a.edit(p.id, p.text)}>Edit</span>
        <span style={chip} onClick={() => a.pausePrinciple(p.id)}>{paused ? 'Resume' : 'Pause'}</span>
      </div>
    </div>
  )
}

function EditingCard({ p, a }: { p: Principle; a: ReturnType<typeof useAgent> }) {
  return (
    <div style={{ background: C.emphasis, border: `1px solid ${C.goldBorderStrong}`, borderRadius: 10, padding: '16px 18px', marginBottom: 10 }}>
      <div style={{ font: `500 10px ${SANS}`, letterSpacing: '.12em', color: C.gold, textTransform: 'uppercase', marginBottom: 10 }}>Editing</div>
      <textarea
        value={a.draftText}
        onChange={(e) => a.setDraft(e.target.value)}
        rows={2}
        style={{ width: '100%', boxSizing: 'border-box', background: C.bg, border: `1px solid rgba(180,220,190,0.2)`, borderRadius: 8, padding: '12px 14px', font: `italic 400 15px/1.5 ${SERIF}`, color: C.textPrimary, marginBottom: 12, resize: 'none' }}
      />
      <div style={{ display: 'flex', gap: 12, padding: '12px 14px', background: 'rgba(207,174,98,0.05)', borderRadius: 8, marginBottom: 12 }}>
        <div style={{ width: 24, height: 24, flex: 'none', border: `1px solid rgba(207,174,98,0.5)`, borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Dia size={7} color={C.gold} />
        </div>
        <div style={{ font: `400 12px/1.55 ${SANS}`, color: C.secondary }}>
          <span style={{ color: C.lightGold }}>How I'll apply this:</span> {p.restate}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={goldBtn} onClick={a.saveEdit}>Save &amp; backtest</span>
        <span style={outlineBtn} onClick={a.cancelEdit}>Cancel</span>
        <span style={{ font: `400 11px ${SANS}`, color: C.faint, marginLeft: 'auto' }}>Changes apply only after backtest review</span>
      </div>
    </div>
  )
}

export default function Principles() {
  const a = useAgent()
  const mob = a.isMobile
  const prinGrid: React.CSSProperties = mob
    ? { display: 'flex', flexDirection: 'column' }
    : { display: 'grid', gridTemplateColumns: '1fr 340px' }
  const prinMain: React.CSSProperties = mob
    ? { padding: '18px 16px' }
    : { padding: 24, borderRight: `1px solid ${C.borderDim}` }
  const prinRail: React.CSSProperties = {
    padding: mob ? '18px 16px' : '24px 20px',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    background: C.raised,
  }

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto' }}>
      <div style={prinGrid}>
        {/* ── main ── */}
        <div style={prinMain}>
          <div style={{ marginBottom: 6, font: `500 24px ${SERIF}`, color: C.textPrimary }}>The Latticework</div>
          <div style={{ font: `400 12.5px ${SANS}`, color: C.muted, marginBottom: 22 }}>
            12 principles govern every decision. The Partner must cite one for anything it does — or declines to do.
          </div>

          {P_SECTIONS.map((sec) => (
            <div key={sec}>
              <div style={{ ...label(), font: `500 10px ${SANS}`, letterSpacing: '.14em', color: C.faint, margin: '8px 0 10px' }}>{sec}</div>
              {a.allP
                .filter((p) => p.sec === sec)
                .map((p) =>
                  a.editingId === p.id
                    ? <EditingCard key={p.id} p={p} a={a} />
                    : <PrincipleCard key={p.id} p={p} a={a} />
                )}
            </div>
          ))}

          <div style={{ font: `400 11px ${SANS}`, color: C.faint, marginTop: 6 }}>
            Showing {a.shownCount} of {a.principleCount} · <span style={{ color: C.gold, cursor: 'pointer' }}>View all</span>
          </div>
        </div>

        {/* ── rail ── */}
        <div style={prinRail}>
          {/* add a principle */}
          <div style={{ background: C.raised, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
            <div style={railLabel}>Add a principle</div>
            <textarea
              value={a.newPrinciple}
              onChange={(e) => a.setNewPrinciple(e.target.value)}
              rows={2}
              placeholder="Write it in your own words…"
              style={{ width: '100%', boxSizing: 'border-box', background: C.bg, border: `1px solid rgba(180,220,190,0.15)`, borderRadius: 8, padding: '11px 13px', font: `400 12.5px/1.5 ${SANS}`, color: C.textPrimary, marginBottom: 10, resize: 'none' }}
            />
            <div style={{ font: `400 11px/1.5 ${SANS}`, color: C.muted, marginBottom: 12 }}>
              The Partner restates it as an executable rule, backtests it against the last 90 days of decisions, and shows you what would have changed — before adopting it.
            </div>
            <span style={{ display: 'inline-block', ...goldBtn }} onClick={a.propose}>Propose</span>
          </div>

          {/* your proposal */}
          {a.proposed && (
            <div style={{ background: C.emphasis, border: `1px solid rgba(207,174,98,0.3)`, borderRadius: 10, padding: 16 }}>
              <div style={railGoldLabel}>Your proposal</div>
              <div style={{ font: `italic 400 13px/1.5 ${SERIF}`, color: C.textPrimary, marginBottom: 12 }}>"{a.proposed.text}"</div>
              {!a.proposed.done && (
                <>
                  <div style={{ display: 'flex', justifyContent: 'space-between', font: `400 11px ${MONO}`, color: C.muted, marginBottom: 6 }}>
                    <span>backtesting against your trades…</span>
                    <span>{a.proposed.progress}%</span>
                  </div>
                  <div style={{ height: 4, background: 'rgba(255,255,255,0.05)', borderRadius: 2 }}>
                    <div style={{ height: 4, borderRadius: 2, background: C.gold, transition: 'width .4s', width: a.proposed.progress + '%' }} />
                  </div>
                </>
              )}
              {a.proposed.done && a.proposed.result && (
                <>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, font: `400 11.5px ${SANS}`, color: C.secondary, marginBottom: 10 }}>
                    {statRow('Recent orders reviewed', String(a.proposed.result.trades_reviewed), C.textPrimary)}
                    {statRow('Would have changed', String(a.proposed.result.would_block), C.textPrimary)}
                    {a.proposed.result.pnl_effect && statRow('P&L effect', a.proposed.result.pnl_effect, C.gain)}
                    {a.proposed.result.drawdown_effect && statRow('Drawdown effect', a.proposed.result.drawdown_effect, C.gain)}
                  </div>
                  <div style={{ font: `400 11.5px/1.5 ${SANS}`, color: C.body, marginBottom: 12 }}>{a.proposed.result.verdict}</div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <span style={{ flex: 1, textAlign: 'center', ...goldBtn, padding: '8px 0' }} onClick={a.adoptProposed}>Adopt</span>
                    <span style={{ flex: 1, textAlign: 'center', ...outlineBtn, padding: '8px 0' }} onClick={a.discardProposed}>Discard</span>
                  </div>
                </>
              )}
            </div>
          )}

          {/* the latticework (real) */}
          <div style={{ background: C.raised, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
            <div style={{ ...railLabel, marginBottom: 12 }}>The Latticework</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, font: `400 11.5px ${SANS}`, color: C.secondary }}>
              {statRow('Active principles', String(a.shownCount), C.textPrimary)}
              {statRow('Total (incl. paused)', String(a.principleCount), C.body)}
            </div>
            <div style={{ font: `400 11px/1.5 ${SANS}`, color: C.muted, marginTop: 12 }}>Every active principle is fed to the Partner on each tick. Edit one and it reasons against the new wording immediately.</div>
          </div>
        </div>
      </div>
    </div>
  )
}
