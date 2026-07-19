import { forwardRef } from 'react'

/* ══════════════════════════════════════════════════════════════════════
   PnlCard — a "Spotify Wrapped"-style shareable P&L snapshot. Rendered live
   in the community feed AND used as the capture target for the PNG download.
   Self-contained inline styles so it screenshots identically anywhere.
   ══════════════════════════════════════════════════════════════════════ */

export interface PnlStats {
  portfolioValue?: number
  totalReturnPct?: number
  totalGain?: number
  dayChangePct?: number
  positionsCount?: number
  topHolding?: string | null
  bestSymbol?: string | null
  bestPct?: number | null
  generatedAt?: string
  source?: string
}

const GOLD = '#cfae62'
const GAIN = '#7fe3a9'
const LOSS = '#f2937f'
const SERIF = "'EB Garamond', Georgia, serif"
const MONO = "'JetBrains Mono', ui-monospace, monospace"
const SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif"

const money = (n?: number) =>
  n == null ? '—' : '$' + Math.round(n).toLocaleString('en-US')
const pct = (n?: number | null) =>
  n == null ? '—' : `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(1)}%`
const col = (n?: number | null) => (n == null ? GOLD : n >= 0 ? GAIN : LOSS)

interface Props {
  stats: PnlStats
  author?: string | null
  handle?: string | null
}

const PnlCard = forwardRef<HTMLDivElement, Props>(({ stats, author, handle }, ref) => {
  const rc = col(stats.totalReturnPct)
  const when = stats.generatedAt ? new Date(stats.generatedAt) : null
  const dateStr = when
    ? when.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : ''

  return (
    <div
      ref={ref}
      style={{
        width: 380,
        maxWidth: '100%',
        borderRadius: 18,
        padding: '26px 26px 20px',
        background: 'radial-gradient(120% 90% at 15% 0%, #16211c 0%, #0c1114 55%, #0a0e0f 100%)',
        border: '1px solid rgba(207,174,98,0.28)',
        boxShadow: '0 24px 60px rgba(0,0,0,0.45)',
        color: '#eef4f2',
        fontFamily: SANS,
        boxSizing: 'border-box',
      }}
    >
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ width: 10, height: 10, background: GOLD, transform: 'rotate(45deg)', boxShadow: `0 0 14px ${GOLD}` }} />
          <span style={{ font: `600 12px ${SANS}`, letterSpacing: '0.24em', color: GOLD }}>EMOUVA</span>
        </div>
        <span style={{ font: `10px ${MONO}`, letterSpacing: '0.12em', color: 'rgba(238,244,242,0.5)' }}>MY P&amp;L</span>
      </div>

      {/* hero — total return */}
      <div style={{ font: `10px ${MONO}`, letterSpacing: '0.16em', color: 'rgba(238,244,242,0.5)', marginBottom: 4 }}>
        TOTAL RETURN
      </div>
      <div style={{ font: `600 62px ${SERIF}`, lineHeight: 1, color: rc, letterSpacing: '-0.02em' }}>
        {pct(stats.totalReturnPct)}
      </div>
      <div style={{ font: `13px ${MONO}`, color: 'rgba(238,244,242,0.65)', marginTop: 8 }}>
        {money(stats.portfolioValue)} portfolio ·{' '}
        <span style={{ color: col(stats.totalGain) }}>{stats.totalGain != null ? (stats.totalGain >= 0 ? '+' : '−') + money(Math.abs(stats.totalGain)).slice(1) : '—'}</span>{' '}
        all-time
      </div>

      {/* stat grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, margin: '22px 0 18px' }}>
        <Stat label="TODAY" value={pct(stats.dayChangePct)} color={col(stats.dayChangePct)} />
        <Stat label="POSITIONS" value={stats.positionsCount != null ? String(stats.positionsCount) : '—'} />
        <Stat label="TOP HOLDING" value={stats.topHolding || '—'} />
        <Stat
          label="BEST PERFORMER"
          value={stats.bestSymbol ? `${stats.bestSymbol} ${pct(stats.bestPct)}` : '—'}
          color={stats.bestPct != null ? col(stats.bestPct) : undefined}
        />
      </div>

      {/* footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderTop: '1px solid rgba(207,174,98,0.14)', paddingTop: 12 }}>
        <div style={{ font: `12px ${SANS}`, color: 'rgba(238,244,242,0.8)' }}>
          {author ? <span style={{ fontWeight: 600 }}>{author}</span> : 'An Emouva trader'}
          {handle && <span style={{ color: 'rgba(238,244,242,0.4)', fontFamily: MONO, fontSize: 11 }}> · {handle}</span>}
        </div>
        <span style={{ font: `10px ${MONO}`, color: GOLD, letterSpacing: '0.08em' }}>emouva.com</span>
      </div>
      {dateStr && (
        <div style={{ font: `9.5px ${MONO}`, color: 'rgba(238,244,242,0.35)', marginTop: 6, letterSpacing: '0.06em' }}>
          {dateStr} · not investment advice
        </div>
      )}
    </div>
  )
})

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(180,220,190,0.10)', borderRadius: 10, padding: '11px 13px' }}>
      <div style={{ font: `9px ${MONO}`, letterSpacing: '0.13em', color: 'rgba(238,244,242,0.45)', marginBottom: 5 }}>{label}</div>
      <div style={{ font: `600 16px ${SANS}`, color: color || '#eef4f2', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  )
}

PnlCard.displayName = 'PnlCard'
export default PnlCard
