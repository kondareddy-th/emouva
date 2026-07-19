import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Link2, Link2Off, Loader2, CheckCircle, AlertCircle, Eye, EyeOff, Trash2, Database, Shield, User, LogOut, KeyRound, Wallet, RotateCcw } from 'lucide-react'
import clsx from 'clsx'
import { apiFetch } from '../api/client'
import { useAuthStatus } from '../hooks/usePortfolio'
import { syncPortfolio } from '../hooks/usePortfolioStore'
import SyncButton from '../components/SyncButton'
import NotificationsBell from '../components/Notifications'
import ModeToggle from '../components/ModeToggle'
import useAuth from '../hooks/useAuth'
import {
  getCredentials,
  setCredential,
  getItem,
  clearCredentials,
  hasRobinhoodCreds,
} from '../hooks/useCredentialStore'

type ConnectState = 'idle' | 'connecting' | 'connected' | 'failed' | 'challenge'

interface BillingDetails {
  plan: string; source?: string; status?: string | null; started_at?: string | null; current_period_end?: string | null
  cancel_at_period_end?: boolean; amount_usd?: number
  card?: { brand: string; last4: string; exp_month: number; exp_year: number } | null
  invoices?: { date: string; amount_usd: number; status: string; receipt_url?: string }[]
}
const fmtDate = (s?: string | null) => s ? new Date(s).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'

interface PaperAcct {
  account_number: string
  nickname: string
  cash: number
  starting_cash: number
  realized_pnl: number
}

