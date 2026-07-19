// ============================================================
// Shared TypeScript interfaces and utility functions.
// All data comes from the FastAPI backend via Robinhood.
// ============================================================

export interface Position {
  symbol: string
  name: string
  shares: number
  avgCost: number
  currentPrice: number
  previousClose: number
  sector: string
  conviction: number // 1-5
  thesisStatus: 'intact' | 'watch' | 'breaking'
  sparkline?: number[]
}

export interface WatchlistItem {
  symbol: string
  name: string
  price: number
  change: number
  changePct: number
  aiScore: number // 0-100
  sparkline?: number[]
}

export interface PortfolioHistory {
  date: string
  value: number
  after_hours?: boolean
}

export interface DailyBriefAlert {
  type: 'rebalance' | 'tax_harvest' | 'thesis_break' | 'risk' | 'opportunity' | 'overvalued' | 'undervalued' | 'correlation' | 'thesis' | 'tax' | 'earnings' | 'macro'
  severity: 'info' | 'warning' | 'critical'
  title: string
  description: string
  action?: string
}

export interface StockVerdict {
  symbol: string
  verdict: 'strong_hold' | 'hold' | 'watch' | 'trim' | 'sell'
  quality_score: number
  thesis: string
  concerns: string
  action: string
}

export interface ConcentrationBreakdown {
  label: string
  value: number
  weight: number
}

export interface ConcentrationDimension {
  breakdown: ConcentrationBreakdown[]
  hhi: number
  topHoldingPct: number
  rating: 'green' | 'yellow' | 'red'
}

export interface ConcentrationRisk {
  score: number
  rating: 'green' | 'yellow' | 'red'
  dimensions: {
    sector: ConcentrationDimension
    market_cap: ConcentrationDimension
    geography: ConcentrationDimension
  }
}

export interface RiskData {
  score: number
  dailyVaR95: number
  monthlyCVaR95: number
  riskBudgetUsed: number
  portfolioVolatility: number
  maxDrawdown: number
  drawdownSeries: { date: string; drawdown: number }[]
  sectorWeights: { sector: string; value: number; weight: number }[]
  concentration: { hhi: number; top5Pct: number }
  factors: { name: string; exposure: number; status: 'ok' | 'high' | 'low'; detail?: string }[]
  stressTests: { scenario: string; impact: number }[]
  correlationAlerts: { pair: [string, string]; correlation: number; method?: 'pearson' | 'spearman' }[]
  concentrationRisk: ConcentrationRisk
}

export interface StockAnalysis {
  symbol: string
  name: string
  currentPrice: number
  fairValue: { bear: number; base: number; bull: number }
  thesis: string
  bullCase: string
  bearCase: string
  keyRisks: string[]
  metricsToWatch: { metric: string; current: string; threshold: string; status: 'pass' | 'watch' | 'fail' }[]
  sentiment: { news: number; filings: number; insider: number; analyst: number; composite: number }
  financials: { metric: string; value: string; trend: 'up' | 'down' | 'flat'; badge?: string }[]
  // Verdict & decision support
  verdict: 'BUY' | 'HOLD' | 'SELL' | ''
  confidence: 'HIGH' | 'MEDIUM' | 'LOW' | ''
  entryPrice: number | null
  dcfFairValue: number | null
  dcfAssumptions: { wacc: number; phase1_growth: number; phase2_growth: number; terminal_growth: number } | null
  riskReward: string
  thesisBreaks: string[]
}

export interface BearStressResult {
  ticker: string
  scenarioName: string
  estimatedImpactPct: number | null
  stressedPrice: number | null
  competitiveThreats: string
  valuationConcerns: string
  financialRisks: string
  secularHeadwinds: string
  managementRisks: string
  consensusBlindspots: string
}

export interface FullReport {
  ticker: string
  companyName: string
  currentPrice: number | null
  generatedAt: string
  executiveSummary: string
  valuationAnalysis: string
  investmentThesis: string
  keyRisks: string[]
  catalysts: string[]
  financialHighlights: string
  verdict: string
  confidence: string
  verdictReasoning: string
  priceTargets: { bear: number; base: number; bull: number }
}

// --- Empty defaults for hooks ---
const EMPTY_DIMENSION: ConcentrationDimension = {
  breakdown: [], hhi: 0, topHoldingPct: 0, rating: 'green',
}

