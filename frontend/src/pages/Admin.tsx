import { useEffect, useState, useCallback, useMemo } from 'react'

const TOKEN_KEY = 'emouva_admin_token'
const API = (import.meta as any).env?.VITE_API_URL || ''

async function adminFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem(TOKEN_KEY)
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(opts.headers || {}) },
  })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `${res.status}`)
  return res.json()
}

interface Opp {
  symbol: string; name: string; sector: string; category: number | null; margin_pct: number | null
  fair_value: number | null; fv_low: number | null; fv_high: number | null; confident: boolean
  thesis: string | null; falsifiers: any[]; red_team: any[]; growth: string | null; future_growth: string | null
  growth_exception: boolean; understood: boolean | null
  admin_notes: string | null; analysis_status: string; stats: Record<string, any> | null; last_price: number | null
  score: number | null; sector_rank: number | null
  score_breakdown: {
    total: number; base?: number; weights: { quality: number; durability: number; margin: number }
    penalty?: { factor: number; weak: string[]; floor: number }
    quality: { score: number; inputs: Record<string, any> }
    durability: { score: number; inputs: Record<string, any> }
    margin: { score: number; inputs: Record<string, any> }
  } | null
  news: { checked_at?: string; headlines?: string[]; material?: boolean; sentiment?: string; severity?: string; note?: string; needs_review?: boolean } | null
  trend: { status: string; score: number | null; summary?: string; at?: string } | null
}
interface AdminAcct { id: string; email: string; name: string; status: string; is_root: boolean }

export default function Admin() {
  const [token, setToken] = useState<string | null>(localStorage.getItem(TOKEN_KEY))
  const [me, setMe] = useState<AdminAcct | null>(null)
  const [tab, setTab] = useState<'directory' | 'themes' | 'admins'>('directory')

  const logout = () => { localStorage.removeItem(TOKEN_KEY); setToken(null); setMe(null) }
  useEffect(() => {
    if (token) adminFetch<AdminAcct>('/api/admin/me').then(setMe).catch(() => logout())
  }, [token])

  if (!token || !me) return <Login onToken={(t) => { localStorage.setItem(TOKEN_KEY, t); setToken(t) }} />

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <div className="sticky top-0 z-20 bg-base/90 backdrop-blur border-b border-[rgba(180,220,190,0.1)] flex items-center justify-between px-6 h-14">
        <div className="flex items-center gap-4">
          <span className="font-serif text-[17px]">◆ Emouva Admin</span>
          <span className="text-[11px] font-mono uppercase tracking-widest text-warning">compliance · audit</span>
        </div>
        <div className="flex items-center gap-4">
          {(['directory', 'themes', 'admins'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`text-[13px] ${tab === t ? 'text-accent' : 'text-text-tertiary'}`}>{t}</button>
          ))}
          <span className="text-[12px] font-mono text-text-tertiary">{me.email}</span>
          <button onClick={logout} className="text-[12px] text-loss">sign out</button>
        </div>
      </div>
      {tab === 'directory' ? <Directory /> : tab === 'themes' ? <Themes /> : <Admins meRoot={me.is_root} />}
    </div>
  )
}

function Login({ onToken }: { onToken: (t: string) => void }) {
  const [email, setEmail] = useState(''); const [pw, setPw] = useState(''); const [err, setErr] = useState(''); const [mode, setMode] = useState<'login' | 'signup'>('login')
  const submit = async () => {
    setErr('')
    try {
      if (mode === 'login') { const r = await adminFetch<{ token: string }>('/api/admin/login', { method: 'POST', body: JSON.stringify({ email, password: pw }) }); onToken(r.token) }
      else { await adminFetch('/api/admin/signup', { method: 'POST', body: JSON.stringify({ email, password: pw }) }); setErr('Request submitted — awaiting approval by an admin.'); setMode('login') }
    } catch (e: any) { setErr(String(e.message || 'Failed')) }
  }
  return (
    <div className="min-h-screen bg-base text-text-primary flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="font-serif text-[24px] mb-1">◆ Emouva Admin</div>
        <div className="text-[12px] text-text-tertiary mb-6">{mode === 'login' ? 'Sign in to the console' : 'Request admin access'}</div>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" className="w-full mb-3 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-2.5 text-[14px] outline-none" />
        <input value={pw} onChange={(e) => setPw(e.target.value)} type="password" placeholder="password" onKeyDown={(e) => e.key === 'Enter' && submit()} className="w-full mb-3 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-2.5 text-[14px] outline-none" />
        {err && <div className="text-[12px] text-warning mb-3">{err}</div>}
        <button onClick={submit} className="w-full bg-accent text-base font-medium rounded-md py-2.5 text-[14px] mb-3">{mode === 'login' ? 'Sign in' : 'Request access'}</button>
        <button onClick={() => { setMode(mode === 'login' ? 'signup' : 'login'); setErr('') }} className="text-[12px] text-text-tertiary">{mode === 'login' ? 'Request admin access →' : '← Back to sign in'}</button>
      </div>
    </div>
  )
}

const CAT_LABEL: Record<string, string> = { '1': 'Confident', '3': 'Watch — overpriced', '2': 'Hard to understand', '0': 'Rejected', 'null': 'Unanalyzed' }
const catColor = (c: number | null) => c === 1 ? 'text-gain' : c === 3 ? 'text-warning' : c === 2 ? 'text-accent' : c === 0 ? 'text-loss' : 'text-text-tertiary'

