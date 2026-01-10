'use client'

import { useEffect, useState, useRef, useCallback } from 'react'
import Cookies from 'js-cookie'

const API_URL = process.env.NEXT_PUBLIC_API_URL;

// Convert HTTP URL to WebSocket URL
const getWebSocketUrl = (): string => {
  const url = API_URL.replace(/^http/, 'ws')
  const token = Cookies.get('auth_token')
  const wsPath = `${url}/api/v1/ws`
  return token ? `${wsPath}?token=${token}` : wsPath
}

export interface Announcement {
  id: string
  trade_date?: string
  script_code?: number
  symbol_nse?: string
  symbol_bse?: string
  company_name?: string
  news_headline?: string
  descriptor_name?: string
  announcement_type?: string
  news_subhead?: string
  news_body?: string
  descriptor_category?: string
  date_of_meeting?: string
  links?: Array<{ title?: string; url: string }>
}

interface UseAnnouncementsWebSocketReturn {
  isConnected: boolean
  error: Error | null
}

/**
 * Hook to manage WebSocket connection for real-time announcement updates
 */
export function useAnnouncementsWebSocket(
  onNewAnnouncement?: (announcement: Announcement) => void
): UseAnnouncementsWebSocketReturn {
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef(0)
  const isConnectingRef = useRef(false)
  const maxReconnectAttempts = 10
  const reconnectDelay = 3000 // 3 seconds
  
  // Use ref for callback to avoid dependency issues
  const onNewAnnouncementRef = useRef(onNewAnnouncement)
  onNewAnnouncementRef.current = onNewAnnouncement

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
        isConnectingRef.current = false
        setIsConnected(true)
        setError(null)
        reconnectAttemptsRef.current = 0
        console.log('[Announcements WebSocket] Connected')
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          
          // Handle new announcement
          if (data.type === 'announcement' || data.event === 'new_announcement') {
            const announcement = data.data || data
            if (announcement && announcement.id) {
              onNewAnnouncementRef.current?.(announcement)
            }
          }
          // Handle connection status
          else if (data.type === 'connection' || data.type === 'pong') {
            // Connection alive
          }
        } catch (err) {
          console.warn('[Announcements WebSocket] Failed to parse message:', err)
        }
      }

      ws.onerror = (err) => {
        console.warn('[Announcements WebSocket] Error:', err)
        isConnectingRef.current = false
        setError(new Error('WebSocket connection error'))
      }

      ws.onclose = () => {
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
      console.warn('[Announcements WebSocket] Failed to create connection:', err)
      isConnectingRef.current = false
      setError(err instanceof Error ? err : new Error('Failed to create WebSocket'))
    }
  }, [])

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

  // Initial connection effect
  useEffect(() => {
    const token = Cookies.get('auth_token')
    if (token) {
      connect()
    }

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  // Periodic auth check
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
          reconnectAttemptsRef.current = 0 // Reset attempts for periodic check
          connect()
        }
      }
    }, 5000) // Check every 5 seconds
    
    return () => clearInterval(interval)
  }, [connect, disconnect])

  return { isConnected, error }
}

