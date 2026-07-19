import { useState, useEffect, useCallback } from 'react'
import {
  Plus,
  Loader2,
  Play,
  Trash2,
  ToggleLeft,
  ToggleRight,
  ChevronDown,
  Zap,
  Clock,
  AlertCircle,
  CheckCircle,
  XCircle,
} from 'lucide-react'
import clsx from 'clsx'
import { apiFetch } from '../api/client'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'
import ModeToggle from '../components/ModeToggle'

interface BuyRule {
  id: string
  symbol: string
  drop_pct: number
  market_benchmark: string
  market_drop_pct: number
  max_excess_drop_pct: number
  buy_amount_usd: number
  is_active: boolean
  check_interval_hours: number
  last_checked_at: string | null
  last_triggered_at: string | null
  created_at: string
}

interface Execution {
  id: string
  rule_id: string
  symbol: string
  trigger_price: number
  avg_cost: number
  market_drop_pct_actual: number
  stock_drop_pct_actual: number
  buy_amount_usd: number
  shares_bought: number | null
  order_id: string | null
  status: string
  error_message: string | null
  executed_at: string | null
  created_at: string
}

const defaultForm = {
  symbol: '',
  drop_pct: 10,
  market_benchmark: 'QQQ',
  market_drop_pct: 5,
  max_excess_drop_pct: 15,
  buy_amount_usd: 500,
  check_interval_hours: 48,
}

