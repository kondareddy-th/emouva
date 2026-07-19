import {
  Search,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  BarChart3,
  FileText,
  Sparkles,
  Bookmark,
  BookmarkCheck,
  RefreshCw,
  XCircle,
  Loader2,
  ArrowRight,
  Download,
  ChevronDown,
  ChevronUp,
  Zap,
  Copy,
  ClipboardCheck,
} from 'lucide-react'
import clsx from 'clsx'
import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { formatCurrency, type FullReport } from '../data/mockData'
import { useResearchStore } from '../hooks/useResearchStore'
import { useWatchlistStore, type WatchlistEntry } from '../hooks/useWatchlistStore'
import { useDemoStore } from '../hooks/useDemoStore'
import { showToast } from '../components/Toast'
import DemoEmailModal from '../components/DemoEmailModal'
import DemoLimitModal from '../components/DemoLimitModal'
import { SentimentBar } from '../components/shared/SentimentBar'
import { ValuationGauge } from '../components/shared/ValuationGauge'
import { FreshnessBadge } from '../components/shared/FreshnessBadge'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'
import ModeToggle from '../components/ModeToggle'

// ── Price Impact Arrow ───────────────────────────────────────────

function PriceImpactArrow({ currentPrice, stressedPrice, impactPct }: {
  currentPrice: number
  stressedPrice: number
  impactPct: number
}) {
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="font-mono text-[15px] font-medium font-tabular text-text-primary">${currentPrice.toFixed(2)}</span>
      <div className="flex-1 relative h-1.5 rounded-full bg-base overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-loss/70"
          style={{ width: `${Math.min(100, Math.abs(impactPct))}%` }}
        />
      </div>
      <ArrowRight className="w-4 h-4 text-loss flex-shrink-0" strokeWidth={1.5} />
      <span className="font-mono text-[15px] font-medium font-tabular text-loss">${stressedPrice.toFixed(2)}</span>
      <span className="font-mono text-[13px] font-medium font-tabular text-loss">({impactPct > 0 ? '+' : ''}{impactPct.toFixed(0)}%)</span>
    </div>
  )
}

// ── Report Section ───────────────────────────────────────────────