export default function Settings() {
  const auth = useAuthStatus()
  const { user, logout, refreshUser } = useAuth()
  const navigate = useNavigate()

  // Paper trading + stable public id
  const [paper, setPaper] = useState<PaperAcct[]>([])
  const [paperBusy, setPaperBusy] = useState(false)
  const [depositAmt, setDepositAmt] = useState('')
  const [publicId, setPublicId] = useState<string | null>((user as any)?.public_id ?? null)

  // Robinhood state
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [mfaCode, setMfaCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [rememberCreds, setRememberCreds] = useState(hasRobinhoodCreds())
  const [state, setState] = useState<ConnectState>(auth.connected ? 'connected' : 'idle')
  const [message, setMessage] = useState('')

  // Cache stats
  const [cacheCount, setCacheCount] = useState(0)

  // ── AI Token (bring your own Anthropic key) — stored only in this browser ──
  const [aiKey, setAiKey] = useState(getItem('anthropic_key'))
  const [showKey, setShowKey] = useState(false)
  const [aiSaved, setAiSaved] = useState(false)
  const saveAiKey = () => { setCredential('anthropic_key', aiKey.trim()); setAiSaved(true); setTimeout(() => setAiSaved(false), 2500) }
  const clearAiKey = () => { setCredential('anthropic_key', ''); setAiKey(''); setAiSaved(false) }

  useEffect(() => {
    // Load saved credentials
    const creds = getCredentials()
    if (creds.robinhoodUsername) {
      setUsername(creds.robinhoodUsername)
    }
    // Count cache entries
    updateCacheCount()
    // Paper accounts + freshest public id
    apiFetch<{ accounts: PaperAcct[] }>('/api/paper/accounts').then((r) => setPaper(r.accounts || [])).catch(() => {})
    apiFetch<{ public_id: string }>('/api/users/me').then((r) => setPublicId(r.public_id)).catch(() => {})
  }, [])

  const reloadPaper = async () => {
    const r = await apiFetch<{ accounts: PaperAcct[] }>('/api/paper/accounts')
    setPaper(r.accounts || [])
  }
  const createPaper = async () => {
    setPaperBusy(true)
    try {
      await apiFetch('/api/paper/accounts', { method: 'POST' })
      await reloadPaper()
    } finally { setPaperBusy(false) }
  }
  const resetPaper = async (n: string) => {
    setPaperBusy(true)
    try {
      await apiFetch(`/api/paper/accounts/${encodeURIComponent(n)}/reset`, { method: 'POST' })
      await reloadPaper()
    } finally { setPaperBusy(false) }
  }
  const depositPaper = async (n: string) => {
    const amt = Number(depositAmt) || 0
    if (amt <= 0) return
    setPaperBusy(true)
    try {
      await apiFetch(`/api/paper/accounts/${encodeURIComponent(n)}/deposit`, { method: 'POST', body: JSON.stringify({ amount: amt }) })
      setDepositAmt(''); await reloadPaper()
    } finally { setPaperBusy(false) }
  }

  // Reflect OAuth return (?robinhood=connected|error) + live agentic-MCP status.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const rh = params.get('robinhood')
    if (rh === 'connected') {
      setState('connected')
      setMessage('Robinhood connected via the official agentic MCP.')
      window.history.replaceState({}, '', window.location.pathname)
    } else if (rh === 'error') {
      setState('failed')
      setMessage('Robinhood authorization was cancelled or failed. Please try again.')
      window.history.replaceState({}, '', window.location.pathname)
    }
    apiFetch<{ connected: boolean }>('/api/robinhood/status')
      .then((s) => { if (s.connected) setState('connected') })
      .catch(() => {})
  }, [])

  const updateCacheCount = () => {
    let count = 0
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith('emouva_') && !key.startsWith('emouva_cred_')) {
        count++
      }
    }
    setCacheCount(count)
  }

  const handleConnect = async () => {
    // OAuth via Robinhood's official agentic MCP — redirect the user to authorize.
    setState('connecting')
    setMessage('Redirecting to Robinhood to authorize…')
    try {
      const res = await apiFetch<{ authorize_url: string }>('/api/robinhood/connect')
      window.location.href = res.authorize_url
    } catch (err: any) {
      setState('failed')
      setMessage(err.message || 'Failed to start Robinhood connection')
    }
  }

  const handleDisconnect = async () => {
    try {
      await apiFetch('/api/robinhood/disconnect', { method: 'POST' })
      setState('idle')
      setMessage('')
      auth.refetch()
    } catch {
      setMessage('Failed to disconnect')
    }
  }

  const handleClearCache = () => {
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith('emouva_') && !key.startsWith('emouva_cred_')) {
        keys.push(key)
      }
    }
    keys.forEach(k => localStorage.removeItem(k))
    updateCacheCount()
  }

  const handleClearAll = () => {
    clearCredentials()
    handleClearCache()
    setUsername('')
    setPassword('')
    setRememberCreds(false)
    setAiKey('')
    setAiSaved(false)
  }

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const isConnected = state === 'connected' || auth.connected

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <div className="sticky top-0 z-30 bg-base/80 backdrop-blur-xl border-b border-[rgba(180,220,190,0.10)]">
        <div className="flex items-center justify-between px-8 h-14">
          <h1 className="text-[18px] font-serif font-medium tracking-tight text-text-primary">Settings</h1>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            <SyncButton />
            <NotificationsBell />
          </div>
        </div>
        <div className="header-gradient-line" />
      </div>

      <div className="px-8 py-8 max-w-2xl space-y-8">

        {/* ── Section 0: Account ── */}
        {user && (
          <div>
            <div className="flex items-center gap-2 mb-4">
              <User className="w-4 h-4 text-accent" />
              <h2 className="text-[11px] font-mono uppercase tracking-[0.13em] text-text-tertiary">Account</h2>
            </div>
            <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6">
              <div className="flex items-center gap-4 mb-5">
                <div className="w-12 h-12 rounded-[10px] bg-accent/10 flex items-center justify-center text-[18px] font-serif font-medium text-accent">
                  {user.display_name?.charAt(0).toUpperCase() ?? '?'}
                </div>
                <div>
                  <h3 className="text-[16px] font-serif font-medium text-text-primary">{user.display_name}</h3>
                  <p className="text-[13px] font-mono text-text-tertiary">@{user.username}</p>
                  {publicId && (
                    <p className="text-[11px] font-mono text-text-tertiary/70 mt-0.5" title="Your stable account id">{publicId}</p>
                  )}
                </div>
              </div>

              <div className="border-t border-[rgba(180,220,190,0.06)] pt-4">
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2 px-4 py-2 rounded-[6px] text-[13px] font-medium bg-loss/10 text-loss hover:bg-loss/20 transition-colors"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  Sign out
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Section 1: AI Token (bring your own Anthropic key) ── */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <KeyRound className="w-4 h-4 text-accent" />
            <h2 className="text-[11px] font-mono uppercase tracking-[0.13em] text-text-tertiary">AI Token</h2>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6">
            <h3 className="text-[15px] font-serif font-medium text-text-primary">Your Anthropic API key</h3>
            <p className="text-[12px] text-text-tertiary mt-0.5 mb-4 leading-relaxed max-w-lg">
              Emouva is free &amp; open source — the AI runs on <span className="text-text-secondary">your own</span> Anthropic
              key. It's stored only in this browser and sent directly with your requests; we never keep it on a server.
              Get one at <a href="https://console.anthropic.com/settings/keys" target="_blank" rel="noreferrer" className="text-accent">console.anthropic.com</a>. New here?
              Review how the Partner thinks and trades in <Link to="/trading/principles" className="text-accent">Trading → Principles</Link> before you let it run.
            </p>
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1 flex-1 rounded-[6px] bg-base border border-[rgba(180,220,190,0.12)] px-2.5 py-2">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={aiKey}
                  onChange={(e) => setAiKey(e.target.value)}
                  placeholder="sk-ant-…"
                  className="w-full bg-transparent text-[13px] font-mono text-text-primary placeholder:text-text-tertiary focus:outline-none"
                />
                <button onClick={() => setShowKey((v) => !v)} className="text-text-tertiary hover:text-text-secondary">
                  {showKey ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
              <button onClick={saveAiKey} className="px-4 py-2 rounded-[6px] text-[13px] font-medium bg-accent text-base hover:bg-accent-hover whitespace-nowrap">Save</button>
              {aiKey && (
                <button onClick={clearAiKey} className="px-3 py-2 rounded-[6px] text-[13px] font-medium bg-loss/10 text-loss hover:bg-loss/20 whitespace-nowrap">Remove</button>
              )}
            </div>
            {aiSaved && <p className="text-[11px] text-gain mt-2">✓ Saved in this browser.</p>}
          </div>
        </div>

        {/* ── Section 2: Robinhood Connection ── */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Link2 className="w-4 h-4 text-gain" />
            <h2 className="text-[11px] font-mono uppercase tracking-[0.13em] text-text-tertiary">Brokerage</h2>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] overflow-hidden">
            <div className="p-6">
              <div className="flex items-center justify-between mb-5">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-[10px] bg-[#00C805]/10 flex items-center justify-center">
                    <span className="text-[16px] font-bold text-[#00C805]">R</span>
                  </div>
                  <div>
                    <h3 className="text-[14px] font-serif font-medium text-text-primary">Robinhood</h3>
                    <p className="text-[12px] text-text-tertiary">
                      {isConnected ? 'Live portfolio data connected' : 'Connect your brokerage account'}
                    </p>
                  </div>
                </div>
                <StatusBadge connected={isConnected} />
              </div>

              {isConnected ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-gain/5 border border-gain/10">
                    <CheckCircle className="w-4 h-4 text-gain flex-shrink-0" />
                    <p className="text-[13px] text-text-secondary">
                      Your Robinhood account is connected. Portfolio data is live.
                    </p>
                  </div>
                  <button
                    onClick={handleDisconnect}
                    className="flex items-center gap-2 px-4 py-2 rounded-[6px] bg-loss/10 text-loss text-[13px] font-medium hover:bg-loss/20 transition-colors"
                  >
                    <Link2Off className="w-3.5 h-3.5" />
                    Disconnect
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="flex items-start gap-2 p-3 rounded-lg bg-accent/5 border border-accent/10">
                    <Shield className="w-4 h-4 text-accent flex-shrink-0 mt-0.5" />
                    <p className="text-[13px] text-text-secondary leading-relaxed">
                      Connect securely via Robinhood's official agent authorization. You'll be
                      redirected to Robinhood to approve — we never see your password, and the
                      agent only trades inside a dedicated, separately-funded Agentic account.
                    </p>
                  </div>

                  {message && (
                    <div className={clsx(
                      'flex items-start gap-2 p-3 rounded-lg border',
                      state === 'failed' ? 'bg-loss/5 border-loss/10' :
                      state === 'challenge' ? 'bg-warning/5 border-warning/10' :
                      state === 'connecting' ? 'bg-accent/5 border-accent/10' :
                      'bg-gain/5 border-gain/10'
                    )}>
                      {state === 'connecting' && <Loader2 className="w-4 h-4 text-accent animate-spin flex-shrink-0 mt-0.5" />}
                      {state === 'failed' && <AlertCircle className="w-4 h-4 text-loss flex-shrink-0 mt-0.5" />}
                      {state === 'challenge' && <AlertCircle className="w-4 h-4 text-warning flex-shrink-0 mt-0.5" />}
                      <p className="text-[13px] text-text-secondary">{message}</p>
                    </div>
                  )}

                  <button
                    onClick={handleConnect}
                    disabled={state === 'connecting'}
                    className={clsx(
                      'flex items-center justify-center gap-2 w-full px-4 py-2.5 rounded-[8px] text-[14px] font-medium transition-all',
                      state === 'connecting'
                        ? 'bg-accent/20 text-accent cursor-not-allowed'
                        : 'bg-accent text-base hover:bg-accent-hover'
                    )}
                  >
                    {state === 'connecting' ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Redirecting…
                      </>
                    ) : (
                      <>
                        <Link2 className="w-4 h-4" />
                        Connect Robinhood
                      </>
                    )}
                  </button>

                  <p className="text-[11px] text-text-tertiary leading-relaxed">
                    Uses Robinhood's official agentic MCP over OAuth. You can revoke access anytime
                    here or from your Robinhood app.
                  </p>
                </div>
              )}
            </div>

            <div className="border-t border-[rgba(180,220,190,0.10)] p-6 opacity-50">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-[10px] bg-[rgba(207,174,98,0.06)] flex items-center justify-center">
                  <span className="text-[16px] font-bold text-text-tertiary">+</span>
                </div>
                <div>
                  <h3 className="text-[14px] font-serif font-medium text-text-tertiary">More Brokerages</h3>
                  <p className="text-[12px] text-text-tertiary">
                    Interactive Brokers, Schwab, Fidelity — coming soon
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ── Section 2b: Paper Trading ── */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Wallet className="w-4 h-4 text-gain" />
            <h2 className="text-[11px] font-mono uppercase tracking-[0.13em] text-text-tertiary">Paper Trading</h2>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6">
            <div className="flex items-start justify-between mb-5">
              <div>
                <h3 className="text-[15px] font-serif font-medium text-text-primary">Paper Money Account</h3>
                <p className="text-[12px] text-text-tertiary mt-0.5 max-w-md leading-relaxed">
                  A simulated account funded with virtual cash. When the agent runs in
                  <span className="text-text-secondary"> paper</span> mode it trades here — so you can watch it work before risking real money. Appears in the account switcher alongside your brokerage accounts.
                </p>
              </div>
            </div>

            {paper.length === 0 ? (
              <button
                onClick={createPaper}
                disabled={paperBusy}
                className={clsx(
                  'flex items-center justify-center gap-2 px-4 py-2.5 rounded-[8px] text-[14px] font-medium transition-all',
                  paperBusy ? 'bg-accent/20 text-accent cursor-not-allowed' : 'bg-accent text-base hover:bg-accent-hover'
                )}
              >
                {paperBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wallet className="w-4 h-4" />}
                Create paper account
              </button>
            ) : (
              <div className="space-y-3">
                {paper.map((p) => (
                  <div key={p.account_number} className="p-4 rounded-[8px] bg-[rgba(127,227,169,0.04)] border border-[rgba(127,227,169,0.12)]">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-[13px] font-medium text-text-primary">{p.nickname}</span>
                        <span className="text-[11px] font-mono text-text-tertiary">{p.account_number}</span>
                      </div>
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-[0.11em] bg-gain/10 text-gain">Paper</span>
                    </div>
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Cash</p>
                        <p className="text-[15px] font-mono tabular-nums text-text-primary">${p.cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Funded with</p>
                        <p className="text-[15px] font-mono tabular-nums text-text-secondary">${p.starting_cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
                      </div>
                      <div>
                        <p className="text-[10px] font-mono uppercase tracking-[0.11em] text-text-tertiary mb-1">Realized P&L</p>
                        <p className={clsx('text-[15px] font-mono tabular-nums', p.realized_pnl >= 0 ? 'text-gain' : 'text-loss')}>
                          {p.realized_pnl >= 0 ? '+' : '−'}${Math.abs(p.realized_pnl).toLocaleString(undefined, { maximumFractionDigits: 0 })}
                        </p>
                      </div>
                    </div>
                    {/* Add paper money (recorded as a deposit) */}
                    <div className="flex items-center gap-2 mb-3">
                      <div className="flex items-center gap-1 flex-1 max-w-[220px] rounded-[6px] bg-base border border-[rgba(180,220,190,0.12)] px-2.5 py-1.5">
                        <span className="text-[13px] text-text-tertiary">$</span>
                        <input
                          type="number" min={0} step={1000} value={depositAmt}
                          onChange={(e) => setDepositAmt(e.target.value)}
                          placeholder="Add paper money"
                          className="w-full bg-transparent text-[13px] font-mono tabular-nums text-text-primary placeholder:text-text-tertiary focus:outline-none"
                        />
                      </div>
                      <button
                        onClick={() => depositPaper(p.account_number)}
                        disabled={paperBusy || !(Number(depositAmt) > 0)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] text-[12px] font-medium bg-gain/10 text-gain hover:bg-gain/20 transition-colors disabled:opacity-40"
                      >
                        {paperBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wallet className="w-3 h-3" />}
                        Add funds
                      </button>
                    </div>
                    <button
                      onClick={() => resetPaper(p.account_number)}
                      disabled={paperBusy}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] text-[12px] font-medium bg-warning/10 text-warning hover:bg-warning/20 transition-colors disabled:opacity-50"
                    >
                      {paperBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                      Reset (wipe positions, restore cash)
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── Section 3: Cache & Privacy ── */}
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-4 h-4 text-warning" />
            <h2 className="text-[11px] font-mono uppercase tracking-[0.13em] text-text-tertiary">Data & Privacy</h2>
          </div>
          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-6 space-y-5">

            {/* Cache info */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Database className="w-4 h-4 text-text-tertiary" />
                <div>
                  <h3 className="text-[14px] font-serif font-medium text-text-primary">Browser Cache</h3>
                  <p className="text-[12px] text-text-tertiary">
                    {cacheCount} cached item{cacheCount !== 1 ? 's' : ''} (research results, news, daily briefs)
                  </p>
                </div>
              </div>
              <button
                onClick={handleClearCache}
                disabled={cacheCount === 0}
                className={clsx(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-[6px] text-[12px] font-medium transition-colors',
                  cacheCount > 0
                    ? 'bg-warning/10 text-warning hover:bg-warning/20'
                    : 'bg-surface-3 text-text-tertiary cursor-not-allowed'
                )}
              >
                <Trash2 className="w-3 h-3" />
                Clear Cache
              </button>
            </div>

            <div className="border-t border-[rgba(180,220,190,0.06)]" />

            {/* Privacy notice */}
            <div className="p-4 rounded-[8px] bg-[rgba(207,174,98,0.04)] border border-[rgba(180,220,190,0.06)]">
              <h4 className="text-[13px] font-serif font-medium text-text-primary mb-2">Your data stays in your browser</h4>
              <ul className="space-y-1.5 text-[12px] text-text-tertiary leading-relaxed">
                <li className="flex items-baseline gap-2"><span className="w-1 h-1 rotate-45 bg-accent flex-none translate-y-[3px]" />Robinhood credentials are sent directly to Robinhood, not stored on our server</li>
                <li className="flex items-baseline gap-2"><span className="w-1 h-1 rotate-45 bg-accent flex-none translate-y-[3px]" />AI analysis results are cached locally for 24 hours</li>
                <li className="flex items-baseline gap-2"><span className="w-1 h-1 rotate-45 bg-accent flex-none translate-y-[3px]" />No analytics or tracking — this is your personal tool</li>
              </ul>
            </div>

            <div className="border-t border-[rgba(180,220,190,0.06)]" />

            {/* Clear all */}
            <button
              onClick={handleClearAll}
              className="flex items-center gap-2 px-4 py-2 rounded-[6px] text-[13px] font-medium bg-loss/10 text-loss hover:bg-loss/20 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear All Data (credentials + cache)
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <div className={clsx(
      'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium',
      connected
        ? 'bg-gain/10 text-gain'
        : 'bg-surface-3 text-text-tertiary'
    )}>
      <div className={clsx(
        'w-1.5 h-1.5 rounded-full',
        connected ? 'bg-gain animate-pulse' : 'bg-text-tertiary'
      )} />
      {connected ? 'LIVE' : 'Not Connected'}
    </div>
  )
}
