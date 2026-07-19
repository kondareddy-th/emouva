/**
 * Real Earnings Yield — the market's true return above inflation.
 * Dual-axis chart: Real EY (left, line + shading) overlaid with S&P 500 price (right, area).
 * Green zones = positive REY (good time to invest), Red zones = negative (caution).
 * Dashed line for 1-month forecast via Holt's method.
 */

import { useState, useEffect, useMemo } from 'react'
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ReferenceArea,
} from 'recharts'
import { TrendingUp, TrendingDown, Minus, AlertTriangle, ShieldCheck, Loader2 } from 'lucide-react'
import clsx from 'clsx'
import { apiFetch } from '../../api/client'

interface HistoricalPoint {
  date: string
  sp500: number | null
  earnings_yield: number | null
  cpi_yoy: number | null
  real_ey: number | null
  cape_yield: number | null
  long_rate: number | null
  erp: number | null
}

interface ForecastPoint {
  date: string
  real_ey: number
}

interface CurrentSnapshot {
  earnings_yield: number
  inflation: number
  real_earnings_yield: number
  excess_cape_yield: number | null
  equity_risk_premium: number | null
  treasury_10y: number | null
  sp500_price: number | null
  spy_pe: number | null
  cape: number | null
  signal: 'STRONG_BUY' | 'BUY' | 'HOLD' | 'CAUTION' | 'DANGER'
  signal_description: string
}

interface Stats {
  avg: number
  median: number
  min: number
  max: number
  current: number
  current_percentile: number
  positive_pct: number
  data_points: number
  start_year: number
  end_year: number
}

interface ECYStats {
  avg: number
  median: number
  min: number
  max: number
  current: number
  current_percentile: number
}

interface NasdaqData {
  qqq_pe: number
  spy_pe: number
  relative_pe: number
  qqq_ey: number | null
  interpretation: string
}

interface REYData {
  historical: HistoricalPoint[]
  current: CurrentSnapshot
  forecast: ForecastPoint[]
  stats: Stats
  ecy_stats: ECYStats
  nasdaq: NasdaqData
  error?: string
}

const signalConfig: Record<string, { color: string; bg: string; border: string; icon: typeof TrendingUp; label: string }> = {
  STRONG_BUY: { color: 'text-gain', bg: 'bg-gain/15', border: 'border-gain/30', icon: TrendingUp, label: 'Strong Buy' },
  BUY: { color: 'text-gain', bg: 'bg-gain/10', border: 'border-gain/20', icon: TrendingUp, label: 'Buy' },
  HOLD: { color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/20', icon: Minus, label: 'Hold' },
  CAUTION: { color: 'text-warning', bg: 'bg-warning/10', border: 'border-warning/20', icon: AlertTriangle, label: 'Caution' },
  DANGER: { color: 'text-loss', bg: 'bg-loss/15', border: 'border-loss/30', icon: TrendingDown, label: 'Danger' },
}

const timeRanges = [
  { label: '10Y', years: 10 },
  { label: '20Y', years: 20 },
  { label: '30Y', years: 30 },
  { label: 'All', years: 100 },
]

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Record<string, unknown> }> }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-surface-3 border border-[rgba(180,220,190,0.12)] rounded-[10px] px-3 py-2.5 shadow-xl text-[11px] space-y-1">
      <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">{new Date(d.date as string).toLocaleDateString('en-US', { month: 'short', year: 'numeric' })}</p>
      {d.real_ey != null && (
        <p className={clsx('font-mono tabular-nums', (d.real_ey as number) >= 0 ? 'text-gain' : 'text-loss')}>
          Real EY: {(d.real_ey as number).toFixed(2)}%
        </p>
      )}
      {d.sp500 != null && (
        <p className="text-text-secondary font-mono tabular-nums">S&P 500: ${(d.sp500 as number).toLocaleString('en-US', { maximumFractionDigits: 0 })}</p>
      )}
      {d.erp != null && (
        <p className="text-text-tertiary font-mono tabular-nums">ERP: {(d.erp as number).toFixed(2)}%</p>
      )}
      {d.forecast === true && <p className="text-accent text-[10px]">Forecast</p>}
    </div>
  )
}

