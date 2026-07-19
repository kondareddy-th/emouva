import { useRef, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import clsx from 'clsx'
import { Search, RefreshCw } from 'lucide-react'
import {
  type Position,
  formatCurrency,
  formatPercent,
  getChangeColor,
} from '../data/mockData'
import type { TickerMetrics } from '../hooks/usePortfolioMetrics'

function StockLogo({ symbol }: { symbol: string }) {
  const [src, setSrc] = useState(
    `https://financialmodelingprep.com/image-stock/${symbol}.png`
  )
  const [fallbackLevel, setFallbackLevel] = useState(0)

  const handleError = () => {
    if (fallbackLevel === 0) {
      setSrc(`https://assets.parqet.com/logos/symbol/${symbol}?format=svg`)
      setFallbackLevel(1)
    } else {
      setFallbackLevel(2)
    }
  }

  if (fallbackLevel === 2) {
    return (
      <div className="w-8 h-8 rounded-[7px] bg-surface-3 flex items-center justify-center text-[11px] font-mono font-medium text-text-secondary">
        {symbol.slice(0, 2)}
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={symbol}
      className="w-8 h-8 rounded-[7px] bg-surface-3 object-contain"
      onError={handleError}
    />
  )
}

interface Props {
  compact?: boolean
  positions?: Position[]
  metrics?: Record<string, TickerMetrics>
}

export default function PositionsTable({ compact = false, positions, metrics }: Props) {
  const navigate = useNavigate()
  const data = positions ?? []
  const showAI = !compact && !!metrics && Object.keys(metrics).length > 0
  const sorted = [...data].sort(
    (a, b) => b.shares * b.currentPrice - a.shares * a.currentPrice
  )

  // Track previous prices for flash animation
  const prevPrices = useRef<Record<string, number>>({})
  const [flashMap, setFlashMap] = useState<Record<string, 'up' | 'down'>>({})

  useEffect(() => {
    const flashes: Record<string, 'up' | 'down'> = {}
    for (const pos of data) {
      const prev = prevPrices.current[pos.symbol]
      if (prev !== undefined && prev !== pos.currentPrice) {
        flashes[pos.symbol] = pos.currentPrice > prev ? 'up' : 'down'
      }
      prevPrices.current[pos.symbol] = pos.currentPrice
    }
    if (Object.keys(flashes).length > 0) {
      setFlashMap(flashes)
      const timer = setTimeout(() => setFlashMap({}), 650)
      return () => clearTimeout(timer)
    }
  }, [data])

  if (sorted.length === 0) {
    return (
      <div className="py-8 text-center">
        <p className="text-[13px] font-serif text-text-secondary">No positions to display.</p>
        <p className="text-[11px] text-text-tertiary mt-1">Connect your brokerage to see your holdings.</p>
      </div>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[rgba(180,220,190,0.08)]">
            <th className="text-left font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 pr-4">
              Name
            </th>
            {!compact && (
              <th className="text-right font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 px-4">
                Shares
              </th>
            )}
            <th className="text-right font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 px-4">
              Price
            </th>
            <th className="text-right font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 px-4">
              Today
            </th>
            <th className="text-right font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 pl-4">
              Value
            </th>
            {showAI && (
              <>
                <th className="text-right font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 px-4">
                  Fair Value
                </th>
                <th className="text-center font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 px-4">
                  Rating
                </th>
                <th className="text-center font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 px-4">
                  Sentiment
                </th>
              </>
            )}
            {!compact && (
              <th className="text-center font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary pb-3 pl-4">
                Actions
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {sorted.map((pos, index) => {
            const marketValue = pos.shares * pos.currentPrice
            const totalCost = pos.shares * pos.avgCost
            const totalGain = marketValue - totalCost
            const totalGainPct = totalCost > 0 ? ((marketValue - totalCost) / totalCost) * 100 : 0
            const dayChangePct = pos.previousClose > 0
              ? ((pos.currentPrice - pos.previousClose) / pos.previousClose) * 100
              : 0

            return (
              <tr
                key={pos.symbol}
                className={clsx(
                  'border-b border-[rgba(180,220,190,0.06)] hover:bg-[rgba(207,174,98,0.04)] transition-all duration-150 cursor-pointer group',
                  totalGain > 0 && 'border-l-2 border-l-gain/30',
                  totalGain < 0 && 'border-l-2 border-l-loss/30',
                )}
                style={{ animationDelay: `${index * 30}ms` }}
              >
                {/* Name + ticker with logo */}
                <td className="py-4 pr-4">
                  <div
                    className="flex items-center gap-3 cursor-pointer"
                    onClick={() => {
                      const params = new URLSearchParams()
                      if (pos.shares > 0) params.set('shares', pos.shares.toString())
                      if (pos.avgCost > 0) params.set('cost_basis', pos.avgCost.toFixed(2))
                      const qs = params.toString()
                      navigate(`/stock/${pos.symbol}${qs ? `?${qs}` : ''}`)
                    }}
                  >
                    <StockLogo symbol={pos.symbol} />
                    <div>
                      <div className="text-[14px] font-mono font-medium text-text-primary hover:text-accent transition-colors">
                        {pos.symbol}
                      </div>
                      {!compact && (
                        <div className="text-[12px] text-text-tertiary">
                          {pos.name}
                        </div>
                      )}
                    </div>
                  </div>
                </td>

                {/* Shares */}
                {!compact && (
                  <td className="text-right text-[14px] font-mono tabular-nums text-text-secondary py-4 px-4">
                    {pos.shares % 1 === 0 ? pos.shares : pos.shares.toFixed(4)}
                  </td>
                )}

                {/* Price */}
                <td className={clsx(
                  'text-right text-[14px] font-mono tabular-nums text-text-primary py-4 px-4 rounded',
                  flashMap[pos.symbol] === 'up' && 'price-flash-up',
                  flashMap[pos.symbol] === 'down' && 'price-flash-down',
                )}>
                  {formatCurrency(pos.currentPrice)}
                </td>

                {/* Today change */}
                <td className="text-right py-4 px-4">
                  <span
                    className={clsx(
                      'text-[14px] font-medium font-mono tabular-nums',
                      getChangeColor(dayChangePct)
                    )}
                  >
                    {formatPercent(dayChangePct)}
                  </span>
                </td>

                {/* Total value + P&L */}
                <td className="text-right py-4 pl-4">
                  <div className="text-[14px] font-medium font-mono tabular-nums text-text-primary">
                    {formatCurrency(marketValue)}
                  </div>
                  <div
                    className={clsx('text-[12px] font-mono tabular-nums flex items-center justify-end gap-1', getChangeColor(totalGain))}
                    title="Unrealized return since purchase — (current price − average cost) × shares"
                  >
                    <span>{totalGain >= 0 ? '+' : ''}{formatCurrency(totalGain)}</span>
                    <span className="text-text-tertiary">·</span>
                    <span>{formatPercent(totalGainPct)}</span>
                  </div>
                </td>

                {/* AI Metrics columns */}
                {showAI && (() => {
                  const m = metrics[pos.symbol]
                  if (!m || m.freshness === 'missing') {
                    return (
                      <>
                        <td className="text-right py-4 px-4" colSpan={3}>
                          <button
                            onClick={(e) => { e.stopPropagation(); navigate(`/research?ticker=${pos.symbol}`) }}
                            className="text-[11px] text-accent/60 hover:text-accent font-medium flex items-center gap-1 ml-auto transition-colors"
                          >
                            <Search className="w-3 h-3" />
                            Analyze
                          </button>
                        </td>
                      </>
                    )
                  }
                  const fv = m.fair_value
                  const sentiment = m.sentiment_composite
                  const verdict = m.verdict
                  const upside = fv?.base && pos.currentPrice > 0
                    ? ((fv.base - pos.currentPrice) / pos.currentPrice) * 100
                    : null

                  return (
                    <>
                      {/* Fair Value */}
                      <td className="text-right py-4 px-4">
                        {fv?.base ? (
                          <div>
                            <span className="text-[14px] font-mono tabular-nums text-[#E9D6A2] font-medium">
                              ${fv.base.toFixed(0)}
                            </span>
                            {upside !== null && (
                              <div className={clsx('text-[11px] font-mono tabular-nums', upside >= 0 ? 'text-gain' : 'text-loss')}>
                                {upside >= 0 ? '+' : ''}{upside.toFixed(0)}%
                              </div>
                            )}
                          </div>
                        ) : (
                          <span className="text-[12px] font-mono text-text-tertiary">—</span>
                        )}
                      </td>
                      {/* Rating (quality_score.overall: 1-10 scale) */}
                      <td className="text-center py-4 px-4">
                        {verdict != null && verdict > 0 ? (
                          <span className={clsx(
                            'text-[11px] font-mono tabular-nums font-medium px-2 py-0.5 rounded-full',
                            typeof verdict === 'number' && verdict >= 7 ? 'bg-gain/10 text-gain' :
                            typeof verdict === 'number' && verdict >= 4 ? 'bg-warning/10 text-warning' :
                            'bg-loss/10 text-loss'
                          )}>
                            {typeof verdict === 'number' ? `${verdict}/10` : String(verdict)}
                          </span>
                        ) : (
                          <span className="text-[12px] font-mono text-text-tertiary">—</span>
                        )}
                      </td>
                      {/* Sentiment */}
                      <td className="text-center py-4 px-4">
                        {sentiment != null ? (
                          <div className="flex items-center gap-2 justify-center">
                            <div className="w-12 h-1.5 rounded-full bg-surface-3 overflow-hidden">
                              <div
                                className={clsx(
                                  'h-full rounded-full',
                                  sentiment >= 65 ? 'bg-gain' : sentiment >= 45 ? 'bg-warning' : 'bg-loss'
                                )}
                                style={{ width: `${sentiment}%` }}
                              />
                            </div>
                            <span className="text-[11px] font-mono tabular-nums text-text-secondary">{sentiment}</span>
                          </div>
                        ) : (
                          <span className="text-[12px] font-mono text-text-tertiary">—</span>
                        )}
                      </td>
                    </>
                  )
                })()}

                {/* Actions column */}
                {!compact && (
                  <td className="text-center py-4 pl-4">
                    <div className="flex items-center justify-center gap-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/research?ticker=${pos.symbol}`)
                        }}
                        className="p-1.5 rounded-md text-text-tertiary hover:text-accent hover:bg-accent/[0.08] transition-all"
                        title={`Research ${pos.symbol}`}
                      >
                        <Search className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          const params = new URLSearchParams({ ticker: pos.symbol })
                          if (pos.avgCost > 0) params.set('cost_basis', pos.avgCost.toFixed(2))
                          if (pos.shares > 0) params.set('shares', pos.shares.toString())
                          navigate(`/holding-review?${params.toString()}`)
                        }}
                        className="p-1.5 rounded-md text-text-tertiary hover:text-warning hover:bg-warning/[0.08] transition-all"
                        title={`Upgrade ${pos.symbol}`}
                      >
                        <RefreshCw className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
