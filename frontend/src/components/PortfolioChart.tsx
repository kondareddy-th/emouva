import { useState, useMemo, useCallback } from 'react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import clsx from 'clsx'
import { formatCurrency } from '../data/mockData'
import { usePortfolioHistory, usePortfolioSummary } from '../hooks/usePortfolio'

const ranges = [
  { label: '1D', days: 1 },
  { label: '1W', days: 7 },
  { label: '1M', days: 30 },
  { label: '3M', days: 90 },
  { label: 'ALL', days: 999 },
]

/** UTC ms of today's midnight in ET (the market timezone), DST-safe. */
function etMidnightMs(): number {
  const now = new Date()
  const etNow = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }))
  const offset = now.getTime() - etNow.getTime()
  const m = new Date(etNow.getFullYear(), etNow.getMonth(), etNow.getDate(), 0, 0, 0, 0)
  return m.getTime() + offset
}

interface Props {
  liveTotalValue?: number
  hasPositions?: boolean
}

export default function PortfolioChart({ liveTotalValue, hasPositions = true }: Props) {
  const { data: summary } = usePortfolioSummary()
  const [activeRange, setActiveRange] = useState('1D')
  const [hoverValue, setHoverValue] = useState<number | null>(null)
  const [hoverDate, setHoverDate] = useState<string | null>(null)

  const activeDays = ranges.find((r) => r.label === activeRange)?.days ?? 90
  const { data: history } = usePortfolioHistory(activeDays)

  // Live total value of the connected account — drives the headline value and
  // pins the last chart point.
  const liveVal = liveTotalValue ?? (summary.source === 'robinhood' ? summary.totalValue : null)

  const data = useMemo(() => {
    // If live data, update the last point to match the real portfolio value
    if (history.length > 0 && liveVal) {
      const updated = [...history]
      updated[updated.length - 1] = {
        ...updated[updated.length - 1],
        value: liveVal,
      }
      return updated
    }
    return history
  }, [history, liveVal])

  // Numeric time x-axis so 1D can use a FIXED midnight→midnight domain — the line
  // grows left→now instead of stretching a few hours across the whole width.
  const isIntraday = activeRange === '1D'
  const dataT = useMemo(
    () => data.map((d) => ({ ...d, t: Date.parse((d as { date: string }).date) })),
    [data],
  )
  const xDomain: [number | string, number | string] = isIntraday
    ? [etMidnightMs(), etMidnightMs() + 86_400_000]
    : ['dataMin', 'dataMax']

  // Fall back to the live value when there's no history yet (history isn't
  // migrated to the MCP), so the headline Portfolio Value still renders.
  const endValue = data[data.length - 1]?.value ?? liveVal ?? 0

  // After-hours (post-4pm) is drawn muted. With a time axis the gradient must
  // switch at the after-hours TIME position within the drawn line (points aren't
  // evenly spaced), not by index.
  const firstT = dataT[0]?.t
  const lastT = dataT[dataT.length - 1]?.t
  const ahStartT = dataT.find((d) => (d as { after_hours?: boolean }).after_hours)?.t
  const ahOffsetPct =
    ahStartT && firstT && lastT && lastT > firstT
      ? ((ahStartT - firstT) / (lastT - firstT)) * 100
      : 100
  // For 1D, the baseline is yesterday's 4pm close (prior regular session close).
  // The backend's summary.dailyChange is already computed against previous_close per position,
  // so we derive the baseline as (current total − today's dailyChange). This matches Robinhood's
  // "today" convention — after-hours moves roll into the current day's P&L until the next session.
  const startValue = (activeRange === '1D' && summary.source === 'robinhood' && endValue > 0)
    ? endValue - summary.dailyChange
    : (data[0]?.value ?? 0)
  const change = endValue - startValue
  const changePct = startValue > 0 ? (change / startValue) * 100 : 0
  const isPositive = change >= 0

  const displayValue = hoverValue ?? endValue
  const displayChange = hoverValue ? hoverValue - startValue : change
  const displayChangePct = hoverValue
    ? startValue > 0 ? (displayChange / startValue) * 100 : 0
    : changePct

  const displayDate = hoverDate

  const color = isPositive ? '#CFAE62' : '#F2937F'

  const handleMouseMove = useCallback((val: number, date: string) => {
    setHoverValue(val)
    setHoverDate(date)
  }, [])

  const CustomTooltip = ({ active, payload }: { active?: boolean; payload?: Array<{ value: number; payload: { date: string } }> }) => {
    if (active && payload && payload.length) {
      const val = payload[0].value
      const date = payload[0].payload.date
      if (val !== hoverValue) {
        setTimeout(() => handleMouseMove(val, date), 0)
      }
    }
    return null
  }

  // Format x-axis labels based on range
  const formatDate = (dateStr: string) => {
    if (activeRange === '1D') {
      // Intraday: show time like "10:30 AM"
      const d = new Date(dateStr)
      return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
    }
    // Show "Mar 14" style
    const d = new Date(dateStr)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="relative">
      {/* Value display */}
      <div className="mb-6">
        <p className="text-[13px] font-medium text-text-tertiary mb-1">Portfolio Value</p>
        <div className="text-display font-tabular text-text-primary">
          {formatCurrency(displayValue)}
        </div>
        <div className="flex items-center gap-2 mt-1.5">
          <span
            className={clsx(
              'text-[14px] font-medium font-tabular',
              isPositive ? 'text-gain' : 'text-loss'
            )}
          >
            {displayChange >= 0 ? '+' : ''}
            {formatCurrency(displayChange)}
          </span>
          <span
            className={clsx(
              'text-[13px] font-tabular',
              isPositive ? 'text-gain/70' : 'text-loss/70'
            )}
          >
            ({displayChangePct >= 0 ? '+' : ''}
            {displayChangePct.toFixed(2)}%)
          </span>
          <span className="text-caption text-text-tertiary">
            {displayDate
              ? activeRange === '1D'
                ? new Date(displayDate).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
                : new Date(displayDate).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })
              : activeRange}
          </span>
        </div>
      </div>

      {/* Chart */}
      <div
        className="h-[280px] -mx-1"
        onMouseLeave={() => {
          setHoverValue(null)
          setHoverDate(null)
        }}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={dataT} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.15} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="strokeGradient" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={color} />
                <stop offset={`${ahOffsetPct}%`} stopColor={color} />
                <stop offset={`${ahOffsetPct}%`} stopColor={color} stopOpacity={0.4} />
                <stop offset="100%" stopColor={color} stopOpacity={0.4} />
              </linearGradient>
            </defs>
            <XAxis dataKey="t" type="number" scale="time" domain={xDomain} hide />
            <YAxis hide domain={['dataMin', 'dataMax']} />
            <Tooltip
              content={<CustomTooltip />}
              cursor={{
                stroke: 'rgba(255,255,255,0.15)',
                strokeWidth: 1,
                strokeDasharray: 'none',
              }}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="url(#strokeGradient)"
              strokeWidth={2}
              fill="url(#chartGradient)"
              dot={false}
              activeDot={{
                r: 4,
                fill: color,
                stroke: '#0C110E',
                strokeWidth: 2,
                style: { filter: `drop-shadow(0 0 4px ${color}60)` },
              }}
              animationDuration={500}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Range selector — hidden when the account has no holdings (nothing to chart) */}
      {hasPositions && (
        <div className="flex items-center gap-1 mt-3">
          {ranges.map((range) => (
            <button
              key={range.label}
              onClick={() => setActiveRange(range.label)}
              className={clsx(
                'px-3 py-1.5 text-[12px] font-medium rounded-md transition-colors',
                activeRange === range.label
                  ? 'bg-white/[0.08] text-text-primary'
                  : 'text-text-tertiary hover:text-text-secondary'
              )}
            >
              {range.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
