import { useState } from 'react'
import { createPortal } from 'react-dom'
import { Mail, Loader2, X, ShieldCheck } from 'lucide-react'
import { useDemoStore } from '../hooks/useDemoStore'

export default function DemoEmailModal() {
  const { showEmailModal, submitting, submitError, submitEmail, dismissEmailModal } =
    useDemoStore()
  const [email, setEmail] = useState('')

  if (!showEmailModal) return null

  const isValidEmail = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (isValidEmail) submitEmail(email)
  }

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-md mx-4 rounded-2xl bg-[#141416] border border-white/[0.08] p-8 shadow-2xl">
        {/* Close */}
        <button
          onClick={dismissEmailModal}
          className="absolute top-4 right-4 text-white/30 hover:text-white/60 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Header */}
        <div className="flex flex-col items-center mb-6">
          <div className="w-12 h-12 rounded-xl bg-[#CFAE62]/10 flex items-center justify-center mb-4">
            <ShieldCheck className="w-6 h-6 text-[#CFAE62]" />
          </div>
          <h2 className="text-[20px] font-bold text-white mb-1">Try Emouva AI Research</h2>
          <p className="text-[14px] text-white/40 text-center leading-relaxed">
            Enter your email to get 3 free AI analyses per day.
            <br />
            No account needed.
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-white/30" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              autoFocus
              className="w-full h-12 pl-10 pr-4 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white placeholder-white/25 text-[14px] focus:outline-none focus:border-[#CFAE62]/30 focus:ring-1 focus:ring-[#CFAE62]/20 transition-all"
            />
          </div>

          {submitError && (
            <p className="text-[12px] text-[#F2937F] bg-[#F2937F]/10 px-3 py-2 rounded-lg">
              {submitError}
            </p>
          )}

          <button
            type="submit"
            disabled={!isValidEmail || submitting}
            className="w-full py-3 bg-[#CFAE62] hover:bg-[#BD9F58] disabled:opacity-40 disabled:cursor-not-allowed text-white text-[14px] font-semibold rounded-lg transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(207,174,98,0.15)]"
          >
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
            {submitting ? 'Starting...' : 'Start Analyzing'}
          </button>
        </form>

        <p className="text-[11px] text-white/20 text-center mt-4">
          We'll never spam you. Unsubscribe anytime.
        </p>
      </div>
    </div>,
    document.body,
  )
}
