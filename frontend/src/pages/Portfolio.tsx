import { useMemo } from 'react'
import { Download, Filter, Link2, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import PositionsTable from '../components/PositionsTable'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'
import ModeToggle from '../components/ModeToggle'
import { formatCurrency, formatPercent } from '../data/mockData'
import { usePositions, usePortfolioSummary, useRiskData } from '../hooks/usePortfolio'
import { usePortfolioMetrics } from '../hooks/usePortfolioMetrics'

function PortfolioSkeleton() {
  return (
    <div className="px-4 md:px-8 py-8 animate-pulse">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 h-[80px]">
            <div className="h-3 w-20 bg-surface-3 rounded mb-3" />
            <div className="h-6 w-28 bg-surface-3 rounded" />
          </div>
        ))}
      </div>
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 mb-8 h-[80px]">
        <div className="h-4 w-36 bg-surface-3 rounded mb-4" />
        <div className="h-2 bg-surface-3/50 rounded-full" />
      </div>
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
        <div className="h-4 w-28 bg-surface-3 rounded mb-4" />
        {[...Array(6)].map((_, i) => (
          <div key={i} className="flex items-center gap-4 py-3 border-b border-[rgba(180,220,190,0.06)]">
            <div className="h-4 w-12 bg-surface-3 rounded" />
            <div className="h-4 w-32 bg-surface-3 rounded flex-1" />
            <div className="h-4 w-20 bg-surface-3 rounded" />
            <div className="h-4 w-16 bg-surface-3 rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Portfolio() {
  const { data: positions, source, loading } = usePositions()
  const { data: summary, loading: summaryLoading } = usePortfolioSummary()
  const { data: riskData } = useRiskData()  // for resolved sector allocation
  const isDisconnected = source === 'disconnected' && !loading && positions.length === 0
  const isLoading = loading || summaryLoading

  // Fetch cached AI metrics for all portfolio tickers
  const tickerList = useMemo(() => positions.map(p => p.symbol), [positions])
  const { metrics } = usePortfolioMetrics(tickerList)

  const totalInvested = positions.reduce((sum, p) => sum + p.shares * p.avgCost, 0)
  const totalCurrent = positions.reduce((sum, p) => sum + p.shares * p.currentPrice, 0)
  const totalGain = totalCurrent - totalInvested
  const totalGainPct = totalInvested > 0 ? (totalGain / totalInvested) * 100 : 0

  // Sector breakdown — prefer the risk engine's resolved sectors (MCP positions
  // carry only "Unknown"); fall back to the positions map until risk data loads.
  const sectors = riskData.sectorWeights.length > 0
    ? riskData.sectorWeights
        .map((s) => ({ name: s.sector, value: s.value, pct: totalCurrent > 0 ? (s.value / totalCurrent) * 100 : s.weight }))
        .sort((a, b) => b.value - a.value)
    : Array.from(
        positions.reduce((m, p) => {
          const val = p.shares * p.currentPrice
          return m.set(p.sector, (m.get(p.sector) || 0) + val)
        }, new Map<string, number>()).entries()
      )
        .sort((a, b) => b[1] - a[1])
        .map(([name, value]) => ({ name, value, pct: (value / totalCurrent) * 100 }))

  const SECTOR_PALETTE = [
    'bg-[#CFAE62]', 'bg-[#95814D]', 'bg-[#E9D6A2]', 'bg-[#85BFC9]',
    'bg-[#85BFC9]', 'bg-[#BD9F58]', 'bg-[#95814D]', 'bg-[#DFB65A]',
    'bg-[#DFB65A]', 'bg-[#F2937F]', 'bg-[#746540]', 'bg-[#564B31]',
  ]

  const sectorColors: Record<string, string> = {
    'Technology Services': 'bg-[#CFAE62]',
    'Electronic Technology': 'bg-[#95814D]',
    Technology: 'bg-[#CFAE62]',
    ETF: 'bg-[#746540]',
    Commodities: 'bg-[#DFB65A]',
    Utilities: 'bg-[#85BFC9]',
    Defense: 'bg-[#F2937F]',
    'Retail Trade': 'bg-[#BD9F58]',
    Miscellaneous: 'bg-[#E9D6A2]',
    'Health Technology': 'bg-[#95814D]',
    Finance: 'bg-[#95814D]',
    'Producer Manufacturing': 'bg-[#DFB65A]',
    'Consumer Services': 'bg-[#85BFC9]',
    'Energy Minerals': 'bg-[#DFB65A]',
    'Health Services': 'bg-[#95814D]',
    'Consumer Non-Durables': 'bg-[#746540]',
    'Consumer Durables': 'bg-[#E9D6A2]',
    Transportation: 'bg-[#95814D]',
    Communications: 'bg-[#85BFC9]',
    'Industrial Services': 'bg-[#DFB65A]',
    'Process Industries': 'bg-[#DFB65A]',
    'Distribution Services': 'bg-[#95814D]',
    'Commercial Services': 'bg-[#BD9F58]',
    'Non-Energy Minerals': 'bg-[#E9D6A2]',
    Unknown: 'bg-[#564B31]',
  }

  const getSectorColor = (name: string, index: number) =>
    sectorColors[name] || SECTOR_PALETTE[index % SECTOR_PALETTE.length]

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-base/80 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-4 md:px-8 h-14">
          <div className="flex items-center gap-2.5">
            <div className="w-1.5 h-1.5 bg-accent rotate-45" />
            <h1 className="text-[19px] font-serif font-medium tracking-tight text-text-primary">Portfolio</h1>
          </div>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            <SyncButton />
            <NotificationsBell />
            {!isLoading && !isDisconnected && (
              <>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-secondary text-[12px] font-mono hover:border-[rgba(180,220,190,0.30)] hover:text-text-primary transition-colors press-scale">
                  <Filter className="w-3 h-3 text-text-tertiary" strokeWidth={1.5} />
                  Filter
                </button>
                <button className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-secondary text-[12px] font-mono hover:border-[rgba(180,220,190,0.30)] hover:text-text-primary transition-colors press-scale">
                  <Download className="w-3 h-3 text-text-tertiary" strokeWidth={1.5} />
                  Export
                </button>
              </>
            )}
          </div>
        </div>
        <div className="header-gradient-line" />
      </div>

      {isLoading ? (
        <PortfolioSkeleton />
      ) : isDisconnected ? (
        <div className="px-4 md:px-8 py-12 max-w-lg mx-auto text-center">
          <div className="w-14 h-14 rounded-[10px] bg-accent/10 border border-[rgba(180,220,190,0.12)] flex items-center justify-center mx-auto mb-5">
            <Link2 className="w-6 h-6 text-accent" strokeWidth={1.5} />
          </div>
          <h2 className="text-[24px] font-serif font-medium text-text-primary mb-2">Connect Your Portfolio</h2>
          <p className="text-[14px] text-text-secondary mb-6 leading-relaxed">
            Link your Robinhood account to see your positions, returns, and sector allocation.
          </p>
          <Link
            to="/settings"
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-md bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-all press-scale"
          >
            Connect Account
            <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
          </Link>
        </div>
      ) : (
      <div className="px-4 md:px-8 py-8">
        {/* Summary — stat cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8 stagger">
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
            <p className="font-mono text-[10px] tracking-[0.13em] uppercase text-text-tertiary mb-2">Total Value</p>
            <p className="text-[28px] leading-none font-serif font-medium font-tabular text-text-primary tracking-tight">{formatCurrency(totalCurrent)}</p>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
            <p className="font-mono text-[10px] tracking-[0.13em] uppercase text-text-tertiary mb-2">Cost Basis</p>
            <p className="text-[28px] leading-none font-serif font-medium font-tabular text-text-secondary tracking-tight">{formatCurrency(totalInvested)}</p>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
            <p className="font-mono text-[10px] tracking-[0.13em] uppercase text-text-tertiary mb-2">Total Return</p>
            <p className={`text-[28px] leading-none font-serif font-medium font-tabular tracking-tight ${totalGainPct >= 0 ? 'text-gain' : 'text-loss'}`}>{formatPercent(totalGainPct)}</p>
            <p className={`text-[12px] font-mono font-tabular mt-1.5 ${totalGain >= 0 ? 'text-gain/70' : 'text-loss/70'}`}>{totalGain >= 0 ? '+' : ''}{formatCurrency(totalGain)}</p>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
            <p className="font-mono text-[10px] tracking-[0.13em] uppercase text-text-tertiary mb-2">Positions</p>
            <p className="text-[28px] leading-none font-serif font-medium font-tabular text-text-primary tracking-tight">{positions.length}</p>
            <p className="text-[12px] font-mono text-text-tertiary mt-1.5">{sectors.length} sectors</p>
          </div>
        </div>

        {/* Sector Breakdown */}
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 mb-8">
          <div className="flex items-center gap-2.5 mb-4">
            <div className="w-1.5 h-1.5 bg-accent rotate-45" />
            <h3 className="text-[16px] font-serif font-medium text-text-primary">Sector Allocation</h3>
          </div>
          <div className="h-1.5 rounded-full overflow-hidden flex mb-5 bg-[rgba(255,255,255,0.04)]">
            {sectors.map((s, i) => (
              <div
                key={s.name}
                className={`${getSectorColor(s.name, i)} transition-all`}
                style={{ width: `${s.pct}%` }}
              />
            ))}
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2.5">
            {sectors.map((s, i) => (
              <div key={s.name} className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rotate-45 ${getSectorColor(s.name, i)}`} />
                <span className="text-[12px] text-text-secondary">{s.name}</span>
                <span className="text-[12px] text-text-primary font-mono font-tabular">{s.pct.toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Full Positions Table */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2.5">
              <div className="w-1.5 h-1.5 bg-accent rotate-45" />
              <h3 className="text-[16px] font-serif font-medium text-text-primary">All Positions</h3>
            </div>
            <span className="font-mono text-[11px] text-text-tertiary tabular-nums">{positions.length} holdings</span>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
            <PositionsTable positions={positions} metrics={metrics} />
          </div>
        </div>
      </div>
      )}
    </div>
  )
}
