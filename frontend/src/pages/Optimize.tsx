import { useSearchParams } from 'react-router-dom'
import clsx from 'clsx'
import { Target, Zap, RefreshCw } from 'lucide-react'
import Diversify from './Diversify'
import StressTest from './StressTest'
import HoldingReview from './HoldingReview'
import ModeToggle from '../components/ModeToggle'

const TABS = [
  { id: 'diversify', label: 'Diversify', icon: Target, Comp: Diversify, blurb: 'Balance allocation & cut concentration' },
  { id: 'stress', label: 'Stress Test', icon: Zap, Comp: StressTest, blurb: 'See how shocks hit your portfolio' },
  { id: 'upgrade', label: 'Upgrade', icon: RefreshCw, Comp: HoldingReview, blurb: 'Find stronger replacements for weak holdings' },
] as const

/** One super-page for the three portfolio-optimization tools, switched by a
 *  header sub-menu. Old routes (/diversify, /stress-test, /holding-review) render
 *  this with a defaultTab so existing links — and their query params (e.g.
 *  ?ticker=) — keep working. */
export default function Optimize({ defaultTab }: { defaultTab?: string }) {
  const [params, setParams] = useSearchParams()
  const activeId = params.get('tab') ?? defaultTab ?? 'diversify'
  const active = TABS.find((t) => t.id === activeId) ?? TABS[0]
  const Active = active.Comp

  return (
    <div>
      {/* Header + sub-menu */}
      <div className="sticky top-0 z-20 bg-base/90 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="px-4 md:px-8 max-w-6xl mx-auto pt-5 pb-3">
          <div className="flex items-center justify-between mb-1.5">
            <div className="flex items-center gap-2.5">
              <div className="w-1.5 h-1.5 bg-accent rotate-45" />
              <h1 className="text-[22px] font-serif font-medium text-text-primary tracking-tight">Optimize</h1>
            </div>
            <ModeToggle active="risk" variant="navy" />
          </div>
          <p className="text-[13px] text-text-secondary mb-4 leading-relaxed">{active.blurb}</p>
          <div className="flex gap-1 p-1 rounded-lg bg-surface-2 border border-[rgba(180,220,190,0.12)] w-fit">
            {TABS.map((t) => {
              const Icon = t.icon
              const on = active.id === t.id
              return (
                <button
                  key={t.id}
                  onClick={() => {
                    const next = new URLSearchParams(params)
                    next.set('tab', t.id)
                    setParams(next, { replace: true })
                  }}
                  className={clsx(
                    'flex items-center gap-2 px-3.5 md:px-4 py-2 rounded-md text-[13px] font-medium transition-colors',
                    on
                      ? 'bg-accent text-base'
                      : 'text-text-tertiary hover:text-text-secondary hover:bg-[rgba(207,174,98,0.05)]'
                  )}
                >
                  <Icon className={clsx('w-4 h-4', on ? 'text-base' : 'text-text-tertiary')} strokeWidth={1.75} />
                  {t.label}
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Active tool */}
      <Active embedded />
    </div>
  )
}
