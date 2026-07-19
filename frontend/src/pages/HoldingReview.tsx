import { useState, useEffect, useRef } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import KeyStatsPanel from '../components/KeyStatsPanel'
import {
  ArrowLeft,
  TrendingDown,
  TrendingUp,
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  MinusCircle,
  ChevronDown,
  ChevronUp,
  Loader2,
  RefreshCw,
  ExternalLink,
  Info,
  Zap,
} from 'lucide-react'
import clsx from 'clsx'
import { apiFetch } from '../api/client'
import { usePositions } from '../hooks/usePortfolio'

/* ─── Types ───────────────────────────────────────────────────────── */

interface PerformanceComparison {
  period: string
  stock_return: number
  sector_return: number
  gap: number
  benchmark_return: number | null
}

interface ThesisSignal {
  name: string
  weight: number
  status: 'green' | 'yellow' | 'red'
  score: number
  detail: string
}

interface ThesisHealth {
  ticker: string
  composite_score: number
  signals: ThesisSignal[]
  negative_count: number
  total_count: number
  f_score: number
  verdict: 'healthy' | 'mixed' | 'stressed' | 'broken'
}

interface HoldCondition {
  name: string
  triggered: boolean
  reason: string
}

interface HoldGate {
  should_hold: boolean
  conditions: HoldCondition[]
  hold_reasons: string[]
  review_in_days: number | null
}

interface FactorScores {
  momentum: number
  quality: number
  growth: number
  value: number
  risk: number
  analyst: number
}

interface ScoredCandidate {
  ticker: string
  name: string
  sector: string
  industry: string
  composite_score: number
  factors: FactorScores
  revenue_yoy: number | null
  eps_growth: number | null
  return_6m: number | null
  f_score: number | null
  forward_pe: number | null
  beta: number | null
  dividend_yield: number | null
  market_cap: number | null
}

interface ETFAlternative {
  ticker: string
  name: string
  expense_ratio: number
  top_holdings: string[]
  return_1y: number | null
  return_3y: number | null
  is_sub_industry: boolean
  annual_cost_on_position: number | null
}

interface Narrative {
  current_assessment: string
  why_better: Record<string, string>
  etf_case: string
  key_risks: Record<string, string>
  confidence: 'high' | 'medium' | 'low'
  fresh_money_test: string
}

interface TaxInfo {
  unrealized_gain: number | null
  holding_period_days: number | null
  is_long_term: boolean | null
  days_to_long_term: number | null
  estimated_tax_savings: number | null
  wash_sale_risk: boolean
}

interface ReviewResult {
  ticker: string
  company_name: string
  underperformance: {
    ticker: string
    sector: string
    sector_etf: string
    comparisons: PerformanceComparison[]
    severity: string
    user_pnl_pct: number | null
    user_pnl_dollar: number | null
    summary: string
  }
  thesis_health: ThesisHealth
  hold_gate: HoldGate
  replacements: ScoredCandidate[]
  etf_alternative: ETFAlternative | null
  narrative: Narrative | null
  tax_info: TaxInfo | null
  pipeline_ms: number
  disclaimer: string
}

/* ─── Helpers ─────────────────────────────────────────────────────── */

function pct(v: number | null | undefined, decimals = 1): string {
  if (v == null) return '—'
  return `${(v * 100).toFixed(decimals)}%`
}

