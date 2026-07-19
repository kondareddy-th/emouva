import { createPortal } from 'react-dom'
import { Link } from 'react-router-dom'
import { ArrowRight, Sparkles } from 'lucide-react'
import { useDemoStore } from '../hooks/useDemoStore'

export default function DemoLimitModal() {
  const { showLimitModal, dismissLimitModal } = useDemoStore()

  if (!showLimitModal) return null

  return createPortal(
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="relative w-full max-w-md mx-4 rounded-2xl bg-[#141416] border border-white/[0.08] p-8 shadow-2xl text-center">
        {/* Icon */}
        <div className="w-14 h-14 rounded-2xl bg-[#CFAE62]/10 flex items-center justify-center mx-auto mb-5">
          <Sparkles className="w-7 h-7 text-[#CFAE62]" />
        </div>

        <h2 className="text-[20px] font-bold text-white mb-2">
          You've used all 3 free analyses
        </h2>
        <p className="text-[14px] text-white/40 mb-6 leading-relaxed">
          Create a free account to continue analyzing stocks.
          <br />
          No credit card required.
        </p>

        {/* CTAs */}
        <div className="space-y-3">
          <Link
            to="/signup"
            onClick={dismissLimitModal}
            className="w-full py-3 bg-[#CFAE62] hover:bg-[#BD9F58] text-white text-[14px] font-semibold rounded-lg transition-all flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(207,174,98,0.15)]"
          >
            Create Free Account
            <ArrowRight className="w-4 h-4" />
          </Link>
          <button
            onClick={dismissLimitModal}
            className="w-full py-2.5 text-white/30 text-[13px] font-medium hover:text-white/50 transition-colors"
          >
            Maybe later
          </button>
        </div>

        <p className="text-[11px] text-white/20 mt-5">
          Free accounts get 3 AI analyses + 5 advisor messages per day.
        </p>
      </div>
    </div>,
    document.body,
  )
}
