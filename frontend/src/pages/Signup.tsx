import { useState, useMemo } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Loader2, Eye, EyeOff, Check, X } from 'lucide-react'
import useAuth from '../hooks/useAuth'
import LegalModal, { type LegalDoc } from '../components/LegalDocs'

const POINTS = [
  'Starts on paper money — real portfolio, simulated cash. Go live only when convinced.',
  'It screens the market, buys rarely, and explains every move.',
  'You hold the mandate — approve anything over your limit.',
  'One click to pause: it keeps watching the Ledger, stops trading.',
]

const Dia = ({ className = '' }: { className?: string }) => (
  <div className={`bg-accent rotate-45 flex-none ${className}`} />
)

function ValidationCheck({ valid, label }: { valid: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      {valid ? <Check className="w-3 h-3 text-accent" strokeWidth={2} /> : <X className="w-3 h-3 text-text-tertiary/40" strokeWidth={2} />}
      <span className={`font-mono text-[10.5px] tracking-[0.06em] ${valid ? 'text-accent' : 'text-text-tertiary/60'}`}>{label}</span>
    </div>
  )
}

const fieldBase = 'w-full px-3.5 py-2.5 rounded-[8px] bg-base border text-[14px] text-text-primary placeholder-text-tertiary/60 focus:outline-none transition-colors'
const fieldState = (touched: boolean, valid: boolean) =>
  touched && !valid ? 'border-loss/40 focus:border-loss/60'
    : touched && valid ? 'border-accent/40 focus:border-accent/70'
      : 'border-[rgba(180,220,190,0.12)] focus:border-accent/60'

export default function Signup() {
  const [email, setEmail] = useState(localStorage.getItem('emouva_demo_email') || '')
  const [legal, setLegal] = useState<LegalDoc | null>(null)
  const [displayName, setDisplayName] = useState('')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { signup } = useAuth()
  const navigate = useNavigate()

  const emailValid = useMemo(() => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email), [email])
  const usernameValid = username.length >= 3
  const passwordValid = password.length >= 6
  const showValidation = password.length > 0 || username.length > 0 || email.length > 0
  const canSubmit = emailValid && usernameValid && passwordValid && displayName.trim().length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const u = await signup(username, password, displayName, email)
      localStorage.removeItem('emouva_demo_token')
      localStorage.removeItem('emouva_demo_email')
      navigate(u?.full_access === false ? '/community' : '/')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Signup failed')
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
          Open an account.
          <br />
          <span className="text-accent">Start on paper money.</span>
        </h1>
        <p className="text-[16px] text-text-secondary leading-relaxed max-w-md mb-9">
          Write a mandate, watch the Partner work a real morning, and fund it only when it
          has earned your trust.
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
          <p className="font-serif italic text-[15px] text-accent leading-snug m-0">"Mostly, the job is sitting."</p>
          <p className="font-mono text-[10px] tracking-[0.13em] text-text-tertiary mt-2">— CHARLIE MUNGER · THE PARTNER'S TEMPERAMENT</p>
        </div>
      </div>

      {/* ── Right: create account ── */}
      <div className="flex-1 lg:max-w-md xl:max-w-lg flex flex-col items-center justify-center px-6 py-10">
        <div className="w-full max-w-sm">
          {/* Mobile header */}
          <div className="lg:hidden mb-6">
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
            <h1 className="font-serif font-medium text-[24px] text-text-primary mb-1">Join Emouva</h1>
            <p className="text-[13px] text-text-secondary mb-6">Free &amp; open source — run your own AI trader locally and share your P&amp;L with the community.</p>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1.5">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={`${fieldBase} ${fieldState(!!email, emailValid)}`}
                  placeholder="you@example.com"
                  autoFocus
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1.5">Display Name</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className={`${fieldBase} border-[rgba(180,220,190,0.12)] focus:border-accent/60`}
                  placeholder="Your name"
                  required
                />
              </div>

              <div>
                <label className="block font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1.5">Username</label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''))}
                  className={`${fieldBase} ${fieldState(!!username, usernameValid)}`}
                  placeholder="Choose a username"
                  required
                  minLength={3}
                />
              </div>

              <div>
                <label className="block font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-1.5">Password</label>
                <div className="relative">
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={`${fieldBase} pr-10 ${fieldState(!!password, passwordValid)}`}
                    placeholder="Min 6 characters"
                    required
                    minLength={6}
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

              {showValidation && (
                <div className="flex flex-wrap gap-x-4 gap-y-1 pt-1">
                  <ValidationCheck valid={emailValid} label="Valid email" />
                  <ValidationCheck valid={usernameValid} label="3+ chars username" />
                  <ValidationCheck valid={passwordValid} label="6+ chars password" />
                </div>
              )}

              {error && (
                <p className="text-[12px] text-loss bg-loss/10 px-3.5 py-2.5 rounded-[8px]">{error}</p>
              )}

              <button
                type="submit"
                disabled={loading || !canSubmit}
                className="w-full py-3 bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed text-base text-[14px] font-semibold rounded-[8px] transition-colors flex items-center justify-center gap-2"
              >
                {loading && <Loader2 className="w-4 h-4 animate-spin" />}
                {loading ? 'Creating account...' : 'Open an account'}
              </button>
            </form>

            <div className="mt-4 text-center">
              <Link to="/trading" className="text-[12px] text-text-tertiary hover:text-accent transition-colors">
                Or watch it work — the live demo →
              </Link>
            </div>
          </div>

          <p className="text-center text-[13px] text-text-secondary mt-5">
            Already have an account?{' '}
            <Link to="/login" className="text-accent hover:text-accent-hover transition-colors font-medium">
              Sign in
            </Link>
          </p>

          <p className="text-center text-[11px] text-text-tertiary/70 mt-4 leading-relaxed">
            By opening an account, you agree to our{' '}
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