function fmtDollar(v: number | null | undefined): string {
  if (v == null) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e12) return `$${(v / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `$${(v / 1e6).toFixed(1)}M`
  return v < 0 ? `-$${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}` : `$${abs.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

const signalIcon = (status: string) => {
  if (status === 'green') return <CheckCircle2 className="w-4 h-4 text-gain" strokeWidth={1.5} />
  if (status === 'red') return <XCircle className="w-4 h-4 text-loss" strokeWidth={1.5} />
  return <MinusCircle className="w-4 h-4 text-warning" strokeWidth={1.5} />
}

const verdictColors: Record<string, string> = {
  healthy: 'text-gain',
  mixed: 'text-warning',
  stressed: 'text-[#C48A5B]',
  broken: 'text-loss',
}

const verdictLabels: Record<string, string> = {
  healthy: 'Thesis Intact',
  mixed: 'Mixed Signals',
  stressed: 'Thesis Under Stress',
  broken: 'Thesis Likely Broken',
}

const severityColors: Record<string, string> = {
  none: 'text-gain',
  early_warning: 'text-warning',
  confirmed: 'text-[#C48A5B]',
  severe: 'text-loss',
}

const confidenceColors: Record<string, string> = {
  high: 'text-gain',
  medium: 'text-warning',
  low: 'text-text-tertiary',
}

/* ─── Sub-Components ──────────────────────────────────────────────── */

function ThesisGauge({ score, verdict }: { score: number; verdict: string }) {
  const pctFill = (score / 10) * 100
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-text-secondary">Thesis Health</span>
        <span className={clsx('font-serif text-[16px] font-medium tabular-nums', verdictColors[verdict])}>
          {score}/10
        </span>
      </div>
      <div className="h-2 bg-[rgba(180,220,190,0.06)] rounded-full overflow-hidden">
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-700',
            score >= 7 ? 'bg-gain' : score >= 4 ? 'bg-warning' : 'bg-loss'
          )}
          style={{ width: `${pctFill}%` }}
        />
      </div>
      <p className={clsx('text-[12px] font-medium', verdictColors[verdict])}>
        {verdictLabels[verdict] || verdict}
      </p>
    </div>
  )
}

