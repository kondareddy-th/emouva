import { useState, useCallback } from 'react'
import {
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  CheckCircle,
  Eye,
  Scissors,
  XCircle,
  Clock,
} from 'lucide-react'
import clsx from 'clsx'
import { apiFetch } from '../api/client'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'
import ModeToggle from '../components/ModeToggle'

// ── Types ────────────────────────────────────────────────────────

interface ScoreBreakdown {
  fundamental: number
  valuation: number
  thesis: number
  momentum: number
}

interface ScoreDetail {
  fundamental_notes: string
  valuation_notes: string
  thesis_notes: string
  momentum_notes: string
  catalysts: string[]
  risks: string[]
}

interface StockScoreItem {
  symbol: string
  company_name: string
  validity_score: number
  breakdown: ScoreBreakdown
  verdict: string
  thesis_summary: string
  concerns: string
  key_changes: string
  details: ScoreDetail | null
  week_label: string
  scored_at: string
}

interface ScoreRefreshResponse {
  scores: StockScoreItem[]
  elapsed_seconds: number
  week_label: string
}

interface LatestScoresResponse {
  scores: StockScoreItem[]
  week_label: string
}

// ── Score display helpers ────────────────────────────────────────

function getScoreColor(score: number): string {
  if (score >= 75) return '#CFAE62'
  if (score >= 55) return '#85BFC9'
  if (score >= 40) return '#DFB65A'
  return '#F2937F'
}

function getScoreLabel(score: number): string {
  if (score >= 75) return 'Strong'
  if (score >= 55) return 'Solid'
  if (score >= 40) return 'Mixed'
  return 'Weak'
}

function getVerdictConfig(verdict: string) {
  switch (verdict) {
    case 'strong_buy':
      return { label: 'Strong Buy', icon: CheckCircle, color: 'text-gain', bg: 'bg-gain/10' }
    case 'hold':
      return { label: 'Hold', icon: Minus, color: 'text-accent', bg: 'bg-accent/10' }
    case 'watch':
      return { label: 'Watch', icon: Eye, color: 'text-warning', bg: 'bg-warning/10' }
    case 'trim':
      return { label: 'Trim', icon: Scissors, color: 'text-loss', bg: 'bg-loss/10' }
    case 'sell':
      return { label: 'Sell', icon: XCircle, color: 'text-loss', bg: 'bg-loss/10' }
    default:
      return { label: verdict, icon: Minus, color: 'text-text-tertiary', bg: 'bg-surface-3' }
  }
}

// ── Score Ring (mini circular gauge) ─────────────────────────────

function ScoreRing({ score, size = 48 }: { score: number; size?: number }) {
  const r = (size - 6) / 2
  const circumference = 2 * Math.PI * r
  const progress = (score / 100) * circumference
  const color = getScoreColor(score)

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg viewBox={`0 0 ${size} ${size}`} className="w-full h-full -rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="rgba(180,220,190,0.10)" strokeWidth="3"
        />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth="3" strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          className="transition-all duration-700"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[15px] font-serif font-medium font-tabular" style={{ color }}>
          {score}
        </span>
      </div>
    </div>
  )
}

// ── Sub-score bar ────────────────────────────────────────────────

