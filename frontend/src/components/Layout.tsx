import { useState } from 'react'
import { Outlet, NavLink } from 'react-router-dom'
import { LayoutDashboard, Search, ShieldCheck, MessageCircle, Settings, CandlestickChart, Layers } from 'lucide-react'
import clsx from 'clsx'
import Sidebar from './Sidebar'
import ToastContainer from './Toast'

const mobileNavItems = [
  { to: '/', icon: LayoutDashboard, label: 'Home' },
  { to: '/polytrade', icon: Layers, label: 'Themes' },
  { to: '/trading', icon: CandlestickChart, label: 'Trading' },
  { to: '/research', icon: Search, label: 'Research' },
  { to: '/risk', icon: ShieldCheck, label: 'Risk' },
  { to: '/advisor', icon: MessageCircle, label: 'Advisor' },
  { to: '/settings', icon: Settings, label: 'Settings' },
]

export default function Layout() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div
      className="flex min-h-screen bg-base"
      style={{
        background:
          'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(207,174,98,0.06) 0%, transparent 60%), #0C110E',
      }}
    >
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed(!collapsed)} />
      <main className={clsx('flex-1 transition-all duration-300 pb-16 md:pb-0', collapsed ? 'md:ml-[60px]' : 'md:ml-[200px]')}>
        <Outlet />
      </main>

      {/* Mobile bottom navigation — warm private-bank top-bar treatment */}
      <nav
        className="fixed bottom-0 left-0 right-0 z-50 backdrop-blur-xl border-t border-[rgba(207,174,98,0.25)] md:hidden"
        style={{ background: 'rgba(12,17,14,0.98)' }}
      >
        <div className="flex items-center justify-around h-14 px-2">
          {mobileNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex flex-col items-center gap-1 px-2 py-1 rounded-md transition-colors',
                  isActive
                    ? 'text-accent'
                    : 'text-text-tertiary'
                )
              }
            >
              {({ isActive }) => (
                <>
                  <item.icon className="w-[18px] h-[18px]" strokeWidth={isActive ? 1.75 : 1.5} />
                  <span
                    className="text-[9.5px] font-medium"
                    style={isActive ? { color: '#E9D6A2', letterSpacing: '.04em' } : { letterSpacing: '.04em' }}
                  >
                    {item.label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      <ToastContainer />
    </div>
  )
}
