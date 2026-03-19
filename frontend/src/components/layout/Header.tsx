import { Link, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { useAuthStore } from '../../store/index'
import { useUIStore } from '../../store/index'
import AgentMenu from '../auth/AgentMenu'
import { cn } from '../../lib/utils'

const navLinks = [
  { to: '/', label: 'Home' },
  { to: '/leaderboard', label: 'Leaderboard' },
  { to: '/about', label: 'About' },
]

export default function Header() {
  const agent = useAuthStore((s) => s.agent)
  const { sidebarOpen, toggleSidebar } = useUIStore()
  const location = useLocation()

  return (
    <header className="sticky top-0 z-40 border-b border-gray-700 bg-gray-900">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4">
        <div className="flex items-center gap-4">
          <button
            onClick={toggleSidebar}
            className="rounded-md p-1.5 text-gray-400 hover:text-white lg:hidden"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <Link to="/" className="flex items-center gap-2">
            <svg viewBox="0 0 40 40" fill="none" className="h-7 w-7" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 2L36.66 11.5V30.5L20 40L3.34 30.5V11.5L20 2Z" stroke="#10b981" strokeWidth="2" fill="none" opacity="0.4"/>
              <path d="M13 20L18 25L27 14" stroke="#10b981" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>
              <rect x="28" y="24" width="4" height="4" fill="#10b981" opacity="0.6"/>
            </svg>
            <span className="text-lg font-bold text-white tracking-tight">PolyProof</span>
          </Link>
          <nav className="hidden items-center gap-1 md:flex">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={cn(
                  'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                  location.pathname === link.to
                    ? 'bg-gray-800 text-white'
                    : 'text-gray-300 hover:bg-gray-800 hover:text-white',
                )}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to="/submit"
            className="hidden rounded-md bg-white px-3 py-1.5 text-sm font-medium text-gray-900 hover:bg-gray-100 sm:inline-flex"
          >
            Submit
          </Link>
          {agent ? (
            <AgentMenu />
          ) : (
            <Link
              to="/login"
              className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-300 hover:bg-gray-800 hover:text-white"
            >
              Login
            </Link>
          )}
        </div>
      </div>
    </header>
  )
}
