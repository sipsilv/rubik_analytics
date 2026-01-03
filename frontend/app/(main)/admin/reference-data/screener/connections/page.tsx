'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { ArrowLeft, Play, Square } from 'lucide-react'
import { screenerAPI } from '@/lib/api'
import { AddConnectionModal } from './AddConnectionModal'
import { RefreshButton } from '@/components/ui/RefreshButton'

type ConnectionType = 'WEBSITE_SCRAPING' | 'API_CONNECTION'
type ConnectionStatus = 'Idle' | 'Running' | 'Completed' | 'Failed' | 'Stopped'

interface ScreenerConnection {
  id: number
  connection_name: string
  connection_type: ConnectionType
  status: ConnectionStatus
  last_run: string | null
  records_loaded: number
  website_name?: string
  api_provider_name?: string
}

export default function ScreenerConnectionsPage() {
  const router = useRouter()
  const [connections, setConnections] = useState<ScreenerConnection[]>([])
  const [loading, setLoading] = useState(true)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [runningJobs, setRunningJobs] = useState<Set<number>>(new Set())
  const hasLoadedRef = useRef(false)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const previousStatusesRef = useRef<Map<number, ConnectionStatus>>(new Map())

  useEffect(() => {
    // Prevent double call in React Strict Mode
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true
    loadConnections(true) // Show loading on initial load
    
    // Set up polling for real-time status updates (every 2 seconds for more responsive updates)
    // This automatically pushes status updates to frontend
    // More frequent polling ensures status changes are detected quickly
    pollingIntervalRef.current = setInterval(() => {
      loadConnections(false) // Don't show loading spinner on polling updates
    }, 2000) // Reduced from 3s to 2s for faster status updates
    
    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current)
        pollingIntervalRef.current = null
      }
    }
  }, [])

  const loadConnections = async (showLoading = false) => {
    try {
      if (showLoading) {
        setLoading(true)
      }
      const data = await screenerAPI.getConnections()
      
      // Detect status changes and trigger immediate refresh if status changed
      const statusChanged = data?.some((conn: ScreenerConnection) => {
        const prevStatus = previousStatusesRef.current.get(conn.id)
        const currentStatus = conn.status || 'Idle'
        if (prevStatus && prevStatus !== currentStatus) {
          // Status changed - especially important for terminal states
          if (prevStatus === 'Running' && (currentStatus === 'Failed' || currentStatus === 'Completed' || currentStatus === 'Stopped')) {
            return true // Terminal state change from Running
          }
          return true // Any status change
        }
        return false
      })
      
      // Update previous statuses
      const newStatuses = new Map<number, ConnectionStatus>()
      data?.forEach((conn: ScreenerConnection) => {
        newStatuses.set(conn.id, (conn.status || 'Idle') as ConnectionStatus)
      })
      previousStatusesRef.current = newStatuses
      
      setConnections(data || [])
      
      // Update runningJobs based on actual status
      const runningIds = new Set<number>()
      data?.forEach((conn: ScreenerConnection) => {
        if (conn.status === 'Running') {
          runningIds.add(conn.id)
        }
      })
      setRunningJobs(runningIds)
      
      // If status changed (especially from Running to terminal state), refresh again immediately after a brief delay
      if (statusChanged) {
        console.log('[Screener Connections] Status change detected, scheduling immediate refresh...')
        setTimeout(() => {
          loadConnections(false) // Immediate refresh without loading spinner
        }, 500) // 500ms delay to ensure backend has updated
      }
    } catch (e) {
      console.error('Failed to load connections:', e)
      setConnections([])
    } finally {
      if (showLoading) {
        setLoading(false)
      }
    }
  }

  const handleStart = async (connectionId: number) => {
    try {
      setRunningJobs(prev => new Set(prev).add(connectionId))
      await screenerAPI.startScraping(connectionId)
      
      // Load connections immediately to show Running status
      await loadConnections(true)
      
      // Schedule additional refresh after a short delay to catch status changes quickly
      setTimeout(() => {
        loadConnections(false)
      }, 1000)
    } catch (e: any) {
      console.error('Failed to start scraping:', e)
      if (e.response?.status === 409) {
        alert('Scraping is already in progress for this connection.')
      } else {
        alert('Failed to start scraping. Please try again.')
      }
      setRunningJobs(prev => {
        const newSet = new Set(prev)
        newSet.delete(connectionId)
        return newSet
      })
      // Refresh to get accurate status
      await loadConnections(false)
    }
  }

  const handleStop = async (connectionId: number) => {
    try {
      await screenerAPI.stopScraping(connectionId)
      setRunningJobs(prev => {
        const newSet = new Set(prev)
        newSet.delete(connectionId)
        return newSet
      })
      await loadConnections(true)
      
      // Schedule additional refresh to catch status change to Stopped
      setTimeout(() => {
        loadConnections(false)
      }, 500)
      
      alert('Scraping stopped successfully')
    } catch (e: any) {
      console.error('Failed to stop scraping:', e)
      alert('Failed to stop scraping. Please try again.')
      // Refresh to get accurate status even on error
      await loadConnections(false)
    }
  }

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    try {
      const date = new Date(dateString)
      return date.toLocaleString()
    } catch (e) {
      return dateString
    }
  }

  const getStatusColor = (status: ConnectionStatus) => {
    switch (status) {
      case 'Running':
        return 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
      case 'Completed':
        return 'bg-green-500/20 text-green-400 border border-green-500/30'
      case 'Failed':
        return 'bg-red-500/20 text-red-400 border border-red-500/30 font-semibold'
      case 'Stopped':
        return 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
      default:
        return 'bg-gray-500/20 text-gray-400 border border-gray-500/30'
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push('/admin/reference-data')}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
            Screener Connections
          </h1>
          <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
            Manage Screener data source connections and control scraping
          </p>
        </div>
      </div>
      
      <div className="flex items-center justify-between">
        <div></div>
        <div className="flex gap-2 items-center">
          <RefreshButton
            variant="secondary"
            onClick={loadConnections}
            size="sm"
            disabled={loading}
          />
          <Button size="sm" onClick={() => setIsAddOpen(true)}>
            Add Connection
          </Button>
        </div>
      </div>

      {/* Connections Table */}
      <Card compact>
        <Table>
          <TableHeader>
            <TableHeaderCell>Connection Name</TableHeaderCell>
            <TableHeaderCell>Connection Type</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell>Last Run</TableHeaderCell>
            <TableHeaderCell className="text-right" numeric>Records Loaded</TableHeaderCell>
            <TableHeaderCell className="text-right" numeric>Actions</TableHeaderCell>
          </TableHeader>
          <TableBody>
            {loading && connections.length === 0 ? (
              <TableRow>
                <td colSpan={6} className="px-3 py-12 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    <p className="text-text-secondary">Loading connections...</p>
                  </div>
                </td>
              </TableRow>
            ) : (
              <>
                {connections.map((conn, index) => {
                  const isRunning = runningJobs.has(conn.id) || conn.status === 'Running'
                  const displayStatus = conn.status || 'Idle'
                  
                  // Disable Start button ONLY when Running (user can retry after Failed/Stopped/Completed)
                  const startDisabled = isRunning
                  
                  return (
                    <TableRow key={conn.id} index={index}>
                      <TableCell className="font-sans font-semibold text-xs">
                        {conn.connection_name}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                        {conn.connection_type === 'WEBSITE_SCRAPING' ? 'Website Scraping' : 'API Connection'}
                      </TableCell>
                      <TableCell>
                        <span className={`text-[10px] font-sans px-2 py-1 rounded-md uppercase font-medium ${getStatusColor(displayStatus as ConnectionStatus)}`}>
                          {displayStatus}
                        </span>
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs whitespace-nowrap">
                        {formatDate(conn.last_run)}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs whitespace-nowrap text-right" numeric>
                        {conn.records_loaded?.toLocaleString() || 0}
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap" numeric>
                        <div className="flex gap-1 justify-end">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleStart(conn.id)}
                            disabled={startDisabled}
                            className={startDisabled ? 'opacity-50 cursor-not-allowed' : ''}
                            title={isRunning ? 'Scraping is already running' : 'Start scraping'}
                          >
                            <Play className={`w-4 h-4 ${startDisabled ? 'text-gray-500' : 'text-primary'}`} />
                            Start
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleStop(conn.id)}
                            disabled={!isRunning}
                            className={!isRunning ? 'opacity-50 cursor-not-allowed' : ''}
                            title={!isRunning ? 'No active scraping to stop' : 'Stop scraping'}
                          >
                            <Square className={`w-4 h-4 ${!isRunning ? 'text-gray-500' : 'text-warning'}`} />
                            Stop
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
                {connections.length === 0 && !loading && (
                  <TableRow>
                    <td colSpan={6} className="px-3 py-12 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <p className="text-text-secondary">No connections found</p>
                        <p className="text-xs text-text-secondary">
                          Click "Add Connection" to create one
                        </p>
                      </div>
                    </td>
                  </TableRow>
                )}
              </>
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Add Connection Modal */}
      <AddConnectionModal
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        onSuccess={loadConnections}
      />
    </div>
  )
}

