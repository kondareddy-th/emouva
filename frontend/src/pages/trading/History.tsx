import { useAgent } from '../../hooks/useAgentStore'
import { C, SANS, MONO, SERIF, label, HIST_FILTERS } from '../../data/agentMockData'

/** Action badge — BUY (gold) / SELL (loss). */
function ActionBadge({ act }: { act: 'BUY' | 'SELL' }) {
  const bb = act === 'BUY' ? C.lightGold : C.lossBadge
  const bc = act === 'BUY' ? '#0C110E' : C.textPrimary
  return <span style={{ font: `600 9px ${SANS}`, letterSpacing: '.1em', padding: '3px 0', borderRadius: 4, textAlign: 'center', width: 44, color: bc, background: bb, textTransform: 'uppercase' }}>{act}</span>
}

function Stat({ name, children }: { name: React.ReactNode; children: React.ReactNode }) {
  return (
    <div>
      <div style={label()}>{name}</div>
      <div style={{ font: `500 22px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>{children}</div>
    </div>
  )
}

const statusColor: Record<string, string> = { filled: C.gain, placed: C.gold, rejected: C.loss, failed: C.loss }

export default function History() {
  const a = useAgent()
  const mob = a.isMobile
  const hf = a.histFilter

  const rows = a.trades.filter(
    (r) =>
      hf === 'All' ||
      (hf === 'Buys' && r.act === 'BUY') ||
      (hf === 'Sells' && r.act === 'SELL') ||
      (hf === 'Auto-executed' && r.auth === 'Auto') ||
      (hf === 'Approved by you' && r.auth === 'Approved by you'),
  )
  const buys = a.trades.filter((r) => r.act === 'BUY').length
  const sells = a.trades.filter((r) => r.act === 'SELL').length
  const auto = a.trades.filter((r) => r.auth === 'Auto').length

  const gridCols = '80px 68px minmax(200px,1fr) 130px 120px 30px'

  const histStatsStyle: React.CSSProperties = mob
    ? { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, padding: '18px 16px', borderBottom: `1px solid ${C.borderDim}`, background: C.raised }
    : { display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 16, padding: '20px 24px', borderBottom: `1px solid ${C.borderDim}`, background: C.raised }
  const histPadStyle: React.CSSProperties = mob ? { padding: '16px 16px 26px' } : { padding: '18px 24px 26px' }

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto' }}>
      {/* ── stat strip (real) ── */}
      <div style={histStatsStyle}>
        <div>
          <div style={label()}>Trades placed</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
            <span style={{ font: `500 22px ${SERIF}`, color: C.textPrimary }}>{a.trades.length}</span>
            <span style={{ font: `italic 400 12px ${SERIF}`, color: C.gold }}>few, by design</span>
          </div>
        </div>
        <Stat name="Realized P&amp;L">
          <span style={{ color: a.realizedPnl >= 0 ? C.gain : C.loss }}>{a.realizedPnl >= 0 ? '+' : '−'}${Math.abs(a.realizedPnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
        </Stat>
        <Stat name="Buys / Sells">{buys} / {sells}</Stat>
        <Stat name="Auto-executed">{auto}</Stat>
      </div>

      <div style={histPadStyle}>
        {/* ── filter pills ── */}
        <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
          {HIST_FILTERS.map((f) => {
            const on = hf === f
            return (
              <span
                key={f}
                onClick={() => a.setHistFilter(f)}
                style={on
                  ? { font: `500 11.5px ${SANS}`, color: C.bg, background: C.gold, padding: '6px 14px', borderRadius: 14, cursor: 'pointer', userSelect: 'none' }
                  : { font: `400 11.5px ${SANS}`, color: C.muted, border: `1px solid ${C.border}`, padding: '6px 14px', borderRadius: 14, cursor: 'pointer', userSelect: 'none', transition: 'border-color .15s' }}
              >
                {f}
              </span>
            )
          })}
        </div>

        {/* ── table ── */}
        <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 10, overflow: 'hidden' }}>
          {!mob && (
            <div style={{ display: 'grid', gridTemplateColumns: gridCols, padding: '9px 18px', borderBottom: `1px solid ${C.borderHeader}`, font: `500 9.5px ${SANS}`, letterSpacing: '.1em', color: C.faint, textTransform: 'uppercase' }}>
              <span>Date</span><span>Action</span><span>Order</span><span>Authorized</span><span>Status</span><span />
            </div>
          )}
          {rows.length === 0 && (
            <div style={{ padding: '28px 18px', textAlign: 'center', font: `400 12.5px ${SANS}`, color: C.muted }}>
              No trades yet — the Partner buys rarely, and only when something clears the funnel.
            </div>
          )}
          {rows.map((r) => {
            const open = !!a.expanded[r.id]
            const sc = statusColor[r.status] || C.muted
            return (
              <div key={r.id}>
                {!mob ? (
                  <div
                    onClick={() => a.toggleExpanded(r.id)}
                    style={{ display: 'grid', gridTemplateColumns: gridCols, padding: '12px 18px', font: `400 12px ${MONO}`, color: C.body, fontVariantNumeric: 'tabular-nums', alignItems: 'center', cursor: 'pointer', borderBottom: `1px solid ${C.borderRow}` }}
                  >
                    <span style={{ color: C.muted }}>{r.date}</span>
                    <ActionBadge act={r.act} />
                    <span style={{ paddingRight: 10 }}>{r.order}</span>
                    <span style={{ fontFamily: SANS, color: r.auth === 'Auto' ? C.muted : C.gold }}>{r.auth}</span>
                    <span style={{ fontFamily: SANS, color: sc, textTransform: 'capitalize' }}>{r.status}</span>
                    <span style={{ textAlign: 'right', flex: 'none', color: open ? C.gold : C.faint }}>{open ? '▴' : '▾'}</span>
                  </div>
                ) : (
                  <div onClick={() => a.toggleExpanded(r.id)} style={{ padding: '13px 14px', cursor: 'pointer', borderBottom: `1px solid ${C.borderRow}` }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: 6 }}>
                      <span style={{ font: `400 11px ${MONO}`, color: C.muted, flex: 'none' }}>{r.date}</span>
                      <ActionBadge act={r.act} />
                      <span style={{ textAlign: 'right', marginLeft: 'auto', font: `400 12px ${SANS}`, color: sc, textTransform: 'capitalize' }}>{r.status}</span>
                      <span style={{ flex: 'none', color: open ? C.gold : C.faint }}>{open ? '▴' : '▾'}</span>
                    </div>
                    <div style={{ font: `400 12px ${MONO}`, color: C.body, marginBottom: 4 }}>{r.order}</div>
                    <div style={{ font: `400 10.5px ${SANS}`, color: r.auth === 'Auto' ? C.muted : C.gold }}>{r.auth}</div>
                  </div>
                )}
                {open && r.rationale && (
                  <div style={{ padding: mob ? '4px 14px 16px' : '4px 18px 16px 110px' }}>
                    <div style={{ background: C.bg, border: `1px solid ${C.borderDim}`, borderRadius: 8, padding: '12px 14px' }}>
                      <div style={{ font: `500 9.5px ${SANS}`, letterSpacing: '.12em', color: C.faint, textTransform: 'uppercase', marginBottom: 6 }}>The Partner's reasoning</div>
                      <div style={{ font: `400 12px/1.55 ${SANS}`, color: C.secondary }}>{r.rationale}</div>
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div style={{ font: `400 11px ${SANS}`, color: C.faint, marginTop: 12 }}>Every row is a real order the Partner placed on the active account — traceable back to its Ledger entry.</div>
      </div>
    </div>
  )
}
