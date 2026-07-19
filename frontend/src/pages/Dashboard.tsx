import {
  Search,
  ChevronRight,
  Wallet,
  Activity,
  ShieldCheck,
  Link2,
  Sparkles,
  BarChart3,
  MessageCircle,
  ArrowRight,
  TrendingUp,
} from 'lucide-react'
import clsx from 'clsx'
import PositionsTable from '../components/PositionsTable'
import DailyBrief from '../components/DailyBrief'
import WatchlistPanel from '../components/WatchlistPanel'
import SyncButton from '../components/SyncButton'
import AccountSwitcher from '../components/AccountSwitcher'
import ModeToggle from '../components/ModeToggle'
import { formatCurrency } from '../data/mockData'
import { Link } from 'react-router-dom'
import { usePortfolioSummary, usePositions } from '../hooks/usePortfolio'
import { useWatchlistStore } from '../hooks/useWatchlistStore'
import NewsFeed from '../components/NewsFeed'
import NotificationsBell from '../components/Notifications'

function getGreeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 17) return 'Good afternoon'
  return 'Good evening'
}

function DashboardSkeleton() {
  return (
    <div className="min-h-screen">
      <div className="sticky top-0 z-30 bg-base/90 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-4 md:px-8 h-14">
          <div className="h-5 w-40 bg-surface-3 rounded animate-pulse" />
        </div>
        <div className="header-gradient-line" />
      </div>
      <div className="px-4 md:px-8 py-6 animate-pulse">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 h-[80px]">
              <div className="h-3 w-20 bg-surface-3 rounded mb-3" />
              <div className="h-6 w-28 bg-surface-3 rounded" />
            </div>
          ))}
        </div>
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 h-[280px] mb-6">
          <div className="h-4 w-32 bg-surface-3 rounded mb-4" />
          <div className="h-[200px] bg-surface-3/50 rounded" />
        </div>
      </div>
    </div>
  )
}

