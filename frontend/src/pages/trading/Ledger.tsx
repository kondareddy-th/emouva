import { useNavigate } from 'react-router-dom'
import { useAgent } from '../../hooks/useAgentStore'
import type { LedgerEntry } from '../../hooks/useAgentStore'
import { C, SANS, MONO, SERIF, label } from '../../data/agentMockData'
import { Dia } from '../../components/trading/primitives'

const goldBtn: React.CSSProperties = { font: `500 12px ${SANS}`, color: C.bg, background: C.gold, padding: '9px 20px', borderRadius: 6, cursor: 'pointer', transition: 'background .15s' }
const outlineBtn: React.CSSProperties = { font: `500 12px ${SANS}`, color: C.secondary, border: `1px solid ${C.goldBorder}`, padding: '9px 20px', borderRadius: 6, cursor: 'pointer', transition: 'border-color .15s' }
const p155 = (color = C.secondary): React.CSSProperties => ({ font: `400 12.5px/1.55 ${SANS}`, color })

function Badge({ text, bg, color, pulse }: { text: string; bg: string; color: string; pulse?: boolean }) {
  return <span className={pulse ? 'em-pulse' : undefined} style={{ font: `600 9.5px ${SANS}`, letterSpacing: '.11em', color, background: bg, padding: '3px 8px', borderRadius: 4 }}>{text}</span>
}
function Row({ time, children }: { time: string; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 14, padding: '16px 0', borderTop: `1px solid ${C.borderDim}` }}>
      <div style={{ width: 62, flex: 'none', paddingTop: 2 }}>
        <div style={{ font: `400 11px ${MONO}`, color: C.faint }}>{time}</div>
        <div style={{ font: `400 8.5px ${MONO}`, color: C.faint, letterSpacing: '.05em' }}>ET</div>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </div>
  )
}

// badge styling per ledger-entry type: [label, bg, color, pulse]
const BADGE: Record<string, [string, string, string, boolean]> = {
  awaiting: ['AWAITING APPROVAL', C.gold, C.bg, true],
  executed: ['EXECUTED', C.gain, C.bg, false],
  approved: ['APPROVED', C.gain, C.bg, false],
  declined: ['DECLINED BY YOU', 'rgba(255,255,255,0.07)', C.secondary, false],
  check: ['PORTFOLIO CHECK', 'rgba(255,255,255,0.05)', C.muted, false],
  pass: ['PASSED', 'rgba(255,255,255,0.05)', C.muted, false],
  screen: ['MORNING SCREEN', 'rgba(207,174,98,0.14)', C.lightGold, false],
  error: ['REVIEW FAILED', 'rgba(242,147,127,0.14)', C.loss, false],
  veto: ['DOUBLE-CHECK VETO', 'rgba(242,147,127,0.14)', C.loss, false],
  action: ['ACTION NEEDED', C.warning, C.bg, true],
  note: ['NOTE', 'rgba(255,255,255,0.05)', C.muted, false],
}

function inFilter(e: LedgerEntry, lf: string): boolean {
  if (lf === 'All') return true
  if (lf === 'Trades') return e.order_id != null || ['executed', 'approved', 'awaiting', 'declined'].includes(e.type)
  if (lf === 'Checks') return e.type === 'check'
  if (lf === 'Notes') return e.type === 'note' || e.type === 'error'
  return true
}

