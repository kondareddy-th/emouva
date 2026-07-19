import clsx from 'clsx'

export function ValuationGauge({ bear, base, bull, current }: { bear: number; base: number; bull: number; current: number }) {
  const min = bear * 0.85
  const max = bull * 1.15
  const range = max - min
  const bearPos = ((bear - min) / range) * 100
  const basePos = ((base - min) / range) * 100
  const bullPos = ((bull - min) / range) * 100
  const currentPos = Math.min(100, Math.max(0, ((current - min) / range) * 100))

  const getValuationLabel = () => {
    if (current <= bear) return { text: 'Undervalued', color: 'text-gain' }
    if (current >= bull) return { text: 'Overvalued', color: 'text-loss' }
    if (current <= base) return { text: 'Below Fair Value', color: 'text-gain' }
    return { text: 'Above Fair Value', color: 'text-warning' }
  }

  const label = getValuationLabel()

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between">
        <div className="text-center">
          <div className="text-[10px] text-loss font-medium">Bear</div>
          <div className="text-[14px] font-semibold text-loss font-tabular">${bear}</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-text-tertiary font-medium">Fair Value</div>
          <div className="text-[14px] font-semibold text-text-primary font-tabular">${base}</div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-gain font-medium">Bull</div>
          <div className="text-[14px] font-semibold text-gain font-tabular">${bull}</div>
        </div>
      </div>
      <div className="relative h-2 rounded-full bg-surface-3 overflow-hidden">
        <div
          className="absolute inset-0 rounded-full"
          style={{ background: 'linear-gradient(90deg, #F2937F 0%, #DFB65A 35%, #CFAE62 65%, #CFAE62 100%)', opacity: 0.2 }}
        />
        <div className="absolute top-0 bottom-0 w-px bg-loss/40" style={{ left: `${bearPos}%` }} />
        <div className="absolute top-0 bottom-0 w-px bg-text-tertiary" style={{ left: `${basePos}%` }} />
        <div className="absolute top-0 bottom-0 w-px bg-gain/40" style={{ left: `${bullPos}%` }} />
        <div
          className="absolute top-1/2 -translate-y-1/2 w-3.5 h-3.5 rounded-full bg-white border-2 border-base shadow-lg"
          style={{ left: `${currentPos}%`, marginLeft: '-7px' }}
        />
      </div>
      <div className="flex items-center justify-center gap-2">
        <span className="text-caption text-text-tertiary">Current:</span>
        <span className="text-[14px] font-semibold font-tabular">${current.toFixed(2)}</span>
        <span className={clsx('text-[13px] font-medium', label.color)}>— {label.text}</span>
      </div>
    </div>
  )
}
