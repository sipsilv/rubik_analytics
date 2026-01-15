'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { adminAPI } from '@/lib/api'
import { ConnectionModal } from '@/components/ConnectionModal'
import { ArrowLeft, Settings, RefreshCw, Trash2, AlertTriangle, Plus, Copy, Check } from 'lucide-react'
import { Switch } from '@/components/ui/Switch'
import { SecondaryModal } from '@/components/ui/Modal'
import { RefreshButton } from '@/components/ui/RefreshButton'

export default function TrueDataPage() {
  const router = useRouter()
  const [connection, setConnection] = useState<any>(null)
  const [tokenInfo, setTokenInfo] = useState<any>(null)
  const [websocketStatus, setWebsocketStatus] = useState<{ running: boolean, connected: boolean } | null>(null)
  const [loading, setLoading] = useState(true)
  const [countdown, setCountdown] = useState<string>('--:--:--')
  const [countdownColor, setCountdownColor] = useState<'green' | 'orange' | 'red'>('green')
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isDeleteOpen, setIsDeleteOpen] = useState(false)
  const [isRefreshOpen, setIsRefreshOpen] = useState(false)
  const [isSuccessOpen, setIsSuccessOpen] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [tokenValue, setTokenValue] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const refreshInProgress = useRef(false)
  const tokenInfoRef = useRef(tokenInfo)

  // Standardized date/time formatter - consistent across all displays
  // Handles IST timezone correctly (backend sends IST timestamps with +05:30)
  const formatDateTime = (dateString: string | null | undefined): string => {
    if (!dateString) return 'N/A'
    try {
      // Parse the date string - backend sends IST format (e.g., "2026-01-03T04:00:00+05:30")
      const date = new Date(dateString)

      // Use Intl.DateTimeFormat to format in IST timezone explicitly
      // This ensures the time is displayed correctly regardless of browser timezone
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

      // Format the date parts
      const parts = formatter.formatToParts(date)
      const day = parts.find(p => p.type === 'day')?.value.padStart(2, '0') || '00'
      const month = parts.find(p => p.type === 'month')?.value || 'Jan'
      const year = parts.find(p => p.type === 'year')?.value || '2026'
      const hours = parts.find(p => p.type === 'hour')?.value.padStart(2, '0') || '00'
      const minutes = parts.find(p => p.type === 'minute')?.value.padStart(2, '0') || '00'
      const seconds = parts.find(p => p.type === 'second')?.value.padStart(2, '0') || '00'

      return `${day} ${month} ${year}, ${hours}:${minutes}:${seconds} IST`
    } catch (e) {
      // If parsing fails, try to extract time from ISO string directly
      try {
        // If it's an ISO string with timezone, try to parse it manually
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

  useEffect(() => {
    loadConnection()
  }, [])
  
  // Auto-refresh WebSocket status every 10 seconds when connection exists
  useEffect(() => {
    if (!connection) return
    
    loadWebSocketStatus() // Load immediately
    const wsStatusInterval = setInterval(() => {
      loadWebSocketStatus()
    }, 10000)
    
    return () => {
      clearInterval(wsStatusInterval)
    }
  }, [connection])

  // Auto-refresh WebSocket status every 10 seconds when connection exists
  useEffect(() => {
    if (!connection) return

    loadWebSocketStatus() // Load immediately
    const wsStatusInterval = setInterval(() => {
      loadWebSocketStatus()
    }, 10000)

    return () => {
      clearInterval(wsStatusInterval)
    }
  }, [connection])

  const loadConnection = async () => {
    try {
      setLoading(true)
      const connections = await adminAPI.getConnections()
      const truedata = connections.find((c: any) => {
        if (!c.provider) return false
        const provider = c.provider.toUpperCase().replace(/\s+/g, '').replace(/[_-]/g, '')
        return provider === 'TRUEDATA' || provider.includes('TRUEDATA')
      })

      // Debug logging
      console.log('[TrueData Page] All connections:', connections.map((c: any) => ({
        id: c.id,
        name: c.name,
        provider: c.provider,
        type: c.connection_type
      })))
      console.log('[TrueData Page] TrueData connection found:', truedata)

      if (truedata) {
        setConnection(truedata)
        await loadTokenStatus(truedata.id)
        await loadWebSocketStatus()
      } else {
        // No TrueData connection found
        setConnection(null)
        setWebsocketStatus(null)
      }
    } catch (error) {
      console.error('Error loading connection:', error)
    } finally {
      setLoading(false)
    }
  }


  const loadWebSocketStatus = async () => {
    try {
      const { announcementsAPI } = await import('@/lib/api')
      const response = await announcementsAPI.getTrueDataConnection()
      if (response.websocket_running !== undefined) {
        setWebsocketStatus({
          running: response.websocket_running || false,
          connected: response.websocket_connected || false
        })
      }
    } catch (error) {
      console.error('Error loading WebSocket status:', error)
      setWebsocketStatus({ running: false, connected: false })
    }
  }

  const loadTokenStatus = async (connectionId: number) => {
    try {
      console.log('[TrueData] Loading token status for connection:', connectionId)
      const response = await adminAPI.getTokenStatus(String(connectionId))
      console.log('[TrueData] Token status response:', response)

      // Handle standardized response format
      if (response.token_status) {
        // Map standardized response to frontend format
        // Backend is authoritative - use values directly
        setTokenInfo({
          token_status: response.token_status,
          expires_at: response.expires_at, // IST format from backend
          expires_at_ist: response.expires_at_ist || response.expires_at, // IST timestamp from backend
          expires_at_utc: response.expires_at_utc, // UTC for reference
          last_refreshed_at: response.last_refreshed_at,
          last_generated_at: response.last_refreshed_at, // Use last_refreshed_at as last_generated_at
          seconds_left: Number(response.seconds_left ?? 0), // Authoritative - frontend uses this ONLY
          is_expired: response.token_status === 'EXPIRED',
          is_expiring: false, // No longer used - refresh happens after expiry
          time_until_expiry_seconds: Number(response.seconds_left ?? 0),
          refresh_before_minutes: 0, // Refresh happens after expiry, not before
          next_auto_refresh_at: response.next_auto_refresh_at // Next 4:00 AM IST when token will auto-refresh
        })

        console.log('[TrueData] Token status loaded:', {
          token_status: response.token_status,
          seconds_left: response.seconds_left,
          expires_at: response.expires_at,
          expires_at_ist: response.expires_at_ist
        })

        // Fetch actual token value if token is active
        if (response.token_status === 'ACTIVE') {
          try {
            const tokenResponse = await adminAPI.getTrueDataToken(connectionId)
            console.log('[TrueData] Token value response:', tokenResponse ? 'Received' : 'None')
            if (tokenResponse?.access_token) {
              setTokenValue(tokenResponse.access_token)
            }
          } catch (error) {
            console.error('[TrueData] Error fetching token value:', error)
            setTokenValue(null)
          }
        } else {
          setTokenValue(null)
        }
      } else {
        console.log('[TrueData] No token status in response')
        setTokenInfo(null)
        setTokenValue(null)
      }
    } catch (error: any) {
      console.error('[TrueData] Error loading token status:', error)
      console.error('[TrueData] Error details:', {
        message: error?.message,
        response: error?.response?.data,
        status: error?.response?.status
      })
      setTokenInfo(null)
      setTokenValue(null)
    }
  }

  const handleCopyToken = async () => {
    if (!tokenValue) return

    try {
      await navigator.clipboard.writeText(tokenValue)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('Failed to copy token:', error)
    }
  }

  // Update tokenInfo ref when it changes
  useEffect(() => {
    tokenInfoRef.current = tokenInfo
  }, [tokenInfo])

  // AUTHORITATIVE TIMER: Uses ONLY seconds_left from backend
  // Frontend NEVER calculates expiry - only decrements seconds_left
  // seconds_left can be negative (expired) - we clamp to 0 for display
  useEffect(() => {
    if (!tokenInfo || tokenInfo.seconds_left === undefined || tokenInfo.seconds_left === null) {
      setCountdown('--:--:--')
      setCountdownColor('green')
      return
    }

    // Start with authoritative seconds_left from backend (authoritative source)
    // Clamp to 0 for display (negative means expired, show as 00:00:00)
    let currentSeconds = Math.max(0, tokenInfo.seconds_left)
    let lastBackendSeconds = tokenInfo.seconds_left

    const updateCountdown = () => {
      try {
        // Get latest tokenInfo from ref (may have been updated by polling)
        const currentTokenInfo = tokenInfoRef.current

        if (!currentTokenInfo || currentTokenInfo.seconds_left === undefined || currentTokenInfo.seconds_left === null) {
          setCountdown('--:--:--')
          setCountdownColor('green')
          return
        }

        // If backend provided new seconds_left (from polling), reset to authoritative value
        // This is the ONLY way to update the countdown - backend is authoritative
        if (currentTokenInfo.seconds_left !== lastBackendSeconds) {
          currentSeconds = Math.max(0, currentTokenInfo.seconds_left)
          lastBackendSeconds = currentTokenInfo.seconds_left
        } else {
          // Decrement by 1 second (simple countdown, no calculations)
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

        // Use backend token_status (authoritative) - frontend does NOT calculate status
        const currentStatus = currentTokenInfo.token_status

        // Color based on backend status (authoritative)
        // Timer shows countdown to 4:00 AM IST expiry
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

  // NO AUTO-REFRESH - Only refresh when user clicks refresh button or page loads

  const handleToggle = async () => {
    if (!connection?.id) return

    setLoading(true)
    try {
      await adminAPI.toggleConnection(String(connection.id))
      await loadConnection()
    } catch (error) {
      console.error('Error toggling connection:', error)
    } finally {
      setLoading(false)
    }
  }


  const handleRefreshToken = async () => {
    if (!connection?.id) return

    // Prevent multiple simultaneous refresh calls
    if (refreshInProgress.current) {
      console.log('[TrueData] Refresh already in progress, skipping...')
      return
    }

    setIsRefreshOpen(false)
    refreshInProgress.current = true
    setRefreshing(true)
    setLoading(true)

    try {
      console.log('[TrueData] Refreshing token for connection:', connection.id)
      const response = await adminAPI.refreshToken(String(connection.id))
      console.log('[TrueData] Token refresh response:', response)

      await loadConnection() // Reload connection to get updated status
      await loadTokenStatus(connection.id)
      await loadWebSocketStatus() // Refresh WebSocket status
      // Show success message in modal (refresh always generates a new token)
      setSuccessMessage(response.message || 'Token refreshed successfully!')
      setIsSuccessOpen(true)
    } catch (error: any) {
      console.error('[TrueData] Error refreshing token:', error)

      // Extract error message
      let errorMessage = 'Failed to refresh token'
      if (error?.response?.data?.detail) {
        errorMessage = error.response.data.detail
      } else if (error?.message) {
        errorMessage = error.message
      }

      // Show error to user in modal
      setSuccessMessage(`Error: ${errorMessage}`)
      setIsSuccessOpen(true)
    } finally {
      setRefreshing(false)
      setLoading(false)
      refreshInProgress.current = false
    }
  }

  const handleDelete = async () => {
    if (!connection?.id) return

    setDeleting(true)
    try {
      // Delete token from storage
      try {
        await adminAPI.deleteConnection(String(connection.id))
      } catch (error) {
        console.error('Error deleting connection:', error)
      }

      // Navigate back to connections page
      router.push('/admin/connections')
    } catch (error) {
      console.error('Error deleting connection:', error)
    } finally {
      setDeleting(false)
      setIsDeleteOpen(false)
    }
  }

  if (loading && !connection) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-text-secondary">Loading...</div>
      </div>
    )
  }

  if (!connection) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push('/admin/connections')}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
              TrueData Connection
            </h1>
            <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
              Master token provider for multiple app connections
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div></div>
          <Button size="sm" onClick={() => setIsEditOpen(true)}>
            <Plus className="w-4 h-4 mr-1" />
            Create TrueData Connection
          </Button>
        </div>

        <Card className="p-6 border-2 border-dashed border-text-secondary/30 bg-secondary/5">
          <div className="text-center space-y-4">
            <div>
              <h3 className="text-lg font-sans font-semibold text-text-primary mb-2">
                No TrueData Connection Found
              </h3>
              <p className="text-sm text-text-secondary mb-4">
                Configure TrueData as a central token provider for multiple app connections.
              </p>
              <div className="text-xs text-text-secondary/80 space-y-1 text-left max-w-md mx-auto mb-6">
                <p>• Set Provider to <span className="font-mono font-semibold text-primary">TrueData</span></p>
                <p>• Enter your TrueData username and password</p>
                <p>• Token will be generated and refreshed automatically</p>
              </div>
            </div>
          </div>
        </Card>

        <ConnectionModal
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          onUpdate={loadConnection}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-1">
          <button
            onClick={() => router.push('/admin/connections')}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <h1 className="text-2xl font-sans font-semibold text-text-primary">
            {connection.name}
          </h1>
        </div>
        <p className="text-xs font-sans text-text-secondary">
          Master Token Provider
        </p>
      </div>

      <div className="flex items-center justify-between">
        <div></div>
        <div className="flex gap-2">
          <RefreshButton
            variant="secondary"
            size="sm"
            onClick={async () => {
              if (connection?.id) {
                await loadTokenStatus(connection.id)
                await loadConnection()
                await loadWebSocketStatus()
              }
            }}
            disabled={loading}
          />
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setIsRefreshOpen(true)}
            disabled={loading || refreshing || !connection.is_enabled}
          >
            <RefreshCw className={`w-4 h-4 mr-1 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh Token
          </Button>
          <Button size="sm" variant="primary" onClick={() => setIsEditOpen(true)}>
            <Settings className="w-4 h-4 mr-1" />
            Configure
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => setIsDeleteOpen(true)}
          >
            <Trash2 className="w-4 h-4 mr-1" />
            Delete
          </Button>
        </div>
      </div>

      {/* Connection & Token Status Table */}
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-sans font-semibold text-text-primary">Connection & Token Information</h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full border-collapse table-fixed">
            <colgroup>
              <col className="w-1/3" />
              <col className="w-2/3" />
            </colgroup>
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-3 px-4 text-xs font-sans font-semibold text-text-secondary uppercase tracking-wider">Property</th>
                <th className="text-left py-3 px-4 text-xs font-sans font-semibold text-text-secondary uppercase tracking-wider">Value</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {/* Connection Status Row */}
              <tr className="hover:bg-background/50 transition-colors">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Connection Status</td>
                <td className="py-3 px-4 align-top">
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-sans font-semibold ${connection.status === 'CONNECTED' ? 'bg-success/10 text-success border border-success/20' :
                      connection.status === 'DISCONNECTED' || connection.status === 'ERROR' ? 'bg-error/10 text-error border border-error/20' :
                        'bg-text-secondary/10 text-text-secondary border border-text-secondary/20'
                    }`}>
                    {connection.status}
                  </span>
                </td>
              </tr>

              {/* Enabled Status Row - Slider Toggle */}
              <tr className="hover:bg-background/50 transition-colors">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Enabled</td>
                <td className="py-3 px-4 align-top">
                  <div className="flex items-center gap-3">
                    <Switch
                      checked={connection.is_enabled}
                      onCheckedChange={(checked) => {
                        if (checked !== connection.is_enabled) {
                          handleToggle()
                        }
                      }}
                      disabled={loading}
                    />
                    <span className="text-sm font-sans text-text-secondary">
                      {connection.is_enabled ? 'Enabled' : 'Disabled'}
                    </span>
                  </div>
                </td>
              </tr>

              {/* Environment Row */}
              <tr className="hover:bg-background/50 transition-colors">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Environment</td>
                <td className="py-3 px-4 text-sm font-sans text-text-primary align-top">{connection.environment}</td>
              </tr>

              {/* Provider Row */}
              <tr className="hover:bg-background/50 transition-colors">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Provider</td>
                <td className="py-3 px-4 text-sm font-sans text-text-primary align-top">{connection.provider}</td>
              </tr>

              {/* URL Row */}
              <tr className="hover:bg-background/50 transition-colors">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">URL</td>
                <td className="py-3 px-4 text-sm font-sans font-mono text-text-primary align-top">
                  {connection.url || 'https://auth.truedata.in/token'}
                </td>
              </tr>

              {/* Port Row */}
              <tr className="hover:bg-background/50 transition-colors">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Port</td>
                <td className="py-3 px-4 text-sm font-sans font-mono text-text-primary align-top">
                  {connection.port || '8086'}
                </td>
              </tr>

              {/* WebSocket Status Row */}
              {connection && (
                <tr className="hover:bg-background/50 transition-colors">
                  <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">WebSocket Status</td>
                  <td className="py-3 px-4 align-top">
                    {websocketStatus ? (
                      <div className="flex items-center gap-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-sans font-semibold ${websocketStatus.connected
                            ? 'bg-success/10 text-success border border-success/20'
                            : websocketStatus.running
                              ? 'bg-warning/10 text-warning border border-warning/20'
                              : 'bg-error/10 text-error border border-error/20'
                          }`}>
                          {websocketStatus.connected ? 'Connected' : websocketStatus.running ? 'Running' : 'Disconnected'}
                        </span>
                        {(websocketStatus.connected || websocketStatus.running) && (
                          <span className="text-xs font-sans text-text-secondary">
                            {websocketStatus.connected
                              ? 'Receiving live announcements'
                              : 'Service running but not connected'}
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-sm font-sans text-text-secondary">Loading...</span>
                    )}
                  </td>
                </tr>
              )}

              {/* Token Status Row */}
              <tr className="hover:bg-background/50 transition-colors border-t-2 border-border">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Token Status</td>
                <td className="py-3 px-4 align-top">
                  {tokenInfo ? (
                    <div className="flex items-center gap-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-sans font-semibold ${tokenInfo.token_status === 'EXPIRED' || tokenInfo.is_expired
                          ? 'bg-error/10 text-error border border-error/20'
                          : tokenInfo.token_status === 'ERROR'
                            ? 'bg-error/10 text-error border border-error/20'
                            : tokenInfo.token_status === 'ACTIVE'
                              ? 'bg-success/10 text-success border border-success/20'
                              : 'bg-text-secondary/10 text-text-secondary border border-text-secondary/20'
                        }`}>
                        {tokenInfo.token_status === 'EXPIRED' ? 'Expired' :
                          tokenInfo.token_status === 'ERROR' ? 'Error' :
                            tokenInfo.token_status === 'ACTIVE' ? 'Active' :
                              tokenInfo.token_status === 'NOT_GENERATED' ? 'Not Generated' :
                                'Unknown'}
                      </span>
                    </div>
                  ) : (
                    <span className="text-sm font-sans text-text-secondary">No token generated</span>
                  )}
                </td>
              </tr>

              {/* Token Value Row */}
              {tokenValue && (
                <tr className="hover:bg-background/50 transition-colors">
                  <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Token</td>
                  <td className="py-3 px-4 align-top">
                    <div className="flex items-center gap-2">
                      <code className="text-xs font-mono bg-background/50 px-2 py-1 rounded border border-border text-text-primary break-all max-w-md">
                        {tokenValue}
                      </code>
                      <button
                        onClick={handleCopyToken}
                        className="flex-shrink-0 p-1.5 hover:bg-background/50 rounded transition-colors"
                        title={copied ? 'Copied!' : 'Copy token'}
                      >
                        {copied ? (
                          <Check className="w-4 h-4 text-success" />
                        ) : (
                          <Copy className="w-4 h-4 text-text-secondary hover:text-text-primary" />
                        )}
                      </button>
                    </div>
                  </td>
                </tr>
              )}

              {/* Token Expiry Timer - Prominent Display */}
              <tr className="hover:bg-background/50 transition-colors bg-primary/5">
                <td className="py-4 px-4 text-sm font-sans font-semibold text-text-primary align-top">Token Expires In</td>
                <td className="py-4 px-4 align-top">
                  {tokenInfo && tokenInfo.seconds_left !== undefined && tokenInfo.seconds_left !== null ? (
                    <div className="flex items-center gap-3">
                      <div className={`text-2xl font-mono font-bold tracking-wider ${countdownColor === 'red' ? 'text-error' :
                          'text-success'
                        }`}>
                        {countdown}
                      </div>
                      <div className={`w-3 h-3 rounded-full ${countdownColor === 'red' ? 'bg-error animate-pulse' :
                          'bg-success'
                        }`}></div>
                    </div>
                  ) : (
                    <span className="text-sm font-sans text-text-secondary">--:--:--</span>
                  )}
                </td>
              </tr>

              {/* Expires At Row */}
              {tokenInfo && (tokenInfo.expires_at || tokenInfo.expires_at_ist) && (
                <tr className="hover:bg-background/50 transition-colors">
                  <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Expires At</td>
                  <td className="py-3 px-4 text-sm font-sans font-mono text-text-primary align-top">
                    {formatDateTime(tokenInfo.expires_at_ist || tokenInfo.expires_at)}
                  </td>
                </tr>
              )}

              {/* Last Refreshed Row */}
              {tokenInfo && tokenInfo.last_refreshed_at && (
                <tr className="hover:bg-background/50 transition-colors">
                  <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Last Refreshed</td>
                  <td className="py-3 px-4 text-sm font-sans font-mono text-text-primary align-top">
                    {formatDateTime(tokenInfo.last_refreshed_at)}
                  </td>
                </tr>
              )}

              {/* Connection ID Row */}
              <tr className="hover:bg-background/50 transition-colors">
                <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Connection ID</td>
                <td className="py-3 px-4 text-sm font-sans font-mono text-text-primary align-top">{connection.id}</td>
              </tr>

              {/* Next Auto Refresh Row */}
              {tokenInfo && tokenInfo.next_auto_refresh_at && (
                <tr className="hover:bg-background/50 transition-colors">
                  <td className="py-3 px-4 text-sm font-sans font-medium text-text-secondary align-top">Next Auto Refresh</td>
                  <td className="py-3 px-4 text-sm font-sans font-mono text-text-primary align-top">
                    {formatDateTime(tokenInfo.next_auto_refresh_at)}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>


      {/* Edit Modal */}
      <ConnectionModal
        isOpen={isEditOpen}
        onClose={() => setIsEditOpen(false)}
        connection={connection}
        onUpdate={loadConnection}
      />

      {/* Refresh Token Confirmation Modal */}
      <SecondaryModal
        isOpen={isRefreshOpen}
        onClose={() => setIsRefreshOpen(false)}
        title=""
        showCloseButton={true}
        closeOnBackdropClick={true}
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <RefreshCw className={`w-6 h-6 text-primary ${refreshing ? 'animate-spin' : ''}`} />
            <h3 className="text-lg font-sans font-semibold text-text-primary">
              Refresh Token
            </h3>
          </div>
          <div className="bg-primary/10 border border-primary/30 rounded-lg p-4">
            <p className="text-text-primary font-semibold mb-2">Confirm Token Refresh</p>
            <p className="text-text-secondary">
              Are you sure you want to refresh the TrueData token? This will generate a new token
              {tokenInfo?.expires_at_ist && ` that expires at ${formatDateTime(tokenInfo.expires_at_ist)}`}.
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setIsRefreshOpen(false)} disabled={refreshing}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleRefreshToken}
              disabled={refreshing}
            >
              {refreshing ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                  Refreshing...
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4 mr-1" />
                  Refresh Token
                </>
              )}
            </Button>
          </div>
        </div>
      </SecondaryModal>

      {/* Delete Confirmation Modal */}
      <SecondaryModal
        isOpen={isDeleteOpen}
        onClose={() => setIsDeleteOpen(false)}
        title=""
        showCloseButton={true}
        closeOnBackdropClick={true}
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-6 h-6 text-error" />
            <h3 className="text-lg font-sans font-semibold text-error">
              Delete TrueData Connection
            </h3>
          </div>
          <div className="bg-error/10 border border-error/30 rounded-lg p-4">
            <p className="text-error font-semibold mb-2">Warning!</p>
            <p className="text-text-secondary">
              Are you sure you want to delete this connection? This action cannot be undone.
              All tokens will be removed and dependent connections will be disabled.
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="secondary" onClick={() => setIsDeleteOpen(false)} disabled={deleting}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={handleDelete}
              disabled={deleting}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </Button>
          </div>
        </div>
      </SecondaryModal>

      {/* Success/Error Message Modal */}
      <SecondaryModal
        isOpen={isSuccessOpen}
        onClose={() => setIsSuccessOpen(false)}
        title=""
        showCloseButton={true}
        closeOnBackdropClick={true}
      >
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            {successMessage.startsWith('Error:') ? (
              <AlertTriangle className="w-6 h-6 text-error" />
            ) : (
              <Check className="w-6 h-6 text-success" />
            )}
            <h3 className={`text-lg font-sans font-semibold ${successMessage.startsWith('Error:') ? 'text-error' : 'text-success'
              }`}>
              {successMessage.startsWith('Error:') ? 'Error' : 'Success'}
            </h3>
          </div>
          <div className={`rounded-lg p-4 ${successMessage.startsWith('Error:')
              ? 'bg-error/10 border border-error/30'
              : 'bg-success/10 border border-success/30'
            }`}>
            <p className={`font-semibold mb-2 ${successMessage.startsWith('Error:') ? 'text-error' : 'text-success'
              }`}>
              {successMessage.startsWith('Error:') ? 'Token Refresh Failed' : 'Token Refreshed'}
            </p>
            <p className="text-text-secondary">
              {successMessage}
            </p>
          </div>
          <div className="flex justify-end gap-2 pt-4">
            <Button
              variant="primary"
              onClick={() => setIsSuccessOpen(false)}
            >
              OK
            </Button>
          </div>
        </div>
      </SecondaryModal>
    </div>
  )
}

