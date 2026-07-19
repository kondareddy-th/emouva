import { useState, useCallback, useRef, useEffect } from 'react'
import {
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  FileText,
  ChevronDown,
  Search,
  RefreshCw,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  Eye,
  Scissors,
  XCircle,
  BarChart3,
} from 'lucide-react'
import clsx from 'clsx'
import { apiStream, apiFetch, type SSEDoneEvent } from '../api/client'
import { getCache, setCache, clearCache } from '../hooks/useLocalCache'
import { getSelectedAccount } from '../hooks/usePortfolioStore'
import { type DailyBriefAlert, type StockVerdict } from '../data/mockData'

const alertIconMap: Record<string, any> = {
  rebalance: BarChart3,
  tax_harvest: DollarSign,
  thesis_break: AlertTriangle,
  risk: AlertTriangle,
  opportunity: TrendingUp,
  overvalued: TrendingDown,
  undervalued: TrendingUp,
  // Legacy types
  correlation: AlertTriangle,
  earnings: FileText,
  tax: DollarSign,
  thesis: FileText,
  macro: TrendingUp,
}

const severityColor: Record<DailyBriefAlert['severity'], string> = {
  info: 'text-text-tertiary',
  warning: 'text-warning',
  critical: 'text-loss',
}

const verdictConfig: Record<string, { label: string; color: string; icon: any }> = {
  strong_hold: { label: 'Strong Hold', color: 'text-gain', icon: ShieldCheck },
  hold: { label: 'Hold', color: 'text-text-secondary', icon: ShieldCheck },
  watch: { label: 'Watch', color: 'text-warning', icon: Eye },
  trim: { label: 'Trim', color: 'text-warning', icon: Scissors },
  sell: { label: 'Sell', color: 'text-loss', icon: XCircle },
}

interface AnalysisData {
  summary: string
  alerts: DailyBriefAlert[]
  stock_analyses: StockVerdict[]
  market_context: string
}

interface CachedAnalysis {
  data: AnalysisData
  generatedAt: string
}

function getCacheKey() {
  return `portfolio_analysis_${new Date().toISOString().slice(0, 10)}`
}

