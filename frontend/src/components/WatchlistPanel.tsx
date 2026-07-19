import clsx from 'clsx'
import { Plus } from 'lucide-react'
import { formatCurrency, formatPercent, getChangeColor, type WatchlistItem } from '../data/mockData'
import { usePortfolioStore } from '../hooks/usePortfolioStore'
import Sparkline from './Sparkline'

interface Props {
  watchlist?: WatchlistItem[]
}

export default function WatchlistPanel({ watchlist = [] }: Props) {
  const { quotes } = usePortfolioStore()

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[rgba(180,220,190,0.08)] flex items-center justify-between">
        <h3 className="text-[16px] font-serif font-medium text-text-primary">Watchlist</h3>
        <button className="w-6 h-6 rounded-md hover:bg-[rgba(207,174,98,0.06)] flex items-center justify-center transition-colors">
          <Plus className="w-3.5 h-3.5 text-text-tertiary" strokeWidth={1.5} />
        </button>
      </div>

      {/* Items */}
      {watchlist.length === 0 ? (
        <div className="px-4 py-6 text-center">
          <p className="text-[12px] text-text-tertiary">No watchlist items yet.</p>
        </div>
      ) : (
        <div className="stagger">
          {watchlist.slice(0, 6).map((item, i) => (
            <div
              key={item.symbol}
              className={clsx(
                'px-4 py-2.5 hover:bg-[rgba(207,174,98,0.04)] transition-colors cursor-pointer',
                i < Math.min(watchlist.length, 6) - 1 && 'border-b border-[rgba(180,220,190,0.06)]'
              )}
            >
              <div className="flex items-center justify-between">
                <div className="min-w-0">
                  <div className="text-[13px] font-mono font-medium text-text-primary">
                    {item.symbol}
                  </div>
                  <div className="text-[11px] text-text-tertiary truncate">
                    {item.name}
                  </div>
                </div>
                {item.sparkline && item.sparkline.length > 0 && (
                  <Sparkline
                    data={item.sparkline}
                    width={48}
                    height={20}
                    positive={item.changePct >= 0}
                  />
                )}
                <div className="text-right ml-2">
                  <div className="text-[13px] font-mono tabular-nums text-text-primary font-medium">
                    {formatCurrency(quotes?.[item.symbol]?.price ?? item.price)}
                  </div>
                  <div
                    className={clsx(
                      'text-[11px] font-mono tabular-nums font-medium',
                      getChangeColor(quotes?.[item.symbol]?.change_pct ?? item.changePct)
                    )}
                  >
                    {formatPercent(quotes?.[item.symbol]?.change_pct ?? item.changePct)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
