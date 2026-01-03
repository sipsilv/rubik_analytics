'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { symbolsAPI } from '@/lib/api'
import { ReferenceDataBackNav } from '@/components/ReferenceDataBackNav'
import { Play, Edit, Trash2, Power, PowerOff, RefreshCw, Clock, CheckCircle, XCircle, AlertCircle, TestTube, X, Search } from 'lucide-react'
import { getErrorMessage } from '@/lib/error-utils'
import { useAuthStore } from '@/lib/store'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { Tooltip } from '@/components/ui/Tooltip'

interface Scheduler {
  id: number
  name: string
  description?: string
  mode: string
  interval_value?: number
  interval_unit?: string
  cron_expression?: string
  is_active: boolean
  status?: string | null  // Current active status (queued/running if active, null if no active run)
  last_run_at?: string | null  // ISO format timestamp of last execution start
  last_run_status?: string | null  // Status of most recent execution (completed/failed/crashed/etc)
  next_run_at?: string | null
  duration?: string | null
  inserted_count?: number
  updated_count?: number
  failed_count?: number
  active_run_id?: number | null  // ID of the active run log (for cancellation)
  sources: Array<{
    id: number
    name: string
    source_type: string
    url: string
    is_enabled: boolean
    last_run_at?: string
    last_status?: string
    last_error?: string
    last_record_count?: number
  }>
}