// fraction (0.18) → "18%"; already-percent margin handled separately
const pctF = (v: any) => v == null ? '—' : `${(v * 100).toFixed(0)}%`
const num = (v: any) => v == null ? '—' : Number(v).toFixed(v != null && Math.abs(v) < 100 ? 1 : 0)
const marginFmt = (v: number | null) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(0)}%`

// fundamental metrics we store per stock — shown in the detail grid
const METRICS: [string, string, 'pct' | 'num'][] = [
  ['ROE', 'return_on_equity', 'pct'], ['ROA', 'return_on_assets', 'pct'],
  ['Gross margin', 'gross_margins', 'pct'], ['Op margin', 'operating_margins', 'pct'],
  ['Profit margin', 'profit_margins', 'pct'], ['Revenue growth', 'revenue_growth', 'pct'],
  ['Earnings growth', 'earnings_growth', 'pct'], ['P/E', 'pe_ratio', 'num'],
  ['Forward P/E', 'forward_pe', 'num'], ['PEG', 'peg_ratio', 'num'],
  ['Debt/Equity', 'debt_to_equity', 'num'], ['Current ratio', 'current_ratio', 'num'],
]

type SortKey = 'symbol' | 'name' | 'sector' | 'score' | 'quality' | 'durability' | 'value' | 'roe' | 'profit' | 'revgr' | 'margin' | 'trend' | 'rank' | 'category'
const sortVal = (o: Opp, k: SortKey): number | string => {
  switch (k) {
    case 'symbol': return o.symbol
    case 'name': return o.name || ''
    case 'sector': return o.sector || 'zzz'
    case 'score': return o.score ?? -1
    case 'quality': return o.score_breakdown?.quality.score ?? -1
    case 'durability': return o.score_breakdown?.durability.score ?? -1
    case 'value': return o.score_breakdown?.margin.score ?? -1
    case 'roe': return o.stats?.return_on_equity ?? -Infinity
    case 'profit': return o.stats?.profit_margins ?? -Infinity
    case 'revgr': return o.stats?.revenue_growth ?? -Infinity
    case 'margin': return o.margin_pct ?? -Infinity
    case 'trend': return o.trend?.score ?? -1
    case 'rank': return o.sector_rank ?? 9999
    case 'category': return o.category ?? -1
  }
}

// falling knife → loss, basing → warning, rising → gain, stable → neutral
const TREND_STYLE: Record<string, string> = {
  falling: 'bg-loss/15 text-loss', basing: 'bg-warning/15 text-warning',
  rising: 'bg-gain/15 text-gain', stable: 'text-text-tertiary',
}
const trendBadge = (t: Opp['trend']): React.ReactNode => {
  if (!t || !t.status || t.status === 'unknown') return <span className="text-text-tertiary text-[11px]">—</span>
  return <span title={t.summary || ''} className={`text-[10px] px-1.5 py-0.5 rounded ${TREND_STYLE[t.status] || 'text-text-tertiary'}`}>{t.status}</span>
}

// [label, key, width, align, render]
const COLS: [string, SortKey, string, 'left' | 'right', (o: Opp) => React.ReactNode][] = [
  ['Symbol', 'symbol', 'w-16', 'left', (o) => <span className="font-mono text-[13px]">{o.symbol}</span>],
  ['Company', 'name', 'flex-1 min-w-[120px]', 'left', (o) => <span className="text-[12px] text-text-secondary truncate flex items-center gap-1.5">{o.name}{o.news?.needs_review ? <span title={o.news.note || ''} className="text-loss text-[10px] flex-none">⚠ news</span> : o.news?.material ? <span title={o.news.note || ''} className="text-warning text-[10px] flex-none">• news</span> : o.news ? <span title={o.news.note || 'recent news — judged not thesis-relevant'} className="text-text-tertiary text-[10px] flex-none">news</span> : null}</span>],
  ['Sector', 'sector', 'w-32', 'left', (o) => <span className="text-[11px] text-text-tertiary truncate">{o.sector || '—'}</span>],
  ['Score', 'score', 'w-16', 'right', (o) => <span className="font-mono text-[12px] text-text-primary font-semibold">{o.score == null ? '—' : o.score.toFixed(0)}</span>],
  ['Rank', 'rank', 'w-12', 'right', (o) => <span className="font-mono text-[11px] text-text-tertiary">{o.sector_rank ? `#${o.sector_rank}` : '—'}</span>],
  ['Qual', 'quality', 'w-12', 'right', (o) => <span className="font-mono text-[11px] text-text-secondary">{o.score_breakdown ? o.score_breakdown.quality.score.toFixed(0) : '—'}</span>],
  ['Dura', 'durability', 'w-12', 'right', (o) => <span className="font-mono text-[11px] text-text-secondary">{o.score_breakdown ? o.score_breakdown.durability.score.toFixed(0) : '—'}</span>],
  ['Val', 'value', 'w-12', 'right', (o) => <span className="font-mono text-[11px] text-text-secondary">{o.score_breakdown ? o.score_breakdown.margin.score.toFixed(0) : '—'}</span>],
  ['ROE', 'roe', 'w-14', 'right', (o) => <span className="font-mono text-[11px] text-text-secondary">{pctF(o.stats?.return_on_equity)}</span>],
  ['Profit', 'profit', 'w-14', 'right', (o) => <span className="font-mono text-[11px] text-text-secondary">{pctF(o.stats?.profit_margins)}</span>],
  ['Rev gr', 'revgr', 'w-14', 'right', (o) => <span className={`font-mono text-[11px] ${(o.stats?.revenue_growth ?? 0) < 0 ? 'text-loss' : 'text-text-secondary'}`}>{pctF(o.stats?.revenue_growth)}</span>],
  ['Margin', 'margin', 'w-16', 'right', (o) => <span className={`font-mono text-[12px] ${o.margin_pct == null ? 'text-text-tertiary' : o.margin_pct >= 0 ? 'text-gain' : 'text-loss'}`}>{marginFmt(o.margin_pct)}</span>],
  ['Trend', 'trend', 'w-16', 'right', (o) => trendBadge(o.trend)],
  ['Status', 'category', 'w-24', 'right', (o) => <span className={`text-[10px] ${catColor(o.category)}`}>{o.growth_exception ? '◆ ' : ''}{o.category == null ? '·' : CAT_LABEL[String(o.category)]}</span>],
]