function SubScoreBar({ label, score, note }: { label: string; score: number; note?: string }) {
  const color = getScoreColor(score)
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-text-tertiary font-mono uppercase tracking-[0.11em]">{label}</span>
        <span className="text-[12px] font-mono font-medium font-tabular" style={{ color }}>{score}</span>
      </div>
      <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${score}%`, backgroundColor: color }}
        />
      </div>
      {note && <p className="text-[11px] text-text-tertiary leading-relaxed">{note}</p>}
    </div>
  )
}

// ── Stock Score Card ─────────────────────────────────────────────

function StockScoreCard({ item }: { item: StockScoreItem }) {
  const [expanded, setExpanded] = useState(false)
  const verdict = getVerdictConfig(item.verdict)
  const VerdictIcon = verdict.icon

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden card-hover transition-all duration-200">
      {/* Header row */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-4 px-5 py-4 hover:bg-[rgba(207,174,98,0.04)] transition-colors"
      >
        <ScoreRing score={item.validity_score} />

        <div className="flex-1 min-w-0 text-left">
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-mono font-medium text-text-primary">{item.symbol}</span>
            <span className="text-[12px] text-text-tertiary truncate">{item.company_name}</span>
          </div>
          <p className="text-[12px] text-text-secondary mt-0.5 line-clamp-1">{item.thesis_summary}</p>
        </div>

        {/* Verdict badge */}
        <div className={clsx('flex items-center gap-1.5 px-2.5 py-1 rounded-[6px]', verdict.bg)}>
          <VerdictIcon className={clsx('w-3.5 h-3.5', verdict.color)} />
          <span className={clsx('text-[11px] font-mono uppercase tracking-[0.08em]', verdict.color)}>{verdict.label}</span>
        </div>

        {/* Expand chevron */}
        {expanded
          ? <ChevronUp className="w-4 h-4 text-text-tertiary" />
          : <ChevronDown className="w-4 h-4 text-text-tertiary" />
        }
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-5 pb-5 border-t border-[rgba(180,220,190,0.06)] pt-4 space-y-4">
          {/* Sub-scores */}
          <div className="grid grid-cols-2 gap-x-6 gap-y-3">
            <SubScoreBar
              label="Fundamentals"
              score={item.breakdown.fundamental}
              note={item.details?.fundamental_notes}
            />
            <SubScoreBar
              label="Valuation"
              score={item.breakdown.valuation}
              note={item.details?.valuation_notes}
            />
            <SubScoreBar
              label="Thesis Integrity"
              score={item.breakdown.thesis}
              note={item.details?.thesis_notes}
            />
            <SubScoreBar
              label="Momentum"
              score={item.breakdown.momentum}
              note={item.details?.momentum_notes}
            />
          </div>

          {/* Concerns */}
          {item.concerns && (
            <div className="flex items-start gap-2 p-3 rounded-[8px] bg-loss/5 border border-loss/10">
              <AlertTriangle className="w-3.5 h-3.5 text-loss shrink-0 mt-0.5" />
              <p className="text-[12px] text-loss/90 leading-relaxed">{item.concerns}</p>
            </div>
          )}

          {/* Changes since last week */}
          {item.key_changes && item.key_changes !== 'Initial scoring' && (
            <div className="flex items-start gap-2 p-3 rounded-[8px] bg-accent/5 border border-accent/10">
              <Clock className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
              <p className="text-[12px] text-accent/90 leading-relaxed">{item.key_changes}</p>
            </div>
          )}

          {/* Catalysts & Risks */}
          {item.details && (
            <div className="grid grid-cols-2 gap-4">
              {item.details.catalysts.length > 0 && (
                <div>
                  <p className="text-[10px] text-text-tertiary font-mono mb-1.5 uppercase tracking-[0.13em]">Catalysts</p>
                  <ul className="space-y-1">
                    {item.details.catalysts.map((c, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <TrendingUp className="w-3 h-3 text-gain shrink-0 mt-0.5" />
                        <span className="text-[12px] text-text-secondary leading-relaxed">{c}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {item.details.risks.length > 0 && (
                <div>
                  <p className="text-[10px] text-text-tertiary font-mono mb-1.5 uppercase tracking-[0.13em]">Risks</p>
                  <ul className="space-y-1">
                    {item.details.risks.map((r, i) => (
                      <li key={i} className="flex items-start gap-1.5">
                        <TrendingDown className="w-3 h-3 text-loss shrink-0 mt-0.5" />
                        <span className="text-[12px] text-text-secondary leading-relaxed">{r}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Summary Stats Row ────────────────────────────────────────────

function SummaryStats({ scores }: { scores: StockScoreItem[] }) {
  if (scores.length === 0) return null

  const avg = Math.round(scores.reduce((s, sc) => s + sc.validity_score, 0) / scores.length)
  const strongBuys = scores.filter(s => s.verdict === 'strong_buy').length
  const watches = scores.filter(s => s.verdict === 'watch' || s.verdict === 'trim' || s.verdict === 'sell').length
  const best = scores.reduce((a, b) => a.validity_score > b.validity_score ? a : b)
  const worst = scores.reduce((a, b) => a.validity_score < b.validity_score ? a : b)

  return (
    <div className="grid grid-cols-4 gap-4 mb-6 stagger">
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover">
        <p className="text-[10px] text-text-tertiary font-mono uppercase tracking-[0.13em] mb-1.5">Avg Validity</p>
        <div className="flex items-center gap-2">
          <span className="text-[24px] font-serif font-medium font-tabular" style={{ color: getScoreColor(avg) }}>{avg}</span>
          <span className="text-[12px] font-medium" style={{ color: getScoreColor(avg) }}>{getScoreLabel(avg)}</span>
        </div>
        <p className="text-[11px] text-text-tertiary mt-1">{scores.length} stocks scored</p>
      </div>

      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover">
        <p className="text-[10px] text-text-tertiary font-mono uppercase tracking-[0.13em] mb-1.5">Strong Buys</p>
        <div className="text-[24px] font-serif font-medium font-tabular text-gain">{strongBuys}</div>
        <p className="text-[11px] text-text-tertiary mt-1">Score 75+</p>
      </div>

      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover">
        <p className="text-[10px] text-text-tertiary font-mono uppercase tracking-[0.13em] mb-1.5">Needs Attention</p>
        <div className={clsx('text-[24px] font-serif font-medium font-tabular', watches > 0 ? 'text-warning' : 'text-text-secondary')}>
          {watches}
        </div>
        <p className="text-[11px] text-text-tertiary mt-1">Watch / Trim / Sell</p>
      </div>

      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover">
        <p className="text-[10px] text-text-tertiary font-mono uppercase tracking-[0.13em] mb-1.5">Range</p>
        <div className="flex items-center gap-1.5">
          <span className="text-[14px] font-mono font-medium font-tabular text-gain">{best.symbol} {best.validity_score}</span>
          <span className="text-[11px] text-text-tertiary">–</span>
          <span className="text-[14px] font-mono font-medium font-tabular text-loss">{worst.symbol} {worst.validity_score}</span>
        </div>
        <p className="text-[11px] text-text-tertiary mt-1">Best – Worst</p>
      </div>
    </div>
  )
}

// ── Empty State ──────────────────────────────────────────────────

function EmptyState({ onRefresh, loading }: { onRefresh: () => void; loading: boolean }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-accent/20 to-gain/20 flex items-center justify-center mb-5 shadow-[0_0_30px_rgba(207,174,98,0.15)]">
        <TrendingUp className="w-8 h-8 text-accent" strokeWidth={1.5} />
      </div>
      <h3 className="text-[20px] font-serif font-medium text-text-primary mb-2">Portfolio Validity Scores</h3>
      <p className="text-[13px] text-text-tertiary text-center max-w-md mb-8 leading-relaxed">
        AI scores each holding 0-100 across four dimensions: fundamentals, valuation, thesis integrity, and momentum. Track weekly changes and get actionable verdicts.
      </p>

      {/* Preview of what scores look like */}
      <div className="w-full max-w-md mb-8 opacity-40 pointer-events-none select-none">
        <div className="flex items-center gap-4 px-5 py-4 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] mb-2">
          <ScoreRing score={82} size={40} />
          <div className="flex-1">
            <span className="text-[14px] font-mono font-medium text-text-tertiary">NVDA</span>
            <p className="text-[11px] text-text-tertiary/60">AI/data center growth intact...</p>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] bg-gain/10">
            <CheckCircle className="w-3.5 h-3.5 text-gain/60" />
            <span className="text-[11px] font-mono uppercase tracking-[0.08em] text-gain/60">Strong Buy</span>
          </div>
        </div>
        <div className="flex items-center gap-4 px-5 py-4 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)]">
          <ScoreRing score={54} size={40} />
          <div className="flex-1">
            <span className="text-[14px] font-mono font-medium text-text-tertiary">TSLA</span>
            <p className="text-[11px] text-text-tertiary/60">Valuation stretched, watch margins...</p>
          </div>
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-[6px] bg-warning/10">
            <Eye className="w-3.5 h-3.5 text-warning/60" />
            <span className="text-[11px] font-mono uppercase tracking-[0.08em] text-warning/60">Watch</span>
          </div>
        </div>
      </div>

      <button
        onClick={onRefresh}
        disabled={loading}
        className="flex items-center gap-2 px-6 py-2.5 rounded-[8px] bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-all press-scale disabled:opacity-50 shadow-[0_0_20px_rgba(207,174,98,0.25)]"
      >
        <RefreshCw className={clsx('w-4 h-4', loading && 'animate-spin')} />
        Score My Portfolio
      </button>
    </div>
  )
}

// ── Skeleton loader ──────────────────────────────────────────────

function ScoreSkeleton() {
  return (
    <div className="space-y-3">
      {[1, 2, 3, 4, 5].map((i) => (
        <div key={i} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] px-5 py-4 flex items-center gap-4 animate-pulse">
          <div className="w-12 h-12 rounded-full bg-surface-3" />
          <div className="flex-1 space-y-2">
            <div className="h-4 w-32 bg-surface-3 rounded" />
            <div className="h-3 w-64 bg-surface-3 rounded" />
          </div>
          <div className="h-7 w-20 bg-surface-3 rounded-md" />
        </div>
      ))}
    </div>
  )
}

// ── Main Page Component ──────────────────────────────────────────

export default function StockScores() {
  const [scores, setScores] = useState<StockScoreItem[]>([])
  const [weekLabel, setWeekLabel] = useState('')
  const [loading, setLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [initialLoaded, setInitialLoaded] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState('')

  // Load latest scores on mount
  const loadLatest = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await apiFetch<LatestScoresResponse>('/api/scores/latest')
      setScores(data.scores)
      setWeekLabel(data.week_label)
    } catch (err) {
      // No scores yet is fine
      setScores([])
    } finally {
      setLoading(false)
      setInitialLoaded(true)
    }
  }, [])

  // Load on mount
  useState(() => { loadLatest() })

  // Refresh (re-score all holdings)
  const handleRefresh = useCallback(async () => {
    setRefreshing(true)
    setError(null)
    setStatusMessage('Scoring portfolio holdings... This takes ~15-30 seconds per stock.')
    try {
      const data = await apiFetch<ScoreRefreshResponse>('/api/scores/refresh', {
        method: 'POST',
        body: JSON.stringify({ symbols: null }),
      })
      setScores(data.scores)
      setWeekLabel(data.week_label)
      setStatusMessage('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to score portfolio')
      setStatusMessage('')
    } finally {
      setRefreshing(false)
    }
  }, [])

  const sortedScores = [...scores].sort((a, b) => b.validity_score - a.validity_score)

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-base/80 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-8 h-14">
          <div className="flex items-center gap-3">
            <h1 className="text-[18px] font-serif font-medium tracking-tight text-text-primary">Stock Scores</h1>
            {weekLabel && (
              <span className="text-[10px] px-2 py-0.5 rounded-[4px] bg-surface-3 text-text-tertiary font-mono uppercase tracking-[0.1em]">
                {weekLabel}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            <SyncButton />
            <NotificationsBell />
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] bg-surface-3 text-text-secondary text-[13px] font-medium hover:bg-surface-4 transition-colors press-scale disabled:opacity-50"
            >
              <RefreshCw className={clsx('w-3 h-3', refreshing && 'animate-spin')} />
              {refreshing ? 'Scoring...' : 'Refresh Scores'}
            </button>
          </div>
        </div>
        <div className="header-gradient-line" />
      </div>

      <div className="px-8 py-8">
        {/* Status message during refresh */}
        {statusMessage && (
          <div className="flex items-center gap-2 mb-6 p-3 rounded-lg bg-accent/5 border border-accent/10">
            <RefreshCw className="w-4 h-4 text-accent animate-spin" />
            <p className="text-[13px] text-accent">{statusMessage}</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 mb-6 p-3 rounded-lg bg-loss/5 border border-loss/10">
            <AlertTriangle className="w-4 h-4 text-loss" />
            <p className="text-[13px] text-loss">{error}</p>
          </div>
        )}

        {/* Loading state */}
        {loading && !initialLoaded && <ScoreSkeleton />}

        {/* Empty state */}
        {initialLoaded && scores.length === 0 && !loading && (
          <EmptyState onRefresh={handleRefresh} loading={refreshing} />
        )}

        {/* Scores */}
        {scores.length > 0 && (
          <>
            <SummaryStats scores={sortedScores} />
            <div className="space-y-3">
              {sortedScores.map((item) => (
                <StockScoreCard key={item.symbol} item={item} />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