export default function ActivityPage() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin' || user?.role === 'super_admin'
  const [schedulers, setSchedulers] = useState<Scheduler[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [editingScheduler, setEditingScheduler] = useState<Scheduler | null>(null)
  const [editName, setEditName] = useState('')
  const [editDescription, setEditDescription] = useState('')
  const [editIsActive, setEditIsActive] = useState(false)
  const [editNextRunAt, setEditNextRunAt] = useState('')
  const [testingScheduler, setTestingScheduler] = useState<number | null>(null)
  const [runningScheduler, setRunningScheduler] = useState<number | null>(null)

  useEffect(() => {
    loadSchedulers()
  }, [])
  
  // NO auto-refresh - user must manually click Refresh button

  const loadSchedulers = async () => {
    try {
      setError(null)
      const data = await symbolsAPI.getSchedulers()
      console.log('[Activity] Loaded schedulers:', data)
      // Log each scheduler to verify API response structure and status
      if (data && data.length > 0) {
        data.forEach((scheduler: Scheduler) => {
          console.log(`[Activity] Scheduler "${scheduler.name}":`, {
            id: scheduler.id,
            status: scheduler.status,  // Should be null if no active run
            last_run_at: scheduler.last_run_at,  // Should show actual last run time
            last_run_status: scheduler.last_run_status,
            hasActiveRun: scheduler.status === 'running' || scheduler.status === 'queued'
          })
        })
      }
      setSchedulers(data)
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to load schedulers'))
    } finally {
      setLoading(false)
    }
  }

  const handleTestScheduler = async (schedulerId: number) => {
    try {
      setError(null)
      setTestingScheduler(schedulerId)
      
      const result = await symbolsAPI.testScheduler(schedulerId)
      
      // Format test results
      const nextRunTime = result.calculated_next_run_at 
        ? new Date(result.calculated_next_run_at).toLocaleString()
        : 'Not scheduled'
      
      const timeUntilRun = result.time_until_next_run || 'N/A'
      
      let message = `Scheduler Test Results:\n\n`
      message += `Status: ${result.test_status}\n`
      message += `Next Run: ${nextRunTime}\n`
      message += `Time Until Run: ${timeUntilRun}\n`
      message += `Mode: ${result.mode}\n`
      message += `Is Active: ${result.is_active ? 'Yes' : 'No'}\n`
      
      if (result.validation_errors && result.validation_errors.length > 0) {
        message += `\nErrors:\n${result.validation_errors.join('\n')}\n`
      }
      
      if (result.validation_warnings && result.validation_warnings.length > 0) {
        message += `\nWarnings:\n${result.validation_warnings.join('\n')}\n`
      }
      
      alert(message)
      
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to test scheduler'))
    } finally {
      setTestingScheduler(null)
    }
  }

  const handleRunNow = async (schedulerId: number) => {
    console.log("RUN CLICKED", schedulerId)
    
    // Prevent multiple simultaneous requests for the same scheduler
    if (runningScheduler === schedulerId) {
      console.log('Scheduler is already being triggered, ignoring duplicate click')
      return
    }
    
    const scheduler = schedulers.find(s => s.id === schedulerId)
    if (!scheduler) {
      console.log("Scheduler not found:", schedulerId)
      return
    }

    // SINGLE SOURCE OF TRUTH: Check if scheduler is actually running (from API status field only)
    if (scheduler.status === 'running' || scheduler.status === 'queued') {
      console.log('Scheduler is already running (status:', scheduler.status, '), ignoring duplicate click')
      setError('A run is already in progress. Please wait for it to complete.')
      return
    }

    // Check if scheduler has enabled sources
    // Prevent duplicate clicks - check IMMEDIATELY
    if (runningScheduler === schedulerId) {
      console.log("[FRONTEND] BLOCKED: Scheduler already running, ignoring duplicate click")
      return
    }

    const enabledSources = scheduler.sources?.filter(s => s.is_enabled) || []
    if (enabledSources.length === 0) {
      setError('Cannot run scheduler: No enabled sources found. Please enable at least one source.')
      console.log("[FRONTEND] No enabled sources for scheduler:", schedulerId)
      return
    }

    // Set running state IMMEDIATELY before any async operations
    setRunningScheduler(schedulerId)
    console.log(`[FRONTEND] Starting Run Now for scheduler: ${schedulerId}`)

    try {
      setError(null)
      
      console.log(`[FRONTEND] Calling API: runSchedulerNow for scheduler ${schedulerId}`)
      const result = await symbolsAPI.runSchedulerNow(schedulerId)
      console.log('[FRONTEND] Run Now result:', result)
      
      // Refresh immediately to show updated status from database
      await loadSchedulers()
      
    } catch (e: any) {
      console.error('[FRONTEND] Run Now error:', e)
      // If error is 409 (conflict), backend confirmed a run is in progress
      if (e?.response?.status === 409) {
        setError(e?.response?.data?.detail || 'A run is already in progress. Please wait for it to complete.')
      } else {
        setError(getErrorMessage(e, 'Failed to run scheduler'))
      }
      // Refresh to get current status from database
      await loadSchedulers()
    } finally {
      // Clear running state after execution completes (increased delay to 10 seconds)
      setTimeout(() => {
        console.log(`[FRONTEND] Clearing running state for scheduler ${schedulerId}`)
        setRunningScheduler(null)
      }, 10000)  // Increased from 2000 to 10000 to prevent rapid re-triggers
    }
  }

  const handleToggleActive = async (schedulerId: number, currentStatus: boolean) => {
    try {
      setError(null)
      await symbolsAPI.updateScheduler(schedulerId, { is_active: !currentStatus })
      await loadSchedulers()
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to update scheduler'))
    }
  }

  const handleDelete = async (schedulerId: number) => {
    const scheduler = schedulers.find(s => s.id === schedulerId)
    if (!scheduler) return

    if (!window.confirm(`Are you sure you want to delete scheduler "${scheduler.name}"? This will cancel all future runs.`)) {
      return
    }

    try {
      setError(null)
      await symbolsAPI.deleteScheduler(schedulerId)
      await loadSchedulers()
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to delete scheduler'))
    }
  }

  const handleEdit = (scheduler: Scheduler) => {
    setEditingScheduler(scheduler)
    setEditName(scheduler.name)
    setEditDescription(scheduler.description || '')
    setEditIsActive(scheduler.is_active)
    // Format next_run_at for datetime-local input (YYYY-MM-DDTHH:mm)
    if (scheduler.next_run_at) {
      try {
        const date = new Date(scheduler.next_run_at)
        // Convert to local timezone and format for datetime-local input
        const year = date.getFullYear()
        const month = String(date.getMonth() + 1).padStart(2, '0')
        const day = String(date.getDate()).padStart(2, '0')
        const hours = String(date.getHours()).padStart(2, '0')
        const minutes = String(date.getMinutes()).padStart(2, '0')
        setEditNextRunAt(`${year}-${month}-${day}T${hours}:${minutes}`)
      } catch (e) {
        console.error('Error parsing next_run_at:', e)
        setEditNextRunAt('')
      }
    } else {
      setEditNextRunAt('')
    }
  }

  const handleSaveEdit = async () => {
    if (!editingScheduler) return

    if (!editName.trim()) {
      setError('Scheduler name is required')
      return
    }

    try {
      setError(null)
      
      // Convert datetime-local format to ISO string
      let nextRunAtISO: string | undefined = undefined
      if (editNextRunAt) {
        try {
          // datetime-local gives us local time, convert to ISO string
          const localDate = new Date(editNextRunAt)
          // Convert to UTC ISO string
          nextRunAtISO = localDate.toISOString()
        } catch (e) {
          console.error('Error converting next_run_at:', e)
          setError('Invalid date/time format')
          return
        }
      }
      
      await symbolsAPI.updateScheduler(editingScheduler.id, {
        name: editName,
        description: editDescription,
        is_active: editIsActive,
        next_run_at: nextRunAtISO
      })
      setEditingScheduler(null)
      await loadSchedulers()
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to update scheduler'))
    }
  }

  const handleCancelEdit = () => {
    setEditingScheduler(null)
    setEditName('')
    setEditDescription('')
    setEditIsActive(false)
    setEditNextRunAt('')
    setError(null)
  }

  const handleCancelRun = async (scheduler: Scheduler) => {
    if (!scheduler.active_run_id) {
      setError('No active run to cancel')
      return
    }

    if (!window.confirm(`Are you sure you want to cancel the running job for scheduler "${scheduler.name}"?`)) {
      return
    }

    try {
      setError(null)
      await symbolsAPI.cancelUpload(String(scheduler.active_run_id))
      // Refresh to get updated status
      await loadSchedulers()
    } catch (e: any) {
      setError(getErrorMessage(e, 'Failed to cancel run'))
      // Refresh anyway to get current status
      await loadSchedulers()
    }
  }

  const formatFrequency = (scheduler: Scheduler): string => {
    if (scheduler.mode === 'RUN_ONCE') {
      return 'Run Once'
    } else if (scheduler.mode === 'INTERVAL') {
      if (scheduler.interval_value && scheduler.interval_unit) {
        const unit = scheduler.interval_unit === 'seconds' ? 'sec' :
                     scheduler.interval_unit === 'minutes' ? 'min' :
                     scheduler.interval_unit === 'hours' ? 'hr' :
                     scheduler.interval_unit === 'days' ? 'day' :
                     scheduler.interval_unit === 'weeks' ? 'week' : scheduler.interval_unit
        return `Every ${scheduler.interval_value} ${unit}${scheduler.interval_value > 1 ? 's' : ''}`
      }
      return 'Interval'
    } else if (scheduler.mode === 'CRON') {
      return scheduler.cron_expression || 'Cron'
    }
    return 'Unknown'
  }

  const formatNextRun = (nextRunAt: string | null | undefined): string => {
    if (!nextRunAt) return 'Not scheduled'
    try {
      const date = new Date(nextRunAt)
      const now = new Date()
      const diffMs = date.getTime() - now.getTime()
      const diffMins = Math.floor(diffMs / 60000)
      
      if (diffMins < 1) return 'Running now'
      if (diffMins < 60) return `In ${diffMins} min${diffMins > 1 ? 's' : ''}`
      const diffHours = Math.floor(diffMins / 60)
      if (diffHours < 24) return `In ${diffHours} hr${diffHours > 1 ? 's' : ''}`
      const diffDays = Math.floor(diffHours / 24)
      return `In ${diffDays} day${diffDays > 1 ? 's' : ''}`
    } catch {
      return 'Invalid date'
    }
  }

  const getLastRunStatus = (scheduler: Scheduler): { status: string; icon: any; color: string } => {
    // SINGLE SOURCE OF TRUTH: Use last_run_status field from API (from database)
    const status = scheduler.last_run_status
    
    if (!status) {
      return { status: 'Never run', icon: Clock, color: 'text-text-secondary' }
    }

    // Normalize status values for display
    const statusLower = status.toLowerCase()
    if (statusLower === 'completed' || statusLower === 'success') {
      return { status: 'Completed', icon: CheckCircle, color: 'text-success' }
    } else if (statusLower === 'failed') {
      return { status: 'Failed', icon: XCircle, color: 'text-danger' }
    } else if (statusLower === 'cancelled') {
      return { status: 'Cancelled', icon: AlertCircle, color: 'text-warning' }
    } else if (statusLower === 'crashed' || statusLower === 'stopped' || statusLower === 'interrupted') {
      // INTERRUPTED is a legacy status that means server restarted - treat as crashed
      return { status: statusLower === 'interrupted' ? 'Interrupted (Server Restarted)' : (statusLower === 'crashed' ? 'Crashed' : 'Stopped'), icon: XCircle, color: 'text-danger' }
    } else if (statusLower === 'running' || statusLower === 'queued') {
      return { status: status === 'running' ? 'Running' : 'Queued', icon: Clock, color: 'text-primary' }
    }

    return { status: status, icon: Clock, color: 'text-text-secondary' }
  }

  const formatLastRun = (lastRunAt: string | null | undefined): string => {
    if (!lastRunAt) return '—'
    try {
      const date = new Date(lastRunAt)
      if (isNaN(date.getTime())) {
        return 'Invalid date'
      }
      // Format as full date and time for clarity
      const dateStr = date.toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: '2-digit', 
        day: '2-digit' 
      })
      const timeStr = date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit',
        second: '2-digit',
        hour12: true
      })
      return `${dateStr} ${timeStr}`
    } catch (e) {
      console.error('[formatLastRun] Error formatting date:', lastRunAt, e)
      return 'Invalid date'
    }
  }

  // Update search input value only (no filtering)
  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  // Execute search only on button click
  const handleSearchClick = () => {
    setSearchQuery(search)
  }

  // Clear search and reset to default (unfiltered) state
  const handleClearSearch = () => {
    setSearch('')
    setSearchQuery('')
  }

  // Handle Enter key in search input
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  const filteredSchedulers = schedulers.filter(scheduler =>
    scheduler.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    scheduler.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    scheduler.mode?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    scheduler.sources?.some(s => s.name?.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  const getSourceDisplay = (scheduler: Scheduler): string => {
    const enabledSources = scheduler.sources?.filter(s => s.is_enabled) || []
    if (enabledSources.length === 0) return 'No sources'
    if (enabledSources.length === 1) {
      return enabledSources[0].source_type === 'API_ENDPOINT' ? 'API' : 'URL'
    }
    return `${enabledSources.length} sources`
  }

  if (loading) {
    return (
      <div className="p-6">
        <ReferenceDataBackNav />
        <Card className="mt-4">
          <div className="p-8 text-center">
            <RefreshCw className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
            <p className="text-text-secondary">Loading schedulers...</p>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="p-6">
      <ReferenceDataBackNav />
      
      <div className="flex justify-between items-center mt-4 mb-4">
        <h1 className="text-2xl font-bold">Activity</h1>
        <RefreshButton onClick={loadSchedulers} variant="secondary" size="sm" />
      </div>

      {error && (
        <div className="mb-4 p-4 bg-danger/10 border border-danger/20 rounded-lg text-danger">
          {error}
        </div>
      )}

      <Card>
        <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div className="flex-1 max-w-md">
              <Input
                placeholder="Search schedulers..."
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                className="h-9"
              />
            </div>
            <Button
              variant="primary"
              onClick={handleSearchClick}
              size="sm"
              disabled={loading}
              className="h-9 px-4 flex-shrink-0"
            >
              <Search className="w-4 h-4 mr-1.5" />
              Search
            </Button>
            {search && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearSearch}
                disabled={loading}
                className="h-9 px-3 flex-shrink-0"
              >
                <X className="w-4 h-4 mr-1.5" />
                Clear
              </Button>
            )}
          </div>
        </div>
        {schedulers.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">
            <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No scheduled jobs found. Create a scheduler to get started.</p>
          </div>
        ) : filteredSchedulers.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">
            <Clock className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No schedulers found matching "{searchQuery}"</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
            <TableHeader>
              <TableRow>
                <TableHeaderCell>Schedule Name</TableHeaderCell>
                <TableHeaderCell>Source Type</TableHeaderCell>
                <TableHeaderCell>Frequency</TableHeaderCell>
                <TableHeaderCell>Status</TableHeaderCell>
                <TableHeaderCell>Last Run</TableHeaderCell>
                <TableHeaderCell>Last Run Status</TableHeaderCell>
                <TableHeaderCell>Next Run</TableHeaderCell>
                <TableHeaderCell>Enabled</TableHeaderCell>
                <TableHeaderCell>Actions</TableHeaderCell>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredSchedulers.map((scheduler) => {
                const lastRunStatus = getLastRunStatus(scheduler)
                const StatusIcon = lastRunStatus.icon
                // SINGLE SOURCE OF TRUTH: Check if scheduler is actually running (from API status field only)
                // NO fake state - status comes directly from database via API
                const isRunning = scheduler.status === 'running' || scheduler.status === 'queued'

                return (
                  <TableRow key={scheduler.id}>
                    <TableCell>
                      <div>
                        <div className="font-medium">{scheduler.name}</div>
                        {scheduler.description && (
                          <div className="text-sm text-text-secondary">{scheduler.description}</div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-text-primary">
                        {(() => {
                          const enabledSource = scheduler.sources?.find(s => s.is_enabled)
                          if (!enabledSource) return 'N/A'
                          if (enabledSource.source_type === 'API_ENDPOINT') return 'API'
                          if (enabledSource.source_type === 'DOWNLOADABLE_URL') return 'URL'
                          return enabledSource.source_type || 'N/A'
                        })()}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm text-text-primary">{formatFrequency(scheduler)}</span>
                    </TableCell>
                    {/* Status Column - Current Active Status (from database only) */}
                    <TableCell className="min-w-[100px]">
                      {scheduler.status ? (
                        <div className="flex items-center gap-2">
                          <StatusIcon className={`w-4 h-4 ${scheduler.status === 'running' ? 'text-primary' : scheduler.status === 'queued' ? 'text-info' : 'text-text-secondary'}`} />
                          <span className={`text-sm font-medium ${scheduler.status === 'running' ? 'text-primary' : scheduler.status === 'queued' ? 'text-info' : 'text-text-secondary'}`}>
                            {scheduler.status === 'running' ? 'Running' : scheduler.status === 'queued' ? 'Queued' : scheduler.status}
                          </span>
                        </div>
                      ) : (
                        <span className="text-sm text-text-secondary">Idle</span>
                      )}
                    </TableCell>
                    {/* Last Run Column - Date and Time of Last Execution */}
                    <TableCell className="min-w-[220px]">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-text-secondary flex-shrink-0" />
                        <span className="text-sm text-text-primary font-medium whitespace-nowrap">
                          {scheduler.last_run_at ? formatLastRun(scheduler.last_run_at) : '—'}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <StatusIcon className={`w-4 h-4 ${lastRunStatus.color}`} />
                        <span className={`text-sm ${lastRunStatus.color}`}>{lastRunStatus.status}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-text-secondary" />
                        <span className="text-sm text-text-secondary">{formatNextRun(scheduler.next_run_at)}</span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Tooltip text={scheduler.is_active ? "Disable scheduler" : "Enable scheduler"}>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleToggleActive(scheduler.id, scheduler.is_active)}
                          className={scheduler.is_active ? 'text-success' : 'text-text-secondary'}
                        >
                          {scheduler.is_active ? (
                            <Power className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                          ) : (
                            <PowerOff className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                          )}
                        </Button>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {isRunning ? (
                          <Tooltip text="Cancel Running Job">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                handleCancelRun(scheduler)
                              }}
                              className="text-danger hover:text-danger p-1.5"
                            >
                              <X className="w-4 h-4 btn-icon-hover icon-button icon-button-shake" />
                            </Button>
                          </Tooltip>
                        ) : (
                          <Tooltip text="Run Now">
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={runningScheduler === scheduler.id || scheduler.status === 'running' || scheduler.status === 'queued'}
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                handleRunNow(scheduler.id).catch(err => {
                                  console.error("handleRunNow threw error:", err)
                                  // If error is 409 (conflict), backend confirmed a run is in progress
                                  if (err?.response?.status === 409) {
                                    setError(err?.response?.data?.detail || 'A run is already in progress.')
                                  }
                                })
                              }}
                              disabled={isRunning || runningScheduler === scheduler.id}
                              className="text-primary hover:text-primary p-1.5"
                            >
                              <Play className="w-4 h-4 btn-icon-hover icon-button icon-button-pulse" />
                            </Button>
                          </Tooltip>
                        )}
                        {isAdmin && (
                          <Tooltip text="Test Scheduler - Verify next run time (Admin Only)">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                handleTestScheduler(scheduler.id)
                              }}
                              disabled={testingScheduler === scheduler.id}
                              className="text-warning hover:text-warning p-1.5"
                            >
                              <TestTube className={`w-4 h-4 btn-icon-hover icon-button icon-button-bounce ${testingScheduler === scheduler.id ? 'animate-spin' : ''}`} />
                            </Button>
                          </Tooltip>
                        )}
                        <Tooltip text="Edit scheduler">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleEdit(scheduler)}
                            className="text-info hover:text-info p-1.5"
                          >
                            <Edit className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                          </Button>
                        </Tooltip>
                        <Tooltip text="Delete scheduler">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDelete(scheduler.id)}
                            className="text-danger hover:text-danger p-1.5"
                          >
                            <Trash2 className="w-4 h-4 btn-icon-hover icon-button icon-button-shake" />
                          </Button>
                        </Tooltip>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
            </Table>
          </div>
        )}
      </Card>

      {/* Edit Modal */}
      {editingScheduler && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold text-text-primary">Edit Scheduler</h2>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm text-text-secondary mb-1 block">Scheduler Name *</label>
                <Input
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  placeholder="Enter scheduler name"
                  className="w-full"
                />
              </div>

              <div>
                <label className="text-sm text-text-secondary mb-1 block">Description</label>
                <Input
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Optional description"
                  className="w-full"
                />
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="edit-active"
                  checked={editIsActive}
                  onChange={(e) => setEditIsActive(e.target.checked)}
                  className="w-4 h-4 text-primary bg-[#0a1020] border-[#1f2a44] rounded focus:ring-primary"
                />
                <label htmlFor="edit-active" className="text-sm text-text-primary cursor-pointer">
                  Enable scheduler
                </label>
              </div>

              <div>
                <label className="text-sm text-text-secondary mb-1 block">Next Run Time (Optional)</label>
                <input
                  type="datetime-local"
                  value={editNextRunAt}
                  onChange={(e) => setEditNextRunAt(e.target.value)}
                  className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                  placeholder="Select date and time"
                />
                <p className="text-xs text-text-secondary mt-1">
                  Leave empty to use calculated schedule time. Set a specific time to override.
                </p>
              </div>

              {error && (
                <div className="p-2 bg-danger/10 border border-danger/20 rounded text-danger text-sm">
                  {error}
                </div>
              )}

              <div className="flex gap-2 justify-end pt-4">
                <Button variant="ghost" onClick={handleCancelEdit}>
                  Cancel
                </Button>
                <Button onClick={handleSaveEdit}>
                  Save Changes
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

