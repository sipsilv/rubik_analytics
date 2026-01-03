'use client'

import { useEffect, useRef } from 'react'
import { useAuthStore } from '@/lib/store'
import Cookies from 'js-cookie'
import { userAPI } from '@/lib/api'

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const setUser = useAuthStore((state) => state.setUser)
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const heartbeatIntervalRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    const userStr = Cookies.get('user')
    if (userStr) {
      try {
        const user = JSON.parse(userStr)
        setUser(user)
      } catch (e) {
        Cookies.remove('user')
        Cookies.remove('auth_token')
      }
    }
  }, [setUser])

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
