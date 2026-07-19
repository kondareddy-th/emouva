import clsx from 'clsx'

interface CorrelationAlert {
  pair: [string, string]
  correlation: number
  method?: 'pearson' | 'spearman'
}

interface Props {
  alerts: CorrelationAlert[]
}

export default function CorrelationMatrix({ alerts }: Props) {
  if (!alerts.length) {
    return (
      <div className="py-4 flex flex-col items-center justify-center text-text-tertiary">
        <p className="text-[13px]">No high correlations detected</p>
        <p className="text-[11px] mt-1">All pairs below 0.65 threshold</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {alerts.map((alert, i) => {
        const severity = alert.correlation > 0.85 ? 'critical' : alert.correlation > 0.75 ? 'high' : 'moderate'
        return (
          <div
            key={i}
            className={clsx(
              'flex items-center justify-between p-3.5 rounded-[10px] border transition-colors',
              severity === 'critical'
                ? 'bg-loss/5 border-loss/15'
                : severity === 'high'
                  ? 'bg-warning/5 border-warning/10'
                  : 'bg-surface-2 border-[rgba(180,220,190,0.10)]'
            )}
          >
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5">
                <span className="font-mono text-[12px] text-text-primary tabular-nums bg-surface-3 px-2 py-0.5 rounded">
                  {alert.pair[0]}
                </span>
                <span className="text-[11px] text-text-tertiary">&mdash;</span>
                <span className="font-mono text-[12px] text-text-primary tabular-nums bg-surface-3 px-2 py-0.5 rounded">
                  {alert.pair[1]}
                </span>
              </div>
              {alert.method && (
                <span className="font-mono text-[9px] text-text-tertiary uppercase tracking-[0.13em]">
                  {alert.method === 'spearman' ? 'ρ' : 'r'}
                </span>
              )}
            </div>
            <div className="flex items-center gap-3">
              <div className="w-16 h-1.5 bg-[rgba(180,220,190,0.08)] rounded-full overflow-hidden">
                <div
                  className={clsx(
                    'h-full rounded-full',
                    severity === 'critical' ? 'bg-loss' : severity === 'high' ? 'bg-warning' : 'bg-accent'
                  )}
                  style={{ width: `${alert.correlation * 100}%` }}
                />
              </div>
              <span className={clsx(
                'text-[17px] font-serif font-medium font-tabular min-w-[40px] text-right',
                severity === 'critical' ? 'text-loss' : severity === 'high' ? 'text-warning' : 'text-text-primary'
              )}>
                {alert.correlation.toFixed(2)}
              </span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
