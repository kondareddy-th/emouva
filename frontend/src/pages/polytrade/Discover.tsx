import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listThemes, type Theme } from '../../api/themes'
import { C, SANS, SERIF, MONO, Gauge, HealthPill, StatusChip, Tag, Card, money, pct, pctColor } from '../../components/polytrade/parts'

type Sort = 'conviction' | 'return' | 'funded' | 'trending'
const SORTS: { id: Sort; label: string; key: (t: Theme) => number }[] = [
  { id: 'trending', label: 'Trending', key: t => (t.n_investors || 0) * 2 + (t.n_followers || 0) + (t.n_comments || 0) },
  { id: 'conviction', label: 'Top conviction', key: t => t.conviction },
  { id: 'return', label: 'Best return', key: t => t.perf_snapshot?.since_inception_pct ?? -999 },
  { id: 'funded', label: 'Most funded', key: t => t.total_committed || 0 },
]

export default function Discover() {
  const [themes, setThemes] = useState<Theme[] | null>(null)
  const [err, setErr] = useState('')
  const [sort, setSort] = useState<Sort>('trending')
  const nav = useNavigate()

  useEffect(() => {
    let live = true
    listThemes().then(t => live && setThemes(t)).catch(e => live && setErr(String(e.message || 'Failed to load')))
    return () => { live = false }
  }, [])

  const sorted = useMemo(() => {
    const key = SORTS.find(s => s.id === sort)!.key
    return [...(themes || [])].sort((a, b) => key(b) - key(a))
  }, [themes, sort])

  return (
    <div>
      {/* hero header */}
      <div style={{ marginBottom: 22 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <div style={{ width: 6, height: 6, transform: 'rotate(45deg)', background: C.gold }} />
          <span style={{ font: `500 11px ${MONO}`, letterSpacing: '.16em', color: C.gold, textTransform: 'uppercase' }}>Thematic investing · auto-managed</span>
        </div>
        <h1 style={{ font: `500 34px ${SERIF}`, letterSpacing: '-.01em', margin: '0 0 6px', color: C.textPrimary }}>
          Back a thesis. <span style={{ color: C.lightGold }}>We trade it for you.</span>
        </h1>
        <p style={{ font: `400 14px ${SANS}`, color: C.secondary, maxWidth: 620, lineHeight: 1.55, margin: 0 }}>
          Each theme is a live conviction bet — an AI writes the thesis, picks the best names, and rebalances daily.
          Fund one in a tap; we auto-exit everyone the moment the thesis breaks.
        </p>
      </div>

      {/* sort rails */}
      {themes && themes.length > 0 && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 18, flexWrap: 'wrap' }}>
          {SORTS.map(s => {
            const on = s.id === sort
            return (
              <button key={s.id} onClick={() => setSort(s.id)} style={{
                font: `${on ? 600 : 400} 12px ${SANS}`, color: on ? '#0C110E' : C.secondary,
                background: on ? C.gold : 'rgba(255,255,255,0.04)', border: `1px solid ${on ? C.gold : C.borderDim}`,
                borderRadius: 999, padding: '6px 13px', cursor: 'pointer',
              }}>{s.label}</button>
            )
          })}
        </div>
      )}

      {err && <div style={{ font: `400 13px ${SANS}`, color: C.loss, marginBottom: 16 }}>{err}</div>}
      {!themes && !err && <div style={{ font: `400 13px ${SANS}`, color: C.muted }}>Loading themes…</div>}
      {themes && !themes.length && !err && (
        <div style={{ font: `400 13px ${SANS}`, color: C.muted }}>No live themes yet — check back soon.</div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 16 }}>
        {sorted.map(t => <ThemeTile key={t.id} t={t} onClick={() => nav(`/polytrade/${t.slug}`)} />)}
      </div>
    </div>
  )
}

function ThemeTile({ t, onClick }: { t: Theme; onClick: () => void }) {
  const since = t.perf_snapshot?.since_inception_pct
  const day = t.perf_snapshot?.day_pct
  const mine = t.my_allocation
  return (
    <Card hover onClick={onClick} style={{ display: 'flex', flexDirection: 'column', gap: 12, minHeight: 210 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>{(t.tags || []).slice(0, 3).map(x => <Tag key={x}>{x}</Tag>)}</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 'none' }}><StatusChip s={t.status} /><HealthPill h={t.health} /></div>
      </div>

      <div>
        <div style={{ font: `500 18px ${SERIF}`, color: C.textPrimary, lineHeight: 1.2, marginBottom: 4 }}>{t.title}</div>
        {t.hero_stat && <div style={{ font: `italic 400 13px ${SERIF}`, color: C.lightGold, lineHeight: 1.4 }}>“{t.hero_stat}”</div>}
      </div>

      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', font: `400 9.5px ${MONO}`, letterSpacing: '.1em', textTransform: 'uppercase', color: C.faint, marginBottom: 5 }}>
          <span>Conviction</span><span>{t.n_constituents ?? 0} names</span>
        </div>
        <Gauge v={t.conviction} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 18, marginTop: 'auto', paddingTop: 10, borderTop: `1px solid ${C.borderRow}` }}>
        <Stat label="Since basket" value={pct(since)} color={pctColor(since)} />
        <Stat label="Today" value={pct(day)} color={pctColor(day)} />
        <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
          <div style={{ font: `400 9.5px ${MONO}`, letterSpacing: '.08em', textTransform: 'uppercase', color: C.faint }}>
            {t.n_investors || 0} in · {money(t.total_committed)}{t.n_followers ? ` · ${t.n_followers} following` : ''}
          </div>
          {mine ? <div style={{ font: `500 11px ${SANS}`, color: C.gain, marginTop: 2 }}>You're in · {pct(mine.total_pnl_pct)}</div>
                : t.i_follow ? <div style={{ font: `500 11px ${SANS}`, color: C.lightGold, marginTop: 2 }}>Following · tap to fund →</div>
                : <div style={{ font: `500 11px ${SANS}`, color: C.gold, marginTop: 2 }}>Tap to fund →</div>}
        </div>
      </div>
    </Card>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <div style={{ font: `400 9.5px ${MONO}`, letterSpacing: '.08em', textTransform: 'uppercase', color: C.faint, marginBottom: 2 }}>{label}</div>
      <div style={{ font: `500 14px ${MONO}`, color, fontVariantNumeric: 'tabular-nums' }}>{value}</div>
    </div>
  )
}
