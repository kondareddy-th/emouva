import { useState } from 'react'
import clsx from 'clsx'
import {
  RefreshCw,
  Shield,
  Flame,
  Rocket,
  Anchor,
  Scale,
  Target,
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  ArrowRight,
  Sparkles,
  Link2,
  ChevronDown,
  ChevronUp,
  Info,
  Search,
  Briefcase,
  BarChart3,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import { formatCurrency } from '../data/mockData'
import type {
  RiskProfile,
  RiskProfileFinding,
  DiversificationSuggestion,
} from '../data/mockData'
import { useRiskProfile, useRiskNarrative } from '../hooks/useRiskProfile'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'

// ── Persona icons ──
const PERSONA_ICONS: Record<string, typeof Shield> = {
  shield: Shield,
  anchor: Anchor,
  scale: Scale,
  rocket: Rocket,
  fire: Flame,
}

const PERSONA_COLORS: Record<string, string> = {
  Guardian: '#CFAE62',
  Steady: '#CFAE62',
  Balanced: '#85BFC9',
  'Growth Seeker': '#DFB65A',
  'Thrill Rider': '#F2937F',
}

// ── Factor labels ──
const FACTOR_LABELS: Record<string, { name: string; desc: string }> = {
  composition: { name: 'Composition', desc: 'Portfolio beta, holding count, sector tilt' },
  concentration: { name: 'Concentration', desc: 'Top position weight, sector HHI' },
  volatility: { name: 'Volatility', desc: 'Price swings, drawdown, stress test results' },
  correlation: { name: 'Correlation', desc: 'How much your stocks move together' },
}

// ── Score gauge (large) ──
function BehavioralScoreGauge({ score, persona }: { score: number; persona: RiskProfile['persona'] }) {
  const circumference = 2 * Math.PI * 90
  const progress = (score / 100) * circumference
  const color = PERSONA_COLORS[persona.name] || '#CFAE62'
  const Icon = PERSONA_ICONS[persona.emoji] || Shield

  return (
    <div className="flex flex-col items-center">
      <div className="relative w-44 h-44">
        <svg viewBox="0 0 200 200" className="w-full h-full -rotate-90">
          <circle
            cx="100" cy="100" r="90" fill="none"
            stroke="rgba(180,220,190,0.08)" strokeWidth="10"
          />
          <circle
            cx="100" cy="100" r="90" fill="none"
            stroke={color} strokeWidth="10" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference - progress}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-serif text-[40px] font-medium tabular-nums" style={{ color }}>{score}</span>
          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">/ 100</span>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-2">
        <div
          className="w-8 h-8 rounded-[8px] flex items-center justify-center"
          style={{ backgroundColor: `${color}15` }}
        >
          <Icon className="w-4 h-4" style={{ color }} strokeWidth={1.5} />
        </div>
        <div>
          <p className="font-serif text-[16px] font-medium text-text-primary">{persona.name}</p>
          <p className="text-[11px] text-text-tertiary">{persona.description}</p>
        </div>
      </div>
    </div>
  )
}

// ── Sub-metric display labels ──
const DETAIL_LABELS: Record<string, Record<string, { label: string; format: (v: number) => string }>> = {
  composition: {
    portfolio_beta: { label: 'Portfolio Beta', format: (v) => `${v.toFixed(2)}x` },
    num_holdings: { label: 'Holdings', format: (v) => `${v} stocks` },
    tech_weight_pct: { label: 'Tech Weight', format: (v) => `${v.toFixed(1)}%` },
  },
  concentration: {
    top1_pct: { label: 'Top Position', format: (v) => `${v.toFixed(1)}%` },
    top3_pct: { label: 'Top 3 Positions', format: (v) => `${v.toFixed(1)}%` },
    sector_hhi: { label: 'Sector HHI', format: (v) => v.toFixed(3) },
  },
  volatility: {
    annualized_vol_pct: { label: 'Annualized Vol', format: (v) => `${v.toFixed(1)}%` },
    max_drawdown_pct: { label: 'Max Drawdown', format: (v) => `${v.toFixed(1)}%` },
    worst_stress_pct: { label: 'Worst Stress', format: (v) => `-${v.toFixed(1)}%` },
  },
  correlation: {
    high_corr_pairs: { label: 'Correlated Pairs', format: (v) => `${v}` },
  },
}

