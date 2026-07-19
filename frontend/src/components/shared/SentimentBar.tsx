import clsx from 'clsx'

export function SentimentBar({ label, value }: { label: string; value: number }) {
  const getColor = (v: number) => {
    if (v >= 65) return 'bg-gain'
    if (v >= 45) return 'bg-warning'
    return 'bg-loss'
  }
  return (
    <div className="flex items-center gap-3">
      <span className="text-caption text-text-tertiary w-14">{label}</span>
      <div className="flex-1 h-1 bg-surface-3 rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all', getColor(value))}
          style={{ width: `${value}%` }}
        />
      </div>
      <span className="text-caption text-text-secondary font-tabular w-8 text-right font-medium">
        {value}
      </span>
    </div>
  )
}