export default function Dashboard() {
  const { data: summary, source, loading: summaryLoading } = usePortfolioSummary()
  const { data: positions, loading: positionsLoading } = usePositions()
  // Our own watchlist (curated from AI Research), not Robinhood's.
  const { items: watchlistEntries } = useWatchlistStore()
  const watchlist = watchlistEntries.map((e) => ({
    symbol: e.symbol, name: e.name, price: e.lastPrice,
    change: 0, changePct: 0, aiScore: 0,
  }))
  const isConnected = source === 'robinhood'
  const isInitialLoad = summaryLoading && positionsLoading && positions.length === 0
  const isDisconnected = source === 'disconnected' && !summaryLoading && positions.length === 0

  // Loading state — show skeleton while initial data loads
  if (isInitialLoad) {
    return <DashboardSkeleton />
  }

  // Disconnected onboarding state
  if (isDisconnected) {
    return (
      <div className="min-h-screen">
        {/* Top bar */}
        <div className="sticky top-0 z-30 bg-base/90 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
          <div className="flex items-center justify-between px-4 md:px-8 h-14">
            <h1 className="font-serif text-[19px] font-medium text-text-primary tracking-tight">
              {getGreeting()}
            </h1>
            <NotificationsBell />
          </div>
          <div className="header-gradient-line" />
        </div>

        <div className="px-4 md:px-8 py-8 md:py-10 max-w-4xl mx-auto">
          {/* Hero welcome */}
          <div className="text-center mb-10 animate-fade-in">
            <div className="w-16 h-16 rounded-2xl bg-accent/10 border border-[rgba(180,220,190,0.14)] flex items-center justify-center mx-auto mb-5">
              <div className="w-4 h-4 bg-accent rotate-45" />
            </div>
            <h2 className="font-serif text-[30px] font-medium text-text-primary tracking-tight mb-3">
              Welcome to Emouva
            </h2>
            <p className="text-[15px] text-text-secondary max-w-md mx-auto leading-relaxed">
              Connect your Robinhood account to unlock AI-powered portfolio intelligence, risk analysis, and personalized insights.
            </p>
          </div>

          {/* Connect CTA */}
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 md:p-6 mb-8 animate-slide-up">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className="w-11 h-11 rounded-[8px] bg-accent/10 border border-[rgba(180,220,190,0.12)] flex items-center justify-center flex-shrink-0">
                  <Link2 className="w-5 h-5 text-text-tertiary" strokeWidth={1.25} />
                </div>
                <div>
                  <h3 className="text-[15px] font-semibold text-text-primary mb-0.5">Connect Robinhood</h3>
                  <p className="text-[13px] text-text-tertiary">Link your brokerage to see positions, P&L, and AI insights</p>
                </div>
              </div>
              <Link
                to="/settings"
                className="flex items-center gap-2 px-5 py-2.5 rounded-[6px] bg-accent hover:bg-accent-hover text-base text-[13px] font-medium transition-colors press-scale flex-shrink-0"
              >
                Get Started
                <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
              </Link>
            </div>
          </div>

          {/* Feature preview cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8 stagger">
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 card-hover">
              <div className="w-9 h-9 rounded-[8px] bg-surface-3 border border-[rgba(180,220,190,0.10)] flex items-center justify-center mb-3">
                <TrendingUp className="w-4 h-4 text-text-tertiary" strokeWidth={1.25} />
              </div>
              <h4 className="text-[14px] font-medium text-text-primary mb-1">Portfolio Tracking</h4>
              <p className="text-[12px] text-text-tertiary leading-relaxed">
                Positions, daily P&L, portfolio chart with 1D to 1Y ranges, and performance tracking.
              </p>
            </div>
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 card-hover">
              <div className="w-9 h-9 rounded-[8px] bg-surface-3 border border-[rgba(180,220,190,0.10)] flex items-center justify-center mb-3">
                <ShieldCheck className="w-4 h-4 text-text-tertiary" strokeWidth={1.25} />
              </div>
              <h4 className="text-[14px] font-medium text-text-primary mb-1">Risk Intelligence</h4>
              <p className="text-[12px] text-text-tertiary leading-relaxed">
                Concentration risk scoring, stress tests, correlation alerts, and drawdown analysis.
              </p>
            </div>
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 card-hover">
              <div className="w-9 h-9 rounded-[8px] bg-surface-3 border border-[rgba(180,220,190,0.10)] flex items-center justify-center mb-3">
                <BarChart3 className="w-4 h-4 text-text-tertiary" strokeWidth={1.25} />
              </div>
              <h4 className="text-[14px] font-medium text-text-primary mb-1">Daily Brief</h4>
              <p className="text-[12px] text-text-tertiary leading-relaxed">
                AI-generated daily market brief covering your holdings, sector trends, and actionable insights.
              </p>
            </div>
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 card-hover">
              <div className="w-9 h-9 rounded-[8px] bg-surface-3 border border-[rgba(180,220,190,0.10)] flex items-center justify-center mb-3">
                <MessageCircle className="w-4 h-4 text-text-tertiary" strokeWidth={1.25} />
              </div>
              <h4 className="text-[14px] font-medium text-text-primary mb-1">AI Advisor</h4>
              <p className="text-[12px] text-text-tertiary leading-relaxed">
                Ask anything about your portfolio, get rebalancing suggestions, and explore "what if" scenarios.
              </p>
            </div>
          </div>

          {/* Quick actions that work without brokerage */}
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
            <h3 className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-4">Available now — no brokerage needed</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <Link
                to="/research"
                className="flex items-center gap-3 p-4 rounded-[8px] bg-base border border-[rgba(180,220,190,0.06)] hover:border-[rgba(180,220,190,0.20)] transition-colors group"
              >
                <Search className="w-4 h-4 text-text-tertiary group-hover:text-accent transition-colors" strokeWidth={1.25} />
                <div>
                  <p className="text-[13px] font-medium text-text-primary group-hover:text-accent transition-colors">AI Stock Research</p>
                  <p className="text-[11px] text-text-tertiary">Analyze any ticker with AI</p>
                </div>
              </Link>
              <Link
                to="/advisor"
                className="flex items-center gap-3 p-4 rounded-[8px] bg-base border border-[rgba(180,220,190,0.06)] hover:border-[rgba(180,220,190,0.20)] transition-colors group"
              >
                <MessageCircle className="w-4 h-4 text-text-tertiary group-hover:text-accent transition-colors" strokeWidth={1.25} />
                <div>
                  <p className="text-[13px] font-medium text-text-primary group-hover:text-accent transition-colors">AI Advisor</p>
                  <p className="text-[11px] text-text-tertiary">Ask investment questions</p>
                </div>
              </Link>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-base/90 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-4 md:px-8 h-14">
          <h1 className="font-serif text-[19px] font-medium text-text-primary tracking-tight">
            {getGreeting()}
          </h1>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            <AccountSwitcher />
            <SyncButton />
            <NotificationsBell />
            <Link
              to="/research"
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-[6px] bg-accent/10 text-accent text-[13px] font-medium hover:bg-accent/20 transition-colors press-scale border border-[rgba(180,220,190,0.20)]"
            >
              <Search className="w-3.5 h-3.5" strokeWidth={1.5} />
              Analyze Stock
            </Link>
          </div>
        </div>
        <div className="header-gradient-line" />
      </div>

      <div className="flex flex-col lg:flex-row">
        {/* Main Content */}
        <div className="flex-1 px-4 md:px-8 py-6 md:py-8 min-w-0">
          {/* Portfolio value + today's change — a predictable, always-correct readout (like
              Robinhood), replacing the chart. Same live data source as Buying Power below. */}
          <div className="mb-6 md:mb-8 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 md:p-6">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-1.5 h-1.5 bg-accent rotate-45" />
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Portfolio Value</p>
              {isConnected && (
                <span className="ml-auto flex items-center gap-1.5 text-[10px] font-mono text-text-tertiary">
                  <span className="w-1.5 h-1.5 rounded-full bg-gain animate-pulse" /> LIVE
                </span>
              )}
            </div>
            <p className="font-serif text-[36px] md:text-[42px] font-medium font-tabular text-text-primary leading-none">
              {formatCurrency(summary.totalValue)}
            </p>
            <div className="flex items-baseline gap-2 mt-3">
              <span className={clsx(
                'font-mono text-[15px] font-tabular font-medium',
                summary.dailyChange >= 0 ? 'text-gain' : 'text-loss',
              )}>
                {summary.dailyChange >= 0 ? '▲' : '▼'} {formatCurrency(Math.abs(summary.dailyChange))}
                {' ('}{summary.dailyChange >= 0 ? '+' : ''}{summary.dailyChangePct.toFixed(2)}%{')'}
              </span>
              <span className="font-mono text-[10px] uppercase tracking-[0.10em] text-text-tertiary">today</span>
            </div>
          </div>

          {/* Quick stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4 mb-6 md:mb-8 stagger">
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 card-hover">
              <div className="flex items-center gap-2 mb-2.5">
                <div className="w-1.5 h-1.5 bg-accent rotate-45" />
                <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Buying Power</p>
                <Wallet className="w-3.5 h-3.5 text-text-tertiary ml-auto" strokeWidth={1.25} />
              </div>
              <p className="font-serif text-[26px] font-medium font-tabular text-text-primary">
                {formatCurrency(summary.buyingPower)}
              </p>
            </div>
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 card-hover">
              <div className="flex items-center gap-2 mb-2.5">
                <div className="w-1.5 h-1.5 bg-accent rotate-45" />
                <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Total Return</p>
                <Activity className={clsx(
                  'w-3.5 h-3.5 ml-auto',
                  summary.totalGainPct >= 0 ? 'text-gain/70' : 'text-loss/70'
                )} strokeWidth={1.25} />
              </div>
              <p className={clsx(
                'font-serif text-[26px] font-medium font-tabular',
                summary.totalGainPct >= 0 ? 'text-gain' : 'text-loss'
              )}>
                {summary.totalGainPct >= 0 ? '+' : ''}{summary.totalGainPct.toFixed(1)}%
              </p>
              <p className={clsx(
                'font-mono text-[12px] font-tabular mt-1',
                summary.totalGain >= 0 ? 'text-gain/70' : 'text-loss/70'
              )}>
                {summary.totalGain >= 0 ? '+' : ''}{formatCurrency(summary.totalGain)}
              </p>
              <p className="font-mono text-[10px] uppercase tracking-[0.10em] text-text-tertiary/70 mt-1.5">all-time · since purchase</p>
            </div>
          </div>

          {/* Portfolio Insights */}
          {positions.length > 0 && (
            <div className="mb-8 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
              <div className="flex items-center gap-2.5 mb-4">
                <div className="w-1.5 h-1.5 bg-accent rotate-45" />
                <h2 className="font-serif text-[18px] font-medium text-text-primary tracking-tight">Quick Insights</h2>
                <Sparkles className="w-3.5 h-3.5 text-text-tertiary ml-auto" strokeWidth={1.25} />
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {(() => {
                  const sorted = [...positions].sort((a, b) => {
                    const aChg = ((a.currentPrice - a.previousClose) / a.previousClose) * 100
                    const bChg = ((b.currentPrice - b.previousClose) / b.previousClose) * 100
                    return bChg - aChg
                  })
                  const topMover = sorted[0]
                  const worstMover = sorted[sorted.length - 1]
                  const topMovChg = ((topMover.currentPrice - topMover.previousClose) / topMover.previousClose) * 100
                  const worstMovChg = ((worstMover.currentPrice - worstMover.previousClose) / worstMover.previousClose) * 100

                  const biggest = [...positions].sort((a, b) =>
                    (b.shares * b.currentPrice) - (a.shares * a.currentPrice)
                  )[0]
                  const bigPct = summary.totalValue > 0
                    ? ((biggest.shares * biggest.currentPrice) / summary.totalValue * 100).toFixed(1)
                    : '0'

                  return (
                    <>
                      <div className="p-4 rounded-[8px] bg-base border border-[rgba(180,220,190,0.06)]">
                        <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-2">Top Mover Today</p>
                        <p className="font-mono text-[15px] font-medium text-text-primary">{topMover.symbol}</p>
                        <p className={clsx('font-mono text-[12px] font-tabular mt-0.5', topMovChg >= 0 ? 'text-gain' : 'text-loss')}>
                          {topMovChg >= 0 ? '+' : ''}{topMovChg.toFixed(2)}%
                        </p>
                      </div>
                      <div className="p-4 rounded-[8px] bg-base border border-[rgba(180,220,190,0.06)]">
                        <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-2">Biggest Laggard</p>
                        <p className="font-mono text-[15px] font-medium text-text-primary">{worstMover.symbol}</p>
                        <p className={clsx('font-mono text-[12px] font-tabular mt-0.5', worstMovChg >= 0 ? 'text-gain' : 'text-loss')}>
                          {worstMovChg >= 0 ? '+' : ''}{worstMovChg.toFixed(2)}%
                        </p>
                      </div>
                      <div className="p-4 rounded-[8px] bg-base border border-[rgba(180,220,190,0.06)]">
                        <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-2">Largest Position</p>
                        <p className="font-mono text-[15px] font-medium text-text-primary">{biggest.symbol}</p>
                        <p className="font-mono text-[12px] font-tabular text-accent mt-0.5">{bigPct}% of portfolio</p>
                      </div>
                    </>
                  )
                })()}
              </div>
            </div>
          )}

          {/* Holdings */}
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-1.5 h-1.5 bg-accent rotate-45" />
                <h2 className="font-serif text-[18px] font-medium text-text-primary tracking-tight">Holdings</h2>
              </div>
              <Link
                to="/portfolio"
                className="font-mono text-[11px] uppercase tracking-[0.10em] text-text-tertiary hover:text-accent transition-colors flex items-center gap-1"
              >
                View All
                <ChevronRight className="w-3.5 h-3.5" strokeWidth={1.5} />
              </Link>
            </div>
            <PositionsTable positions={positions} />
          </div>

          {/* Portfolio Analysis — deep research on every holding. Moved to the end
              of the page; DB-cached per account, regenerated only on Refresh. */}
          <div className="mt-6 md:mt-8">
            <DailyBrief />
          </div>
        </div>

        {/* Right Sidebar */}
        <div className="w-full lg:w-[300px] flex-shrink-0 lg:border-l border-t lg:border-t-0 border-[rgba(180,220,190,0.10)] px-4 md:px-5 py-6 md:py-8 space-y-5 lg:sticky lg:top-14 lg:h-[calc(100vh-56px)] lg:overflow-y-auto">
          {/* Watchlist */}
          <WatchlistPanel watchlist={watchlist} />

          {/* News Feed */}
          <NewsFeed />
        </div>
      </div>
    </div>
  )
}
