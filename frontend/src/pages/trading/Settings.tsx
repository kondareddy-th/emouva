import { useEffect } from 'react'
import { useAgent } from '../../hooks/useAgentStore'
import { C, SERIF, MONO, SANS, CADENCES } from '../../data/agentMockData'
import { ToggleRow } from '../../components/trading/primitives'

const fmtDate = (s?: string | null) => s ? new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

const cardStyle: React.CSSProperties = {
  background: C.card,
  border: `1px solid ${C.border}`,
  borderRadius: 10,
  padding: '18px 20px',
}
const bodyText = (color = C.body): React.CSSProperties => ({ font: `400 12.5px ${SANS}`, color })

const SECTORS = ['Technology', 'Healthcare', 'Financial Services', 'Consumer Cyclical', 'Consumer Defensive',
  'Industrials', 'Energy', 'Utilities', 'Real Estate', 'Basic Materials', 'Communication Services']

/** Gold note box with a small rotated-square diamond marker. */
function GoldNote({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', background: C.goldTint, borderRadius: 8, padding: '10px 14px' }}>
      <div style={{ width: 6, height: 6, flex: 'none', background: C.gold, transform: 'rotate(45deg)', position: 'relative', top: -1 }} />
      <span style={{ font: `400 11.5px/1.5 ${SANS}`, color: C.secondary }}>{children}</span>
    </div>
  )
}

function CardLabel({ children, color = C.faint }: { children: React.ReactNode; color?: string }) {
  return <div style={{ font: `500 10px ${SANS}`, letterSpacing: '.13em', color, textTransform: 'uppercase', marginBottom: 14 }}>{children}</div>
}

