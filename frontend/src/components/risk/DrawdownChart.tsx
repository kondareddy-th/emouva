import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts'

interface Props {
  data: { date: string; drawdown: number }[]
  maxDrawdown: number
}

export default function DrawdownChart({ data, maxDrawdown }: Props) {
  if (!data.length) {
    return (
      <div className="h-[180px] flex items-center justify-center text-text-tertiary text-[13px]">
        No drawdown data available
      </div>
    )
  }

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload?.length) return null
    const { date, drawdown } = payload[0].payload
    return (
      <div className="bg-surface-3 border border-[rgba(180,220,190,0.12)] rounded-[10px] px-3 py-2 shadow-lg">
        <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary">
          {new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
        </p>
        <p className="font-mono text-[13px] tabular-nums text-loss mt-0.5">
          {drawdown.toFixed(2)}%
        </p>
      </div>
    )
  }

  return (
    <div className="h-[180px]">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="transparent" stopOpacity={0} />
              <stop offset="100%" stopColor="#F2937F" stopOpacity={0.2} />
            </linearGradient>
          </defs>
          <XAxis
            dataKey="date"
            tickFormatter={(d) => new Date(d).toLocaleDateString('en-US', { month: 'short' })}
            tick={{ fontSize: 11, fill: 'rgba(180,220,190,0.35)' }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            tick={{ fontSize: 11, fill: 'rgba(180,220,190,0.35)' }}
            axisLine={false}
            tickLine={false}
            domain={['dataMin', 0]}
            width={50}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={0} stroke="rgba(180,220,190,0.08)" strokeDasharray="3 3" />
          <Area
            type="monotone"
            dataKey="drawdown"
            stroke="#F2937F"
            strokeWidth={1.5}
            fill="url(#drawdownGradient)"
            dot={false}
            animationDuration={500}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
