'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import Cookies from 'js-cookie'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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

interface UseWebSocketStatusReturn {
  isConnected: boolean
  error: Error | null
}

/**
 * Hook to manage WebSocket connection for real-time user status updates
 * Falls back gracefully if WebSocket is not available
 */
export function useWebSocketStatus(
  onStatusUpdate?: (update: UserStatusUpdate) => void
): UseWebSocketStatusReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = 3000 // 3 seconds

  const connect = useCallback(() => {
    // Don't connect if already connected or no auth token
    const token = Cookies.get('auth_token')
    if (!token || wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }

    try {
      const wsUrl = getWebSocketUrl()
      const ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('[WebSocket] Connected')
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
            onStatusUpdate?.(update)
          }
        } catch (err) {
          console.warn('[WebSocket] Failed to parse message:', err)
        }
      }

      ws.onerror = (err) => {
        console.warn('[WebSocket] Error:', err)
        setError(new Error('WebSocket connection error'))
        setIsConnected(false)
      }

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected')
        setIsConnected(false)
        wsRef.current = null

        // Attempt to reconnect if we haven't exceeded max attempts
        if (reconnectAttemptsRef.current < maxReconnectAttempts) {
          reconnectAttemptsRef.current++
          console.log(
            `[WebSocket] Reconnecting in ${reconnectDelay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`
          )
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, reconnectDelay)
        } else {
          console.log('[WebSocket] Max reconnect attempts reached. WebSocket disabled.')
          setError(new Error('WebSocket connection failed after multiple attempts'))
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.warn('[WebSocket] Failed to create connection:', err)
      setError(err instanceof Error ? err : new Error('Failed to create WebSocket'))
      setIsConnected(false)
    }
  }, [onStatusUpdate])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  useEffect(() => {
    // Only connect if we have an auth token
    const token = Cookies.get('auth_token')
    if (token) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  // Reconnect when auth state changes
  useEffect(() => {
    const checkAuth = () => {
      const token = Cookies.get('auth_token')
      if (token && !isConnected && !wsRef.current) {
        connect()
      } else if (!token && wsRef.current) {
        disconnect()
      }
    }
    
    // Check immediately
    checkAuth()
    
    // Set up interval to check auth token changes
    const interval = setInterval(checkAuth, 1000)
    
    return () => clearInterval(interval)
  }, [isConnected, connect, disconnect])

  return { isConnected, error }
}

