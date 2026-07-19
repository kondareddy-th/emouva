import { useEffect, useState, useCallback } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { myAllocations, unwindAllocation, type Allocation } from '../../api/themes'
import { C, SANS, SERIF, MONO, HealthPill, Card, money2, pct, pctColor } from '../../components/polytrade/parts'

export default function MyThemes() {
  const [allocs, setAllocs] = useState<Allocation[] | null>(null)
  const [err, setErr] = useState('')
  const nav = useNavigate()
  const load = useCallback(() => myAllocations().then(setAllocs).catch(e => setErr(String(e.message || 'Failed'))), [])
  useEffect(() => { load() }, [load])

  const open = (allocs || []).filter(a => a.status !== 'closed')
  const closed = (allocs || []).filter(a => a.status === 'closed')
  const totalValue = open.reduce((s, a) => s + (a.market_value || 0), 0)
  const totalCommitted = open.reduce((s, a) => s + a.committed_usd, 0)
  const totalPnl = totalValue - totalCommitted

  return (
    <div>
      <h1 style={{ font: `500 28px ${SERIF}`, margin: '0 0 4px', color: C.textPrimary }}>My Themes</h1>
      <p style={{ font: `400 13px ${SANS}`, color: C.muted, margin: '0 0 22px' }}>Your thematic positions — managed and rebalanced for you.</p>

      {err && <div style={{ font: `400 13px ${SANS}`, color: C.loss, marginBottom: 16 }}>{err}</div>}
      {!allocs && !err && <div style={{ font: `400 13px ${SANS}`, color: C.muted }}>Loading…</div>}

      {allocs && open.length > 0 && (
        <Card style={{ marginBottom: 20, display: 'flex', gap: 40 }}>
          <div><Lbl>Total value</Lbl><div style={{ font: `500 26px ${MONO}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>{money2(totalValue)}</div></div>
          <div><Lbl>Total P&L</Lbl><div style={{ font: `500 26px ${MONO}`, color: pctColor(totalPnl), fontVariantNumeric: 'tabular-nums' }}>{totalPnl >= 0 ? '+' : ''}{money2(totalPnl)}</div></div>
          <div><Lbl>Committed</Lbl><div style={{ font: `500 26px ${MONO}`, color: C.secondary, fontVariantNumeric: 'tabular-nums' }}>{money2(totalCommitted)}</div></div>
        </Card>
      )}

      {allocs && !open.length && !err && (
        <Card style={{ textAlign: 'center', padding: 40 }}>
          <div style={{ font: `400 14px ${SANS}`, color: C.secondary, marginBottom: 12 }}>You haven't funded any themes yet.</div>
          <Link to="/polytrade" style={{ font: `600 13px ${SANS}`, color: C.gold, textDecoration: 'none' }}>Discover themes →</Link>
        </Card>
      )}

      <div style={{ display: 'grid', gap: 14 }}>
        {open.map(a => <AllocRow key={a.id} a={a} onClick={() => a.theme && nav(`/polytrade/${a.theme.slug}`)} onDone={load} />)}
      </div>

      {closed.length > 0 && (
        <>
          <div style={{ font: `500 11px ${MONO}`, letterSpacing: '.1em', textTransform: 'uppercase', color: C.faint, margin: '26px 0 10px' }}>Closed</div>
          <div style={{ display: 'grid', gap: 10 }}>
            {closed.map(a => (
              <Card key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 16, opacity: 0.75 }}>
                <span style={{ font: `500 14px ${SERIF}`, color: C.body, flex: 1 }}>{a.theme?.title || 'Theme'}</span>
                <span style={{ font: `400 11px ${MONO}`, color: C.faint }}>{a.close_reason || 'closed'}</span>
                <span style={{ font: `500 13px ${MONO}`, color: pctColor(a.total_pnl) }}>{pct(a.total_pnl_pct)}</span>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function AllocRow({ a, onClick, onDone }: { a: Allocation; onClick: () => void; onDone: () => void }) {
  const [busy, setBusy] = useState(false)
  const exit = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Exit this theme? We sell the basket and return the cash.')) return
    setBusy(true)
    try { await unwindAllocation(a.id); onDone() } catch (err: any) { alert(String(err.message || 'Failed')); setBusy(false) }
  }
  return (
    <Card hover onClick={onClick} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ font: `500 16px ${SERIF}`, color: C.textPrimary }}>{a.theme?.title || 'Theme'}</span>
            {a.theme && <HealthPill h={a.theme.health} />}
            {a.status === 'pending' && <span style={{ font: `500 10px ${MONO}`, color: C.warning }}>INVESTING…</span>}
            {a.status === 'unwinding' && <span style={{ font: `500 10px ${MONO}`, color: C.loss }}>EXITING…</span>}
          </div>
          {a.theme?.hero_stat && <div style={{ font: `italic 400 12px ${SERIF}`, color: C.lightGold, marginTop: 2 }}>“{a.theme.hero_stat}”</div>}
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ font: `500 18px ${MONO}`, color: C.textPrimary, fontVariantNumeric: 'tabular-nums' }}>{money2(a.market_value)}</div>
          <div style={{ font: `500 12px ${MONO}`, color: pctColor(a.total_pnl) }}>{a.total_pnl != null && a.total_pnl >= 0 ? '▲' : '▼'} {money2(Math.abs(a.total_pnl || 0))} ({pct(a.total_pnl_pct)})</div>
        </div>
        <button onClick={exit} disabled={busy || (a.status !== 'active' && a.status !== 'pending')} style={{ background: 'transparent', color: C.loss, border: `1px solid ${C.redBorder}`, borderRadius: 8, padding: '7px 12px', font: `500 12px ${SANS}`, cursor: 'pointer', opacity: (busy || (a.status !== 'active' && a.status !== 'pending')) ? 0.4 : 1, flex: 'none' }}>Exit</button>
      </div>
      {(a.holdings || []).length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', paddingTop: 10, borderTop: `1px solid ${C.borderRow}` }}>
          {a.holdings!.map(h => (
            <div key={h.symbol} style={{ display: 'flex', alignItems: 'center', gap: 6, background: C.raised, border: `1px solid ${C.borderDim}`, borderRadius: 6, padding: '4px 8px' }}>
              <span style={{ font: `500 11px ${MONO}`, color: C.body }}>{h.symbol}</span>
              <span style={{ font: `400 11px ${MONO}`, color: pctColor(h.unrealized_pnl) }}>{money2(h.market_value)}</span>
            </div>
          ))}
          {a.cash > 0.5 && <div style={{ font: `400 11px ${MONO}`, color: C.faint, alignSelf: 'center' }}>+ {money2(a.cash)} cash</div>}
        </div>
      )}
    </Card>
  )
}

const Lbl = ({ children }: { children: React.ReactNode }) =>
  <div style={{ font: `500 10px ${MONO}`, letterSpacing: '.1em', textTransform: 'uppercase', color: C.faint, marginBottom: 4 }}>{children}</div>