export default function Ledger() {
  const a = useAgent()
  const nav = useNavigate()
  const mob = a.isMobile
  const lf = a.ledgerFilter

  const metric = (name: string, value: React.ReactNode) => (
    <div>
      <div style={label()}>{name}</div>
      <div style={{ font: `500 24px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  )

  const po = a.pendingOrder
  const apprRailNote = a.apprApproved
    ? 'Nothing pending. Your last approval is in the Ledger.'
    : a.apprDeclined
      ? 'Nothing pending. You declined the last order — it stays on the watchlist.'
      : 'Nothing pending. The Partner has full discretion under ' + a.thresholdFmt + '.'

  const entries = a.ledgerEntries.filter((e) => inFilter(e, lf))
  // Surface an unresolved account-action prominently, regardless of the active filter.
  // Self-clearing: only shows while an 'action' entry is the most recent event — once the
  // Partner logs anything newer (e.g. a successful trade after setup), the banner disappears.
  const newest = a.ledgerEntries.reduce<LedgerEntry | null>((m, e) => (!m || +new Date(e.ts) > +new Date(m.ts) ? e : m), null)
  const actionBanner = newest && newest.type === 'action' ? newest : null
  const abMeta = (actionBanner?.meta || {}) as { action_url?: string; action_label?: string }

  const renderEntry = (e: LedgerEntry) => {
    const [bt, bbg, bcolor, pulse] = BADGE[e.type] || BADGE.note
    const time = new Date(e.ts).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
    const meta = (e.meta || {}) as { order_line?: string; action_url?: string; action_label?: string }
    if (e.type === 'action') {
      return (
        <Row key={e.id} time={time}>
          <div style={{ background: C.amberTint, border: `1px solid ${C.amberBorder}`, borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
              <Badge text={bt} bg={bbg} color={bcolor} pulse={pulse} />
              {e.title && <span style={{ font: `500 13px ${SANS}`, color: C.textPrimary }}>{e.title}</span>}
            </div>
            {e.body && <div style={{ ...p155(), marginBottom: meta.action_url ? 12 : 0 }}>{e.body}</div>}
            {meta.action_url && (
              <a href={meta.action_url} target="_blank" rel="noopener noreferrer" style={{ ...goldBtn, display: 'inline-block', textDecoration: 'none' }}>
                {meta.action_label || 'Complete setup'} →
              </a>
            )}
          </div>
        </Row>
      )
    }
    if (e.type === 'awaiting') {
      return (
        <Row key={e.id} time={time}>
          <div style={{ background: C.goldTint, border: `1px solid ${C.goldBorder}`, borderRadius: 8, padding: '14px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, flexWrap: 'wrap' }}>
              <Badge text={bt} bg={bbg} color={bcolor} pulse={pulse} />
            </div>
            {meta.order_line && <div style={{ font: `500 14px ${SANS}`, color: C.textPrimary, marginBottom: 6 }}>{meta.order_line}</div>}
            <div style={{ ...p155(), marginBottom: 12 }}>{e.body}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={goldBtn} onClick={a.approve}>Approve</span>
              <span style={outlineBtn} onClick={a.decline}>Decline</span>
              <span style={{ font: `400 11px ${SANS}`, color: C.faint, marginLeft: 'auto' }}>Also sent to your phone</span>
            </div>
          </div>
        </Row>
      )
    }
    return (
      <Row key={e.id} time={time}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6, flexWrap: 'wrap' }}>
          <Badge text={bt} bg={bbg} color={bcolor} />
          {meta.order_line
            ? <span style={{ font: `500 12px ${MONO}`, color: C.textPrimary }}>{meta.order_line}</span>
            : e.title && <span style={{ font: `500 12px ${SANS}`, color: C.textPrimary }}>{e.title}</span>}
        </div>
        {e.body && <div style={p155()}>{e.body}</div>}
      </Row>
    )
  }

  return (
    <div>
      {/* ── metric strip ── */}
      {!a.stripCollapsed ? (
        <div style={{ display: 'flex', alignItems: mob ? 'stretch' : 'center', gap: 16, padding: mob ? '14px 16px' : '16px 20px', borderBottom: `1px solid ${C.border}`, background: C.raised, flexDirection: mob ? 'column' : 'row' }}>
          <div style={{ flex: 1, display: 'grid', gridTemplateColumns: mob ? '1fr 1fr' : 'repeat(5,1fr)', gap: mob ? '14px 10px' : 20 }}>
            {metric('Net Liquidity', a.netLiq)}
            <div><div style={label()}>Day P&amp;L</div><div style={{ font: `500 24px ${SERIF}`, color: a.dayPnlColor, fontVariantNumeric: 'tabular-nums' }}>{a.dayPnl} <span style={{ font: `400 12px ${MONO}` }}>{a.dayPct}</span></div></div>
            <div><div style={label()}>Open P&amp;L</div><div style={{ font: `500 24px ${SERIF}`, color: a.openPnlColor, fontVariantNumeric: 'tabular-nums' }}>{a.openPnl}</div></div>
            {metric('Cash', a.cashPct)}
            <div>
              <div style={label()}>Risk Temperature</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ font: `500 24px ${SERIF}`, color: a.riskTemp.color }}>{a.riskTemp.label}</div>
                <div style={{ display: 'flex', gap: 2, alignItems: 'flex-end', paddingBottom: 3 }} title={`${Math.round(a.riskTemp.level * 100)}% — deployment + concentration`}>
                  {[7, 11, 15, 19].map((h, i) => <div key={i} style={{ width: 4, height: h, background: i < Math.round(a.riskTemp.level * 4) ? a.riskTemp.color : 'rgba(180,220,190,0.18)', borderRadius: 1 }} />)}
                </div>
              </div>
            </div>
          </div>
          <div onClick={a.toggleStrip} style={{ display: 'flex', alignItems: 'center', gap: 6, color: C.faint, font: `400 11px ${SANS}`, cursor: 'pointer', padding: '6px 10px', border: `1px solid ${C.border}`, borderRadius: 6, flex: 'none', alignSelf: mob ? 'flex-start' : 'auto' }}>Collapse <span style={{ fontSize: 9 }}>▲</span></div>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '12px 20px', borderBottom: `1px solid ${C.border}`, background: C.raised, flexWrap: 'wrap' }}>
          <span style={{ font: `500 18px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>{a.netLiq}</span>
          <span style={{ font: `400 12px ${MONO}`, color: a.dayPnlColor }}>{a.dayPnl} · {a.dayPct}</span>
          <span style={{ font: `400 12px ${SANS}`, color: C.muted }}>Cash {a.cashPct}</span>
          <div onClick={a.toggleStrip} style={{ display: 'flex', alignItems: 'center', gap: 6, color: C.faint, font: `400 11px ${SANS}`, cursor: 'pointer', padding: '5px 10px', border: `1px solid ${C.border}`, borderRadius: 6, marginLeft: 'auto' }}>Expand <span style={{ fontSize: 9 }}>▼</span></div>
        </div>
      )}

      <div style={{ display: mob ? 'flex' : 'grid', gridTemplateColumns: '1fr 340px', flexDirection: 'column' }}>
        {/* ── feed ── */}
        <div style={{ padding: mob ? '18px 16px' : '22px 24px', borderRight: mob ? undefined : `1px solid ${C.borderDim}`, borderBottom: mob ? `1px solid ${C.borderDim}` : undefined }}>
          <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 14, gap: 12, flexWrap: 'wrap' }}>
            <div style={{ font: `500 20px ${SERIF}`, color: C.textPrimary }}>The Ledger</div>
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {['All', 'Trades', 'Checks', 'Notes'].map((f) => {
                const on = lf === f
                return <span key={f} onClick={() => a.setLedgerFilter(f)} style={{ font: `${on ? 500 : 400} 11px ${SANS}`, color: on ? C.gold : C.faint, padding: '5px 10px', cursor: 'pointer', borderBottom: `1.5px solid ${on ? C.gold : 'transparent'}`, transition: 'color .15s' }}>{f}</span>
              })}
            </div>
          </div>

          {actionBanner && (
            <div className="em-pulse" style={{ display: 'flex', alignItems: 'center', gap: 14, flexWrap: 'wrap', background: C.amberTint, border: `1px solid ${C.amberBorder}`, borderRadius: 8, padding: '13px 16px', marginBottom: 16 }}>
              <div style={{ flex: 1, minWidth: 200 }}>
                <div style={{ font: `600 12px ${SANS}`, color: C.warning, letterSpacing: '.02em', marginBottom: 3 }}>{actionBanner.title}</div>
                <div style={{ font: `400 12px/1.5 ${SANS}`, color: C.secondary }}>{actionBanner.body}</div>
              </div>
              {abMeta.action_url && (
                <a href={abMeta.action_url} target="_blank" rel="noopener noreferrer" style={{ ...goldBtn, display: 'inline-block', textDecoration: 'none', flex: 'none' }}>
                  {abMeta.action_label || 'Complete setup'} →
                </a>
              )}
            </div>
          )}

          {entries.length === 0 ? (
            <div style={{ padding: '26px 0', borderTop: `1px solid ${C.borderDim}`, font: `400 13px/1.6 ${SANS}`, color: C.muted }}>
              The Partner hasn't logged anything on this account yet. It reviews on your cadence during market hours — or{' '}
              <span onClick={a.runNow} style={{ color: C.gold, cursor: 'pointer', textDecoration: 'underline', textUnderlineOffset: 3 }}>run a review now →</span>
            </div>
          ) : entries.map(renderEntry)}

          <div style={{ display: 'flex', gap: 14, padding: '14px 0', borderTop: `1px solid ${C.borderDim}` }}>
            <div style={{ width: 44, flex: 'none' }} />
            <div style={{ font: `400 11px ${SANS}`, color: C.faint }}>
              {a.ledgerEntries.length} {a.ledgerEntries.length === 1 ? 'entry' : 'entries'} ·{' '}
              <span onClick={() => nav('/trading/history')} style={{ color: C.muted, cursor: 'pointer', textDecoration: 'underline', textUnderlineOffset: 3 }}>older activity lives in History</span> ·{' '}
              <span onClick={a.runNow} style={{ color: C.gold, cursor: 'pointer' }}>run a review now →</span>
            </div>
          </div>
        </div>

        {/* ── right rail ── */}
        <div style={{ padding: mob ? '18px 16px' : '22px 20px', display: 'flex', flexDirection: 'column', gap: 16, background: C.raised }}>
          <div style={a.apprPending ? { background: C.emphasis, border: `1px solid ${C.goldBorder}`, borderRadius: 10, padding: 16 } : { background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ font: `500 10px ${SANS}`, letterSpacing: '.13em', color: C.gold, textTransform: 'uppercase' }}>Approvals</span>
              {a.apprPending && <span style={{ font: `500 10px ${MONO}`, color: C.bg, background: C.gold, padding: '2px 7px', borderRadius: 9 }}>1</span>}
            </div>
            {a.apprPending && po ? (
              <>
                <div style={{ font: `500 13px ${SANS}`, color: C.textPrimary, marginBottom: 3, textTransform: 'capitalize' }}>{po.side} {po.qty} {po.symbol} ≈ ${po.est_notional.toLocaleString('en-US', { maximumFractionDigits: 0 })}</div>
                <div style={{ font: `400 11.5px ${SANS}`, color: C.muted, marginBottom: 12 }}>Over {a.thresholdShort} limit · awaiting you</div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <span onClick={a.approve} style={{ flex: 1, textAlign: 'center', ...goldBtn, padding: '8px 0' }}>Approve</span>
                  <span onClick={a.decline} style={{ flex: 1, textAlign: 'center', ...outlineBtn, padding: '8px 0' }}>Decline</span>
                </div>
              </>
            ) : (
              <div style={{ font: `400 12px/1.55 ${SANS}`, color: C.muted }}>{apprRailNote}</div>
            )}
          </div>

          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ font: `500 10px ${SANS}`, letterSpacing: '.13em', color: C.faint, textTransform: 'uppercase' }}>Guiding Principles</span>
              <span onClick={() => nav('/trading/principles')} style={{ font: `400 11px ${SANS}`, color: C.gold, cursor: 'pointer' }}>Edit →</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {a.railPrinciples.map((p, i) => (
                <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'baseline' }}>
                  <Dia size={6} style={{ position: 'relative', top: -1 }} />
                  <div style={{ font: `italic 400 12.5px/1.45 ${SERIF}`, color: C.body }}>{p.text}</div>
                </div>
              ))}
            </div>
            <div style={{ font: `400 10.5px ${SANS}`, color: C.faint, marginTop: 12 }}>{a.principleCount} principles · {a.lastEdited}</div>
          </div>

          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ font: `500 10px ${SANS}`, letterSpacing: '.13em', color: C.faint, textTransform: 'uppercase' }}>Cadence</span>
              <span onClick={() => nav('/trading/settings')} style={{ font: `400 11px ${SANS}`, color: C.gold, cursor: 'pointer' }}>Adjust →</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
              <span style={{ font: `500 20px ${SERIF}`, color: C.textPrimary }}>{a.cadenceLabel}</span>
              <span style={{ font: `400 11px ${SANS}`, color: C.muted }}>market hours</span>
            </div>
            <div style={{ font: `400 11.5px ${MONO}`, color: C.muted }}>{a.nextCheckText}</div>
            <div style={{ height: 1, background: C.borderDim, margin: '12px 0' }} />
            <div style={{ font: `400 11.5px/1.5 ${SANS}`, color: C.muted }}>Low activity is the design, not a defect.</div>
          </div>

          {/* ── Account memory (read-only) ── */}
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span style={{ font: `500 10px ${SANS}`, letterSpacing: '.13em', color: C.faint, textTransform: 'uppercase' }}>Memory</span>
              <span style={{ font: `400 10px ${SANS}`, color: C.faint }}>what the Partner remembers</span>
            </div>
            {a.memory.long_term ? (
              <div style={{ font: `400 11.5px/1.55 ${SANS}`, color: C.body, whiteSpace: 'pre-wrap' }}>{a.memory.long_term}</div>
            ) : (
              <div style={{ font: `400 11.5px/1.5 ${SANS}`, color: C.muted }}>Building memory — consolidated weekly from this account's activity.</div>
            )}
            {a.memory.days.length > 0 && (
              <div style={{ marginTop: 12, borderTop: `1px solid ${C.borderDim}`, paddingTop: 10 }}>
                <div style={{ font: `500 9px ${SANS}`, letterSpacing: '.13em', color: C.faint, textTransform: 'uppercase', marginBottom: 6 }}>This week</div>
                {a.memory.days.map((d) => (
                  <div key={d.day} style={{ font: `400 11px/1.45 ${MONO}`, color: C.muted, marginBottom: 4 }}>
                    <span style={{ color: C.faint }}>{new Date(d.day + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}:</span> {d.summary}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