export default function DailyBrief() {
  const [data, setData] = useState<AnalysisData | null>(() => {
    const cached = getCache<CachedAnalysis>(getCacheKey())
    return cached?.data ?? null
  })
  const [generatedAt, setGeneratedAt] = useState<string | null>(() => {
    const cached = getCache<CachedAnalysis>(getCacheKey())
    return cached?.generatedAt ?? null
  })
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState('')
  const [streamText, setStreamText] = useState('')
  const [expandedAlerts, setExpandedAlerts] = useState<Set<number>>(new Set())
  const [showStocks, setShowStocks] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  // Load the DB-cached brief (per account) on mount — the source of truth that
  // persists across sessions/devices until the user refreshes. Overrides the
  // localStorage flash-of-content above.
  useEffect(() => {
    const acct = getSelectedAccount()
    const q = acct ? `?account=${encodeURIComponent(acct)}` : ''
    apiFetch<{ data: AnalysisData | null; generated_at: string | null }>(`/api/brief/latest${q}`)
      .then((res) => {
        if (res?.data) {
          setData(res.data)
          if (res.generated_at) {
            setGeneratedAt(new Date(res.generated_at).toLocaleString('en-US', {
              month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
            }))
          }
        }
      })
      .catch(() => {})
  }, [])

  const toggleAlert = (index: number) => {
    setExpandedAlerts(prev => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  const runAnalysis = useCallback(() => {
    // Cancel any existing stream
    abortRef.current?.abort()

    setLoading(true)
    setStatusMessage('Starting analysis...')
    setStreamText('')
    setData(null)

    const controller = apiStream('/api/brief/generate/stream', {
      onStatus: ({ message }) => {
        setStatusMessage(message)
      },
      onDelta: ({ text }) => {
        setStreamText(prev => prev + text)
      },
      onDone: ({ result }: SSEDoneEvent) => {
        const analysisData = result as unknown as AnalysisData
        setData(analysisData)
        const now = new Date().toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
        setGeneratedAt(now)
        setCache(getCacheKey(), { data: analysisData, generatedAt: now }, 24 * 60 * 60 * 1000)
        // Persist per account to DB so the same brief shows across sessions/devices
        // until the user refreshes.
        const acct = getSelectedAccount()
        const saveQ = acct ? `?account=${encodeURIComponent(acct)}` : ''
        apiFetch(`/api/brief/save${saveQ}`, { method: 'POST', body: JSON.stringify(analysisData) }).catch(() => {})
        setExpandedAlerts(new Set())
        setLoading(false)
        setStatusMessage('')
        setStreamText('')
        abortRef.current = null
      },
      onError: ({ message }) => {
        setStatusMessage(`Error: ${message}`)
        setLoading(false)
        abortRef.current = null
      },
    })

    abortRef.current = controller
  }, [])

  const alerts = data?.alerts ?? []
  const stocks = data?.stock_analyses ?? []

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-[rgba(180,220,190,0.08)] flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Search className="w-4 h-4 text-text-tertiary" strokeWidth={1.5} />
          <div>
            <h3 className="text-[16px] font-serif font-medium text-text-primary">
              Portfolio Analysis
            </h3>
            <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mt-0.5">
              Deep research on every holding
              {generatedAt && (
                <span className="text-text-tertiary/60"> · Last run {generatedAt}</span>
              )}
            </p>
          </div>
        </div>
        {data ? (
          <button
            onClick={() => {
              clearCache(getCacheKey())
              runAnalysis()
            }}
            disabled={loading}
            className="p-1.5 rounded-md hover:bg-[rgba(207,174,98,0.06)] transition-colors disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-3.5 h-3.5 text-text-tertiary animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5 text-text-tertiary" strokeWidth={1.5} />
            )}
          </button>
        ) : null}
      </div>

      {/* Streaming state — status + progress indicator */}
      {loading && (
        <div className="px-5 py-5">
          <div className="flex items-center gap-2.5 mb-3">
            <Loader2 className="w-4 h-4 text-accent animate-spin flex-shrink-0" />
            <p className="text-[13px] text-text-secondary font-medium">{statusMessage}</p>
          </div>
          {streamText ? (
            <div className="mt-2">
              <div className="flex items-center gap-2 mb-1">
                <div className="h-1 flex-1 rounded-full bg-[rgba(180,220,190,0.06)] overflow-hidden">
                  <div className="h-full bg-accent/40 rounded-full animate-pulse" style={{ width: '60%' }} />
                </div>
                <span className="text-[11px] font-mono tabular-nums text-text-tertiary whitespace-nowrap">
                  {Math.round(streamText.length / 1000)}K chars
                </span>
              </div>
              <p className="text-caption text-text-tertiary">
                Claude is analyzing your portfolio. Results will appear when complete.
              </p>
            </div>
          ) : (
            <p className="text-caption text-text-tertiary">
              Fetching fresh data for every position. This may take 30-60 seconds.
            </p>
          )}
        </div>
      )}

      {/* Empty state — prompt user to run analysis */}
      {!loading && !data && (
        <div className="px-5 py-8 text-center">
          <div className="w-1.5 h-1.5 bg-accent rotate-45 mx-auto mb-4" />
          <p className="text-[15px] font-serif text-text-primary mb-1">
            Run a deep analysis on your portfolio
          </p>
          <p className="text-caption text-text-tertiary mb-4">
            Fetches live fundamentals, earnings, and news for every stock.<br />
            Evaluates each position and provides actionable recommendations.
          </p>
          <button
            onClick={runAnalysis}
            className="px-4 py-2 bg-accent hover:bg-accent-hover text-base text-[13px] font-medium rounded-md transition-colors"
          >
            Analyze Portfolio
          </button>
        </div>
      )}

      {/* Results */}
      {!loading && data && (
        <>
          {/* Summary */}
          {data.summary && (
            <div className="px-5 py-3 border-b border-[rgba(180,220,190,0.06)]">
              <p className="text-[13px] text-text-secondary leading-relaxed">
                {data.summary}
              </p>
            </div>
          )}

          {/* Alerts */}
          {alerts.length > 0 && (
            <div>
              <div className="px-5 py-2 border-b border-[rgba(180,220,190,0.06)]">
                <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">
                  Recommendations ({alerts.length})
                </span>
              </div>
              {alerts.map((alert, i) => {
                const Icon = alertIconMap[alert.type] || AlertTriangle
                const isExpanded = expandedAlerts.has(i)
                return (
                  <div
                    key={i}
                    onClick={() => toggleAlert(i)}
                    className={clsx(
                      'px-5 py-3.5 hover:bg-[rgba(207,174,98,0.04)] transition-colors cursor-pointer group',
                      i < alerts.length - 1 && 'border-b border-[rgba(180,220,190,0.06)]'
                    )}
                  >
                    <div className="flex items-start gap-3">
                      <Icon
                        className={clsx(
                          'w-4 h-4 mt-0.5 flex-shrink-0',
                          severityColor[alert.severity] || 'text-text-tertiary'
                        )}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2">
                          <h4 className="text-[13px] font-medium text-text-primary truncate">
                            {alert.title}
                          </h4>
                          <ChevronDown
                            className={clsx(
                              'w-3.5 h-3.5 text-text-tertiary transition-transform flex-shrink-0',
                              isExpanded && 'rotate-180'
                            )}
                          />
                        </div>
                        <p className={clsx(
                          'text-[12px] text-text-tertiary mt-0.5',
                          !isExpanded && 'line-clamp-1'
                        )}>
                          {alert.description}
                        </p>
                        {isExpanded && alert.action && (
                          <p className="text-[12px] text-accent mt-1.5">
                            Action: {alert.action}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Stock Verdicts */}
          {stocks.length > 0 && (
            <div className="border-t border-[rgba(180,220,190,0.08)]">
              <button
                onClick={() => setShowStocks(!showStocks)}
                className="w-full px-5 py-3 flex items-center justify-between hover:bg-[rgba(207,174,98,0.04)] transition-colors"
              >
                <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">
                  Stock Verdicts ({stocks.length})
                </span>
                <ChevronDown
                  className={clsx(
                    'w-3.5 h-3.5 text-text-tertiary transition-transform',
                    showStocks && 'rotate-180'
                  )}
                />
              </button>
              {showStocks && (
                <div className="px-5 pb-3 space-y-2">
                  {stocks.map((stock) => {
                    const config = verdictConfig[stock.verdict] || verdictConfig.hold
                    const VerdictIcon = config.icon
                    return (
                      <div
                        key={stock.symbol}
                        className="flex items-center gap-3 py-2 px-3 rounded-md bg-[rgba(180,220,190,0.04)]"
                      >
                        <VerdictIcon className={clsx('w-4 h-4 flex-shrink-0', config.color)} />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-[13px] font-mono font-medium text-text-primary">{stock.symbol}</span>
                            <span className={clsx('text-[11px] font-medium', config.color)}>{config.label}</span>
                            <span className="text-[11px] font-mono tabular-nums text-text-tertiary">Q: {stock.quality_score}/10</span>
                          </div>
                          {stock.thesis && (
                            <p className="text-[11px] text-text-tertiary mt-0.5 line-clamp-1">{stock.thesis}</p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )}

          {/* Market Context */}
          {data.market_context && (
            <div className="px-5 py-3 border-t border-[rgba(180,220,190,0.08)]">
              <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">
                Market Context
              </p>
              <p className="text-[12px] text-text-tertiary leading-relaxed">
                {data.market_context}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  )
}