function SignalList({ signals, negCount, totalCount }: { signals: ThesisSignal[]; negCount: number; totalCount: number }) {
  const [expanded, setExpanded] = useState(false)
  const visibleSignals = expanded ? signals : signals.slice(0, 3)

  return (
    <div className="space-y-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-[12px] text-text-tertiary hover:text-text-secondary transition-colors"
      >
        <span className="font-medium">{negCount} of {totalCount} signals negative</span>
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      <div className="space-y-1.5">
        {visibleSignals.map((s) => (
          <div key={s.name} className="flex items-start gap-2">
            {signalIcon(s.status)}
            <div className="flex-1 min-w-0">
              <span className="text-[12px] font-medium text-text-secondary">{s.name}: </span>
              <span className="text-[12px] text-text-tertiary">{s.detail}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function PerformanceBars({ comparisons, sectorEtf }: { comparisons: PerformanceComparison[]; sectorEtf: string }) {
  return (
    <div className="space-y-3">
      {comparisons.map((c) => {
        const maxAbs = Math.max(Math.abs(c.stock_return), Math.abs(c.sector_return), 0.01)
        return (
          <div key={c.period} className="space-y-1">
            <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">{c.period}</p>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-tertiary w-10">Stock</span>
                <div className="flex-1 h-4 bg-[rgba(180,220,190,0.05)] rounded-sm overflow-hidden relative">
                  <div
                    className={clsx('h-full rounded-sm', c.stock_return >= 0 ? 'bg-gain/40' : 'bg-loss/40')}
                    style={{ width: `${Math.min(Math.abs(c.stock_return) / maxAbs * 100, 100)}%` }}
                  />
                </div>
                <span className={clsx('text-[12px] font-mono tabular-nums w-14 text-right', c.stock_return >= 0 ? 'text-gain' : 'text-loss')}>
                  {pct(c.stock_return)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-tertiary w-10">{sectorEtf}</span>
                <div className="flex-1 h-4 bg-[rgba(180,220,190,0.05)] rounded-sm overflow-hidden relative">
                  <div
                    className={clsx('h-full rounded-sm', c.sector_return >= 0 ? 'bg-accent/40' : 'bg-loss/40')}
                    style={{ width: `${Math.min(Math.abs(c.sector_return) / maxAbs * 100, 100)}%` }}
                  />
                </div>
                <span className={clsx('text-[12px] font-mono tabular-nums w-14 text-right', c.sector_return >= 0 ? 'text-accent' : 'text-loss')}>
                  {pct(c.sector_return)}
                </span>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

function CandidateCard({
  candidate,
  originalTicker,
  narrative,
  expanded,
  onToggle,
}: {
  candidate: ScoredCandidate
  originalTicker: string
  narrative: Narrative | null
  expanded: boolean
  onToggle: () => void
}) {
  const whyBetter = narrative?.why_better?.[candidate.ticker]
  const keyRisk = narrative?.key_risks?.[candidate.ticker]

  return (
    <div className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] overflow-hidden">
      {/* Header */}
      <button onClick={onToggle} className="w-full px-4 py-3 flex items-center justify-between hover:bg-[rgba(207,174,98,0.04)] transition-colors">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-[8px] bg-accent/10 flex items-center justify-center">
            <span className="font-serif text-[15px] font-medium text-accent tabular-nums">{candidate.composite_score.toFixed(0)}</span>
          </div>
          <div className="text-left">
            <p className="font-mono text-[14px] font-medium text-text-primary">{candidate.ticker}</p>
            <p className="text-[12px] text-text-tertiary">{candidate.name}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">Emouva Score</span>
          {expanded ? <ChevronUp className="w-4 h-4 text-text-tertiary" /> : <ChevronDown className="w-4 h-4 text-text-tertiary" />}
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-[rgba(180,220,190,0.06)]">
          {/* Why it's better */}
          {whyBetter && (
            <p className="text-[13px] text-text-secondary leading-relaxed pt-3">{whyBetter}</p>
          )}

          {/* Key risk */}
          {keyRisk && (
            <div className="flex items-start gap-2 bg-loss/[0.06] rounded-[8px] px-3 py-2">
              <AlertTriangle className="w-3.5 h-3.5 text-loss mt-0.5 flex-shrink-0" strokeWidth={1.5} />
              <p className="text-[12px] text-loss/80">{keyRisk}</p>
            </div>
          )}

          {/* Factor breakdown */}
          <div className="grid grid-cols-3 gap-2">
            {(['momentum', 'quality', 'growth', 'value', 'risk', 'analyst'] as const).map((f) => (
              <div key={f} className="bg-[rgba(180,220,190,0.05)] rounded-[8px] px-2.5 py-2">
                <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.1em] capitalize">{f}</p>
                <p className="font-mono text-[13px] font-medium text-text-primary tabular-nums">{candidate.factors[f].toFixed(0)}</p>
              </div>
            ))}
          </div>

          {/* Metrics comparison row */}
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[12px]">
            <div>
              <span className="text-text-tertiary">Revenue YoY</span>
              <p className={clsx('font-mono font-medium tabular-nums', (candidate.revenue_yoy ?? 0) >= 0 ? 'text-gain' : 'text-loss')}>
                {pct(candidate.revenue_yoy)}
              </p>
            </div>
            <div>
              <span className="text-text-tertiary">Fwd P/E</span>
              <p className="font-mono font-medium text-text-primary tabular-nums">{candidate.forward_pe?.toFixed(1) ?? '—'}x</p>
            </div>
            <div>
              <span className="text-text-tertiary">Beta</span>
              <p className="font-mono font-medium text-text-primary tabular-nums">{candidate.beta?.toFixed(2) ?? '—'}</p>
            </div>
            <div>
              <span className="text-text-tertiary">6mo Return</span>
              <p className={clsx('font-mono font-medium tabular-nums', (candidate.return_6m ?? 0) >= 0 ? 'text-gain' : 'text-loss')}>
                {pct(candidate.return_6m)}
              </p>
            </div>
            <div>
              <span className="text-text-tertiary">EPS Growth</span>
              <p className={clsx('font-mono font-medium tabular-nums', (candidate.eps_growth ?? 0) >= 0 ? 'text-gain' : 'text-loss')}>
                {pct(candidate.eps_growth)}
              </p>
            </div>
            <div>
              <span className="text-text-tertiary">Mkt Cap</span>
              <p className="font-mono font-medium text-text-primary tabular-nums">{fmtDollar(candidate.market_cap)}</p>
            </div>
          </div>

          {/* Research link */}
          <Link
            to={`/research?ticker=${candidate.ticker}`}
            className="flex items-center gap-1.5 text-[12px] text-accent hover:text-accent-hover transition-colors"
          >
            <ExternalLink className="w-3 h-3" />
            Deep-dive research on {candidate.ticker}
          </Link>
        </div>
      )}
    </div>
  )
}

function ETFCard({ etf, narrative }: { etf: ETFAlternative; narrative: Narrative | null }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <div className="bg-surface-2 border border-accent/25 rounded-[10px] overflow-hidden">
      <button onClick={() => setExpanded(!expanded)} className="w-full px-4 py-3 flex items-center justify-between hover:bg-[rgba(207,174,98,0.04)] transition-colors">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-[8px] bg-accent/10 flex items-center justify-center">
            <Shield className="w-5 h-5 text-accent" strokeWidth={1.5} />
          </div>
          <div className="text-left">
            <div className="flex items-center gap-2">
              <p className="font-mono text-[14px] font-medium text-text-primary">{etf.ticker}</p>
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-[4px] bg-accent/10 text-accent uppercase tracking-[0.1em]">
                DIVERSIFIED PLAY
              </span>
            </div>
            <p className="text-[12px] text-text-tertiary">{etf.name}</p>
          </div>
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-text-tertiary" /> : <ChevronDown className="w-4 h-4 text-text-tertiary" />}
      </button>

      {expanded && (
        <div className="px-4 pb-4 space-y-3 border-t border-[rgba(180,220,190,0.06)]">
          {narrative?.etf_case && (
            <p className="text-[13px] text-text-secondary leading-relaxed pt-3">{narrative.etf_case}</p>
          )}

          <div className="flex flex-wrap gap-1.5">
            {etf.top_holdings.map((h) => (
              <span key={h} className="font-mono text-[11px] px-2 py-0.5 rounded-[4px] bg-[rgba(180,220,190,0.08)] text-text-secondary">{h}</span>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-2 text-[12px]">
            <div>
              <span className="text-text-tertiary">Expense Ratio</span>
              <p className="font-mono font-medium text-text-primary tabular-nums">{(etf.expense_ratio * 100).toFixed(2)}%/yr</p>
            </div>
            {etf.annual_cost_on_position != null && (
              <div>
                <span className="text-text-tertiary">Annual Cost</span>
                <p className="font-mono font-medium text-text-primary tabular-nums">${etf.annual_cost_on_position.toFixed(2)}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/* ─── Main Page ───────────────────────────────────────────────────── */

export default function HoldingReview({ embedded = false }: { embedded?: boolean }) {
  const [params] = useSearchParams()
  const tickerParam = params.get('ticker')?.toUpperCase() || ''

  const { data: positions, loading: positionsLoading } = usePositions()
  const [selectedSymbol, setSelectedSymbol] = useState(tickerParam)
  const [searchQuery, setSearchQuery] = useState('')
  const [dropdownOpen, setDropdownOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ReviewResult | null>(null)
  const [error, setError] = useState('')
  const [expandedCard, setExpandedCard] = useState<number>(0)

  const dropdownRef = useRef<HTMLDivElement>(null)

  // Close dropdown on outside click
  useEffect(() => {
    if (!dropdownOpen) return
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false)
        setSearchQuery('')
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [dropdownOpen])

  // Filter positions by search query
  const filteredPositions = positions.filter((p) => {
    if (!searchQuery) return true
    const q = searchQuery.toLowerCase()
    return p.symbol.toLowerCase().includes(q) || p.name.toLowerCase().includes(q)
  })

  // Find the selected position to auto-populate cost basis & shares
  const selectedPosition = positions.find((p) => p.symbol === selectedSymbol)

  // Auto-run if ticker provided via URL
  useEffect(() => {
    if (tickerParam && !result && !loading) {
      runReview(tickerParam)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tickerParam])

  async function runReview(overrideTicker?: string) {
    const t = overrideTicker || selectedSymbol
    if (!t.trim()) return

    setLoading(true)
    setError('')
    setResult(null)
    setExpandedCard(0)

    const pos = positions.find((p) => p.symbol === t)

    try {
      const body: Record<string, unknown> = { ticker: t.trim().toUpperCase() }
      if (pos) {
        body.cost_basis = pos.avgCost
        body.shares = pos.shares
      }

      const data = await apiFetch<ReviewResult>('/api/replacement/review', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setResult(data)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Analysis failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6 space-y-6">
      {/* Header (hidden when embedded in the Optimize super-page) */}
      {!embedded && (
        <div className="flex items-center gap-3">
          <Link to="/portfolio" className="p-1.5 rounded-[8px] hover:bg-[rgba(207,174,98,0.04)] transition-colors">
            <ArrowLeft className="w-5 h-5 text-text-tertiary" />
          </Link>
          <div>
            <h1 className="font-serif text-[22px] font-medium text-text-primary">Position Review</h1>
            <p className="text-[13px] text-text-secondary">
              Select a holding from your portfolio to evaluate and compare alternatives
            </p>
          </div>
        </div>
      )}

      {/* Stock Selector */}
      <div className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] p-4 space-y-3">
        <div className="relative" ref={dropdownRef}>
          <label className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1 block">Select a position</label>
          <div
            className="w-full bg-[rgba(180,220,190,0.05)] border border-[rgba(180,220,190,0.12)] rounded-[8px] px-3 py-2.5 text-[14px] text-text-primary focus-within:border-accent/40 transition-colors cursor-pointer flex items-center gap-2"
            onClick={() => !positionsLoading && setDropdownOpen(!dropdownOpen)}
          >
            {positionsLoading ? (
              <span className="text-text-tertiary/50 flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading portfolio...
              </span>
            ) : selectedSymbol ? (
              <span className="font-mono">{selectedSymbol} — <span className="font-sans">{selectedPosition?.name ?? ''}</span></span>
            ) : (
              <span className="text-text-tertiary/50">Search or select a stock...</span>
            )}
            <ChevronDown className="w-4 h-4 text-text-tertiary ml-auto flex-shrink-0" />
          </div>

          {dropdownOpen && (
            <div className="absolute z-20 left-0 right-0 mt-1 bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[8px] shadow-xl overflow-hidden">
              <div className="p-2 border-b border-[rgba(180,220,190,0.10)]">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by ticker or name..."
                  className="w-full bg-[rgba(180,220,190,0.05)] border border-[rgba(180,220,190,0.10)] rounded-[6px] px-3 py-2 text-[13px] text-text-primary placeholder:text-text-tertiary/50 focus:outline-none focus:border-accent/40"
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                />
              </div>
              <div className="max-h-[240px] overflow-y-auto">
                {positionsLoading ? (
                  <div className="px-3 py-4 text-[13px] text-text-tertiary text-center flex items-center justify-center gap-2">
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Loading positions...
                  </div>
                ) : filteredPositions.length === 0 ? (
                  <div className="px-3 py-4 text-[13px] text-text-tertiary text-center">No matching positions</div>
                ) : (
                  filteredPositions.map((p) => (
                    <button
                      key={p.symbol}
                      onClick={(e) => {
                        e.stopPropagation()
                        setSelectedSymbol(p.symbol)
                        setSearchQuery('')
                        setDropdownOpen(false)
                      }}
                      className={clsx(
                        'w-full px-3 py-2.5 flex items-center justify-between text-left hover:bg-[rgba(207,174,98,0.04)] transition-colors',
                        selectedSymbol === p.symbol && 'bg-accent/[0.06]'
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-[13px] font-medium text-text-primary w-12">{p.symbol}</span>
                        <span className="text-[12px] text-text-tertiary truncate max-w-[200px]">{p.name}</span>
                      </div>
                      <span className="font-mono text-[11px] text-text-tertiary tabular-nums">
                        {p.shares.toFixed(2)} @ ${p.avgCost.toFixed(2)}
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Show selected position summary */}
        {selectedPosition && (
          <div className="flex items-center gap-4 px-3 py-2 rounded-[8px] bg-[rgba(180,220,190,0.04)] border border-[rgba(180,220,190,0.06)] font-mono text-[12px] text-text-secondary tabular-nums">
            <span><span className="text-text-tertiary">Shares:</span> {selectedPosition.shares.toFixed(2)}</span>
            <span><span className="text-text-tertiary">Avg Cost:</span> ${selectedPosition.avgCost.toFixed(2)}</span>
            <span><span className="text-text-tertiary">Current:</span> ${selectedPosition.currentPrice.toFixed(2)}</span>
            <span className={clsx(
              'font-medium',
              selectedPosition.currentPrice >= selectedPosition.avgCost ? 'text-gain' : 'text-loss'
            )}>
              {selectedPosition.currentPrice >= selectedPosition.avgCost ? '+' : ''}
              {(((selectedPosition.currentPrice - selectedPosition.avgCost) / selectedPosition.avgCost) * 100).toFixed(1)}%
            </span>
          </div>
        )}

        <button
          onClick={() => runReview()}
          disabled={loading || !selectedSymbol}
          className="w-full bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-base text-[14px] font-semibold rounded-[8px] py-2.5 flex items-center justify-center gap-2 transition-colors"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Analyzing {selectedSymbol}...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4" />
              Review Position
            </>
          )}
        </button>
      </div>

      {/* Current holding — full key statistics (the same rich data shown on the
          stock page): composite scores, fundamentals, and industry peer ranking. */}
      {selectedSymbol && (
        <div className="space-y-3">
          <h2 className="font-serif text-[16px] font-medium text-text-primary tracking-tight">
            <span className="font-mono">{selectedSymbol}</span> — Key Statistics
          </h2>
          <KeyStatsPanel ticker={selectedSymbol} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-loss/[0.08] border border-loss/20 rounded-[10px] px-4 py-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-loss mt-0.5 flex-shrink-0" strokeWidth={1.5} />
          <p className="text-[13px] text-loss">{error}</p>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="space-y-4 animate-pulse">
          <div className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] h-48" />
          <div className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] h-32" />
          <div className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] h-64" />
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <div className="space-y-5">
          {/* Stage 1: Underperformance */}
          <section className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="font-serif text-[18px] font-medium text-text-primary">{result.company_name}</h2>
              <span className={clsx(
                'font-mono text-[11px] px-2 py-0.5 rounded-full uppercase tracking-[0.08em]',
                result.underperformance.severity === 'none' ? 'bg-gain/10 text-gain' :
                result.underperformance.severity === 'early_warning' ? 'bg-warning/10 text-warning' :
                result.underperformance.severity === 'confirmed' ? 'bg-[#C48A5B]/10 text-[#C48A5B]' :
                'bg-loss/10 text-loss'
              )}>
                {result.underperformance.severity === 'none' ? 'In Line' :
                 result.underperformance.severity === 'early_warning' ? 'Early Warning' :
                 result.underperformance.severity === 'confirmed' ? 'Underperforming' :
                 'Severe Underperformance'}
              </span>
            </div>

            <p className="text-[13px] text-text-secondary leading-relaxed">
              {result.underperformance.summary}
            </p>

            {/* P&L */}
            {result.underperformance.user_pnl_dollar != null && (
              <div className={clsx(
                'flex items-center gap-2 px-3 py-2 rounded-[8px]',
                result.underperformance.user_pnl_dollar >= 0 ? 'bg-gain/[0.06]' : 'bg-loss/[0.06]'
              )}>
                {result.underperformance.user_pnl_dollar >= 0 ?
                  <TrendingUp className="w-4 h-4 text-gain" strokeWidth={1.5} /> :
                  <TrendingDown className="w-4 h-4 text-loss" strokeWidth={1.5} />
                }
                <span className={clsx('font-mono text-[13px] font-medium tabular-nums', result.underperformance.user_pnl_dollar >= 0 ? 'text-gain' : 'text-loss')}>
                  {fmtDollar(result.underperformance.user_pnl_dollar)} ({pct(result.underperformance.user_pnl_pct)})
                </span>
              </div>
            )}

            {/* Performance bars */}
            <PerformanceBars
              comparisons={result.underperformance.comparisons}
              sectorEtf={result.underperformance.sector_etf}
            />
          </section>

          {/* Stage 2: Thesis Health */}
          <section className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] p-4 space-y-4">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-accent" strokeWidth={1.5} />
              <h2 className="font-serif text-[16px] font-medium text-text-primary">Thesis Health Check</h2>
            </div>

            <ThesisGauge score={result.thesis_health.composite_score} verdict={result.thesis_health.verdict} />

            <SignalList
              signals={result.thesis_health.signals}
              negCount={result.thesis_health.negative_count}
              totalCount={result.thesis_health.total_count}
            />

            <div className="flex items-center gap-2 text-[12px] text-text-tertiary">
              <Info className="w-3 h-3" strokeWidth={1.5} />
              <span className="font-mono tabular-nums">Piotroski F-Score: {result.thesis_health.f_score}/9</span>
            </div>
          </section>

          {/* Stage 3: Hold Gate */}
          {result.hold_gate.should_hold && (
            <section className="bg-accent/[0.06] border border-accent/25 rounded-[10px] p-4 space-y-3">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-5 h-5 text-accent" strokeWidth={1.5} />
                <h2 className="font-serif text-[16px] font-medium text-text-primary">Our Take: Hold {result.ticker} For Now</h2>
              </div>

              <div className="space-y-2">
                {result.hold_gate.hold_reasons.map((reason, i) => (
                  <div key={i} className="flex items-start gap-2.5 pl-7">
                    <span className="w-1.5 h-1.5 bg-accent rotate-45 mt-[7px] flex-none" />
                    <p className="text-[13px] text-text-secondary leading-relaxed">{reason}</p>
                  </div>
                ))}
              </div>

              {result.hold_gate.review_in_days && (
                <p className="text-[12px] text-text-tertiary pl-7">
                  We'll suggest checking again in {result.hold_gate.review_in_days} days.
                </p>
              )}
            </section>
          )}

          {/* Narrative: Current Assessment */}
          {result.narrative && (
            <section className="bg-surface-2 border border-[rgba(180,220,190,0.12)] rounded-[10px] p-4 space-y-3">
              <p className="text-[13px] text-text-secondary leading-relaxed">
                {result.narrative.current_assessment}
              </p>

              {/* Fresh money test */}
              <div className="bg-[rgba(180,220,190,0.04)] rounded-[8px] px-3 py-2.5 border-l-2 border-accent/40">
                <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">The Fresh Money Test</p>
                <p className="font-serif text-[13px] text-text-secondary italic">
                  "{result.narrative.fresh_money_test}"
                </p>
              </div>

              {/* Confidence */}
              <div className="flex items-center gap-1.5">
                <span className="text-[11px] text-text-tertiary">Analysis Confidence:</span>
                <span className={clsx('text-[11px] font-medium capitalize', confidenceColors[result.narrative.confidence])}>
                  {result.narrative.confidence}
                </span>
              </div>
            </section>
          )}

          {/* Stages 4-7: Replacements */}
          {result.replacements.length > 0 && (
            <section className="space-y-3">
              <h2 className="font-serif text-[18px] font-medium text-text-primary px-1">
                Alternatives to {result.ticker}
              </h2>

              {result.replacements.map((c, i) => (
                <CandidateCard
                  key={c.ticker}
                  candidate={c}
                  originalTicker={result.ticker}
                  narrative={result.narrative}
                  expanded={expandedCard === i}
                  onToggle={() => setExpandedCard(expandedCard === i ? -1 : i)}
                />
              ))}

              {result.etf_alternative && (
                <ETFCard etf={result.etf_alternative} narrative={result.narrative} />
              )}
            </section>
          )}

          {/* Tax Info */}
          {result.tax_info && result.tax_info.estimated_tax_savings != null && result.tax_info.estimated_tax_savings > 0 && (
            <div className="bg-gain/[0.06] border border-gain/20 rounded-[10px] px-4 py-3 flex items-start gap-2">
              <TrendingUp className="w-4 h-4 text-gain mt-0.5 flex-shrink-0" strokeWidth={1.5} />
              <p className="text-[13px] text-text-secondary">
                <span className="font-medium text-gain">Tax-loss harvesting opportunity: </span>
                Selling at your current loss could save ~${result.tax_info.estimated_tax_savings.toFixed(0)} in taxes.
                {result.replacements.length > 0 && ' Replacing with a different company is NOT a wash sale.'}
              </p>
            </div>
          )}

          {/* Disclaimer */}
          <p className="text-[11px] text-text-tertiary/60 leading-relaxed px-1">
            {result.disclaimer}
          </p>

          {/* Pipeline time */}
          <p className="text-[10px] text-text-tertiary/40 text-right">
            Analysis completed in {(result.pipeline_ms / 1000).toFixed(1)}s
          </p>
        </div>
      )}
    </div>
  )
}
