'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuthStore, useNavigationStore } from '@/lib/store'
import { authAPI } from '@/lib/api'
import { SessionWarning } from './SessionWarning'
import { SidebarTooltip } from './SidebarTooltip'
import {
  LayoutDashboard,
  BarChart3,
  FileText,
  Settings,
  Cpu,
  Database,
  Hash,
  Activity,
  Network,
  UserPlus,
  MessageSquare,
  UserCog,
  LogOut,
  Bell,
} from 'lucide-react'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  color: string
}

interface AdminNavItem {
  name: string
  href: string
  icon?: React.ComponentType<{ className?: string; style?: React.CSSProperties }>
  color?: string
  children?: { name: string; href: string; icon?: React.ComponentType<{ className?: string; style?: React.CSSProperties }>; color?: string }[]
}

const mainNavItems: NavItem[] = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard, color: 'text-primary' },
  { name: 'Analytics', href: '/analytics', icon: BarChart3, color: 'text-success' },
  { name: 'Reports', href: '/reports', icon: FileText, color: 'text-primary' },
  { name: 'Announcements', href: '/announcements', icon: Bell, color: 'text-warning' },

  { name: 'Feature & Feedback', href: '/feature-feedback', icon: MessageSquare, color: 'text-primary' },
  { name: 'Settings', href: '/settings', icon: Settings, color: 'text-warning' },
]