export default function BuyRules() {
  const [rules, setRules] = useState<BuyRule[]>([])
  const [executions, setExecutions] = useState<Execution[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(defaultForm)
  const [submitting, setSubmitting] = useState(false)
  const [checkingRule, setCheckingRule] = useState<string | null>(null)
  const [checkResult, setCheckResult] = useState<any>(null)
  const [showExecutions, setShowExecutions] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [rulesData, execData] = await Promise.all([
        apiFetch<BuyRule[]>('/api/rules'),
        apiFetch<Execution[]>('/api/rules/executions'),
      ])
      setRules(rulesData)
      setExecutions(execData)
    } catch {
      // silently fail
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchData() }, [fetchData])

  const createRule = async (e: React.FormEvent) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await apiFetch('/api/rules', {
        method: 'POST',
        body: JSON.stringify(form),
      })
      setForm(defaultForm)
      setShowForm(false)
      await fetchData()
    } catch {
      // handle error
    } finally {
      setSubmitting(false)
    }
  }

  const toggleRule = async (rule: BuyRule) => {
    await apiFetch(`/api/rules/${rule.id}`, {
      method: 'PUT',
      body: JSON.stringify({ is_active: !rule.is_active }),
    })
    await fetchData()
  }

  const deleteRule = async (ruleId: string) => {
    await apiFetch(`/api/rules/${ruleId}`, { method: 'DELETE' })
    await fetchData()
  }

  const checkNow = async (ruleId: string) => {
    setCheckingRule(ruleId)
    setCheckResult(null)
    try {
      const result = await apiFetch(`/api/rules/${ruleId}/check-now`, { method: 'POST' })
      setCheckResult(result)
      await fetchData()
    } catch {
      setCheckResult({ reason: 'Check failed' })
    } finally {
      setCheckingRule(null)
    }
  }

  const formatDate = (iso: string | null) => {
    if (!iso) return 'Never'
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-accent animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-screen">
      {/* Header */}
      <div className="sticky top-0 z-30 bg-base/80 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-4 md:px-8 h-14">
          <div className="flex items-center gap-3">
            <Zap className="w-4 h-4 text-warning" />
            <h1 className="text-[18px] font-serif font-medium tracking-tight text-text-primary">Dip-Buying Rules</h1>
          </div>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            <SyncButton />
            <NotificationsBell />
            <button
              onClick={() => setShowForm(!showForm)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] bg-accent text-base text-[13px] font-medium hover:bg-accent-hover transition-colors press-scale"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Rule
            </button>
          </div>
        </div>
        <div className="header-gradient-line" />
      </div>

      <div className="px-4 md:px-8 py-6 max-w-3xl">
        {/* Info banner */}
        <div className="rounded-[8px] bg-[rgba(207,174,98,0.06)] border border-[rgba(207,174,98,0.25)] px-4 py-3 mb-6">
          <p className="text-[12px] text-text-secondary leading-relaxed">
            Rules auto-buy when: stock drops X% below your avg cost <strong>AND</strong> the market benchmark is also down
            (ruling out company-specific problems). Rules are checked every 48 hours or on-demand.
          </p>
        </div>

        {/* Create Form */}
        {showForm && (
          <form onSubmit={createRule} className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-5 mb-6">
            <h3 className="text-[15px] font-serif font-medium text-text-primary mb-4">New Buy Rule</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Stock Symbol</label>
                <input
                  type="text"
                  value={form.symbol}
                  onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })}
                  className="w-full px-3 py-2 rounded-[8px] bg-[rgba(207,174,98,0.04)] border border-[rgba(180,220,190,0.12)] text-[13px] font-mono text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                  placeholder="AAPL"
                  required
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Drop % (from avg cost)</label>
                <input
                  type="number"
                  value={form.drop_pct}
                  onChange={(e) => setForm({ ...form, drop_pct: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-[8px] bg-[rgba(207,174,98,0.04)] border border-[rgba(180,220,190,0.12)] text-[13px] font-mono text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                  min={1}
                  max={100}
                  step={0.5}
                  required
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Market Benchmark</label>
                <input
                  type="text"
                  value={form.market_benchmark}
                  onChange={(e) => setForm({ ...form, market_benchmark: e.target.value.toUpperCase() })}
                  className="w-full px-3 py-2 rounded-[8px] bg-[rgba(207,174,98,0.04)] border border-[rgba(180,220,190,0.12)] text-[13px] font-mono text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                  placeholder="QQQ"
                  required
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Market Drop % (from 52w high)</label>
                <input
                  type="number"
                  value={form.market_drop_pct}
                  onChange={(e) => setForm({ ...form, market_drop_pct: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-[8px] bg-[rgba(207,174,98,0.04)] border border-[rgba(180,220,190,0.12)] text-[13px] font-mono text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                  min={1}
                  max={100}
                  step={0.5}
                  required
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Max Excess Drop %</label>
                <input
                  type="number"
                  value={form.max_excess_drop_pct}
                  onChange={(e) => setForm({ ...form, max_excess_drop_pct: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-[8px] bg-[rgba(207,174,98,0.04)] border border-[rgba(180,220,190,0.12)] text-[13px] font-mono text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                  min={1}
                  max={100}
                  step={0.5}
                />
              </div>
              <div>
                <label className="block text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Buy Amount ($)</label>
                <input
                  type="number"
                  value={form.buy_amount_usd}
                  onChange={(e) => setForm({ ...form, buy_amount_usd: Number(e.target.value) })}
                  className="w-full px-3 py-2 rounded-[8px] bg-[rgba(207,174,98,0.04)] border border-[rgba(180,220,190,0.12)] text-[13px] font-mono text-text-primary focus:outline-none focus:ring-1 focus:ring-accent"
                  min={1}
                  required
                />
              </div>
            </div>
            <div className="flex items-center gap-3 mt-5">
              <button
                type="submit"
                disabled={submitting || !form.symbol}
                className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 text-base text-[13px] font-medium rounded-[6px] transition-colors flex items-center gap-2"
              >
                {submitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                Create Rule
              </button>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="px-4 py-2 text-text-tertiary text-[13px] hover:text-text-secondary transition-colors"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Rules list */}
        {rules.length === 0 ? (
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-8 text-center">
            <Zap className="w-8 h-8 text-accent/40 mx-auto mb-3" />
            <p className="text-[15px] font-serif font-medium text-text-secondary mb-1">No buy rules yet</p>
            <p className="text-[12px] text-text-tertiary mb-4">
              Create a rule to automatically buy stocks when they dip during a market downturn.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className={clsx(
                  'rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-4 transition-opacity',
                  !rule.is_active && 'opacity-50'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-[15px] font-mono font-medium text-text-primary">{rule.symbol}</span>
                      <span className={clsx(
                        'text-[10px] font-mono uppercase tracking-[0.08em] px-1.5 py-0.5 rounded-[4px]',
                        rule.is_active ? 'bg-gain/10 text-gain' : 'bg-[rgba(207,174,98,0.06)] text-text-tertiary'
                      )}>
                        {rule.is_active ? 'Active' : 'Paused'}
                      </span>
                    </div>
                    <div className="text-[12px] text-text-tertiary space-y-0.5">
                      <p>Buy <span className="font-mono text-text-secondary">${rule.buy_amount_usd}</span> when down <strong className="font-mono text-accent">{rule.drop_pct}%</strong> from avg cost</p>
                      <p>Requires {rule.market_benchmark} down <strong className="font-mono text-accent">{rule.market_drop_pct}%</strong> from 52w high</p>
                      <p>Max excess drop: <span className="font-mono text-text-secondary">{rule.max_excess_drop_pct}%</span></p>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-[11px] text-text-tertiary">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        Checked: <span className="font-mono">{formatDate(rule.last_checked_at)}</span>
                      </span>
                      {rule.last_triggered_at && (
                        <span className="flex items-center gap-1 text-warning">
                          <Zap className="w-3 h-3" />
                          Triggered: <span className="font-mono">{formatDate(rule.last_triggered_at)}</span>
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => checkNow(rule.id)}
                      disabled={checkingRule === rule.id}
                      className="flex items-center gap-1 px-2 py-1 rounded-[6px] hover:bg-[rgba(207,174,98,0.04)] transition-colors text-text-tertiary hover:text-accent disabled:opacity-50 text-[11px] font-medium"
                    >
                      {checkingRule === rule.id ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Play className="w-3.5 h-3.5" />
                      )}
                      <span className="hidden sm:inline">Check</span>
                    </button>
                    <button
                      onClick={() => toggleRule(rule)}
                      className="flex items-center gap-1 px-2 py-1 rounded-[6px] hover:bg-[rgba(207,174,98,0.04)] transition-colors text-text-tertiary text-[11px] font-medium"
                    >
                      {rule.is_active ? (
                        <ToggleRight className="w-3.5 h-3.5 text-gain" />
                      ) : (
                        <ToggleLeft className="w-3.5 h-3.5" />
                      )}
                      <span className="hidden sm:inline">{rule.is_active ? 'Pause' : 'Resume'}</span>
                    </button>
                    <button
                      onClick={() => deleteRule(rule.id)}
                      className="flex items-center gap-1 px-2 py-1 rounded-[6px] hover:bg-[rgba(207,174,98,0.04)] transition-colors text-text-tertiary hover:text-loss text-[11px] font-medium"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                      <span className="hidden sm:inline">Delete</span>
                    </button>
                  </div>
                </div>

                {/* Check result */}
                {checkResult && checkResult.rule_id === rule.id && (
                  <div className={clsx(
                    'mt-3 px-3 py-2 rounded-[8px] text-[12px]',
                    checkResult.triggered ? 'bg-gain/10 text-gain' : 'bg-[rgba(207,174,98,0.05)] text-text-tertiary'
                  )}>
                    {checkResult.triggered ? (
                      <span className="flex items-center gap-1.5">
                        <CheckCircle className="w-3.5 h-3.5" />
                        {checkResult.reason}
                      </span>
                    ) : (
                      <span className="flex items-center gap-1.5">
                        <AlertCircle className="w-3.5 h-3.5" />
                        {checkResult.reason}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Execution History */}
        {executions.length > 0 && (
          <div className="mt-8">
            <button
              onClick={() => setShowExecutions(!showExecutions)}
              className="flex items-center gap-2 text-[13px] font-medium text-text-secondary hover:text-text-primary transition-colors mb-3"
            >
              <ChevronDown className={clsx('w-4 h-4 transition-transform', showExecutions && 'rotate-180')} />
              Execution History ({executions.length})
            </button>
            {showExecutions && (
              <div className="space-y-2">
                {executions.map((exec) => (
                  <div
                    key={exec.id}
                    className="rounded-[8px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-3 flex items-center gap-3"
                  >
                    {exec.status === 'executed' ? (
                      <CheckCircle className="w-4 h-4 text-gain flex-shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-loss flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-mono font-medium text-text-primary">{exec.symbol}</span>
                        <span className={clsx(
                          'text-[10px] font-mono uppercase tracking-[0.08em] px-1.5 py-0.5 rounded-[4px]',
                          exec.status === 'executed' ? 'bg-gain/10 text-gain' : 'bg-loss/10 text-loss'
                        )}>
                          {exec.status}
                        </span>
                      </div>
                      <p className="text-[11px] font-mono text-text-tertiary mt-0.5">
                        ${exec.buy_amount_usd} at ${exec.trigger_price.toFixed(2)} · Stock -{exec.stock_drop_pct_actual.toFixed(1)}% · Market -{exec.market_drop_pct_actual.toFixed(1)}%
                      </p>
                    </div>
                    <span className="text-[11px] font-mono text-text-tertiary flex-shrink-0">
                      {formatDate(exec.executed_at || exec.created_at)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
