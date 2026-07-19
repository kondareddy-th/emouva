import clsx from 'clsx'
import { usePeerComparison, type PeerMetric } from '../hooks/usePeerComparison'

function fmt(v: number | null, kind: string): string {
  if (v === null || v === undefined) return '—'
  if (kind === 'money') {
    const a = Math.abs(v)
    for (const [d, s] of [[1e12, 'T'], [1e9, 'B'], [1e6, 'M']] as [number, string][]) {
      if (a >= d) return `$${(v / d).toFixed(1)}${s}`
    }
    return `$${v.toFixed(0)}`
  }
  if (kind === 'pct') return `${(v * 100).toFixed(0)}%`
  if (kind === 'x') return `${v.toFixed(0)}x`
  return String(v)
}

const rankColor = (pct: number) =>
  pct >= 66 ? 'bg-gain/10 text-gain' : pct >= 33 ? 'bg-warning/10 text-warning' : 'bg-loss/10 text-loss'

export default function PeerComparison({ ticker }: { ticker: string }) {
  const { data, loading } = usePeerComparison(ticker)

  if (loading && !data) {
    return (
      <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 text-center">
        <p className="text-[12px] text-text-tertiary font-serif italic">Comparing to industry peers…</p>
      </div>
    )
  }
  if (!data || data.peers.length < 2) return null
  const cols = data.metrics

  return (
    <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
      <div className="px-4 py-3 border-b border-[rgba(180,220,190,0.10)] flex items-center gap-2.5">
        <span className="w-[6px] h-[6px] bg-accent rotate-45 flex-shrink-0" />
        <h3 className="text-[14px] font-serif font-medium text-text-primary">
          vs {data.peer_group} peers
        </h3>
      </div>

      {/* target's rank per metric */}
      <div className="px-4 py-3 flex flex-wrap gap-2 border-b border-[rgba(180,220,190,0.10)]">
        {cols.filter((c) => data.ranks[c.key]).map((c) => {
          const r = data.ranks[c.key]
          return (
            <span key={c.key} className={clsx('text-[11px] px-2 py-1 rounded-md font-mono font-tabular', rankColor(r.percentile))}>
              {c.label}: #{r.rank}/{r.of}
            </span>
          )
        })}
      </div>

      {/* peer table — mono tabular columns, gold-tint header */}
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="text-text-tertiary bg-accent/[0.05]">
              <th className="text-left px-4 py-2.5 font-medium text-[9.5px] uppercase tracking-[0.1em]">Company</th>
              {cols.map((c) => (
                <th key={c.key} className="text-right px-3 py-2.5 font-medium text-[9.5px] uppercase tracking-[0.1em] whitespace-nowrap">{c.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.peers.map((p: PeerMetric) => {
              const isTarget = p.symbol === data.symbol
              return (
                <tr key={p.symbol} className={clsx('border-t border-[rgba(180,220,190,0.06)]', isTarget && 'bg-accent/[0.05]')}>
                  <td className="px-4 py-2">
                    <span className={clsx('font-mono font-medium', isTarget ? 'text-accent' : 'text-text-primary')}>{p.symbol}</span>
                  </td>
                  {cols.map((c) => (
                    <td
                      key={c.key}
                      className={clsx('text-right px-3 py-2 font-mono font-tabular whitespace-nowrap', isTarget ? 'text-[#E9D6A2]' : 'text-text-secondary')}
                    >
                      {fmt((p as unknown as Record<string, number | null>)[c.key], c.fmt)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
