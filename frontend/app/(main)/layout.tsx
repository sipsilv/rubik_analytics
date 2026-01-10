'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore, useSessionStore, useThemeStore } from '@/lib/store'
import { Sidebar } from '@/components/Sidebar'
import { TopSubNav } from '@/components/TopSubNav'
import Cookies from 'js-cookie'
import { userAPI } from '@/lib/api'

export default function MainLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const { user, setUser, isAuthenticated } = useAuthStore()
  const { setSessionExpiry, setIdleTimeout } = useSessionStore()
  const { initializeTheme } = useThemeStore()
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
    
    const checkAuthAndLoadUser = () => {
      const token = Cookies.get('auth_token')
      if (!token) {
        // Clear any stale user state
        setUser(null)
        router.push('/login')
        return
      }

      // Fetch current user if not loaded or state is out of sync
      if (!user || !isAuthenticated) {
        userAPI
          .getCurrentUser()
          .then((data) => {
            setUser(data)
            // Initialize theme from user preference (defaults to dark)
            initializeTheme(data.theme_preference || 'dark')
            // Set session expiry (8 hours from now)
            const expiry = Date.now() + 8 * 60 * 60 * 1000
            setSessionExpiry(expiry)
            setIdleTimeout(30) // 30 minutes
          })
          .catch((error) => {
            console.error('Failed to get current user:', error)
            // Clear invalid auth state
            Cookies.remove('auth_token')
            Cookies.remove('user')
            setUser(null)
            router.push('/login')
          })
      } else {
        // Verify token is still valid by making a lightweight check
        // Initialize theme if not already initialized
        if (user.theme_preference) {
          initializeTheme(user.theme_preference)
        } else {
          initializeTheme('dark') // Default to dark
        }
        // Set session expiry if not set
        const expiry = Date.now() + 8 * 60 * 60 * 1000
        setSessionExpiry(expiry)
        setIdleTimeout(30)
      }
    }

    // Check on mount
    checkAuthAndLoadUser()

    // Also check when window gains focus (handles cross-tab login)
    const handleFocus = () => {
      checkAuthAndLoadUser()
    }
    
    window.addEventListener('focus', handleFocus)
    
    return () => {
      window.removeEventListener('focus', handleFocus)
    }
  }, [user, setUser, router, setSessionExpiry, setIdleTimeout, initializeTheme, isAuthenticated])

  // Activity tracking - ping server every 2 minutes to update last_active_at
  useEffect(() => {
    if (!user) return

    // NO auto-refresh - activity ping removed
    // Ping immediately on mount only
    userAPI.pingActivity().catch(() => {})
  }, [user])

  // Prevent hydration mismatch by not rendering auth-dependent content until mounted
  if (!mounted) {
    return (
      <div className="flex h-screen bg-background dark:bg-[#0b1220] overflow-hidden">
        <div className="flex-1 flex flex-col overflow-hidden">
          <main className="flex-1 overflow-y-auto transition-all duration-[200ms] bg-page-bg dark:bg-[#0e1628]">
            <div className="min-h-full p-4">{children}</div>
          </main>
        </div>
      </div>
    )
  }

  // Always return the same structure to prevent hydration mismatch
  // The router will handle redirects if not authenticated
  return (
    <div className="flex h-screen bg-background dark:bg-[#0b1220] overflow-hidden">
      {isAuthenticated && user && <Sidebar />}
      <div className="flex-1 flex flex-col overflow-hidden">
        {isAuthenticated && user && <TopSubNav />}
        <main className="flex-1 overflow-y-auto transition-all duration-[200ms] bg-page-bg dark:bg-[#0e1628]">
          <div className="min-h-full p-4">{children}</div>
        </main>
      </div>
    </div>
  )
}
