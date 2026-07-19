/**
 * Module-level research store that persists across component mounts.
 * When a user starts an analysis and navigates away, the fetch continues.
 * Coming back shows the current state (loading, result, or error).
 */

import { useSyncExternalStore } from 'react'
import { type StockAnalysis, type BearStressResult, type FullReport } from '../data/mockData'
import { apiFetch } from '../api/client'
import { getCache, setCache } from './useLocalCache'
import { SAMPLE_TICKER, sampleAnalysis, sampleBearStress } from '../data/sampleAnalysis'

const RESEARCH_CACHE_TTL = 24 * 60 * 60 * 1000 // 24h
const REPORT_CACHE_TTL = 7 * 24 * 60 * 60 * 1000 // 7 days

interface SentimentScores {
  news: number
  filings: number
  insider: number
  analyst: number
  composite: number
}

type FreshnessStatus = 'fresh' | 'stale' | 'missing' | null

interface ResearchState {
  query: string
  analysis: StockAnalysis | null
  loading: boolean
  error: string | null
  fromCache: boolean
  isSample: boolean
  // Sentiment
  sentimentLoading: boolean
  // Bear stress test
  bearStress: BearStressResult | null
  bearStressLoading: boolean
  bearStressError: string | null
  customBearStress: BearStressResult | null
  customBearLoading: boolean
  // Full report
  report: FullReport | null
  reportLoading: boolean
  reportError: string | null
  // Server cache freshness
  analysisFreshness: FreshnessStatus
  bearCaseFreshness: FreshnessStatus
  sentimentFreshness: FreshnessStatus
  refreshingInBackground: boolean
}

let state: ResearchState = {
  query: '',
  analysis: null,
  loading: false,
  error: null,
  fromCache: false,
  isSample: false,
  sentimentLoading: false,
  bearStress: null,
  bearStressLoading: false,
  bearStressError: null,
  customBearStress: null,
  customBearLoading: false,
  report: null,
  reportLoading: false,
  reportError: null,
  analysisFreshness: null,
  bearCaseFreshness: null,
  sentimentFreshness: null,
  refreshingInBackground: false,
}

// Restore last viewed research on module load — or show sample
const lastTicker = getCache<string>('research_last_ticker')
if (lastTicker) {
  const cached = getCache<StockAnalysis>(`research_${lastTicker}`)
  if (cached) {
    state = { ...state, query: lastTicker, analysis: cached, fromCache: true }
  }
  // Restore cached report if available
  const cachedReport = getCache<FullReport>(`report_${lastTicker}`)
  if (cachedReport) {
    state = { ...state, report: cachedReport }
  }
} else {
  // First visit — load sample data
  state = {
    ...state,
    query: SAMPLE_TICKER,
    analysis: sampleAnalysis,
    bearStress: sampleBearStress,
    isSample: true,
    fromCache: false,
  }
}

const listeners = new Set<() => void>()

function emit() {
  listeners.forEach((fn) => fn())
}

function setState(updates: Partial<ResearchState>) {
  state = { ...state, ...updates }
  emit()
}