function ReportView({ report, onDownload }: { report: FullReport; onDownload: () => void }) {
  const verdictColors: Record<string, string> = {
    Buy: 'bg-gain/10 text-gain border-gain/20',
    Hold: 'bg-warning/10 text-warning border-warning/20',
    Avoid: 'bg-loss/10 text-loss border-loss/20',
  }
  const confidenceColors: Record<string, string> = {
    High: 'text-gain',
    Medium: 'text-warning',
    Low: 'text-loss',
  }

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
      {/* Report Header */}
      <div className="px-6 py-5 border-b border-[rgba(180,220,190,0.10)] flex items-start justify-between">
        <div>
          <div className="flex items-baseline gap-3 mb-1">
            <h3 className="font-serif text-[20px] font-medium text-text-primary tracking-[-0.006em]">Emouva Report</h3>
            <span className="font-mono text-[13px] text-text-secondary">{report.ticker} — {report.companyName}</span>
          </div>
          <p className="text-[11px] font-mono text-text-tertiary">
            Generated {new Date(report.generatedAt).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={clsx('px-3 py-1 rounded-full text-[12px] font-semibold border', verdictColors[report.verdict] || verdictColors.Hold)}>
            {report.verdict}
          </span>
          <span className={clsx('text-[12px] font-medium', confidenceColors[report.confidence] || 'text-text-secondary')}>
            {report.confidence} Confidence
          </span>
        </div>
      </div>

      {/* Report Body */}
      <div id="emouva-report-content" className="px-6 py-5 space-y-6">
        {/* Executive Summary */}
        <section>
          <h4 className="font-mono text-[10px] font-medium text-accent mb-2.5 uppercase tracking-[0.13em]">Executive Summary</h4>
          <p className="text-[13px] text-text-secondary leading-relaxed">{report.executiveSummary}</p>
        </section>

        {/* Valuation Analysis */}
        <section>
          <h4 className="font-mono text-[10px] font-medium text-accent mb-2.5 uppercase tracking-[0.13em]">Valuation Analysis</h4>
          <p className="text-[13px] text-text-secondary leading-relaxed whitespace-pre-line">{report.valuationAnalysis}</p>
          {report.priceTargets.base > 0 && (
            <div className="mt-3 flex gap-4">
              <div className="px-3 py-2 rounded-md bg-loss/5 border border-[rgba(242,147,127,0.3)]">
                <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] block mb-0.5">Bear</span>
                <span className="font-serif text-[18px] font-medium text-loss font-tabular">${report.priceTargets.bear}</span>
              </div>
              <div className="px-3 py-2 rounded-md bg-accent/[0.06] border border-[rgba(207,174,98,0.25)]">
                <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] block mb-0.5">Fair Value</span>
                <span className="font-serif text-[18px] font-medium text-[#E9D6A2] font-tabular">${report.priceTargets.base}</span>
              </div>
              <div className="px-3 py-2 rounded-md bg-gain/5 border border-[rgba(127,227,169,0.28)]">
                <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] block mb-0.5">Bull</span>
                <span className="font-serif text-[18px] font-medium text-gain font-tabular">${report.priceTargets.bull}</span>
              </div>
            </div>
          )}
        </section>

        {/* Investment Thesis */}
        <section>
          <h4 className="font-mono text-[10px] font-medium text-accent mb-2.5 uppercase tracking-[0.13em]">Investment Thesis</h4>
          <p className="text-[13px] text-text-secondary leading-relaxed whitespace-pre-line">{report.investmentThesis}</p>
        </section>

        {/* Key Risks */}
        {report.keyRisks.length > 0 && (
          <section>
            <h4 className="font-mono text-[10px] font-medium text-accent mb-2.5 uppercase tracking-[0.13em]">Key Risks</h4>
            <ol className="space-y-2">
              {report.keyRisks.map((risk, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <span className="font-mono text-[12px] font-medium text-loss mt-0.5 flex-shrink-0 w-5 tabular-nums">{i + 1}.</span>
                  <span className="text-[13px] text-text-secondary leading-relaxed">{risk}</span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* Catalysts */}
        {report.catalysts.length > 0 && (
          <section>
            <h4 className="font-mono text-[10px] font-medium text-accent mb-2.5 uppercase tracking-[0.13em]">Catalysts</h4>
            <ol className="space-y-2">
              {report.catalysts.map((cat, i) => (
                <li key={i} className="flex items-start gap-2.5">
                  <Zap className="w-3.5 h-3.5 text-warning mt-0.5 flex-shrink-0" strokeWidth={1.5} />
                  <span className="text-[13px] text-text-secondary leading-relaxed">{cat}</span>
                </li>
              ))}
            </ol>
          </section>
        )}

        {/* Financial Highlights */}
        <section>
          <h4 className="font-mono text-[10px] font-medium text-accent mb-2.5 uppercase tracking-[0.13em]">Financial Highlights</h4>
          <p className="text-[13px] text-text-secondary leading-relaxed whitespace-pre-line">{report.financialHighlights}</p>
        </section>

        {/* Verdict */}
        <section className="rounded-md bg-accent/[0.04] border border-[rgba(207,174,98,0.25)] p-4">
          <h4 className="font-mono text-[10px] font-medium text-accent mb-2.5 uppercase tracking-[0.13em]">Verdict</h4>
          <div className="flex items-center gap-3 mb-2">
            <span className={clsx('px-4 py-1.5 rounded-lg text-[14px] font-bold border', verdictColors[report.verdict] || verdictColors.Hold)}>
              {report.verdict}
            </span>
            <span className={clsx('text-[13px] font-medium', confidenceColors[report.confidence])}>
              {report.confidence} Confidence
            </span>
          </div>
          <p className="text-[13px] text-text-secondary leading-relaxed">{report.verdictReasoning}</p>
        </section>
      </div>

      {/* Report Footer */}
      <div className="px-6 py-4 border-t border-[rgba(180,220,190,0.10)] flex items-center justify-between bg-base/40">
        <div className="flex items-center gap-2">
          <span className="w-1.5 h-1.5 bg-accent rotate-45 flex-shrink-0" />
          <span className="text-[11px] font-mono text-text-tertiary uppercase tracking-[0.13em]">Powered by Emouva AI</span>
        </div>
        <button
          onClick={onDownload}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-accent text-base text-[13px] font-medium hover:bg-accent-hover transition-colors"
        >
          <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
          Download PDF
        </button>
      </div>
    </div>
  )
}

// ── Main Component ───────────────────────────────────────────────

export default function AIResearch() {
  const {
    query, analysis, loading, error, fromCache, isSample,
    sentimentLoading,
    bearStress, bearStressLoading, bearStressError,
    customBearStress, customBearLoading,
    report, reportLoading, reportError,
    analysisFreshness, bearCaseFreshness, sentimentFreshness, refreshingInBackground,
    setQuery, runAnalysis, forceRefresh, clearError,
    runBearStress, generateReport, dismissSample,
  } = useResearchStore()

  const { isInWatchlist, addToWatchlist, removeFromWatchlist } = useWatchlistStore()
  const demo = useDemoStore()

  const [searchParams, setSearchParams] = useSearchParams()
  const [activeTab, setActiveTab] = useState<'thesis' | 'bear' | 'financials'>('thesis')
  const [customScenario, setCustomScenario] = useState('')
  const [showReport, setShowReport] = useState(false)
  const reportRef = useRef<HTMLDivElement>(null)

  // Auto-analyze from URL param (e.g., /research?ticker=AAPL from Portfolio click-through)
  useEffect(() => {
    const tickerParam = searchParams.get('ticker')
    if (tickerParam && tickerParam.toUpperCase() !== query.toUpperCase()) {
      setQuery(tickerParam.toUpperCase())
      runAnalysis(tickerParam)
      setSearchParams({}, { replace: true }) // clean URL
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const inWatchlist = analysis ? isInWatchlist(analysis.symbol) : false

  const handleWatchlist = () => {
    if (!analysis) return
    if (inWatchlist) {
      removeFromWatchlist(analysis.symbol)
    } else {
      const entry: WatchlistEntry = {
        symbol: analysis.symbol,
        name: analysis.name,
        fairValue: analysis.fairValue,
        lastPrice: analysis.currentPrice,
        thesis: analysis.thesis.slice(0, 200),
        addedAt: new Date().toISOString(),
        lastAnalyzedAt: new Date().toISOString(),
      }
      addToWatchlist(entry)
    }
  }

  const handleGenerateReport = () => {
    if (!analysis) return
    generateReport(analysis.symbol)
    setShowReport(true)
  }

  const handleDownloadPdf = async () => {
    const el = document.getElementById('emouva-report-content')
    if (!el || !report) return

    try {
      const html2pdf = (await import('html2pdf.js')).default
      html2pdf().set({
        margin: [15, 15],
        filename: `Emouva_Report_${report.ticker}_${new Date().toISOString().slice(0, 10)}.pdf`,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: '#0D0D12' },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      }).from(el).save()
      showToast('PDF downloaded', 'success')
    } catch {
      showToast('PDF download failed', 'error')
    }
  }

  const handleCustomStress = () => {
    if (!analysis || !customScenario.trim()) return
    runBearStress(analysis.symbol, customScenario)
  }

  // ── Copy / PDF helpers ──
  const [copiedSection, setCopiedSection] = useState<string | null>(null)

  const copyToClipboard = async (text: string, section: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedSection(section)
      showToast('Copied to clipboard', 'success')
      setTimeout(() => setCopiedSection(null), 2000)
    } catch {
      showToast('Copy failed', 'error')
    }
  }

  const downloadSectionPdf = async (elementId: string, filename: string) => {
    const el = document.getElementById(elementId)
    if (!el) return
    try {
      const html2pdf = (await import('html2pdf.js')).default
      html2pdf().set({
        margin: [15, 15],
        filename,
        image: { type: 'jpeg', quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: '#0D0D12' },
        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
      }).from(el).save()
      showToast('PDF downloaded', 'success')
    } catch {
      showToast('PDF download failed', 'error')
    }
  }

  const getAnalysisText = () => {
    if (!analysis) return ''
    const lines = [
      `${analysis.symbol} — ${analysis.name}`,
      `Current Price: $${analysis.currentPrice.toFixed(2)}`,
      `Fair Value: $${analysis.fairValue.base} (Bear: $${analysis.fairValue.bear}, Bull: $${analysis.fairValue.bull})`,
      '',
      '── Investment Thesis ──',
      analysis.thesis,
      '',
      '── Bull Case ──',
      analysis.bullCase,
      '',
      '── Bear Case ──',
      analysis.bearCase,
      '',
      '── Key Risks ──',
      ...analysis.keyRisks.map((r, i) => `${i + 1}. ${r}`),
    ]
    if (analysis.metricsToWatch.length > 0) {
      lines.push('', '── Metrics to Watch ──')
      analysis.metricsToWatch.forEach((m) => lines.push(`• ${m.metric}: ${m.current} (${m.threshold})`))
    }
    return lines.join('\n')
  }

  const getBearStressText = (bs: typeof bearStress) => {
    if (!bs) return ''
    const sections: string[] = [
      `Bear Case Stress Test: ${bs.scenarioName || 'Default Scenario'}`,
    ]
    if (bs.estimatedImpactPct != null && bs.stressedPrice != null) {
      sections.push(`Estimated Impact: ${bs.estimatedImpactPct.toFixed(0)}% → $${bs.stressedPrice.toFixed(2)}`)
    }
    if (bs.competitiveThreats) sections.push('', '── Competitive Threats ──', bs.competitiveThreats)
    if (bs.valuationConcerns) sections.push('', '── Valuation Concerns ──', bs.valuationConcerns)
    if (bs.financialRisks) sections.push('', '── Financial Risks ──', bs.financialRisks)
    if (bs.secularHeadwinds) sections.push('', '── Secular Headwinds ──', bs.secularHeadwinds)
    if (bs.managementRisks) sections.push('', '── Management Risks ──', bs.managementRisks)
    if (bs.consensusBlindspots) sections.push('', '── Consensus Blindspots ──', bs.consensusBlindspots)
    return sections.join('\n')
  }

  // ── Demo gating ──
  const handleAnalyze = (ticker: string) => {
    if (!ticker.trim()) return
    if (demo.isDemoMode) {
      const gate = demo.checkAndGate(ticker)
      if (gate === 'needs_email' || gate === 'limit_reached') return
    }
    runAnalysis(ticker)
  }

  // Record analysis completion for demo usage tracking
  const prevLoadingRef = useRef(false)
  useEffect(() => {
    if (prevLoadingRef.current && !loading && analysis && !isSample) {
      demo.recordAnalysis()
    }
    prevLoadingRef.current = loading
  }, [loading, analysis, isSample])

  // Auto-run pending analysis after email submission
  useEffect(() => {
    if (demo.token && demo.pendingTicker && !loading) {
      const ticker = demo.pendingTicker
      demo.dismissEmailModal()
      runAnalysis(ticker)
    }
  }, [demo.token, demo.pendingTicker])

  const placeholders = [
    'What if AI regulation passes?',
    'What if their CEO resigns?',
    'What if interest rates hit 7%?',
    'What if China invades Taiwan?',
  ]
  const [placeholderIdx] = useState(() => Math.floor(Math.random() * placeholders.length))

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-base/90 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-4 md:px-8 h-14">
          <h1 className="font-serif text-[18px] font-medium text-text-primary tracking-[-0.006em]">AI Research</h1>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            <SyncButton />
            <NotificationsBell />
          </div>
        </div>
        <div className="h-px bg-[rgba(180,220,190,0.12)]" />
      </div>

      <div className="px-4 md:px-8 py-8">
        {/* Search Bar */}
        <div className="relative mb-8">
          <div className="relative max-w-[720px]">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-text-tertiary" strokeWidth={1.5} />
            <input
              type="text"
              placeholder="Enter a ticker to analyze (e.g., NVDA, AAPL, TSLA)..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleAnalyze(query)}
              className="w-full h-12 pl-11 pr-28 rounded-lg bg-base border border-[rgba(180,220,190,0.12)] text-text-primary placeholder-text-tertiary text-[14px] font-mono focus:outline-none focus:border-[rgba(207,174,98,0.4)] focus:ring-1 focus:ring-[rgba(207,174,98,0.15)] transition-all"
            />
            <button
              onClick={() => handleAnalyze(query)}
              disabled={loading || !query.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-1.5 rounded-md bg-accent text-base text-[13px] font-medium hover:bg-accent-hover transition-colors disabled:opacity-40"
            >
              {loading ? 'Analyzing...' : 'Analyze'}
            </button>
          </div>
          <div className="flex items-center gap-2 mt-2.5 px-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Trending</span>
            {['NVDA', 'TSLA', 'PLTR', 'SMCI', 'ARM'].map((t) => (
              <button
                key={t}
                onClick={() => { setQuery(t); handleAnalyze(t) }}
                className="px-2 py-0.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] font-mono text-[11px] text-text-secondary hover:border-[rgba(180,220,190,0.25)] hover:text-text-primary transition-colors"
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Loading State */}
        {loading && !analysis && (
          <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
            <div className="relative mb-6">
              <div className="w-16 h-16 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] flex items-center justify-center">
                <Loader2 className="w-7 h-7 text-accent animate-spin" strokeWidth={1.5} />
              </div>
            </div>
            <h3 className="font-serif text-[18px] font-medium text-text-primary mb-2">
              Analyzing <span className="font-mono text-[16px]">{query.toUpperCase()}</span>
            </h3>
            <p className="text-[13px] text-text-tertiary max-w-sm text-center">
              Running AI-powered analysis including valuation, thesis generation, and risk assessment. This may take 15-30 seconds.
            </p>
          </div>
        )}

        {/* Error State */}
        {error && !loading && (
          <div className="max-w-lg mx-auto mt-4 mb-6 animate-fade-in">
            <div className="rounded-[10px] bg-loss/5 border border-[rgba(242,147,127,0.3)] p-5">
              <div className="flex items-start gap-3">
                <XCircle className="w-5 h-5 text-loss flex-shrink-0 mt-0.5" strokeWidth={1.5} />
                <div className="flex-1">
                  <h3 className="font-serif text-[16px] font-medium text-loss mb-1">Analysis Failed</h3>
                  <p className="text-[13px] text-text-secondary leading-relaxed">{error}</p>
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => runAnalysis(query)}
                      className="px-3 py-1.5 rounded-md bg-loss/10 border border-[rgba(242,147,127,0.3)] text-loss text-[12px] font-medium hover:bg-loss/20 transition-colors"
                    >
                      Try Again
                    </button>
                    <button
                      onClick={clearError}
                      className="px-3 py-1.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-tertiary text-[12px] font-medium hover:text-text-secondary transition-colors"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Empty State — Sample preview */}
        {!analysis && !loading && !error && (
          <div className="animate-fade-in">
            <div className="text-center mb-8">
              <div className="w-14 h-14 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-6 h-6 text-accent" strokeWidth={1.5} />
              </div>
              <h3 className="font-serif text-[22px] font-medium text-text-primary mb-2 tracking-[-0.006em]">AI-Powered Stock Analysis</h3>
              <p className="text-[13px] text-text-tertiary max-w-md mx-auto leading-relaxed">
                Enter any ticker above to get a comprehensive analysis including valuation, investment thesis, risk assessment, and sentiment scoring.
              </p>
            </div>

            {/* Sample analysis preview */}
            <div className="max-w-[720px] opacity-50 pointer-events-none select-none">
              <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6 mb-4">
                <div className="flex items-start justify-between mb-5">
                  <div>
                    <div className="flex items-baseline gap-3 mb-1">
                      <span className="font-mono text-[20px] text-text-tertiary">NVDA</span>
                      <span className="text-[14px] text-text-tertiary/60">NVIDIA Corporation</span>
                    </div>
                    <span className="font-serif text-[32px] font-medium font-tabular text-text-tertiary/60">$142.50</span>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex items-end justify-between text-text-tertiary/50">
                    <div className="text-center"><div className="font-mono text-[10px] uppercase tracking-[0.13em]">Bear</div><div className="font-serif text-[16px] font-medium font-tabular">$95</div></div>
                    <div className="text-center"><div className="font-mono text-[10px] uppercase tracking-[0.13em]">Fair Value</div><div className="font-serif text-[16px] font-medium font-tabular text-[#E9D6A2]/60">$155</div></div>
                    <div className="text-center"><div className="font-mono text-[10px] uppercase tracking-[0.13em]">Bull</div><div className="font-serif text-[16px] font-medium font-tabular">$210</div></div>
                  </div>
                  <div className="h-2 rounded-full bg-base overflow-hidden">
                    <div className="h-full rounded-full bg-gradient-to-r from-loss/30 via-warning/30 to-gain/30" style={{ width: '55%' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ═══ Analysis Results ═══ */}
        {analysis && (
          <div className="space-y-4 animate-fade-in">
            {/* Sample data banner */}
            {isSample && (
              <div className="rounded-[10px] bg-accent/[0.06] border border-[rgba(207,174,98,0.25)] px-5 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-accent" strokeWidth={1.5} />
                  <span className="text-[13px] text-accent font-medium">
                    Sample analysis — search any ticker above to run your own
                  </span>
                </div>
                <button
                  onClick={dismissSample}
                  className="text-[12px] text-accent/60 hover:text-accent transition-colors font-medium"
                >
                  Dismiss
                </button>
              </div>
            )}

            {/* Demo: soft banner when 1 analysis left */}
            {demo.isDemoMode && demo.remaining === 1 && !demo.showLimitModal && (
              <div className="rounded-[10px] bg-warning/5 border border-[rgba(223,182,90,0.25)] px-5 py-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-warning" strokeWidth={1.5} />
                  <span className="text-[13px] text-warning font-medium">
                    1 free analysis left today.
                  </span>
                  <span className="text-[13px] text-text-tertiary">
                    Create an account for unlimited access.
                  </span>
                </div>
                <Link
                  to="/signup"
                  className="text-[12px] text-accent hover:text-accent-hover transition-colors font-medium whitespace-nowrap"
                >
                  Sign Up Free
                </Link>
              </div>
            )}

            {/* Inline loading overlay when refreshing */}
            {loading && (
              <div className="rounded-[10px] bg-accent/[0.06] border border-[rgba(207,174,98,0.25)] px-4 py-3 flex items-center gap-3">
                <Loader2 className="w-4 h-4 text-accent animate-spin" strokeWidth={1.5} />
                <span className="text-[13px] text-accent font-medium">Refreshing analysis for <span className="font-mono">{query.toUpperCase()}</span></span>
              </div>
            )}

            {/* Header Card */}
            <div id="emouva-analysis-content" className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6">
              <div className="flex items-start justify-between mb-6">
                <div>
                  <div className="flex items-baseline gap-3 mb-1">
                    <h2 className="font-mono text-[22px] font-medium text-text-primary tracking-[0.02em]">{analysis.symbol}</h2>
                    <span className="text-[14px] text-text-secondary">{analysis.name}</span>
                    <FreshnessBadge freshness={analysisFreshness} refreshing={refreshingInBackground} />
                  </div>
                  <div className="flex items-baseline gap-4 mt-2">
                    <span className="font-serif text-[34px] font-medium font-tabular text-text-primary tracking-[-0.01em]">${analysis.currentPrice.toFixed(2)}</span>
                    {analysis.fairValue.base > 0 && (
                      <span className="font-mono text-[12px] text-text-tertiary uppercase tracking-[0.08em]">
                        Fair Value <span className="text-[#E9D6A2] font-medium normal-case tracking-normal text-[13px]">${analysis.fairValue.base}</span>
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  <button
                    onClick={handleWatchlist}
                    className={clsx(
                      'px-3 py-2 rounded-md text-[13px] font-medium transition-colors flex items-center gap-1.5 border',
                      inWatchlist
                        ? 'bg-gain/10 text-gain border-[rgba(127,227,169,0.28)] hover:bg-gain/20'
                        : 'bg-surface-3 text-text-secondary border-[rgba(180,220,190,0.12)] hover:border-[rgba(180,220,190,0.25)] hover:text-text-primary'
                    )}
                  >
                    {inWatchlist ? <BookmarkCheck className="w-3.5 h-3.5" strokeWidth={1.5} /> : <Bookmark className="w-3.5 h-3.5" strokeWidth={1.5} />}
                    {inWatchlist ? 'In Watchlist' : 'Add to Watchlist'}
                  </button>
                  <button
                    onClick={() => copyToClipboard(getAnalysisText(), 'analysis')}
                    className="px-3 py-2 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-secondary text-[13px] font-medium hover:border-[rgba(180,220,190,0.25)] hover:text-text-primary transition-colors flex items-center gap-1.5"
                  >
                    {copiedSection === 'analysis' ? <ClipboardCheck className="w-3.5 h-3.5 text-gain" strokeWidth={1.5} /> : <Copy className="w-3.5 h-3.5" strokeWidth={1.5} />}
                    {copiedSection === 'analysis' ? 'Copied' : 'Copy'}
                  </button>
                  <button
                    onClick={() => downloadSectionPdf('emouva-analysis-content', `Emouva_Analysis_${analysis.symbol}_${new Date().toISOString().slice(0, 10)}.pdf`)}
                    className="px-3 py-2 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-secondary text-[13px] font-medium hover:border-[rgba(180,220,190,0.25)] hover:text-text-primary transition-colors flex items-center gap-1.5"
                  >
                    <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
                    PDF
                  </button>
                  <button
                    onClick={handleGenerateReport}
                    disabled={reportLoading}
                    className="px-3 py-2 rounded-md bg-accent text-base text-[13px] font-medium hover:bg-accent-hover transition-colors flex items-center gap-1.5 disabled:opacity-40"
                  >
                    {reportLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" strokeWidth={1.5} />}
                    {reportLoading ? 'Generating...' : 'Full Report'}
                  </button>
                  <button
                    onClick={() => forceRefresh(analysis.symbol)}
                    disabled={loading}
                    className="px-3 py-2 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-secondary text-[13px] font-medium hover:border-[rgba(180,220,190,0.25)] hover:text-text-primary transition-colors flex items-center gap-1.5 disabled:opacity-50"
                  >
                    <RefreshCw className={clsx('w-3.5 h-3.5', loading && 'animate-spin')} strokeWidth={1.5} />
                    Refresh
                  </button>
                </div>
              </div>
              <ValuationGauge
                bear={analysis.fairValue.bear}
                base={analysis.fairValue.base}
                bull={analysis.fairValue.bull}
                current={analysis.currentPrice}
              />
              {/* DCF methodology — how fair value is calculated */}
              {(analysis.dcfFairValue || analysis.dcfAssumptions) && (
                <details className="mt-4 group">
                  <summary className="cursor-pointer text-[12px] text-text-tertiary hover:text-text-secondary transition-colors flex items-center gap-1.5 list-none">
                    <ChevronDown className="w-3.5 h-3.5 transition-transform group-open:rotate-180" strokeWidth={1.5} />
                    How is this calculated?
                  </summary>
                  <div className="mt-3 px-3 py-3 rounded-md bg-base border border-[rgba(180,220,190,0.10)] space-y-2">
                    <p className="text-[12px] text-text-secondary leading-relaxed">
                      <strong className="text-text-primary font-medium">DCF Fair Value: <span className="font-mono text-[#E9D6A2]">${analysis.dcfFairValue?.toFixed(0) ?? '—'}</span></strong>
                      {' '}— computed from trailing free cash flow, projected 5 years forward, discounted back to today, plus a terminal-value perpetuity.
                    </p>
                    {analysis.dcfAssumptions && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mt-2">
                        <div className="text-[11px]">
                          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.1em]">WACC (discount rate)</span>
                          <div className="text-text-primary font-mono font-tabular font-medium">{analysis.dcfAssumptions.wacc}%</div>
                        </div>
                        <div className="text-[11px]">
                          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.1em]">Growth Y1–3</span>
                          <div className="text-text-primary font-mono font-tabular font-medium">{analysis.dcfAssumptions.phase1_growth}%</div>
                        </div>
                        <div className="text-[11px]">
                          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.1em]">Growth Y4–5</span>
                          <div className="text-text-primary font-mono font-tabular font-medium">{analysis.dcfAssumptions.phase2_growth}%</div>
                        </div>
                        <div className="text-[11px]">
                          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.1em]">Terminal growth</span>
                          <div className="text-text-primary font-mono font-tabular font-medium">{analysis.dcfAssumptions.terminal_growth}%</div>
                        </div>
                      </div>
                    )}
                    <p className="text-[11px] text-text-tertiary leading-relaxed mt-2 pt-2 border-t border-[rgba(180,220,190,0.06)]">
                      <strong>Bear/Base/Bull</strong> on the gauge above are Claude's long-term fair-value scenarios using the same fundamentals plus a qualitative assessment of moat, growth runway, and margins. The <strong>Bear</strong> here is the structural bear (years-out fair value) — distinct from the Bear Case Stress Test further below, which models near-term impact of a specific event.
                    </p>
                  </div>
                </details>
              )}
            </div>

            {/* Verdict Card */}
            {analysis.verdict && (
              <div className="rounded-[10px] bg-surface-2 border border-[rgba(207,174,98,0.25)] p-5">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {/* Verdict */}
                  <div>
                    <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Verdict</p>
                    <span className={clsx(
                      'font-serif text-[24px] font-medium',
                      analysis.verdict === 'BUY' ? 'text-gain' : analysis.verdict === 'SELL' ? 'text-loss' : 'text-warning'
                    )}>
                      {analysis.verdict}
                    </span>
                    {analysis.confidence && (
                      <p className={clsx(
                        'text-[11px] font-medium mt-0.5',
                        analysis.confidence === 'HIGH' ? 'text-gain/70' : analysis.confidence === 'LOW' ? 'text-loss/70' : 'text-warning/70'
                      )}>
                        {analysis.confidence} confidence
                      </p>
                    )}
                  </div>
                  {/* Entry Price */}
                  {analysis.entryPrice && (
                    <div>
                      <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Buy Below</p>
                      <p className="font-serif text-[24px] font-medium text-[#E9D6A2] font-tabular">${analysis.entryPrice.toFixed(0)}</p>
                      {analysis.dcfFairValue ? (
                        <p className="text-[11px] font-mono text-text-tertiary mt-0.5">
                          DCF fair value ${analysis.dcfFairValue.toFixed(0)} − 20%
                        </p>
                      ) : (
                        <p className="text-[11px] text-text-tertiary mt-0.5">20% margin of safety</p>
                      )}
                      {analysis.dcfAssumptions && (
                        <p className="text-[10px] font-mono text-text-tertiary/60 mt-0.5">
                          WACC {analysis.dcfAssumptions.wacc}% · Growth {analysis.dcfAssumptions.phase1_growth}%→{analysis.dcfAssumptions.phase2_growth}%
                        </p>
                      )}
                    </div>
                  )}
                  {/* Risk/Reward */}
                  {analysis.riskReward && (
                    <div>
                      <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Risk / Reward</p>
                      <p className="font-serif text-[24px] font-medium text-accent font-tabular">{analysis.riskReward}</p>
                      <p className="text-[11px] text-text-tertiary mt-0.5">upside vs downside</p>
                    </div>
                  )}
                  {/* Thesis Breaks */}
                  {analysis.thesisBreaks.length > 0 && (
                    <div>
                      <p className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Thesis Breaks If</p>
                      {analysis.thesisBreaks.slice(0, 2).map((tb, i) => (
                        <p key={i} className="text-[11px] text-loss/80 leading-relaxed">
                          {tb.length > 60 ? tb.slice(0, 57) + '...' : tb}
                        </p>
                      ))}
                      {analysis.thesisBreaks.length > 2 && (
                        <p className="text-[10px] text-text-tertiary mt-0.5">+{analysis.thesisBreaks.length - 2} more</p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Two Column Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Left Column */}
              <div className="lg:col-span-2 space-y-4">
                {/* Tab Selector */}
                <div className="flex gap-1 p-1 rounded-lg bg-surface-2 border border-[rgba(180,220,190,0.12)]">
                  {([
                    { key: 'thesis', label: 'Investment Thesis', icon: FileText },
                    { key: 'bear', label: 'Bear Case', icon: AlertTriangle },
                    { key: 'financials', label: 'Financials', icon: BarChart3 },
                  ] as const).map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => setActiveTab(tab.key)}
                      className={clsx(
                        'flex-1 flex items-center justify-center gap-1.5 py-2 rounded-md text-[13px] font-medium transition-all',
                        activeTab === tab.key
                          ? 'bg-accent/[0.12] text-accent'
                          : 'text-text-tertiary hover:text-text-secondary'
                      )}
                    >
                      <tab.icon className="w-3.5 h-3.5" strokeWidth={1.5} />
                      {tab.label}
                    </button>
                  ))}
                </div>

                {/* Tab Content */}
                <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
                  {activeTab === 'thesis' && (
                    <div className="space-y-4">
                      <p className="text-[13px] text-text-secondary leading-relaxed">{analysis.thesis}</p>
                      <div>
                        <h4 className="text-[13px] font-medium text-gain mb-2 flex items-center gap-1.5">
                          <TrendingUp className="w-3.5 h-3.5" strokeWidth={1.5} />
                          Bull Case
                        </h4>
                        <p className="text-[12px] text-text-tertiary leading-relaxed">{analysis.bullCase}</p>
                      </div>
                      {analysis.metricsToWatch.length > 0 && (
                        <div>
                          <h4 className="font-mono text-[10px] font-medium text-text-tertiary uppercase tracking-[0.13em] mb-3 mt-4">Metrics to Watch</h4>
                          <div className="space-y-2">
                            {analysis.metricsToWatch.map((m, i) => (
                              <div key={i} className="flex items-center justify-between py-2.5 px-3 rounded-md hover:bg-accent/[0.03] transition-colors">
                                <span className="text-[13px] text-text-secondary">{m.metric}</span>
                                <div className="flex items-center gap-3">
                                  <span className="text-[13px] text-text-primary font-mono font-medium font-tabular">{m.current}</span>
                                  <span className="font-mono text-[11px] text-text-tertiary">{m.threshold}</span>
                                  <CheckCircle2 className={clsx('w-3.5 h-3.5', m.status === 'pass' ? 'text-gain' : m.status === 'watch' ? 'text-warning' : 'text-loss')} strokeWidth={1.5} />
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'bear' && (
                    <div className="space-y-4">
                      <div className="p-4 rounded-md bg-loss/5 border border-[rgba(242,147,127,0.3)]">
                        <h4 className="text-[13px] font-medium text-loss mb-1 flex items-center gap-1.5">
                          <TrendingDown className="w-3.5 h-3.5" strokeWidth={1.5} />
                          Structural Bear Case — Fair Value: <span className="font-mono font-tabular">${analysis.fairValue.bear}</span>
                        </h4>
                        <p className="text-[11px] text-text-tertiary mb-2 leading-relaxed">Long-term fair value if the bear thesis plays out over 3–5 years. For near-term event-driven impact, use the Bear Case Stress Test below.</p>
                        <p className="text-[13px] text-text-secondary leading-relaxed">{analysis.bearCase}</p>
                      </div>
                      {analysis.keyRisks.length > 0 && (
                        <div>
                          <h4 className="font-mono text-[10px] font-medium text-text-tertiary uppercase tracking-[0.13em] mb-3">Key Risks</h4>
                          <div className="space-y-2">
                            {analysis.keyRisks.map((risk, i) => (
                              <div key={i} className="flex items-start gap-2.5 py-2.5 px-3 rounded-md hover:bg-accent/[0.03] transition-colors">
                                <AlertTriangle className="w-3.5 h-3.5 text-warning mt-0.5 flex-shrink-0" strokeWidth={1.5} />
                                <span className="text-[12px] text-text-secondary leading-relaxed">{risk}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {activeTab === 'financials' && (
                    <div className="space-y-1">
                      {analysis.financials.length === 0 ? (
                        <p className="text-[13px] text-text-tertiary py-4 text-center">No financial data available. Try re-analyzing the stock.</p>
                      ) : (
                        analysis.financials.map((f, i) => (
                          <div key={i} className="flex items-center justify-between py-3 px-3 rounded-md hover:bg-accent/[0.03] transition-colors">
                            <span className="text-[13px] text-text-secondary">{f.metric}</span>
                            <div className="flex items-center gap-2">
                              {(f as { badge?: string }).badge && (
                                <span className={clsx(
                                  'font-mono text-[9.5px] font-medium px-1.5 py-0.5 rounded uppercase tracking-[0.08em]',
                                  (f as { badge?: string }).badge === 'Excellent' || (f as { badge?: string }).badge === 'Strong' || (f as { badge?: string }).badge === 'Attractive'
                                    ? 'bg-gain/10 text-gain'
                                    : (f as { badge?: string }).badge === 'Weak' || (f as { badge?: string }).badge === 'Low'
                                      ? 'bg-loss/10 text-loss'
                                      : 'bg-warning/10 text-warning'
                                )}>
                                  {(f as { badge?: string }).badge}
                                </span>
                              )}
                              <span className="text-[13px] text-text-primary font-mono font-medium font-tabular">{f.value}</span>
                              {f.trend === 'up' ? (
                                <TrendingUp className="w-3 h-3 text-gain" strokeWidth={1.5} />
                              ) : f.trend === 'down' ? (
                                <TrendingDown className="w-3 h-3 text-loss" strokeWidth={1.5} />
                              ) : (
                                <span className="w-1.5 h-1.5 bg-text-tertiary rotate-45 flex-shrink-0" />
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Right Column: Sentiment */}
              <div className="space-y-4">
                <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4">
                  <h3 className="font-serif text-[16px] font-medium text-text-primary mb-4 tracking-[-0.006em]">Sentiment Analysis</h3>
                  {sentimentLoading ? (
                    <div className="space-y-3">
                      {['News', 'Filings', 'Insider', 'Analyst'].map((l) => (
                        <div key={l} className="flex items-center gap-3">
                          <span className="text-caption text-text-tertiary w-14">{l}</span>
                          <div className="flex-1 h-1 bg-surface-3 rounded-full overflow-hidden">
                            <div className="h-full w-1/3 bg-surface-3 rounded-full animate-pulse" />
                          </div>
                          <span className="text-caption text-text-tertiary w-8 text-right">--</span>
                        </div>
                      ))}
                      <div className="mt-4 pt-3 border-t border-[rgba(180,220,190,0.10)]">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">Composite</span>
                          <span className="text-caption text-text-tertiary animate-pulse">Loading...</span>
                        </div>
                      </div>
                    </div>
                  ) : analysis.sentiment.composite === 0 ? (
                    <p className="text-caption text-text-tertiary">Sentiment data not available.</p>
                  ) : (
                    <>
                      <div className="space-y-3">
                        <SentimentBar label="News" value={analysis.sentiment.news} />
                        <SentimentBar label="Filings" value={analysis.sentiment.filings} />
                        <SentimentBar label="Insider" value={analysis.sentiment.insider} />
                        <SentimentBar label="Analyst" value={analysis.sentiment.analyst} />
                      </div>
                      <div className="mt-4 pt-3 border-t border-[rgba(180,220,190,0.10)]">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">Composite</span>
                          <div className="flex items-baseline gap-1.5">
                            <span className={clsx('font-serif text-[22px] font-medium font-tabular', analysis.sentiment.composite >= 65 ? 'text-gain' : analysis.sentiment.composite >= 45 ? 'text-warning' : 'text-loss')}>
                              {analysis.sentiment.composite}
                            </span>
                            <span className="font-mono text-[11px] text-text-tertiary">/100</span>
                          </div>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* ═══ Bear Case Stress Test Section ═══ */}
            <div id="emouva-stress-test-content" className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-loss" strokeWidth={1.5} />
                  <div>
                    <h3 className="font-serif text-[16px] font-medium text-text-primary tracking-[-0.006em]">Bear Case Stress Test</h3>
                    <p className="text-[11px] text-text-tertiary leading-relaxed">Near-term event impact — models what happens if a specific scenario materializes. Different from the structural bear value on the gauge.</p>
                  </div>
                </div>
                {(bearStress || customBearStress) && (
                  <div className="flex gap-1.5">
                    <button
                      onClick={() => copyToClipboard(
                        [getBearStressText(bearStress), customBearStress ? getBearStressText(customBearStress) : ''].filter(Boolean).join('\n\n'),
                        'stress'
                      )}
                      className="p-1.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-tertiary hover:text-text-primary hover:border-[rgba(180,220,190,0.25)] transition-colors"
                      title="Copy stress test"
                    >
                      {copiedSection === 'stress' ? <ClipboardCheck className="w-3.5 h-3.5 text-gain" strokeWidth={1.5} /> : <Copy className="w-3.5 h-3.5" strokeWidth={1.5} />}
                    </button>
                    <button
                      onClick={() => downloadSectionPdf('emouva-stress-test-content', `Emouva_StressTest_${analysis.symbol}_${new Date().toISOString().slice(0, 10)}.pdf`)}
                      className="p-1.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-tertiary hover:text-text-primary hover:border-[rgba(180,220,190,0.25)] transition-colors"
                      title="Download as PDF"
                    >
                      <Download className="w-3.5 h-3.5" strokeWidth={1.5} />
                    </button>
                  </div>
                )}
              </div>

              {/* Default scenario */}
              {bearStressLoading && (
                <div className="flex items-center gap-3 py-4">
                  <Loader2 className="w-4 h-4 text-text-tertiary animate-spin" />
                  <span className="text-[13px] text-text-tertiary">Running default bear case analysis...</span>
                </div>
              )}

              {bearStressError && (
                <p className="text-[12px] text-loss mb-4">{bearStressError}</p>
              )}

              {bearStress && (
                <div className="mb-5">
                  <div className="rounded-md bg-loss/5 border border-[rgba(242,147,127,0.3)] p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-[10px] font-medium text-loss uppercase tracking-[0.13em]">{bearStress.scenarioName || 'Default Scenario'}</span>
                    </div>
                    <div className="space-y-2 mb-3">
                      {bearStress.competitiveThreats && (
                        <p className="text-[12px] text-text-secondary leading-relaxed">{bearStress.competitiveThreats}</p>
                      )}
                      {bearStress.valuationConcerns && (
                        <p className="text-[12px] text-text-secondary leading-relaxed">{bearStress.valuationConcerns}</p>
                      )}
                      {bearStress.financialRisks && (
                        <p className="text-[12px] text-text-secondary leading-relaxed">{bearStress.financialRisks}</p>
                      )}
                      {bearStress.secularHeadwinds && (
                        <p className="text-[12px] text-text-secondary leading-relaxed">{bearStress.secularHeadwinds}</p>
                      )}
                      {bearStress.managementRisks && (
                        <p className="text-[12px] text-text-secondary leading-relaxed">{bearStress.managementRisks}</p>
                      )}
                      {bearStress.consensusBlindspots && (
                        <p className="text-[12px] text-text-secondary leading-relaxed">{bearStress.consensusBlindspots}</p>
                      )}
                    </div>
                    {bearStress.estimatedImpactPct != null && bearStress.stressedPrice != null && (
                      <PriceImpactArrow
                        currentPrice={analysis.currentPrice}
                        stressedPrice={bearStress.stressedPrice}
                        impactPct={bearStress.estimatedImpactPct}
                      />
                    )}
                  </div>
                </div>
              )}

              {/* Custom scenario input */}
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder={placeholders[placeholderIdx]}
                  value={customScenario}
                  onChange={(e) => setCustomScenario(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleCustomStress()}
                  className="flex-1 h-10 px-4 rounded-lg bg-base border border-[rgba(180,220,190,0.12)] text-text-primary placeholder-text-tertiary text-[13px] focus:outline-none focus:border-[rgba(207,174,98,0.4)] focus:ring-1 focus:ring-[rgba(207,174,98,0.15)] transition-all"
                />
                <button
                  onClick={handleCustomStress}
                  disabled={customBearLoading || !customScenario.trim()}
                  className="px-4 py-2 rounded-lg bg-loss/10 border border-[rgba(242,147,127,0.3)] text-loss text-[13px] font-medium hover:bg-loss/20 transition-colors flex items-center gap-1.5 disabled:opacity-50"
                >
                  {customBearLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldAlert className="w-3.5 h-3.5" strokeWidth={1.5} />}
                  Run Stress Test
                </button>
              </div>

              {/* Custom scenario result */}
              {customBearStress && (
                <div className="mt-4 rounded-md bg-loss/5 border border-[rgba(242,147,127,0.3)] p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-mono text-[10px] font-medium text-loss uppercase tracking-[0.13em]">{customBearStress.scenarioName || 'Custom Scenario'}</span>
                  </div>
                  <div className="space-y-2 mb-3">
                    {customBearStress.competitiveThreats && (
                      <p className="text-[12px] text-text-secondary leading-relaxed">{customBearStress.competitiveThreats}</p>
                    )}
                    {customBearStress.valuationConcerns && (
                      <p className="text-[12px] text-text-secondary leading-relaxed">{customBearStress.valuationConcerns}</p>
                    )}
                    {customBearStress.financialRisks && (
                      <p className="text-[12px] text-text-secondary leading-relaxed">{customBearStress.financialRisks}</p>
                    )}
                    {customBearStress.secularHeadwinds && (
                      <p className="text-[12px] text-text-secondary leading-relaxed">{customBearStress.secularHeadwinds}</p>
                    )}
                    {customBearStress.managementRisks && (
                      <p className="text-[12px] text-text-secondary leading-relaxed">{customBearStress.managementRisks}</p>
                    )}
                    {customBearStress.consensusBlindspots && (
                      <p className="text-[12px] text-text-secondary leading-relaxed">{customBearStress.consensusBlindspots}</p>
                    )}
                  </div>
                  {customBearStress.estimatedImpactPct != null && customBearStress.stressedPrice != null && (
                    <PriceImpactArrow
                      currentPrice={analysis.currentPrice}
                      stressedPrice={customBearStress.stressedPrice}
                      impactPct={customBearStress.estimatedImpactPct}
                    />
                  )}
                </div>
              )}
            </div>

            {/* ═══ Full Report Section ═══ */}
            {reportError && (
              <div className="rounded-[10px] bg-loss/5 border border-[rgba(242,147,127,0.3)] p-4 flex items-center gap-3">
                <XCircle className="w-4 h-4 text-loss flex-shrink-0" strokeWidth={1.5} />
                <span className="text-[13px] text-text-secondary flex-1">{reportError}</span>
                <button onClick={handleGenerateReport} className="text-[12px] text-loss font-medium hover:underline">Retry</button>
              </div>
            )}

            {reportLoading && (
              <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-8 flex flex-col items-center justify-center">
                <Loader2 className="w-8 h-8 text-accent animate-spin mb-4" strokeWidth={1.5} />
                <h3 className="font-serif text-[16px] font-medium text-text-primary mb-1 tracking-[-0.006em]">Generating Emouva Report</h3>
                <p className="text-[12px] text-text-tertiary">Comprehensive analysis with fresh market data. This may take 30-60 seconds.</p>
              </div>
            )}

            {report && !reportLoading && (
              <div ref={reportRef}>
                <div className="flex items-center justify-between mb-3">
                  <button
                    onClick={() => setShowReport(!showReport)}
                    className="flex items-center gap-2 text-[14px] font-medium text-text-primary hover:text-accent transition-colors"
                  >
                    {showReport ? <ChevronUp className="w-4 h-4" strokeWidth={1.5} /> : <ChevronDown className="w-4 h-4" strokeWidth={1.5} />}
                    {showReport ? 'Hide' : 'Show'} Emouva Report
                    <span className="font-mono text-[11px] text-text-tertiary font-normal ml-1 tabular-nums">
                      Generated {new Date(report.generatedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                  </button>
                </div>
                {showReport && <ReportView report={report} onDownload={handleDownloadPdf} />}
              </div>
            )}

            {/* Generate Report CTA (if no report yet) */}
            {!report && !reportLoading && !reportError && (
              <button
                onClick={handleGenerateReport}
                className="w-full py-4 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] hover:border-[rgba(207,174,98,0.35)] hover:bg-accent/[0.04] transition-all flex items-center justify-center gap-2 group"
              >
                <Sparkles className="w-4 h-4 text-text-tertiary group-hover:text-accent transition-colors" strokeWidth={1.5} />
                <span className="text-[14px] font-medium text-text-secondary group-hover:text-accent transition-colors">
                  Generate Full Investment Report
                </span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Demo modals */}
      <DemoEmailModal />
      <DemoLimitModal />
    </div>
  )
}
