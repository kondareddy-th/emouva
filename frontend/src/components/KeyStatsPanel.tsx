import clsx from 'clsx'
import { useKeyStats, type KeyStatItem } from '../hooks/useKeyStats'
import Sparkline from './Sparkline'
import PeerComparison from './PeerComparison'

const TONE: Record<string, string> = {
  good: 'text-gain',
  bad: 'text-loss',
  warn: 'text-warning',
  neutral: 'text-text-primary',
}

const scoreColor = (v: number) => (v >= 70 ? 'text-gain' : v >= 45 ? 'text-warning' : 'text-loss')
const scoreBg = (v: number) => (v >= 70 ? 'bg-gain/10' : v >= 45 ? 'bg-warning/10' : 'bg-loss/10')

const SECTIONS: [string, string][] = [
  ['valuation', 'Valuation'],
  ['profitability', 'Profitability'],
  ['growth', 'Growth'],
  ['health', 'Financial Health'],
  ['cashflow', 'Cash Flow & Capital'],
  ['per_share', 'Per Share'],
  ['technicals', 'Technicals'],
  ['ownership', 'Ownership & Short Interest'],
]

function ScoreCard({ label, v, big }: { label: string; v: number; big?: boolean }) {
  return (
    <div className={clsx('rounded-[10px] border border-[rgba(180,220,190,0.12)] p-3 text-center', scoreBg(v))}>
      <div className={clsx('font-serif font-medium font-tabular leading-none', big ? 'text-[30px]' : 'text-[24px]', scoreColor(v))}>{v}</div>
      <div className="text-[10px] uppercase tracking-[0.1em] text-text-tertiary mt-1.5">{label}</div>
    </div>
  )
}

function Metric({ it }: { it: KeyStatItem }) {
  return (
    <div className="flex items-start justify-between py-1.5 gap-3">
      <div className="min-w-0">
        <div className="text-[12.5px] text-text-secondary">{it.label}</div>
        {it.context && <div className="text-[11px] text-text-tertiary truncate">{it.context}</div>}
      </div>
      <div className={clsx('text-[12.5px] font-mono font-tabular whitespace-nowrap', TONE[it.tone] || 'text-text-primary')}>
        {it.value}
      </div>
    </div>
  )
}

function TrendRow({ trends }: { trends: Record<string, number[]> }) {
  const items: [string, number[]][] = [
    ['Revenue (4y)', trends.revenue],
    ['Gross Margin (4y)', trends.gross_margin],
    ['Free Cash Flow (4y)', trends.fcf],
    ['Share Count (4y)', trends.shares],
  ]
  const present = items.filter(([, d]) => d && d.length >= 2)
  if (!present.length) return null
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {present.map(([label, d]) => {
        const up = d[d.length - 1] >= d[0]
        const positive = label.startsWith('Share') ? !up : up // fewer shares = good
        return (
          <div key={label} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-3">
            <div className="text-[10px] uppercase tracking-[0.08em] text-text-tertiary mb-1.5">{label}</div>
            <Sparkline data={d} width={120} height={32} positive={positive} />
          </div>
        )
      })}
    </div>
  )
}

export default function KeyStatsPanel({ ticker }: { ticker: string }) {
  const { data, loading } = useKeyStats(ticker)

  if (loading && !data) {
    return (
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6 text-center">
        <p className="text-[13px] text-text-tertiary font-serif italic">Crunching fundamentals…</p>
      </div>
    )
  }
  if (!data) return null
  const s = data.scores

  return (
    <div className="space-y-5">
      {/* Composite scores */}
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-3">
        <ScoreCard label="Overall" v={s.overall} big />
        <ScoreCard label="Quality" v={s.quality} />
        <ScoreCard label="Health" v={s.health} />
        <ScoreCard label="Growth" v={s.growth} />
        <ScoreCard label="Value" v={s.value} />
      </div>

      {/* Insights */}
      {data.insights.length > 0 && (
        <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4">
          <h3 className="text-[14px] font-serif font-medium text-text-primary mb-2.5">Key Insights</h3>
          <ul className="space-y-2">
            {data.insights.map((t, i) => (
              <li key={i} className="text-[12.5px] text-text-secondary flex gap-2.5 items-start">
                <span className="w-[6px] h-[6px] bg-accent rotate-45 flex-shrink-0 mt-[6px]" />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Multi-year trends */}
      <TrendRow trends={data.trends} />

      {/* Metric sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {SECTIONS.filter(([k]) => data.sections[k]?.length).map(([k, title]) => (
          <div key={k} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4">
            <h3 className="text-[14px] font-serif font-medium text-text-primary mb-1.5">{title}</h3>
            <div className="divide-y divide-[rgba(180,220,190,0.10)]">
              {data.sections[k].map((it, i) => (
                <Metric key={i} it={it} />
              ))}
            </div>
          </div>
        ))}
        {data.dividend && (
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4">
            <h3 className="text-[14px] font-serif font-medium text-text-primary mb-1.5">Dividend</h3>
            <div className="divide-y divide-[rgba(180,220,190,0.10)]">
              <Metric it={{ label: 'Yield', value: data.dividend.yield, context: '', tone: 'good' }} />
              <Metric it={{ label: 'Annual Rate', value: data.dividend.rate, context: '', tone: 'neutral' }} />
              <Metric it={{ label: 'Payout Ratio', value: data.dividend.payout_ratio, context: 'earnings paid out', tone: 'neutral' }} />
            </div>
          </div>
        )}
      </div>

      {/* Sector / industry peer comparison */}
      <PeerComparison ticker={data.symbol} />

      <p className="text-[11px] text-text-tertiary text-center font-serif italic">
        Fundamentals via yfinance · live price fetched per request · scores & insights computed in-house
      </p>
    </div>
  )
}
