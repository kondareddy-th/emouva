import clsx from 'clsx'
import { RefreshCw, ShieldCheck, Link2, ArrowRight, AlertTriangle, BarChart3, Layers, Target } from 'lucide-react'
import { Link } from 'react-router-dom'
import { formatCurrency } from '../data/mockData'
import { useRiskData, usePortfolioSummary, usePositions } from '../hooks/usePortfolio'
import DrawdownChart from '../components/risk/DrawdownChart'
import SectorConcentration from '../components/risk/SectorConcentration'
import CorrelationMatrix from '../components/risk/CorrelationMatrix'
import ConcentrationRiskCard from '../components/risk/ConcentrationRiskCard'
import RealEarningsYield from '../components/risk/RealEarningsYield'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'
import ModeToggle from '../components/ModeToggle'

function RiskScoreGauge({ score }: { score: number }) {
  const circumference = 2 * Math.PI * 80
  const progress = (score / 100) * circumference
  const getColor = (s: number) => {
    if (s <= 30) return '#CFAE62'
    if (s <= 50) return '#DFB65A'
    if (s <= 70) return '#C48A5B'
    return '#F2937F'
  }
  const getLabel = (s: number) => {
    if (s <= 30) return 'Low'
    if (s <= 50) return 'Moderate'
    if (s <= 70) return 'Moderate-High'
    return 'High'
  }

  return (
    <div className="flex items-center gap-4">
      <div className="relative w-20 h-20 shrink-0">
        <svg viewBox="0 0 200 200" className="w-full h-full -rotate-90">
          <circle
            cx="100" cy="100" r="80" fill="none"
            stroke="rgba(180,220,190,0.08)" strokeWidth="12"
          />
          <circle
            cx="100" cy="100" r="80" fill="none"
            stroke={getColor(score)} strokeWidth="12" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference - progress}
            className="gauge-animate"
            style={{
              '--circumference': `${circumference}`,
              '--target-offset': `${circumference - progress}`,
            } as React.CSSProperties}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[26px] font-serif font-medium font-tabular leading-none" style={{ color: getColor(score) }}>
            {score}
          </span>
        </div>
      </div>
      <div>
        <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Risk Score</p>
        <p className="text-[16px] font-serif font-medium mt-1" style={{ color: getColor(score) }}>
          {getLabel(score)}
        </p>
      </div>
    </div>
  )
}

function MetricCard({ label, value, subtext, color }: {
  label: string
  value: string
  subtext: string
  color: string
}) {
  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover">
      <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-2">{label}</p>
      <div className={clsx('text-[26px] font-serif font-medium font-tabular leading-none', color)}>
        {value}
      </div>
      <p className="text-[11px] text-text-tertiary mt-2">{subtext}</p>
    </div>
  )
}

function FactorBar({ name, exposure, status, detail }: { name: string; exposure: number; status: 'ok' | 'high' | 'low'; detail?: string }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-[13px] text-text-secondary font-medium">{name}</span>
          {status === 'high' && (
            <span className="font-mono text-[9.5px] tracking-[0.11em] px-1.5 py-0.5 rounded bg-warning/10 text-warning">HIGH</span>
          )}
          {status === 'low' && (
            <span className="font-mono text-[9.5px] tracking-[0.11em] px-1.5 py-0.5 rounded bg-loss/10 text-loss">LOW</span>
          )}
          {detail && (
            <span className="font-mono text-[10px] text-text-tertiary tabular-nums">{detail}</span>
          )}
        </div>
        <span className="font-mono text-[13px] text-text-primary tabular-nums">{exposure}%</span>
      </div>
      <div className="h-1.5 bg-[rgba(180,220,190,0.08)] rounded-full overflow-hidden">
        <div
          className={clsx(
            'h-full rounded-full transition-all duration-700',
            status === 'high' ? 'bg-warning' : status === 'low' ? 'bg-loss/50' : 'bg-accent'
          )}
          style={{ width: `${exposure}%` }}
        />
      </div>
    </div>
  )
}

