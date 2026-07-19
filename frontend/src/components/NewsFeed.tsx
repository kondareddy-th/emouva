import { useState } from 'react'
import clsx from 'clsx'
import { RefreshCw, Newspaper, ChevronDown } from 'lucide-react'
import { type NewsArticle } from '../hooks/usePortfolioNews'
import useMarketNews from '../hooks/useMarketNews'

function ImpactDot({ impact }: { impact: NewsArticle['impact'] }) {
  return (
    <div className={clsx(
      'w-1.5 h-1.5 rounded-full flex-shrink-0',
      impact === 'positive' ? 'bg-gain' : impact === 'negative' ? 'bg-loss' : 'bg-text-tertiary'
    )} />
  )
}

function SymbolTag({ symbol }: { symbol: string }) {
  return (
    <span className="text-[10px] font-mono font-medium px-1.5 py-0.5 rounded bg-accent/10 text-accent">
      {symbol}
    </span>
  )
}

export default function NewsFeed() {
  const { articles, loading, refetch } = useMarketNews()
  const [expandedArticles, setExpandedArticles] = useState<Set<number>>(new Set())

  const toggleArticle = (index: number) => {
    setExpandedArticles(prev => {
      const next = new Set(prev)
      if (next.has(index)) next.delete(index)
      else next.add(index)
      return next
    })
  }

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[rgba(180,220,190,0.08)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Newspaper className="w-3.5 h-3.5 text-text-tertiary" strokeWidth={1.5} />
          <h3 className="text-[16px] font-serif font-medium text-text-primary">Market News</h3>
        </div>
        <button
          onClick={refetch}
          disabled={loading}
          className="w-6 h-6 rounded-md hover:bg-[rgba(207,174,98,0.06)] flex items-center justify-center transition-colors disabled:opacity-50"
        >
          <RefreshCw className={clsx('w-3 h-3 text-text-tertiary', loading && 'animate-spin')} />
        </button>
      </div>

      {/* Content */}
      {loading && !articles.length ? (
        <div className="px-4 py-6 space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="space-y-1.5">
              <div className="skeleton h-3 w-16" />
              <div className="skeleton h-3 w-full" />
              <div className="skeleton h-3 w-3/4" />
            </div>
          ))}
        </div>
      ) : articles.length > 0 ? (
        <div className="divide-y divide-[rgba(180,220,190,0.06)]">
          {articles.slice(0, 6).map((article, i) => {
            const isExpanded = expandedArticles.has(i)
            return (
              <div
                key={i}
                onClick={() => toggleArticle(i)}
                className="px-4 py-3 hover:bg-[rgba(207,174,98,0.04)] transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <SymbolTag symbol={article.symbol} />
                    {article.urgency === 'high' && (
                      <span className="text-[9px] font-mono font-medium px-1.5 py-0.5 rounded bg-loss/10 text-loss uppercase tracking-[0.11em]">
                        Urgent
                      </span>
                    )}
                  </div>
                  <ChevronDown
                    className={clsx(
                      'w-3 h-3 text-text-tertiary transition-transform flex-shrink-0',
                      isExpanded && 'rotate-180'
                    )}
                  />
                </div>
                <div className="flex items-start gap-2">
                  <ImpactDot impact={article.impact} />
                  <div className="min-w-0 -mt-0.5">
                    <p className={clsx(
                      'text-[12px] text-text-primary font-medium leading-snug',
                      !isExpanded && 'line-clamp-2'
                    )}>
                      {article.title}
                    </p>
                    {article.summary && (
                      <p className={clsx(
                        'text-[11px] text-text-tertiary mt-0.5 leading-relaxed',
                        !isExpanded && 'line-clamp-2'
                      )}>
                        {article.summary}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      ) : (
        <div className="px-4 py-6 text-center">
          <p className="text-[12px] text-text-tertiary">
            Connect your brokerage to see curated news for your portfolio.
          </p>
        </div>
      )}
    </div>
  )
}