function getSnapshot(): ResearchState {
  return state
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

// In-flight abort controller
let abortController: AbortController | null = null

function parseAnalysisResponse(res: Record<string, unknown>, ticker: string): StockAnalysis {
  const valuation = res.valuation as Record<string, number> | undefined
  return {
    symbol: (res.ticker as string) || ticker.toUpperCase(),
    name: (res.company_name as string) || ticker.toUpperCase(),
    currentPrice: (res.current_price as number) || valuation?.base || 0,
    fairValue: {
      bear: valuation?.bear || 0,
      base: valuation?.base || 0,
      bull: valuation?.bull || 0,
    },
    thesis: (res.investment_thesis as string) || '',
    bullCase: (res.bull_case as string) || '',
    bearCase: (res.bear_case as string) || '',
    keyRisks: (res.key_risks as string[]) || [],
    metricsToWatch: [],
    sentiment: { news: 0, filings: 0, insider: 0, analyst: 0, composite: 0 },
    financials: (res.financials as { metric: string; value: string; trend: 'up' | 'down' | 'flat'; badge?: string }[]) || [],
    verdict: (res.verdict as 'BUY' | 'HOLD' | 'SELL') || '',
    confidence: (res.confidence as 'HIGH' | 'MEDIUM' | 'LOW') || '',
    entryPrice: (res.entry_price as number) || null,
    dcfFairValue: (res.dcf_fair_value as number) || null,
    dcfAssumptions: (res.dcf_assumptions as { wacc: number; phase1_growth: number; phase2_growth: number; terminal_growth: number }) || null,
    riskReward: (res.risk_reward as string) || '',
    thesisBreaks: (res.thesis_breaks as string[]) || [],
  }
}

function parseBearStressResponse(res: Record<string, unknown>): BearStressResult {
  return {
    ticker: (res.ticker as string) || '',
    scenarioName: (res.scenario_name as string) || 'General Bear Case',
    estimatedImpactPct: (res.estimated_impact_pct as number) ?? null,
    stressedPrice: (res.stressed_price as number) ?? null,
    competitiveThreats: (res.competitive_threats as string) || '',
    valuationConcerns: (res.valuation_concerns as string) || '',
    financialRisks: (res.financial_risks as string) || '',
    secularHeadwinds: (res.secular_headwinds as string) || '',
    managementRisks: (res.management_risks as string) || '',
    consensusBlindspots: (res.consensus_blindspots as string) || '',
  }
}

function parseReportResponse(res: Record<string, unknown>): FullReport {
  const pt = (res.price_targets as Record<string, number>) || {}
  return {
    ticker: (res.ticker as string) || '',
    companyName: (res.company_name as string) || '',
    currentPrice: (res.current_price as number) ?? null,
    generatedAt: (res.generated_at as string) || new Date().toISOString(),
    executiveSummary: (res.executive_summary as string) || '',
    valuationAnalysis: (res.valuation_analysis as string) || '',
    investmentThesis: (res.investment_thesis as string) || '',
    keyRisks: (res.key_risks as string[]) || [],
    catalysts: (res.catalysts as string[]) || [],
    financialHighlights: (res.financial_highlights as string) || '',
    verdict: (res.verdict as string) || 'Hold',
    confidence: (res.confidence as string) || 'Medium',
    verdictReasoning: (res.verdict_reasoning as string) || '',
    priceTargets: { bear: pt.bear || 0, base: pt.base || 0, bull: pt.bull || 0 },
  }
}

async function runAnalysis(ticker: string) {
  if (!ticker.trim()) return
  const normalizedTicker = ticker.trim().toUpperCase()

  // Check local cache first
  const cached = getCache<StockAnalysis>(`research_${normalizedTicker}`)
  if (cached) {
    const cachedReport = getCache<FullReport>(`report_${normalizedTicker}`)
    setState({
      query: normalizedTicker, analysis: cached, fromCache: true, error: null, loading: false,
      isSample: false,
      bearStress: null, bearStressError: null, customBearStress: null,
      report: cachedReport || null, reportError: null,
      analysisFreshness: 'fresh', bearCaseFreshness: null, sentimentFreshness: null,
      refreshingInBackground: false,
    })
    setCache('research_last_ticker', normalizedTicker, RESEARCH_CACHE_TTL)
    // If cached analysis lacks sentiment, fetch it
    if (!cached.sentiment || cached.sentiment.composite === 0) {
      runSentiment(normalizedTicker)
    }
    return
  }

  // Check server cache (stale-while-revalidate)
  try {
    const serverCache = await apiFetch<{
      ticker: string
      fields: Record<string, { data: Record<string, unknown> | null; status: string; updated_at: string | null }>
    }>(`/api/metrics/${normalizedTicker}`)

    const analysisField = serverCache.fields?.ai_analysis
    const bearField = serverCache.fields?.ai_bear_case
    const sentimentField = serverCache.fields?.ai_sentiment

    if (analysisField?.data && (analysisField.status === 'fresh' || analysisField.status === 'stale')) {
      const parsed = parseAnalysisResponse(analysisField.data, normalizedTicker)

      // Apply cached sentiment if available
      if (sentimentField?.data) {
        const scores = (sentimentField.data as Record<string, unknown>).scores as SentimentScores | undefined
        if (scores) parsed.sentiment = scores
      }

      // Apply cached bear case if available
      let bearStress: BearStressResult | null = null
      if (bearField?.data) {
        bearStress = parseBearStressResponse(bearField.data)
      }

      setState({
        query: normalizedTicker,
        analysis: parsed,
        fromCache: true,
        error: null,
        loading: false,
        isSample: false,
        bearStress,
        bearStressError: null,
        customBearStress: null,
        report: null,
        reportError: null,
        analysisFreshness: analysisField.status as FreshnessStatus,
        bearCaseFreshness: (bearField?.status as FreshnessStatus) || 'missing',
        sentimentFreshness: (sentimentField?.status as FreshnessStatus) || 'missing',
        refreshingInBackground: analysisField.status === 'stale',
      })
      setCache(`research_${normalizedTicker}`, parsed, RESEARCH_CACHE_TTL)
      setCache('research_last_ticker', normalizedTicker, RESEARCH_CACHE_TTL)

      // If stale, refresh in background
      if (analysisField.status === 'stale') {
        _refreshInBackground(normalizedTicker)
      }
      // If bear case or sentiment missing/stale, fetch them
      if (!bearField?.data || bearField.status !== 'fresh') {
        runBearStress(normalizedTicker)
      }
      if (!sentimentField?.data || sentimentField.status !== 'fresh') {
        runSentiment(normalizedTicker)
      }
      return
    }
  } catch {
    // Server cache miss — proceed with full analysis
  }

  // No cache at all — run full analysis
  if (abortController) abortController.abort()
  abortController = new AbortController()

  setState({
    query: normalizedTicker, loading: true, error: null, fromCache: false, isSample: false,
    bearStress: null, bearStressError: null, customBearStress: null,
    report: null, reportError: null,
    analysisFreshness: null, bearCaseFreshness: null, sentimentFreshness: null,
    refreshingInBackground: false,
  })

  // Fire all 3 calls in true parallel — bear case + sentiment don't depend on stock result
  runBearStress(normalizedTicker)
  runSentiment(normalizedTicker)

  try {
    const res = await apiFetch<Record<string, unknown>>('/api/analysis/stock', {
      method: 'POST',
      body: JSON.stringify({ ticker: normalizedTicker }),
      signal: abortController.signal,
    })
    const parsed = parseAnalysisResponse(res, normalizedTicker)
    // Preserve sentiment if it was already loaded by the parallel runSentiment call
    if (state.analysis?.sentiment && state.analysis.sentiment.composite > 0) {
      parsed.sentiment = state.analysis.sentiment
    }
    setState({ analysis: parsed, loading: false, error: null, analysisFreshness: 'fresh' })
    setCache(`research_${normalizedTicker}`, parsed, RESEARCH_CACHE_TTL)
    setCache('research_last_ticker', normalizedTicker, RESEARCH_CACHE_TTL)
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    const message = err instanceof Error ? err.message : 'Analysis failed. Please try again.'
    setState({ loading: false, error: message })
  }
}

/** Background refresh for stale server-cached data */
async function _refreshInBackground(ticker: string) {
  try {
    const res = await apiFetch<Record<string, unknown>>('/api/analysis/stock', {
      method: 'POST',
      body: JSON.stringify({ ticker }),
    })
    const parsed = parseAnalysisResponse(res, ticker)
    // Preserve existing sentiment data
    if (state.analysis?.sentiment && state.analysis.sentiment.composite > 0) {
      parsed.sentiment = state.analysis.sentiment
    }
    setState({
      analysis: parsed,
      fromCache: false,
      analysisFreshness: 'fresh',
      refreshingInBackground: false,
    })
    setCache(`research_${ticker}`, parsed, RESEARCH_CACHE_TTL)
  } catch {
    setState({ refreshingInBackground: false })
  }
}

async function forceRefresh(ticker: string) {
  if (!ticker.trim()) return
  const normalizedTicker = ticker.trim().toUpperCase()

  if (abortController) abortController.abort()
  abortController = new AbortController()

  setState({ loading: true, error: null, fromCache: false })

  // Fire all 3 calls in true parallel
  runBearStress(normalizedTicker)
  runSentiment(normalizedTicker)

  try {
    const res = await apiFetch<Record<string, unknown>>('/api/analysis/stock', {
      method: 'POST',
      body: JSON.stringify({ ticker: normalizedTicker }),
      signal: abortController.signal,
    })
    const parsed = parseAnalysisResponse(res, normalizedTicker)
    // Preserve sentiment if already loaded by parallel runSentiment call
    if (state.analysis?.sentiment && state.analysis.sentiment.composite > 0) {
      parsed.sentiment = state.analysis.sentiment
    }
    setState({ analysis: parsed, loading: false, error: null })
    setCache(`research_${normalizedTicker}`, parsed, RESEARCH_CACHE_TTL)
    setCache('research_last_ticker', normalizedTicker, RESEARCH_CACHE_TTL)
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === 'AbortError') return
    const message = err instanceof Error ? err.message : 'Refresh failed. Please try again.'
    setState({ loading: false, error: message })
  }
}

