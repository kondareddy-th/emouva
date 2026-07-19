import { useState, useEffect, useMemo } from 'react'
import { apiFetch } from '../api/client'
import { useNavigate } from 'react-router-dom'
import { usePositions } from '../hooks/usePortfolio'
import {
  Zap, TrendingDown, Globe, Factory, AlertTriangle,
  History, ChevronDown, ChevronUp, Search, RefreshCw,
  ArrowRight, Shield, Clock, Info, Loader2,
} from 'lucide-react'

// ── Types ────────────────────────────────────────────────────────

interface ScenarioListItem {
  id: string
  name: string
  category: string
  severity: number
  description: string
  sp500_impact: number | null
  duration_months: number | null
  tags: string[]
  version: string
}

interface StockImpact {
  symbol: string
  name: string
  sector: string
  current_value: number
  stressed_value: number
  change_pct: number
  change_usd: number
  weight_pct: number
  sensitivity_factors: string[]
  historical_actual: number | null
}

interface StressTestResult {
  result_id: string
  scenario: {
    id: string
    name: string
    description: string
    category: string
    severity: number
    sp500_impact: number | null
    duration_months: number | null
    tags: string[]
  }
  portfolio_impact: {
    total_value_before: number
    total_value_after: number
    total_change_pct: number
    total_change_usd: number
    worst_day_estimate_pct: number
    recovery_time_months: number | null
  }
  per_stock_impact: StockImpact[]
  correlation_adjustment: {
    applied: boolean
    normal_portfolio_correlation: number
    stressed_portfolio_correlation: number
    additional_impact_pct: number
  } | null
  confidence: {
    level: string
    methodology: string
    data_coverage_pct: number
    disclaimer: string
  }
}

// ── Constants ────────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, typeof Zap> = {
  historical: History,
  macro: TrendingDown,
  geopolitical: Globe,
  sector: Factory,
  black_swan: AlertTriangle,
}

const CATEGORY_LABELS: Record<string, string> = {
  historical: 'Historical',
  macro: 'Macro',
  geopolitical: 'Geopolitical',
  sector: 'Sector',
  black_swan: 'Black Swan',
}

const SEVERITY_COLORS: Record<string, string> = {
  low: 'text-gain',
  mid: 'text-warning',
  high: 'text-loss',
  extreme: 'text-[#B0524A]',
}

function severityLevel(s: number): string {
  if (s <= 3) return 'low'
  if (s <= 5) return 'mid'
  if (s <= 7) return 'high'
  return 'extreme'
}

function formatUSD(n: number): string {
  const abs = Math.abs(n)
  if (abs >= 1000) return `$${(abs / 1000).toFixed(1)}k`
  return `$${abs.toFixed(0)}`
}

function formatUSDFull(n: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(n)
}

// ── Component ────────────────────────────────────────────────────