const adminNavItems: AdminNavItem[] = [
  {
    name: 'Processors',
    href: '/admin/processors',
    icon: Cpu,
    color: 'text-primary',
  },
  {
    name: 'Reference Data',
    href: '/admin/reference-data',
    icon: Database,
    color: 'text-warning',
    children: [
      { name: 'Symbols', href: '/admin/symbols', icon: Hash, color: 'text-primary' },
      { name: 'Indicators', href: '/admin/reference-data/indicators', icon: Activity, color: 'text-success' },
      { name: 'Activity', href: '/admin/activity', icon: Activity, color: 'text-info' },
    ],
  },
  {
    name: 'Connections',
    href: '/admin/connections',
    icon: Network,
    color: 'text-primary',
  },
  {
    name: 'Request & Feedback',
    href: '/admin/requests-feedback',
    icon: UserPlus,
    color: 'text-warning',
    children: [
      { name: 'Access Requests', href: '/admin/requests', icon: UserPlus, color: 'text-warning' },
    ],
  },
  {
    name: 'Accounts',
    href: '/admin/accounts',
    icon: UserCog,
    color: 'text-primary',
  },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout: storeLogout } = useAuthStore()
  const { setSubItems, clearSubItems } = useNavigationStore()

  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'

  const handleLogout = async () => {
    try {
      await authAPI.logout()
    } catch (e) {
      // Ignore errors
    }
    storeLogout()
    router.push('/login')
  }

  const isActive = (href: string) => {
    if (href === '/admin/reference-data') {
      return pathname?.startsWith('/admin/reference-data')
    }
    if (href === '/admin/requests-feedback') {
      return pathname?.startsWith('/admin/requests-feedback') || pathname === '/admin/requests'
    }
    if (href === '/feature-feedback') {
      return pathname?.startsWith('/feature-feedback')
    }
    // Removed screener route logic
    return pathname === href
  }

  // Update sub-items when pathname changes

  useEffect(() => {
    // Don't show sub-items for Reference Data pages (navigation removed)
    if (pathname?.startsWith('/admin/reference-data') || pathname === '/admin/symbols') {
      clearSubItems()
      return
    }

    // Don't show sub-items for Request & Feedback pages (navigation removed - using back navigation instead)
    if (pathname === '/admin/requests-feedback' ||
      pathname === '/admin/requests') {
      clearSubItems()
      return
    }

    // Don't show sub-items for Feature & Feedback user pages
    if (pathname?.startsWith('/feature-feedback')) {
      clearSubItems()
      return
    }

    const activeItem = adminNavItems.find((item) => {
      if (item.href === '/admin/reference-data') {
        return false // Don't match Reference Data
      }
      if (item.href === '/admin/requests-feedback') {
        return false // Don't match Request & Feedback
      }
      return pathname === item.href
    })

    if (activeItem?.children) {
      setSubItems(activeItem.children)
    } else {
      clearSubItems()
    }
  }, [pathname, setSubItems, clearSubItems])

  return (
    <>
      {/* Toggle Button - Fixed position, outside sidebar container */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className={`fixed top-1/2 z-50 w-7 h-7 rounded-full bg-[#f3f4f6] dark:bg-[#121b2f] border border-border dark:border-[#1f2a44] flex items-center justify-center hover:bg-[#e5e7eb] dark:hover:bg-[#182447] transition-[left] duration-300 ease-in-out focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 cursor-pointer ${collapsed ? 'left-[50px]' : 'left-[242px]'
          }`}
        style={{
          transform: 'translateY(-50%)',
        }}
        onMouseDown={(e) => {
          e.currentTarget.style.transform = 'translateY(-50%) scale(0.96)'
        }}
        onMouseUp={(e) => {
          e.currentTarget.style.transform = 'translateY(-50%)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(-50%)'
        }}
        onTouchStart={(e) => {
          e.currentTarget.style.transform = 'translateY(-50%) scale(0.96)'
        }}
        onTouchEnd={(e) => {
          e.currentTarget.style.transform = 'translateY(-50%)'
        }}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
      >
        <span className="text-sm font-sans text-text-secondary hover:text-text-primary transition-colors duration-150 inline-block">
          {collapsed ? '>' : '<'}
        </span>
      </button>

      <aside
        className={`relative h-screen bg-panel dark:bg-[#0a1020] border-r border-border dark:border-[#1f2a44] transition-[width] duration-300 ease-in-out flex flex-col flex-shrink-0 overflow-hidden ${collapsed ? 'w-16' : 'w-64'
          }`}
        style={{
          transition: 'width 300ms cubic-bezier(0.4, 0, 0.2, 1)'
        }}
      >
        {/* Logo */}
        <div className="flex flex-col items-center justify-center border-b border-border dark:border-[#1f2a44] px-3 py-4 flex-shrink-0 min-h-[64px] relative">
          {/* RUBIK - Full text, fades out smoothly when collapsing */}
          <h1 className={`text-base font-sans font-semibold text-text-primary tracking-tight transition-all duration-300 ease-in-out text-center absolute ${collapsed ? 'opacity-0 scale-95 pointer-events-none' : 'opacity-100 scale-100'
            }`}>
            RUBIK
          </h1>
          {/* R - Single letter, stays still with cool animation when collapsed */}
          <div className={`text-xl font-sans font-bold text-primary flex items-center justify-center absolute transition-all duration-300 ease-in-out ${collapsed ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none'
            }`}
            style={{
              animation: collapsed ? 'pulse-glow 2s ease-in-out infinite' : 'none',
              textShadow: collapsed ? '0 0 8px rgba(59, 130, 246, 0.5), 0 0 12px rgba(59, 130, 246, 0.3)' : 'none',
            }}>
            R
          </div>
        </div>

        {/* Scrollable Navigation Area */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden min-h-0 py-3" style={{ scrollBehavior: 'smooth' }}>
          <div className="px-2 space-y-0.5">
            {/* Main Navigation Items */}
            {mainNavItems.map((item) => {
              const active = isActive(item.href)
              const IconComponent = item.icon
              return (
                <SidebarTooltip key={item.href} text={item.name} collapsed={collapsed}>
                  <Link
                    href={item.href}
                    className={`group relative flex items-center justify-start py-2 rounded-lg transition-all duration-200 ease-in-out min-h-[38px] active:scale-[0.98] focus:outline-none w-full ${active
                      ? 'bg-[#f1f5f9] dark:bg-[#182447] text-text-primary font-semibold'
                      : 'text-text-secondary hover:bg-[#f3f4f6] dark:hover:bg-[#182447]/60 hover:text-text-primary'
                      }`}
                  >
                    {/* Icon - Fixed width container for stable alignment rail */}
                    <div className="flex-shrink-0 w-[48px] flex items-center justify-center">
                      <IconComponent className={`w-5 h-5 transition-all duration-300 ease-in-out ${active
                        ? 'scale-110'
                        : 'group-hover:scale-110'
                        }`}
                        style={{
                          color: 'transparent',
                          filter: 'none',
                          strokeWidth: active ? 2 : 1.5,
                          fill: 'none',
                          stroke: active
                            ? (item.color === 'text-primary' ? '#3b82f6' : item.color === 'text-success' ? '#10b981' : item.color === 'text-warning' ? '#f59e0b' : '#3b82f6')
                            : (item.color === 'text-primary' ? '#9ca3af' : item.color === 'text-success' ? '#9ca3af' : item.color === 'text-warning' ? '#9ca3af' : '#9ca3af'),
                          strokeLinejoin: 'round',
                          strokeLinecap: 'round',
                          paintOrder: 'stroke',
                          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                        }} />
                    </div>
                    {/* Text - Absolutely positioned to prevent layout shift, opacity transition only */}
                    <span className={`absolute left-[54px] top-1/2 -translate-y-1/2 text-[14.5px] font-sans leading-[1.5] whitespace-nowrap transition-all duration-300 ease-in-out ${active ? 'font-semibold' : 'font-medium'
                      } ${collapsed
                        ? 'opacity-0 pointer-events-none'
                        : 'opacity-100'
                      }`}>
                      {item.name}
                    </span>
                  </Link>
                </SidebarTooltip>
              )
            })}

            {/* Spacer before ADMIN section - equal spacing */}
            {/* Using padding-top to avoid space-y interference */}
            {isAdmin && <div style={{ paddingTop: '1rem', width: '100%', display: 'block' }} />}

            {/* Fixed Divider with ADMIN Label - Always visible, fixed position, no jumping */}
            {isAdmin && (
              <div className="relative mx-2 flex-shrink-0" style={{ paddingBottom: '1rem', display: 'block' }}>
                {/* Divider Line - More visible */}
                <div className="h-[1px] bg-gradient-to-r from-transparent via-border dark:via-[#1f2a44] to-transparent" />
                {/* ADMIN Label - Fixed position, smooth fade with spacing */}
                <div className={`absolute left-1/2 -translate-x-1/2 -top-2.5 px-3 py-0.5 bg-panel dark:bg-[#0a1020] transition-all duration-300 ease-in-out ${collapsed ? 'opacity-0 scale-95 pointer-events-none' : 'opacity-100 scale-100'
                  }`}>
                  <span className="text-[11px] font-sans font-semibold text-text-muted uppercase tracking-wider">
                    Admin
                  </span>
                </div>
              </div>
            )}

            {/* Admin Section */}
            {isAdmin && (
              <div>
                <div className="space-y-1.5">
                  {adminNavItems.map((item, index) => {
                    const active = isActive(item.href)
                    const IconComponent = item.icon || Settings
                    return (
                      <SidebarTooltip key={item.href} text={item.name} collapsed={collapsed}>
                        <Link
                          href={item.href}
                          className={`group relative flex items-center justify-start py-2 rounded-lg transition-all duration-200 ease-in-out min-h-[38px] active:scale-[0.98] focus:outline-none w-full ${active
                            ? 'bg-[#f1f5f9] dark:bg-[#182447] text-text-primary font-semibold'
                            : 'text-text-secondary hover:bg-[#f3f4f6] dark:hover:bg-[#182447]/60 hover:text-text-primary'
                            }`}
                        >
                          {/* Icon - Fixed width container for stable alignment rail */}
                          <div className="flex-shrink-0 w-[48px] flex items-center justify-center">
                            <IconComponent className={`w-5 h-5 transition-all duration-300 ease-in-out ${active
                              ? 'scale-110'
                              : 'group-hover:scale-110'
                              }`}
                              style={{
                                color: 'transparent',
                                filter: 'none',
                                strokeWidth: active ? 2 : 1.5,
                                fill: 'none',
                                stroke: active
                                  ? (item.color === 'text-primary' ? '#3b82f6' : item.color === 'text-success' ? '#10b981' : item.color === 'text-warning' ? '#f59e0b' : item.color === 'text-info' ? '#06b6d4' : '#3b82f6')
                                  : (item.color === 'text-primary' ? '#9ca3af' : item.color === 'text-success' ? '#9ca3af' : item.color === 'text-warning' ? '#9ca3af' : item.color === 'text-info' ? '#9ca3af' : '#9ca3af'),
                                strokeLinejoin: 'round',
                                strokeLinecap: 'round',
                                paintOrder: 'stroke',
                                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
                              }} />
                          </div>
                          {/* Text - Absolutely positioned to prevent layout shift, opacity transition only */}
                          <span className={`absolute left-[54px] top-1/2 -translate-y-1/2 text-[14.5px] font-sans leading-[1.5] whitespace-nowrap transition-all duration-300 ease-in-out ${active ? 'font-semibold' : 'font-medium'
                            } ${collapsed
                              ? 'opacity-0 pointer-events-none'
                              : 'opacity-100'
                            }`}>
                            {item.name}
                          </span>
                        </Link>
                      </SidebarTooltip>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </nav>

        {/* Session Warning */}
        <SessionWarning collapsed={collapsed} />

        {/* Logout */}
        <div className="border-t border-border p-2 flex-shrink-0">
          <SidebarTooltip text="Logout" collapsed={collapsed}>
            <button
              onClick={handleLogout}
              className={`group relative w-full flex items-center justify-start py-2 rounded-lg text-text-secondary hover:bg-[#f3f4f6] dark:hover:bg-[#182447]/60 hover:text-error transition-all duration-200 min-h-[38px] active:scale-[0.98] focus:outline-none`}
            >
              {/* Icon - Fixed width container for stable alignment rail */}
              <div className="flex-shrink-0 w-[48px] flex items-center justify-center">
                <LogOut className="w-5 h-5 text-text-secondary group-hover:text-error transition-colors duration-150" />
              </div>
              {/* Text - Absolutely positioned to prevent layout shift, opacity transition only */}
              <span className={`absolute left-[54px] top-1/2 -translate-y-1/2 text-[14.5px] font-sans font-medium leading-[1.5] whitespace-nowrap transition-all duration-300 ease-in-out ${collapsed
                ? 'opacity-0 pointer-events-none'
                : 'opacity-100'
                }`}>
                Logout
              </span>
            </button>
          </SidebarTooltip>
        </div>
      </aside>
    </>
  )
}