export default function Settings() {
  const a = useAgent()
  const mob = a.isMobile

  const chipStyle: React.CSSProperties = {
    font: `500 14px ${MONO}`,
    color: C.textPrimary,
    background: C.bg,
    border: `1px solid ${C.goldBorder}`,
    padding: '5px 12px',
    borderRadius: 6,
  }
  const limitInputStyle: React.CSSProperties = {
    width: 78, textAlign: 'right', font: `500 14px ${MONO}`, color: C.textPrimary,
    background: C.bg, border: `1px solid ${C.goldBorder}`, borderRadius: 6, padding: '5px 8px', outline: 'none',
  }
  // editable hard-limit row. pre='$' shows a leading unit, suf='%' a trailing one.
  const editRow = (name: string, value: number, onChange: (v: number) => void, step: number, min: number, max: number, pre = '', suf = '') => (
    <div key={name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
      <span style={bodyText()}>{name}</span>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
        {pre && <span style={{ font: `500 13px ${MONO}`, color: C.faint }}>{pre}</span>}
        <input type="number" value={value} step={step} min={min} max={max}
          onChange={(e) => onChange(Math.max(min, Math.min(max, Number(e.target.value) || 0)))}
          style={limitInputStyle} />
        {suf && <span style={{ font: `500 13px ${MONO}`, color: C.faint }}>{suf}</span>}
      </div>
    </div>
  )
  const r1 = (v: number) => Math.round(v * 10) / 10   // 1-dp for the % fields
  const segBtn = (active: boolean, disabled = false): React.CSSProperties => ({
    flex: 1, minWidth: 150, cursor: disabled ? 'not-allowed' : 'pointer',
    padding: '11px 14px', borderRadius: 8, userSelect: 'none',
    background: active ? C.goldTint : C.bg,
    border: `1px solid ${active ? C.goldBorderStrong : C.border}`,
    opacity: disabled ? 0.5 : 1, transition: 'border-color .15s, background .15s',
  })

  return (
    <div style={{ maxWidth: 1440, margin: '0 auto' }}>
      {/* ── header ── */}
      <div style={{ padding: mob ? '18px 16px 0' : '24px 24px 4px' }}>
        <div style={{ font: `500 24px ${SERIF}`, color: C.textPrimary, marginBottom: 4 }}>The Mandate</div>
        <div style={{ font: `400 12.5px ${SANS}`, color: C.muted }}>What the Partner may do alone, when it must ask, and how often it looks.</div>
      </div>

      {/* ── Execution target: paper ↔ live (everything follows the account) ── */}
      <div style={{ padding: mob ? '14px 16px 0' : '16px 24px 0' }}>
        <div style={cardStyle}>
          <CardLabel>Execution — which account the Partner trades</CardLabel>
          <div style={{ display: 'flex', gap: 8, marginBottom: 14, flexWrap: 'wrap' }}>
            <div onClick={() => a.setMode('paper')} style={segBtn(a.mode === 'paper')}>
              <div style={{ font: `500 13px ${SANS}`, color: a.mode === 'paper' ? C.lightGold : C.body }}>Paper money</div>
              <div style={{ font: `400 10.5px ${MONO}`, color: C.faint, marginTop: 3 }}>{a.paperAccount || 'create in Risk › Settings'}</div>
            </div>
            <div
              onClick={() => (a.liveEnabled ? a.setMode('live') : a.pop("Live execution isn't enabled yet (pending order-schema verification)."))}
              style={segBtn(a.mode === 'live', !a.liveEnabled)}
            >
              <div style={{ font: `500 13px ${SANS}`, color: a.mode === 'live' ? C.lightGold : C.body }}>Live · Robinhood agentic</div>
              <div style={{ font: `400 10.5px ${MONO}`, color: C.faint, marginTop: 3 }}>
                {a.agenticAccount ? '••' + a.agenticAccount.slice(-4) : '—'}{!a.liveEnabled ? ' · not enabled yet' : ' · REAL money'}
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, marginBottom: 12 }}>
            <span style={bodyText()}>Max per live order · small-cap rollout</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, ...chipStyle, padding: '3px 10px' }}>
              <span style={{ color: C.faint }}>$</span>
              <input
                type="number" min={1} step={25} value={a.liveMaxNotional}
                onChange={(e) => a.setLiveMaxNotional(Math.max(1, Number(e.target.value) || 0))}
                style={{ width: 64, background: 'transparent', border: 'none', outline: 'none', font: `500 14px ${MONO}`, color: C.textPrimary, textAlign: 'right' }}
              />
            </div>
          </div>
          <GoldNote>
            {a.mode === 'live'
              ? `Live orders place on your Robinhood agentic account, capped at $${a.liveMaxNotional.toLocaleString()} each during rollout. Switching modes changes the positions, ledger, and approvals shown across the app.`
              : `Paper mode simulates fills against your book — no real money. Everything you see follows the account; switch to live when you're ready.`}
          </GoldNote>
          {a.tradingHalt && (
            <div style={{ marginTop: 8, font: `600 11px ${MONO}`, color: C.loss }}>⚠ Live trading is halted platform-wide right now.</div>
          )}
        </div>
      </div>

      {/* ── Circle of competence (sector allow / deny) ── */}
      <div style={{ padding: mob ? '14px 16px 0' : '16px 24px 0' }}>
        <div style={cardStyle}>
          <CardLabel>Circle of competence</CardLabel>
          <div style={{ ...bodyText(C.muted), marginBottom: 12 }}>
            Click a sector to cycle: <span style={{ color: C.gain }}>only-here</span> → <span style={{ color: C.loss }}>never-here</span> → neutral. Leave all neutral for no restriction.
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {SECTORS.map((sec) => {
              const inc = a.circleInclude.includes(sec)
              const exc = a.circleExclude.includes(sec)
              const cycle = () => {
                if (inc) a.setCircle(a.circleInclude.filter((s) => s !== sec), [...a.circleExclude, sec])
                else if (exc) a.setCircle(a.circleInclude, a.circleExclude.filter((s) => s !== sec))
                else a.setCircle([...a.circleInclude, sec], a.circleExclude)
              }
              const col = inc ? C.gain : exc ? C.loss : C.muted
              const bg = inc ? 'rgba(127,227,169,0.10)' : exc ? 'rgba(242,147,127,0.10)' : C.bg
              return (
                <span key={sec} onClick={cycle}
                  style={{ font: `500 11px ${SANS}`, color: col, background: bg, border: `1px solid ${inc ? C.greenBorder : exc ? C.redBorder : C.border}`, padding: '6px 11px', borderRadius: 7, cursor: 'pointer', userSelect: 'none', transition: 'border-color .15s' }}
                >{inc ? '✓ ' : exc ? '✕ ' : ''}{sec}</span>
              )
            })}
          </div>
        </div>
      </div>

      {/* ── 2×2 grid + full-width pause block ── */}
      <div style={{ display: mob ? 'flex' : 'grid', gridTemplateColumns: mob ? undefined : '1fr 1fr', flexDirection: mob ? 'column' : undefined, gap: 16, padding: mob ? '16px 16px 26px' : '20px 24px 26px' }}>
        {/* ── Autonomy ── */}
        <div style={cardStyle}>
          <CardLabel>Autonomy</CardLabel>
          <div style={{ marginBottom: 8 }}>
            <span style={bodyText()}>Ask my approval above</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8 }}>
            <span style={{ font: `500 18px ${SERIF}`, color: C.lightGold }}>$</span>
            <input
              type="number" min={0} step={500} value={a.threshold}
              onChange={(e) => a.setThreshold(Math.max(0, Number(e.target.value) || 0))}
              style={{ width: 150, background: C.bg, border: `1px solid ${C.goldBorder}`, borderRadius: 6, padding: '6px 11px', font: `500 18px ${SERIF}`, color: C.lightGold, outline: 'none', fontVariantNumeric: 'tabular-nums' }}
            />
          </div>
          <div style={{ font: `400 10.5px/1.5 ${SANS}`, color: C.faint, marginBottom: 14 }}>
            Orders at or below this place automatically; anything above comes to you for approval. Set $0 to approve everything.
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span style={bodyText()}>Required margin of safety</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 3, ...chipStyle, padding: '3px 10px' }}>
              <input
                type="number" min={0} max={90} step={5} value={a.marginOfSafety}
                onChange={(e) => a.setMarginOfSafety(Math.max(0, Math.min(90, Number(e.target.value) || 0)))}
                style={{ width: 40, background: 'transparent', border: 'none', outline: 'none', font: `500 14px ${MONO}`, color: C.textPrimary, textAlign: 'right' }}
              />
              <span style={{ color: C.faint }}>%</span>
            </div>
          </div>
          <div style={{ font: `400 10.5px/1.5 ${SANS}`, color: C.faint, marginBottom: 16 }}>
            The Partner won't buy unless the price is at least this far below a conservative fair value — and skips anything it can't value with confidence.
          </div>
          <div>
            <ToggleRow label="Always ask for brand-new positions" on={a.toggles.newPos} onClick={() => a.setToggle('newPos')} />
            <ToggleRow label="Always ask before selling at a loss" on={a.toggles.lossSales} onClick={() => a.setToggle('lossSales')} />
            <ToggleRow label="Double-check before buying" on={a.toggles.doubleCheck} onClick={() => a.setToggle('doubleCheck')} />
            <ToggleRow label="Options & leverage" disabled chip="OUTSIDE MANDATE" />
          </div>
          <div style={{ marginTop: 14 }}>
            <GoldNote>Anything above {a.thresholdFmt} — and every brand-new name — comes to you as a message on your phone and a card in the Ledger.</GoldNote>
          </div>
        </div>

        {/* ── Cadence ── */}
        <div style={cardStyle}>
          <CardLabel>Cadence</CardLabel>
          <div style={{ ...bodyText(), marginBottom: 10 }}>Check the portfolio every</div>
          <div style={{ display: 'flex', gap: 6, marginBottom: 12, flexWrap: 'wrap' }}>
            {CADENCES.map((c) => {
              const on = c === a.cadence
              const locked = c !== '1h'      // for now the platform runs on a fixed hourly review
              return (
                <span
                  key={c}
                  onClick={locked ? undefined : () => a.setCadence(c)}
                  title={locked ? 'Hourly review is the default while we scale — other cadences coming soon' : undefined}
                  style={locked
                    ? { font: `500 12px ${MONO}`, color: C.faint, border: `1px solid ${C.border}`, padding: '8px 14px', borderRadius: 7, cursor: 'not-allowed', userSelect: 'none', opacity: 0.4 }
                    : on
                      ? { font: `500 12px ${MONO}`, color: C.bg, background: C.gold, padding: '8px 14px', borderRadius: 7, cursor: 'pointer', userSelect: 'none' }
                      : { font: `500 12px ${MONO}`, color: C.muted, border: `1px solid ${C.border}`, padding: '8px 14px', borderRadius: 7, cursor: 'pointer', userSelect: 'none', transition: 'border-color .15s' }}
                >
                  {c}
                </span>
              )
            })}
          </div>
          <div style={{ font: `400 11.5px ${MONO}`, color: C.muted, marginBottom: 12 }}>{a.nextCheckText}</div>
          <div style={{ marginBottom: 14 }}>
            <GoldNote>The Partner reviews every position once an hour through the trading day, starting an hour before the open. Checking more often doesn't earn more — it just finds more reasons to act.</GoldNote>
          </div>
          <div>
            <ToggleRow label="Intraday checks on portfolio earnings days" on={a.toggles.earnDays} onClick={() => a.setToggle('earnDays')} />
            <ToggleRow label="After-hours monitoring" on={a.toggles.afterHours} onClick={() => a.setToggle('afterHours')} />
          </div>
        </div>

        {/* ── Hard limits ── */}
        <div style={cardStyle}>
          <CardLabel>Hard limits</CardLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {editRow('Max position weight', r1(a.hardLimits.maxPositionPct * 100), (v) => a.setHardLimit('max_position_pct', v / 100), 0.5, 1, 100, '', '%')}
            {editRow('Cash floor', r1(a.hardLimits.cashFloorPct * 100), (v) => a.setHardLimit('cash_floor_pct', v / 100), 1, 0, 90, '', '%')}
            {editRow('Max orders per week', a.hardLimits.maxOrdersWeek, (v) => a.setHardLimit('max_orders_week', Math.round(v)), 1, 1, 50)}
            {editRow('Single-day deployment cap', Math.round(a.hardLimits.dailyCap), (v) => a.setHardLimit('daily_spend_cap_usd', v), 1000, 0, 100000000, '$')}
            {editRow('Sector cap', r1(a.hardLimits.sectorCapPct * 100), (v) => a.setHardLimit('sector_cap_pct', v / 100), 1, 1, 100, '', '%')}
            {editRow('Catastrophic review', r1(a.hardLimits.catastrophicStopPct * 100), (v) => a.setHardLimit('catastrophic_stop_pct', v / 100), 5, 0, 90, '', '%')}
          </div>
          <div style={{ font: `400 11px/1.5 ${SANS}`, color: C.faint, marginTop: 14 }}>Enforced as hard caps — the Partner cannot cross them even with your approval on a single order. Set them to fit your style: a concentrated book of a few names needs a higher max position weight (e.g. 5 stocks → ~20%).</div>
          <div style={{ font: `400 11px/1.5 ${SANS}`, color: C.faint, marginTop: 8 }}><strong style={{ color: C.muted }}>Catastrophic review</strong> is NOT a stop-loss. A holding down this much from cost forces the Partner to re-examine the thesis on fresh data and propose an exit <em>only if it can't reaffirm the story</em> — a big paper loss alone is never a sell reason, a broken thesis is. Deliberately wide (default 30%); set to 0 to turn it off.</div>
        </div>

        {/* ── right column: Notifications + Pause ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div style={cardStyle}>
            <CardLabel>Notifications</CardLabel>
            <div>
              <ToggleRow label="Message to phone for approvals" on={a.toggles.phone} onClick={() => a.setToggle('phone')} />
              <ToggleRow label="In-app approvals queue" on={a.toggles.queue} onClick={() => a.setToggle('queue')} />
              <ToggleRow label="Daily P&amp;L push" on={a.toggles.daily} onClick={() => a.setToggle('daily')} sub="off by default; watching daily P&L breeds twitchiness" />
            </div>
          </div>

          {/* ── Pause ── */}
          <div style={{ ...cardStyle, border: `1px solid ${C.redBorder}` }}>
            <CardLabel color={C.loss}>Pause</CardLabel>
            {!a.paused && !a.pauseConfirm && (
              <>
                <div style={{ font: `400 12px/1.55 ${SANS}`, color: C.secondary, marginBottom: 12 }}>Pausing stops all trading immediately. The Partner keeps watching and writing to the Ledger. Liquidation requires a typed confirmation and a 24-hour cooling-off period — panic is not a strategy.</div>
                <span onClick={a.askPause} style={{ display: 'inline-block', font: `500 12px ${SANS}`, color: C.loss, border: '1px solid rgba(242,147,127,0.4)', padding: '9px 16px', borderRadius: 6, cursor: 'pointer', transition: 'background .15s' }}>Pause the Partner</span>
              </>
            )}
            {a.pauseConfirm && (
              <>
                <div style={{ font: `400 12.5px/1.55 ${SANS}`, color: C.body, marginBottom: 12 }}>Pause all trading now? Watching and the Ledger continue. You can resume any time.</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <span onClick={a.confirmPause} style={{ font: `500 12px ${SANS}`, color: C.textPrimary, background: C.lossBadge, padding: '9px 16px', borderRadius: 6, cursor: 'pointer' }}>Yes, pause trading</span>
                  <span onClick={a.cancelPause} style={{ font: `500 12px ${SANS}`, color: C.secondary, border: `1px solid ${C.goldBorder}`, padding: '9px 16px', borderRadius: 6, cursor: 'pointer' }}>Keep trading</span>
                </div>
              </>
            )}
            {a.paused && (
              <>
                <div style={{ font: `400 12px/1.55 ${SANS}`, color: C.secondary, marginBottom: 12 }}>Paused since 11:06 ET. The Partner is still watching, still writing to the Ledger — just not trading. No checks are scheduled.</div>
                <span onClick={a.resume} style={{ display: 'inline-block', font: `500 12px ${SANS}`, color: C.bg, background: C.gold, padding: '9px 16px', borderRadius: 6, cursor: 'pointer', transition: 'background .15s' }}>Resume the Partner</span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── Live-trading T&C modal (first live enable) ── */}
      {a.tcModal && (
        <div style={{ position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.62)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20 }}>
          <div className="em-fade" style={{ maxWidth: 560, width: '100%', maxHeight: '86vh', overflow: 'auto', background: C.card, border: `1px solid ${C.goldBorder}`, borderRadius: 12, padding: mob ? 20 : 26 }}>
            <div style={{ font: `500 19px ${SERIF}`, color: C.textPrimary, marginBottom: 4 }}>{a.tcModal.title}</div>
            <div style={{ font: `400 10px ${MONO}`, color: C.faint, letterSpacing: '.1em', textTransform: 'uppercase', marginBottom: 14 }}>Version {a.tcModal.version}</div>
            <div style={{ font: `400 12.5px/1.65 ${SANS}`, color: C.body, whiteSpace: 'pre-wrap', marginBottom: 18 }}>{a.tcModal.text}</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <span onClick={a.acceptTc} style={{ font: `500 13px ${SANS}`, color: C.bg, background: C.gold, padding: '10px 20px', borderRadius: 7, cursor: 'pointer' }}>I agree — enable live</span>
              <span onClick={a.declineTc} style={{ font: `500 13px ${SANS}`, color: C.secondary, border: `1px solid ${C.goldBorder}`, padding: '10px 20px', borderRadius: 7, cursor: 'pointer' }}>Decline — stay on paper</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
