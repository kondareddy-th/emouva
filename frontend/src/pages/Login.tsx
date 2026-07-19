import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Eye, EyeOff } from 'lucide-react'
import useAuth from '../hooks/useAuth'
import LegalModal, { type LegalDoc } from '../components/LegalDocs'

const POINTS = [
  'Checks the market every 30 minutes — and, most days, does nothing.',
  'Trades only under a mandate you write, in plain English.',
  'Asks your approval for anything over your limit.',
  'Explains every action in a Ledger you can audit — starting on paper money.',
]

const Dia = ({ className = '' }: { className?: string }) => (
  <div className={`bg-accent rotate-45 flex-none ${className}`} />
)

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [legal, setLegal] = useState<LegalDoc | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const u = await login(username, password)
      navigate(u?.full_access === false ? '/community' : '/')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-base text-text-primary flex">
      {/* ── Left: the pitch (agentic trading) ── */}
      <div className="hidden lg:flex flex-1 flex-col justify-center px-16 xl:px-24 border-r border-[rgba(180,220,190,0.10)]">
        <Link to="/" className="flex items-center gap-2.5 mb-10">
          <Dia className="w-2.5 h-2.5" />
          <span className="font-mono text-[13px] tracking-[0.22em] text-[#E9D6A2]">EMOUVA</span>
          <span className="text-[8.5px] font-mono font-medium tracking-[0.12em] text-accent border border-accent/40 rounded-[3px] px-1 py-[1px] leading-none ml-1.5">BETA</span>
        </Link>

        <div className="flex items-center gap-2 mb-4">
          <Dia className="w-1.5 h-1.5" />
          <span className="font-mono text-[11px] tracking-[0.16em] text-accent">AGENTIC TRADING · UNDER A HUMAN MANDATE</span>
        </div>
        <h1 className="font-serif font-medium text-[44px] leading-[1.08] tracking-tight mb-4">
          Hire a partner,
          <br />
          <span className="text-accent">not another app.</span>
        </h1>
        <p className="text-[16px] text-text-secondary leading-relaxed max-w-md mb-9">
          Emouva runs your portfolio the way the best investors actually work — screen
          everything, buy rarely, explain every move.
        </p>

        <div className="flex flex-col gap-3.5 max-w-lg">
          {POINTS.map((p) => (
            <div key={p} className="flex items-baseline gap-3">
              <Dia className="w-1.5 h-1.5 relative -top-px" />
              <span className="text-[13.5px] text-text-secondary leading-relaxed">{p}</span>
            </div>
          ))}
        </div>

        <div className="border-t border-[rgba(180,220,190,0.10)] mt-9 pt-6 max-w-lg">
          <p className="font-serif italic text-[15px] text-accent leading-snug m-0">
            "The big money is not in the buying and the selling, but in the waiting."
          </p>
          <p className="font-mono text-[10px] tracking-[0.13em] text-text-tertiary mt-2">
            — CHARLIE MUNGER · THE PARTNER'S TEMPERAMENT
          </p>
        </div>
      </div>

      {/* ── Right: sign in ── */}
      <div className="flex-1 lg:max-w-md xl:max-w-lg flex flex-col items-center justify-center px-6">
        <div className="w-full max-w-sm">
          {/* Mobile header */}
          <div className="lg:hidden mb-8">
            <Link to="/" className="flex items-center justify-center gap-2.5 mb-4">
              <Dia className="w-2.5 h-2.5" />
              <span className="font-mono text-[13px] tracking-[0.22em] text-[#E9D6A2]">EMOUVA</span>
          <span className="text-[8.5px] font-mono font-medium tracking-[0.12em] text-accent border border-accent/40 rounded-[3px] px-1 py-[1px] leading-none ml-1.5">BETA</span>
            </Link>
            <p className="text-center font-mono text-[10px] uppercase tracking-[0.14em] text-text-tertiary">
              Agentic trading · under your mandate
            </p>
          </div>

          <div className="rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] p-7">
            <h1 className="font-serif font-medium text-[24px] text-text-primary mb-1">Welcome back</h1>
            <p className="text-[13px] text-text-secondary mb-6">Sign in to your Partner.</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1.5">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-[8px] bg-base border border-[rgba(180,220,190,0.12)] text-[14px] text-text-primary placeholder-text-tertiary/60 focus:outline-none focus:border-accent/60 transition-colors"
                  placeholder="Enter username"
                  autoFocus
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1.5">
                  Password
                </label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3.5 py-2.5 pr-10 rounded-[8px] bg-base border border-[rgba(180,220,190,0.12)] text-[14px] text-text-primary placeholder-text-tertiary/60 focus:outline-none focus:border-accent/60 transition-colors"
                    placeholder="Enter password"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-text-tertiary hover:text-text-secondary transition-colors"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" strokeWidth={1.5} /> : <Eye className="w-4 h-4" strokeWidth={1.5} />}
                  </button>
                </div>
              </div>

              {error && (
                <p className="text-[12px] text-loss bg-loss/10 px-3.5 py-2.5 rounded-[8px]">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading || !username || !password}
                className="w-full py-3 bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-base text-[14px] font-semibold rounded-[8px] transition-colors flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                {loading ? 'Signing in...' : 'Sign in'}
              </button>
            </form>

            <div className="mt-4 text-center">
              <Link to="/trading" className="text-[12px] text-text-tertiary hover:text-accent transition-colors">
                Or watch it work — the live demo →
              </Link>
            </div>
          </div>

          <p className="text-center text-[13px] text-text-secondary mt-5">
            Don't have an account?{' '}
            <Link to="/signup" className="text-accent hover:text-accent-hover transition-colors font-medium">
              Open an account
            </Link>
          </p>

          <p className="text-center text-[11px] text-text-tertiary/70 mt-4 leading-relaxed">
            By signing in, you agree to our{' '}
            <span onClick={() => setLegal('terms')} className="underline cursor-pointer hover:text-text-secondary transition-colors">Terms of Service</span>
            {' '}and{' '}
            <span onClick={() => setLegal('privacy')} className="underline cursor-pointer hover:text-text-secondary transition-colors">Privacy Policy</span>
          </p>
          <LegalModal doc={legal} onClose={() => setLegal(null)} />
        </div>
      </div>
    </div>
  )
}
