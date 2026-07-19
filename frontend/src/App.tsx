import { BrowserRouter, Routes, Route, Outlet, Link, Navigate, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AIResearch from './pages/AIResearch'
import RiskCenter from './pages/RiskCenter'
import Portfolio from './pages/Portfolio'
import BuyRules from './pages/BuyRules'
import StockScores from './pages/StockScores'
import Advisor from './pages/Advisor'
import Watchlist from './pages/Watchlist'
import Optimize from './pages/Optimize'
import TradingLayout from './components/trading/TradingLayout'
import Ledger from './pages/trading/Ledger'
import Positions from './pages/trading/Positions'
import History from './pages/trading/History'
import Principles from './pages/trading/Principles'
import Research from './pages/trading/Research'
import TradingSettings from './pages/trading/Settings'
import ScreenDetail from './pages/trading/ScreenDetail'
import Admin from './pages/Admin'
import PolytradeLayout from './components/polytrade/PolytradeLayout'
import Discover from './pages/polytrade/Discover'
import ThemeView from './pages/polytrade/ThemeView'
import MyThemes from './pages/polytrade/MyThemes'
import StockDetail from './pages/StockDetail'
import ComingSoon from './pages/ComingSoon'
import Settings from './pages/Settings'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Landing from './pages/Landing'
import Community from './pages/Community'
import useAuth from './hooks/useAuth'
import { ShieldCheck, Loader2 } from 'lucide-react'

function LoadingSpinner() {
  return (
    <div className="min-h-screen bg-base flex items-center justify-center">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
          <ShieldCheck className="w-5 h-5 text-accent" />
        </div>
        <Loader2 className="w-5 h-5 text-text-tertiary animate-spin" />
      </div>
    </div>
  )
}

/** Minimal layout for unauthenticated users accessing /research (Try Demo). */
function DemoLayout() {
  return (
    <div className="min-h-screen bg-base">
      <nav className="sticky top-0 z-50 bg-base/80 backdrop-blur-xl border-b border-[rgba(255,255,255,0.06)]">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
              <ShieldCheck className="w-4.5 h-4.5 text-accent" />
            </div>
            <span className="text-[16px] font-semibold tracking-tight text-text-primary">Emouva</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="px-4 py-1.5 text-[13px] font-medium text-text-secondary hover:text-text-primary transition-colors"
            >
              Sign In
            </Link>
            <Link
              to="/signup"
              className="px-4 py-1.5 rounded-lg bg-accent text-white text-[13px] font-medium hover:bg-accent-hover transition-colors"
            >
              Sign Up
            </Link>
          </div>
        </div>
      </nav>
      <Outlet />
    </div>
  )
}

/**
 * AppShell — decides what to render based on auth state + route.
 * - Authenticated users → full Layout with sidebar
 * - Unauthenticated on /research → DemoLayout (sample analysis)
 * - Unauthenticated on anything else → Landing page
 */
function AppShell() {
  const { isAuthenticated, verifying, user } = useAuth()
  const location = useLocation()

  if (verifying) return <LoadingSpinner />

  if (!isAuthenticated) {
    // Allow /research without auth for "Try Demo"
    if (location.pathname === '/research') {
      return <DemoLayout />
    }
    return <Landing />
  }

  // Personal hosted instance: community-only members live at /community.
  if (user?.full_access === false) return <Navigate to="/community" replace />

  return <Layout />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Auth pages (no Layout wrapper) */}
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        {/* Community — one public channel; read is public, posting needs sign-in */}
        <Route path="/community" element={<Community />} />

        {/* Admin console (separate admin accounts; no user layout) */}
        <Route path="/admin" element={<Admin />} />

        {/* Trading side ("The Partner") — its own warm-charcoal/gold layout */}
        <Route path="/trading" element={<TradingLayout />}>
          <Route index element={<Ledger />} />
          <Route path="positions" element={<Positions />} />
          <Route path="history" element={<History />} />
          <Route path="principles" element={<Principles />} />
          <Route path="research" element={<Research />} />
          <Route path="settings" element={<TradingSettings />} />
          <Route path="screen/:id" element={<ScreenDetail />} />
        </Route>

        {/* Polytrade — thematic auto-managed baskets, its own immersive surface */}
        <Route path="/polytrade" element={<PolytradeLayout />}>
          <Route index element={<Discover />} />
          <Route path="mine" element={<MyThemes />} />
          <Route path=":slug" element={<ThemeView />} />
        </Route>

        {/* Main app — AppShell conditionally renders Landing, DemoLayout, or Layout */}
        <Route path="/" element={<AppShell />}>
          <Route index element={<Dashboard />} />
          <Route path="research" element={<AIResearch />} />
          <Route path="risk" element={<RiskCenter />} />
          {/* One Optimize super-page (Diversify · Stress Test · Upgrade). Old
              paths still render it with the right default tab so existing links
              and their query params keep working. */}
          <Route path="optimize" element={<Optimize />} />
          <Route path="diversify" element={<Optimize defaultTab="diversify" />} />
          <Route path="stress-test" element={<Optimize defaultTab="stress" />} />
          <Route path="holding-review" element={<Optimize defaultTab="upgrade" />} />
          <Route path="stock/:ticker" element={<StockDetail />} />
          <Route path="portfolio" element={<Portfolio />} />
          <Route path="buy-rules" element={<BuyRules />} />
          <Route path="scores" element={<StockScores />} />
          <Route path="advisor" element={<Advisor />} />
          <Route path="watchlist" element={<Watchlist />} />
          <Route path="macro" element={<ComingSoon title="Macro Dashboard" />} />
          <Route path="tax" element={<ComingSoon title="Tax Center" />} />
          <Route path="coach" element={<ComingSoon title="Behavioral Coach" />} />
          <Route path="settings" element={<Settings />} />
          <Route path="*" element={<ComingSoon title="Page Not Found" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
