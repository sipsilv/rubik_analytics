'use client'

import { useState, useEffect, useRef } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { adminAPI } from '@/lib/api'
import { Settings, Power, PowerOff } from 'lucide-react'
import { RefreshButton } from '@/components/ui/RefreshButton'

interface TrueDataConnectionCardProps {
  connection: any
  onConfigure: () => void
  onViewDetails: () => void
  onUpdate: () => void
}

export function TrueDataConnectionCard({ connection, onConfigure, onViewDetails, onUpdate }: TrueDataConnectionCardProps) {
  const [tokenInfo, setTokenInfo] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [countdown, setCountdown] = useState<string>('--:--:--')
  const [countdownColor, setCountdownColor] = useState<'green' | 'orange' | 'red'>('green')
  const tokenInfoRef = useRef(tokenInfo)

  // Standardized date/time formatter - consistent across all displays
  const formatDateTime = (dateString: string | null | undefined): string => {
    if (!dateString) return 'N/A'
    try {
      const date = new Date(dateString)
      const formatter = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: 'short',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      })

      const parts = formatter.formatToParts(date)
      const day = parts.find(p => p.type === 'day')?.value.padStart(2, '0') || '00'
      const month = parts.find(p => p.type === 'month')?.value || 'Jan'
      const year = parts.find(p => p.type === 'year')?.value || '2026'
      const hours = parts.find(p => p.type === 'hour')?.value.padStart(2, '0') || '00'
      const minutes = parts.find(p => p.type === 'minute')?.value.padStart(2, '0') || '00'
      const seconds = parts.find(p => p.type === 'second')?.value.padStart(2, '0') || '00'

      return `${day} ${month} ${year}, ${hours}:${minutes}:${seconds} IST`
    } catch (e) {
      try {
        const match = dateString.match(/(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/)
        if (match) {
          const [, year, monthNum, day, hours, minutes, seconds] = match
          const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
          const month = monthNames[parseInt(monthNum) - 1] || 'Jan'
          return `${day} ${month} ${year}, ${hours}:${minutes}:${seconds} IST`
        }
      } catch (e2) {
        // If all parsing fails, return the string as-is
      }
      return dateString
    }
  }

  // Load token status
  const loadTokenStatus = async () => {
    if (!connection?.id) return

    try {
      const response = await adminAPI.getTokenStatus(String(connection.id))
      if (response.token_status) {
        // Map standardized response to frontend format
        setTokenInfo({
          token_status: response.token_status,
          expires_at: response.expires_at,
          expires_at_ist: response.expires_at_ist || response.expires_at,
          expires_at_utc: response.expires_at_utc,
          last_refreshed_at: response.last_refreshed_at,
          seconds_left: response.seconds_left,
          is_expired: response.token_status === 'EXPIRED',
          next_auto_refresh_at: response.next_auto_refresh_at
        })
      } else {
        setTokenInfo(null)
      }
    } catch (error) {
      console.error('Error loading token status:', error)
      setTokenInfo(null)
    }
  }

  // Update tokenInfo ref when it changes
  useEffect(() => {
    tokenInfoRef.current = tokenInfo
  }, [tokenInfo])

  // AUTHORITATIVE TIMER: Uses ONLY seconds_left from backend
  useEffect(() => {
    if (!tokenInfo || tokenInfo.seconds_left === undefined || tokenInfo.seconds_left === null) {
      setCountdown('--:--:--')
      setCountdownColor('green')
      return
    }

    // Start with authoritative seconds_left from backend
    let currentSeconds = Math.max(0, Number(tokenInfo.seconds_left) || 0)
    let lastBackendSeconds = tokenInfo.seconds_left

    const updateCountdown = () => {
      try {
        const currentTokenInfo = tokenInfoRef.current

        if (!currentTokenInfo || currentTokenInfo.seconds_left === undefined || currentTokenInfo.seconds_left === null) {
          setCountdown('--:--:--')
          setCountdownColor('green')
          return
        }

        // If backend provided new seconds_left (from polling), reset to authoritative value
        if (currentTokenInfo.seconds_left !== lastBackendSeconds) {
          currentSeconds = Math.max(0, Number(currentTokenInfo.seconds_left) || 0)
          lastBackendSeconds = currentTokenInfo.seconds_left
        } else {
          // Decrement by 1 second
          currentSeconds = Math.max(0, currentSeconds - 1)
        }

        // Format countdown
        if (currentSeconds <= 0) {
          setCountdown('00:00:00')
          setCountdownColor('red')
          return
        }

        const hours = Math.floor(currentSeconds / 3600)
        const minutes = Math.floor((currentSeconds % 3600) / 60)
        const secs = Math.floor(currentSeconds % 60)

        const formatted = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
        setCountdown(formatted)

        // Color based on backend status
        const currentStatus = currentTokenInfo.token_status
        if (currentStatus === 'EXPIRED' || currentSeconds <= 0) {
          setCountdownColor('red')
        } else if (currentStatus === 'ACTIVE') {
          setCountdownColor('green')
        } else {
          setCountdownColor('green')
        }
      } catch (error) {
        console.error('Error updating countdown:', error)
        setCountdown('--:--:--')
        setCountdownColor('green')
      }
    }

    // Update immediately
    updateCountdown()

    // Update every second (decrement timer)
    const interval = setInterval(updateCountdown, 1000)

    return () => {
      clearInterval(interval)
    }
  }, [tokenInfo, connection?.id])

  // Load token status on mount and when connection changes (no auto-polling)
  useEffect(() => {
    loadTokenStatus()
  }, [connection?.id])

  const handleToggle = async () => {
    if (!connection?.id) return

    setLoading(true)
    try {
      await adminAPI.toggleConnection(String(connection.id))
      await loadTokenStatus()
      onUpdate()
    } catch (error) {
      console.error('Error toggling connection:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRefreshToken = async () => {
    if (!connection?.id) return

    setLoading(true)
    try {
      await adminAPI.refreshToken(String(connection.id))
      await loadTokenStatus()
      onUpdate()
    } catch (error) {
      console.error('Error refreshing token:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'CONNECTED':
        return 'text-success'
      case 'ERROR':
        return 'text-error'
      case 'DISCONNECTED':
      default:
        return 'text-text-secondary'
    }
  }

  const getTokenStatusText = () => {
    if (!tokenInfo) return 'No Token'
    if (tokenInfo.is_expired) return 'Expired'
    if (tokenInfo.needs_refresh) return 'Refreshing Soon'
    return 'Active'
  }

  const getTokenStatusColor = () => {
    if (!tokenInfo) return 'text-text-secondary'
    if (tokenInfo.is_expired) return 'text-error'
    if (tokenInfo.needs_refresh) return 'text-warning'
    return 'text-success'
  }

  return (
    <Card className="p-6 border-2 hover:shadow-lg transition-all duration-200 flex flex-col w-full max-w-sm">
      <div className="space-y-5 flex-1 flex flex-col h-full">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-sans font-semibold text-text-primary">
              {connection?.name || 'TrueData'}
            </h3>
            <p className="text-xs text-text-secondary mt-1">
              Master Token Provider
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-2.5 py-1 text-xs font-bold rounded-full uppercase ${getStatusColor(connection?.status || 'DISCONNECTED')}`}>
              {connection?.status || 'DISCONNECTED'}
            </span>
            {connection?.is_enabled ? (
              <Power className="w-5 h-5 text-success" />
            ) : (
              <PowerOff className="w-5 h-5 text-text-secondary" />
            )}
          </div>
        </div>

        {/* Token Status */}
        <div className="border border-[#1f2a44] p-5 rounded-lg bg-secondary/5">
          <div className="flex items-center justify-between mb-4">
            <span className="text-sm font-semibold text-text-primary">Token Status</span>
            <span className={`text-sm font-bold px-2 py-1 rounded ${getTokenStatusColor()}`}>
              {getTokenStatusText()}
            </span>
          </div>

          {tokenInfo && (
            <div className="space-y-3">
              {/* Timer */}
              <div className="flex items-center justify-between">
                <span className="text-xs text-text-secondary">Expires In</span>
                <div className="flex items-center gap-2">
                  <span className={`text-xl font-mono font-bold tracking-wider ${countdownColor === 'red' ? 'text-error' :
                    countdownColor === 'orange' ? 'text-warning' :
                      'text-success'
                    }`}>
                    {countdown}
                  </span>
                  <div className={`w-2.5 h-2.5 rounded-full ${countdownColor === 'red' ? 'bg-error animate-pulse' :
                    countdownColor === 'orange' ? 'bg-warning' :
                      'bg-success'
                    }`}></div>
                </div>
              </div>

              {/* Next Auto Refresh */}
              {tokenInfo.next_auto_refresh_at && (
                <div className="flex items-center justify-between pt-2 border-t border-[#1f2a44]">
                  <span className="text-xs text-text-secondary">Next Auto Refresh</span>
                  <span className="text-xs text-text-primary font-mono">
                    {formatDateTime(tokenInfo.next_auto_refresh_at)}
                  </span>
                </div>
              )}

              {/* Last Refreshed */}
              {tokenInfo.last_refreshed_at && (
                <div className="flex items-center justify-between">
                  <span className="text-xs text-text-secondary">Last Refreshed</span>
                  <span className="text-xs text-text-primary font-mono">
                    {formatDateTime(tokenInfo.last_refreshed_at)}
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={onViewDetails}
            className="flex-1"
          >
            <Settings className="w-4 h-4 mr-1" />
            Settings
          </Button>

          <RefreshButton
            variant="secondary"
            size="sm"
            onClick={handleRefreshToken}
            disabled={loading || !connection?.is_enabled}
            className="flex-1"
          >
            Refresh Token
          </RefreshButton>

          <Button
            variant={connection?.is_enabled ? "secondary" : "primary"}
            size="sm"
            onClick={handleToggle}
            disabled={loading}
            className="flex-1"
          >
            {connection?.is_enabled ? (
              <>
                <PowerOff className="w-4 h-4 mr-1" />
                Disable
              </>
            ) : (
              <>
                <Power className="w-4 h-4 mr-1" />
                Enable
              </>
            )}
          </Button>
        </div>
      </div>
    </Card>
  )
}

