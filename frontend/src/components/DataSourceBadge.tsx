import clsx from 'clsx'

export default function DataSourceBadge({ source }: { source: 'robinhood' | 'disconnected' | 'mock' }) {
  const isLive = source === 'robinhood'

  return (
    <span className={clsx(
      'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide',
      isLive ? 'bg-gain/10 text-gain' : 'bg-warning/10 text-warning'
    )}>
      <span className={clsx(
        'w-1.5 h-1.5 rounded-full',
        isLive ? 'bg-gain animate-pulse' : 'bg-warning'
      )} />
      {isLive ? 'LIVE' : 'DEMO'}
    </span>
  )
}