export const EMPTY_RISK_DATA: RiskData = {
  score: 0,
  dailyVaR95: 0,
  monthlyCVaR95: 0,
  riskBudgetUsed: 0,
  portfolioVolatility: 0,
  maxDrawdown: 0,
  drawdownSeries: [],
  sectorWeights: [],
  concentration: { hhi: 0, top5Pct: 0 },
  factors: [],
  stressTests: [],
  correlationAlerts: [],
  concentrationRisk: {
    score: 0,
    rating: 'green',
    dimensions: { sector: { ...EMPTY_DIMENSION }, market_cap: { ...EMPTY_DIMENSION }, geography: { ...EMPTY_DIMENSION } },
  },
}

// --- Risk Profile Types ---

export interface RiskProfilePersona {
  name: string
  description: string
  emoji: string
}

export interface RiskProfileFactorDetail {
  score: number
  weight: number
  details: Record<string, number>
}

export interface RiskProfileFinding {
  type: 'critical' | 'warning' | 'positive'
  text: string
}

export interface DiversificationSuggestion {
  symbol: string
  name: string
  category: string
  expense_ratio: number
  reason: string
  suggested_allocation_pct: number
  suggested_allocation_dollar: number
  impact: {
    drawdown_improvement_pct: number
    crash_savings_2022: number
    crash_savings_2020: number
    crash_savings_2008: number
    annual_cost: number
  }
}

export interface BeforeAfterMetrics {
  crash_2022_pct: number
  crash_2022_dollar: number
  crash_2020_pct: number
  crash_2020_dollar: number
  crash_2008_pct: number
  crash_2008_dollar: number
  health_score: number
  sectors_count: number
  effective_positions: number
  max_drawdown_pct: number
}

export interface RiskProfile {
  behavioral_score: number
  persona: RiskProfilePersona
  factor_breakdown: {
    composition: RiskProfileFactorDetail
    concentration: RiskProfileFactorDetail
    volatility: RiskProfileFactorDetail
    correlation: RiskProfileFactorDetail
  }
  key_findings: RiskProfileFinding[]
  diversification_suggestions: DiversificationSuggestion[]
  before_after: {
    current: BeforeAfterMetrics
    suggested: BeforeAfterMetrics
    improvement: {
      crash_savings_dollar: number
      crash_savings_2020_dollar: number
      crash_savings_2008_dollar: number
      health_score_gain: number
      new_sectors_added: number
    }
  }
  portfolio_value: number
  source?: string
}

export const EMPTY_RISK_PROFILE: RiskProfile = {
  behavioral_score: 0,
  persona: { name: 'Unknown', description: 'Connect your portfolio to see your risk profile.', emoji: 'shield' },
  factor_breakdown: {
    composition: { score: 0, weight: 0.40, details: {} },
    concentration: { score: 0, weight: 0.30, details: {} },
    volatility: { score: 0, weight: 0.20, details: {} },
    correlation: { score: 0, weight: 0.10, details: {} },
  },
  key_findings: [],
  diversification_suggestions: [],
  before_after: {
    current: { crash_2022_pct: 0, crash_2022_dollar: 0, crash_2020_pct: 0, crash_2020_dollar: 0, crash_2008_pct: 0, crash_2008_dollar: 0, health_score: 0, sectors_count: 0, effective_positions: 0, max_drawdown_pct: 0 },
    suggested: { crash_2022_pct: 0, crash_2022_dollar: 0, crash_2020_pct: 0, crash_2020_dollar: 0, crash_2008_pct: 0, crash_2008_dollar: 0, health_score: 0, sectors_count: 0, effective_positions: 0, max_drawdown_pct: 0 },
    improvement: { crash_savings_dollar: 0, crash_savings_2020_dollar: 0, crash_savings_2008_dollar: 0, health_score_gain: 0, new_sectors_added: 0 },
  },
  portfolio_value: 0,
}

// --- Helper Functions ---
export function formatCurrency(value: number, compact = false): string {
  if (compact && Math.abs(value) >= 1000) {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(value)
  }
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

export function formatPercent(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

export function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value)
}

export function getChangeColor(value: number): string {
  if (value > 0) return 'text-gain'
  if (value < 0) return 'text-loss'
  return 'text-text-tertiary'
}

export function getChangeBgColor(value: number): string {
  if (value > 0) return 'bg-gain/10'
  if (value < 0) return 'bg-loss/10'
  return 'bg-surface-3'
}
