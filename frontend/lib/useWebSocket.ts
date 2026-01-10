'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import Cookies from 'js-cookie'

const API_URL = process.env.NEXT_PUBLIC_API_URL
if(!API_URL){
	throw new Error("api url is not found");
}

// Convert HTTP URL to WebSocket URL
const getWebSocketUrl = (): string => {
  const url = API_URL.replace(/^http/, 'ws')
  const token = Cookies.get('auth_token')
  // WebSocket endpoint - adjust path as needed
  const wsPath = `${url}/api/v1/ws`
  return token ? `${wsPath}?token=${token}` : wsPath
}

export interface UserStatusUpdate {
  user_id: string | number
  is_online: boolean
  last_active_at?: string | null
}

export interface AnnouncementUpdate {
  id: string
  trade_date?: string
  symbol_nse?: string
  symbol_bse?: string
  company_name?: string
  news_headline?: string
  descriptor_name?: string
  announcement_type?: string
  [key: string]: any
}

interface UseWebSocketStatusReturn {
  isConnected: boolean
  error: Error | null
}

/**
 * Hook to manage WebSocket connection for real-time user status updates and announcements
 * Falls back gracefully if WebSocket is not available
 */
export function useWebSocketStatus(
  onStatusUpdate?: (update: UserStatusUpdate) => void,
  onAnnouncement?: (announcement: AnnouncementUpdate) => void
): UseWebSocketStatusReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const isConnectingRef = useRef(false)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000 // 3 seconds
  
  // Use ref for callback to avoid dependency issues
  const onStatusUpdateRef = useRef(onStatusUpdate)
  onStatusUpdateRef.current = onStatusUpdate
  
  const onAnnouncementRef = useRef(onAnnouncement)
  onAnnouncementRef.current = onAnnouncement

  const connect = useCallback(() => {
    // Prevent multiple simultaneous connection attempts
    if (isConnectingRef.current) {
      return
    }
    
    // Don't connect if already connected or no auth token
    const token = Cookies.get('auth_token')
    if (!token || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    isConnectingRef.current = true

    try {
      const wsUrl = getWebSocketUrl()
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        // WebSocket connection logs suppressed
        isConnectingRef.current = false
        setIsConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // Handle user status updates
          if (data.type === 'user_status_update' || data.event === 'user_status_update') {
            const update: UserStatusUpdate = {
              user_id: data.user_id || data.userId,
              is_online: data.is_online ?? data.isOnline ?? false,
              last_active_at: data.last_active_at || data.lastActiveAt || null,
            }
            onStatusUpdateRef.current?.(update)
          }
          // Handle new announcements
          else if (data.type === 'announcement' || data.event === 'new_announcement') {
            const announcement: AnnouncementUpdate = data.data || data
            if (announcement && announcement.id) {
              onAnnouncementRef.current?.(announcement)
            }
          }
        } catch (err) {
          console.warn('[WebSocket] Failed to parse message:', err)
        }
      }

      ws.onerror = (err) => {
        console.warn('[WebSocket] Error:', err)
        isConnectingRef.current = false
        setError(new Error('WebSocket connection error'))
      }

      ws.onclose = () => {
        // WebSocket disconnection logs suppressed
        isConnectingRef.current = false
        setIsConnected(false)
        wsRef.current = null

        // Attempt to reconnect if we haven't exceeded max attempts
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectDelay)
        } else {
          setError(new Error('WebSocket connection failed after multiple attempts'))
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.warn('[WebSocket] Failed to create connection:', err)
      isConnectingRef.current = false
      setError(err instanceof Error ? err : new Error('Failed to create WebSocket'))
    }
  }, []) // No dependencies - uses refs for mutable values

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    isConnectingRef.current = false
    setIsConnected(false)
  }, [])

  // Initial connection effect - runs once on mount
  useEffect(() => {
    const token = Cookies.get('auth_token')
    if (token) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, []) // Empty deps - only run on mount/unmount

  // Periodic auth check - separate from connection logic
  useEffect(() => {
    const interval = setInterval(() => {
      const token = Cookies.get('auth_token')
      const wsState = wsRef.current?.readyState
      
      // Connect if we have token but no connection
      if (token && !wsRef.current && !isConnectingRef.current) {
        connect()
      }
      // Disconnect if no token but have connection
      else if (!token && wsRef.current) {
        disconnect()
      }
      // Reconnect if connection is closed/closing and we still have token
      else if (token && wsState !== WebSocket.OPEN && wsState !== WebSocket.CONNECTING && !isConnectingRef.current) {
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          connect()
        }
      }
    }, 5000) // Check every 5 seconds instead of 1 second
    
    return () => clearInterval(interval)
  }, [connect, disconnect])

  return { isConnected, error }
}