// Styled multi-select sector filter — native <select> options can't be dark-themed and
// don't multi-select, so this is a custom dropdown (checkbox list, click-outside to close).
function SectorFilter({ all, selected, onToggle, onClear }: { all: string[]; selected: Set<string>; onToggle: (s: string) => void; onClear: () => void }) {
  const [open, setOpen] = useState(false)
  const label = selected.size === 0 ? 'All sectors' : `${selected.size} sector${selected.size > 1 ? 's' : ''}`
  return (
    <div className="relative">
      <button onClick={() => setOpen((o) => !o)} className={`bg-surface-2 border rounded-md px-3 py-1.5 text-[12px] flex items-center gap-2 ${selected.size ? 'text-text-primary border-accent/40' : 'text-text-secondary border-[rgba(180,220,190,0.12)]'} hover:border-[rgba(180,220,190,0.3)]`}>
        {label} <span className="text-[8px] text-text-tertiary">▼</span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute right-0 mt-1 z-30 w-56 max-h-80 overflow-auto bg-surface-2 border border-[rgba(180,220,190,0.18)] rounded-lg shadow-2xl py-1">
            <button onClick={onClear} className={`w-full text-left px-3 py-1.5 text-[12px] hover:bg-[rgba(180,220,190,0.06)] ${selected.size === 0 ? 'text-accent' : 'text-text-secondary'}`}>All sectors</button>
            <div className="h-px bg-[rgba(180,220,190,0.08)] my-1" />
            {all.map((s) => {
              const on = selected.has(s)
              return (
                <button key={s} onClick={() => onToggle(s)} className="w-full text-left px-3 py-1.5 text-[12px] hover:bg-[rgba(180,220,190,0.06)] flex items-center gap-2">
                  <span className={`w-3.5 h-3.5 rounded-[3px] border flex items-center justify-center flex-none ${on ? 'bg-accent border-accent' : 'border-[rgba(180,220,190,0.3)]'}`}>{on && <span className="text-base text-[9px] leading-none">✓</span>}</span>
                  <span className={on ? 'text-text-primary' : 'text-text-secondary'}>{s}</span>
                </button>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}

function Directory() {
  const [filter, setFilter] = useState<number | 'all'>(1)
  const [opps, setOpps] = useState<Opp[]>([]); const [counts, setCounts] = useState<Record<string, number>>({}); const [sel, setSel] = useState<Opp | null>(null)
  const [sortKey, setSortKey] = useState<SortKey>('score'); const [sortDir, setSortDir] = useState<1 | -1>(-1)
  const [selSectors, setSelSectors] = useState<Set<string>>(new Set()); const [search, setSearch] = useState('')
  const load = useCallback(() => {
    const q = filter === 'all' ? '' : `?category=${filter}`
    adminFetch<{ opportunities: Opp[]; counts: Record<string, number> }>(`/api/admin/opportunities${q}`).then((r) => { setOpps(r.opportunities); setCounts(r.counts) }).catch(() => {})
  }, [filter])
  useEffect(() => { load() }, [load])

  // memoized so the ~500-row filter+sort runs ONLY when an input actually changes,
  // not on every unrelated re-render (opening a detail panel, toggling the dropdown…).
  const sectorList = useMemo(() => Array.from(new Set(opps.map((o) => o.sector).filter(Boolean) as string[])).sort(), [opps])
  const rows = useMemo(() => opps
    .filter((o) => selSectors.size === 0 || (o.sector != null && selSectors.has(o.sector)))
    .filter((o) => !search || o.symbol.toLowerCase().includes(search.toLowerCase()) || (o.name || '').toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      const va = sortVal(a, sortKey), vb = sortVal(b, sortKey)
      const c = typeof va === 'string' ? String(va).localeCompare(String(vb)) : (va as number) - (vb as number)
      return c * sortDir
    }), [opps, selSectors, search, sortKey, sortDir])
  const toggleSector = (s: string) => setSelSectors((prev) => { const n = new Set(prev); n.has(s) ? n.delete(s) : n.add(s); return n })
  // switching the category resets the sector picks — otherwise a sector selected in one
  // bucket that has no names in the next reads as a stuck-empty list.
  const pickCategory = (c: number | 'all') => { setFilter(c); setSelSectors(new Set()) }
  const clickSort = (k: SortKey) => { if (k === sortKey) setSortDir((d) => (d === 1 ? -1 : 1)); else { setSortKey(k); setSortDir(k === 'symbol' || k === 'name' || k === 'sector' ? 1 : -1) } }

  return (
    <div className="overflow-auto" style={{ height: 'calc(100vh - 56px)' }}>
      <div className="flex gap-2 items-center px-4 py-3 flex-wrap sticky top-0 bg-base z-10 border-b border-[rgba(180,220,190,0.08)]">
        {([1, 3, 2, 0, 'all'] as const).map((c) => (
          <button key={String(c)} onClick={() => pickCategory(c)} className={`text-[11px] px-3 py-1.5 rounded-full border ${filter === c ? 'bg-accent text-base border-accent' : 'text-text-secondary border-[rgba(180,220,190,0.12)]'}`}>
            {c === 'all' ? 'All' : CAT_LABEL[String(c)]} {c !== 'all' && <span className="opacity-60">{counts[String(c)] || 0}</span>}
          </button>
        ))}
        <div className="flex-1" />
        <SectorFilter all={sectorList} selected={selSectors} onToggle={toggleSector} onClear={() => setSelSectors(new Set())} />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="search…" className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-1.5 text-[12px] outline-none w-32" />
        <span className="text-[11px] text-text-tertiary">{rows.length}</span>
      </div>
      <div className="min-w-[860px]">
        <div className="flex items-center gap-3 px-4 py-2 border-b border-[rgba(180,220,190,0.08)] text-[9.5px] font-mono uppercase tracking-wider text-text-tertiary sticky top-[49px] bg-base">
          {COLS.map(([label, key, w, align]) => (
            <button key={key} onClick={() => clickSort(key)} className={`${w} ${align === 'right' ? 'text-right' : 'text-left'} hover:text-text-secondary ${sortKey === key ? 'text-accent' : ''}`}>
              {label}{sortKey === key ? (sortDir === -1 ? ' ↓' : ' ↑') : ''}
            </button>
          ))}
        </div>
        {rows.map((o) => (
          <div key={o.symbol} onClick={() => setSel(o)} className={`px-4 py-2.5 border-b border-[rgba(180,220,190,0.05)] cursor-pointer flex items-center gap-3 hover:bg-surface-2 ${sel?.symbol === o.symbol ? 'bg-surface-2' : ''}`}>
            {COLS.map(([label, key, w, align, render]) => (
              <span key={key} className={`${w} ${align === 'right' ? 'text-right' : 'text-left'} truncate`}>{render(o)}</span>
            ))}
          </div>
        ))}
        {rows.length === 0 && <div className="p-6 text-[12px] text-text-tertiary">None match — the central analysis fills the pool in the background.</div>}
      </div>
      {sel && (
        <div className="fixed inset-0 z-30 bg-black/30" onClick={() => setSel(null)}>
          <div className="absolute right-0 top-14 bottom-0 w-full max-w-2xl bg-base border-l border-[rgba(180,220,190,0.12)] overflow-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <Detail o={sel} onChange={(u) => { setSel(u); load() }} onClose={() => setSel(null)} />
          </div>
        </div>
      )}
    </div>
  )
}

function ScoreBreakdown({ o }: { o: Opp }) {
  const b = o.score_breakdown
  if (!b) return null
  const bar = (v: number, w: number) => (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-surface-2 overflow-hidden"><div className="h-full bg-accent" style={{ width: `${Math.min(100, v)}%` }} /></div>
      <span className="font-mono text-[12px] text-text-primary w-16 text-right">{v.toFixed(0)}<span className="text-text-tertiary text-[10px]"> ×{w.toFixed(2)}</span></span>
    </div>
  )
  const comp = (title: string, c: { score: number; inputs: Record<string, any> }, w: number, fmtInputs: () => string) => (
    <div className="mb-3">
      <div className="flex justify-between items-baseline mb-1"><span className="text-[12px] text-text-secondary font-medium">{title}</span></div>
      {bar(c.score, w)}
      <div className="text-[11px] text-text-tertiary mt-1 leading-relaxed">{fmtInputs()}</div>
    </div>
  )
  return (
    <Section title={`Score ${b.total.toFixed(0)}/100 · how it's calculated (quality-first)`}>
      {comp('Quality', b.quality, b.weights.quality, () => `ROE ${pctF(b.quality.inputs.return_on_equity)} · ROA ${pctF(b.quality.inputs.return_on_assets)} · profit ${pctF(b.quality.inputs.profit_margin)} · op ${pctF(b.quality.inputs.operating_margin)} · red-team ${b.quality.inputs.red_team}`)}
      {comp('Durability', b.durability, b.weights.durability, () => `revenue growth ${pctF(b.durability.inputs.revenue_growth)} · earnings growth ${pctF(b.durability.inputs.earnings_growth)}${b.durability.inputs.durability_writeup ? ' · 5–10yr durability write-up ✓' : ''}`)}
      {comp('Value (margin of safety)', b.margin, b.weights.margin, () => `margin ${b.margin.inputs.margin_of_safety_pct == null ? 'n/a' : b.margin.inputs.margin_of_safety_pct.toFixed(0) + '%'} — supportive, not decisive`)}
      {b.penalty && b.penalty.factor < 1
        ? <div className="text-[11px] text-loss mt-1 mb-1 rounded bg-loss/[0.06] border border-loss/30 px-2 py-1.5">
            ⚠ Risk penalty ×{b.penalty.factor.toFixed(2)} — weak {b.penalty.weak.map((w) => w === 'margin' ? 'value' : w).join(' + ')} (below {b.penalty.floor}). Base {b.base?.toFixed(0)} → {b.total.toFixed(0)}.
          </div>
        : null}
      <div className="text-[10px] text-text-tertiary mt-1 font-mono">= (0.45·Q + 0.30·D + 0.25·V){b.penalty && b.penalty.factor < 1 ? ` × ${b.penalty.factor.toFixed(2)}` : ''} = {b.total.toFixed(1)}</div>
    </Section>
  )
}

function MetricsGrid({ o }: { o: Opp }) {
  if (!o.stats) return null
  return (
    <Section title="Fundamentals">
      <div className="grid grid-cols-3 gap-x-4 gap-y-1.5">
        {METRICS.map(([label, key, kind]) => (
          <div key={key} className="flex justify-between text-[11.5px]">
            <span className="text-text-tertiary">{label}</span>
            <span className="font-mono text-text-secondary">{o.stats![key] == null ? '—' : kind === 'pct' ? pctF(o.stats![key]) : num(o.stats![key])}</span>
          </div>
        ))}
      </div>
    </Section>
  )
}

function Detail({ o, onChange, onClose }: { o: Opp; onChange: (o: Opp) => void; onClose?: () => void }) {
  const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false); const [reply, setReply] = useState('')
  const send = async () => {
    if (!msg.trim()) return
    setBusy(true); setReply('')
    try { const r = await adminFetch<Opp & { reply: string }>(`/api/admin/opportunities/${o.symbol}/chat`, { method: 'POST', body: JSON.stringify({ message: msg }) }); setReply(r.reply); setMsg(''); onChange(r) }
    catch (e: any) { setReply(String(e.message)) } finally { setBusy(false) }
  }
  return (
    <div className="p-6">
      <div className="flex items-center gap-3 mb-1">
        <span className="font-serif text-[22px]">{o.symbol}</span>
        <span className={`text-[11px] font-medium ${catColor(o.category)}`}>{CAT_LABEL[String(o.category)]}</span>
        {o.score != null && <span className="text-[11px] font-mono text-text-primary bg-surface-2 rounded px-2 py-0.5">score {o.score.toFixed(0)}{o.sector_rank ? ` · #${o.sector_rank} in ${o.sector}` : ''}</span>}
        {onClose && <button onClick={onClose} className="ml-auto text-[13px] text-text-tertiary hover:text-text-secondary">✕</button>}
      </div>
      <div className="text-[12px] text-text-tertiary mb-4">{o.name} · {o.sector} · ${o.last_price} · FV ${o.fair_value} (range ${o.fv_low}–${o.fv_high}) · margin {o.margin_pct == null ? '—' : o.margin_pct.toFixed(1) + '%'} · {o.confident ? 'confident' : 'low-confidence'}</div>
      <ScoreBreakdown o={o} />
      <MetricsGrid o={o} />
      {o.growth_exception && (
        <div className="mb-4 rounded-md border border-accent/40 bg-accent/[0.06] px-3 py-2 text-[12px] text-accent">
          ◆ Growth exception — fairly valued (no classic margin of safety), but an exceptional durable grower. Surfaced for the user's judgment call; requires approval, not auto-traded.
        </div>
      )}
      {o.news && (
        <div className={`mb-4 rounded-md border px-3 py-2 ${o.news.needs_review ? 'border-loss/40 bg-loss/[0.06]' : 'border-[rgba(180,220,190,0.12)] bg-surface-2'}`}>
          <div className={`text-[11px] font-medium mb-1 ${o.news.needs_review ? 'text-loss' : 'text-text-secondary'}`}>
            {o.news.needs_review ? '⚠ Thesis-relevant news' : 'End-of-day news'}
            {o.news.sentiment && <span className="text-text-tertiary font-normal"> · {o.news.sentiment}/{o.news.severity}</span>}
          </div>
          {o.news.note && <div className="text-[12px] text-text-secondary mb-1.5">{o.news.note}</div>}
          {!!o.news.headlines?.length && <div className="text-[11px] text-text-tertiary leading-relaxed">{o.news.headlines.slice(0, 4).map((h, i) => <div key={i} className="truncate">– {h}</div>)}</div>}
        </div>
      )}
      {o.thesis && <Section title="Thesis"><p className="text-[13px] leading-relaxed text-text-secondary">{o.thesis}</p></Section>}
      {o.growth && <Section title="Growth (near-term)"><p className="text-[13px] leading-relaxed text-text-secondary">{o.growth}</p></Section>}
      {o.future_growth && <Section title="Durability · 5–10 year runway"><p className="text-[13px] leading-relaxed text-text-secondary">{o.future_growth}</p></Section>}
      {!!o.falsifiers?.length && <Section title="Falsifiers · if any of these happens, the thesis breaks">{o.falsifiers.map((f, i) => <div key={i} className="text-[12px] text-text-secondary flex gap-2"><span className="text-text-tertiary flex-none">◇</span>{f.label}</div>)}</Section>}
      {!!o.red_team?.length && <Section title="Red-team">{o.red_team.map((r, i) => <div key={i} className="text-[12px] mb-1.5"><span className={`font-mono ${r.verdict === 'kills' ? 'text-loss' : 'text-gain'}`}>{r.lens} {r.verdict === 'kills' ? '✕' : '✓'}</span> <span className="text-text-tertiary">{r.attack}</span></div>)}</Section>}
      {o.analysis_status === 'rejected_stats' && <div className="text-[12px] text-loss mb-4">Rejected by the stats gate (no LLM spent): {(o.stats && JSON.stringify(Object.fromEntries(Object.entries(o.stats).filter(([k]) => ['revenue_growth', 'profit_margins', 'return_on_equity'].includes(k)))))}</div>}
      {o.admin_notes && <Section title="Admin-provided info"><p className="text-[12px] text-text-tertiary whitespace-pre-wrap">{o.admin_notes}</p></Section>}
      {/* chat — feed info + re-analyze (esp. category 2) */}
      <div className="mt-4 border-t border-[rgba(180,220,190,0.08)] pt-4">
        <div className="text-[11px] font-mono uppercase tracking-wider text-text-tertiary mb-2">Feed the harness info → re-analyze</div>
        <textarea value={msg} onChange={(e) => setMsg(e.target.value)} rows={3} placeholder="e.g. context on the business model, a filing detail, why the moat is durable…" className="w-full bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-2 text-[13px] outline-none mb-2" />
        <button onClick={send} disabled={busy} className="bg-accent text-base text-[13px] font-medium rounded-md px-4 py-2 disabled:opacity-50">{busy ? 'Re-analyzing…' : 'Send + re-analyze'}</button>
        {reply && <div className="mt-3 text-[12px] text-text-secondary bg-surface-2 rounded-md p-3">{reply}</div>}
      </div>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="mb-4"><div className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary mb-1.5">{title}</div>{children}</div>
}

function Admins({ meRoot }: { meRoot: boolean }) {
  const [admins, setAdmins] = useState<AdminAcct[]>([])
  const load = () => adminFetch<{ admins: AdminAcct[] }>('/api/admin/admins').then((r) => setAdmins(r.admins)).catch(() => {})
  useEffect(() => { load() }, [])
  const act = (id: string, action: string) => adminFetch(`/api/admin/admins/${id}/${action}`, { method: 'POST' }).then(load).catch(() => {})
  return (
    <div className="p-6 max-w-2xl">
      <div className="text-[15px] font-serif mb-4">Admin accounts</div>
      {admins.map((a) => (
        <div key={a.id} className="flex items-center gap-3 py-3 border-b border-[rgba(180,220,190,0.06)]">
          <span className="text-[13px] flex-1">{a.email} {a.is_root && <span className="text-[10px] text-accent">root</span>}</span>
          <span className={`text-[11px] font-mono uppercase ${a.status === 'active' ? 'text-gain' : a.status === 'pending' ? 'text-warning' : 'text-loss'}`}>{a.status}</span>
          {a.status === 'pending' && (
            <>
              <button onClick={() => act(a.id, 'approve')} className="text-[12px] text-gain">approve</button>
              <button onClick={() => act(a.id, 'reject')} className="text-[12px] text-loss">reject</button>
            </>
          )}
        </div>
      ))}
      {!meRoot && <div className="text-[11px] text-text-tertiary mt-4">Any active admin can approve new requests.</div>}
    </div>
  )
}

// ── Polytrade themes ──────────────────────────────────────────────────────────
interface ThemeConstituentT { symbol: string; target_weight: number; role: string; conviction: number | null; rationale: string | null; status: string }
interface ThemeEventT { kind: string; summary: string; detail: any; created_at: string | null }
interface ThemeT {
  id: string; slug: string; title: string; tags: string[]; narrative: string; hero_stat: string | null
  status: string; conviction: number; health: string; falsifiers: any[]; red_team: any[]
  target_version: number; survives_red_team: boolean | null; gen_status: string | null; basket_status: string | null
  monitor_status: string | null
  report_status: string | null
  pick_note: string | null
  perf_snapshot: { since_inception_pct: number | null; day_pct: number | null; updated_at?: string; per_name?: any[] } | null
  created_by: string | null; created_at: string | null; updated_at: string | null; last_thesis_run_at: string | null
  n_constituents?: number; n_allocations?: number
  constituents?: ThemeConstituentT[]; events?: ThemeEventT[]
}
const pctColor = (v: number | null | undefined) => v == null ? 'text-text-tertiary' : v >= 0 ? 'text-gain' : 'text-loss'
const pctStr = (v: number | null | undefined) => v == null ? '—' : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`

const HEALTH_UI: Record<string, { cls: string; dot: string }> = {
  strong: { cls: 'text-gain border-gain/40 bg-gain/10', dot: '🟢' },
  watching: { cls: 'text-warning border-warning/40 bg-warning/10', dot: '🟡' },
  breaking: { cls: 'text-loss border-loss/40 bg-loss/10', dot: '🔴' },
}
const healthPill = (h: string) => {
  const u = HEALTH_UI[h] || { cls: 'text-text-tertiary border-[rgba(180,220,190,0.2)]', dot: '' }
  return <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${u.cls}`}>{u.dot} {h}</span>
}
const STATUS_CLS: Record<string, string> = {
  draft: 'text-text-tertiary border-[rgba(180,220,190,0.2)]', live: 'text-gain border-gain/40',
  weakening: 'text-warning border-warning/40', breaking: 'text-loss border-loss/40', closed: 'text-text-tertiary border-[rgba(180,220,190,0.15)] opacity-70',
}
const statusPill = (s: string) => <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded-full border ${STATUS_CLS[s] || STATUS_CLS.draft}`}>{s}</span>
const roleCls = (r: string) => r === 'anchor' ? 'text-accent' : r === 'speculative' ? 'text-warning' : 'text-text-secondary'

function Gauge({ v }: { v: number }) {
  const color = v >= 60 ? 'bg-gain' : v >= 40 ? 'bg-warning' : 'bg-loss'
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-surface-2 overflow-hidden border border-[rgba(180,220,190,0.08)]"><div className={`h-full ${color} transition-all`} style={{ width: `${Math.max(2, Math.min(100, v))}%` }} /></div>
      <span className="text-[12px] font-mono tabular-nums w-8 text-right">{v}</span>
    </div>
  )
}

function ThemeRow({ t, active, onClick }: { t: ThemeT; active: boolean; onClick: () => void }) {
  const busy = t.gen_status === 'generating' || t.basket_status === 'picking'
  return (
    <button onClick={onClick} className={`w-full text-left rounded-lg border p-3 transition-colors ${active ? 'border-accent/50 bg-surface-2' : 'border-[rgba(180,220,190,0.1)] hover:bg-surface-2/50'}`}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <span className="text-[13.5px] font-medium truncate">{t.title}</span>
        {statusPill(t.status)}
      </div>
      {busy ? (
        <div className="text-[11px] font-mono text-accent animate-pulse">{t.gen_status === 'generating' ? 'researching thesis…' : 'picking basket…'}</div>
      ) : (
        <>
          <Gauge v={t.conviction} />
          <div className="flex items-center justify-between mt-1.5">
            {healthPill(t.health)}
            <span className="text-[10.5px] font-mono text-text-tertiary">{t.n_constituents ?? 0} names · v{t.target_version}</span>
          </div>
        </>
      )}
    </button>
  )
}

function CreateTheme({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [title, setTitle] = useState(''); const [seed, setSeed] = useState(''); const [tags, setTags] = useState('')
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('')
  const submit = async () => {
    if (!title.trim()) { setErr('Title required'); return }
    setBusy(true); setErr('')
    try {
      const r = await adminFetch<{ theme: ThemeT }>('/api/admin/themes', {
        method: 'POST',
        body: JSON.stringify({ title: title.trim(), seed_narrative: seed.trim(), tags: tags.split(',').map(s => s.trim()).filter(Boolean) }),
      })
      onCreated(r.theme.id)
    } catch (e: any) { setErr(String(e.message || 'Failed')); setBusy(false) }
  }
  return (
    <div className="max-w-xl">
      <div className="flex items-center justify-between mb-4">
        <span className="font-serif text-[19px]">New theme</span>
        <button onClick={onClose} className="text-[12px] text-text-tertiary hover:text-text-secondary">✕ cancel</button>
      </div>
      <label className="block font-mono text-[10px] uppercase tracking-widest text-text-tertiary mb-1.5">Title</label>
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. High-bandwidth memory supercycle" className="w-full mb-4 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-2.5 text-[14px] outline-none focus:border-accent/60" autoFocus />
      <label className="block font-mono text-[10px] uppercase tracking-widest text-text-tertiary mb-1.5">Seed idea <span className="text-text-tertiary/60">(optional — the AI develops it)</span></label>
      <textarea value={seed} onChange={e => setSeed(e.target.value)} rows={4} placeholder="The core narrative in a sentence or two — the AI researches, writes the thesis, arms falsifiers and red-teams it." className="w-full mb-4 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-2.5 text-[13px] outline-none focus:border-accent/60 resize-y" />
      <label className="block font-mono text-[10px] uppercase tracking-widest text-text-tertiary mb-1.5">Tags <span className="text-text-tertiary/60">(comma-separated)</span></label>
      <input value={tags} onChange={e => setTags(e.target.value)} placeholder="AI, semis, memory" className="w-full mb-4 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-2.5 text-[14px] outline-none focus:border-accent/60" />
      {err && <div className="text-[12px] text-loss mb-3">{err}</div>}
      <button onClick={submit} disabled={busy} className="bg-accent text-base font-medium rounded-md px-4 py-2.5 text-[14px] disabled:opacity-50">{busy ? 'Originating…' : 'Originate theme'}</button>
      <p className="text-[11px] text-text-tertiary mt-3">The thesis is researched in the background (web search + our data). It appears here in ~10–30s.</p>
    </div>
  )
}

function ThemeDetail({ t, onChange, onDelete }: { t: ThemeT; onChange: () => void; onDelete: () => void }) {
  const [busy, setBusy] = useState('')
  const [pickHint, setPickHint] = useState('')
  const act = async (fn: () => Promise<any>, tag: string) => { setBusy(tag); try { await fn() } catch (e: any) { alert(String(e.message || 'Failed')) } finally { setBusy(''); onChange() } }
  const setStatus = (status: string) => act(() => adminFetch(`/api/admin/themes/${t.id}/status`, { method: 'POST', body: JSON.stringify({ status }) }), 'status')
  const pick = () => act(async () => { const r = await adminFetch(`/api/admin/themes/${t.id}/pick`, { method: 'POST', body: JSON.stringify(pickHint.trim() ? { hint: pickHint.trim() } : {}) }); setPickHint(''); return r }, 'pick')
  const report = () => act(() => adminFetch(`/api/admin/themes/${t.id}/report`, { method: 'POST' }), 'report')
  const regen = () => act(() => adminFetch(`/api/admin/themes/${t.id}/regenerate`, { method: 'POST' }), 'regen')
  const refresh = () => act(() => adminFetch(`/api/admin/themes/${t.id}/refresh`, { method: 'POST' }), 'refresh')
  const monitoring = t.monitor_status === 'running'
  const del = async () => { if (!confirm(`Delete theme "${t.title}"?`)) return; try { await adminFetch(`/api/admin/themes/${t.id}`, { method: 'DELETE' }); onDelete() } catch (e: any) { alert(String(e.message || 'Failed')) } }

  const generating = t.gen_status === 'generating'
  const picking = t.basket_status === 'picking'

  return (
    <div className="max-w-3xl">
      <div className="flex items-start justify-between gap-4 mb-1">
        <div>
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="font-serif text-[22px]">{t.title}</span>
            {statusPill(t.status)} {healthPill(t.health)}
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            {(t.tags || []).map(tag => <span key={tag} className="text-[10px] font-mono uppercase tracking-wider text-text-tertiary bg-surface-2 rounded px-1.5 py-0.5">{tag}</span>)}
            <span className="text-[10.5px] font-mono text-text-tertiary">v{t.target_version} · {t.created_by || '—'}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-none">
          {!generating && (t.constituents || []).length > 0 && <button onClick={refresh} disabled={!!busy || monitoring} className="text-[12px] border border-accent/40 text-accent rounded px-2.5 py-1 disabled:opacity-40">{monitoring ? 'refreshing…' : '↻ Refresh'}</button>}
          {t.status === 'draft' && <button onClick={() => setStatus('live')} disabled={!!busy || generating} className="text-[12px] bg-accent text-base rounded px-2.5 py-1 disabled:opacity-40">Publish</button>}
          {t.status !== 'draft' && t.status !== 'closed' && <button onClick={() => setStatus('closed')} disabled={!!busy} className="text-[12px] border border-[rgba(180,220,190,0.2)] rounded px-2.5 py-1">Close</button>}
          {t.status === 'closed' && <button onClick={() => setStatus('draft')} disabled={!!busy} className="text-[12px] border border-[rgba(180,220,190,0.2)] rounded px-2.5 py-1">Reopen</button>}
          <button onClick={del} className="text-[12px] text-loss">Delete</button>
        </div>
      </div>

      {generating ? (
        <div className="text-[13px] text-accent animate-pulse mt-6">Researching the thesis — web search + our data…</div>
      ) : (
        <>
          {t.hero_stat && <div className="text-[15px] text-accent font-serif italic mt-4 mb-3">“{t.hero_stat}”</div>}
          <div className="flex items-end gap-6 mb-4">
            <div className="flex-1"><div className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary mb-1.5">Conviction</div><Gauge v={t.conviction} /></div>
            {t.perf_snapshot && (
              <div className="flex gap-5 flex-none">
                <div><div className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary mb-1">Since basket</div><div className={`text-[15px] font-mono tabular-nums ${pctColor(t.perf_snapshot.since_inception_pct)}`}>{pctStr(t.perf_snapshot.since_inception_pct)}</div></div>
                <div><div className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary mb-1">Today</div><div className={`text-[15px] font-mono tabular-nums ${pctColor(t.perf_snapshot.day_pct)}`}>{pctStr(t.perf_snapshot.day_pct)}</div></div>
              </div>
            )}
          </div>
          <p className="text-[13.5px] text-text-secondary leading-relaxed mb-5">{t.narrative || <span className="text-text-tertiary">No narrative.</span>}</p>

          <div className="grid grid-cols-2 gap-4 mb-5">
            <Section title={`Falsifiers · ${(t.falsifiers || []).length}`}>
              <div className="space-y-2">
                {(t.falsifiers || []).map((f: any, i: number) => (
                  <div key={i} className="text-[12px]">
                    <div className="flex items-center gap-1.5"><span className="text-text-primary">{f.label}</span><span className={`text-[9px] font-mono uppercase px-1 rounded ${f.kind === 'metric' ? 'text-accent bg-accent/10' : 'text-warning bg-warning/10'}`}>{f.kind}</span></div>
                    <div className="text-[11px] text-text-tertiary">breaks if: {f.breaks_if}</div>
                  </div>
                ))}
                {!(t.falsifiers || []).length && <div className="text-[12px] text-text-tertiary">—</div>}
              </div>
            </Section>
            <Section title={`Red-team · ${t.survives_red_team ? 'survived' : 'needs work'}`}>
              <div className="space-y-2">
                {(t.red_team || []).map((r: any, i: number) => (
                  <div key={i} className="text-[12px]">
                    <span className={`font-mono text-[10px] uppercase tracking-wider ${r.verdict === 'survives' ? 'text-gain' : 'text-loss'}`}>{r.lens} · {r.verdict}</span>
                    <div className="text-[11px] text-text-tertiary">{r.attack}</div>
                  </div>
                ))}
                {!(t.red_team || []).length && <div className="text-[12px] text-text-tertiary">—</div>}
              </div>
            </Section>
          </div>

          {/* Basket */}
          <div className="flex items-center justify-between mb-2">
            <span className="font-mono text-[10px] uppercase tracking-widest text-text-tertiary">Basket · {(t.constituents || []).length} names</span>
            <div className="flex items-center gap-3">
              <button onClick={regen} disabled={!!busy} className="text-[11px] text-text-tertiary hover:text-text-secondary">↻ regenerate thesis</button>
              {(t.constituents || []).length > 0 && <button onClick={report} disabled={!!busy || t.report_status === 'generating'} className="text-[11px] text-text-tertiary hover:text-text-secondary">{t.report_status === 'generating' ? 'writing report…' : '📄 report'}</button>}
              <button onClick={pick} disabled={!!busy || picking} className="text-[12px] bg-accent/90 text-base rounded px-2.5 py-1 disabled:opacity-40">{picking ? 'picking…' : (t.constituents || []).length ? 'Re-pick basket' : 'Pick basket'}</button>
            </div>
          </div>
          {/* optional guidance: force specific names into the pick */}
          <div className="flex items-center gap-2 mb-3">
            <input
              value={pickHint}
              onChange={(e) => setPickHint(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && pickHint.trim() && !picking) pick() }}
              placeholder="Also consider… (e.g. SK Hynix, or a note for the pick)"
              className="flex-1 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 py-1.5 text-[12px] text-text-primary placeholder-text-tertiary/60 outline-none focus:border-accent/40"
            />
            <span className="text-[10px] text-text-tertiary">threaded into the AI's universe + selection</span>
          </div>
          {!picking && t.pick_note && <div className="text-[11px] text-warning mb-3">⚠ {t.pick_note}</div>}
          {picking ? (
            <div className="text-[12px] text-accent animate-pulse mb-5">Researching the best US / ADR names for this theme + scoring them on our metrics…</div>
          ) : (t.constituents || []).length ? (
            <div className="rounded-lg border border-[rgba(180,220,190,0.1)] overflow-hidden mb-5">
              {(t.constituents || []).map(c => (
                <div key={c.symbol} className="flex items-center gap-3 px-3 py-2 border-b border-[rgba(180,220,190,0.06)] last:border-0">
                  <span className="font-mono text-[12px] w-14">{c.symbol}</span>
                  <span className={`text-[10px] font-mono uppercase tracking-wider w-16 ${roleCls(c.role)}`}>{c.role}</span>
                  <div className="w-28 h-1.5 rounded-full bg-surface-2 overflow-hidden"><div className="h-full bg-accent" style={{ width: `${c.target_weight * 100}%` }} /></div>
                  <span className="text-[11px] font-mono tabular-nums w-10 text-right">{(c.target_weight * 100).toFixed(1)}%</span>
                  <span className="text-[11px] text-text-tertiary truncate flex-1">{c.rationale}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-[12px] text-text-tertiary mb-5">No basket yet — the AI picks the best US / ADR names for the theme, scored on our metrics.</div>
          )}

          {/* Event feed */}
          <Section title="Activity">
            <div className="space-y-1.5">
              {(t.events || []).map((e, i) => (
                <div key={i} className="flex items-start gap-2 text-[11.5px]">
                  <span className="font-mono text-[9px] uppercase tracking-wider text-text-tertiary bg-surface-2 rounded px-1 py-0.5 mt-0.5 flex-none">{e.kind}</span>
                  <span className="text-text-secondary">{e.summary}</span>
                  <span className="text-text-tertiary/60 ml-auto flex-none">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</span>
                </div>
              ))}
              {!(t.events || []).length && <div className="text-[12px] text-text-tertiary">—</div>}
            </div>
          </Section>
        </>
      )}
    </div>
  )
}

function Themes() {
  const [list, setList] = useState<ThemeT[]>([])
  const [sel, setSel] = useState<string | null>(null)
  const [detail, setDetail] = useState<ThemeT | null>(null)
  const [showCreate, setShowCreate] = useState(false)

  const loadList = useCallback(() => adminFetch<{ themes: ThemeT[] }>('/api/admin/themes').then(r => setList(r.themes)).catch(() => {}), [])
  useEffect(() => { loadList() }, [loadList])
  useEffect(() => {
    if (!list.some(t => t.gen_status === 'generating' || t.basket_status === 'picking')) return
    const id = setInterval(loadList, 4000); return () => clearInterval(id)
  }, [list, loadList])

  const loadDetail = useCallback((id: string) => adminFetch<ThemeT>(`/api/admin/themes/${id}`).then(setDetail).catch(() => {}), [])
  useEffect(() => { if (sel) { loadDetail(sel) } else { setDetail(null) } }, [sel, loadDetail])
  useEffect(() => {
    if (!sel || !detail) return
    if (detail.gen_status !== 'generating' && detail.basket_status !== 'picking' && detail.monitor_status !== 'running' && detail.report_status !== 'generating') return
    const id = setInterval(() => loadDetail(sel), 3500); return () => clearInterval(id)
  }, [sel, detail, loadDetail])

  return (
    <div className="flex">
      <div className="w-[360px] border-r border-[rgba(180,220,190,0.1)] p-4 space-y-2 min-h-[calc(100vh-56px)]">
        <div className="flex items-center justify-between mb-1">
          <span className="font-mono text-[11px] uppercase tracking-widest text-text-tertiary">Themes · {list.length}</span>
          <button onClick={() => { setShowCreate(true); setSel(null) }} className="text-[12px] bg-accent text-base rounded px-2.5 py-1">+ New</button>
        </div>
        {list.map(t => <ThemeRow key={t.id} t={t} active={!showCreate && t.id === sel} onClick={() => { setShowCreate(false); setSel(t.id) }} />)}
        {!list.length && <div className="text-[12px] text-text-tertiary mt-4">No themes yet. Create one to seed the pipeline.</div>}
      </div>
      <div className="flex-1 p-6">
        {showCreate ? <CreateTheme onClose={() => setShowCreate(false)} onCreated={(id) => { setShowCreate(false); loadList(); setSel(id) }} />
          : detail ? <ThemeDetail t={detail} onChange={() => { if (sel) loadDetail(sel); loadList() }} onDelete={() => { setSel(null); loadList() }} />
            : <div className="text-[13px] text-text-tertiary">Select a theme, or create one to start the pipeline.</div>}
      </div>
    </div>
  )
}