// ── Factor breakdown bars (expandable) ──
function FactorBreakdown({ factors }: { factors: RiskProfile['factor_breakdown'] }) {
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  return (
    <div className="space-y-3">
      {Object.entries(factors).map(([key, factor]) => {
        const label = FACTOR_LABELS[key]
        if (!label || !factor) return null
        const score = factor.score
        const color = score > 70 ? '#F2937F' : score > 40 ? '#DFB65A' : '#7FE3A9'
        const isExpanded = expandedKey === key
        const detailDefs = DETAIL_LABELS[key] || {}
        const details = factor.details || {}

        return (
          <div key={key}>
            <button
              onClick={() => setExpandedKey(isExpanded ? null : key)}
              className="w-full text-left group"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1">
                  <span className="text-[13px] text-text-secondary font-medium group-hover:text-text-primary transition-colors">{label.name}</span>
                  <span className="font-mono text-[10px] text-text-tertiary ml-1 tabular-nums">{Math.round(factor.weight * 100)}%</span>
                  <ChevronDown className={clsx(
                    'w-3 h-3 text-text-tertiary transition-transform duration-200',
                    isExpanded && 'rotate-180'
                  )} />
                </div>
                <span className="font-mono text-[13px] font-medium tabular-nums" style={{ color }}>{score}</span>
              </div>
              <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{ width: `${score}%`, backgroundColor: color }}
                />
              </div>
            </button>
            {isExpanded && Object.keys(detailDefs).length > 0 && (
              <div className="mt-1.5 ml-1 pl-2 border-l border-[rgba(180,220,190,0.12)] space-y-1">
                {Object.entries(detailDefs).map(([dk, def]) => {
                  const val = details[dk]
                  if (val === undefined) return null
                  return (
                    <div key={dk} className="flex items-center justify-between text-[11px]">
                      <span className="text-text-tertiary">{def.label}</span>
                      <span className="font-mono text-text-secondary tabular-nums">{def.format(val)}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Finding badges ──
function FindingBadge({ finding }: { finding: RiskProfileFinding }) {
  const config = {
    critical: { icon: AlertTriangle, color: 'text-loss', bg: 'bg-loss/8', border: 'border-loss/10' },
    warning: { icon: Info, color: 'text-warning', bg: 'bg-warning/8', border: 'border-warning/10' },
    positive: { icon: CheckCircle2, color: 'text-gain', bg: 'bg-gain/8', border: 'border-gain/10' },
  }
  const c = config[finding.type] || config.warning
  const Icon = c.icon

  return (
    <div className={clsx('flex items-start gap-2.5 p-3 rounded-lg border', c.bg, c.border)}>
      <Icon className={clsx('w-4 h-4 mt-0.5 shrink-0', c.color)} strokeWidth={1.5} />
      <p className="text-[13px] text-text-secondary leading-relaxed">{finding.text}</p>
    </div>
  )
}

// ── Suggestion card ──
function SuggestionCard({ suggestion, portfolioValue }: {
  suggestion: DiversificationSuggestion
  portfolioValue: number
}) {
  const [expanded, setExpanded] = useState(false)
  const impact = suggestion.impact

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 transition-colors hover:border-accent/25">
      <div className="flex items-start justify-between mb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[15px] font-medium text-text-primary">{suggestion.symbol}</span>
            <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-[4px] bg-accent/10 text-accent uppercase tracking-[0.08em]">
              {suggestion.category}
            </span>
          </div>
          <p className="text-[12px] text-text-tertiary mt-0.5">{suggestion.name}</p>
        </div>
        <div className="text-right">
          <p className="font-serif text-[16px] font-medium text-accent tabular-nums">10%</p>
          <p className="font-mono text-[11px] text-text-tertiary tabular-nums">
            {formatCurrency(suggestion.suggested_allocation_dollar)}
          </p>
        </div>
      </div>

      <p className="text-[12px] text-text-secondary leading-relaxed mb-3">
        {suggestion.reason}
      </p>

      {/* Impact metrics */}
      <div className="grid grid-cols-2 gap-2 mb-2">
        <div className="rounded-[8px] bg-surface-3/50 px-3 py-2">
          <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Best Crash Savings</p>
          <p className="font-serif text-[16px] font-medium text-gain tabular-nums">
            +{formatCurrency(Math.max(impact.crash_savings_2022, impact.crash_savings_2020 || 0, impact.crash_savings_2008 || 0))}
          </p>
        </div>
        <div className="rounded-[8px] bg-surface-3/50 px-3 py-2">
          <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Drawdown Reduction</p>
          <p className="font-serif text-[16px] font-medium text-accent tabular-nums">
            {impact.drawdown_improvement_pct > 0 ? '+' : ''}{impact.drawdown_improvement_pct.toFixed(1)}pp
          </p>
        </div>
      </div>

      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[11px] text-text-tertiary hover:text-text-secondary transition-colors"
      >
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        {expanded ? 'Less' : 'Details'}
      </button>

      {expanded && (
        <div className="mt-2 pt-2 border-t border-[rgba(180,220,190,0.06)] space-y-1">
          <div className="flex justify-between text-[11px]">
            <span className="text-text-tertiary">2022 savings</span>
            <span className="text-gain font-mono tabular-nums">+{formatCurrency(impact.crash_savings_2022)}</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-text-tertiary">COVID 2020 savings</span>
            <span className={clsx('font-mono tabular-nums', (impact.crash_savings_2020 || 0) > 0 ? 'text-gain' : 'text-text-tertiary')}>
              {(impact.crash_savings_2020 || 0) > 0 ? '+' : ''}{formatCurrency(impact.crash_savings_2020 || 0)}
            </span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-text-tertiary">2008 crisis savings</span>
            <span className={clsx('font-mono tabular-nums', (impact.crash_savings_2008 || 0) > 0 ? 'text-gain' : 'text-text-tertiary')}>
              {(impact.crash_savings_2008 || 0) > 0 ? '+' : ''}{formatCurrency(impact.crash_savings_2008 || 0)}
            </span>
          </div>
          <div className="flex justify-between text-[11px] mt-1 pt-1 border-t border-[rgba(180,220,190,0.06)]">
            <span className="text-text-tertiary">Expense ratio</span>
            <span className="text-text-secondary font-mono tabular-nums">{suggestion.expense_ratio}%/yr ({formatCurrency(impact.annual_cost)}/yr)</span>
          </div>
          <div className="flex justify-between text-[11px]">
            <span className="text-text-tertiary">Allocation</span>
            <span className="text-text-secondary font-mono tabular-nums">{formatCurrency(suggestion.suggested_allocation_dollar)} (10% of portfolio)</span>
          </div>
          <Link
            to={`/research?ticker=${suggestion.symbol}`}
            className="flex items-center gap-1 mt-2 text-[11px] text-accent hover:text-accent-hover transition-colors"
          >
            <Search className="w-3 h-3" />
            Research {suggestion.symbol}
          </Link>
        </div>
      )}
    </div>
  )
}

// ── Before/After comparison ──
function BeforeAfterComparison({ data, portfolioValue }: {
  data: RiskProfile['before_after']
  portfolioValue: number
}) {
  const current = data.current
  const suggested = data.suggested
  const improvement = data.improvement

  const rows: { label: string; current: string; suggested: string; improved: boolean }[] = [
    {
      label: '2022 Rate Shock',
      current: `${current.crash_2022_pct}% (${formatCurrency(current.crash_2022_dollar)})`,
      suggested: `${suggested.crash_2022_pct}% (${formatCurrency(suggested.crash_2022_dollar)})`,
      improved: Math.abs(suggested.crash_2022_pct) < Math.abs(current.crash_2022_pct),
    },
    {
      label: 'COVID 2020',
      current: `${current.crash_2020_pct}% (${formatCurrency(current.crash_2020_dollar)})`,
      suggested: `${suggested.crash_2020_pct}% (${formatCurrency(suggested.crash_2020_dollar)})`,
      improved: Math.abs(suggested.crash_2020_pct) < Math.abs(current.crash_2020_pct),
    },
    {
      label: '2008 Financial Crisis',
      current: `${current.crash_2008_pct}% (${formatCurrency(current.crash_2008_dollar)})`,
      suggested: `${suggested.crash_2008_pct}% (${formatCurrency(suggested.crash_2008_dollar)})`,
      improved: Math.abs(suggested.crash_2008_pct) < Math.abs(current.crash_2008_pct),
    },
    {
      label: 'Max Drawdown',
      current: `-${current.max_drawdown_pct}%`,
      suggested: `-${suggested.max_drawdown_pct}%`,
      improved: suggested.max_drawdown_pct < current.max_drawdown_pct,
    },
    {
      label: 'Health Score',
      current: `${current.health_score}/100`,
      suggested: `${suggested.health_score}/100`,
      improved: suggested.health_score > current.health_score,
    },
    {
      label: 'Sectors Represented',
      current: `${current.sectors_count}`,
      suggested: `${suggested.sectors_count}`,
      improved: suggested.sectors_count > current.sectors_count,
    },
    {
      label: 'Effective Positions',
      current: `${current.effective_positions}`,
      suggested: `${suggested.effective_positions}`,
      improved: suggested.effective_positions > current.effective_positions,
    },
  ]

  return (
    <div>
      {/* Hero stat — show max savings across all 3 scenarios */}
      {(() => {
        const maxSavings = Math.max(
          improvement.crash_savings_dollar,
          improvement.crash_savings_2020_dollar || 0,
          improvement.crash_savings_2008_dollar || 0,
        )
        const scenarioLabel = maxSavings === improvement.crash_savings_dollar
          ? '2022-style'
          : maxSavings === (improvement.crash_savings_2008_dollar || 0)
            ? '2008-style'
            : 'COVID-style'
        return maxSavings > 0 ? (
          <div className="rounded-[10px] bg-accent/[0.06] border border-accent/15 p-4 mb-4 flex items-center gap-4">
            <div className="w-12 h-12 rounded-[10px] bg-accent/10 flex items-center justify-center shrink-0">
              <TrendingUp className="w-6 h-6 text-accent" strokeWidth={1.5} />
            </div>
            <div>
              <p className="font-serif text-[24px] font-medium text-accent tabular-nums">
                {formatCurrency(maxSavings)}
              </p>
              <p className="text-[12px] text-text-tertiary">
                protected in a {scenarioLabel} crash with these {improvement.new_sectors_added} changes
              </p>
            </div>
          </div>
        ) : null
      })()}

      {/* Comparison table */}
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
        <div className="grid grid-cols-3 font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary px-4 py-2.5 bg-surface-3/30">
          <span>Metric</span>
          <span className="text-center">Today</span>
          <span className="text-center">With Changes</span>
        </div>
        {rows.map((row) => (
          <div
            key={row.label}
            className="grid grid-cols-3 items-center px-4 py-3 border-t border-[rgba(180,220,190,0.06)] hover:bg-[rgba(207,174,98,0.04)] transition-colors"
          >
            <span className="text-[13px] text-text-secondary">{row.label}</span>
            <span className="font-mono text-[13px] text-text-tertiary tabular-nums text-center">{row.current}</span>
            <span className={clsx(
              'font-mono text-[13px] font-medium tabular-nums text-center',
              row.improved ? 'text-gain' : 'text-text-secondary'
            )}>
              {row.suggested}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ── AI Narrative section ──
function NarrativeSection() {
  const { narrative, loading, error, generate } = useRiskNarrative()

  if (!narrative && !loading && !error) {
    return (
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-accent" strokeWidth={1.5} />
            <h3 className="font-serif text-[16px] font-medium text-text-primary">AI Risk Analysis</h3>
          </div>
        </div>
        <p className="text-[13px] text-text-tertiary mb-4 leading-relaxed">
          Get a personalized narrative interpreting your risk profile — written in plain English, not finance jargon.
        </p>
        <button
          onClick={generate}
          className="flex items-center gap-2 px-4 py-2 rounded-[8px] bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-all press-scale"
        >
          <Sparkles className="w-3.5 h-3.5" />
          Generate Analysis
        </button>
      </div>
    )
  }

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-accent" strokeWidth={1.5} />
        <h3 className="font-serif text-[16px] font-medium text-text-primary">AI Risk Analysis</h3>
        {loading && (
          <span className="font-mono text-[10px] px-2 py-0.5 rounded-full bg-accent/10 text-accent animate-pulse uppercase tracking-[0.08em]">
            Analyzing...
          </span>
        )}
      </div>
      {error ? (
        <div className="text-[13px] text-loss bg-loss/10 px-3 py-2 rounded-[8px] mb-3">{error}</div>
      ) : (
        <div className="prose prose-invert prose-sm max-w-none text-[13px] text-text-secondary leading-relaxed">
          <ReactMarkdown>{narrative || ''}</ReactMarkdown>
          {loading && <span className="inline-block w-2 h-4 bg-accent/60 animate-pulse ml-0.5 rounded-sm" />}
        </div>
      )}
      {!loading && narrative && (
        <button
          onClick={generate}
          className="mt-3 flex items-center gap-1.5 text-[11px] text-text-tertiary hover:text-accent transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Regenerate
        </button>
      )}
    </div>
  )
}

// ── Loading skeleton ──
function LoadingSkeleton() {
  return (
    <div className="px-4 md:px-8 py-6 md:py-8 animate-pulse">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6 h-[300px]">
          <div className="h-44 w-44 bg-surface-3 rounded-full mx-auto" />
        </div>
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 h-[300px]">
          <div className="h-4 w-32 bg-surface-3 rounded mb-4" />
          <div className="space-y-3">
            {[...Array(4)].map((_, i) => <div key={i} className="h-10 bg-surface-3/50 rounded" />)}
          </div>
        </div>
      </div>
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 h-[120px] mb-6" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 h-[200px]" />
        ))}
      </div>
    </div>
  )
}

// ── Disconnected state ──
function DisconnectedState() {
  return (
    <div className="px-4 md:px-8 py-8 md:py-10 max-w-3xl mx-auto">
      <div className="text-center mb-8 animate-fade-in">
        <div className="w-16 h-16 rounded-[14px] bg-accent/10 border border-[rgba(180,220,190,0.12)] flex items-center justify-center mx-auto mb-5">
          <Target className="w-8 h-8 text-accent" strokeWidth={1.5} />
        </div>
        <h2 className="font-serif text-[28px] font-medium text-text-primary tracking-tight mb-3">
          Diversification Intelligence
        </h2>
        <p className="text-[14px] text-text-secondary max-w-md mx-auto leading-relaxed">
          See your real risk profile, discover blind spots, and get specific ETF suggestions
          that would reduce your downside without killing upside.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8 stagger">
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
          <div className="w-9 h-9 rounded-[8px] bg-accent/10 flex items-center justify-center mb-3">
            <Target className="w-4.5 h-4.5 text-accent" strokeWidth={1.5} />
          </div>
          <h4 className="text-[13px] font-medium text-text-primary mb-1">Risk Profile</h4>
          <p className="text-[11px] text-text-tertiary leading-relaxed">
            Your behavioral risk score — what your portfolio reveals about your actual risk tolerance.
          </p>
        </div>
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
          <div className="w-9 h-9 rounded-[8px] bg-warning/10 flex items-center justify-center mb-3">
            <AlertTriangle className="w-4.5 h-4.5 text-warning" strokeWidth={1.5} />
          </div>
          <h4 className="text-[13px] font-medium text-text-primary mb-1">Gap Analysis</h4>
          <p className="text-[11px] text-text-tertiary leading-relaxed">
            Find the sectors and asset classes your portfolio is missing.
          </p>
        </div>
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
          <div className="w-9 h-9 rounded-[8px] bg-gain/10 flex items-center justify-center mb-3">
            <TrendingDown className="w-4.5 h-4.5 text-gain" strokeWidth={1.5} />
          </div>
          <h4 className="text-[13px] font-medium text-text-primary mb-1">Before / After</h4>
          <p className="text-[11px] text-text-tertiary leading-relaxed">
            See exactly how much less you'd lose in a crash with 3 simple changes.
          </p>
        </div>
      </div>

      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-[10px] bg-accent/10 flex items-center justify-center shrink-0">
              <Link2 className="w-6 h-6 text-accent" strokeWidth={1.5} />
            </div>
            <div>
              <h3 className="font-serif text-[16px] font-medium text-text-primary mb-0.5">Connect to get started</h3>
              <p className="text-[13px] text-text-tertiary">Your risk profile is computed from actual positions</p>
            </div>
          </div>
          <Link
            to="/settings"
            className="flex items-center gap-2 px-5 py-2.5 rounded-[8px] bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-all press-scale shrink-0"
          >
            Connect
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </div>
  )
}

// ── Main page ──
export default function Diversify({ embedded = false }: { embedded?: boolean }) {
  const { data: profile, source, refetch, loading } = useRiskProfile()
  const isDisconnected = source === 'disconnected' && !loading && profile.portfolio_value === 0

  return (
    <div className="min-h-screen">
      {/* Top bar (hidden when embedded in the Optimize super-page) */}
      {!embedded && (
        <div className="sticky top-0 z-30 bg-base/80 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
          <div className="flex items-center justify-between px-4 md:px-8 h-14">
            <h1 className="font-serif text-[16px] font-medium text-text-primary tracking-tight">Diversify</h1>
            <div className="flex items-center gap-2">
              <SyncButton />
              <NotificationsBell />
            </div>
          </div>
          <div className="header-gradient-line" />
        </div>
      )}

      {loading ? <LoadingSkeleton /> : isDisconnected ? <DisconnectedState /> : (
        <div className="px-4 md:px-8 py-6 md:py-8">
          {/* Portfolio context bar */}
          <div className="flex items-center gap-4 mb-5 animate-fade-in">
            <div className="flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-text-tertiary" strokeWidth={1.5} />
              <span className="font-mono text-[13px] text-text-secondary font-medium tabular-nums">
                {formatCurrency(profile.portfolio_value)}
              </span>
            </div>
            <div className="w-px h-4 bg-[rgba(180,220,190,0.12)]" />
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-text-tertiary" strokeWidth={1.5} />
              <span className="text-[13px] text-text-secondary">
                {profile.factor_breakdown.composition?.details?.num_holdings || '—'} holdings
              </span>
            </div>
            <div className="w-px h-4 bg-[rgba(180,220,190,0.12)]" />
            <span className="text-[13px] text-text-tertiary">
              {profile.factor_breakdown.concentration?.details?.top1_pct
                ? `Top position: ${profile.factor_breakdown.concentration.details.top1_pct.toFixed(0)}%`
                : ''}
            </span>
          </div>

          {/* Row 1: Score + Factors */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6 mb-6 stagger">
            {/* Risk Score Gauge */}
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6 flex flex-col items-center justify-center">
              <h3 className="font-mono text-[10px] text-text-tertiary mb-4 uppercase tracking-[0.13em]">
                Behavioral Risk Score
              </h3>
              <BehavioralScoreGauge score={profile.behavioral_score} persona={profile.persona} />
            </div>

            {/* Factor Breakdown */}
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
              <h3 className="font-serif text-[16px] font-medium text-text-primary mb-4">What Drives Your Score</h3>
              <FactorBreakdown factors={profile.factor_breakdown} />
              <p className="text-[11px] text-text-tertiary mt-3">
                Higher bars = more risk. Each factor is weighted by its importance to overall portfolio risk.
              </p>
            </div>
          </div>

          {/* Row 2: Key Findings */}
          {profile.key_findings.length > 0 && (
            <div className="mb-6 stagger">
              <h3 className="font-serif text-[16px] font-medium text-text-primary mb-3">Key Findings</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {profile.key_findings.map((f, i) => (
                  <FindingBadge key={i} finding={f} />
                ))}
              </div>
            </div>
          )}

          {/* Row 3: AI Narrative */}
          <div className="mb-6 stagger">
            <NarrativeSection />
          </div>

          {/* Row 4: Before/After */}
          {(profile.before_after.improvement.crash_savings_dollar > 0 ||
            profile.before_after.current.sectors_count > 0) && (
            <div className="mb-6 stagger">
              <h3 className="font-serif text-[16px] font-medium text-text-primary mb-3">Before vs After</h3>
              <BeforeAfterComparison data={profile.before_after} portfolioValue={profile.portfolio_value} />
            </div>
          )}

          {/* Row 5: Diversification Suggestions */}
          {profile.diversification_suggestions.length > 0 && (
            <div className="mb-6 stagger">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-serif text-[16px] font-medium text-text-primary">Suggested Additions</h3>
                <span className="text-[11px] text-text-tertiary">10% allocation each</span>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {profile.diversification_suggestions.map((s) => (
                  <SuggestionCard key={s.symbol} suggestion={s} portfolioValue={profile.portfolio_value} />
                ))}
              </div>
            </div>
          )}

          {/* Disclaimer */}
          <div className="mt-8 mb-4">
            <p className="text-[10px] text-text-tertiary/60 leading-relaxed max-w-3xl">
              Emouva provides portfolio analytics and educational tools. These insights are for informational
              purposes only and do not constitute investment advice or a recommendation to buy or sell any
              security. Past performance does not guarantee future results. Investing involves risk, including
              possible loss of principal. Consult a qualified financial advisor before making investment decisions.
            </p>
          </div>
        </div>
      )}
    </div>
  )
}