function LoadingSkeleton() {
  return (
    <div className="px-4 md:px-8 py-6 md:py-8 animate-pulse">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 h-[88px]">
            <div className="h-3 w-20 bg-surface-3 rounded mb-3" />
            <div className="h-6 w-28 bg-surface-3 rounded" />
          </div>
        ))}
      </div>
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 mb-6 h-[200px]">
        <div className="h-4 w-40 bg-surface-3 rounded mb-4" />
        <div className="h-[140px] bg-surface-3/50 rounded" />
      </div>
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 mb-6 h-[220px]">
        <div className="h-4 w-32 bg-surface-3 rounded mb-3" />
        <div className="h-[160px] bg-surface-3/50 rounded" />
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 h-[280px]">
            <div className="h-4 w-32 bg-surface-3 rounded mb-3" />
            <div className="space-y-3">
              {[...Array(4)].map((_, j) => (
                <div key={j} className="h-8 bg-surface-3/50 rounded" />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function RiskCenter() {
  const { data: riskData, source, refetch, loading } = useRiskData()
  const { data: summary, loading: summaryLoading } = usePortfolioSummary()
  const { data: positions } = usePositions()
  const portfolioValue = summary.totalValue
  const isDisconnected = source === 'disconnected' && !loading && positions.length === 0

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-base/80 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-4 md:px-8 h-14">
          <h1 className="text-[18px] font-serif font-medium text-text-primary tracking-tight">Risk Center</h1>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            <SyncButton />
            <NotificationsBell />
          </div>
        </div>
        <div className="header-gradient-line" />
      </div>

      {loading ? (
        <LoadingSkeleton />
      ) : isDisconnected ? (
        <div className="px-4 md:px-8 py-8 md:py-10 max-w-3xl mx-auto">
          {/* Hero */}
          <div className="text-center mb-8 md:mb-10 animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-accent/[0.08] border border-[rgba(180,220,190,0.12)] flex items-center justify-center mx-auto mb-5">
              <ShieldCheck className="w-8 h-8 text-accent" strokeWidth={1.5} />
            </div>
            <h2 className="text-[28px] font-serif font-medium text-text-primary tracking-tight mb-3">
              Portfolio Risk Analysis
            </h2>
            <p className="text-[14px] text-text-secondary max-w-md mx-auto leading-relaxed">
              Connect your Robinhood account to get a comprehensive risk assessment of your portfolio.
            </p>
          </div>

          {/* What you'll get */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8 stagger">
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
              <div className="w-9 h-9 rounded-lg bg-loss/10 flex items-center justify-center mb-3">
                <AlertTriangle className="w-4.5 h-4.5 text-loss" strokeWidth={1.5} />
              </div>
              <h4 className="text-[15px] font-serif font-medium text-text-primary mb-1">Value at Risk</h4>
              <p className="text-[11px] text-text-tertiary leading-relaxed">
                Daily VaR, drawdown history, and volatility metrics for your actual holdings.
              </p>
            </div>
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
              <div className="w-9 h-9 rounded-lg bg-warning/10 flex items-center justify-center mb-3">
                <Layers className="w-4.5 h-4.5 text-warning" strokeWidth={1.5} />
              </div>
              <h4 className="text-[15px] font-serif font-medium text-text-primary mb-1">Concentration Risk</h4>
              <p className="text-[11px] text-text-tertiary leading-relaxed">
                Sector, market cap, and geography concentration with HHI scoring.
              </p>
            </div>
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
              <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center mb-3">
                <BarChart3 className="w-4.5 h-4.5 text-accent" strokeWidth={1.5} />
              </div>
              <h4 className="text-[15px] font-serif font-medium text-text-primary mb-1">Stress Tests</h4>
              <p className="text-[11px] text-text-tertiary leading-relaxed">
                See how your portfolio would perform in recession, rate hike, and crash scenarios.
              </p>
            </div>
          </div>

          {/* Connect CTA */}
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(207,174,98,0.25)] p-6">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                  <Link2 className="w-6 h-6 text-accent" strokeWidth={1.5} />
                </div>
                <div>
                  <h3 className="text-[17px] font-serif font-medium text-text-primary mb-0.5">Connect to analyze your risk</h3>
                  <p className="text-[13px] text-text-tertiary">Risk scores are computed from your actual positions</p>
                </div>
              </div>
              <Link
                to="/settings"
                className="flex items-center gap-2 px-5 py-2.5 rounded-md bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-all press-scale shrink-0"
              >
                Connect
                <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      ) : (
      <div className="px-4 md:px-8 py-6 md:py-8">
        {/* Market Indicator: Real Earnings Yield */}
        <div className="mb-6">
          <RealEarningsYield />
        </div>

        {/* Summary Row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4 mb-6 stagger">
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 flex items-center card-hover">
            <RiskScoreGauge score={riskData.score} />
          </div>
          <MetricCard
            label="Daily VaR (95%)"
            value={`${riskData.dailyVaR95}%`}
            subtext={`Max daily loss: ${formatCurrency(portfolioValue * Math.abs(riskData.dailyVaR95) / 100)}`}
            color="text-loss"
          />
          <MetricCard
            label="Annualized Volatility"
            value={`${riskData.portfolioVolatility.toFixed(1)}%`}
            subtext={`${riskData.portfolioVolatility > 25 ? 'Above average' : 'Within normal range'}`}
            color={riskData.portfolioVolatility > 25 ? 'text-warning' : 'text-accent'}
          />
          <MetricCard
            label="Max Drawdown"
            value={`${riskData.maxDrawdown.toFixed(1)}%`}
            subtext={`Worst peak-to-trough: ${formatCurrency(portfolioValue * Math.abs(riskData.maxDrawdown) / 100)}`}
            color="text-loss"
          />
        </div>

        {/* Concentration Risk */}
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 mb-6 card-hover">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[16px] font-serif font-medium text-text-primary">Concentration Risk</h3>
            <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Sector + Market Cap + Geography</span>
          </div>
          <ConcentrationRiskCard data={riskData.concentrationRisk} />
        </div>

        {/* Drawdown Chart — Full Width */}
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 mb-6 card-hover">
          <div className="flex items-center justify-between mb-1">
            <h3 className="text-[16px] font-serif font-medium text-text-primary">Drawdown History</h3>
            <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Last 90 days</span>
          </div>
          <p className="text-[11px] text-text-tertiary mb-3">
            How far your portfolio has fallen from its peak value over time — deeper dips mean higher risk.
          </p>
          <DrawdownChart data={riskData.drawdownSeries} maxDrawdown={riskData.maxDrawdown} />
        </div>

        {/* Three-Column Grid — equal height cards with scrollable content */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {/* Sector Concentration */}
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover flex flex-col">
            <div className="flex items-center justify-between mb-3 shrink-0">
              <h3 className="text-[16px] font-serif font-medium text-text-primary">Sector Concentration</h3>
              <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">By weight</span>
            </div>
            <div className="overflow-y-auto max-h-[360px] scrollbar-thin flex-1">
              <SectorConcentration
                sectors={riskData.sectorWeights}
                hhi={riskData.concentration.hhi}
                top5Pct={riskData.concentration.top5Pct}
              />
            </div>
          </div>
          {/* Correlation Alerts */}
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover flex flex-col">
            <div className="flex items-center justify-between mb-3 shrink-0">
              <h3 className="text-[16px] font-serif font-medium text-text-primary">Correlation Alerts</h3>
              <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Threshold 0.65</span>
            </div>
            <div className="overflow-y-auto max-h-[360px] scrollbar-thin flex-1">
              <CorrelationMatrix alerts={riskData.correlationAlerts} />
            </div>
          </div>

          {/* Stress Tests */}
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover flex flex-col">
            <h3 className="text-[16px] font-serif font-medium text-text-primary mb-3 shrink-0">Stress Tests</h3>
            <div className="space-y-3 overflow-y-auto max-h-[360px] scrollbar-thin flex-1">
              {riskData.stressTests.map((test) => {
                const dollarImpact = portfolioValue * (test.impact / 100)
                const severity = Math.abs(test.impact) > 30 ? 'critical' : Math.abs(test.impact) > 20 ? 'warning' : 'moderate'
                return (
                  <div key={test.scenario} className="p-3 rounded-lg hover:bg-accent/[0.03] transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[13px] text-text-secondary font-medium">{test.scenario}</span>
                      <span className={clsx(
                        'text-[16px] font-serif font-medium font-tabular',
                        severity === 'critical' ? 'text-loss' : severity === 'warning' ? 'text-warning' : 'text-text-secondary'
                      )}>
                        {test.impact}%
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <div className="flex-1 h-1 bg-[rgba(180,220,190,0.08)] rounded-full overflow-hidden">
                        <div
                          className={clsx(
                            'h-full rounded-full',
                            severity === 'critical' ? 'bg-loss' : severity === 'warning' ? 'bg-warning' : 'bg-text-tertiary'
                          )}
                          style={{ width: `${Math.min(Math.abs(test.impact), 100)}%` }}
                        />
                      </div>
                      <span className="font-mono text-[11px] text-text-tertiary tabular-nums min-w-[70px] text-right">
                        {formatCurrency(dollarImpact)}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Factor Exposure — Full Width */}
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 card-hover">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-[16px] font-serif font-medium text-text-primary">Factor Exposure</h3>
            <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">OLS vs SPY + sector-derived</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-4">
            {riskData.factors.map((f) => (
              <FactorBar key={f.name} name={f.name} exposure={f.exposure} status={f.status} detail={f.detail} />
            ))}
          </div>
        </div>

        {/* CTA to Diversify page */}
        <div className="rounded-[10px] bg-[rgba(207,174,98,0.06)] border border-[rgba(207,174,98,0.25)] p-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                <Target className="w-5 h-5 text-accent" strokeWidth={1.5} />
              </div>
              <div>
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="w-1.5 h-1.5 bg-accent rotate-45 shrink-0" />
                  <h4 className="text-[15px] font-serif font-medium text-text-primary">Reduce your risk with 3 simple changes</h4>
                </div>
                <p className="text-[11px] text-text-tertiary">See specific ETF suggestions and before/after crash simulations</p>
              </div>
            </div>
            <Link
              to="/diversify"
              className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-all press-scale shrink-0"
            >
              Diversify
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </div>
      )}
    </div>
  )
}
