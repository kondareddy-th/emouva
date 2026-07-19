import clsx from 'clsx'
import { ShieldCheck, ShieldAlert, AlertTriangle } from 'lucide-react'
import { formatCurrency } from '../../data/mockData'
import type { ConcentrationRisk, ConcentrationDimension } from '../../data/mockData'

interface Props {
  data: ConcentrationRisk
}

const ratingConfig = {
  green: { label: 'Diversified', color: 'text-gain', bg: 'bg-gain/10', Icon: ShieldCheck },
  yellow: { label: 'Moderate', color: 'text-warning', bg: 'bg-warning/10', Icon: ShieldAlert },
  red: { label: 'Concentrated', color: 'text-loss', bg: 'bg-loss/10', Icon: AlertTriangle },
}

const dimensionLabels: Record<string, { title: string; description: string }> = {
  sector: { title: 'Sector', description: 'Industry diversification' },
  market_cap: { title: 'Market Cap', description: 'Size diversification' },
  geography: { title: 'Geography', description: 'Regional diversification' },
}

const BAR_PALETTE = [
  'bg-[#CFAE62]', 'bg-[#BD9F58]', 'bg-[#95814D]', 'bg-[#7FE3A9]',
  'bg-[#C4CEC1]', 'bg-[#F2937F]', 'bg-[#DFB65A]', 'bg-[#746540]',
  'bg-[#A6B2A3]', 'bg-[#564B31]',
]

function RatingBadge({ rating }: { rating: 'green' | 'yellow' | 'red' }) {
  const config = ratingConfig[rating]
  const Icon = config.Icon
  return (
    <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium', config.bg, config.color)}>
      <Icon className="w-3 h-3" strokeWidth={1.5} />
      {config.label}
    </span>
  )
}

function DimensionPanel({ dimKey, dim }: { dimKey: string; dim: ConcentrationDimension }) {
  const meta = dimensionLabels[dimKey] || { title: dimKey, description: '' }
  const config = ratingConfig[dim.rating]

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-[14px] font-serif font-medium text-text-primary">{meta.title}</h4>
          <p className="text-[11px] text-text-tertiary">{meta.description}</p>
        </div>
        <RatingBadge rating={dim.rating} />
      </div>

      {/* Stacked bar */}
      {dim.breakdown.length > 0 && (
        <div className="h-3 rounded-full overflow-hidden flex bg-[rgba(180,220,190,0.08)]">
          {dim.breakdown.map((b, i) => (
            <div
              key={b.label}
              className={clsx('h-full transition-all duration-500', BAR_PALETTE[i % BAR_PALETTE.length])}
              style={{ width: `${Math.max(b.weight, 1)}%` }}
              title={`${b.label}: ${b.weight.toFixed(1)}%`}
            />
          ))}
        </div>
      )}

      {/* Legend */}
      <div className="space-y-1.5">
        {dim.breakdown.slice(0, 6).map((b, i) => (
          <div key={b.label} className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className={clsx('w-1.5 h-1.5 rotate-45 shrink-0', BAR_PALETTE[i % BAR_PALETTE.length])} />
              <span className="text-[12px] text-text-secondary">{b.label}</span>
              {b.weight > 60 && (
                <span className="font-mono text-[9.5px] tracking-[0.11em] px-1.5 py-0.5 rounded bg-loss/10 text-loss">HIGH</span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-[11px] text-text-tertiary tabular-nums">{formatCurrency(b.value)}</span>
              <span className="font-mono text-[12px] text-text-primary tabular-nums w-12 text-right">{b.weight.toFixed(1)}%</span>
            </div>
          </div>
        ))}
        {dim.breakdown.length > 6 && (
          <p className="text-[11px] text-text-tertiary">+{dim.breakdown.length - 6} more</p>
        )}
      </div>

      {/* Metrics footer */}
      <div className="flex items-center gap-4 pt-2 border-t border-[rgba(180,220,190,0.08)]">
        <div>
          <p className="font-mono text-[9.5px] uppercase tracking-[0.13em] text-text-tertiary mb-0.5">HHI</p>
          <p className={clsx('text-[15px] font-serif font-medium font-tabular leading-none', config.color)}>
            {(dim.hhi * 10000).toFixed(0)}
          </p>
        </div>
        <div className="w-px h-6 bg-[rgba(180,220,190,0.10)]" />
        <div>
          <p className="font-mono text-[9.5px] uppercase tracking-[0.13em] text-text-tertiary mb-0.5">Top Bucket</p>
          <p className={clsx('text-[15px] font-serif font-medium font-tabular leading-none', config.color)}>
            {dim.topHoldingPct.toFixed(1)}%
          </p>
        </div>
      </div>
    </div>
  )
}

export default function ConcentrationRiskCard({ data }: Props) {
  const overallConfig = ratingConfig[data.rating]
  const OverallIcon = overallConfig.Icon

  return (
    <div className="space-y-5">
      {/* Overall Score */}
      <div className="flex items-center gap-4 p-3 rounded-[10px] bg-accent/[0.03] border border-[rgba(180,220,190,0.10)]">
        <div className={clsx('w-12 h-12 rounded-xl flex items-center justify-center', overallConfig.bg)}>
          <OverallIcon className={clsx('w-6 h-6', overallConfig.color)} strokeWidth={1.5} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span className="text-[15px] font-serif font-medium text-text-primary">Concentration Score</span>
            <span className={clsx('text-[22px] font-serif font-medium font-tabular leading-none', overallConfig.color)}>{data.score}</span>
            <span className="font-mono text-[11px] text-text-tertiary tabular-nums">/100</span>
          </div>
          <p className="text-[12px] text-text-tertiary">
            {data.rating === 'green' && 'Your portfolio is well diversified across all dimensions.'}
            {data.rating === 'yellow' && 'Some concentration detected. Consider diversifying further.'}
            {data.rating === 'red' && 'High concentration risk. Portfolio is heavily tilted in one or more areas.'}
          </p>
        </div>
      </div>

      {/* Three Dimension Panels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {(['sector', 'market_cap', 'geography'] as const).map((key) => (
          <div
            key={key}
            className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.10)] p-4"
          >
            <DimensionPanel dimKey={key} dim={data.dimensions[key]} />
          </div>
        ))}
      </div>
    </div>
  )
}
