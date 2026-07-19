import { useNavigate } from 'react-router-dom'
import { useAgent } from '../../hooks/useAgentStore'
import { C, SANS, MONO, SERIF, label, RANGES, type Position } from '../../data/agentMockData'

const cardShell: React.CSSProperties = { background: C.card, border: `1px solid ${C.border}`, borderRadius: 10 }

function Stat({ name, value, color = C.textPrimary }: { name: string; value: string; color?: string }) {
  return (
    <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 9, padding: '11px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
      <span style={{ font: `400 11.5px ${SANS}`, color: C.muted }}>{name}</span>
      <span style={{ font: `500 15px ${SERIF}`, color }}>{value}</span>
    </div>
  )
}

function AllocRow({ name, pct, bar }: { name: string; pct: string; bar: string }) {
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', font: `400 11px ${SANS}`, color: C.secondary, marginBottom: 4 }}>
        <span>{name}</span>
        <span style={{ fontFamily: MONO }}>{pct}</span>
      </div>
      <div style={{ height: 5, background: 'rgba(255,255,255,0.05)', borderRadius: 3 }}>
        <div style={{ width: pct, height: 5, background: bar, borderRadius: 3 }} />
      </div>
    </div>
  )
}

const BARS = ['#CFAE62', '#BD9F58', '#95814D', '#746540']