async function runBearStress(ticker: string, scenario?: string) {
  if (!ticker.trim()) return
  const isCustom = !!scenario

  if (isCustom) {
    setState({ customBearLoading: true })
  } else {
    setState({ bearStressLoading: true, bearStressError: null })
  }

  try {
    const body: Record<string, string> = { ticker: ticker.toUpperCase() }
    if (scenario) body.scenario = scenario

    const res = await apiFetch<Record<string, unknown>>('/api/analysis/bear-case', {
      method: 'POST',
      body: JSON.stringify(body),
    })
    const parsed = parseBearStressResponse(res)

    if (isCustom) {
      setState({ customBearStress: parsed, customBearLoading: false })
    } else {
      setState({ bearStress: parsed, bearStressLoading: false })
    }
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Bear case analysis failed.'
    if (isCustom) {
      setState({ customBearLoading: false })
    } else {
      setState({ bearStressLoading: false, bearStressError: message })
    }
  }
}

async function runSentiment(ticker: string) {
  if (!ticker.trim()) return
  setState({ sentimentLoading: true })

  try {
    const res = await apiFetch<Record<string, unknown>>('/api/analysis/sentiment', {
      method: 'POST',
      body: JSON.stringify({ ticker: ticker.toUpperCase() }),
    })
    const scores = res.scores as SentimentScores | undefined
    if (scores && state.analysis) {
      setState({
        sentimentLoading: false,
        analysis: { ...state.analysis, sentiment: scores },
      })
      // Update cached analysis with sentiment
      const cached = getCache<StockAnalysis>(`research_${ticker.toUpperCase()}`)
      if (cached) {
        setCache(`research_${ticker.toUpperCase()}`, { ...cached, sentiment: scores }, RESEARCH_CACHE_TTL)
      }
    } else {
      setState({ sentimentLoading: false })
    }
  } catch {
    setState({ sentimentLoading: false })
  }
}

async function generateReport(ticker: string) {
  if (!ticker.trim()) return

  setState({ reportLoading: true, reportError: null })

  try {
    const res = await apiFetch<Record<string, unknown>>('/api/analysis/report', {
      method: 'POST',
      body: JSON.stringify({ ticker: ticker.toUpperCase() }),
    })
    const parsed = parseReportResponse(res)
    setState({ report: parsed, reportLoading: false })
    setCache(`report_${ticker.toUpperCase()}`, parsed, REPORT_CACHE_TTL)
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Report generation failed.'
    setState({ reportLoading: false, reportError: message })
  }
}

function setQuery(query: string) {
  setState({ query })
}

function clearError() {
  setState({ error: null })
}

function dismissSample() {
  setState({ isSample: false })
}

export { runAnalysis, setQuery }

export function useResearchStore() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot)
  return {
    ...snapshot,
    setQuery,
    runAnalysis,
    forceRefresh,
    clearError,
    runBearStress,
    generateReport,
    dismissSample,
  }
}
