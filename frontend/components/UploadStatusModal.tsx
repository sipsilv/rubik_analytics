'use client'

import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X, Clock, CheckCircle2, XCircle, AlertCircle, ChevronDown, ChevronUp, ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { symbolsAPI } from '@/lib/api'

// Handle ESC key to close modal
const useEscapeKey = (callback: () => void) => {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        callback()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [callback])
}

// Valid status values from backend
const VALID_STATUSES = [
  'QUEUED',
  'RUNNING',
  'PENDING',
  'SUCCESS',
  'COMPLETED',
  'PARTIAL',
  'COMPLETED_WITH_WARNINGS',
  'FAILED',
  'CANCELLED',
  'INTERRUPTED',
  'CRASHED',
  'STOPPED'
] as const

type ValidStatus = typeof VALID_STATUSES[number]

interface UploadLog {
  job_id: string
  file_name: string
  upload_type: string
  triggered_by: string
  started_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  total_rows: number
  inserted_rows: number
  updated_rows: number
  failed_rows: number
  status: string
  progress_percentage: number
  error_summary: string[]
}

interface UploadStatusModalProps {
  isOpen: boolean
  onClose: () => void
  refreshTrigger?: number // Trigger refresh when this value changes
}

// Status utility functions - defined outside component for reusability
const normalizeStatus = (status: string | null | undefined): string => {
  if (!status || typeof status !== 'string') return ''
  const normalized = status.trim().toUpperCase()
  return normalized
}

const isValidStatus = (status: string): status is ValidStatus => {
  return VALID_STATUSES.includes(normalizeStatus(status) as ValidStatus)
}

const isRunningStatus = (status: string | null | undefined): boolean => {
  const normalized = normalizeStatus(status)
  return ['QUEUED', 'RUNNING', 'PENDING'].includes(normalized)
}

const isCancelledStatus = (status: string | null | undefined): boolean => {
  return normalizeStatus(status) === 'CANCELLED'
}

const isTerminalStatus = (status: string | null | undefined): boolean => {
  const normalized = normalizeStatus(status)
  return [
    'CANCELLED',
    'FAILED',
    'CRASHED',
    'INTERRUPTED',
    'STOPPED',
    'SUCCESS',
    'COMPLETED',
    'PARTIAL',
    'COMPLETED_WITH_WARNINGS'
  ].includes(normalized)
}

// Validate and sanitize log data
const validateAndSanitizeLog = (log: any): UploadLog | null => {
  try {
    if (!log || typeof log !== 'object') return null
    
    // Validate required fields
    if (!log.job_id || typeof log.job_id !== 'string') return null
    if (!log.file_name || typeof log.file_name !== 'string') return null
    
    // Sanitize and validate status - CRITICAL: Preserve CANCELLED status
    const rawStatus = log.status || ''
    const normalizedStatus = normalizeStatus(rawStatus)
    
    // CRITICAL: CANCELLED must be preserved - check it first
    let validStatus: string
    if (normalizedStatus === 'CANCELLED') {
      validStatus = 'CANCELLED' // Always preserve CANCELLED
    } else if (isValidStatus(normalizedStatus)) {
      validStatus = normalizedStatus
    } else {
      // For unknown statuses, log warning but preserve the normalized value
      console.warn('[UploadStatusModal] Unknown status detected:', {
        raw: rawStatus,
        normalized: normalizedStatus,
        job_id: log.job_id
      })
      validStatus = normalizedStatus || 'UNKNOWN'
    }
    
    // Validate and sanitize numeric fields
    const totalRows = typeof log.total_rows === 'number' && log.total_rows >= 0 ? log.total_rows : 0
    const insertedRows = typeof log.inserted_rows === 'number' && log.inserted_rows >= 0 ? log.inserted_rows : 0
    const updatedRows = typeof log.updated_rows === 'number' && log.updated_rows >= 0 ? log.updated_rows : 0
    const failedRows = typeof log.failed_rows === 'number' && log.failed_rows >= 0 ? log.failed_rows : 0
    const progressPercentage = typeof log.progress_percentage === 'number' 
      ? Math.max(0, Math.min(100, log.progress_percentage)) 
      : 0
    
    // Validate and sanitize error_summary
    let errorSummary: string[] = []
    if (Array.isArray(log.error_summary)) {
      errorSummary = log.error_summary
        .filter((e: any) => typeof e === 'string')
        .map((e: string) => e.trim())
        .filter((e: string) => e.length > 0)
    }
    
    return {
      job_id: String(log.job_id).trim(),
      file_name: String(log.file_name).trim(),
      upload_type: typeof log.upload_type === 'string' ? log.upload_type.trim() : 'UNKNOWN',
      triggered_by: typeof log.triggered_by === 'string' ? log.triggered_by.trim() : 'UNKNOWN',
      started_at: log.started_at && typeof log.started_at === 'string' ? log.started_at : null,
      ended_at: log.ended_at && typeof log.ended_at === 'string' ? log.ended_at : null,
      duration_seconds: typeof log.duration_seconds === 'number' && log.duration_seconds >= 0 
        ? log.duration_seconds 
        : null,
      total_rows: totalRows,
      inserted_rows: insertedRows,
      updated_rows: updatedRows,
      failed_rows: failedRows,
      status: validStatus,
      progress_percentage: progressPercentage,
      error_summary: errorSummary
    }
  } catch (error) {
    console.error('[UploadStatusModal] Error validating log:', error, log)
    return null
  }
}

