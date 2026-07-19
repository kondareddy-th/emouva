import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  Search,
  Bookmark,
  PieChart,
  ShieldCheck,
  Sparkles,
  MessageCircle,
  Settings,
  ChevronLeft,
  ChevronRight,
  LogOut,
} from 'lucide-react'
import clsx from 'clsx'
import useAuth from '../hooks/useAuth'

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/research', icon: Search, label: 'AI Research' },
  { to: '/watchlist', icon: Bookmark, label: 'Watchlist' },
  { to: '/portfolio', icon: PieChart, label: 'Portfolio' },
  { to: '/risk', icon: ShieldCheck, label: 'Risk Center' },
  { to: '/optimize', icon: Sparkles, label: 'Optimize' },
  { to: '/advisor', icon: MessageCircle, label: 'Advisor' },
]

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

export default function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const initials = user?.display_name
    ? user.display_name.charAt(0).toUpperCase()
    : user?.username?.charAt(0).toUpperCase() ?? '?'

  return (
    <aside
      className={clsx(
        'fixed left-0 top-0 h-screen flex-col bg-surface-1 border-r border-[rgba(180,220,190,0.12)] z-50 transition-all duration-300 hidden md:flex',
        collapsed ? 'w-[60px]' : 'w-[200px]'
      )}
    >
      {/* Logo — gold diamond motif + mono-tracked wordmark */}
      <div className={clsx(
        'flex items-center gap-2.5 h-[54px] border-b border-[rgba(180,220,190,0.12)]',
        collapsed ? 'justify-center px-0' : 'px-4'
      )}>
        <div className="w-2.5 h-2.5 bg-accent rotate-45 flex-shrink-0" />
        {!collapsed && (
          <span className="flex items-center gap-1.5">
            <span
              className="text-[13px] font-medium"
              style={{ letterSpacing: '.22em', color: '#E9D6A2' }}
            >
              EMOUVA
            </span>
            <span className="text-[8.5px] font-mono font-medium tracking-[0.12em] text-accent border border-accent/40 rounded-[3px] px-1 py-[1px] leading-none">BETA</span>
          </span>
        )}
      </div>

      {/* Nav Items */}
      <nav className="flex-1 py-3 px-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-all duration-200 group relative',
                isActive
                  ? 'bg-accent/[0.10] text-text-primary'
                  : 'text-text-tertiary hover:text-text-secondary hover:bg-accent/[0.04]'
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-accent rounded-r" />
                )}
                <item.icon
                  className={clsx(
                    'w-[15px] h-[15px] flex-shrink-0 transition-all duration-200',
                    isActive ? 'text-accent' : 'text-text-tertiary group-hover:text-text-secondary'
                  )}
                  strokeWidth={isActive ? 1.75 : 1.5}
                />
                {!collapsed && (
                  <span className={clsx(
                    'text-[12.5px] truncate transition-colors',
                    isActive ? 'font-medium' : 'font-normal'
                  )}>
                    {item.label}
                  </span>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="px-2 py-2 border-t border-[rgba(180,220,190,0.12)] space-y-0.5">
        {/* User profile */}
        {user && (
          <div className={clsx(
            'flex items-center gap-2.5 px-2.5 py-2 mb-1',
            collapsed ? 'justify-center' : ''
          )}>
            <div className="w-7 h-7 rounded-full bg-surface-4 border border-[rgba(180,220,190,0.20)] flex items-center justify-center flex-shrink-0 text-[12px] font-medium text-accent font-serif">
              {initials}
            </div>
            {!collapsed && (
              <div className="flex-1 min-w-0">
                <p className="text-[12px] font-medium text-text-primary truncate">
                  {user.display_name}
                </p>
                <p className="text-[10px] text-text-tertiary truncate">
                  @{user.username}
                </p>
              </div>
            )}
          </div>
        )}

        <NavLink
          to="/settings"
          className={({ isActive }) =>
            clsx(
              'flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-all duration-200 relative',
              isActive
                ? 'bg-accent/[0.10] text-text-primary'
                : 'text-text-tertiary hover:text-text-secondary hover:bg-accent/[0.04]'
            )
          }
        >
          {({ isActive }) => (
            <>
              {isActive && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-4 bg-accent rounded-r" />
              )}
              <Settings className="w-[15px] h-[15px] flex-shrink-0" strokeWidth={isActive ? 1.75 : 1.5} />
              {!collapsed && <span className={clsx('text-[12.5px]', isActive ? 'font-medium' : 'font-normal')}>Settings</span>}
            </>
          )}
        </NavLink>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-text-tertiary hover:text-loss hover:bg-loss/[0.06] transition-all duration-200 w-full"
          title="Sign out"
        >
          <LogOut className="w-[15px] h-[15px] flex-shrink-0" strokeWidth={1.5} />
          {!collapsed && <span className="text-[12.5px] font-normal">Sign out</span>}
        </button>

        <button
          onClick={onToggle}
          className="flex items-center gap-2.5 px-2.5 py-2 rounded-md text-text-tertiary hover:text-text-secondary hover:bg-accent/[0.04] transition-all duration-200 w-full"
        >
          {collapsed ? (
            <ChevronRight className="w-[15px] h-[15px]" />
          ) : (
            <>
              <ChevronLeft className="w-[15px] h-[15px]" />
              <span className="text-[12px]">Collapse</span>
            </>
          )}
        </button>
      </div>
    </aside>
  )
}
