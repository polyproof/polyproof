import type { ReactNode } from 'react'
import Header from './Header'
import Footer from './Footer'
import Sidebar from './Sidebar'
import { useUIStore } from '../../store/index'
import { cn } from '../../lib/utils'

interface LayoutProps {
  children: ReactNode
  sidebar?: boolean
}

export default function Layout({ children, sidebar = false }: LayoutProps) {
  const { sidebarOpen, toggleSidebar } = useUIStore()

  return (
    <div className="flex min-h-screen flex-col bg-gray-50">
      <Header />
      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-6 px-4 py-6">
        <main className="min-w-0 flex-1">{children}</main>
        {sidebar && (
          <>
            {/* Desktop sidebar */}
            <div className="hidden w-72 shrink-0 lg:block">
              <Sidebar />
            </div>
            {/* Mobile sidebar overlay */}
            {sidebarOpen && (
              <div className="fixed inset-0 z-30 lg:hidden">
                <div className="absolute inset-0 bg-black/50" onClick={toggleSidebar} />
                <div className={cn('absolute left-0 top-14 bottom-0 w-72 overflow-y-auto bg-gray-50 p-4')}>
                  <Sidebar />
                </div>
              </div>
            )}
          </>
        )}
      </div>
      <Footer />
    </div>
  )
}
