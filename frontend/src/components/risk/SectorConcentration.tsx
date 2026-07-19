import clsx from 'clsx'
import { formatCurrency } from '../../data/mockData'

interface SectorWeight {
  sector: string
  value: number
  weight: number
}

interface Props {
  sectors: SectorWeight[]
  hhi: number
  top5Pct: number
}

// Warm, muted, gold-forward palette — matches the private-bank aesthetic.
// Explicit hex bg classes (never semantic) so dynamic contexts can't strip them.
const SECTOR_PALETTE = [
  'bg-[#CFAE62]',
  'bg-[#BD9F58]',
  'bg-[#95814D]',
  'bg-[#7FE3A9]',
  'bg-[#C4CEC1]',
  'bg-[#F2937F]',
  'bg-[#DFB65A]',
  'bg-[#746540]',
  'bg-[#A6B2A3]',
  'bg-[#564B31]',
]

const sectorColors: Record<string, string> = {
  'Technology Services': 'bg-[#CFAE62]',
  'Electronic Technology': 'bg-[#BD9F58]',
  Technology: 'bg-[#CFAE62]',
  ETF: 'bg-[#C4CEC1]',
  Commodities: 'bg-[#DFB65A]',
  Utilities: 'bg-[#7FE3A9]',
  Defense: 'bg-[#F2937F]',
  'Retail Trade': 'bg-[#95814D]',
  Miscellaneous: 'bg-[#A6B2A3]',
  'Health Technology': 'bg-[#BD9F58]',
  Finance: 'bg-[#7FE3A9]',
  'Producer Manufacturing': 'bg-[#746540]',
  'Consumer Services': 'bg-[#C4CEC1]',
  'Energy Minerals': 'bg-[#DFB65A]',
  'Health Services': 'bg-[#BD9F58]',
  'Consumer Non-Durables': 'bg-[#A6B2A3]',
  'Consumer Durables': 'bg-[#C4CEC1]',
  Transportation: 'bg-[#7FE3A9]',
  Communications: 'bg-[#95814D]',
  'Industrial Services': 'bg-[#746540]',
  'Process Industries': 'bg-[#DFB65A]',
  'Distribution Services': 'bg-[#7FE3A9]',
  'Commercial Services': 'bg-[#95814D]',
  'Non-Energy Minerals': 'bg-[#A6B2A3]',
  Unknown: 'bg-[#564B31]',
}

function getSectorColor(sector: string, index: number): string {
  return sectorColors[sector] || SECTOR_PALETTE[index % SECTOR_PALETTE.length]
}

export default function SectorConcentration({ sectors, hhi, top5Pct }: Props) {
  if (!sectors.length) {
    return (
      <div className="h-[180px] flex items-center justify-center text-text-tertiary text-[13px]">
        No sector data available
      </div>
    )
  }

  return (
    <div>
      {/* Sector bars */}
      <div className="space-y-3">
        {sectors.slice(0, 8).map((s, i) => {
          const color = s.weight > 40 ? 'bg-warning' : getSectorColor(s.sector, i)
          return (
            <div key={s.sector} className="space-y-1">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={clsx('w-1.5 h-1.5 rotate-45 shrink-0', getSectorColor(s.sector, i))} />
                  <span className="text-[13px] text-text-secondary font-medium">{s.sector}</span>
                  {s.weight > 40 && (
                    <span className="font-mono text-[9.5px] tracking-[0.11em] px-1.5 py-0.5 rounded bg-warning/10 text-warning">
                      HIGH
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className="font-mono text-[11px] text-text-tertiary tabular-nums">
                    {formatCurrency(s.value)}
                  </span>
                  <span className="font-mono text-[13px] text-text-primary tabular-nums w-12 text-right">
                    {s.weight.toFixed(1)}%
                  </span>
                </div>
              </div>
              <div className="h-1.5 bg-[rgba(180,220,190,0.08)] rounded-full overflow-hidden">
                <div
                  className={clsx('h-full rounded-full transition-all duration-700', color)}
                  style={{ width: `${Math.min(s.weight, 100)}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Summary metrics */}
      <div className="flex items-center gap-3 md:gap-6 mt-5 pt-4 border-t border-[rgba(180,220,190,0.10)]">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1">HHI Index</p>
          <p className={clsx(
            'text-[18px] font-serif font-medium font-tabular leading-none',
            hhi > 0.25 ? 'text-warning' : 'text-text-primary'
          )}>
            {(hhi * 10000).toFixed(0)}
          </p>
          <p className="text-[10px] text-text-tertiary mt-1">
            {hhi > 0.25 ? 'Concentrated' : hhi > 0.15 ? 'Moderate' : 'Diversified'}
          </p>
        </div>
        <div className="w-px h-8 bg-[rgba(180,220,190,0.10)]" />
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1">Top 5 Sectors</p>
          <p className={clsx(
            'text-[18px] font-serif font-medium font-tabular leading-none',
            top5Pct > 90 ? 'text-warning' : 'text-text-primary'
          )}>
            {top5Pct.toFixed(1)}%
          </p>
          <p className="text-[10px] text-text-tertiary mt-1">of portfolio</p>
        </div>
      </div>
    </div>
  )
}