export default function RealEarningsYield() {
  const [data, setData] = useState<REYData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeRange, setActiveRange] = useState('All')

  useEffect(() => {
    setLoading(true)
    apiFetch<REYData>('/api/market/real-earnings-yield')
      .then((res) => {
        if (res.error) {
          setError(res.error)
        } else {
          setData(res)
        }
      })
      .catch((err) => setError(err.message || 'Failed to load data'))
      .finally(() => setLoading(false))
  }, [])

  // Filter data by selected time range
  const chartData = useMemo(() => {
    if (!data?.historical) return []

    const range = timeRanges.find((r) => r.label === activeRange)
    const cutoffDate = new Date()
    cutoffDate.setFullYear(cutoffDate.getFullYear() - (range?.years ?? 100))
    const cutoff = cutoffDate.toISOString().slice(0, 10)

    const filtered = data.historical
      .filter((p) => p.date >= cutoff)
      .map((p) => ({
        ...p,
        // Split into positive/negative for area coloring
        real_ey_pos: p.real_ey != null && p.real_ey >= 0 ? p.real_ey : 0,
        real_ey_neg: p.real_ey != null && p.real_ey < 0 ? p.real_ey : 0,
        forecast: false,
      }))

    // Append forecast points
    if (data.forecast?.length) {
      for (const fp of data.forecast) {
        filtered.push({
          date: fp.date,
          sp500: null,
          earnings_yield: null,
          cpi_yoy: null,
          real_ey: fp.real_ey,
          cape_yield: null,
          long_rate: null,
          erp: null,
          real_ey_pos: fp.real_ey >= 0 ? fp.real_ey : 0,
          real_ey_neg: fp.real_ey < 0 ? fp.real_ey : 0,
          forecast: true,
        })
      }
    }

    return filtered
  }, [data, activeRange])

  // Find negative REY zones for red reference areas
  const negativeZones = useMemo(() => {
    if (!chartData.length) return []
    const zones: { start: string; end: string }[] = []
    let zoneStart: string | null = null

    for (const point of chartData) {
      if (point.real_ey != null && point.real_ey < 0) {
        if (!zoneStart) zoneStart = point.date
      } else {
        if (zoneStart) {
          zones.push({ start: zoneStart, end: point.date })
          zoneStart = null
        }
      }
    }
    if (zoneStart) {
      zones.push({ start: zoneStart, end: chartData[chartData.length - 1].date })
    }
    return zones
  }, [chartData])

  if (loading) {
    return (
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center">
            <Loader2 className="w-4.5 h-4.5 text-accent animate-spin" strokeWidth={1.5} />
          </div>
          <div>
            <h3 className="text-[15px] font-serif font-medium text-text-primary">Real Earnings Yield</h3>
            <p className="text-[12px] text-text-tertiary">Loading 60 years of market data...</p>
          </div>
        </div>
        <div className="h-[350px] bg-surface-3/30 rounded-lg animate-pulse" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5">
        <p className="text-[13px] text-loss">{error || 'Failed to load Real Earnings Yield data'}</p>
      </div>
    )
  }

  const { current, stats } = data
  const config = signalConfig[current.signal] || signalConfig.HOLD
  const SignalIcon = config.icon

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 card-hover">
      {/* Header + Signal */}
      <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 mb-5">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0 mt-0.5">
            <ShieldCheck className="w-4.5 h-4.5 text-accent" strokeWidth={1.5} />
          </div>
          <div>
            <h3 className="text-[16px] font-serif font-medium text-text-primary">Real Earnings Yield</h3>
            <p className="text-[12px] text-text-tertiary leading-relaxed max-w-md">
              What stocks really earn after inflation — the single best indicator of when equities are cheap or expensive.
            </p>
          </div>
        </div>

        {/* Signal badge */}
        <div className={clsx('flex items-center gap-2.5 px-4 py-2.5 rounded-xl border', config.bg, config.border)}>
          <SignalIcon className={clsx('w-5 h-5', config.color)} strokeWidth={1.5} />
          <div>
            <div className="flex items-center gap-2">
              <span className={clsx('text-[22px] font-serif font-medium font-tabular leading-none', config.color)}>
                {current.real_earnings_yield?.toFixed(1)}%
              </span>
              <span className={clsx('font-mono text-[10px] uppercase tracking-[0.13em]', config.color)}>
                {config.label}
              </span>
            </div>
            <p className="font-mono text-[10px] text-text-tertiary tabular-nums mt-1">
              EY {current.earnings_yield?.toFixed(1)}% − Inflation {current.inflation?.toFixed(1)}%
            </p>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-3 sm:grid-cols-6 gap-3 mb-4">
        <div className="px-3 py-2 rounded-[10px] bg-accent/[0.03] border border-[rgba(180,220,190,0.10)]">
          <p className="font-mono text-[9.5px] text-text-tertiary uppercase tracking-[0.13em] mb-0.5">Real EY</p>
          <p className={clsx('text-[16px] font-serif font-medium font-tabular leading-none', current.real_earnings_yield >= 0 ? 'text-gain' : 'text-loss')}>
            {current.real_earnings_yield?.toFixed(2)}%
          </p>
        </div>
        {current.excess_cape_yield != null && (
          <div className="px-3 py-2 rounded-[10px] bg-accent/[0.03] border border-[rgba(180,220,190,0.10)]">
            <p className="font-mono text-[9.5px] text-text-tertiary uppercase tracking-[0.13em] mb-0.5">Excess CAPE</p>
            <p className={clsx('text-[16px] font-serif font-medium font-tabular leading-none', current.excess_cape_yield >= 0 ? 'text-accent' : 'text-loss')}>
              {current.excess_cape_yield.toFixed(2)}%
            </p>
          </div>
        )}
        <div className="px-3 py-2 rounded-[10px] bg-accent/[0.03] border border-[rgba(180,220,190,0.10)]">
          <p className="font-mono text-[9.5px] text-text-tertiary uppercase tracking-[0.13em] mb-0.5">60Y Avg</p>
          <p className="text-[16px] font-serif font-medium font-tabular leading-none text-text-primary">{stats.avg}%</p>
        </div>
        <div className="px-3 py-2 rounded-[10px] bg-accent/[0.03] border border-[rgba(180,220,190,0.10)]">
          <p className="font-mono text-[9.5px] text-text-tertiary uppercase tracking-[0.13em] mb-0.5">Percentile</p>
          <p className="text-[16px] font-serif font-medium font-tabular leading-none text-text-primary">{stats.current_percentile}th</p>
        </div>
        <div className="px-3 py-2 rounded-[10px] bg-accent/[0.03] border border-[rgba(180,220,190,0.10)]">
          <p className="font-mono text-[9.5px] text-text-tertiary uppercase tracking-[0.13em] mb-0.5">CAPE</p>
          <p className="text-[16px] font-serif font-medium font-tabular leading-none text-text-primary">{current.cape?.toFixed(1) ?? '—'}x</p>
        </div>
        <div className="px-3 py-2 rounded-[10px] bg-accent/[0.03] border border-[rgba(180,220,190,0.10)]">
          <p className="font-mono text-[9.5px] text-text-tertiary uppercase tracking-[0.13em] mb-0.5">10Y Treasury</p>
          <p className="text-[16px] font-serif font-medium font-tabular leading-none text-text-primary">{current.treasury_10y?.toFixed(2)}%</p>
        </div>
      </div>

      {/* Time range selector */}
      <div className="flex items-center gap-1 mb-3">
        {timeRanges.map((r) => (
          <button
            key={r.label}
            onClick={() => setActiveRange(r.label)}
            className={clsx(
              'px-3 py-1 font-mono text-[10px] uppercase tracking-[0.11em] rounded-md transition-colors',
              activeRange === r.label
                ? 'bg-accent/[0.12] text-text-primary'
                : 'text-text-tertiary hover:text-text-secondary'
            )}
          >
            {r.label}
          </button>
        ))}
      </div>

      {/* Chart */}
      <div className="h-[350px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="reyGreenGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#CFAE62" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#CFAE62" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="reyRedGrad" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#F2937F" stopOpacity={0.2} />
                <stop offset="100%" stopColor="#F2937F" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="sp500Grad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(166,158,140,0.10)" stopOpacity={1} />
                <stop offset="100%" stopColor="rgba(166,158,140,0)" stopOpacity={0} />
              </linearGradient>
            </defs>

            <XAxis
              dataKey="date"
              tickFormatter={(d: string) => {
                const dt = new Date(d)
                return activeRange === '10Y' ? dt.toLocaleDateString('en-US', { year: '2-digit', month: 'short' }) : dt.getFullYear().toString()
              }}
              tick={{ fontSize: 10, fill: 'rgba(180,220,190,0.35)' }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
              minTickGap={60}
            />

            {/* Left Y axis: Real Earnings Yield */}
            <YAxis
              yAxisId="left"
              tickFormatter={(v: number) => `${v}%`}
              tick={{ fontSize: 10, fill: 'rgba(180,220,190,0.35)' }}
              axisLine={false}
              tickLine={false}
              width={45}
            />

            {/* Right Y axis: S&P 500 price */}
            <YAxis
              yAxisId="right"
              orientation="right"
              tickFormatter={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : `${v}`}
              tick={{ fontSize: 10, fill: 'rgba(180,220,190,0.2)' }}
              axisLine={false}
              tickLine={false}
              width={40}
            />

            <Tooltip content={<CustomTooltip />} />

            {/* Zero line */}
            <ReferenceLine yAxisId="left" y={0} stroke="rgba(180,220,190,0.15)" strokeDasharray="3 3" />

            {/* Red zones for negative REY periods */}
            {negativeZones.map((zone, i) => (
              <ReferenceArea
                key={i}
                yAxisId="left"
                x1={zone.start}
                x2={zone.end}
                fill="#F2937F"
                fillOpacity={0.06}
              />
            ))}

            {/* S&P 500 price (background area) */}
            <Area
              yAxisId="right"
              type="monotone"
              dataKey="sp500"
              stroke="rgba(166,158,140,0.18)"
              strokeWidth={1}
              fill="url(#sp500Grad)"
              dot={false}
              connectNulls
            />

            {/* Positive REY area (green) */}
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="real_ey_pos"
              stroke="transparent"
              fill="url(#reyGreenGrad)"
              dot={false}
              baseLine={0}
            />

            {/* Negative REY area (red) */}
            <Area
              yAxisId="left"
              type="monotone"
              dataKey="real_ey_neg"
              stroke="transparent"
              fill="url(#reyRedGrad)"
              dot={false}
              baseLine={0}
            />

            {/* Real Earnings Yield line */}
            <Line
              yAxisId="left"
              type="monotone"
              dataKey="real_ey"
              stroke="#CFAE62"
              strokeWidth={2}
              dot={false}
              connectNulls
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-3 font-mono text-[10px] uppercase tracking-[0.11em] text-text-tertiary">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-0.5 bg-accent rounded" />
          <span>Real Earnings Yield</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-[rgba(166,158,140,0.15)]" />
          <span>S&P 500</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-accent/15" />
          <span>Positive (invest)</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded-sm bg-loss/15" />
          <span>Negative (caution)</span>
        </div>
      </div>

      {/* Signal description */}
      <div className={clsx('mt-4 px-4 py-3 rounded-lg border', config.bg, config.border)}>
        <p className="text-[12px] text-text-secondary leading-relaxed">
          {current.signal_description}
        </p>
        <p className="text-[11px] text-text-tertiary mt-2">
          Positive {stats.positive_pct}% of the time since {stats.start_year}. Historical avg: {stats.avg}%. You're at the {stats.current_percentile}th percentile.
          {data?.ecy_stats?.current != null && (
            <> Excess CAPE Yield: {data.ecy_stats.current}% (median {data.ecy_stats.median}%).</>
          )}
        </p>
      </div>

      {/* Nasdaq relative valuation */}
      {data?.nasdaq?.qqq_pe && (
        <div className="mt-3 px-4 py-2.5 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.10)]">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4 text-[11px] text-text-tertiary">
              <span>Nasdaq P/E: <span className="text-text-primary font-mono tabular-nums">{data.nasdaq.qqq_pe}x</span></span>
              <span>S&P P/E: <span className="text-text-primary font-mono tabular-nums">{data.nasdaq.spy_pe}x</span></span>
              <span>Relative: <span className="text-text-primary font-mono tabular-nums">{data.nasdaq.relative_pe}x</span></span>
            </div>
          </div>
          <p className="text-[11px] text-text-tertiary mt-1">{data.nasdaq.interpretation}</p>
        </div>
      )}
    </div>
  )
}
