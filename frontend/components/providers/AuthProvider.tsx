'use client'

import { useEffect, useRef } from 'react'
import { useAuthStore } from '@/lib/store'
import Cookies from 'js-cookie'
import { userAPI } from '@/lib/api'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const setUser = useAuthStore((state) => state.setUser)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const user = useAuthStore((state) => state.user)
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null)

  // Initialize auth state from cookies on mount (works across tabs)
  useEffect(() => {
    const syncAuthFromCookies = () => {
      const userStr = Cookies.get('user')
      const token = Cookies.get('auth_token')
      
      if (userStr && token) {
        try {
          const userFromCookie = JSON.parse(userStr)
          // Only update if user changed or not authenticated
          if (!isAuthenticated || JSON.stringify(user) !== JSON.stringify(userFromCookie)) {
            setUser(userFromCookie)
          }
        } catch (e) {
          Cookies.remove('user')
          Cookies.remove('auth_token')
          setUser(null)
        }
      } else if (isAuthenticated) {
        // Cookies cleared but state still authenticated - clear state
        setUser(null)
      }
    }

    // Sync on mount
    syncAuthFromCookies()

    // Also sync when window gains focus (in case cookies were updated in another tab)
    const handleFocus = () => {
      syncAuthFromCookies()
    }
    
    window.addEventListener('focus', handleFocus)
    
    return () => {
      window.removeEventListener('focus', handleFocus)
    }
  }, [setUser, isAuthenticated, user])

  // Heartbeat mechanism: ping server every 2 minutes to keep user status LIVE
  useEffect(() => {
    if (isAuthenticated) {
      // Clear any existing interval
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current)
      }

      // Ping immediately on mount/authentication
      const ping = async () => {
        try {
          await userAPI.pingActivity()
        } catch (error) {
          // Silently fail - don't break the app if ping fails
          // The user will still be marked offline after threshold expires
          console.debug('[Heartbeat] Ping failed (non-critical):', error)
        }
      }

      // Ping immediately
      ping()

      // Then ping every 2 minutes (less than 5-minute threshold to keep status LIVE)
      heartbeatIntervalRef.current = setInterval(ping, 2 * 60 * 1000)

      return () => {
        if (heartbeatIntervalRef.current) {
          clearInterval(heartbeatIntervalRef.current)
          heartbeatIntervalRef.current = null
        }
      }
    } else {
      // Clear interval if user logs out
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current)
        heartbeatIntervalRef.current = null
      }
    }
  }, [isAuthenticated])

  return <>{children}</>
}