export default function StressTest({ embedded = false }: { embedded?: boolean }) {
  const navigate = useNavigate()
  const { data: positions } = usePositions()
  const [scenarios, setScenarios] = useState<ScenarioListItem[]>([])
  const [scenariosLoading, setScenariosLoading] = useState(true)
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [result, setResult] = useState<StressTestResult | null>(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [expandedStock, setExpandedStock] = useState<string | null>(null)
  const [customScenario, setCustomScenario] = useState('')
  const [showCustom, setShowCustom] = useState(false)

  // Load scenarios on mount
  useEffect(() => {
    apiFetch<{ scenarios: ScenarioListItem[] }>('/api/stress-test/scenarios')
      .then((data) => setScenarios(data.scenarios))
      .catch(() => setError('Failed to load scenarios'))
      .finally(() => setScenariosLoading(false))
  }, [])

  // Filtered scenarios
  const filtered = useMemo(() => {
    let list = scenarios
    if (selectedCategory) {
      list = list.filter((s) => s.category === selectedCategory)
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      list = list.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q) ||
          s.tags.some((t) => t.includes(q))
      )
    }
    return list
  }, [scenarios, selectedCategory, searchQuery])

  const categories = useMemo(
    () => [...new Set(scenarios.map((s) => s.category))],
    [scenarios]
  )

  // Run a stress test
  async function runTest(scenarioId: string | null, customText?: string) {
    setRunning(true)
    setError(null)
    setResult(null)
    setExpandedStock(null)

    try {
      const body: Record<string, unknown> = {}
      if (scenarioId) body.scenario_id = scenarioId
      else if (customText) body.custom_scenario = customText
      else return

      // Send the current holdings so the backend stresses the real portfolio
      // (it has no live brokerage fallback). Without this it stresses an empty
      // portfolio and errors with "No portfolio holdings available".
      if (positions.length > 0) {
        body.portfolio = positions.map((p) => ({
          symbol: p.symbol,
          shares: p.shares,
          current_price: p.currentPrice,
        }))
      }

      const data = await apiFetch<StressTestResult>('/api/stress-test/run', {
        method: 'POST',
        body: JSON.stringify(body),
      })
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Stress test failed')
    } finally {
      setRunning(false)
    }
  }

  function handleCustomSubmit() {
    if (!customScenario.trim()) return
    runTest(null, customScenario.trim())
  }

  // Back to scenario selection
  function handleBack() {
    setResult(null)
    setError(null)
  }

  return (
    <div className="p-4 md:p-6 max-w-6xl mx-auto">
      {/* Header (hidden when embedded in the Optimize super-page) */}
      <div className={embedded ? 'mb-2' : 'mb-6'}>
        <div className="flex items-center justify-between">
          {embedded ? <div /> : (
            <div>
              <h1 className="font-serif text-[24px] font-medium text-text-primary tracking-tight">
                Portfolio Stress Test
              </h1>
              <p className="text-[13px] text-text-secondary mt-1">
                See how your portfolio could perform under different market scenarios
              </p>
            </div>
          )}
          {result && (
            <button
              onClick={handleBack}
              className="px-3 py-1.5 rounded-[8px] bg-surface-2 border border-[rgba(180,220,190,0.12)] text-[12px] font-medium text-text-secondary hover:text-text-primary hover:border-[rgba(180,220,190,0.20)] transition-all"
            >
              ← Back to Scenarios
            </button>
          )}
        </div>
        {!embedded && <div className="header-gradient-line mt-3" />}
      </div>

      {/* Results view */}
      {result ? (
        <ResultsView
          result={result}
          expandedStock={expandedStock}
          onToggleStock={(s) => setExpandedStock(expandedStock === s ? null : s)}
          onRunAnother={handleBack}
          navigate={navigate}
        />
      ) : (
        <>
          {/* Search + Category Chips */}
          <div className="flex flex-col sm:flex-row gap-3 mb-5">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" />
              <input
                type="text"
                placeholder="Search scenarios... (e.g., recession, China, AI)"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] text-[13px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent/40 transition-colors"
              />
            </div>
          </div>

          {/* Category chips */}
          <div className="flex gap-2 mb-5 overflow-x-auto pb-1 scrollbar-thin">
            <button
              onClick={() => setSelectedCategory(null)}
              className={`px-3 py-1.5 rounded-[8px] font-mono text-[11px] tracking-[0.04em] whitespace-nowrap transition-all ${
                !selectedCategory
                  ? 'bg-accent/10 text-accent border border-accent/25'
                  : 'bg-surface-2 text-text-tertiary border border-[rgba(180,220,190,0.12)] hover:text-text-secondary'
              }`}
            >
              All ({scenarios.length})
            </button>
            {categories.map((cat) => {
              const Icon = CATEGORY_ICONS[cat] || Zap
              const count = scenarios.filter((s) => s.category === cat).length
              return (
                <button
                  key={cat}
                  onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-[8px] font-mono text-[11px] tracking-[0.04em] whitespace-nowrap transition-all ${
                    selectedCategory === cat
                      ? 'bg-accent/10 text-accent border border-accent/25'
                      : 'bg-surface-2 text-text-tertiary border border-[rgba(180,220,190,0.12)] hover:text-text-secondary'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  {CATEGORY_LABELS[cat] || cat} ({count})
                </button>
              )
            })}
          </div>

          {/* Custom scenario input */}
          <div className="mb-5">
            <button
              onClick={() => setShowCustom(!showCustom)}
              className="flex items-center gap-2 text-[13px] text-text-secondary hover:text-accent transition-colors"
            >
              <Search className="w-3.5 h-3.5" />
              {showCustom ? 'Hide custom scenario' : 'Or describe your own scenario...'}
            </button>
            {showCustom && (
              <div className="mt-3 flex gap-2">
                <input
                  type="text"
                  placeholder='e.g., "What if China bans rare earth exports?"'
                  value={customScenario}
                  onChange={(e) => setCustomScenario(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCustomSubmit()}
                  className="flex-1 px-4 py-2.5 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] text-[13px] text-text-primary placeholder:text-text-tertiary focus:outline-none focus:border-accent/40"
                />
                <button
                  onClick={handleCustomSubmit}
                  disabled={running || !customScenario.trim()}
                  className="px-4 py-2.5 rounded-[10px] bg-accent text-base text-[13px] font-medium hover:bg-accent-hover disabled:opacity-40 transition-all"
                >
                  {running ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Run Test'}
                </button>
              </div>
            )}
          </div>

          {/* Loading state */}
          {running && (
            <div className="flex flex-col items-center justify-center py-20 gap-4">
              <div className="w-12 h-12 rounded-[10px] bg-accent/10 flex items-center justify-center">
                <Loader2 className="w-6 h-6 text-accent animate-spin" />
              </div>
              <div className="text-center">
                <p className="text-[14px] font-medium text-text-primary">Analyzing your portfolio...</p>
                <p className="text-[12px] text-text-tertiary mt-1">Computing per-stock impact with factor model</p>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="rounded-[10px] bg-loss/10 border border-loss/20 p-4 mb-5">
              <p className="text-[13px] text-loss">{error}</p>
            </div>
          )}

          {/* Scenarios loading skeleton */}
          {scenariosLoading && !running && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 h-36 animate-pulse" />
              ))}
            </div>
          )}

          {/* Scenario Cards */}
          {!scenariosLoading && !running && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {filtered.map((scenario) => (
                <ScenarioCard
                  key={scenario.id}
                  scenario={scenario}
                  onRun={() => runTest(scenario.id)}
                  disabled={running}
                />
              ))}
              {filtered.length === 0 && (
                <div className="col-span-full text-center py-12 text-text-tertiary text-[13px] font-serif italic">
                  No scenarios match your search.
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Scenario Card ────────────────────────────────────────────────

function ScenarioCard({
  scenario,
  onRun,
  disabled,
}: {
  scenario: ScenarioListItem
  onRun: () => void
  disabled: boolean
}) {
  const Icon = CATEGORY_ICONS[scenario.category] || Zap
  const level = severityLevel(scenario.severity)

  return (
    <button
      onClick={onRun}
      disabled={disabled}
      className="group text-left rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 hover:border-accent/25 hover:bg-[rgba(207,174,98,0.04)] transition-all duration-200 disabled:opacity-40"
    >
      <div className="flex items-start justify-between mb-2.5">
        <div className="w-8 h-8 rounded-[8px] bg-[rgba(180,220,190,0.06)] flex items-center justify-center">
          <Icon className={`w-4 h-4 ${SEVERITY_COLORS[level]}`} strokeWidth={1.5} />
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`font-mono text-[11px] font-medium tabular-nums ${SEVERITY_COLORS[level]}`}>
            {scenario.severity}/10
          </span>
          {scenario.sp500_impact !== null && (
            <span className="font-mono text-[11px] text-text-tertiary tabular-nums">
              S&P {scenario.sp500_impact > 0 ? '+' : ''}{scenario.sp500_impact}%
            </span>
          )}
        </div>
      </div>
      <h3 className="font-serif text-[15px] font-medium text-text-primary mb-1 group-hover:text-accent transition-colors">
        {scenario.name}
      </h3>
      <p className="text-[12px] text-text-tertiary leading-relaxed line-clamp-2">
        {scenario.description}
      </p>
      {scenario.duration_months && (
        <div className="flex items-center gap-1 mt-2.5 font-mono text-[11px] text-text-tertiary tabular-nums">
          <Clock className="w-3 h-3" />
          <span>~{scenario.duration_months}mo duration</span>
        </div>
      )}
    </button>
  )
}

// ── Results View ─────────────────────────────────────────────────

function ResultsView({
  result,
  expandedStock,
  onToggleStock,
  onRunAnother,
  navigate,
}: {
  result: StressTestResult
  expandedStock: string | null
  onToggleStock: (s: string) => void
  onRunAnother: () => void
  navigate: ReturnType<typeof useNavigate>
}) {
  const { portfolio_impact: pi, per_stock_impact: stocks, scenario, confidence, correlation_adjustment: corr } = result
  const isLoss = pi.total_change_usd < 0

  return (
    <div className="space-y-5 stagger">
      {/* Impact Summary Card */}
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <div>
            <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">
              Scenario
            </p>
            <h2 className="font-serif text-[20px] font-medium text-text-primary">{scenario.name}</h2>
            <p className="text-[12px] text-text-tertiary mt-0.5">{scenario.description}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`font-mono text-[11px] font-medium px-2 py-0.5 rounded-[6px] tabular-nums ${
              severityLevel(scenario.severity) === 'extreme' ? 'bg-[#B0524A]/10 text-[#B0524A]' :
              severityLevel(scenario.severity) === 'high' ? 'bg-loss/10 text-loss' :
              severityLevel(scenario.severity) === 'mid' ? 'bg-warning/10 text-warning' :
              'bg-gain/10 text-gain'
            }`}>
              Severity {scenario.severity}/10
            </span>
            <span className="font-mono text-[10px] text-text-tertiary px-2 py-0.5 rounded-[6px] bg-[rgba(180,220,190,0.06)] uppercase tracking-[0.08em]">
              {confidence.methodology.replace(/_/g, ' ')}
            </span>
          </div>
        </div>

        {/* Big numbers */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Portfolio Today</p>
            <p className="font-serif text-[20px] font-medium text-text-primary tabular-nums">{formatUSDFull(pi.total_value_before)}</p>
          </div>
          <div>
            <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">After Scenario</p>
            <p className="font-serif text-[20px] font-medium text-text-primary tabular-nums">{formatUSDFull(pi.total_value_after)}</p>
          </div>
          <div>
            <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Estimated Impact</p>
            <p className={`font-serif text-[24px] font-medium tabular-nums ${isLoss ? 'text-loss' : 'text-gain'}`}>
              {isLoss ? '-' : '+'}{formatUSDFull(Math.abs(pi.total_change_usd))}
            </p>
          </div>
          <div>
            <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Percentage</p>
            <p className={`font-serif text-[20px] font-medium tabular-nums ${isLoss ? 'text-loss' : 'text-gain'}`}>
              {pi.total_change_pct > 0 ? '+' : ''}{pi.total_change_pct}%
            </p>
          </div>
        </div>

        {/* Recovery + Context */}
        <div className="flex flex-wrap gap-3 mt-4 pt-3 border-t border-[rgba(180,220,190,0.10)]">
          {pi.recovery_time_months && (
            <div className="flex items-center gap-1.5 text-[12px] text-text-tertiary">
              <Clock className="w-3.5 h-3.5" />
              <span>Markets historically recovered in ~{pi.recovery_time_months} months</span>
            </div>
          )}
          {corr?.applied && (
            <div className="flex items-center gap-1.5 text-[12px] text-text-tertiary">
              <Info className="w-3.5 h-3.5" />
              <span>
                Correlation spike: {(corr.normal_portfolio_correlation * 100).toFixed(0)}% → {(corr.stressed_portfolio_correlation * 100).toFixed(0)}% ({corr.additional_impact_pct > 0 ? '+' : ''}{corr.additional_impact_pct}% extra impact)
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Waterfall Chart */}
      <WaterfallChart stocks={stocks} totalBefore={pi.total_value_before} />

      {/* Per-Stock Impact Table */}
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
        <div className="px-4 py-3 border-b border-[rgba(180,220,190,0.10)]">
          <h3 className="font-serif text-[16px] font-medium text-text-primary">Per-Stock Impact</h3>
          <p className="text-[11px] text-text-tertiary mt-0.5">Click a stock for details</p>
        </div>

        {/* Header row */}
        <div className="hidden sm:grid grid-cols-[1fr_90px_90px_90px_60px] gap-2 px-4 py-2 font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] border-b border-[rgba(180,220,190,0.06)]">
          <span>Stock</span>
          <span className="text-right">Current Value</span>
          <span className="text-right">Est. Impact</span>
          <span className="text-right">Your Loss</span>
          <span className="text-right">Weight</span>
        </div>

        {stocks.map((stock) => (
          <StockRow
            key={stock.symbol}
            stock={stock}
            expanded={expandedStock === stock.symbol}
            onToggle={() => onToggleStock(stock.symbol)}
            onResearch={() => navigate(`/research?ticker=${stock.symbol}`)}
          />
        ))}
      </div>

      {/* Disclaimer */}
      <div className="rounded-[10px] bg-[rgba(180,220,190,0.03)] border border-[rgba(180,220,190,0.06)] p-4">
        <div className="flex items-start gap-2">
          <Shield className="w-4 h-4 text-text-tertiary flex-shrink-0 mt-0.5" strokeWidth={1.5} />
          <div>
            <p className="text-[11px] text-text-tertiary leading-relaxed">
              <span className="font-medium text-text-secondary">Hypothetical illustration only.</span>{' '}
              {confidence.disclaimer} Actual results could be significantly different.
              Data coverage: {confidence.data_coverage_pct}% of your holdings.
            </p>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={onRunAnother}
          className="flex items-center gap-2 px-4 py-2.5 rounded-[10px] bg-accent text-base text-[13px] font-medium hover:bg-accent-hover transition-all"
        >
          <RefreshCw className="w-4 h-4" />
          Test Another Scenario
        </button>
        <button
          onClick={() => navigate('/diversify')}
          className="flex items-center gap-2 px-4 py-2.5 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] text-[13px] font-medium text-text-secondary hover:text-text-primary hover:border-accent/25 transition-all"
        >
          <Shield className="w-4 h-4" strokeWidth={1.5} />
          Protect My Portfolio
          <ArrowRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  )
}

// ── Waterfall Chart ──────────────────────────────────────────────

function WaterfallChart({
  stocks,
  totalBefore,
}: {
  stocks: StockImpact[]
  totalBefore: number
}) {
  // Sort by absolute impact (largest loss first)
  const sorted = [...stocks].sort((a, b) => a.change_usd - b.change_usd)
  const maxAbsImpact = Math.max(...sorted.map((s) => Math.abs(s.change_usd)), 1)
  const topN = sorted.slice(0, 10) // Show top 10

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4">
      <h3 className="font-serif text-[16px] font-medium text-text-primary mb-3">Impact Cascade</h3>
      <div className="space-y-1.5">
        {topN.map((stock) => {
          const isLoss = stock.change_usd < 0
          const barWidth = Math.min(100, (Math.abs(stock.change_usd) / maxAbsImpact) * 100)

          return (
            <div key={stock.symbol} className="flex items-center gap-3">
              <span className="w-12 font-mono text-[12px] font-medium text-text-primary text-right shrink-0">
                {stock.symbol}
              </span>
              <div className="flex-1 h-6 relative rounded-[6px] overflow-hidden bg-[rgba(180,220,190,0.05)]">
                <div
                  className={`absolute top-0 h-full rounded-[6px] transition-all duration-500 ${
                    isLoss ? 'bg-loss/25 left-0' : 'bg-gain/25 left-0'
                  }`}
                  style={{ width: `${barWidth}%` }}
                />
                <div className="absolute inset-0 flex items-center px-2">
                  <span className={`font-mono text-[11px] font-medium tabular-nums ${
                    isLoss ? 'text-loss' : 'text-gain'
                  }`}>
                    {isLoss ? '-' : '+'}{formatUSDFull(Math.abs(stock.change_usd))} ({stock.change_pct > 0 ? '+' : ''}{stock.change_pct}%)
                  </span>
                </div>
              </div>
            </div>
          )
        })}
        {stocks.length > 10 && (
          <p className="text-[11px] text-text-tertiary text-center pt-1">
            +{stocks.length - 10} more positions
          </p>
        )}
      </div>
    </div>
  )
}

// ── Stock Row ────────────────────────────────────────────────────

function StockRow({
  stock,
  expanded,
  onToggle,
  onResearch,
}: {
  stock: StockImpact
  expanded: boolean
  onToggle: () => void
  onResearch: () => void
}) {
  const isLoss = stock.change_usd < 0

  return (
    <div className="border-b border-[rgba(180,220,190,0.06)] last:border-0">
      <button
        onClick={onToggle}
        className="w-full grid grid-cols-[1fr_auto] sm:grid-cols-[1fr_90px_90px_90px_60px] gap-2 px-4 py-3 text-left hover:bg-[rgba(207,174,98,0.04)] transition-colors items-center"
      >
        <div className="flex items-center gap-2.5">
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5 text-text-tertiary flex-shrink-0" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 text-text-tertiary flex-shrink-0" />
          )}
          <div>
            <span className="font-mono text-[13px] font-medium text-text-primary">{stock.symbol}</span>
            <span className="text-[11px] text-text-tertiary ml-1.5 hidden sm:inline">{stock.sector}</span>
          </div>
        </div>
        <span className="font-mono text-[13px] text-text-secondary text-right hidden sm:block tabular-nums">
          {formatUSDFull(stock.current_value)}
        </span>
        <span className={`font-mono text-[13px] font-medium text-right hidden sm:block tabular-nums ${isLoss ? 'text-loss' : 'text-gain'}`}>
          {stock.change_pct > 0 ? '+' : ''}{stock.change_pct}%
        </span>
        <span className={`font-mono text-[13px] font-medium text-right tabular-nums ${isLoss ? 'text-loss' : 'text-gain'}`}>
          {isLoss ? '-' : '+'}{formatUSDFull(Math.abs(stock.change_usd))}
        </span>
        <span className="font-mono text-[12px] text-text-tertiary text-right hidden sm:block tabular-nums">
          {stock.weight_pct}%
        </span>
      </button>

      {/* Expanded details */}
      {expanded && (
        <div className="px-4 pb-3 pl-10 space-y-2">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-[12px]">
            <div>
              <span className="text-text-tertiary">Current: </span>
              <span className="font-mono text-text-secondary tabular-nums">{formatUSDFull(stock.current_value)}</span>
            </div>
            <div>
              <span className="text-text-tertiary">After: </span>
              <span className="font-mono text-text-secondary tabular-nums">{formatUSDFull(stock.stressed_value)}</span>
            </div>
            {stock.historical_actual !== null && (
              <div>
                <span className="text-text-tertiary">Actual historical: </span>
                <span className={`font-mono font-medium tabular-nums ${stock.historical_actual < 0 ? 'text-loss' : 'text-gain'}`}>
                  {stock.historical_actual > 0 ? '+' : ''}{stock.historical_actual}%
                </span>
              </div>
            )}
          </div>
          {stock.sensitivity_factors.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {stock.sensitivity_factors.map((f, i) => (
                <span
                  key={i}
                  className="px-2 py-0.5 rounded-[6px] bg-[rgba(180,220,190,0.06)] text-[11px] text-text-tertiary"
                >
                  {f}
                </span>
              ))}
            </div>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation()
              onResearch()
            }}
            className="text-[12px] text-accent hover:text-accent-hover transition-colors flex items-center gap-1"
          >
            Research {stock.symbol} <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  )
}
