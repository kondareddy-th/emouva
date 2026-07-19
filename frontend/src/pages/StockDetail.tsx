import { useState } from 'react'
import { useParams, useSearchParams, Link } from 'react-router-dom'
import clsx from 'clsx'
import {
  ArrowLeft,
  TrendingUp,
  TrendingDown,
  ShieldCheck,
  AlertTriangle,
  BarChart3,
  Newspaper,
  Target,
  Search,
  ExternalLink,
  MessageCircle,
  Info,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from 'recharts'
import { useStockMetrics } from '../hooks/useStockMetrics'
import KeyStatsPanel from '../components/KeyStatsPanel'
import { formatCurrency, formatPercent, getChangeColor } from '../data/mockData'
import { ValuationGauge } from '../components/shared/ValuationGauge'
import { SentimentBar } from '../components/shared/SentimentBar'
import { FreshnessBadge } from '../components/shared/FreshnessBadge'

// ── Helpers ──────────────────────────────────────────────────────

function StockLogo({ symbol }: { symbol: string }) {
  const [src, setSrc] = useState(
    `https://financialmodelingprep.com/image-stock/${symbol}.png`
  )
  const [fallbackLevel, setFallbackLevel] = useState(0)

  const handleError = () => {
    if (fallbackLevel === 0) {
      setSrc(`https://assets.parqet.com/logos/symbol/${symbol}?format=svg`)
      setFallbackLevel(1)
    } else {
      setFallbackLevel(2)
    }
  }

  if (fallbackLevel === 2) {
    return (
      <div className="w-10 h-10 rounded-[10px] bg-surface-3 border border-[rgba(180,220,190,0.12)] flex items-center justify-center text-[13px] font-mono font-medium text-text-secondary">
        {symbol.slice(0, 2)}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={symbol}
      className="w-10 h-10 rounded-[10px] bg-surface-3 border border-[rgba(180,220,190,0.12)] object-contain"
      onError={handleError}
    />
  )
}

function SectionCard({
  title,
  icon: Icon,
  badge,
  children,
  missing,
  ticker,
}: {
  title: string
  icon: React.ElementType
  badge?: React.ReactNode
  children: React.ReactNode
  missing?: boolean
  ticker?: string
}) {
  if (missing) {
    return (
      <div className="bg-surface-2 rounded-[10px] border border-[rgba(180,220,190,0.12)] p-6">
        <div className="flex items-center gap-2 mb-3">
          <Icon className="w-3.5 h-3.5 text-text-tertiary" strokeWidth={1.5} />
          <h3 className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">{title}</h3>
        </div>
        <div className="flex flex-col items-center gap-3 py-6">
          <p className="text-[13px] text-text-tertiary">No cached data available</p>
          {ticker && (
            <Link
              to={`/research?ticker=${ticker}`}
              className="text-[12px] text-accent hover:text-accent-hover font-medium flex items-center gap-1 transition-colors"
            >
              <Search className="w-3 h-3" strokeWidth={1.5} />
              Run AI Research to populate
            </Link>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="bg-surface-2 rounded-[10px] border border-[rgba(180,220,190,0.12)] p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Icon className="w-3.5 h-3.5 text-text-tertiary" strokeWidth={1.5} />
          <h3 className="font-serif text-[16px] font-medium text-text-primary tracking-[-0.006em]">{title}</h3>
        </div>
        {badge}
      </div>
      {children}
    </div>
  )
}

function MetricRow({ label, value, sub }: { label: string; value: React.ReactNode; sub?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[rgba(180,220,190,0.06)] last:border-0">
      <span className="text-[13px] text-text-secondary">{label}</span>
      <div className="text-right">
        <span className="text-[13px] font-mono font-medium font-tabular text-text-primary">{value}</span>
        {sub && <div className="text-[11px] font-mono text-text-tertiary">{sub}</div>}
      </div>
    </div>
  )
}

// ── Type helpers for cache data ──────────────────────────────────

type AnyData = Record<string, unknown> | unknown[] | null | undefined

function asRecord(data: AnyData): Record<string, unknown> {
  if (data && typeof data === 'object' && !Array.isArray(data)) return data
  return {}
}

function asArray(data: AnyData): Record<string, unknown>[] {
  if (Array.isArray(data)) return data as Record<string, unknown>[]
  return []
}

function num(val: unknown): number | null {
  if (typeof val === 'number' && !isNaN(val)) return val
  return null
}

function str(val: unknown): string {
  if (typeof val === 'string') return val
  return ''
}

function pct(val: unknown): string {
  const n = num(val)
  if (n === null) return '—'
  return `${(n * 100).toFixed(1)}%`
}

function fmtLarge(val: unknown): string {
  const n = num(val)
  if (n === null) return '—'
  if (Math.abs(n) >= 1e12) return `$${(n / 1e12).toFixed(2)}T`
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`
  return formatCurrency(n)
}

function ratio(val: unknown): string {
  const n = num(val)
  if (n === null) return '—'
  return n.toFixed(2)
}

// ── Main Page ────────────────────────────────────────────────────

export default function StockDetail() {
  const { ticker: rawTicker } = useParams<{ ticker: string }>()
  const [searchParams] = useSearchParams()
  const ticker = (rawTicker ?? '').toUpperCase()

  const shares = parseFloat(searchParams.get('shares') ?? '0')
  const costBasis = parseFloat(searchParams.get('cost_basis') ?? '0')

  const { cache, loading } = useStockMetrics(ticker)

  if (!ticker) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <p className="text-text-tertiary">No ticker specified</p>
      </div>
    )
  }

  // Extract data from cache fields
  const marketData = asRecord(cache?.fields?.market_data?.data)
  const companyInfo = asRecord(cache?.fields?.company_info?.data)
  const earningsData = asRecord(cache?.fields?.earnings?.data)
  const newsData = asArray(cache?.fields?.news?.data)
  const aiAnalysis = asRecord(cache?.fields?.ai_analysis?.data)
  const aiBearCase = asRecord(cache?.fields?.ai_bear_case?.data)
  const aiSentiment = asRecord(cache?.fields?.ai_sentiment?.data)

  // Derived values
  const currentPrice = num(marketData.current_price) ?? num(companyInfo.current_price) ?? 0
  const previousClose = num(marketData.previous_close) ?? 0
  const dayChange = previousClose > 0 ? currentPrice - previousClose : 0
  const dayChangePct = previousClose > 0 ? (dayChange / previousClose) * 100 : 0
  const companyName = str(companyInfo.name) || ticker
  const sector = str(companyInfo.sector) || '—'
  const industry = str(companyInfo.industry) || '—'

  // Position P&L
  const hasPosition = shares > 0 && costBasis > 0
  const marketValue = shares * currentPrice
  const totalCost = shares * costBasis
  const totalGain = marketValue - totalCost
  const totalGainPct = totalCost > 0 ? (totalGain / totalCost) * 100 : 0

  // Valuation
  const valuation = asRecord(aiAnalysis.valuation as AnyData)
  const fairBear = num(valuation.bear)
  const fairBase = num(valuation.base)
  const fairBull = num(valuation.bull)
  const hasValuation = fairBear !== null && fairBase !== null && fairBull !== null

  // Quality
  const qualityScore = asRecord(aiAnalysis.quality_score as AnyData)

  // Earnings
  const quarters = asArray(earningsData.quarters as AnyData)

  // Sentiment
  const sentimentScores = asRecord(aiSentiment.scores as AnyData)

  // Freshness
  const analysisFreshness = cache?.fields?.ai_analysis?.status ?? null
  const sentimentFreshness = cache?.fields?.ai_sentiment?.status ?? null
  const bearCaseFreshness = cache?.fields?.ai_bear_case?.status ?? null

  // Loading skeleton
  if (loading) {
    return (
      <div className="max-w-5xl mx-auto space-y-6 animate-pulse">
        <div className="h-8 w-48 bg-surface-3 rounded-md" />
        <div className="h-32 bg-surface-3 rounded-[10px]" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-48 bg-surface-3 rounded-[10px]" />
          <div className="h-48 bg-surface-3 rounded-[10px]" />
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link
            to="/portfolio"
            className="p-2 rounded-md hover:bg-surface-3 text-text-tertiary hover:text-text-primary transition-all"
          >
            <ArrowLeft className="w-4 h-4" strokeWidth={1.5} />
          </Link>
          <StockLogo symbol={ticker} />
          <div>
            <div className="flex items-baseline gap-3">
              <h1 className="font-mono text-[22px] font-medium text-text-primary tracking-[0.02em] tabular-nums">{ticker}</h1>
              <span className="w-1.5 h-1.5 bg-accent rotate-45 self-center flex-shrink-0" />
              <span className="text-[13px] text-text-secondary">{companyName}</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">{sector}</span>
              <span className="text-text-tertiary text-[10px]">·</span>
              <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">{industry}</span>
            </div>
          </div>
        </div>

        {/* Price + day change */}
        <div className="text-right">
          <div className="font-serif text-[34px] font-medium font-tabular text-text-primary leading-none tracking-[-0.01em]">
            {currentPrice > 0 ? formatCurrency(currentPrice) : '—'}
          </div>
          {currentPrice > 0 && (
            <div className={clsx('text-[13px] font-mono font-medium font-tabular mt-1.5', getChangeColor(dayChange))}>
              {dayChange >= 0 ? '+' : ''}{formatCurrency(Math.abs(dayChange))} ({formatPercent(dayChangePct)})
            </div>
          )}
        </div>
      </div>

      {/* ── Quick Actions ───────────────────────────────────────── */}
      <div className="flex items-center gap-3">
        <Link
          to={`/research?ticker=${ticker}`}
          className="text-[12px] px-3.5 py-1.5 rounded-md bg-accent text-base hover:bg-accent-hover font-medium transition-colors flex items-center gap-1.5"
        >
          <Search className="w-3 h-3" strokeWidth={1.5} />
          Full Analysis
        </Link>
        <Link
          to={`/advisor?ticker=${ticker}`}
          className="text-[12px] px-3.5 py-1.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-secondary hover:text-text-primary hover:border-[rgba(180,220,190,0.25)] font-medium transition-colors flex items-center gap-1.5"
        >
          <MessageCircle className="w-3 h-3" strokeWidth={1.5} />
          Ask Advisor
        </Link>
        {hasPosition && (
          <Link
            to={`/holding-review?ticker=${ticker}&cost_basis=${costBasis.toFixed(2)}&shares=${shares}`}
            className="text-[12px] px-3.5 py-1.5 rounded-md bg-surface-3 border border-[rgba(180,220,190,0.12)] text-text-secondary hover:text-text-primary hover:border-[rgba(180,220,190,0.25)] font-medium transition-colors flex items-center gap-1.5"
          >
            <Target className="w-3 h-3" strokeWidth={1.5} />
            Upgrade Check
          </Link>
        )}
      </div>

      {/* ── Key Statistics & Insights ───────────────────────────── */}
      <div>
        <div className="flex items-center gap-2.5 mb-3">
          <span className="w-1.5 h-1.5 bg-accent rotate-45 flex-shrink-0" />
          <h2 className="font-serif text-[18px] font-medium text-text-primary tracking-[-0.006em]">Key Statistics</h2>
        </div>
        <KeyStatsPanel ticker={ticker} />
      </div>

      {/* ── Section 1: Position Summary ─────────────────────────── */}
      {hasPosition && (
        <SectionCard title="Your Position" icon={BarChart3}>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
            <div>
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Shares</div>
              <div className="font-serif text-[22px] font-medium font-tabular text-text-primary">
                {shares % 1 === 0 ? shares : shares.toFixed(4)}
              </div>
            </div>
            <div>
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Avg Cost</div>
              <div className="font-serif text-[22px] font-medium font-tabular text-text-primary">
                {formatCurrency(costBasis)}
              </div>
            </div>
            <div>
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Market Value</div>
              <div className="font-serif text-[22px] font-medium font-tabular text-text-primary">
                {formatCurrency(marketValue)}
              </div>
            </div>
            <div>
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Total P&L</div>
              <div className={clsx('font-serif text-[22px] font-medium font-tabular', getChangeColor(totalGain))}>
                {totalGain >= 0 ? '+' : ''}{formatCurrency(totalGain)}
              </div>
              <div className={clsx('text-[12px] font-mono font-tabular', getChangeColor(totalGainPct))}>
                {formatPercent(totalGainPct)}
              </div>
            </div>
          </div>
        </SectionCard>
      )}

      {/* ── Two-column grid ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

        {/* ── Section 2: Valuation Check ──────────────────────────── */}
        <SectionCard
          title="Valuation"
          icon={Target}
          badge={<FreshnessBadge freshness={analysisFreshness} />}
          missing={!hasValuation}
          ticker={ticker}
        >
          {hasValuation && (
            <div className="space-y-4">
              <ValuationGauge
                bear={fairBear!}
                base={fairBase!}
                bull={fairBull!}
                current={currentPrice}
              />
              {str(valuation.methodology) && (
                <p className="text-[11px] text-text-tertiary flex items-start gap-1.5 mt-2 leading-relaxed">
                  <Info className="w-3 h-3 mt-0.5 flex-shrink-0 text-text-tertiary" strokeWidth={1.5} />
                  {str(valuation.methodology)}
                </p>
              )}
            </div>
          )}
        </SectionCard>

        {/* ── Section 3: AI Rating + Quick Thesis ─────────────────── */}
        <SectionCard
          title="AI Rating"
          icon={ShieldCheck}
          badge={<FreshnessBadge freshness={analysisFreshness} />}
          missing={cache?.fields?.ai_analysis?.status === 'missing'}
          ticker={ticker}
        >
          <div className="space-y-4">
            {/* Quality scores row */}
            {num(qualityScore.overall) !== null && (
              <div className="flex items-center gap-4">
                <div className="flex items-baseline gap-2">
                  <div className={clsx(
                    'font-serif text-[24px] font-medium font-tabular',
                    num(qualityScore.overall)! >= 7 ? 'text-gain' :
                    num(qualityScore.overall)! >= 4 ? 'text-warning' : 'text-loss'
                  )}>
                    {num(qualityScore.overall)}<span className="text-[15px] text-text-tertiary">/10</span>
                  </div>
                  <span className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">Overall</span>
                </div>
                <div className="flex-1 grid grid-cols-4 gap-2">
                  {['moat', 'management', 'financial_health', 'growth_runway'].map(key => {
                    const val = num(qualityScore[key])
                    const labels: Record<string, string> = {
                      moat: 'Moat', management: 'Mgmt',
                      financial_health: 'Health', growth_runway: 'Growth'
                    }
                    return (
                      <div key={key} className="text-center">
                        <div className={clsx(
                          'font-serif text-[16px] font-medium font-tabular',
                          val !== null && val >= 7 ? 'text-gain' :
                          val !== null && val >= 4 ? 'text-warning' : 'text-loss'
                        )}>
                          {val ?? '—'}
                        </div>
                        <div className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mt-0.5">{labels[key]}</div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Executive summary / thesis */}
            {str(aiAnalysis.investment_thesis) && (
              <p className="text-[13px] text-text-secondary leading-relaxed line-clamp-4">
                {str(aiAnalysis.investment_thesis)}
              </p>
            )}

            {/* Sector outlook */}
            {str(aiAnalysis.sector_outlook) && (
              <p className="text-[12px] text-text-tertiary italic">
                {str(aiAnalysis.sector_outlook)}
              </p>
            )}
          </div>
        </SectionCard>

        {/* ── Section 4: Earnings Snapshot ─────────────────────────── */}
        <SectionCard
          title="Earnings"
          icon={BarChart3}
          missing={quarters.length === 0}
          ticker={ticker}
        >
          {quarters.length > 0 && (
            <div className="space-y-3">
              {/* Earnings bar chart */}
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={[...quarters].reverse().slice(-6).map(q => ({
                      quarter: str(q.date).slice(0, 7),
                      eps: num(q.eps),
                      revenue: num(q.revenue),
                    }))}
                    margin={{ top: 5, right: 5, left: -15, bottom: 0 }}
                  >
                    <XAxis
                      dataKey="quarter"
                      tick={{ fill: 'rgba(180,220,190,0.45)', fontSize: 11, fontFamily: "'IBM Plex Mono',monospace" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'rgba(180,220,190,0.45)', fontSize: 11, fontFamily: "'IBM Plex Mono',monospace" }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: '#1A241D',
                        border: '1px solid rgba(180,220,190,0.12)',
                        borderRadius: '8px',
                        fontSize: '12px',
                        fontFamily: "'IBM Plex Mono',monospace",
                        color: '#F7FAF6',
                      }}
                      formatter={(value: number) => [`$${value?.toFixed(2) ?? '—'}`, 'EPS']}
                    />
                    <ReferenceLine y={0} stroke="rgba(180,220,190,0.12)" />
                    <Bar dataKey="eps" radius={[4, 4, 0, 0]} maxBarSize={32}>
                      {[...quarters].reverse().slice(-6).map((_, i) => (
                        <Cell
                          key={i}
                          fill={num([...quarters].reverse().slice(-6)[i]?.eps) !== null &&
                            num([...quarters].reverse().slice(-6)[i]?.eps)! >= 0
                            ? 'rgba(207,174,98,0.7)' : 'rgba(242,147,127,0.7)'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Revenue trend summary */}
              {quarters.length >= 2 && (() => {
                const latest = num(quarters[0]?.revenue)
                const prev = num(quarters[1]?.revenue)
                if (latest && prev && prev > 0) {
                  const revGrowth = ((latest - prev) / prev) * 100
                  return (
                    <div className="flex items-center gap-2 text-[12px] font-mono">
                      {revGrowth >= 0 ? (
                        <TrendingUp className="w-3.5 h-3.5 text-gain" strokeWidth={1.5} />
                      ) : (
                        <TrendingDown className="w-3.5 h-3.5 text-loss" strokeWidth={1.5} />
                      )}
                      <span className="text-text-tertiary uppercase tracking-[0.08em] text-[10px]">QoQ Revenue</span>
                      <span className={clsx('font-tabular', getChangeColor(revGrowth))}>
                        {revGrowth >= 0 ? '+' : ''}{revGrowth.toFixed(1)}%
                      </span>
                      <span className="text-text-tertiary font-tabular">
                        ({fmtLarge(prev)} → {fmtLarge(latest)})
                      </span>
                    </div>
                  )
                }
                return null
              })()}
            </div>
          )}
        </SectionCard>

        {/* ── Section 5: Sentiment + News ──────────────────────────── */}
        <SectionCard
          title="Sentiment & News"
          icon={Newspaper}
          badge={<FreshnessBadge freshness={sentimentFreshness} />}
          missing={cache?.fields?.ai_sentiment?.status === 'missing' && newsData.length === 0}
          ticker={ticker}
        >
          <div className="space-y-4">
            {/* Sentiment bars */}
            {num(sentimentScores.composite) !== null && (
              <div className="space-y-2">
                {num(sentimentScores.news) !== null && (
                  <SentimentBar label="News" value={num(sentimentScores.news)!} />
                )}
                {num(sentimentScores.filings) !== null && (
                  <SentimentBar label="Filings" value={num(sentimentScores.filings)!} />
                )}
                {num(sentimentScores.insider) !== null && (
                  <SentimentBar label="Insider" value={num(sentimentScores.insider)!} />
                )}
                {num(sentimentScores.analyst) !== null && (
                  <SentimentBar label="Analyst" value={num(sentimentScores.analyst)!} />
                )}
                <div className="pt-1 border-t border-[rgba(180,220,190,0.10)]">
                  <SentimentBar label="Overall" value={num(sentimentScores.composite)!} />
                </div>
              </div>
            )}

            {/* Sentiment summary */}
            {str(aiSentiment.summary) && (
              <p className="text-[12px] text-text-secondary leading-relaxed">
                {str(aiSentiment.summary)}
              </p>
            )}

            {/* Recent news */}
            {newsData.length > 0 && (
              <div className="space-y-2 pt-2">
                <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em]">Recent Headlines</div>
                {newsData.slice(0, 4).map((item, i) => (
                  <a
                    key={i}
                    href={str(item.link)}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-start gap-2 py-1.5 group"
                  >
                    <ExternalLink className="w-3 h-3 text-text-tertiary group-hover:text-accent mt-0.5 flex-shrink-0 transition-colors" strokeWidth={1.5} />
                    <div>
                      <div className="text-[13px] text-text-secondary group-hover:text-text-primary transition-colors line-clamp-1">
                        {str(item.title)}
                      </div>
                      <div className="text-[11px] font-mono text-text-tertiary">
                        {str(item.publisher)}
                      </div>
                    </div>
                  </a>
                ))}
              </div>
            )}
          </div>
        </SectionCard>

        {/* ── Section 6: Key Risks ────────────────────────────────── */}
        <SectionCard
          title="Key Risks"
          icon={AlertTriangle}
          badge={<FreshnessBadge freshness={analysisFreshness} />}
          missing={!aiAnalysis.key_risks}
          ticker={ticker}
        >
          {(() => {
            const risks = aiAnalysis.key_risks
            if (!Array.isArray(risks) || risks.length === 0) return null
            return (
              <ul className="space-y-2.5">
                {(risks as string[]).slice(0, 5).map((risk, i) => (
                  <li key={i} className="flex items-start gap-2.5">
                    <span className="w-1.5 h-1.5 bg-accent rotate-45 mt-1.5 flex-shrink-0" />
                    <span className="text-[13px] text-text-secondary leading-relaxed">{risk}</span>
                  </li>
                ))}
              </ul>
            )
          })()}
        </SectionCard>

        {/* ── Section 7: Metrics to Watch ─────────────────────────── */}
        <SectionCard
          title="Key Metrics"
          icon={BarChart3}
          missing={cache?.fields?.company_info?.status === 'missing'}
          ticker={ticker}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
            <div>
              <MetricRow label="P/E (TTM)" value={ratio(companyInfo.pe_ratio)} />
              <MetricRow label="Forward P/E" value={ratio(companyInfo.forward_pe)} />
              <MetricRow label="P/S" value={ratio(companyInfo.price_to_sales)} />
              <MetricRow label="PEG" value={ratio(companyInfo.peg_ratio)} />
              <MetricRow label="P/B" value={ratio(companyInfo.price_to_book)} />
              <MetricRow label="EV/EBITDA" value={ratio(companyInfo.enterprise_to_ebitda)} />
            </div>
            <div>
              <MetricRow label="Gross Margin" value={pct(companyInfo.gross_margins)} />
              <MetricRow label="Operating Margin" value={pct(companyInfo.operating_margins)} />
              <MetricRow label="Profit Margin" value={pct(companyInfo.profit_margins)} />
              <MetricRow label="Revenue Growth" value={pct(companyInfo.revenue_growth)} />
              <MetricRow label="Debt/Equity" value={ratio(companyInfo.debt_to_equity)} />
              <MetricRow label="Current Ratio" value={ratio(companyInfo.current_ratio)} />
            </div>
          </div>

          {/* Additional metrics row */}
          <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-[rgba(180,220,190,0.10)]">
            <div className="text-center">
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Market Cap</div>
              <div className="font-serif text-[16px] font-medium font-tabular text-text-primary">{fmtLarge(companyInfo.market_cap)}</div>
            </div>
            <div className="text-center">
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">52W Range</div>
              <div className="font-mono text-[13px] font-tabular text-text-primary">
                {num(companyInfo.fifty_two_week_low) !== null
                  ? `$${num(companyInfo.fifty_two_week_low)!.toFixed(0)} – $${num(companyInfo.fifty_two_week_high)?.toFixed(0) ?? '—'}`
                  : '—'}
              </div>
            </div>
            <div className="text-center">
              <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Dividend Yield</div>
              <div className="font-serif text-[16px] font-medium font-tabular text-text-primary">
                {num(companyInfo.dividend_yield) !== null
                  ? `${(num(companyInfo.dividend_yield)! * 100).toFixed(2)}%`
                  : '—'}
              </div>
            </div>
          </div>
        </SectionCard>

        {/* ── Section 8: Bear Case ────────────────────────────────── */}
        <SectionCard
          title="Bear Case"
          icon={TrendingDown}
          badge={<FreshnessBadge freshness={bearCaseFreshness} />}
          missing={cache?.fields?.ai_bear_case?.status === 'missing'}
          ticker={ticker}
        >
          <div className="space-y-4">
            {/* Scenario headline */}
            {str(aiBearCase.scenario_name) && (
              <div className="flex items-center gap-2.5">
                <span className="w-1.5 h-1.5 bg-loss rotate-45 flex-shrink-0" />
                <span className="text-[13px] font-medium text-loss">{str(aiBearCase.scenario_name)}</span>
                {num(aiBearCase.estimated_impact_pct) !== null && (
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-loss/10 border border-[rgba(242,147,127,0.3)] text-loss font-mono font-tabular font-medium">
                    {num(aiBearCase.estimated_impact_pct)! > 0 ? '+' : ''}{num(aiBearCase.estimated_impact_pct)}%
                  </span>
                )}
              </div>
            )}

            {/* Stressed price + dollar impact */}
            {num(aiBearCase.stressed_price) !== null && hasPosition && (
              <div className="bg-base rounded-[10px] border border-[rgba(180,220,190,0.10)] p-4 flex items-center justify-between">
                <div>
                  <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Worst-Case Price</div>
                  <div className="font-serif text-[22px] font-medium font-tabular text-loss">
                    {formatCurrency(num(aiBearCase.stressed_price)!)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Your Dollar Impact</div>
                  <div className="font-serif text-[22px] font-medium font-tabular text-loss">
                    {formatCurrency((num(aiBearCase.stressed_price)! - currentPrice) * shares)}
                  </div>
                </div>
              </div>
            )}

            {num(aiBearCase.stressed_price) !== null && !hasPosition && (
              <div className="bg-base rounded-[10px] border border-[rgba(180,220,190,0.10)] p-4">
                <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1">Worst-Case Price Target</div>
                <div className="font-serif text-[22px] font-medium font-tabular text-loss">
                  {formatCurrency(num(aiBearCase.stressed_price)!)}
                  <span className="text-[13px] font-mono text-text-tertiary ml-2">
                    vs current {formatCurrency(currentPrice)}
                  </span>
                </div>
              </div>
            )}

            {/* Bear case details */}
            {str(aiBearCase.competitive_threats) && (
              <div>
                <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Competitive Threats</div>
                <p className="text-[13px] text-text-secondary leading-relaxed">{str(aiBearCase.competitive_threats)}</p>
              </div>
            )}
            {str(aiBearCase.financial_risks) && (
              <div>
                <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Financial Risks</div>
                <p className="text-[13px] text-text-secondary leading-relaxed">{str(aiBearCase.financial_risks)}</p>
              </div>
            )}
            {str(aiBearCase.secular_headwinds) && (
              <div>
                <div className="font-mono text-[10px] text-text-tertiary uppercase tracking-[0.13em] mb-1.5">Secular Headwinds</div>
                <p className="text-[13px] text-text-secondary leading-relaxed">{str(aiBearCase.secular_headwinds)}</p>
              </div>
            )}
          </div>
        </SectionCard>

        {/* ── Section 9: Portfolio Context ─────────────────────────── */}
        <SectionCard
          title="Portfolio Context"
          icon={Target}
          missing={!hasPosition && cache?.fields?.company_info?.status === 'missing'}
          ticker={ticker}
        >
          <div className="space-y-3">
            <MetricRow label="Sector" value={sector} />
            <MetricRow label="Industry" value={industry} />
            <MetricRow label="Beta" value={num(companyInfo.beta) !== null ? ratio(companyInfo.beta) : '—'} />
            {num(companyInfo.recommendation_key) === null && str(companyInfo.recommendation_key) && (
              <MetricRow
                label="Analyst Consensus"
                value={str(companyInfo.recommendation_key).replace(/_/g, ' ').toUpperCase()}
                sub={num(companyInfo.number_of_analysts) !== null
                  ? `${num(companyInfo.number_of_analysts)} analysts`
                  : undefined}
              />
            )}
            {num(companyInfo.target_mean_price) !== null && (
              <MetricRow
                label="Analyst Target"
                value={formatCurrency(num(companyInfo.target_mean_price)!)}
                sub={num(companyInfo.target_low_price) !== null && num(companyInfo.target_high_price) !== null
                  ? `$${num(companyInfo.target_low_price)!.toFixed(0)} – $${num(companyInfo.target_high_price)!.toFixed(0)}`
                  : undefined}
              />
            )}
            {num(companyInfo.held_percent_institutions) !== null && (
              <MetricRow label="Institutional Ownership" value={pct(companyInfo.held_percent_institutions)} />
            )}
            {num(companyInfo.short_percent_of_float) !== null && (
              <MetricRow label="Short % of Float" value={pct(companyInfo.short_percent_of_float)} />
            )}
          </div>
        </SectionCard>
      </div>
    </div>
  )
}
