import { useNavigate } from 'react-router-dom'
import { useEffect, useRef, useState } from 'react'
import { Bookmark, Search, Trash2, RefreshCw, X, ExternalLink, Sparkles, Loader2, Plus } from 'lucide-react'
import clsx from 'clsx'
import { formatCurrency } from '../data/mockData'
import {
  useWatchlistStore, searchStocks, addSymbol, getWatchlistDetail,
  type WatchlistEntry, type StockSearchResult, type WatchlistDetail,
} from '../hooks/useWatchlistStore'
import { runAnalysis } from '../hooks/useResearchStore'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'
import ModeToggle from '../components/ModeToggle'

// ── formatters ──
const pct = (v: unknown) => (typeof v === 'number' ? `${(v * 100).toFixed(1)}%` : '—')
const cur = (v: unknown) => (typeof v === 'number' ? `$${v.toFixed(2)}` : '—')
const num = (v: unknown, d = 2) => (typeof v === 'number' ? v.toFixed(d) : '—')
const big = (v: unknown) => {
  if (typeof v !== 'number' || !v) return '—'
  const a = Math.abs(v)
  if (a >= 1e12) return `$${(v / 1e12).toFixed(2)}T`
  if (a >= 1e9) return `$${(v / 1e9).toFixed(2)}B`
  if (a >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  return `$${v.toFixed(0)}`
}

// ── search + add box ──
function SearchAdd() {
  const [q, setQ] = useState('')
  const [results, setResults] = useState<StockSearchResult[]>([])
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const t = useRef<ReturnType<typeof setTimeout>>()

  useEffect(() => {
    if (t.current) clearTimeout(t.current)
    if (!q.trim()) { setResults([]); return }
    setBusy(true)
    t.current = setTimeout(async () => {
      const r = await searchStocks(q)
      setResults(r); setBusy(false); setOpen(true)
    }, 250)
    return () => { if (t.current) clearTimeout(t.current) }
  }, [q])

  const add = async (s: StockSearchResult) => {
    setQ(''); setResults([]); setOpen(false)
    await addSymbol(s.symbol, s.name)   // metrics + 30d news fill in server-side
  }

  return (
    <div className="relative w-full max-w-md">
      <div className="flex items-center gap-2 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-md px-3 h-9 focus-within:border-accent/40">
        <Search className="w-4 h-4 text-text-tertiary flex-none" strokeWidth={1.75} />
        <input
          value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => results.length && setOpen(true)}
          placeholder="Search a stock to add (e.g. NVDA, Apple)…"
          className="flex-1 bg-transparent text-[13px] text-text-primary placeholder:text-text-tertiary outline-none"
        />
        {busy && <Loader2 className="w-3.5 h-3.5 text-text-tertiary animate-spin flex-none" />}
      </div>
      {open && results.length > 0 && (
        <>
          <div className="fixed inset-0 z-20" onClick={() => setOpen(false)} />
          <div className="absolute left-0 right-0 mt-1 z-30 max-h-80 overflow-auto bg-surface-2 border border-[rgba(180,220,190,0.18)] rounded-lg shadow-2xl py-1">
            {results.map((r) => (
              <button key={r.symbol} onClick={() => add(r)}
                className="w-full text-left px-3 py-2 hover:bg-[rgba(207,174,98,0.06)] flex items-center gap-3">
                <span className="font-mono text-[12px] text-accent w-14 flex-none">{r.symbol}</span>
                <span className="text-[12px] text-text-secondary truncate flex-1">{r.name}</span>
                <span className="text-[10px] text-text-tertiary flex-none">{r.exchange}</span>
                <Plus className="w-3.5 h-3.5 text-text-tertiary flex-none" />
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ── detail slide-over (metrics + 30d news + run research) ──
const M: [string, string, (v: unknown) => string][] = [
  ['Market cap', 'market_cap', big], ['P/E', 'pe_ratio', (v) => num(v, 1)], ['Fwd P/E', 'forward_pe', (v) => num(v, 1)],
  ['P/B', 'price_to_book', (v) => num(v, 2)], ['P/S', 'price_to_sales', (v) => num(v, 2)],
  ['Profit margin', 'profit_margins', pct], ['Op margin', 'operating_margins', pct], ['Gross margin', 'gross_margins', pct],
  ['ROE', 'return_on_equity', pct], ['ROA', 'return_on_assets', pct],
  ['Revenue growth', 'revenue_growth', pct], ['Earnings growth', 'earnings_growth', pct],
  ['Free cash flow', 'free_cash_flow', big], ['Debt/Equity', 'debt_to_equity', (v) => num(v, 2)],
  ['Current ratio', 'current_ratio', (v) => num(v, 2)], ['Dividend yield', 'dividend_yield', pct], ['Beta', 'beta', (v) => num(v, 2)],
  ['Fwd EPS est', 'forward_eps_est', cur], ['Analyst target', 'target_mean_price', cur],
]

function DetailPanel({ symbol, onClose }: { symbol: string; onClose: () => void }) {
  const navigate = useNavigate()
  const [d, setD] = useState<WatchlistDetail | null>(null)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let alive = true
    setLoading(true)
    getWatchlistDetail(symbol).then((r) => { if (alive) { setD(r); setLoading(false) } })
    return () => { alive = false }
  }, [symbol])

  const m = d?.meta?.metrics || {}
  const news = d?.meta?.news || []
  const runResearch = () => { runAnalysis(symbol); navigate('/research') }

  return (
    <div className="fixed inset-0 z-40 bg-black/30" onClick={onClose}>
      <div className="absolute right-0 top-0 bottom-0 w-full max-w-xl bg-base border-l border-[rgba(180,220,190,0.12)] overflow-auto shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="sticky top-0 bg-base/95 backdrop-blur border-b border-[rgba(180,220,190,0.10)] px-6 py-4 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[18px] font-mono font-medium text-text-primary">{symbol}</span>
              {typeof m.price === 'number' && <span className="text-[14px] font-mono text-accent">{cur(m.price)}</span>}
            </div>
            <div className="text-[12px] text-text-tertiary">{String(m.name || d?.name || '')}{m.sector ? ` · ${m.sector}` : ''}{m.industry ? ` · ${m.industry}` : ''}</div>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md text-text-tertiary hover:text-text-primary hover:bg-surface-2"><X className="w-4.5 h-4.5" /></button>
        </div>

        <div className="px-6 py-5">
          <button onClick={runResearch} className="w-full mb-6 inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-colors press-scale">
            <Sparkles className="w-4 h-4" strokeWidth={1.75} /> Run AI Research
          </button>

          {loading ? (
            <div className="flex items-center gap-2 text-[13px] text-text-tertiary py-10 justify-center"><Loader2 className="w-4 h-4 animate-spin" /> Loading metrics…</div>
          ) : !d?.meta ? (
            <div className="text-[13px] text-text-tertiary py-10 text-center">Fetching FMP metrics &amp; news — check back in a moment.</div>
          ) : (
            <>
              <div className="text-[10px] font-mono uppercase tracking-[0.13em] text-text-tertiary mb-3">Key metrics (FMP)</div>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-3 mb-3">
                {M.map(([label, key, fmt]) => (
                  <div key={key}>
                    <div className="text-[10px] text-text-tertiary uppercase tracking-[0.08em]">{label}</div>
                    <div className="text-[13px] font-mono text-text-secondary mt-0.5">{fmt(m[key])}</div>
                  </div>
                ))}
              </div>
              {(typeof m.target_low_price === 'number' || typeof m.fifty_two_week_low === 'number') && (
                <div className="text-[11px] text-text-tertiary mb-1">
                  {typeof m.target_low_price === 'number' && <>Target range {cur(m.target_low_price)}–{cur(m.target_high_price)} · </>}
                  {typeof m.fifty_two_week_low === 'number' && <>52-wk {cur(m.fifty_two_week_low)}–{cur(m.fifty_two_week_high)}</>}
                </div>
              )}
              {m.grade_trend && <div className="text-[11px] text-accent mb-5">{String(m.grade_trend)}</div>}

              <div className="text-[10px] font-mono uppercase tracking-[0.13em] text-text-tertiary mb-3 mt-2">Last 30 days news</div>
              {news.length === 0 ? (
                <div className="text-[12px] text-text-tertiary">No recent headlines.</div>
              ) : (
                <div className="space-y-2.5">
                  {news.map((n, i) => (
                    <a key={i} href={n.url} target="_blank" rel="noopener noreferrer"
                      className="block group">
                      <div className="text-[12.5px] text-text-secondary group-hover:text-text-primary leading-snug flex items-start gap-1.5">
                        <span className="flex-1">{n.title}</span>
                        <ExternalLink className="w-3 h-3 text-text-tertiary flex-none mt-1 opacity-0 group-hover:opacity-100" />
                      </div>
                      <div className="text-[10px] text-text-tertiary mt-0.5">{n.site}{n.date ? ` · ${n.date.replace('T', ' ')}` : ''}</div>
                    </a>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function WatchlistRow({ entry, onOpen, onReanalyze, onRemove }: {
  entry: WatchlistEntry
  onOpen: (symbol: string) => void
  onReanalyze: (symbol: string) => void
  onRemove: (symbol: string) => void
}) {
  const pctFromFairValue = entry.fairValue.base > 0
    ? ((entry.fairValue.base - entry.lastPrice) / entry.fairValue.base) * 100 : 0
  const isUndervalued = pctFromFairValue > 0
  const analyzed = entry.fairValue.base > 0

  return (
    <tr onClick={() => onOpen(entry.symbol)} className="border-b border-[rgba(180,220,190,0.06)] hover:bg-[rgba(207,174,98,0.04)] transition-colors cursor-pointer">
      <td className="py-3.5 px-4">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-surface-2 border border-[rgba(180,220,190,0.12)] flex items-center justify-center">
            <span className="text-[10px] font-mono font-medium text-accent tracking-wide">{entry.symbol.slice(0, 2)}</span>
          </div>
          <div>
            <span className="text-[13px] font-mono font-medium text-text-primary tracking-wide">{entry.symbol}</span>
            <p className="text-[11px] text-text-tertiary truncate max-w-[160px]">{entry.name}</p>
          </div>
        </div>
      </td>
      <td className="py-3.5 px-4 text-right"><span className="text-[13px] font-mono tabular-nums text-text-primary">{entry.lastPrice ? formatCurrency(entry.lastPrice) : '—'}</span></td>
      <td className="py-3.5 px-4 text-right"><span className="text-[13px] font-mono tabular-nums text-[#E9D6A2]">{analyzed ? formatCurrency(entry.fairValue.base) : '—'}</span></td>
      <td className="py-3.5 px-4 text-right">
        {analyzed ? <span className={clsx('text-[13px] font-mono tabular-nums font-medium', isUndervalued ? 'text-gain' : 'text-loss')}>{isUndervalued ? '+' : ''}{pctFromFairValue.toFixed(1)}%</span>
          : <span className="text-[11px] text-text-tertiary">not analyzed</span>}
      </td>
      <td className="py-3.5 px-4">
        <p className="text-[12px] text-text-secondary leading-relaxed line-clamp-2 max-w-[280px]">{entry.thesis || <span className="text-text-tertiary">Click to view metrics &amp; news, or run research.</span>}</p>
      </td>
      <td className="py-3.5 px-4 text-right" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-end gap-1">
          <button onClick={() => onReanalyze(entry.symbol)} className="p-1.5 rounded-md text-text-tertiary hover:text-accent hover:bg-[rgba(207,174,98,0.10)] transition-colors" title="Run research"><RefreshCw className="w-3.5 h-3.5" strokeWidth={1.5} /></button>
          <button onClick={() => onRemove(entry.symbol)} className="p-1.5 rounded-md text-text-tertiary hover:text-loss hover:bg-loss/10 transition-colors" title="Remove"><Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} /></button>
        </div>
      </td>
    </tr>
  )
}

export default function Watchlist() {
  const { items, removeFromWatchlist } = useWatchlistStore()
  const navigate = useNavigate()
  const [selected, setSelected] = useState<string | null>(null)

  const handleReanalyze = (symbol: string) => { runAnalysis(symbol); navigate('/research') }

  return (
    <div className="min-h-screen">
      <div className="sticky top-0 z-30 bg-base/90 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-8 h-14 gap-4">
          <div className="flex items-center gap-3 flex-none">
            <div className="w-1.5 h-1.5 bg-accent rotate-45" />
            <h1 className="text-[17px] font-serif font-medium text-text-primary tracking-tight">Watchlist</h1>
            {items.length > 0 && <span className="px-2 py-0.5 rounded-full border border-[rgba(180,220,190,0.12)] text-accent text-[11px] font-mono tabular-nums">{items.length}</span>}
          </div>
          <SearchAdd />
          <div className="flex items-center gap-2 flex-none">
            <ModeToggle active="risk" variant="navy" />
            <SyncButton />
            <NotificationsBell />
          </div>
        </div>
      </div>

      <div className="px-8 py-8">
        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24">
            <div className="w-12 h-12 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] flex items-center justify-center mb-6">
              <Bookmark className="w-5 h-5 text-accent" strokeWidth={1.5} />
            </div>
            <h2 className="text-[22px] font-serif font-medium text-text-primary mb-2 tracking-tight">Your watchlist is empty</h2>
            <p className="text-[13px] text-text-secondary max-w-sm text-center leading-relaxed">
              Search for a stock above to add it — we'll pull its metrics &amp; recent news, and you can run full AI research anytime.
            </p>
          </div>
        ) : (
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[rgba(180,220,190,0.08)]">
                  {['Stock', 'Price', 'Fair Value', '% from FV', 'Thesis', ''].map((h, i) => (
                    <th key={i} className={clsx('text-[10px] font-mono font-medium text-text-tertiary uppercase tracking-[0.13em] py-3 px-4', i === 0 || i === 4 ? 'text-left' : 'text-right')}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((entry) => (
                  <WatchlistRow key={entry.symbol} entry={entry} onOpen={setSelected} onReanalyze={handleReanalyze} onRemove={removeFromWatchlist} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {selected && <DetailPanel symbol={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