function ThesisCard({ t }: { t: import('../../hooks/useAgentStore').Thesis }) {
  const survived = t.red_team.filter((r) => r.verdict === 'survives').length
  const trippedLabels = new Set(t.tripped.map((f) => f.label))
  const stColor = t.status === 'broken' ? C.loss : t.status === 'flashed' ? C.warning : C.gain
  return (
    <div style={{ background: C.card, border: `1px solid ${t.status === 'active' ? C.border : stColor}`, borderRadius: 10, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ font: `500 14px ${MONO}`, color: C.textPrimary }}>{t.symbol}</span>
        <span style={{ font: `500 9px ${SANS}`, letterSpacing: '.09em', textTransform: 'uppercase', color: stColor }}>{t.status}</span>
        <span style={{ marginLeft: 'auto', font: `400 10.5px ${MONO}`, color: survived >= 3 ? C.gain : C.loss }}>red-team {survived}/{t.red_team.length || 4}</span>
      </div>
      <div style={{ font: `400 12px/1.55 ${SANS}`, color: C.secondary, marginBottom: 12 }}>{t.thesis}</div>
      <div style={{ font: `500 9px ${SANS}`, letterSpacing: '.11em', color: C.faint, textTransform: 'uppercase', marginBottom: 6 }}>Falsifiers · downward triggers</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 12 }}>
        {t.falsifiers.map((f, i) => {
          const trip = trippedLabels.has(f.label)
          return (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline', font: `400 11.5px/1.4 ${SANS}`, color: trip ? C.loss : C.secondary }}>
              <span style={{ flex: 'none', color: trip ? C.loss : C.muted, font: `500 10px ${MONO}` }}>{trip ? '⚠' : '◇'}</span>
              <span>{f.label}</span>
            </div>
          )
        })}
      </div>
      <div style={{ font: `500 9px ${SANS}`, letterSpacing: '.11em', color: C.faint, textTransform: 'uppercase', marginBottom: 6 }}>Red-team it survived</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {t.red_team.map((r, i) => (
          <span key={i} style={{ font: `500 10px ${MONO}`, color: r.verdict === 'kills' ? C.loss : C.gain, border: `1px solid ${r.verdict === 'kills' ? C.redBorder : C.greenBorder}`, padding: '2px 8px', borderRadius: 5 }} title={r.attack}>
            {r.lens} {r.verdict === 'kills' ? '✕' : '✓'}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function Positions() {
  const a = useAgent()
  const nav = useNavigate()
  const mob = a.isMobile

  const rowGrid: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '74px minmax(120px,1fr) 48px 74px 74px 62px 84px 82px 66px 58px',
    padding: '11px 18px', font: `400 12px ${MONO}`, color: C.body,
    fontVariantNumeric: 'tabular-nums', alignItems: 'center', borderBottom: `1px solid ${C.borderRow}`,
  }
  const rt: React.CSSProperties = { textAlign: 'right' }
  const cardFor = (r: Position): React.CSSProperties => ({ padding: '13px 14px', borderBottom: `1px solid ${C.borderRow}`, ...(r.hl ? { background: C.goldTintRow } : {}) })

  // real allocation: top holdings by weight + cash
  const topAlloc = [...a.positions].sort((x, y) => parseFloat(y.w) - parseFloat(x.w)).slice(0, 4)
  const deltaColor = a.chart.has ? (a.chart.up ? C.gain : C.loss) : a.dayPnlColor
  const deltaText = a.chart.has ? a.chart.delta : `${a.dayPnl} · ${a.dayPct} today`

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto' }}>
      {/* ── header: net liquidity + chart | stat stack ── */}
      <div style={mob
        ? { display: 'flex', flexDirection: 'column', gap: 16, padding: '18px 16px 8px' }
        : { display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, padding: '24px 24px 16px' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ ...label(8), fontWeight: 500, fontSize: 10 }}>Net Liquidity</div>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginBottom: 14, flexWrap: 'wrap' }}>
            <span style={{ font: `500 38px ${SERIF}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.01em' }}>{a.hasAccount ? a.netLiq : '—'}</span>
            <span style={{ font: `500 13px ${MONO}`, color: deltaColor }}>{deltaText}</span>
            <div style={{ display: 'flex', gap: 2, marginLeft: 'auto' }}>
              {RANGES.map((r) => {
                const on = r === a.chartRange
                return (
                  <span key={r} onClick={() => a.setChartRange(r)}
                    style={{ font: `500 11px ${MONO}`, color: on ? C.bg : C.muted, background: on ? C.gold : undefined, padding: '4px 10px', borderRadius: 5, cursor: 'pointer', userSelect: 'none', transition: on ? undefined : 'color .15s' }}
                  >{r}</span>
                )
              })}
            </div>
          </div>
          <svg viewBox="0 0 860 120" preserveAspectRatio="none" style={{ width: '100%', height: 120, display: 'block' }}>
            <defs>
              <linearGradient id="goldfillP" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0" stopColor="#CFAE62" stopOpacity="0.22" />
                <stop offset="1" stopColor="#CFAE62" stopOpacity="0" />
              </linearGradient>
            </defs>
            {a.chart.has ? (
              <>
                <polygon points={`${a.chart.points} 860,120 0,120`} fill="url(#goldfillP)" />
                <polyline points={a.chart.points} fill="none" stroke={C.gold} strokeWidth={1.8} vectorEffect="non-scaling-stroke" />
              </>
            ) : (
              <line x1="0" y1="60" x2="860" y2="60" stroke="rgba(207,174,98,0.4)" strokeWidth={1.5} strokeDasharray="4 4" vectorEffect="non-scaling-stroke" />
            )}
            <line x1="0" y1="119" x2="860" y2="119" stroke="rgba(180,220,190,0.15)" strokeWidth={1} />
          </svg>
          {!a.chart.has && (
            <div style={{ font: `400 10.5px ${SANS}`, color: C.faint, marginTop: 6 }}>The value curve fills in as the Partner trades this account.</div>
          )}
        </div>
        <div style={mob
          ? { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }
          : { display: 'grid', gridTemplateRows: 'repeat(4,1fr)', gap: 10, paddingTop: 24 }}>
          <Stat name="Cash reserve" value={a.cashRow} />
          <Stat name="Open P&amp;L" value={a.openPnl} color={a.openPnlColor} />
          <Stat name="Day P&amp;L" value={`${a.dayPnl} · ${a.dayPct}`} color={a.dayPnlColor} />
          <Stat name="Holdings" value={String(a.positions.length)} />
        </div>
      </div>

      {/* ── body: table | rail ── */}
      <div style={mob
        ? { display: 'flex', flexDirection: 'column', gap: 16, padding: '10px 16px 26px' }
        : { display: 'grid', gridTemplateColumns: '1fr 300px', gap: 24, padding: '0 24px 26px' }}>
        {/* table card */}
        <div style={{ ...cardShell, overflow: 'hidden', minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 18px', borderBottom: `1px solid ${C.borderDim}`, gap: 10, flexWrap: 'wrap' }}>
            <span style={{ font: `500 16px ${SERIF}`, color: C.textPrimary }}>Positions</span>
            <span style={{ font: `400 11px ${SANS}`, color: C.faint }}>{a.positions.length} holdings on the active account</span>
          </div>

          {a.positions.length === 0 ? (
            <div style={{ padding: '30px 18px', textAlign: 'center', font: `400 12.5px ${SANS}`, color: C.muted }}>
              No positions yet. When the Partner buys, holdings appear here.
            </div>
          ) : !mob ? (
            <div style={{ overflowX: 'auto' }}>
              <div style={{ minWidth: 760 }}>
                <div style={{ display: 'grid', gridTemplateColumns: '74px minmax(120px,1fr) 48px 74px 74px 62px 84px 82px 66px 58px', padding: '8px 18px', borderBottom: `1px solid ${C.borderHeader}`, font: `500 9.5px ${SANS}`, letterSpacing: '.1em', color: C.faint, textTransform: 'uppercase' }}>
                  <span>Ticker</span><span>Company</span>
                  <span style={rt}>Qty</span><span style={rt}>Avg Cost</span><span style={rt}>Price</span>
                  <span style={rt}>Day</span><span style={rt}>Open P&amp;L</span><span style={rt}>Fair Value</span><span style={rt}>Margin</span><span style={rt}>Weight</span>
                </div>
                {a.positions.map((r) => (
                  <div key={r.t} style={{ ...rowGrid, ...(r.hl ? { background: C.goldTintRow } : {}) }}>
                    <span style={{ color: C.textPrimary, fontWeight: 500 }}>{r.t} {r.diamond && <span style={{ color: C.gold, fontSize: 10 }}>◆</span>}</span>
                    <span style={{ fontFamily: SANS, color: C.muted, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', paddingRight: 8 }}>{r.n}</span>
                    <span style={rt}>{r.q}</span>
                    <span style={rt}>{r.a}</span>
                    <span style={rt}>{r.p}</span>
                    <span style={{ ...rt, color: r.dc }}>{r.d}</span>
                    <span style={{ ...rt, color: r.plc }}>{r.pl}</span>
                    <span style={{ ...rt, color: C.lightGold }}>{r.fv}</span>
                    <span style={{ ...rt, color: r.mc }}>{r.m}</span>
                    <span style={rt}>{r.w}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {a.positions.map((r) => (
                <div key={r.t} style={cardFor(r)}>
                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 10, marginBottom: 2 }}>
                    <span style={{ font: `500 13.5px ${MONO}`, color: C.textPrimary }}>{r.t} {r.diamond && <span style={{ color: C.gold, fontSize: 10 }}>◆</span>}</span>
                    <span style={{ font: `500 12px ${MONO}`, color: r.plc }}>{r.pl}</span>
                  </div>
                  <div style={{ font: `400 11px ${SANS}`, color: C.muted, marginBottom: 8 }}>{r.n}</div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, font: `400 11px ${MONO}`, color: C.secondary, flexWrap: 'wrap' }}>
                    <span>{r.q} sh · ${r.p}</span>
                    <span style={{ color: r.dc }}>{r.d} today</span>
                    <span style={{ color: C.body }}>{r.w}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* right rail — real allocation + bands */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
          <div style={{ ...cardShell, padding: 16 }}>
            <div style={{ ...label(12), fontWeight: 500, fontSize: 10 }}>Allocation</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
              {topAlloc.map((p, i) => <AllocRow key={p.t} name={p.t} pct={p.w} bar={BARS[i]} />)}
              <AllocRow name="Cash" pct={a.cashAlloc} bar="#564B31" />
            </div>
          </div>

          <div style={{ ...cardShell, padding: 16 }}>
            <div style={{ ...label(10), fontWeight: 500, fontSize: 10 }}>Position Bands</div>
            <div style={{ display: 'flex', justifyContent: 'space-between', font: `400 11.5px ${SANS}`, color: C.secondary, marginBottom: 6 }}>
              <span>Weight ceiling</span><span style={{ fontFamily: MONO, color: C.textPrimary }}>{a.limits.maxPositionPct}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', font: `400 11.5px ${SANS}`, color: C.secondary, marginBottom: 6 }}>
              <span>Cash floor</span><span style={{ fontFamily: MONO, color: C.textPrimary }}>{a.limits.cashFloorPct}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', font: `400 11.5px ${SANS}`, color: C.secondary }}>
              <span>Sector cap</span><span style={{ fontFamily: MONO, color: C.textPrimary }}>{a.limits.sectorCapPct}</span>
            </div>
            <div style={{ height: 1, background: C.borderDim, margin: '12px 0' }} />
            <div style={{ font: `400 11.5px/1.5 ${SANS}`, color: C.muted }}>The Partner trims automatically if a position crosses its ceiling — you'll see it in the <span style={{ color: C.gold, cursor: 'pointer' }} onClick={() => nav('/trading')}>Ledger</span>.</div>
          </div>
        </div>
      </div>

      {/* ── Living Theses ── */}
      <div style={{ padding: mob ? '0 16px 26px' : '0 24px 30px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
          <span style={{ font: `500 16px ${SERIF}`, color: C.textPrimary }}>Living Theses</span>
          {a.theses.length > 0 && <span onClick={a.sweepTheses} style={{ font: `400 11px ${SANS}`, color: C.gold, cursor: 'pointer' }}>check every trigger now</span>}
        </div>
        <div style={mob ? { display: 'flex', flexDirection: 'column', gap: 14 } : { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
          {a.theses.map((t) => <ThesisCard key={t.id} t={t} />)}
          {a.positions.filter((p) => !a.theses.some((t) => t.symbol === p.t)).map((p) => (
            <div key={p.t} style={{ background: C.card, border: `1px dashed ${C.border}`, borderRadius: 10, padding: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <span style={{ font: `400 12px ${SANS}`, color: C.muted }}><span style={{ fontFamily: MONO, color: C.body }}>{p.t}</span> has no thesis yet.</span>
              <span onClick={() => { if (a.arming !== p.t) a.armThesis(p.t) }} style={{ font: `500 11.5px ${SANS}`, color: C.bg, background: a.arming === p.t ? C.muted : C.gold, padding: '7px 14px', borderRadius: 6, cursor: a.arming === p.t ? 'default' : 'pointer', whiteSpace: 'nowrap' }}>{a.arming === p.t ? 'Writing…' : 'Write thesis'}</span>
            </div>
          ))}
          {a.theses.length === 0 && a.positions.length === 0 && (
            <div style={{ font: `400 12px ${SANS}`, color: C.muted }}>Theses are written when the Partner buys or you approve a tracked idea.</div>
          )}
        </div>
      </div>
    </div>
  )
}