export function UploadStatusModal({ isOpen, onClose, refreshTrigger }: UploadStatusModalProps) {
  const [logs, setLogs] = useState<UploadLog[]>([])
  const [loading, setLoading] = useState(false)
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set())
  const [mounted, setMounted] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(8)
  const [totalPages, setTotalPages] = useState(1)
  const [total, setTotal] = useState(0)
  const [showConfirmDialog, setShowConfirmDialog] = useState(false)
  const [confirmMessage, setConfirmMessage] = useState('')
  const [confirmCallback, setConfirmCallback] = useState<(() => void) | null>(null)
  const [showErrorDialog, setShowErrorDialog] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')
  const [isVisible, setIsVisible] = useState(false)
  const [lastError, setLastError] = useState<string | null>(null)

  // Ensure we're mounted (client-side only for portal)
  useEffect(() => {
    setMounted(true)
    return () => setMounted(false)
  }, [])

  // Animation state - sync with modal open/close
  useEffect(() => {
    if (isOpen) {
      setIsVisible(false)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsVisible(true)
        })
      })
    } else {
      setIsVisible(false)
    }
  }, [isOpen])

  // Close on ESC key
  useEscapeKey(() => {
    if (isOpen) {
      onClose()
    }
  })

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  // Load logs with comprehensive error handling and data validation
  const loadLogs = useCallback(async (silent: boolean = false) => {
    if (!isOpen) return

    try {
      if (!silent) {
        setLoading(true)
        setLastError(null)
      }
      
      console.log('[UploadStatusModal] Fetching upload logs - page:', page, 'pageSize:', pageSize)
      
      // Validate inputs
      const validPage = typeof page === 'number' && page > 0 ? page : 1
      const validPageSize = typeof pageSize === 'number' && pageSize > 0 ? pageSize : 8
      
      const response = await symbolsAPI.getUploadLogs(validPageSize, validPage)
      
      // Validate response structure
      if (!response || typeof response !== 'object') {
        throw new Error('Invalid response format from API')
      }
      
      // Validate and sanitize logs array
      const rawLogs = Array.isArray(response.logs) ? response.logs : []
      
      // Debug: Log raw statuses before validation
      console.log('[UploadStatusModal] Raw statuses from API:', rawLogs.map((log: any) => ({
        job_id: log?.job_id,
        status: log?.status,
        status_type: typeof log?.status
      })))
      
      const validatedLogs = rawLogs
        .map(validateAndSanitizeLog)
        .filter((log): log is UploadLog => log !== null)
      
      // Debug: Log validated statuses
      console.log('[UploadStatusModal] Validated statuses:', validatedLogs.map(log => ({
        job_id: log.job_id,
        status: log.status
      })))
      
      console.log('[UploadStatusModal] Loaded logs:', {
        total: response.total || 0,
        logs_count: validatedLogs.length,
        raw_logs_count: rawLogs.length,
        page: response.page || validPage,
        total_pages: response.total_pages || 1,
        validated: validatedLogs.length === rawLogs.length,
        cancelled_count: validatedLogs.filter(log => normalizeStatus(log.status) === 'CANCELLED').length
      })
      
      // Set validated logs
      setLogs(validatedLogs)
      
      // Validate and set pagination
      const validTotal = typeof response.total === 'number' && response.total >= 0 ? response.total : 0
      
      // Calculate totalPages - use backend value if available, otherwise calculate from total
      // If we got a full page of results, there might be more pages
      const hasMorePages = validatedLogs.length === validPageSize
      let validTotalPages = 1
      
      if (typeof response.total_pages === 'number' && response.total_pages > 0) {
        validTotalPages = response.total_pages
      } else if (validTotal > 0) {
        validTotalPages = Math.ceil(validTotal / validPageSize)
      } else if (hasMorePages) {
        // If we got a full page but no total, assume there might be more pages
        // Set to current page + 1 to enable Next button
        validTotalPages = Math.max(page + 1, 2)
      }
      
      setTotal(validTotal)
      setTotalPages(validTotalPages)
      
      console.log('[UploadStatusModal] Pagination calculated:', {
        validTotal,
        validTotalPages,
        hasMorePages,
        currentPage: page,
        logsOnPage: validatedLogs.length,
        pageSize: validPageSize
      })
      
      // Log status breakdown for debugging
      if (validatedLogs.length > 0) {
        const statusBreakdown = {
          running: validatedLogs.filter(log => isRunningStatus(log.status)).length,
          completed: validatedLogs.filter(log => normalizeStatus(log.status) === 'SUCCESS').length,
          cancelled: validatedLogs.filter(log => isCancelledStatus(log.status)).length,
          failed: validatedLogs.filter(log => normalizeStatus(log.status) === 'FAILED').length,
          crashed: validatedLogs.filter(log => normalizeStatus(log.status) === 'CRASHED').length,
          interrupted: validatedLogs.filter(log => normalizeStatus(log.status) === 'INTERRUPTED').length
        }
        console.log('[UploadStatusModal] Status breakdown:', statusBreakdown)
      }
    } catch (error: any) {
      const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to load upload logs'
      console.error('[UploadStatusModal] Failed to load upload logs:', {
        message: errorMsg,
        response: error?.response?.data,
        status: error?.response?.status,
        code: error?.code,
        url: error?.config?.url
      })
      
      setLastError(errorMsg)
      
      // On error, keep previous logs if available, otherwise set empty
      setLogs(prevLogs => {
        if (prevLogs.length === 0) {
          setTotal(0)
          setTotalPages(1)
          return []
        }
        return prevLogs
      })
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }, [isOpen, page, pageSize])

  // Reset to page 1 when modal opens
  useEffect(() => {
    if (isOpen) {
      setPage(1)
      setLastError(null)
    }
  }, [isOpen])
  
  // Track last refresh trigger to refresh when modal opens
  const lastRefreshTriggerRef = useRef<number>(0)

  // Load logs when modal opens or page changes
  useEffect(() => {
    if (!isOpen) return
    
    console.log('[UploadStatusModal] Modal opened or page changed, loading logs:', { page, isOpen, lastRefreshTrigger: lastRefreshTriggerRef.current, currentRefreshTrigger: refreshTrigger })
    
    // If there was a refresh trigger while modal was closed, refresh now
    const shouldRefresh = refreshTrigger !== undefined && refreshTrigger > lastRefreshTriggerRef.current
    if (shouldRefresh) {
      console.log('[UploadStatusModal] Refresh trigger detected on modal open, refreshing logs...')
      lastRefreshTriggerRef.current = refreshTrigger || 0
    }
    
    const isInitialLoad = page === 1
    loadLogs(!isInitialLoad && !shouldRefresh) // Silent if refreshing due to trigger
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, page])

  // Auto-refresh logs when refreshTrigger changes (e.g., after upload completes)
  // Refresh immediately if modal is open, or mark for refresh when modal opens
  useEffect(() => {
    if (refreshTrigger !== undefined && refreshTrigger > 0) {
      console.log('[UploadStatusModal] Refresh trigger detected, refreshing logs...', { isOpen, refreshTrigger, lastRefreshTrigger: lastRefreshTriggerRef.current })
      
      if (isOpen) {
        // If modal is open, refresh immediately
        console.log('[UploadStatusModal] Modal is open, refreshing logs immediately...')
        lastRefreshTriggerRef.current = refreshTrigger
        loadLogs(true) // Silent refresh (no loading indicator)
      } else {
        // If modal is closed, mark the trigger so logs refresh when modal opens
        console.log('[UploadStatusModal] Modal is closed, will refresh when modal opens...')
        lastRefreshTriggerRef.current = refreshTrigger
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshTrigger, isOpen])

  // Dialog handlers
  const showConfirm = (message: string, callback: () => void) => {
    if (typeof message !== 'string' || !message.trim()) {
      console.error('[UploadStatusModal] Invalid confirm message')
      return
    }
    setConfirmMessage(message.trim())
    setConfirmCallback(() => callback)
    setShowConfirmDialog(true)
  }

  const handleConfirm = () => {
    if (confirmCallback) {
      try {
        confirmCallback()
      } catch (error: any) {
        console.error('[UploadStatusModal] Error in confirm callback:', error)
        showError(`An error occurred: ${error?.message || 'Unknown error'}`)
      }
    }
    setShowConfirmDialog(false)
    setConfirmCallback(null)
  }

  const handleCancelConfirm = () => {
    setShowConfirmDialog(false)
    setConfirmCallback(null)
  }

  const showError = (message: string) => {
    if (typeof message !== 'string' || !message.trim()) {
      message = 'An unknown error occurred'
    }
    setErrorMessage(message.trim())
    setShowErrorDialog(true)
  }

  // Cancel upload with comprehensive error handling
  const handleCancelUpload = async (jobId: string) => {
    // Validate jobId
    if (!jobId || typeof jobId !== 'string' || !jobId.trim()) {
      showError('Invalid job ID')
      return
    }

    showConfirm('Are you sure you want to cancel this upload? Processing will stop immediately.', async () => {
      try {
        // Optimistically update UI
        setLogs(prevLogs => prevLogs.map(log => 
          log.job_id === jobId.trim()
            ? { ...log, status: 'CANCELLED', ended_at: new Date().toISOString() }
            : log
        ))
        
        // Call API
        await symbolsAPI.cancelUpload(jobId.trim())
        
        // Reload logs to get accurate status
        await loadLogs(false)
      } catch (error: any) {
        // Reload to get actual status
        await loadLogs(false)
        const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to cancel upload'
        showError(errorMsg)
      }
    })
  }

  // Cancel all running jobs
  const handleCancelAllRunning = async () => {
    const runningJobs = logs.filter(log => 
      isRunningStatus(log.status) && !isCancelledStatus(log.status)
    )

    if (runningJobs.length === 0) {
      showError('No running jobs to cancel.')
      return
    }

    showConfirm(`Are you sure you want to cancel ${runningJobs.length} running job(s)? Processing will stop immediately for all of them.`, async () => {
      try {
        setLoading(true)
        
        // Optimistically update UI
        const jobIds = runningJobs.map(job => job.job_id).filter(Boolean)
        setLogs(prevLogs => prevLogs.map(log => 
          jobIds.includes(log.job_id)
            ? { ...log, status: 'CANCELLED', ended_at: new Date().toISOString() }
            : log
        ))
        
        // Cancel all in parallel
        await Promise.all(
          jobIds.map(jobId => symbolsAPI.cancelUpload(jobId).catch(err => {
            console.error(`[UploadStatusModal] Failed to cancel job ${jobId}:`, err)
            return { error: true, jobId, error: err }
          }))
        )
        
        // Reload logs
        await loadLogs(false)
      } catch (error: any) {
        await loadLogs(false)
        const errorMsg = error?.response?.data?.detail || error?.message || 'Failed to cancel some uploads'
        showError(errorMsg)
      } finally {
        setLoading(false)
      }
    })
  }

  const toggleErrorExpansion = (jobId: string) => {
    if (!jobId || typeof jobId !== 'string') return
    setExpandedErrors(prev => {
      const newSet = new Set(prev)
      if (newSet.has(jobId)) {
        newSet.delete(jobId)
      } else {
        newSet.add(jobId)
      }
      return newSet
    })
  }

  const formatDuration = (seconds: number | null, isRunning: boolean = false): string => {
    if (seconds === null && !isRunning) return '-'
    if (seconds === null && isRunning) return '0s'
    const secs = typeof seconds === 'number' && seconds >= 0 ? seconds : 0
    const hours = Math.floor(secs / 3600)
    const minutes = Math.floor((secs % 3600) / 60)
    const remainingSeconds = secs % 60

    if (hours > 0) {
      return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
    } else {
      return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
    }
  }

  const formatTimestamp = (timestamp: string | null): string => {
    if (!timestamp || typeof timestamp !== 'string') return '-'
    try {
      const date = new Date(timestamp)
      if (isNaN(date.getTime())) return timestamp
      
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      const seconds = String(date.getSeconds()).padStart(2, '0')
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
    } catch {
      return timestamp
    }
  }

  // Get status icon - CANCELLED takes absolute priority
  const getStatusIcon = (status: string | null | undefined) => {
    if (!status) {
      return <Clock className="w-4 h-4 text-gray-500" />
    }
    
    const normalized = normalizeStatus(status)
    
    // CRITICAL: CANCELLED must be checked FIRST
    // Also check original string for "cancel" to catch any variations
    if (normalized === 'CANCELLED' || (typeof status === 'string' && status.toLowerCase().includes('cancel'))) {
      return <AlertCircle className="w-4 h-4 text-warning" />
    }
    if (normalized === 'FAILED' || normalized === 'CRASHED') {
      return <XCircle className="w-4 h-4 text-red-500" />
    }
    if (normalized === 'INTERRUPTED' || normalized === 'STOPPED') {
      return <AlertCircle className="w-4 h-4 text-orange-500" />
    }
    if (normalized === 'SUCCESS') {
      return <CheckCircle2 className="w-4 h-4 text-green-500" />
    }
    if (normalized === 'PARTIAL' || normalized === 'COMPLETED_WITH_WARNINGS') {
      return <AlertCircle className="w-4 h-4 text-yellow-500" />
    }
    if (normalized === 'RUNNING') {
      return <div className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    }
    if (normalized === 'PENDING') {
      return <Clock className="w-4 h-4 text-blue-500" />
    }
    if (normalized === 'QUEUED') {
      return <Clock className="w-4 h-4 text-gray-500" />
    }
    
    return <Clock className="w-4 h-4 text-gray-500" />
  }

  // Get status badge - CANCELLED takes absolute priority
  const getStatusBadge = (status: string | null | undefined) => {
    if (!status) {
      return <span className="text-xs uppercase font-bold px-2 py-0.5 rounded bg-gray-500/10 text-gray-500">Unknown</span>
    }
    
    const normalized = normalizeStatus(status)
    const baseClasses = "text-xs uppercase font-bold px-2 py-0.5 rounded"
    
    // CRITICAL: CANCELLED must be checked FIRST - absolute priority
    // Check both normalized and original string for "cancel" to catch any variations
    if (normalized === 'CANCELLED' || (typeof status === 'string' && status.toLowerCase().includes('cancel'))) {
      // Force to CANCELLED if it contains "cancel" in any form
      if (normalized !== 'CANCELLED') {
        console.warn('[UploadStatusModal] Status contains "cancel" but normalized incorrectly:', {
          original: status,
          normalized: normalized,
          forcing_to: 'CANCELLED'
        })
      }
      return <span className={`${baseClasses} bg-warning/10 text-warning`}>Cancelled</span>
    }
    
    // Terminal error states
    if (normalized === 'FAILED') {
      return <span className={`${baseClasses} bg-red-500/10 text-red-500`}>Failed</span>
    }
    if (normalized === 'CRASHED') {
      return <span className={`${baseClasses} bg-red-500/10 text-red-500`}>Crashed</span>
    }
    if (normalized === 'INTERRUPTED') {
      return <span className={`${baseClasses} bg-orange-500/10 text-orange-500`}>Interrupted</span>
    }
    if (normalized === 'STOPPED') {
      return <span className={`${baseClasses} bg-orange-500/10 text-orange-500`}>Stopped</span>
    }
    
    // Success states
    if (normalized === 'SUCCESS') {
      return <span className={`${baseClasses} bg-green-500/10 text-green-500`}>Completed</span>
    }
    if (normalized === 'PARTIAL' || normalized === 'COMPLETED_WITH_WARNINGS') {
      return <span className={`${baseClasses} bg-yellow-500/10 text-yellow-500`}>Completed (with warnings)</span>
    }
    
    // Running states
    if (normalized === 'RUNNING') {
      return <span className={`${baseClasses} bg-blue-500/10 text-blue-500`}>Running</span>
    }
    if (normalized === 'PENDING') {
      return <span className={`${baseClasses} bg-blue-500/10 text-blue-500`}>Processing</span>
    }
    if (normalized === 'QUEUED') {
      return <span className={`${baseClasses} bg-gray-500/10 text-gray-500`}>Queued</span>
    }
    
    // Fallback
    return <span className={`${baseClasses} bg-gray-500/10 text-gray-500`}>{status || 'Unknown'}</span>
  }

  // Memoize running jobs check
  const hasRunningJobs = useMemo(() => {
    return logs.some(log => isRunningStatus(log.status) && !isCancelledStatus(log.status))
  }, [logs])

  // Get page numbers for pagination (matching symbols page style)
  const getPageNumbers = useMemo(() => {
    const pages: (number | string)[] = []
    const maxVisible = 5
    const actualTotalPages = Math.max(1, totalPages)

    if (actualTotalPages <= maxVisible) {
      // Show all pages if total is small
      for (let i = 1; i <= actualTotalPages; i++) {
        pages.push(i)
      }
    } else {
      // Always show first page
      pages.push(1)

      if (page <= 3) {
        // Near the start
        for (let i = 2; i <= 4; i++) {
          pages.push(i)
        }
        pages.push('ellipsis')
        pages.push(actualTotalPages)
      } else if (page >= actualTotalPages - 2) {
        // Near the end
        pages.push('ellipsis')
        for (let i = actualTotalPages - 3; i <= actualTotalPages; i++) {
          pages.push(i)
        }
      } else {
        // In the middle
        pages.push('ellipsis')
        for (let i = page - 1; i <= page + 1; i++) {
          pages.push(i)
        }
        pages.push('ellipsis')
        pages.push(actualTotalPages)
      }
    }

    return pages
  }, [page, totalPages])

  if (!isOpen || !mounted) return null

  const modalContent = (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center"
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        width: '100vw',
        height: '100vh',
        minWidth: '100vw',
        minHeight: '100vh',
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        MozBackdropFilter: 'blur(12px)',
        opacity: isVisible ? undefined : 0,
        animation: isVisible ? 'backdropFadeIn 0.3s ease-out' : 'none',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        className="bg-background border border-border rounded-lg shadow-2xl w-full max-w-7xl max-h-[90vh] flex flex-col mx-4 relative z-[10000]"
        style={{
          backgroundColor: '#0a1020',
          minHeight: '400px',
          color: '#ffffff',
          opacity: isVisible ? undefined : 0,
          transform: isVisible ? undefined : 'scale(0.95)',
          animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button 
          onClick={onClose} 
          className="absolute top-0 -right-14 z-[10000] w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors flex items-center justify-center"
          title="Close"
        >
          <X className="w-5 h-5" />
        </button>
        
        <div className="flex items-center justify-between p-4 border-b border-border" style={{ backgroundColor: '#0a1020' }}>
          <div>
            <h2 className="text-xl font-semibold" style={{ color: '#ffffff' }}>Upload Status</h2>
            <p className="text-sm" style={{ color: '#9ca3af' }}>File-level upload tracking</p>
          </div>
          <div className="flex items-center gap-2">
            {hasRunningJobs && (
              <Button
                variant="danger"
                size="sm"
                onClick={handleCancelAllRunning}
                disabled={loading}
                title="Cancel all running jobs"
              >
                <XCircle className="w-4 h-4 mr-1.5" />
                Cancel All Running
              </Button>
            )}
            <RefreshButton
              variant="secondary"
              size="sm"
              onClick={() => loadLogs(false)}
              disabled={loading}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4" style={{ minHeight: '300px', backgroundColor: '#0a1020', color: '#ffffff' }}>
          {lastError && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-sm text-red-400">
              Error: {lastError}
            </div>
          )}
          
          {loading && logs.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : logs.length === 0 ? (
            <div className="text-center py-12 text-text-secondary">
              <div className="space-y-2">
                <p className="text-lg font-medium">No Upload History</p>
                <p className="text-sm">No upload logs found. Upload a file to see status information here.</p>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" style={{ color: '#ffffff' }}>
                <thead>
                  <tr className="border-b" style={{ borderColor: '#1f2a44' }}>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Job ID</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>File Name</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Type</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Triggered By</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Started</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Ended</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Duration</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Progress</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Rows</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Status</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Errors</th>
                    <th className="text-left p-2 font-semibold" style={{ color: '#9ca3af' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log, index) => {
                    // CRITICAL: Get raw status and normalize - CANCELLED check must be first
                    const rawStatus = String(log.status || '').trim()
                    const normalizedStatus = normalizeStatus(rawStatus)
                    
                    // CRITICAL: CANCELLED takes absolute priority - check directly
                    const isCancelled = normalizedStatus === 'CANCELLED'
                    const isRunning = !isCancelled && isRunningStatus(rawStatus)
                    const errorsExpanded = expandedErrors.has(log.job_id)
                    const hasErrors = Array.isArray(log.error_summary) && log.error_summary.length > 0
                    const sequentialNumber = (page - 1) * pageSize + index + 1
                    
                    // Debug: Log status for debugging cancelled items
                    if (rawStatus.toLowerCase().includes('cancel') || normalizedStatus === 'CANCELLED') {
                      console.log('[UploadStatusModal] Status check for job:', {
                        job_id: log.job_id,
                        raw_status: rawStatus,
                        normalized_status: normalizedStatus,
                        isCancelled,
                        log_status: log.status
                      })
                    }

                    return (
                      <tr key={log.job_id} className="border-b" style={{ borderColor: '#1f2a44', color: '#ffffff' }}>
                        <td className="p-2 font-mono text-xs font-medium">{sequentialNumber}</td>
                        <td className="p-2 max-w-[200px] truncate" title={log.file_name}>{log.file_name}</td>
                        <td className="p-2 text-xs uppercase" style={{ color: '#9ca3af' }}>{log.upload_type}</td>
                        <td className="p-2 text-xs" style={{ color: '#9ca3af' }}>{log.triggered_by}</td>
                        <td className="p-2 text-xs whitespace-nowrap" style={{ color: '#9ca3af' }}>
                          {formatTimestamp(log.started_at)}
                        </td>
                        <td className="p-2 text-xs whitespace-nowrap" style={{ color: '#9ca3af' }}>
                          {isRunning ? (
                            <span className="text-blue-500">In Progress</span>
                          ) : isCancelled ? (
                            <span className="text-warning">Cancelled</span>
                          ) : (
                            formatTimestamp(log.ended_at)
                          )}
                        </td>
                        <td className="p-2 text-xs font-mono" style={{ color: '#9ca3af' }}>
                          {formatDuration(log.duration_seconds, isRunning)}
                        </td>
                        <td className="p-2">
                          <div className="flex items-center gap-2 min-w-[100px]">
                            <div className="flex-1 bg-gray-700 rounded-full h-2">
                              <div
                                className={`h-2 rounded-full transition-all ${
                                  isCancelled ? 'bg-warning' : 'bg-blue-500'
                                }`}
                                style={{ width: `${Math.min(100, Math.max(0, log.progress_percentage))}%` }}
                              />
                            </div>
                            <span className="text-xs w-12 text-right" style={{ color: '#9ca3af' }}>
                              {log.progress_percentage.toFixed(1)}%
                            </span>
                          </div>
                        </td>
                        <td className="p-2 text-xs" style={{ color: '#9ca3af' }}>
                          <div className="flex flex-col">
                            <span>Total: {log.total_rows}</span>
                            <span className="text-green-600 dark:text-green-400">
                              +{log.inserted_rows} / ↑{log.updated_rows}
                            </span>
                            {log.failed_rows > 0 && (
                              <span className="text-red-600 dark:text-red-400">
                                ✗{log.failed_rows}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="p-2">
                          <div className="flex items-center gap-1">
                            {/* CRITICAL: Use raw status from log, not derived value */}
                            {getStatusIcon(rawStatus)}
                            {getStatusBadge(rawStatus)}
                          </div>
                        </td>
                        <td className="p-2">
                          {hasErrors ? (
                            <button
                              onClick={() => toggleErrorExpansion(log.job_id)}
                              className="flex items-center gap-1 text-xs text-red-500 hover:text-red-600"
                            >
                              {errorsExpanded ? (
                                <ChevronUp className="w-3 h-3" />
                              ) : (
                                <ChevronDown className="w-3 h-3" />
                              )}
                              {log.error_summary.length} error{log.error_summary.length !== 1 ? 's' : ''}
                            </button>
                          ) : (
                            <span className="text-xs text-text-secondary">-</span>
                          )}
                          {errorsExpanded && hasErrors && (
                            <div className="mt-2 p-2 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded text-xs">
                              <ul className="list-disc list-inside space-y-1">
                                {log.error_summary.map((error, idx) => (
                                  <li key={idx} className="text-red-700 dark:text-red-300">
                                    {error}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                        </td>
                        <td className="p-2">
                          {isRunning && (
                            <Button
                              variant="danger"
                              size="sm"
                              onClick={() => handleCancelUpload(log.job_id)}
                              className="text-xs"
                            >
                              <XCircle className="w-4 h-4 mr-1.5" />
                              Cancel
                            </Button>
                          )}
                          {isCancelled && (
                            <span className="text-xs text-warning">Cancelled</span>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}

          {logs.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border flex items-center" style={{ minHeight: '3rem', paddingTop: '1rem' }}>
              {/* Left spacer - flex-1 to push content apart */}
              <div className="flex-1"></div>
              
              {/* Center: Pagination controls */}
              <div className="flex items-center gap-1">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1 || loading}
                  className="px-2"
                >
                  <ChevronLeft className="w-4 h-4" />
                  Previous
                </Button>
                <div className="flex items-center gap-1 flex-wrap">
                  {getPageNumbers.map((pageNum, idx) => {
                    if (pageNum === 'ellipsis') {
                      return (
                        <span key={`ellipsis-${idx}`} className="px-2 text-text-secondary">
                          ...
                        </span>
                      )
                    }
                    const pageNumValue = pageNum as number
                    return (
                      <Button
                        key={pageNumValue}
                        variant={pageNumValue === page ? 'primary' : 'ghost'}
                        size="sm"
                        onClick={() => setPage(pageNumValue)}
                        disabled={loading}
                        className="min-w-[2rem] px-2"
                      >
                        {pageNumValue}
                      </Button>
                    )
                  })}
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage(p => Math.min(p + 1, totalPages))}
                  disabled={loading || page >= totalPages}
                  className="px-2"
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
              
              {/* Right: Record count */}
              <div className="flex-1 flex justify-end">
                <div className="text-sm" style={{ color: '#9ca3af' }}>
                  Showing {((page - 1) * pageSize) + 1}–{Math.min(page * pageSize, total || logs.length)} of {total || logs.length} uploads
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {showConfirmDialog && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-text-primary mb-4">Confirm</h3>
            <p className="text-text-secondary mb-6 whitespace-pre-wrap">{confirmMessage}</p>
            <div className="flex justify-end gap-2">
              <Button variant="secondary" onClick={handleCancelConfirm}>Cancel</Button>
              <Button variant="danger" onClick={handleConfirm}>Confirm</Button>
            </div>
          </div>
        </div>
      )}

      {showErrorDialog && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/70 backdrop-blur-sm">
          <div className="bg-[#121b2f] border border-red-500/50 rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
            <h3 className="text-lg font-semibold text-danger mb-4">Error</h3>
            <p className="text-text-secondary mb-6 whitespace-pre-wrap">{errorMessage}</p>
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => setShowErrorDialog(false)}>OK</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )

  return createPortal(modalContent, document.body)
}
