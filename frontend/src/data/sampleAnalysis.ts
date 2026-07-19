/**
 * Pre-built sample NVDA analysis shown to first-time users.
 * Provides an instant "wow" moment before they run their own analysis.
 */

import type { StockAnalysis, BearStressResult } from './mockData'

export const SAMPLE_TICKER = 'NVDA'

export const sampleAnalysis: StockAnalysis = {
  symbol: 'NVDA',
  name: 'NVIDIA Corporation',
  currentPrice: 131.28,
  fairValue: { bear: 95, base: 155, bull: 210 },
  thesis:
    'NVIDIA dominates the AI accelerator market with ~80% data center GPU share, driven by its CUDA software moat and end-to-end platform approach. The Blackwell architecture cycle is the largest product ramp in company history, with hyperscaler demand outstripping supply through 2026. Revenue is inflecting from a hardware-sale model toward recurring software and cloud revenue (DGX Cloud, NVIDIA AI Enterprise), improving long-term margin durability. Key thesis drivers: (1) AI capex cycle still early innings — enterprise adoption barely started, (2) inference workloads scaling faster than training, expanding TAM, (3) sovereign AI buildouts adding a new demand vector beyond US hyperscalers.',
  bullCase:
    'AI capex accelerates as enterprise adoption hits inflection point. Blackwell margins expand to 78%+ as supply normalizes. Software revenue reaches $5B+ ARR by 2027. Automotive and robotics platforms create new multi-billion dollar TAM. NVIDIA becomes the "computing standard" for AI, similar to Intel in the PC era but with higher margins and a broader addressable market.',
  bearCase:
    'Custom silicon (Google TPUs, Amazon Trainium, Microsoft Maia) erodes GPU share in inference workloads. AI capex cycle moderates as hyperscalers optimize spending efficiency. China export restrictions reduce a ~$10B revenue opportunity. Gross margins compress from 75% to 65% as competition intensifies and customers gain leverage. Valuation multiple compresses from 35x to 20x forward earnings.',
  keyRisks: [
    'Customer concentration: Top 4 hyperscalers represent ~50% of data center revenue',
    'Custom chip threat: Google, Amazon, Meta, and Microsoft all developing in-house AI accelerators',
    'China export controls: ~15% of potential revenue at risk from US government restrictions',
    'Cyclical risk: AI capex spending could decelerate if ROI expectations are not met',
    'Valuation risk: Trading at 30x+ forward P/E leaves little room for execution missteps',
  ],
  metricsToWatch: [
    { metric: 'Data Center Revenue Growth (YoY)', current: '+93%', threshold: '>50% = thesis intact', status: 'pass' },
    { metric: 'Gross Margin', current: '75.2%', threshold: '>70% = pricing power intact', status: 'pass' },
    { metric: 'Hyperscaler Capex Growth', current: '+42%', threshold: '>20% = demand cycle intact', status: 'pass' },
    { metric: 'Custom Chip Market Share', current: '~12%', threshold: '<25% = moat intact', status: 'watch' },
  ],
  sentiment: { news: 72, filings: 68, insider: 45, analyst: 82, composite: 67 },
  financials: [
    { metric: 'Revenue (TTM)', value: '$130.5B', trend: 'up' },
    { metric: 'Net Income (TTM)', value: '$72.9B', trend: 'up' },
    { metric: 'Gross Margin', value: '75.2%', trend: 'up' },
    { metric: 'Free Cash Flow (TTM)', value: '$60.8B', trend: 'up' },
    { metric: 'P/E Ratio (Forward)', value: '32.4x', trend: 'flat' },
    { metric: 'EV/Revenue', value: '25.1x', trend: 'down' },
    { metric: 'ROIC', value: '88.3%', trend: 'up', badge: 'Excellent' },
    { metric: 'Piotroski F-Score', value: '7/9', trend: 'up', badge: 'Strong' },
    { metric: 'P/E vs Sector', value: '45% premium', trend: 'down' },
  ],
  verdict: 'BUY',
  confidence: 'HIGH',
  entryPrice: 110,
  dcfFairValue: 138,
  dcfAssumptions: { wacc: 10.5, phase1_growth: 25.0, phase2_growth: 15.0, terminal_growth: 2.5 },
  riskReward: '2.8:1',
  thesisBreaks: [
    'Data center revenue growth falls below 30% for 2 consecutive quarters',
    'Gross margin drops below 65% (signals competitive pricing pressure)',
    'Hyperscaler capex growth turns negative (demand cycle broken)',
  ],
}

export const sampleBearStress: BearStressResult = {
  ticker: 'NVDA',
  scenarioName: 'AI Capex Slowdown',
  estimatedImpactPct: -35,
  stressedPrice: 85.33,
  competitiveThreats:
    'Google TPU v6 and Amazon Trainium2 reach performance parity for inference workloads, capturing 30% of incremental AI compute spending. Meta deploys custom MTIA chips for 40% of internal inference. This forces NVIDIA to compete on price for the first time, compressing data center GPU ASPs by 15-20%.',
  valuationConcerns:
    'At 32x forward P/E, NVIDIA prices in sustained 40%+ earnings growth. If growth decelerates to 20% as the AI capex cycle matures, multiple compression to 22x would alone drive a 30% decline. Combined with earnings downgrades, downside to $85-90 is plausible.',
  financialRisks:
    'Inventory build-up risk if hyperscaler orders decelerate suddenly. $10B+ in purchase commitments could become a liability. Gross margins could compress 800-1000bps if competitive pricing pressure intensifies.',
  secularHeadwinds:
    'Shift from training to inference favors more efficient, purpose-built chips over general-purpose GPUs. Edge AI deployment reduces reliance on cloud GPU capacity. Open-source AI models reduce the compute intensity needed for competitive performance.',
  managementRisks:
    'Jensen Huang key-man risk. Company culture heavily centralized around founder. Transition planning unclear. Acquisition strategy (ARM attempt) shows willingness for bold moves that could distract from core business.',
  consensusBlindspots:
    'Market underestimates the speed at which hyperscalers can shift workloads to custom silicon. The 2-3 year custom chip development cycle means chips designed in the current AI boom will arrive just as NVIDIA faces its hardest comparisons. Consensus models assume linear growth in a market that has historically been cyclical.',
}
