'use client'

import { useState, useEffect, useRef } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { symbolsAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Switch } from '@/components/ui/Switch'
import { Play, Edit, Trash2, X, RefreshCw } from 'lucide-react'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { SecondaryModal } from '@/components/ui/Modal'

interface UploadSymbolModalProps {
    isOpen: boolean
    onClose: () => void
    onSuccess: () => void
}

export function UploadSymbolModal({ isOpen, onClose, onSuccess }: UploadSymbolModalProps) {
    const [activeTab, setActiveTab] = useState<'manual' | 'auto'>('manual')

    // Scripts
    const [scripts, setScripts] = useState<any[]>([])
    const [selectedScriptId, setSelectedScriptId] = useState<string>('')
    const [enableTransformation, setEnableTransformation] = useState(false)
    const [scriptName, setScriptName] = useState('')
    const [scriptDescription, setScriptDescription] = useState('')
    const [scriptContent, setScriptContent] = useState(`# Python Transformation Script
# FULLY FLEXIBLE - Write ANY Python code you need!
# 
# INPUT/OUTPUT CONTRACT (ONLY RESTRICTION):
# - Input: Variable 'df' (pandas DataFrame) is provided by system
# - Output: Variable 'final_df' (pandas DataFrame) must be assigned
#
# YOU CAN:
# - Write any functions, loops, conditionals
# - Use any variable names
# - Include helper methods
# - Perform any transformations
# - Rename/drop/create columns
# - Apply business logic
#
# SECURITY RESTRICTIONS (sandbox-level):
# - os, sys, subprocess, socket, requests, filesystem, network are blocked

import pandas as pd
import numpy as np
from datetime import datetime

# Example: Flexible transformation with helper function
def normalize_symbols(df):
    """Helper function to normalize symbol data"""
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].str.upper().str.strip()
    if "exchange" in df.columns:
        df["exchange"] = df["exchange"].str.upper()
    return df

# Apply transformations
df = normalize_symbols(df)

# Add metadata if needed
df["processed_at"] = datetime.now()

# REQUIRED: Assign final result to final_df
final_df = df`)
    const [editingScriptId, setEditingScriptId] = useState<number | null>(null)
    const [scriptError, setScriptError] = useState('')
    const [isVisible, setIsVisible] = useState(false)

    // Animation state - sync with modal open/close
    useEffect(() => {
        if (isOpen) {
            // Reset visibility state first, then trigger animation after mount
            setIsVisible(false)
            // Use requestAnimationFrame for smoother animation start
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    setIsVisible(true)
                })
            })
        } else {
            setIsVisible(false)
        }
    }, [isOpen])
    const [savingScript, setSavingScript] = useState(false)
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
    const [scriptToDelete, setScriptToDelete] = useState<number | null>(null)
    const [showErrorPopup, setShowErrorPopup] = useState(false)
    const [errorPopupMessage, setErrorPopupMessage] = useState('')
    const [showBackgroundUploadPopup, setShowBackgroundUploadPopup] = useState(false)
    const [showTestConnectionModal, setShowTestConnectionModal] = useState(false)
    const [testConnectionResult, setTestConnectionResult] = useState<{ success: boolean; message: string } | null>(null)
    const [showDeleteSchedulerConfirm, setShowDeleteSchedulerConfirm] = useState(false)
    const [schedulerToDelete, setSchedulerToDelete] = useState<{ id: number; name: string } | null>(null)

    // Manual State
    const [file, setFile] = useState<File | null>(null)
    const [preview, setPreview] = useState<any>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [step, setStep] = useState<'upload' | 'preview' | 'success'>('upload')
    const [resultMsg, setResultMsg] = useState('')
    // Use ref to store file for re-upload (refs don't cause re-renders and preserve File objects)
    const fileRef = useRef<File | null>(null)
    const scriptIdRef = useRef<number | undefined>(undefined)
    // Refs to track polling state for cleanup
    const pollingTimeoutRef = useRef<NodeJS.Timeout | null>(null)
    const isPollingCompletedRef = useRef<boolean>(false)
    const hasRefreshedRef = useRef<boolean>(false) // Track if symbols table has been refreshed

    // Auto Upload State (mirrors Manual Upload structure)
    const [autoStep, setAutoStep] = useState<'upload' | 'preview' | 'success'>('upload')
    const [autoPreview, setAutoPreview] = useState<any>(null)
    const [autoLoading, setAutoLoading] = useState(false)
    const [autoError, setAutoError] = useState('')
    const [autoResultMsg, setAutoResultMsg] = useState('')

    // Data Source Configuration
    const [dataSourceType, setDataSourceType] = useState<'FILE_URL' | 'API_ENDPOINT' | 'CLOUD_STORAGE'>('FILE_URL')
    const [sourceUrl, setSourceUrl] = useState('')
    const [sourceHeaders, setSourceHeaders] = useState<Record<string, string>>({})
    const [sourceAuthToken, setSourceAuthToken] = useState('')
    const [fileHandlingMode, setFileHandlingMode] = useState<'DOWNLOAD' | 'LIVE_API'>('DOWNLOAD')
    const [fileType, setFileType] = useState<'AUTO' | 'CSV' | 'XLSX' | 'JSON' | 'PARQUET'>('AUTO')

    // Scheduler Configuration (integrated, not separate)
    const [scheduleMode, setScheduleMode] = useState<'RUN_ONCE' | 'INTERVAL' | 'DATETIME' | 'CRON'>('RUN_ONCE')
    const [intervalPreset, setIntervalPreset] = useState<'5min' | '15min' | '30min' | '1hr' | 'custom'>('1hr')
    const [intervalCustomValue, setIntervalCustomValue] = useState(1)
    const [intervalCustomUnit, setIntervalCustomUnit] = useState<'minutes' | 'hours' | 'days'>('hours')
    const [scheduleDateTime, setScheduleDateTime] = useState('')
    const [scheduleTimezone, setScheduleTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone)
    const [cronExpression, setCronExpression] = useState('')

    // Multi-source support
    const [autoSources, setAutoSources] = useState<any[]>([])
    const [editingAutoSource, setEditingAutoSource] = useState<any>(null)
    const [showAutoSourceForm, setShowAutoSourceForm] = useState(false)

    // Existing Schedulers (for management)
    const [schedulers, setSchedulers] = useState<any[]>([])
    const [selectedScheduler, setSelectedScheduler] = useState<any>(null)
    // Old scheduler state (for backward compatibility with existing scheduler management functions)
    const [schedulerName, setSchedulerName] = useState('')
    const [schedulerDescription, setSchedulerDescription] = useState('')
    const [schedulerMode, setSchedulerMode] = useState<'RUN_ONCE' | 'INTERVAL' | 'CRON'>('INTERVAL')
    const [intervalValue, setIntervalValue] = useState(6)
    const [intervalUnit, setIntervalUnit] = useState<'seconds' | 'minutes' | 'hours' | 'days'>('hours')
    const [timeFormat, setTimeFormat] = useState<'12h' | '24h'>('24h')
    const [timezone, setTimezone] = useState<string>(Intl.DateTimeFormat().resolvedOptions().timeZone)
    const [startTime, setStartTime] = useState<string>('')
    const [schedulerSources, setSchedulerSources] = useState<any[]>([])
    const [editingSource, setEditingSource] = useState<any>(null)
    const [showSourceForm, setShowSourceForm] = useState(false)
    // API-specific state
    const [apiMethod, setApiMethod] = useState<'GET' | 'POST'>('GET')
    const [apiAuthType, setApiAuthType] = useState<'NONE' | 'API_KEY' | 'BEARER_TOKEN'>('NONE')
    const [apiKey, setApiKey] = useState('')
    const [apiKeyValue, setApiKeyValue] = useState('')
    const [bearerToken, setBearerToken] = useState('')
    const [queryParams, setQueryParams] = useState<Array<{ key: string, value: string }>>([])

    const [backendHealthy, setBackendHealthy] = useState(true)
    const [isProcessing, setIsProcessing] = useState(false)
    const [processStatus, setProcessStatus] = useState<{ processed: number, total: number, errors: number, inserted?: number, updated?: number, percentage?: number, status?: string } | null>(null)

    // Cleanup polling when modal closes
    useEffect(() => {
        return () => {
            // Cleanup polling when component unmounts or modal closes
            if (pollingTimeoutRef.current) {
                clearTimeout(pollingTimeoutRef.current)
                pollingTimeoutRef.current = null
            }
            isPollingCompletedRef.current = true
        }
    }, [])

    // Debug test connection modal state
    useEffect(() => {
        if (showTestConnectionModal) {
            console.log('[TEST CONNECTION MODAL] Modal should be visible:', {
                showTestConnectionModal,
                testConnectionResult,
                hasResult: !!testConnectionResult
            })
        }
    }, [showTestConnectionModal, testConnectionResult])

    useEffect(() => {
        if (isOpen) {
            // Reset state when modal opens
            setStep('upload')
            setAutoStep('upload')
            setPreview(null)
            setAutoPreview(null)
            setError('')
            setAutoError('')
            // Reset polling state
            isPollingCompletedRef.current = false
            hasRefreshedRef.current = false // Reset refresh flag when modal opens
            if (pollingTimeoutRef.current) {
                clearTimeout(pollingTimeoutRef.current)
                pollingTimeoutRef.current = null
            }
        } else {
            // Stop polling when modal closes
            isPollingCompletedRef.current = true
            if (pollingTimeoutRef.current) {
                clearTimeout(pollingTimeoutRef.current)
                pollingTimeoutRef.current = null
            }
            // Reset refresh flag when modal closes (for next upload)
            hasRefreshedRef.current = false
            setResultMsg('')
            setAutoResultMsg('')
            setIsProcessing(false)
            setProcessStatus(null)
            // Check backend health first
            checkBackendHealth()
            loadScripts()
            loadSchedulers()
        }
    }, [isOpen])

    // NO auto-refresh - user must manually click Refresh button

    const checkBackendHealth = async () => {
        try {
            const health = await symbolsAPI.checkHealth()
            // Only mark as unhealthy if backend is truly unreachable (no HTTP response)
            // If health check returns false but we got an HTTP response, backend IS reachable
            setBackendHealthy(health.healthy)
            if (!health.healthy) {
                // Only show error if it's a network/unreachable error
                if (health.error?.includes('not reachable')) {
                    const apiUrl = process.env.NEXT_PUBLIC_API_URL
                    setError(`Backend server is not reachable. Please ensure the backend is running at ${apiUrl}.`)
                } else {
                    // Backend is reachable but health check failed for other reasons
                    // Don't show error - backend is still functional
                    setBackendHealthy(true)
                }
            } else {
                // Clear error if health check passes
                if (error && error.includes('Backend server is not reachable')) {
                    setError('')
                }
            }
        } catch (e: any) {
            // Only mark as unhealthy if there's NO HTTP response
            const isUnreachable = !e.response && (
                e.code === 'ECONNREFUSED' ||
                e.code === 'ERR_NETWORK' ||
                e.code === 'ENOTFOUND' ||
                e.message?.includes('Network Error') ||
                e.message?.includes('Failed to fetch')
            )

            setBackendHealthy(!isUnreachable)

            if (isUnreachable) {
                const apiUrl = process.env.NEXT_PUBLIC_API_URL
                setError(`Unable to connect to backend server at ${apiUrl}. Please ensure the backend is running.`)
            }
            console.error('Backend health check failed:', e)
        }
    }

    const loadScripts = async () => {
        try {
            const data = await symbolsAPI.getScripts()
            setScripts(data)
        } catch (e) { console.error(e) }
    }

    const loadSchedulers = async () => {
        try {
            console.log('[UploadSymbolModal] Loading schedulers...')
            const data = await symbolsAPI.getSchedulers()
            console.log('[UploadSymbolModal] Schedulers loaded:', {
                count: Array.isArray(data) ? data.length : 0,
                data: data,
                isArray: Array.isArray(data)
            })
            setSchedulers(Array.isArray(data) ? data : [])
        } catch (e: any) {
            console.error('[UploadSymbolModal] Failed to load schedulers:', {
                error: e,
                message: e?.message,
                response: e?.response?.data,
                status: e?.response?.status,
                url: e?.config?.url
            })
            setSchedulers([])
        }
    }

    const handleCreateScheduler = async () => {
        if (!schedulerName.trim()) {
            setAutoError('Scheduler name is required')
            return
        }
        if (schedulerMode === 'INTERVAL' && (!intervalValue || !intervalUnit)) {
            setAutoError('Interval value and unit are required')
            return
        }
        if (schedulerMode === 'CRON' && !cronExpression.trim()) {
            setAutoError('Cron expression is required')
            return
        }
        if (schedulerSources.length === 0 || !schedulerSources[0]?.url) {
            setAutoError('Source URL is required')
            return
        }

        try {
            // Build headers from API configuration
            let headers: any = {}
            if (schedulerSources[0]?.source_type === 'API_ENDPOINT') {
                // Add authentication header
                if (apiAuthType === 'API_KEY' && apiKey && apiKeyValue) {
                    headers[apiKey] = apiKeyValue
                } else if (apiAuthType === 'BEARER_TOKEN' && bearerToken) {
                    headers['Authorization'] = `Bearer ${bearerToken}`
                }
            }

            // Build source with proper headers
            const sourceData = {
                ...schedulerSources[0],
                headers: Object.keys(headers).length > 0 ? headers : undefined
            }

            const payload = {
                name: schedulerName,
                description: schedulerDescription,
                mode: schedulerMode,
                interval_value: schedulerMode === 'INTERVAL' ? intervalValue : null,
                interval_unit: schedulerMode === 'INTERVAL' ? intervalUnit : null,
                cron_expression: schedulerMode === 'CRON' ? cronExpression : null,
                script_id: selectedScriptId ? parseInt(selectedScriptId) : null,
                is_active: true,
                sources: [sourceData]
            }
            await symbolsAPI.createScheduler(payload)
            await loadSchedulers()
            setAutoError('')
            setSchedulerName('')
            setSchedulerDescription('')
            setSchedulerSources([])
            setSelectedScheduler(null)
            setApiMethod('GET')
            setApiAuthType('NONE')
            setApiKey('')
            setApiKeyValue('')
            setBearerToken('')
            setQueryParams([])
        } catch (e: any) {
            setAutoError(getErrorMessage(e, 'Failed to create scheduler'))
        }
    }

    const handleAddSource = () => {
        setEditingSource(null)
        setShowSourceForm(true)
    }

    const handleSaveSource = (sourceData: any) => {
        if (editingSource) {
            setSchedulerSources(schedulerSources.map(s => s.id === editingSource.id ? { ...sourceData, id: editingSource.id } : s))
        } else {
            setSchedulerSources([...schedulerSources, { ...sourceData, id: Date.now() }])
        }
        setShowSourceForm(false)
        setEditingSource(null)
    }

    const handleDeleteSource = (sourceId: any) => {
        setSchedulerSources(schedulerSources.filter(s => s.id !== sourceId))
    }

    const handleTriggerScheduler = async (schedulerId: number) => {
        try {
            await symbolsAPI.runSchedulerNow(schedulerId)
            setError('') // Clear any previous errors
            await loadSchedulers() // Refresh to show updated last_run_at
            // Show success feedback
            const scheduler = schedulers.find(s => s.id === schedulerId)
            if (scheduler) {
                setResultMsg(`Scheduler "${scheduler.name}" is running now. Check Status panel for progress.`)
            }
        } catch (e: any) {
            if (e.response?.status === 409) {
                setError('A run is already in progress. Please wait for it to complete.')
            } else {
                setError(getErrorMessage(e, 'Failed to run scheduler'))
            }
        }
    }

    const handleDeleteScheduler = async (schedulerId: number) => {
        const scheduler = schedulers.find(s => s.id === schedulerId)
        if (!scheduler) return

        // Show confirmation modal
        setSchedulerToDelete({ id: schedulerId, name: scheduler.name })
        setShowDeleteSchedulerConfirm(true)
    }

    const confirmDeleteScheduler = async () => {
        if (!schedulerToDelete) return

        try {
            await symbolsAPI.deleteScheduler(schedulerToDelete.id)
            setError('') // Clear any previous errors
            await loadSchedulers()
            if (selectedScheduler?.id === schedulerToDelete.id) {
                setSelectedScheduler(null)
                setSchedulerName('')
                setSchedulerDescription('')
                setSchedulerSources([])
            }
            setShowDeleteSchedulerConfirm(false)
            setSchedulerToDelete(null)
        } catch (e: any) {
            setError(getErrorMessage(e, 'Failed to delete scheduler'))
            setShowDeleteSchedulerConfirm(false)
            setSchedulerToDelete(null)
        }
    }

    const handleToggleScheduler = async (schedulerId: number) => {
        const scheduler = schedulers.find(s => s.id === schedulerId)
        if (!scheduler) return

        try {
            await symbolsAPI.updateScheduler(schedulerId, {
                is_active: !scheduler.is_active
            })
            setError('') // Clear any previous errors
            await loadSchedulers()
        } catch (e: any) {
            setError(getErrorMessage(e, 'Failed to toggle scheduler'))
        }
    }

    const handleEditScheduler = (scheduler: any) => {
        // Switch to auto tab if not already there
        setActiveTab('auto')
        
        setSelectedScheduler(scheduler)
        setSchedulerName(scheduler.name)
        setSchedulerDescription(scheduler.description || '')
        setSchedulerMode(scheduler.mode)
        setIntervalValue(scheduler.interval_value || 1)
        setIntervalUnit(scheduler.interval_unit || 'hours')
        setCronExpression(scheduler.cron_expression || '')
        // Note: timezone and start_time are not stored in backend yet, using defaults
        setTimeFormat('24h')
        setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone)
        setStartTime('')

        // Load script if scheduler has one
        if (scheduler.script_id) {
            setSelectedScriptId(scheduler.script_id.toString())
            setEnableTransformation(true)
            // Load script content
            const script = scripts.find(s => s.id === scheduler.script_id)
            if (script) {
                setScriptName(script.name)
                setScriptDescription(script.description || '')
                setScriptContent(script.content)
                setEditingScriptId(script.id)
            }
        } else {
            setSelectedScriptId('')
            setEnableTransformation(false)
        }

        // Convert sources to the format expected by the form
        const sources = (scheduler.sources || []).map((s: any) => ({
            id: s.id,
            name: s.name,
            source_type: s.source_type,
            url: s.url,
            headers: typeof s.headers === 'string' ? JSON.parse(s.headers) : (s.headers || {}),
            auth_type: s.auth_type,
            auth_value: s.auth_value,
            is_enabled: s.is_enabled !== false
        }))
        setSchedulerSources(sources)

        // Populate API configuration if source is API
        if (sources[0]?.source_type === 'API_ENDPOINT' && sources[0]?.headers) {
            const headers = sources[0].headers
            // Check for Bearer token
            if (headers['Authorization'] && headers['Authorization'].startsWith('Bearer ')) {
                setApiAuthType('BEARER_TOKEN')
                setBearerToken(headers['Authorization'].replace('Bearer ', ''))
            } else {
                // Check for API key (first non-Authorization header)
                const apiKeyHeader = Object.keys(headers).find(k => k !== 'Authorization')
                if (apiKeyHeader) {
                    setApiAuthType('API_KEY')
                    setApiKey(apiKeyHeader)
                    setApiKeyValue(headers[apiKeyHeader])
                } else {
                    setApiAuthType('NONE')
                }
            }
        } else {
            setApiAuthType('NONE')
            setApiKey('')
            setApiKeyValue('')
            setBearerToken('')
        }
        setQueryParams([]) // Query params not stored in backend yet
        setAutoError('') // Clear any errors
        
        // Scroll to the scheduler configuration form after a brief delay to allow state updates
        setTimeout(() => {
            const formElement = document.querySelector('[data-scheduler-form]')
            if (formElement) {
                formElement.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }
        }, 100)
    }

    const handleCancelEdit = () => {
        setSelectedScheduler(null)
        setSchedulerName('')
        setSchedulerDescription('')
        setSchedulerMode('INTERVAL')
        setIntervalValue(1)
        setIntervalUnit('hours')
        setCronExpression('')
        setSchedulerSources([])
        setSelectedScriptId('')
        setEnableTransformation(false)
        setTimeFormat('24h')
        setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone)
        setStartTime('')
        setScriptName('')
        setScriptDescription('')
        setScriptContent(`# Python Transformation Script
# FULLY FLEXIBLE - Write ANY Python code you need!
# 
# INPUT/OUTPUT CONTRACT (ONLY RESTRICTION):
# - Input: Variable 'df' (pandas DataFrame) is provided by system
# - Output: Variable 'final_df' (pandas DataFrame) must be assigned
#
# YOU CAN:
# - Write any functions, loops, conditionals
# - Use any variable names
# - Include helper methods
# - Perform any transformations
# - Rename/drop/create columns
# - Apply business logic
#
# SECURITY RESTRICTIONS (sandbox-level):
# - os, sys, subprocess, socket, requests, filesystem, network are blocked

import pandas as pd
import numpy as np
from datetime import datetime

# Example: Flexible transformation with helper function
def normalize_symbols(df):
    """Helper function to normalize symbol data"""
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].str.upper().str.strip()
    if "exchange" in df.columns:
        df["exchange"] = df["exchange"].str.upper()
    return df

# Apply transformations
df = normalize_symbols(df)

# Add metadata if needed
df["processed_at"] = datetime.now()

# REQUIRED: Assign final result to final_df
final_df = df`)
        setEditingScriptId(null)
        setApiMethod('GET')
        setApiAuthType('NONE')
        setApiKey('')
        setApiKeyValue('')
        setBearerToken('')
        setQueryParams([])
        setTimeFormat('24h')
        setTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone)
        setStartTime('')
        setAutoError('')
    }

    const handleUpdateScheduler = async () => {
        if (!selectedScheduler) return
        if (!schedulerName.trim()) {
            setAutoError('Scheduler name is required')
            return
        }
        if (schedulerMode === 'INTERVAL' && (!intervalValue || !intervalUnit)) {
            setAutoError('Interval value and unit are required')
            return
        }
        if (schedulerMode === 'CRON' && !cronExpression.trim()) {
            setAutoError('Cron expression is required')
            return
        }
        if (schedulerSources.length === 0 || !schedulerSources[0]?.url) {
            setAutoError('Source URL is required')
            return
        }

        try {
            // Build headers from API configuration
            let headers: any = {}
            if (schedulerSources[0]?.source_type === 'API_ENDPOINT') {
                // Add authentication header
                if (apiAuthType === 'API_KEY' && apiKey && apiKeyValue) {
                    headers[apiKey] = apiKeyValue
                } else if (apiAuthType === 'BEARER_TOKEN' && bearerToken) {
                    headers['Authorization'] = `Bearer ${bearerToken}`
                }
            }

            // Build source with proper headers
            const sourceData = {
                ...schedulerSources[0],
                headers: Object.keys(headers).length > 0 ? headers : undefined
            }

            // Calculate next_run_at based on start_time if provided
            let nextRunAt: string | null = null
            if (startTime && startTime.trim()) {
                try {
                    // Parse start time (format: HH:MM)
                    const [hours, minutes] = startTime.split(':').map(Number)
                    if (!isNaN(hours) && !isNaN(minutes)) {
                        // Get current date
                        const now = new Date()
                        const year = now.getFullYear()
                        const month = now.getMonth()
                        const day = now.getDate()
                        
                        // First, get the current date and time in the target timezone
                        const nowInTimezone = new Intl.DateTimeFormat('en-US', {
                            timeZone: timezone,
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit',
                            hour12: false
                        }).formatToParts(now)
                        
                        const currentTZYear = parseInt(nowInTimezone.find(p => p.type === 'year')?.value || '0')
                        const currentTZMonth = parseInt(nowInTimezone.find(p => p.type === 'month')?.value || '0') - 1
                        const currentTZDay = parseInt(nowInTimezone.find(p => p.type === 'day')?.value || '0')
                        const currentTZHour = parseInt(nowInTimezone.find(p => p.type === 'hour')?.value || '0')
                        const currentTZMinute = parseInt(nowInTimezone.find(p => p.type === 'minute')?.value || '0')
                        
                        // Compare: has the entered time passed today in the target timezone?
                        const enteredTimeMinutes = hours * 60 + minutes
                        const currentTimeMinutes = currentTZHour * 60 + currentTZMinute
                        // Only move to next day if entered time is LESS than current time (has definitely passed)
                        // If entered time >= current time, use today
                        const timeHasPassedToday = enteredTimeMinutes < currentTimeMinutes
                        
                        console.log(`[Schedule Update] ===== TIME COMPARISON =====`)
                        console.log(`[Schedule Update] Timezone: ${timezone}`)
                        console.log(`[Schedule Update] Current date in ${timezone}: ${currentTZYear}-${String(currentTZMonth + 1).padStart(2, '0')}-${String(currentTZDay).padStart(2, '0')}`)
                        console.log(`[Schedule Update] Current time in ${timezone}: ${String(currentTZHour).padStart(2, '0')}:${String(currentTZMinute).padStart(2, '0')}`)
                        console.log(`[Schedule Update] Entered time: ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`)
                        console.log(`[Schedule Update] Entered minutes: ${enteredTimeMinutes}, Current minutes: ${currentTimeMinutes}`)
                        console.log(`[Schedule Update] Comparison: ${enteredTimeMinutes} < ${currentTimeMinutes} = ${timeHasPassedToday}`)
                        console.log(`[Schedule Update] Time has passed today: ${timeHasPassedToday}`)
                        
                        // Determine which date to use (today in timezone or next occurrence)
                        let targetYear = currentTZYear
                        let targetMonth = currentTZMonth
                        let targetDay = currentTZDay
                        
                        if (timeHasPassedToday) {
                            console.log(`[Schedule Update] Time has passed, calculating next occurrence`)
                            // Time has passed, calculate next occurrence
                            if (schedulerMode === 'INTERVAL' && intervalUnit && intervalValue) {
                                if (intervalUnit === 'days') {
                                    // Add interval days to today's date in the timezone
                                    const nextDate = new Date(currentTZYear, currentTZMonth, currentTZDay + intervalValue)
                                    targetYear = nextDate.getFullYear()
                                    targetMonth = nextDate.getMonth()
                                    targetDay = nextDate.getDate()
                                } else if (intervalUnit === 'hours') {
                                    // For hours interval with start time, add 1 day to preserve the start time
                                    const nextDate = new Date(currentTZYear, currentTZMonth, currentTZDay + 1)
                                    targetYear = nextDate.getFullYear()
                                    targetMonth = nextDate.getMonth()
                                    targetDay = nextDate.getDate()
                                } else if (intervalUnit === 'minutes') {
                                    // For minutes, add 1 day
                                    const nextDate = new Date(currentTZYear, currentTZMonth, currentTZDay + 1)
                                    targetYear = nextDate.getFullYear()
                                    targetMonth = nextDate.getMonth()
                                    targetDay = nextDate.getDate()
                                } else {
                                    const nextDate = new Date(currentTZYear, currentTZMonth, currentTZDay + 1)
                                    targetYear = nextDate.getFullYear()
                                    targetMonth = nextDate.getMonth()
                                    targetDay = nextDate.getDate()
                                }
                            } else {
                                // Default: add 1 day
                                const nextDate = new Date(currentTZYear, currentTZMonth, currentTZDay + 1)
                                targetYear = nextDate.getFullYear()
                                targetMonth = nextDate.getMonth()
                                targetDay = nextDate.getDate()
                            }
                        } else {
                            console.log(`[Schedule Update] ✅ Time hasn't passed, using TODAY: ${targetYear}-${String(targetMonth + 1).padStart(2, '0')}-${String(targetDay).padStart(2, '0')}`)
                        }
                        
                        console.log(`[Schedule Update] Target date for conversion: ${targetYear}-${String(targetMonth + 1).padStart(2, '0')}-${String(targetDay).padStart(2, '0')} at ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')} ${timezone}`)
                        
                        // Now convert the target date/time in the timezone to UTC
                        let startDate: Date = new Date(Date.UTC(targetYear, targetMonth, targetDay, hours, minutes, 0)) // Default initialization
                        
                        if (timezone === 'UTC') {
                            // For UTC, create date directly in UTC
                            startDate = new Date(Date.UTC(targetYear, targetMonth, targetDay, hours, minutes, 0))
                        } else {
                            // Convert timezone date/time to UTC
                            // Use a direct method: test all possible UTC times to find exact match
                            
                            const formatter = new Intl.DateTimeFormat('en-US', {
                                timeZone: timezone,
                                year: 'numeric',
                                month: '2-digit',
                                day: '2-digit',
                                hour: '2-digit',
                                minute: '2-digit',
                                hour12: false
                            })
                            
                            // We need to find the UTC time that, when formatted in the target timezone, gives us our target date/time
                            // Test all possible UTC times (hours and minutes) to find exact match
                            
                            let found = false
                            
                            // Test UTC times on the target date and adjacent days (to handle timezone boundaries)
                            for (let dayOffset = -2; dayOffset <= 2 && !found; dayOffset++) {
                                const testDate = new Date(targetYear, targetMonth, targetDay + dayOffset)
                                const testYear = testDate.getFullYear()
                                const testMonth = testDate.getMonth()
                                const testDay = testDate.getDate()
                                
                                // Test each UTC hour
                                for (let utcHour = 0; utcHour < 24 && !found; utcHour++) {
                                    // Test each UTC minute (0-59)
                                    for (let utcMin = 0; utcMin < 60 && !found; utcMin++) {
                                        const testUTC = new Date(Date.UTC(testYear, testMonth, testDay, utcHour, utcMin, 0))
                                        const tzParts = formatter.formatToParts(testUTC)
                                        
                                        const tzYear = parseInt(tzParts.find(p => p.type === 'year')?.value || '0')
                                        const tzMonth = parseInt(tzParts.find(p => p.type === 'month')?.value || '0')
                                        const tzDay = parseInt(tzParts.find(p => p.type === 'day')?.value || '0')
                                        const tzHour = parseInt(tzParts.find(p => p.type === 'hour')?.value || '0')
                                        const tzMin = parseInt(tzParts.find(p => p.type === 'minute')?.value || '0')
                                        
                                        // Check if date and time match exactly
                                        if (tzYear === targetYear && 
                                            tzMonth === targetMonth + 1 && 
                                            tzDay === targetDay &&
                                            tzHour === hours && 
                                            tzMin === minutes) {
                                            startDate = testUTC
                                            found = true
                                            console.log(`[Schedule Update] ✅ Found exact UTC match: ${testUTC.toISOString()} for ${targetYear}-${String(targetMonth + 1).padStart(2, '0')}-${String(targetDay).padStart(2, '0')} ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')} ${timezone}`)
                                            break
                                        }
                                    }
                                }
                            }
                            
                            // If still no exact match found, use a more direct calculation method
                            if (!found) {
                                console.warn(`[Schedule Update] ⚠️ No exact match found, using direct calculation`)
                                // Calculate UTC time more directly by using the timezone offset
                                // Create a date at the target time in UTC, then adjust based on timezone offset
                                
                                // Get timezone offset by testing a known UTC time
                                const testUTC = new Date(Date.UTC(targetYear, targetMonth, targetDay, 12, 0, 0))
                                const tzParts = formatter.formatToParts(testUTC)
                                const tzNoonHour = parseInt(tzParts.find(p => p.type === 'hour')?.value || '12')
                                const tzNoonMin = parseInt(tzParts.find(p => p.type === 'minute')?.value || '0')
                                
                                // Calculate offset: UTC 12:00 becomes what time in timezone?
                                const offsetHours = 12 - tzNoonHour
                                const offsetMinutes = 0 - tzNoonMin
                                
                                // Apply offset to get UTC time
                                const utcHour = hours - offsetHours
                                const utcMin = minutes - offsetMinutes
                                
                                // Handle minute overflow/underflow
                                let finalUtcHour = utcHour
                                let finalUtcMin = utcMin
                                let finalDay = targetDay
                                
                                if (finalUtcMin < 0) {
                                    finalUtcMin += 60
                                    finalUtcHour -= 1
                                } else if (finalUtcMin >= 60) {
                                    finalUtcMin -= 60
                                    finalUtcHour += 1
                                }
                                
                                if (finalUtcHour < 0) {
                                    finalUtcHour += 24
                                    finalDay -= 1
                                } else if (finalUtcHour >= 24) {
                                    finalUtcHour -= 24
                                    finalDay += 1
                                }
                                
                                startDate = new Date(Date.UTC(targetYear, targetMonth, finalDay, finalUtcHour, finalUtcMin, 0))
                                console.log(`[Schedule Update] Using direct calculation: ${startDate.toISOString()}`)
                            }
                        }
                        
                        const nowUTC = new Date()
                        const timeDiffMinutes = (startDate.getTime() - nowUTC.getTime()) / (1000 * 60)
                        console.log(`[Schedule Update] ===== UTC CONVERSION RESULT =====`)
                        console.log(`[Schedule Update] Calculated UTC time: ${startDate.toISOString()}`)
                        console.log(`[Schedule Update] Current UTC time: ${nowUTC.toISOString()}`)
                        console.log(`[Schedule Update] Time difference (minutes): ${timeDiffMinutes.toFixed(2)}`)
                        
                        // Verify the date in the target timezone matches what we expect
                        const verifyFormatter = new Intl.DateTimeFormat('en-US', {
                            timeZone: timezone,
                            year: 'numeric',
                            month: '2-digit',
                            day: '2-digit',
                            hour: '2-digit',
                            minute: '2-digit',
                            hour12: false
                        })
                        const verifyDate = verifyFormatter.formatToParts(startDate)
                        const verifyYear = parseInt(verifyDate.find(p => p.type === 'year')?.value || '0')
                        const verifyMonth = parseInt(verifyDate.find(p => p.type === 'month')?.value || '0')
                        const verifyDay = parseInt(verifyDate.find(p => p.type === 'day')?.value || '0')
                        const verifyHour = parseInt(verifyDate.find(p => p.type === 'hour')?.value || '0')
                        const verifyMin = parseInt(verifyDate.find(p => p.type === 'minute')?.value || '0')
                        console.log(`[Schedule Update] Verification in ${timezone}: ${verifyYear}-${String(verifyMonth).padStart(2, '0')}-${String(verifyDay).padStart(2, '0')} ${String(verifyHour).padStart(2, '0')}:${String(verifyMin).padStart(2, '0')}`)
                        console.log(`[Schedule Update] Expected: ${targetYear}-${String(targetMonth + 1).padStart(2, '0')}-${String(targetDay).padStart(2, '0')} ${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`)
                        if (verifyYear !== targetYear || verifyMonth !== targetMonth + 1 || verifyDay !== targetDay || verifyHour !== hours || verifyMin !== minutes) {
                            console.warn(`[Schedule Update] ⚠️ WARNING: Date/time mismatch! This might cause scheduling for the wrong day.`)
                        }
                        
                        // Format as ISO string (UTC)
                        nextRunAt = startDate.toISOString()
                        
                        // Debug logging
                        console.log(`[Schedule Update] Start time: ${hours}:${String(minutes).padStart(2, '0')} ${timezone}`)
                        console.log(`[Schedule Update] Interval: ${intervalValue} ${intervalUnit}`)
                        console.log(`[Schedule Update] Calculated UTC time: ${startDate.toISOString()}`)
                        console.log(`[Schedule Update] Next run at (UTC): ${nextRunAt}`)
                        console.log(`[Schedule Update] Current UTC time: ${nowUTC.toISOString()}`)
                        console.log(`[Schedule Update] Time difference (minutes): ${(startDate.getTime() - nowUTC.getTime()) / 60000}`)
                    }
                } catch (e) {
                    console.error('Failed to parse start time:', e)
                }
            }

            const payload: any = {
                name: schedulerName,
                description: schedulerDescription,
                mode: schedulerMode,
                interval_value: schedulerMode === 'INTERVAL' ? intervalValue : null,
                interval_unit: schedulerMode === 'INTERVAL' ? intervalUnit : null,
                cron_expression: schedulerMode === 'CRON' ? cronExpression : null,
                script_id: selectedScriptId ? parseInt(selectedScriptId) : null,
                is_active: selectedScheduler.is_active,
                sources: [sourceData]
            }
            
            // If start_time is provided, set next_run_at to that time
            if (nextRunAt) {
                payload.next_run_at = nextRunAt
                console.log(`[Schedule Update] Sending next_run_at to backend: ${nextRunAt}`)
            }
            
            await symbolsAPI.updateScheduler(selectedScheduler.id, payload)

            // Update sources separately
            const existingSourceIds = (selectedScheduler.sources || []).map((s: any) => s.id).filter(Boolean)
            const newSourceIds = schedulerSources.map((s: any) => s.id).filter(Boolean)

            // Delete removed sources
            for (const sourceId of existingSourceIds) {
                if (!newSourceIds.includes(sourceId)) {
                    await symbolsAPI.deleteSource(selectedScheduler.id, sourceId)
                }
            }

            // Add/update sources
            for (const source of schedulerSources) {
                if (source.id && existingSourceIds.includes(source.id)) {
                    // Update existing
                    await symbolsAPI.updateSource(selectedScheduler.id, source.id, source)
                } else {
                    // Add new
                    await symbolsAPI.addSource(selectedScheduler.id, source)
                }
            }

            await loadSchedulers()
            setAutoError('')
            handleCancelEdit()
        } catch (e: any) {
            setAutoError(getErrorMessage(e, 'Failed to update scheduler'))
        }
    }

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const selectedFile = e.target.files[0]
            console.log('File selected:', {
                name: selectedFile.name,
                type: selectedFile.type,
                size: selectedFile.size,
                isFile: selectedFile instanceof File,
                isBlob: selectedFile instanceof Blob,
                constructor: selectedFile.constructor?.name
            })
            // Store in ref first (most reliable)
            fileRef.current = selectedFile
            // Then store in state for UI display
            setFile(selectedFile)
            setError('')
        } else {
            console.warn('No file selected in handleFileChange')
        }
    }

    const handleManualUpload = async (fileToUpload?: File) => {
        // If fileToUpload is provided and it's actually a File, use it
        // Otherwise, prefer fileRef (most reliable), then file state
        // This prevents click events from being passed as files
        let uploadFile: File | null = null

        // Check if fileToUpload is actually a File (not an event)
        if (fileToUpload && fileToUpload instanceof File) {
            uploadFile = fileToUpload
        } else {
            // Ignore fileToUpload if it's not a File (might be an event)
            uploadFile = fileRef.current || file
        }

        if (!uploadFile) {
            setError('Please select a file to upload.')
            return
        }

        // Log what we're working with
        console.log('Preparing to upload file:', {
            source: fileToUpload && fileToUpload instanceof File ? 'parameter' : fileRef.current ? 'ref' : 'state',
            name: uploadFile.name,
            type: uploadFile.type,
            size: uploadFile.size,
            isFile: uploadFile instanceof File,
            isBlob: uploadFile instanceof Blob,
            constructor: uploadFile.constructor?.name,
            hasName: 'name' in uploadFile,
            hasSize: 'size' in uploadFile,
            hasType: 'type' in uploadFile
        })

        // Very lenient validation - accept File, Blob, or any object with file-like properties
        // The API function will do the final validation
        const isFileInstance = uploadFile instanceof File
        const isBlobInstance = uploadFile instanceof Blob
        const isObject = uploadFile && typeof uploadFile === 'object'
        const hasName = isObject && 'name' in uploadFile
        const hasSize = isObject && 'size' in uploadFile

        // Accept if it's a File, Blob, or has at least a name property (minimum requirement)
        const isValidFile = isFileInstance || isBlobInstance || (isObject && hasName)

        if (!isValidFile) {
            console.error('Invalid file object:', {
                uploadFile,
                type: typeof uploadFile,
                constructor: uploadFile?.constructor?.name,
                keys: uploadFile ? Object.keys(uploadFile) : 'null',
                isFile: isFileInstance,
                isBlob: isBlobInstance,
                isObject: isObject,
                hasName: hasName,
                hasSize: hasSize
            })
            setError('Invalid file object. Please select the file again from the file picker.')
            return
        }

        // If it's not a File instance but has File-like properties, log a warning
        if (!isFileInstance && !isBlobInstance && isObject && hasName) {
            console.warn('File is not a File/Blob instance but has File-like properties. Proceeding with upload.')
        }

        setLoading(true)
        setError('')
        try {
            // Determine script ID: use selected script OR create new script if transformation is enabled
            let scriptId: number | undefined = undefined
            if (enableTransformation) {
                if (selectedScriptId) {
                    scriptId = parseInt(selectedScriptId)
                } else if (scriptName.trim() && scriptContent.trim()) {
                    // Create script on-the-fly if not saved yet
                    try {
                        const newScript = await symbolsAPI.createScript({
                            name: scriptName,
                            description: scriptDescription,
                            content: scriptContent
                        })
                        scriptId = newScript.id
                        await loadScripts()
                        setSelectedScriptId(scriptId?.toString() || '')
                        setEditingScriptId(scriptId || null)
                    } catch (e: any) {
                        setError(getErrorMessage(e, 'Failed to create script'))
                        setLoading(false)
                        return
                    }
                }
            }
            // Cast to File for TypeScript, but the API function will handle Blob too
            const data = await symbolsAPI.uploadManual(uploadFile as File, scriptId)
            console.log('Upload preview response:', data)
            console.log('Preview ID received:', data.preview_id)

            // Validate preview data structure
            if (!data || !data.headers || !data.rows) {
                console.error('Invalid preview data structure:', data)
                setError('Invalid preview data received from server. Please try again.')
                setLoading(false)
                return
            }

            // Ensure rows is an array
            if (!Array.isArray(data.rows)) {
                console.error('Preview rows is not an array:', data.rows)
                setError('Invalid preview data format. Please try again.')
                setLoading(false)
                return
            }

            // Ensure headers is an array
            if (!Array.isArray(data.headers)) {
                console.error('Preview headers is not an array:', data.headers)
                setError('Invalid preview data format. Please try again.')
                setLoading(false)
                return
            }

            console.log('Preview data validated:', {
                headers: data.headers.length,
                rows: data.rows.length,
                total_rows: data.total_rows || data.totalRows,
                preview_id: data.preview_id
            })

            // Normalize total_rows field (backend might return total_rows or totalRows)
            const normalizedData = {
                ...data,
                total_rows: data.total_rows || data.totalRows || data.rows.length
            }

            setPreview(normalizedData)
            setError('') // Clear any previous errors
            console.log('Setting step to preview, preview data:', normalizedData)
            setStep('preview') // Move to preview step
            console.log('Step set to preview')
            // Store file in ref for potential re-upload if preview expires
            fileRef.current = uploadFile
            scriptIdRef.current = scriptId
            // Store preview_id in component state for debugging
            if (data.preview_id) {
                console.log('Preview ID stored in state:', data.preview_id)
            }
        } catch (e: any) {
            console.error('Upload error:', e)
            setError(getErrorMessage(e, 'Upload failed'))
        } finally {
            setLoading(false)
        }
    }


    const pollUploadStatus = async (jobIdOrLogId: string | number, totalRows: number) => {
        // Validate job_id - don't start polling with invalid/placeholder job_id
        const jobId = typeof jobIdOrLogId === 'number' ? jobIdOrLogId : parseInt(String(jobIdOrLogId), 10)
        if (!jobId || jobId === 0 || String(jobIdOrLogId).trim() === '0') {
            console.warn('Invalid job_id provided, cannot start polling:', jobIdOrLogId)
            setIsProcessing(false)
            setProcessStatus(null)
            return
        }

        setIsProcessing(true)
        setProcessStatus({ processed: 0, total: totalRows, errors: 0 })

        // Reset completion flag when starting new poll
        isPollingCompletedRef.current = false
        if (pollingTimeoutRef.current) {
            clearTimeout(pollingTimeoutRef.current)
            pollingTimeoutRef.current = null
        }

        let pollCount = 0
        const maxPolls = 1500 // 50 minutes max (1500 * 2 seconds) - for very large uploads
        const pollInterval = 2000 // 2 seconds (mandatory: real-time status updates)
        const maxPollsForPlaceholder = 5 // Max polls for placeholder job_id "0"

        const poll = async () => {
            // Stop polling if already completed or modal closed
            if (isPollingCompletedRef.current) {
                console.log('Polling stopped - upload already completed or modal closed')
                return
            }

            try {
                pollCount++
                console.log(`Polling upload status (attempt ${pollCount}/${maxPolls}):`, jobIdOrLogId)

                const status = await symbolsAPI.getUploadStatus(String(jobId))
                console.log('Upload status response:', status)

                // Normalize status to string (in case it's an enum or number)
                const statusStr = String(status.status || '').toUpperCase()
                
                // Stop polling if we get PENDING status with job_id "0" after a few attempts
                // This indicates we're polling with a placeholder that will never complete
                if ((statusStr === 'PENDING' || statusStr === 'NOT_FOUND') && (jobId === 0 || String(jobIdOrLogId).trim() === '0')) {
                    if (pollCount >= maxPollsForPlaceholder) {
                        console.log('Stopping polling - invalid/placeholder job_id after max attempts')
                        isPollingCompletedRef.current = true
                        setIsProcessing(false)
                        setProcessStatus(null)
                        return
                    }
                }
                
                const uploadedCount = status.uploaded_rows || (status.inserted_rows || 0) + (status.updated_rows || 0)
                const processedCount = status.processed || status.record_count || 0
                const insertedCount = status.inserted_rows || 0
                const updatedCount = status.updated_rows || 0
                const failedCount = status.failed_rows || 0

                // Update progress with detailed counts - use backend-calculated percentage for accuracy
                const progressPercentage = status.progress_percentage !== undefined
                    ? status.progress_percentage
                    : (uploadedCount > 0 && (status.total_rows || totalRows) > 0
                        ? Math.round((uploadedCount / (status.total_rows || totalRows)) * 100 * 10) / 10
                        : 0)
                setProcessStatus({
                    processed: uploadedCount,  // Use uploaded_rows (inserted + updated)
                    total: status.total_rows || totalRows,
                    errors: failedCount,
                    inserted: insertedCount,
                    updated: updatedCount,
                    percentage: progressPercentage,
                    status: statusStr  // Include status for UI display
                })

                // Check if status indicates completion (any terminal status)
                const isCompleted = statusStr === 'SUCCESS' || 
                                   statusStr === 'COMPLETED_WITH_WARNINGS' || 
                                   statusStr === 'PARTIAL' || 
                                   statusStr === 'FAILED' ||
                                   statusStr === 'CANCELLED' ||
                                   statusStr === 'CRASHED' ||
                                   statusStr === 'INTERRUPTED' ||
                                   statusStr === 'STOPPED'
                
                // Only mark as complete if status is any terminal/completion status
                if (isCompleted) {
                    // Mark as completed to stop all further polling
                    isPollingCompletedRef.current = true
                    
                    // Clear any scheduled polling immediately
                    if (pollingTimeoutRef.current) {
                        clearTimeout(pollingTimeoutRef.current)
                        pollingTimeoutRef.current = null
                    }

                    const errorCount = (status.errors || []).length
                    // If errors is a string (JSON), parse it
                    let parsedErrors = status.errors
                    if (typeof status.errors === 'string') {
                        try {
                            parsedErrors = JSON.parse(status.errors)
                        } catch (e) {
                            // If parsing fails, treat as single error message
                            parsedErrors = status.errors ? [status.errors] : []
                        }
                    }
                    const finalErrorCount = Array.isArray(parsedErrors) ? parsedErrors.length : 0

                    const message = (statusStr === 'COMPLETED_WITH_WARNINGS' || finalErrorCount > 0)
                        ? `Successfully uploaded ${processedCount} symbols. ${finalErrorCount} errors occurred.`
                        : `Successfully uploaded ${processedCount} symbols.`

                    console.log('Upload completed - final status:', { 
                        status: statusStr, 
                        processed: processedCount, 
                        total: totalRows, 
                        errors: finalErrorCount,
                        inserted: insertedCount,
                        updated: updatedCount,
                        failed: failedCount
                    })

                    // Update progress to final state - ensure 100% completion is shown
                    setProcessStatus({
                        processed: processedCount,
                        total: totalRows,
                        errors: finalErrorCount,
                        inserted: insertedCount,
                        updated: updatedCount,
                        percentage: 100, // Force 100% on completion
                        status: statusStr
                    })

                    // Small delay to ensure status is displayed, then show success
                    setTimeout(() => {
                        if (activeTab === 'manual') {
                            setResultMsg(message)
                            setStep('success')
                            console.log('Step set to success (manual)')
                        } else {
                            setAutoResultMsg(message)
                            setAutoStep('success')
                            console.log('Step set to success (auto)')
                        }
                        setIsProcessing(false)
                        setProcessStatus(null)

                        // Call onSuccess callback to refresh the symbols table ONCE
                        // Use ref to ensure we only refresh once, even if this code runs multiple times
                        if (!hasRefreshedRef.current) {
                            hasRefreshedRef.current = true
                            console.log('Calling onSuccess callback to refresh symbols table (once)')
                            onSuccess()
                        } else {
                            console.log('Skipping onSuccess callback - already refreshed symbols table')
                        }
                    }, 300) // Small delay to show final status before clearing
                    return
                } else if (statusStr === 'QUEUED') {
                    // Job is queued - show queue status and keep polling
                    setProcessStatus({
                        processed: 0,
                        total: status.total_rows || totalRows,
                        errors: 0,
                        inserted: 0,
                        updated: 0,
                        percentage: 0,
                        status: 'QUEUED'
                    })
                    // Continue polling - job will move to RUNNING when worker picks it up
                    // Only schedule if not completed
                    if (!isPollingCompletedRef.current && pollCount < maxPolls) {
                        pollingTimeoutRef.current = setTimeout(poll, pollInterval)
                    }
                } else if (statusStr === 'RUNNING') {
                    // Job is running - update stats and keep polling
                    setProcessStatus({
                        processed: uploadedCount,
                        total: status.total_rows || totalRows,
                        errors: failedCount,
                        inserted: insertedCount,
                        updated: updatedCount,
                        percentage: progressPercentage,
                        status: 'RUNNING'
                    })
                    // Continue polling - only schedule if not completed
                    if (!isPollingCompletedRef.current && pollCount < maxPolls) {
                        pollingTimeoutRef.current = setTimeout(poll, pollInterval)
                    }
                } else {
                    // Still PENDING or other status, update stats and keep polling
                    const processedCount = status.processed || status.record_count || 0
                    const errorCount = Array.isArray(status.errors) ? status.errors.length : 0

                    // Calculate actual percentage - show real progress, not capped
                    const displayCount = Math.min(processedCount, totalRows) // Cap at total to prevent >100%
                    const displayPercentage = totalRows > 0 ? Math.min(Math.round((displayCount / totalRows) * 100), 100) : 0

                    console.log(`Upload progress update: ${displayCount}/${totalRows} (${displayPercentage}%) - Status: ${statusStr}`)

                    // Always update process status to show real-time progress
                    setProcessStatus({
                        processed: displayCount,
                        total: totalRows,
                        errors: errorCount
                    })

                    // Force a re-render by updating state
                    setIsProcessing(true)

                    if (pollCount >= maxPolls) {
                        throw new Error('Upload is taking too long. Please check the server logs.')
                    }

                    // Continue polling with shorter interval for smoother updates
                    // Only schedule if not completed
                    if (!isPollingCompletedRef.current) {
                        pollingTimeoutRef.current = setTimeout(poll, pollInterval)
                    }
                }
            } catch (e: any) {
                // Mark as completed to stop all further polling
                isPollingCompletedRef.current = true
                
                // Clear any scheduled polling
                if (pollingTimeoutRef.current) {
                    clearTimeout(pollingTimeoutRef.current)
                    pollingTimeoutRef.current = null
                }

                console.error('Polling error:', e)
                const errorMsg = getErrorMessage(e, 'Upload processing failed')
                console.error('Upload processing error details:', {
                    error: e,
                    message: errorMsg,
                    response: e?.response?.data,
                    status: e?.response?.status
                })
                if (activeTab === 'manual') {
                    setError(errorMsg)
                    setStep('preview') // Go back to preview on error
                } else {
                    setAutoError(errorMsg)
                    setAutoStep('preview') // Go back to preview on error
                }
                setIsProcessing(false)
                setProcessStatus(null)
                // Don't call onSuccess on error
            }
        }

        poll()
    }

    const handleManualConfirm = async () => {
        if (!preview?.preview_id) {
            setError('Preview ID is missing. Please upload the file again.')
            return
        }

        // If preview expired, try to re-upload automatically
        if (!fileRef.current) {
            setError('File reference lost. Please click "Re-upload" to refresh the preview.')
            return
        }

        setLoading(true)
        setError('')
        setIsProcessing(true) // Show processing indicator immediately
        setProcessStatus({ processed: 0, total: preview?.total_rows || preview?.totalRows || 0, errors: 0 })

        try {
            console.log('Confirming upload with preview_id:', preview.preview_id)

            const res = await symbolsAPI.confirmUpload(preview.preview_id)
            console.log('Upload confirmation response:', res)

            // Upload started - close modal immediately (non-blocking)
            // Use job_id if available, otherwise fallback to log_id
            const jobIdOrLogId = res.job_id || res.log_id
            // Validate job_id - must be a valid non-zero value
            const isValidJobId = jobIdOrLogId && 
                jobIdOrLogId !== '0' && 
                jobIdOrLogId !== 0 && 
                String(jobIdOrLogId).trim() !== '0' &&
                String(jobIdOrLogId).trim() !== ''
            
            if (isValidJobId) {
                // Determine total rows from message or preview
                const totalRows = preview?.total_rows || preview?.totalRows || 0
                console.log('Starting background upload, job_id/log_id:', jobIdOrLogId, 'totalRows:', totalRows)

                // Start polling for upload status - will call onSuccess once when complete
                pollUploadStatus(jobIdOrLogId, totalRows)
                
                // Show notification that upload is in progress
                setShowBackgroundUploadPopup(true)
                // Close modal immediately - upload runs in background
                // Popup will remain visible because component stays mounted when popup is showing
                onClose()
                // Don't call onSuccess here - it will be called once when polling detects completion
            } else {
                // Fallback to old behavior if no log_id
                setIsProcessing(false)
                setProcessStatus(null)
                const errorCount = res.errors || 0
                const successCount = res.message?.match(/\d+/)?.[0] || res.processed || '0'
                const message = errorCount > 0
                    ? `Successfully uploaded ${successCount} symbols. ${errorCount} errors occurred.`
                    : res.message || `Successfully uploaded ${successCount} symbols.`
                setResultMsg(message)
                setStep('success')
                onSuccess()
            }
        } catch (e: any) {
            console.error('Upload confirmation error:', e)
            console.error('Upload confirmation error details:', {
                error: e,
                response: e?.response?.data,
                status: e?.response?.status,
                message: e?.message
            })
            setIsProcessing(false)
            setProcessStatus(null)
            const errorMsg = getErrorMessage(e, 'Confirmation failed')

            if (e?.response?.status === 404) {
                const detail = e?.response?.data?.detail || 'Preview session expired or not found'
                if (fileRef.current) {
                    setError(`${detail} The preview cache was likely cleared (server restart). Click "Re-upload" to refresh the preview, then immediately click "Confirm Upload".`)
                } else {
                    setError(`${detail} Please upload the file again.`)
                }
            } else {
                setError(errorMsg)
            }
            // Don't call onSuccess on error
        } finally {
            setLoading(false)
        }
    }

    const handleAutoTrigger = async () => {
        if (!sourceUrl) return
        setAutoLoading(true)
        setError('')
        try {
            // Determine script ID: use selected script OR create new script if transformation is enabled
            let scriptId: number | undefined = undefined
            if (enableTransformation) {
                if (selectedScriptId) {
                    scriptId = parseInt(selectedScriptId)
                } else if (scriptName.trim() && scriptContent.trim()) {
                    // Create script on-the-fly if not saved yet
                    try {
                        const newScript = await symbolsAPI.createScript({
                            name: scriptName,
                            description: scriptDescription,
                            content: scriptContent
                        })
                        scriptId = newScript.id
                        await loadScripts()
                        if (scriptId !== undefined) {
                            setSelectedScriptId(scriptId.toString())
                            setEditingScriptId(scriptId)
                        }
                    } catch (e: any) {
                        setError(getErrorMessage(e, 'Failed to create script'))
                        setAutoLoading(false)
                        return
                    }
                }
            }
            await symbolsAPI.uploadAuto({
                source_type: 'API_ENDPOINT', // Defaulting for simple trigger
                url: sourceUrl,
                file_handling_mode: 'LIVE_API', // Default
                script_id: scriptId
            })
            setResultMsg('Auto-ingestion job triggered successfully.')
            setStep('success')
        } catch (e: any) {
            setError(getErrorMessage(e, 'Auto-ingestion failed'))
        } finally {
            setAutoLoading(false)
        }
    }

    const handleDownloadTemplate = async () => {
        try {
            const res = await symbolsAPI.getTemplate()
            const blob = new Blob([res.content], { type: 'text/csv' })
            const url = window.URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = res.filename
            a.click()
        } catch (e) {
            console.error(e)
        }
    }

    const handleAutoUpload = async () => {
        if (!sourceUrl.trim()) {
            setAutoError('Please enter a source URL.')
            return
        }

        setAutoLoading(true)
        setAutoError('')
        try {
            let scriptId: number | undefined = undefined
            if (enableTransformation) {
                if (selectedScriptId) {
                    scriptId = parseInt(selectedScriptId)
                } else if (scriptName.trim() && scriptContent.trim()) {
                    try {
                        const newScript = await symbolsAPI.createScript({
                            name: scriptName,
                            description: scriptDescription,
                            content: scriptContent
                        })
                        scriptId = newScript.id
                        await loadScripts()
                        setSelectedScriptId(scriptId?.toString() || '')
                        setEditingScriptId(scriptId || null)
                    } catch (e: any) {
                        setAutoError(getErrorMessage(e, 'Failed to create script'))
                        setAutoLoading(false)
                        return
                    }
                }
            }

            // Call auto upload API
            const data = await symbolsAPI.uploadAuto({
                source_type: dataSourceType,
                url: sourceUrl,
                headers: Object.keys(sourceHeaders).length > 0 ? sourceHeaders : undefined,
                auth_token: sourceAuthToken || undefined,
                file_handling_mode: fileHandlingMode,
                file_type: fileType === 'AUTO' ? undefined : fileType,
                script_id: scriptId
            })

            setAutoPreview(data)
            setAutoStep('preview')
        } catch (e: any) {
            setAutoError(getErrorMessage(e, 'Failed to fetch data from source'))
        } finally {
            setAutoLoading(false)
        }
    }

    const handleAutoConfirm = async () => {
        if (!autoPreview?.preview_id) {
            setAutoError('Preview session expired. Please fetch data again.')
            return
        }

        setAutoLoading(true)
        setAutoError('')
        try {
            const res = await symbolsAPI.confirmUpload(autoPreview.preview_id)

            const jobIdOrLogId = res.job_id || res.log_id
            // Validate job_id - must be a valid non-zero value
            const isValidJobId = jobIdOrLogId && 
                jobIdOrLogId !== '0' && 
                jobIdOrLogId !== 0 && 
                String(jobIdOrLogId).trim() !== '0' &&
                String(jobIdOrLogId).trim() !== ''
            
            if (isValidJobId) {
                // Determine total rows from auto preview
                const totalRows = autoPreview?.total_rows || autoPreview?.totalRows || 0
                console.log('Starting background auto upload, job_id/log_id:', jobIdOrLogId, 'totalRows:', totalRows)

                // Start polling for upload status - will call onSuccess once when complete
                pollUploadStatus(jobIdOrLogId, totalRows)
                
                // Show notification that upload is in progress
                setShowBackgroundUploadPopup(true)
                // Close modal immediately - upload runs in background
                // Popup will remain visible because component stays mounted when popup is showing
                onClose()
                // Don't call onSuccess here - it will be called once when polling detects completion
            } else {
                setAutoResultMsg('Auto upload completed successfully.')
                setAutoStep('success')
                onSuccess()
            }
        } catch (e: any) {
            setAutoError(getErrorMessage(e, 'Failed to confirm upload'))
        } finally {
            setAutoLoading(false)
        }
    }

    const handleClose = () => {
        setFile(null)
        setPreview(null)
        setStep('upload')
        setError('')
        setResultMsg('')
        setIsProcessing(false)
        setProcessStatus(null)
        // Reset auto upload state
        setAutoStep('upload')
        setAutoPreview(null)
        setAutoError('')
        setAutoResultMsg('')
        setSourceUrl('')
        setSelectedScriptId('')
        setEnableTransformation(false)
        setScriptName('')
        setScriptDescription('')
        setScriptContent(`# Python Transformation Script
# FULLY FLEXIBLE - Write ANY Python code you need!
# 
# INPUT/OUTPUT CONTRACT (ONLY RESTRICTION):
# - Input: Variable 'df' (pandas DataFrame) is provided by system
# - Output: Variable 'final_df' (pandas DataFrame) must be assigned
#
# YOU CAN:
# - Write any functions, loops, conditionals
# - Use any variable names
# - Include helper methods
# - Perform any transformations
# - Rename/drop/create columns
# - Apply business logic
#
# SECURITY RESTRICTIONS (sandbox-level):
# - os, sys, subprocess, socket, requests, filesystem, network are blocked

import pandas as pd
import numpy as np
from datetime import datetime

# Example: Flexible transformation with helper function
def normalize_symbols(df):
    """Helper function to normalize symbol data"""
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].str.upper().str.strip()
    if "exchange" in df.columns:
        df["exchange"] = df["exchange"].str.upper()
    return df

# Apply transformations
df = normalize_symbols(df)

# Add metadata if needed
df["processed_at"] = datetime.now()

# REQUIRED: Assign final result to final_df
final_df = df`)
        setEditingScriptId(null)
        setScriptError('')
        fileRef.current = null
        scriptIdRef.current = undefined
        // Reset auto upload state
        setAutoStep('upload')
        setAutoPreview(null)
        setAutoError('')
        setAutoResultMsg('')
        setDataSourceType('FILE_URL')
        setSourceUrl('')
        setSourceHeaders({})
        setSourceAuthToken('')
        setFileHandlingMode('DOWNLOAD')
        setFileType('AUTO')
        setScheduleMode('RUN_ONCE')
        setIntervalPreset('1hr')
        setIntervalCustomValue(1)
        setIntervalCustomUnit('hours')
        setScheduleDateTime('')
        setScheduleTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone)
        setCronExpression('')
        setAutoSources([])
        setShowAutoSourceForm(false)
        setEditingAutoSource(null)
        // Reset scheduler state
        setSelectedScheduler(null)
        setSchedulers([])
        setSchedulerName('')
        setSchedulerDescription('')
        setSchedulerMode('INTERVAL')
        setIntervalValue(6)
        setIntervalUnit('hours')
        setSchedulerSources([])
        setEditingSource(null)
        setShowSourceForm(false)
        onClose()
    }

    const handleSaveScript = async () => {
        if (!scriptName.trim()) {
            setScriptError('Script name is required')
            return
        }
        if (!scriptContent.trim()) {
            setScriptError('Script content is required')
            return
        }

        // Re-check backend health before attempting save
        try {
            await checkBackendHealth()
        } catch (e) {
            // Health check failed, but continue anyway (might be transient)
        }

        if (!backendHealthy) {
            setScriptError('Backend server is not reachable. Please ensure the backend is running at http://localhost:8000.')
            return
        }

        setSavingScript(true)
        setScriptError('')
        try {
            const payload = { name: scriptName, description: scriptDescription, content: scriptContent }
            if (editingScriptId) {
                await symbolsAPI.updateScript(editingScriptId, payload)
            } else {
                await symbolsAPI.createScript(payload)
            }
            await loadScripts()
            setScriptError('')
            // Optionally select the saved script
            const updatedScripts = await symbolsAPI.getScripts()
            const savedScript = updatedScripts.find((s: any) => s.name === scriptName)
            if (savedScript) {
                setSelectedScriptId(savedScript.id.toString())
                setEditingScriptId(savedScript.id)
            }
        } catch (e: any) {
            console.error('Script save error:', e)
            console.error('Error details:', {
                message: e.message,
                response: e.response?.data,
                status: e.response?.status,
                isNetworkError: e.isNetworkError,
                backendUnreachable: e.backendUnreachable,
                hasResponse: !!e.response
            })

            const errorMsg = getErrorMessage(e, 'Save failed')
            setScriptError(errorMsg)

            // CRITICAL: Only mark backend as unhealthy if there's NO HTTP response
            // If e.response exists, backend IS reachable (even if request failed)
            if (!e.response) {
                // No HTTP response - backend might be unreachable
                const isUnreachable =
                    e.code === 'ECONNREFUSED' ||
                    e.code === 'ERR_NETWORK' ||
                    e.code === 'ENOTFOUND' ||
                    e.message?.includes('Network Error') ||
                    e.message?.includes('Failed to fetch')

                if (isUnreachable) {
                    setBackendHealthy(false)
                    // Try to re-check health
                    try {
                        await checkBackendHealth()
                    } catch (healthError) {
                        console.error('Health check failed:', healthError)
                    }
                }
            } else {
                // Backend IS reachable - don't mark as unhealthy
                // Error is due to auth, validation, or server error - not connectivity
                setBackendHealthy(true)
            }
        } finally {
            setSavingScript(false)
        }
    }

    const handleSaveAsNewScript = async () => {
        if (!scriptName.trim()) {
            setScriptError('Script name is required')
            return
        }
        if (!scriptContent.trim()) {
            setScriptError('Script content is required')
            return
        }

        // Re-check backend health before attempting save
        try {
            await checkBackendHealth()
        } catch (e) {
            // Health check failed, but continue anyway (might be transient)
        }

        if (!backendHealthy) {
            setScriptError('Backend server is not reachable. Please ensure the backend is running at http://localhost:8000.')
            return
        }

        setSavingScript(true)
        setScriptError('')
        try {
            const payload = { name: scriptName, description: scriptDescription, content: scriptContent }
            const newScript = await symbolsAPI.createScript(payload)
            await loadScripts()
            setSelectedScriptId(newScript.id.toString())
            setEditingScriptId(newScript.id)
            setScriptError('')
            // Script saved successfully - user can continue or close modal
        } catch (e: any) {
            console.error('Save as new script error:', e)
            console.error('Error details:', {
                message: e.message,
                response: e.response?.data,
                status: e.response?.status,
                isNetworkError: e.isNetworkError,
                backendUnreachable: e.backendUnreachable,
                hasResponse: !!e.response
            })

            const errorMsg = getErrorMessage(e, 'Save as new failed')
            setScriptError(errorMsg)

            // CRITICAL: Only mark backend as unhealthy if there's NO HTTP response
            // If e.response exists, backend IS reachable (even if request failed)
            if (!e.response) {
                // No HTTP response - backend might be unreachable
                const isUnreachable =
                    e.code === 'ECONNREFUSED' ||
                    e.code === 'ERR_NETWORK' ||
                    e.code === 'ENOTFOUND' ||
                    e.message?.includes('Network Error') ||
                    e.message?.includes('Failed to fetch')

                if (isUnreachable) {
                    setBackendHealthy(false)
                    // Try to re-check health
                    try {
                        await checkBackendHealth()
                    } catch (healthError) {
                        console.error('Health check failed:', healthError)
                    }
                }
            } else {
                // Backend IS reachable - don't mark as unhealthy
                // Error is due to auth, validation, or server error - not connectivity
                setBackendHealthy(true)
            }
        } finally {
            setSavingScript(false)
        }
    }

    const handleSelectScript = (scriptId: string) => {
        setSelectedScriptId(scriptId)
        if (scriptId) {
            const script = scripts.find(s => s.id.toString() === scriptId)
            if (script) {
                setScriptName(script.name)
                setScriptDescription(script.description || '')
                setScriptContent(script.content)
                setEditingScriptId(script.id)
                setEnableTransformation(true)
            }
        } else {
            setScriptName('')
            setScriptDescription('')
            setScriptContent(`# Python Transformation Script
# FULLY FLEXIBLE - Write ANY Python code you need!
# 
# INPUT/OUTPUT CONTRACT (ONLY RESTRICTION):
# - Input: Variable 'df' (pandas DataFrame) is provided by system
# - Output: Variable 'final_df' (pandas DataFrame) must be assigned
#
# YOU CAN:
# - Write any functions, loops, conditionals
# - Use any variable names
# - Include helper methods
# - Perform any transformations
# - Rename/drop/create columns
# - Apply business logic
#
# SECURITY RESTRICTIONS (sandbox-level):
# - os, sys, subprocess, socket, requests, filesystem, network are blocked

import pandas as pd
import numpy as np
from datetime import datetime

# Example: Flexible transformation with helper function
def normalize_symbols(df):
    """Helper function to normalize symbol data"""
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].str.upper().str.strip()
    if "exchange" in df.columns:
        df["exchange"] = df["exchange"].str.upper()
    return df

# Apply transformations
df = normalize_symbols(df)

# Add metadata if needed
df["processed_at"] = datetime.now()

# REQUIRED: Assign final result to final_df
final_df = df`)
            setEditingScriptId(null)
        }
    }

    const handleDeleteScript = (scriptId: number) => {
        console.log('[DELETE SCRIPT] handleDeleteScript called with scriptId:', scriptId)
        if (!scriptId || isNaN(scriptId) || scriptId <= 0) {
            console.error('[DELETE SCRIPT] Invalid scriptId:', scriptId)
            setErrorPopupMessage('Invalid script ID. Please select a script first.')
            setShowErrorPopup(true)
            return
        }
        // Show confirmation dialog
        console.log('[DELETE SCRIPT] Setting scriptToDelete and showing confirmation')
        setScriptToDelete(scriptId)
        setShowDeleteConfirm(true)
    }

    const confirmDeleteScript = async () => {
        if (!scriptToDelete) return
        
        try {
            setScriptError('')
            setShowDeleteConfirm(false)
            console.log('[DELETE SCRIPT] Starting deletion for script ID:', scriptToDelete)

            // Make the API call
            const result = await symbolsAPI.deleteScript(scriptToDelete)
            console.log('[DELETE SCRIPT] API response:', result)

            // Backend returns: {"message": "...", "id": id, "success": True}
            // Check if deletion was successful
            if (result && (result.success === true || result.id === scriptToDelete)) {
                console.log('[DELETE SCRIPT] Deletion successful, reloading scripts list...')

                // Reload scripts list to reflect deletion
                await loadScripts()

                // Verify script was actually removed
                const updatedScripts = await symbolsAPI.getScripts()
                const scriptStillExists = updatedScripts.some((s: any) => s.id === scriptToDelete)

                if (scriptStillExists) {
                    console.warn('[DELETE SCRIPT] Script still exists after deletion')
                    const errorMsg = 'Script may still be in use by a scheduler. Please check and remove scheduler references first.'
                    setScriptError(errorMsg)
                    setError(errorMsg)
                    setErrorPopupMessage(errorMsg)
                    setShowErrorPopup(true)
                } else {
                    console.log('[DELETE SCRIPT] Script successfully deleted and removed from list')
                    // Clear selection if deleted script was selected
                    if (selectedScriptId === scriptToDelete.toString()) {
                        setSelectedScriptId('')
                        setEnableTransformation(false)
                    }
                    // Clear editing if deleted script was being edited
                    if (editingScriptId === scriptToDelete) {
                        setEditingScriptId(null)
                        setScriptName('')
                        setScriptDescription('')
                        setScriptContent(`# Python Transformation Script
# FULLY FLEXIBLE - Write ANY Python code you need!
# 
# INPUT/OUTPUT CONTRACT (ONLY RESTRICTION):
# - Input: Variable 'df' (pandas DataFrame) is provided by system
# - Output: Variable 'final_df' (pandas DataFrame) must be assigned
#
# YOU CAN:
# - Write any functions, loops, conditionals
# - Use any variable names
# - Include helper methods
# - Perform any transformations
# - Rename/drop/create columns
# - Apply business logic
#
# SECURITY RESTRICTIONS (sandbox-level):
# - os, sys, subprocess, socket, requests, filesystem, network are blocked

import pandas as pd
import numpy as np
from datetime import datetime

# Example: Flexible transformation with helper function
def normalize_symbols(df):
    """Helper function to normalize symbol data"""
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].str.upper().str.strip()
    if "exchange" in df.columns:
        df["exchange"] = df["exchange"].str.upper()
    return df

# Apply transformations
df = normalize_symbols(df)

# Add metadata if needed
df["processed_at"] = datetime.now()

# REQUIRED: Assign final result to final_df
final_df = df`)
                    }
                }
            } else {
                const errorMsg = result?.message || result?.detail || 'Delete operation did not return expected result'
                console.error('[DELETE SCRIPT] Unexpected response:', result)
                throw new Error(errorMsg)
            }
        } catch (e: any) {
            console.error('[DELETE SCRIPT] Error in UploadSymbolModal:', e)
            console.error('[DELETE SCRIPT] Error details:', {
                error: e,
                response: e?.response?.data,
                status: e?.response?.status,
                message: e?.message,
                scriptToDelete
            })
            const errorMsg = getErrorMessage(e, 'Delete failed. Please check console for details.')
            setScriptError(errorMsg)
            setError(errorMsg)
            setErrorPopupMessage(errorMsg)
            setShowErrorPopup(true)
        } finally {
            setScriptToDelete(null)
        }
    }

    // Always render the background upload popup even when main modal is closed
    const backgroundUploadPopup = (
        <SecondaryModal
            isOpen={showBackgroundUploadPopup}
            onClose={() => {
                setShowBackgroundUploadPopup(false)
            }}
            title="Upload in Progress"
            maxWidth="max-w-md"
        >
            <div className="flex flex-col items-center justify-center py-4">
                <p className="text-text-secondary text-center whitespace-pre-wrap mb-6">
                    Running in background check under status
                </p>
                <div className="flex justify-center">
                    <Button
                        size="sm"
                        onClick={() => {
                            setShowBackgroundUploadPopup(false)
                        }}
                    >
                        OK
                    </Button>
                </div>
            </div>
        </SecondaryModal>
    )

    if (!isOpen && !showBackgroundUploadPopup) return null

    return (
        <>
        {isOpen && (
        <div 
            className="fixed inset-0 z-[9999] flex items-center justify-center"
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                width: '100vw',
                height: '100dvh',
                minHeight: '100vh',
                margin: 0,
                padding: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                opacity: isVisible ? undefined : 0,
                animation: isVisible ? 'backdropFadeIn 0.3s ease-out' : 'none',
            }}
            onClick={(e) => {
                // Close modal when clicking backdrop
                if (e.target === e.currentTarget) {
                    handleClose()
                }
            }}
        >
            <div 
                className="relative"
                onClick={(e) => e.stopPropagation()}
            >
                <div 
                    className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-6xl mx-4 max-h-[90vh] relative modal-content" 
                    style={{ 
                        minWidth: '800px', 
                        maxWidth: 'calc(100vw - 2rem)',
                        opacity: isVisible ? undefined : 0,
                        transform: isVisible ? undefined : 'scale(0.95)',
                        animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
                    }}
                >
                {/* Close Button - Positioned outside modal at top-right, aligned with modal top */}
                <button 
                    onClick={handleClose} 
                    className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10001] flex items-center justify-center"
                    title="Close"
                    style={{
                        animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
                    }}
                >
                    <X className="w-5 h-5" />
                </button>
                <div className="p-6 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-6">
                    <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
                        Upload Symbols
                    </h2>
                </div>

                {((activeTab === 'manual' && step === 'success') || (activeTab === 'auto' && autoStep === 'success')) ? (
                    <div className="text-center py-10 space-y-4">
                        <div className="text-5xl">✅</div>
                        <h3 className="text-xl font-bold text-success">Upload Successful</h3>
                        <p className="text-text-secondary">{activeTab === 'manual' ? resultMsg : autoResultMsg}</p>
                        <p className="text-xs text-text-secondary mt-2">The symbols have been saved to the database and are now visible in the symbols list.</p>
                        <div className="pt-6">
                            <Button onClick={() => { handleClose(); }}>Done</Button>
                        </div>
                    </div>
                ) : (
                    <>
                        <div className="flex gap-4 border-b border-[#1f2a44] mb-6">
                            <button
                                className={`pb-2 px-1 text-sm font-medium transition-colors ${activeTab === 'manual' ? 'text-primary border-b-2 border-primary' : 'text-text-secondary hover:text-text-primary'}`}
                                onClick={() => setActiveTab('manual')}
                            >
                                Manual Upload
                            </button>
                            <button
                                className={`pb-2 px-1 text-sm font-medium transition-colors ${activeTab === 'auto' ? 'text-primary border-b-2 border-primary' : 'text-text-secondary hover:text-text-primary'}`}
                                onClick={() => {
                                    setActiveTab('auto')
                                    loadSchedulers() // Load schedulers when tab is opened
                                    loadScripts() // Load scripts when tab is opened
                                }}
                            >
                                Auto Schedule
                            </button>
                        </div>

                        {activeTab === 'manual' && (
                            <>
                                {step === 'upload' && (
                                    <div className="space-y-6">
                                        <div className="border-2 border-dashed border-[#1f2a44] rounded-lg p-10 text-center hover:border-primary/50 transition-colors">
                                            <Input
                                                type="file"
                                                accept=".csv,.xlsx"
                                                onChange={handleFileChange}
                                                className="hidden"
                                                id="file-upload"
                                            />
                                            <label htmlFor="file-upload" className="cursor-pointer flex flex-col items-center gap-2">
                                                <span className="text-4xl">📄</span>
                                                <span className="text-text-primary font-medium">Click to select file</span>
                                                <span className="text-text-secondary text-sm">Supported: CSV, Excel</span>
                                                {file && <span className="text-primary font-bold mt-2">{file.name}</span>}
                                            </label>
                                        </div>

                                        {/* Transformation Script Toggle */}
                                        <div className="flex items-center gap-3 p-3 bg-[#0a1020] rounded border border-[#1f2a44]">
                                            <input
                                                type="checkbox"
                                                id="enable-transformation"
                                                checked={enableTransformation}
                                                onChange={(e) => {
                                                    setEnableTransformation(e.target.checked)
                                                    if (!e.target.checked) {
                                                        setSelectedScriptId('')
                                                        setEditingScriptId(null)
                                                    }
                                                }}
                                                className="w-4 h-4 text-primary bg-[#0a1020] border-[#1f2a44] rounded focus:ring-primary"
                                            />
                                            <label htmlFor="enable-transformation" className="text-sm text-text-primary cursor-pointer">
                                                Enable Transformation Script
                                            </label>
                                        </div>

                                        {/* Transformation Script Panel (only if toggle is ON) */}
                                        {enableTransformation && (
                                            <div className="space-y-4 p-4 bg-[#0a1020] rounded border border-[#1f2a44]">
                                                <div className="flex items-center justify-between">
                                                    <h3 className="text-sm font-semibold text-text-primary">Transformation Script</h3>
                                                    <div className="flex gap-2">
                                                        <select
                                                            className="bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-1.5 text-xs text-text-primary focus:outline-none focus:border-primary"
                                                            value={selectedScriptId}
                                                            onChange={(e) => handleSelectScript(e.target.value)}
                                                        >
                                                            <option value="">New Script</option>
                                                            {scripts.map(s => (
                                                                <option key={s.id} value={s.id.toString()}>{s.name} (v{s.version})</option>
                                                            ))}
                                                        </select>
                                                        {selectedScriptId && (
                                                            <>
                                                                <Button
                                                                    type="button"
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    onClick={(e) => {
                                                                        e.preventDefault()
                                                                        e.stopPropagation()
                                                                        console.log('[DELETE BUTTON] Clicked, selectedScriptId:', selectedScriptId)
                                                                        const scriptId = parseInt(selectedScriptId)
                                                                        console.log('[DELETE BUTTON] Parsed scriptId:', scriptId)
                                                                        if (!isNaN(scriptId) && scriptId > 0) {
                                                                            console.log('[DELETE BUTTON] Calling handleDeleteScript with:', scriptId)
                                                                            handleDeleteScript(scriptId)
                                                                        } else {
                                                                            console.error('[DELETE BUTTON] Invalid scriptId:', scriptId, 'from selectedScriptId:', selectedScriptId)
                                                                        }
                                                                    }}
                                                                    className="text-xs text-danger hover:text-danger"
                                                                    title="Delete script"
                                                                >
                                                                    <Trash2 className="w-3 h-3 mr-1" />
                                                                    Delete
                                                                </Button>
                                                            </>
                                                        )}
                                                    </div>
                                                </div>

                                                <div className="grid grid-cols-2 gap-2">
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">Script Name</label>
                                                        <Input
                                                            value={scriptName}
                                                            onChange={(e) => setScriptName(e.target.value)}
                                                            placeholder="e.g. NSE Normalizer"
                                                            className="text-sm"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">Description (Optional)</label>
                                                        <Input
                                                            value={scriptDescription}
                                                            onChange={(e) => setScriptDescription(e.target.value)}
                                                            placeholder="Optional description"
                                                            className="text-sm"
                                                        />
                                                    </div>
                                                </div>

                                                <div className="flex flex-col">
                                                    <label className="text-xs text-text-secondary mb-1">Python Code</label>
                                                    <textarea
                                                        className="flex-1 min-h-[300px] bg-[#0a1020] border border-[#1f2a44] rounded p-4 font-mono text-sm text-gray-300 focus:outline-none focus:border-primary resize-none"
                                                        value={scriptContent}
                                                        onChange={(e) => setScriptContent(e.target.value)}
                                                        spellCheck={false}
                                                        placeholder="# Input: df (pandas DataFrame)&#10;# Output: final_df (pandas DataFrame)&#10;&#10;import pandas as pd&#10;&#10;df['symbol'] = df['symbol'].str.upper()&#10;final_df = df"
                                                    />
                                                </div>

                                                {!backendHealthy && (
                                                    <div className="p-2 bg-yellow-500/10 border border-yellow-500/20 rounded mb-2">
                                                        <p className="text-yellow-500 text-xs">
                                                            ⚠️ Backend server is not reachable. Script saving is disabled. Please ensure the backend is running.
                                                        </p>
                                                    </div>
                                                )}

                                                {scriptError && (
                                                    <div className="p-2 bg-red-500/10 border border-red-500/20 rounded mb-2">
                                                        <p className="text-error text-xs">{scriptError}</p>
                                                    </div>
                                                )}

                                                <div className="flex gap-2 justify-end">
                                                    <Button
                                                        variant="secondary"
                                                        size="sm"
                                                        onClick={handleSaveAsNewScript}
                                                        disabled={!scriptName.trim() || savingScript || !backendHealthy}
                                                        title={!backendHealthy ? 'Backend server is not reachable' : ''}
                                                    >
                                                        {savingScript ? 'Saving...' : 'Save As New'}
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        onClick={handleSaveScript}
                                                        disabled={!scriptName.trim() || savingScript || !backendHealthy}
                                                        title={!backendHealthy ? 'Backend server is not reachable' : ''}
                                                    >
                                                        {savingScript ? 'Saving...' : editingScriptId ? 'Update Script' : 'Save Script'}
                                                    </Button>
                                                </div>
                                                
                                                {/* Edit Current Script Section - appears when a script is selected */}
                                                {selectedScriptId && editingScriptId && (
                                                    <div className="mt-4 pt-4 border-t border-[#1f2a44]">
                                                        <div className="flex items-center justify-between mb-2">
                                                            <span className="text-xs text-text-secondary">Editing: {scriptName}</span>
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                onClick={(e) => {
                                                                    e.preventDefault()
                                                                    e.stopPropagation()
                                                                    handleSelectScript(selectedScriptId) // Reload script
                                                                }}
                                                                className="text-xs text-info hover:text-info"
                                                                title="Reload script from database"
                                                            >
                                                                <RefreshCw className="w-3 h-3 mr-1" />
                                                                Reload
                                                            </Button>
                                                        </div>
                                                        <p className="text-xs text-text-secondary mb-2">
                                                            Make changes above and click "Update Script" to save changes to the current script.
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        <div className="flex justify-between items-center pt-4 border-t border-[#1f2a44]">
                                            <Button variant="ghost" size="sm" onClick={handleDownloadTemplate}>
                                                ⬇ Download Template
                                            </Button>
                                            <div className="flex gap-2">
                                                <Button variant="secondary" onClick={handleClose}>Cancel</Button>
                                                <Button onClick={() => handleManualUpload()} disabled={!file || loading}>
                                                    {loading ? 'Analyzing...' : 'Preview Upload'}
                                                </Button>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {step === 'preview' && preview && (
                                    <div className="space-y-4">
                                        {/* Processing Status Indicator - Show at top when processing */}
                                        {isProcessing && (
                                            <div className="bg-primary/10 border-2 border-primary/50 rounded-lg p-5 shadow-lg">
                                                <div className="flex items-center gap-3 mb-3">
                                                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary"></div>
                                                    <span className="text-base font-bold text-primary">Uploading Symbols...</span>
                                                </div>

                                            </div>
                                        )}

                                        <div className="flex justify-between items-center bg-secondary/10 p-3 rounded">
                                            <div>
                                                <p className="text-sm text-text-secondary">File: <span className="text-text-primary font-bold">{file?.name}</span></p>
                                                <p className="text-sm text-text-secondary">Rows: <span className="text-text-primary font-bold">{preview.total_rows || preview.totalRows || 0}</span></p>
                                            </div>
                                        </div>

                                        {preview.headers && Array.isArray(preview.headers) && preview.headers.length > 0 && preview.rows && Array.isArray(preview.rows) && preview.rows.length > 0 ? (
                                            <div className="overflow-x-auto border border-[#1f2a44] rounded">
                                                <Table>
                                                    <TableHeader>
                                                        {preview.headers.map((h: string) => (
                                                            <TableHeaderCell key={h}>{h}</TableHeaderCell>
                                                        ))}
                                                    </TableHeader>
                                                    <TableBody>
                                                        {preview.rows.map((row: any, i: number) => (
                                                            <TableRow key={i}>
                                                                {preview.headers.map((h: string) => (
                                                                    <TableCell key={h} className="whitespace-nowrap">
                                                                        {row[h] !== null && row[h] !== undefined ? String(row[h]) : ''}
                                                                    </TableCell>
                                                                ))}
                                                            </TableRow>
                                                        ))}
                                                    </TableBody>
                                                </Table>
                                            </div>
                                        ) : (
                                            <div className="border border-[#1f2a44] rounded p-8 text-center">
                                                <p className="text-text-secondary">No preview data available</p>
                                                <p className="text-xs text-text-secondary mt-2">
                                                    Headers: {preview.headers ? (Array.isArray(preview.headers) ? preview.headers.length : 'invalid') : 'missing'}
                                                    <br />
                                                    Rows: {preview.rows ? (Array.isArray(preview.rows) ? preview.rows.length : 'invalid') : 'missing'}
                                                </p>
                                            </div>
                                        )}

                                        <div className="flex justify-end gap-2 pt-4 border-t border-[#1f2a44]">
                                            <Button variant="secondary" onClick={() => setStep('upload')} disabled={isProcessing}>Back</Button>
                                            {fileRef.current && (
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={async (e) => {
                                                        e.preventDefault()
                                                        const storedFile = fileRef.current
                                                        if (storedFile && storedFile instanceof File) {
                                                            setFile(storedFile)
                                                            if (scriptIdRef.current !== undefined) {
                                                                setSelectedScriptId(scriptIdRef.current.toString())
                                                            }
                                                            // Re-upload to get a fresh preview_id
                                                            await handleManualUpload(storedFile)
                                                            // After re-upload, the preview step will show again
                                                            // User can then immediately click "Confirm Upload"
                                                        } else {
                                                            setError('File reference lost. Please select the file again.')
                                                        }
                                                    }}
                                                    disabled={loading || isProcessing}
                                                    title="Re-upload the file to get a fresh preview session"
                                                >
                                                    Re-upload
                                                </Button>
                                            )}
                                            <Button
                                                onClick={handleManualConfirm}
                                                disabled={loading || isProcessing || !preview?.preview_id}
                                                title={!preview?.preview_id ? 'Preview session expired. Please upload again.' : ''}
                                            >
                                                {loading || isProcessing ? 'Processing...' : 'Confirm Upload'}
                                            </Button>
                                        </div>
                                        {preview && !isProcessing && (
                                            <p className="text-xs text-text-secondary text-center mt-2">
                                                Ready to upload {preview.total_rows || preview.totalRows || 0} symbols. Click "Confirm Upload" to save to database.
                                                {fileRef.current && (
                                                    <span className="block mt-1 text-warning">
                                                        ⚠️ If you see a "Preview session expired" error, click "Re-upload" to refresh, then immediately click "Confirm Upload".
                                                    </span>
                                                )}
                                            </p>
                                        )}
                                    </div>
                                )}
                            </>
                        )}

                        {activeTab === 'auto' && (
                            <div className="space-y-6">
                                {/* Auto Upload Form - Matches Manual Upload Structure */}
                                <div className="space-y-6">
                                    {/* Source Configuration Section - Matches Manual Upload File Selection */}
                                    <div className="border-2 border-dashed border-[#1f2a44] rounded-lg p-6 hover:border-primary/50 transition-colors">
                                        <div className="space-y-4">
                                            <div className="flex items-center gap-2 mb-4">
                                                <span className="text-2xl">🔗</span>
                                                <h3 className="text-sm font-semibold text-text-primary">Source Configuration</h3>
                                            </div>

                                            {/* Source Type Selector */}
                                            <div>
                                                <label className="text-xs text-text-secondary mb-1 block">Source Type *</label>
                                                <select
                                                    className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                                    value={schedulerSources[0]?.source_type || 'DOWNLOADABLE_URL'}
                                                    onChange={(e) => {
                                                        const newType = e.target.value
                                                        if (schedulerSources.length > 0) {
                                                            setSchedulerSources([{ ...schedulerSources[0], source_type: newType }])
                                                        } else {
                                                            setSchedulerSources([{ source_type: newType, url: '', name: 'New Source' }])
                                                        }
                                                    }}
                                                >
                                                    <option value="DOWNLOADABLE_URL">URL</option>
                                                    <option value="API_ENDPOINT">API</option>
                                                </select>
                                            </div>

                                            {/* URL Source - Simple */}
                                            {(!schedulerSources[0]?.source_type || schedulerSources[0]?.source_type === 'DOWNLOADABLE_URL') && (
                                                <div>
                                                    <label className="text-xs text-text-secondary mb-1 block">File Download URL *</label>
                                                    <Input
                                                        value={schedulerSources[0]?.url || ''}
                                                        onChange={(e) => {
                                                            if (schedulerSources.length > 0) {
                                                                setSchedulerSources([{ ...schedulerSources[0], url: e.target.value }])
                                                            } else {
                                                                setSchedulerSources([{ source_type: 'DOWNLOADABLE_URL', url: e.target.value, name: 'New Source' }])
                                                            }
                                                        }}
                                                        placeholder="https://example.com/symbols.csv"
                                                        className="text-sm"
                                                    />
                                                    <p className="text-xs text-text-secondary mt-1">
                                                        File will be temporarily downloaded and processed
                                                    </p>
                                                </div>
                                            )}

                                            {/* API Source - Complete Configuration */}
                                            {schedulerSources[0]?.source_type === 'API_ENDPOINT' && (
                                                <div className="space-y-4">
                                                    {/* API Endpoint */}
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">API Endpoint *</label>
                                                        <Input
                                                            value={schedulerSources[0]?.url || ''}
                                                            onChange={(e) => {
                                                                if (schedulerSources.length > 0) {
                                                                    setSchedulerSources([{ ...schedulerSources[0], url: e.target.value }])
                                                                } else {
                                                                    setSchedulerSources([{ source_type: 'API_ENDPOINT', url: e.target.value, name: 'New Source' }])
                                                                }
                                                            }}
                                                            placeholder="https://api.example.com/symbols"
                                                            className="text-sm"
                                                        />
                                                    </div>

                                                    {/* HTTP Method */}
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">HTTP Method</label>
                                                        <select
                                                            className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                                            value={apiMethod}
                                                            onChange={(e) => setApiMethod(e.target.value as 'GET' | 'POST')}
                                                        >
                                                            <option value="GET">GET</option>
                                                            <option value="POST">POST</option>
                                                        </select>
                                                    </div>

                                                    {/* Authentication */}
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">Authentication</label>
                                                        <select
                                                            className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                                            value={apiAuthType}
                                                            onChange={(e) => setApiAuthType(e.target.value as 'NONE' | 'API_KEY' | 'BEARER_TOKEN')}
                                                        >
                                                            <option value="NONE">None</option>
                                                            <option value="API_KEY">API Key</option>
                                                            <option value="BEARER_TOKEN">Bearer Token</option>
                                                        </select>
                                                    </div>

                                                    {/* API Key Configuration */}
                                                    {apiAuthType === 'API_KEY' && (
                                                        <div className="grid grid-cols-2 gap-2">
                                                            <div>
                                                                <label className="text-xs text-text-secondary mb-1 block">Key Name</label>
                                                                <Input
                                                                    value={apiKey}
                                                                    onChange={(e) => setApiKey(e.target.value)}
                                                                    placeholder="X-API-Key"
                                                                    className="text-sm"
                                                                />
                                                            </div>
                                                            <div>
                                                                <label className="text-xs text-text-secondary mb-1 block">Key Value</label>
                                                                <Input
                                                                    type="password"
                                                                    value={apiKeyValue}
                                                                    onChange={(e) => setApiKeyValue(e.target.value)}
                                                                    placeholder="Your API key"
                                                                    className="text-sm"
                                                                />
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Bearer Token */}
                                                    {apiAuthType === 'BEARER_TOKEN' && (
                                                        <div>
                                                            <label className="text-xs text-text-secondary mb-1 block">Bearer Token</label>
                                                            <Input
                                                                type="password"
                                                                value={bearerToken}
                                                                onChange={(e) => setBearerToken(e.target.value)}
                                                                placeholder="Your bearer token"
                                                                className="text-sm"
                                                            />
                                                        </div>
                                                    )}

                                                    {/* Query Parameters */}
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">Query Parameters (Optional)</label>
                                                        <div className="space-y-2">
                                                            {queryParams.map((param, idx) => (
                                                                <div key={idx} className="grid grid-cols-[1fr_1fr_auto] gap-2">
                                                                    <Input
                                                                        value={param.key}
                                                                        onChange={(e) => {
                                                                            const newParams = [...queryParams]
                                                                            newParams[idx].key = e.target.value
                                                                            setQueryParams(newParams)
                                                                        }}
                                                                        placeholder="Key"
                                                                        className="text-sm"
                                                                    />
                                                                    <Input
                                                                        value={param.value}
                                                                        onChange={(e) => {
                                                                            const newParams = [...queryParams]
                                                                            newParams[idx].value = e.target.value
                                                                            setQueryParams(newParams)
                                                                        }}
                                                                        placeholder="Value"
                                                                        className="text-sm"
                                                                    />
                                                                    <Button
                                                                        variant="ghost"
                                                                        size="sm"
                                                                        onClick={() => setQueryParams(queryParams.filter((_, i) => i !== idx))}
                                                                    >
                                                                        ×
                                                                    </Button>
                                                                </div>
                                                            ))}
                                                            <Button
                                                                variant="ghost"
                                                                size="sm"
                                                                onClick={() => setQueryParams([...queryParams, { key: '', value: '' }])}
                                                                className="text-xs"
                                                            >
                                                                + Add Parameter
                                                            </Button>
                                                        </div>
                                                    </div>

                                                    {/* Test Connection Button */}
                                                    <div className="pt-2">
                                                        <Button
                                                            variant="secondary"
                                                            size="sm"
                                                            onClick={async () => {
                                                                const url = schedulerSources[0]?.url
                                                                if (!url) {
                                                                    setAutoError('Please enter a URL/Endpoint first')
                                                                    return
                                                                }
                                                                setAutoError('')
                                                                try {
                                                                    // Build headers for test
                                                                    let testHeaders: any = {}
                                                                    if (apiAuthType === 'BEARER_TOKEN' && bearerToken) {
                                                                        testHeaders['Authorization'] = `Bearer ${bearerToken}`
                                                                    } else if (apiAuthType === 'API_KEY' && apiKey && apiKeyValue) {
                                                                        testHeaders[apiKey] = apiKeyValue
                                                                    }

                                                                    // Use backend endpoint to test connection (avoids CORS issues)
                                                                    const result = await symbolsAPI.testConnection(
                                                                        url,
                                                                        schedulerSources[0]?.source_type || 'DOWNLOADABLE_URL',
                                                                        schedulerSources[0]?.source_type === 'API_ENDPOINT' ? apiMethod : undefined,
                                                                        Object.keys(testHeaders).length > 0 ? testHeaders : undefined
                                                                    )

                                                                    console.log('[TEST CONNECTION] Result:', result)
                                                                    if (result && result.success) {
                                                                        setAutoError('')
                                                                        setTestConnectionResult({ success: true, message: result.message || 'Connection test successful' })
                                                                        setShowTestConnectionModal(true)
                                                                        console.log('[TEST CONNECTION] Setting success modal')
                                                                    } else {
                                                                        setTestConnectionResult({ success: false, message: result?.message || 'Connection test failed' })
                                                                        setShowTestConnectionModal(true)
                                                                        console.log('[TEST CONNECTION] Setting failure modal')
                                                                    }
                                                                } catch (e: any) {
                                                                    console.error('[TEST CONNECTION] Error:', e)
                                                                    setTestConnectionResult({ success: false, message: getErrorMessage(e, 'Connection test failed') })
                                                                    setShowTestConnectionModal(true)
                                                                    console.log('[TEST CONNECTION] Setting error modal')
                                                                }
                                                            }}
                                                            disabled={!schedulerSources[0]?.url}
                                                        >
                                                            Test Connection
                                                        </Button>
                                                    </div>
                                                </div>
                                            )}

                                            {/* Test Connection for URL Source */}
                                            {(!schedulerSources[0]?.source_type || schedulerSources[0]?.source_type === 'DOWNLOADABLE_URL') && schedulerSources[0]?.url && (
                                                <div className="pt-2">
                                                    <Button
                                                        variant="secondary"
                                                        size="sm"
                                                        onClick={async () => {
                                                            const url = schedulerSources[0]?.url
                                                            if (!url) {
                                                                setAutoError('Please enter a URL first')
                                                                return
                                                            }
                                                            setAutoError('')
                                                            try {
                                                                // Use backend endpoint to test connection (avoids CORS issues)
                                                                const result = await symbolsAPI.testConnection(url, 'DOWNLOADABLE_URL')
                                                                
                                                                console.log('[TEST CONNECTION] Result:', result)
                                                                if (result && result.success) {
                                                                    setAutoError('')
                                                                    setTestConnectionResult({ success: true, message: result.message || 'Connection test successful' })
                                                                    setShowTestConnectionModal(true)
                                                                    console.log('[TEST CONNECTION] Setting success modal')
                                                                } else {
                                                                    setTestConnectionResult({ success: false, message: result?.message || 'Connection test failed' })
                                                                    setShowTestConnectionModal(true)
                                                                    console.log('[TEST CONNECTION] Setting failure modal')
                                                                }
                                                            } catch (e: any) {
                                                                console.error('[TEST CONNECTION] Error:', e)
                                                                setTestConnectionResult({ success: false, message: getErrorMessage(e, 'Connection test failed') })
                                                                setShowTestConnectionModal(true)
                                                                console.log('[TEST CONNECTION] Setting error modal')
                                                            }
                                                        }}
                                                    >
                                                        Test Connection
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    </div>

                                    {/* Schedule Name & Description - Matches Manual Upload Form Style */}
                                    <div data-scheduler-form className="space-y-4 p-4 bg-[#0a1020] rounded border border-[#1f2a44]">
                                        <div className="grid grid-cols-2 gap-2">
                                            <div>
                                                <label className="text-xs text-text-secondary mb-1 block">Schedule Name *</label>
                                                <Input
                                                    value={schedulerName}
                                                    onChange={(e) => setSchedulerName(e.target.value)}
                                                    placeholder="e.g. Daily NSE Symbols"
                                                    className="text-sm"
                                                />
                                            </div>
                                            <div>
                                                <label className="text-xs text-text-secondary mb-1 block">Description (Optional)</label>
                                                <Input
                                                    value={schedulerDescription}
                                                    onChange={(e) => setSchedulerDescription(e.target.value)}
                                                    placeholder="Optional description"
                                                    className="text-sm"
                                                />
                                            </div>
                                        </div>
                                    </div>


                                    {/* Transformation Script Toggle - EXACTLY matches Manual Upload */}
                                    <div className="flex items-center gap-3 p-3 bg-[#0a1020] rounded border border-[#1f2a44]">
                                        <input
                                            type="checkbox"
                                            id="enable-transformation-auto"
                                            checked={enableTransformation}
                                            onChange={(e) => {
                                                setEnableTransformation(e.target.checked)
                                                if (!e.target.checked) {
                                                    setSelectedScriptId('')
                                                    setEditingScriptId(null)
                                                }
                                            }}
                                            className="w-4 h-4 text-primary bg-[#0a1020] border-[#1f2a44] rounded focus:ring-primary"
                                        />
                                        <label htmlFor="enable-transformation-auto" className="text-sm text-text-primary cursor-pointer">
                                            Enable Transformation Script
                                        </label>
                                    </div>

                                    {/* Transformation Script Panel - EXACTLY matches Manual Upload */}
                                    {enableTransformation && (
                                        <div className="space-y-4 p-4 bg-[#0a1020] rounded border border-[#1f2a44]">
                                            <div className="flex items-center justify-between">
                                                <h3 className="text-sm font-semibold text-text-primary">Transformation Script</h3>
                                                <div className="flex gap-2">
                                                    <select
                                                        className="bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-1.5 text-xs text-text-primary focus:outline-none focus:border-primary"
                                                        value={selectedScriptId}
                                                        onChange={(e) => handleSelectScript(e.target.value)}
                                                    >
                                                        <option value="">New Script</option>
                                                        {scripts.map(s => (
                                                            <option key={s.id} value={s.id.toString()}>{s.name} (v{s.version})</option>
                                                        ))}
                                                    </select>
                                                    {selectedScriptId && (
                                                        <>
                                                            <Button
                                                                type="button"
                                                                variant="ghost"
                                                                size="sm"
                                                                onClick={(e) => {
                                                                    e.preventDefault()
                                                                    e.stopPropagation()
                                                                    console.log('[DELETE BUTTON] Clicked, selectedScriptId:', selectedScriptId)
                                                                    const scriptId = parseInt(selectedScriptId)
                                                                    console.log('[DELETE BUTTON] Parsed scriptId:', scriptId)
                                                                    if (!isNaN(scriptId) && scriptId > 0) {
                                                                        console.log('[DELETE BUTTON] Calling handleDeleteScript with:', scriptId)
                                                                        handleDeleteScript(scriptId)
                                                                    } else {
                                                                        console.error('[DELETE BUTTON] Invalid scriptId:', scriptId, 'from selectedScriptId:', selectedScriptId)
                                                                    }
                                                                }}
                                                                className="text-xs text-danger hover:text-danger"
                                                                title="Delete script"
                                                            >
                                                                <Trash2 className="w-3 h-3 mr-1" />
                                                                Delete
                                                            </Button>
                                                        </>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-2 gap-2">
                                                <div>
                                                    <label className="text-xs text-text-secondary mb-1 block">Script Name</label>
                                                    <Input
                                                        value={scriptName}
                                                        onChange={(e) => setScriptName(e.target.value)}
                                                        placeholder="e.g. NSE Normalizer"
                                                        className="text-sm"
                                                    />
                                                </div>
                                                <div>
                                                    <label className="text-xs text-text-secondary mb-1 block">Description (Optional)</label>
                                                    <Input
                                                        value={scriptDescription}
                                                        onChange={(e) => setScriptDescription(e.target.value)}
                                                        placeholder="Optional description"
                                                        className="text-sm"
                                                    />
                                                </div>
                                            </div>

                                            <div className="flex flex-col">
                                                <label className="text-xs text-text-secondary mb-1">Python Code</label>
                                                <textarea
                                                    className="flex-1 min-h-[300px] bg-[#0a1020] border border-[#1f2a44] rounded p-4 font-mono text-sm text-gray-300 focus:outline-none focus:border-primary resize-none"
                                                    value={scriptContent}
                                                    onChange={(e) => setScriptContent(e.target.value)}
                                                    spellCheck={false}
                                                    placeholder="# Input: df (pandas DataFrame)&#10;# Output: final_df (pandas DataFrame)&#10;&#10;import pandas as pd&#10;&#10;df['symbol'] = df['symbol'].str.upper()&#10;final_df = df"
                                                />
                                            </div>

                                            {!backendHealthy && (
                                                <div className="p-2 bg-yellow-500/10 border border-yellow-500/20 rounded mb-2">
                                                    <p className="text-yellow-500 text-xs">
                                                        ⚠️ Backend server is not reachable. Script saving is disabled. Please ensure the backend is running.
                                                    </p>
                                                </div>
                                            )}

                                            {scriptError && (
                                                <div className="p-2 bg-red-500/10 border border-red-500/20 rounded mb-2">
                                                    <p className="text-error text-xs">{scriptError}</p>
                                                </div>
                                            )}

                                            <div className="flex gap-2 justify-end">
                                                <Button
                                                    variant="secondary"
                                                    size="sm"
                                                    onClick={handleSaveAsNewScript}
                                                    disabled={!scriptName.trim() || savingScript || !backendHealthy}
                                                    title={!backendHealthy ? 'Backend server is not reachable' : ''}
                                                >
                                                    {savingScript ? 'Saving...' : 'Save As New'}
                                                </Button>
                                                <Button
                                                    size="sm"
                                                    onClick={handleSaveScript}
                                                    disabled={!scriptName.trim() || savingScript || !backendHealthy}
                                                    title={!backendHealthy ? 'Backend server is not reachable' : ''}
                                                >
                                                    {savingScript ? 'Saving...' : editingScriptId ? 'Update Script' : 'Save Script'}
                                                </Button>
                                            </div>
                                            
                                            {/* Edit Current Script Section - appears when a script is selected */}
                                            {selectedScriptId && editingScriptId && (
                                                <div className="mt-4 pt-4 border-t border-[#1f2a44]">
                                                    <div className="flex items-center justify-between mb-2">
                                                        <span className="text-xs text-text-secondary">Editing: {scriptName}</span>
                                                        <Button
                                                            variant="ghost"
                                                            size="sm"
                                                            onClick={(e) => {
                                                                e.preventDefault()
                                                                e.stopPropagation()
                                                                handleSelectScript(selectedScriptId) // Reload script
                                                            }}
                                                            className="text-xs text-info hover:text-info"
                                                            title="Reload script from database"
                                                        >
                                                            <RefreshCw className="w-3 h-3 mr-1" />
                                                            Reload
                                                        </Button>
                                                    </div>
                                                    <p className="text-xs text-text-secondary mb-2">
                                                        Make changes above and click "Update Script" to save changes to the current script.
                                                    </p>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Schedule Timer Section - Matches Manual Upload Card Style */}
                                    <div className="space-y-4 p-4 bg-[#0a1020] rounded border border-[#1f2a44]">
                                        <h3 className="text-sm font-semibold text-text-primary mb-3">Schedule Timer</h3>

                                        <div>
                                            <label className="text-xs text-text-secondary mb-1 block">Schedule Type *</label>
                                            <select
                                                className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                                value={schedulerMode}
                                                onChange={(e) => setSchedulerMode(e.target.value as any)}
                                            >
                                                <option value="RUN_ONCE">Run Once (Manual trigger only)</option>
                                                <option value="INTERVAL">Interval (Every X minutes/hours/days)</option>
                                                <option value="CRON">Cron Expression (Advanced)</option>
                                            </select>
                                        </div>

                                        {schedulerMode === 'INTERVAL' && (
                                            <div className="space-y-3">
                                                <div className="grid grid-cols-2 gap-2">
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">Interval Value *</label>
                                                        <Input
                                                            type="number"
                                                            value={intervalValue}
                                                            onChange={(e) => setIntervalValue(parseInt(e.target.value) || 1)}
                                                            min="1"
                                                            className="text-sm"
                                                        />
                                                    </div>
                                                    <div>
                                                        <label className="text-xs text-text-secondary mb-1 block">Interval Unit *</label>
                                                        <select
                                                            className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                                            value={intervalUnit}
                                                            onChange={(e) => setIntervalUnit(e.target.value as any)}
                                                        >
                                                            <option value="seconds">Seconds</option>
                                                            <option value="minutes">Minutes</option>
                                                            <option value="hours">Hours</option>
                                                            <option value="days">Days</option>
                                                        </select>
                                                    </div>
                                                </div>

                                                {/* Start Time */}
                                                <div>
                                                    <label className="text-xs text-text-secondary mb-1 block">Start Time (Optional)</label>
                                                    <div className="flex gap-2">
                                                        <Input
                                                            type="time"
                                                            value={startTime}
                                                            onChange={(e) => setStartTime(e.target.value)}
                                                            className="text-sm flex-1"
                                                        />
                                                        <select
                                                            className="bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                                            value={timeFormat}
                                                            onChange={(e) => setTimeFormat(e.target.value as '12h' | '24h')}
                                                        >
                                                            <option value="24h">24h</option>
                                                            <option value="12h">12h (AM/PM)</option>
                                                        </select>
                                                    </div>
                                                </div>

                                                {/* Timezone */}
                                                <div>
                                                    <label className="text-xs text-text-secondary mb-1 block">Timezone *</label>
                                                    <select
                                                        className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                                        value={timezone}
                                                        onChange={(e) => setTimezone(e.target.value)}
                                                    >
                                                        <option value="UTC">UTC</option>
                                                        <option value="America/New_York">America/New_York (EST/EDT)</option>
                                                        <option value="America/Chicago">America/Chicago (CST/CDT)</option>
                                                        <option value="America/Denver">America/Denver (MST/MDT)</option>
                                                        <option value="America/Los_Angeles">America/Los_Angeles (PST/PDT)</option>
                                                        <option value="Europe/London">Europe/London (GMT/BST)</option>
                                                        <option value="Europe/Paris">Europe/Paris (CET/CEST)</option>
                                                        <option value="Asia/Kolkata">Asia/Kolkata (IST)</option>
                                                        <option value="Asia/Tokyo">Asia/Tokyo (JST)</option>
                                                        <option value="Asia/Shanghai">Asia/Shanghai (CST)</option>
                                                        <option value="Australia/Sydney">Australia/Sydney (AEDT/AEST)</option>
                                                    </select>
                                                </div>
                                            </div>
                                        )}

                                        {schedulerMode === 'CRON' && (
                                            <div>
                                                <label className="text-xs text-text-secondary mb-1 block">Cron Expression *</label>
                                                <Input
                                                    value={cronExpression}
                                                    onChange={(e) => setCronExpression(e.target.value)}
                                                    placeholder="0 0 * * * (daily at midnight)"
                                                    className="text-sm"
                                                />
                                                <p className="text-xs text-text-secondary mt-1">
                                                    Format: minute hour day month weekday
                                                </p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Action Buttons - Matches Manual Upload */}
                                    <div className="flex justify-end items-center pt-4 border-t border-[#1f2a44]">
                                        <div className="flex gap-2">
                                            {selectedScheduler ? (
                                                <>
                                                    <Button variant="ghost" onClick={handleCancelEdit}>Cancel</Button>
                                                    <Button onClick={handleUpdateScheduler} disabled={!schedulerName.trim() || schedulerSources.length === 0 || !schedulerSources[0]?.url}>
                                                        Update Schedule
                                                    </Button>
                                                </>
                                            ) : (
                                                <Button onClick={handleCreateScheduler} disabled={!schedulerName.trim() || schedulerSources.length === 0 || !schedulerSources[0]?.url}>
                                                    Save Schedule
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                </div>

                                {/* Activity / Schedule Management Section - Matches Manual Upload Theme */}
                                <div className="bg-[#0a1020] rounded border border-[#1f2a44] p-6">
                                    <div className="flex items-center justify-between mb-4">
                                        <h4 className="text-sm font-semibold text-text-primary">Activity & Schedules</h4>
                                        <RefreshButton variant="ghost" size="sm" onClick={loadSchedulers} />
                                    </div>

                                    {schedulers.length === 0 ? (
                                        <div className="border border-[#1f2a44] rounded p-8 text-center">
                                            <p className="text-text-secondary">No schedules configured</p>
                                            <p className="text-xs text-text-secondary mt-2">Create a schedule above to get started</p>
                                        </div>
                                    ) : (
                                        <div className="overflow-x-auto border border-[#1f2a44] rounded">
                                            <Table>
                                                <TableHeader>
                                                    <TableHeaderCell>Schedule Name</TableHeaderCell>
                                                    <TableHeaderCell>Source Type</TableHeaderCell>
                                                    <TableHeaderCell>Frequency</TableHeaderCell>
                                                    <TableHeaderCell>Status</TableHeaderCell>
                                                    <TableHeaderCell>Last Run</TableHeaderCell>
                                                    <TableHeaderCell>Last Run Status</TableHeaderCell>
                                                    <TableHeaderCell>Next Run</TableHeaderCell>
                                                    <TableHeaderCell>Enabled</TableHeaderCell>
                                                    <TableHeaderCell>Actions</TableHeaderCell>
                                                </TableHeader>
                                                <TableBody>
                                                    {schedulers.map((scheduler: any) => {
                                                        const scheduleSummary = scheduler.mode === 'INTERVAL'
                                                            ? `Every ${scheduler.interval_value} ${scheduler.interval_unit}`
                                                            : scheduler.mode === 'CRON'
                                                                ? `Cron: ${scheduler.cron_expression}`
                                                                : 'One-time (Manual)'

                                                        const sourceUrl = scheduler.sources?.[0]?.url || 'N/A'
                                                        const sourceType = scheduler.sources?.[0]?.source_type || 'N/A'
                                                        const sourceTypeLabel = sourceType === 'DOWNLOADABLE_URL' ? 'URL' :
                                                            sourceType === 'API_ENDPOINT' ? 'API' :
                                                                sourceType

                                                        // SINGLE SOURCE OF TRUTH: Get status from API (from database)
                                                        // Current active status (running/queued if active, null if idle)
                                                        const currentStatus = scheduler.status || null
                                                        const isRunning = currentStatus === 'running' || currentStatus === 'queued'
                                                        
                                                        // Last Run timestamp (from database)
                                                        const lastRunAt = scheduler.last_run_at
                                                            ? new Date(scheduler.last_run_at).toLocaleString()
                                                            : '—'
                                                        
                                                        // Last Run Status (status of most recent run from database)
                                                        const lastRunStatus = scheduler.last_run_status || null
                                                        const lastRunStatusDisplay = lastRunStatus
                                                            ? (lastRunStatus === 'completed' || lastRunStatus === 'success' ? 'Completed' :
                                                                lastRunStatus === 'failed' ? 'Failed' :
                                                                lastRunStatus === 'crashed' ? 'Crashed' :
                                                                lastRunStatus === 'cancelled' ? 'Cancelled' :
                                                                lastRunStatus === 'running' ? 'Running' :
                                                                lastRunStatus === 'queued' ? 'Queued' :
                                                                lastRunStatus)
                                                            : 'Never run'

                                                        const nextRun = scheduler.next_run_at
                                                            ? new Date(scheduler.next_run_at).toLocaleString()
                                                            : 'Not scheduled'

                                                        return (
                                                            <TableRow key={scheduler.id}>
                                                                <TableCell className="font-medium text-text-primary">{scheduler.name}</TableCell>
                                                                <TableCell className="text-sm text-text-secondary">
                                                                    <span title={sourceUrl}>{sourceTypeLabel}</span>
                                                                </TableCell>
                                                                <TableCell className="text-sm text-text-secondary">{scheduleSummary}</TableCell>
                                                                {/* Status Column - Current Active Status (from database only) */}
                                                                <TableCell>
                                                                    {currentStatus ? (
                                                                        <span className={`text-xs px-2 py-1 rounded font-medium ${
                                                                            currentStatus === 'running' ? 'bg-primary/10 text-primary' :
                                                                            currentStatus === 'queued' ? 'bg-warning/10 text-warning' :
                                                                            'bg-gray-500/10 text-gray-500'
                                                                        }`}>
                                                                            {currentStatus === 'running' ? 'Running' : currentStatus === 'queued' ? 'Queued' : currentStatus}
                                                                        </span>
                                                                    ) : (
                                                                        <span className="text-xs px-2 py-1 rounded font-medium bg-gray-500/10 text-gray-500">
                                                                            -
                                                                        </span>
                                                                    )}
                                                                </TableCell>
                                                                {/* Last Run Column - Timestamp */}
                                                                <TableCell className="text-sm text-text-secondary">{lastRunAt}</TableCell>
                                                                {/* Last Run Status Column */}
                                                                <TableCell>
                                                                    <span className={`text-xs px-2 py-1 rounded font-medium ${
                                                                        lastRunStatusDisplay === 'Completed' ? 'bg-success/10 text-success' :
                                                                        lastRunStatusDisplay === 'Failed' || lastRunStatusDisplay === 'Crashed' ? 'bg-error/10 text-error' :
                                                                        lastRunStatusDisplay === 'Cancelled' ? 'bg-warning/10 text-warning' :
                                                                        lastRunStatusDisplay === 'Running' || lastRunStatusDisplay === 'Queued' ? 'bg-primary/10 text-primary' :
                                                                        'bg-gray-500/10 text-gray-500'
                                                                    }`}>
                                                                        {lastRunStatusDisplay}
                                                                    </span>
                                                                </TableCell>
                                                                <TableCell className="text-sm text-text-secondary">{nextRun}</TableCell>
                                                                <TableCell>
                                                                    <Switch
                                                                        checked={scheduler.is_active}
                                                                        onCheckedChange={() => handleToggleScheduler(scheduler.id)}
                                                                    />
                                                                </TableCell>
                                                                <TableCell>
                                                                    <div className="flex gap-2">
                                                                        <Button
                                                                            size="sm"
                                                                            variant="ghost"
                                                                            onClick={() => handleTriggerScheduler(scheduler.id)}
                                                                            title={isRunning ? "A run is already in progress" : "Run schedule now"}
                                                                            disabled={isRunning}
                                                                        >
                                                                            <Play className={`w-4 h-4 ${isRunning ? 'text-gray-500' : 'text-primary'}`} />
                                                                        </Button>
                                                                        <Button
                                                                            size="sm"
                                                                            variant="ghost"
                                                                            onClick={() => handleEditScheduler(scheduler)}
                                                                            title="Edit schedule"
                                                                        >
                                                                            <Edit className="w-4 h-4 text-text-secondary hover:text-primary" />
                                                                        </Button>
                                                                        <Button
                                                                            size="sm"
                                                                            variant="ghost"
                                                                            onClick={() => {
                                                                                handleDeleteScheduler(scheduler.id)
                                                                            }}
                                                                            title="Delete schedule"
                                                                            className="text-danger hover:text-danger"
                                                                        >
                                                                            <Trash2 className="w-4 h-4 text-danger" />
                                                                        </Button>
                                                                    </div>
                                                                </TableCell>
                                                            </TableRow>
                                                        )
                                                    })}
                                                </TableBody>
                                            </Table>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </>
                )}

                {/* Source Form Modal */}
                {showSourceForm && (
                    <SourceFormModal
                        source={editingSource}
                        onSave={handleSaveSource}
                        onCancel={() => {
                            setShowSourceForm(false)
                            setEditingSource(null)
                        }}
                    />
                )}

                {(error || autoError) && (
                    <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded">
                        <p className="text-error text-sm text-center">{activeTab === 'manual' ? error : autoError}</p>
                    </div>
                )}
                </div>
                </div>
            </div>

            {/* Delete Confirmation Popup */}
            {showDeleteConfirm && scriptToDelete && (
                <SecondaryModal
                    isOpen={showDeleteConfirm}
                    onClose={() => {
                        setShowDeleteConfirm(false)
                        setScriptToDelete(null)
                    }}
                    title="Delete Script"
                    maxWidth="max-w-md"
                >
                        <p className="text-text-secondary mb-6">
                            Are you sure you want to delete this script? This action cannot be undone.
                        </p>
                        <div className="flex gap-2 justify-end">
                            <Button
                                type="button"
                                variant="secondary"
                                size="sm"
                                onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    console.log('[DELETE CONFIRM] Cancel clicked')
                                    setShowDeleteConfirm(false)
                                    setScriptToDelete(null)
                                }}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="button"
                                variant="danger"
                                size="sm"
                                onClick={(e) => {
                                    e.preventDefault()
                                    e.stopPropagation()
                                    console.log('[DELETE CONFIRM] Delete confirmed, scriptId:', scriptToDelete)
                                    confirmDeleteScript()
                                }}
                            >
                                Delete
                            </Button>
                        </div>
                </SecondaryModal>
            )}

            {/* Error Popup */}
            {showErrorPopup && (
                <SecondaryModal
                    isOpen={showErrorPopup}
                    onClose={() => {
                        setShowErrorPopup(false)
                        setErrorPopupMessage('')
                    }}
                    title="Error"
                    maxWidth="max-w-md"
                >
                        <p className="text-text-secondary mb-6 whitespace-pre-wrap">
                            {errorPopupMessage}
                        </p>
                        <div className="flex justify-end">
                            <Button
                                size="sm"
                                onClick={() => {
                                    setShowErrorPopup(false)
                                    setErrorPopupMessage('')
                                }}
                            >
                                OK
                            </Button>
                        </div>
                </SecondaryModal>
            )}

        </div>
        )}
        
        {/* Test Connection Result Modal - Outside main modal so it can show even when main modal is open */}
        {showTestConnectionModal && testConnectionResult && (
            <SecondaryModal
                isOpen={showTestConnectionModal}
                onClose={() => {
                    setShowTestConnectionModal(false)
                    setTestConnectionResult(null)
                }}
                title={testConnectionResult.success ? 'Connection Successful' : 'Connection Failed'}
                maxWidth="max-w-md"
            >
                <div className="flex items-start gap-4 mb-6">
                    {testConnectionResult.success ? (
                        <div className="flex-shrink-0 w-12 h-12 rounded-full bg-success/20 flex items-center justify-center">
                            <svg className="w-7 h-7 text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                    ) : (
                        <div className="flex-shrink-0 w-12 h-12 rounded-full bg-error/20 flex items-center justify-center">
                            <svg className="w-7 h-7 text-error" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                            </svg>
                        </div>
                    )}
                    <div className="flex-1 pt-1">
                        <p className="text-text-secondary whitespace-pre-wrap">
                            {testConnectionResult.message}
                        </p>
                    </div>
                </div>
                <div className="flex justify-end">
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                            setShowTestConnectionModal(false)
                            setTestConnectionResult(null)
                        }}
                    >
                        OK
                    </Button>
                </div>
            </SecondaryModal>
        )}

        {/* Delete Scheduler Confirmation Modal */}
        {showDeleteSchedulerConfirm && schedulerToDelete && (
            <SecondaryModal
                isOpen={showDeleteSchedulerConfirm}
                onClose={() => {
                    setShowDeleteSchedulerConfirm(false)
                    setSchedulerToDelete(null)
                }}
                title="Delete Scheduler"
                maxWidth="max-w-md"
            >
                <div className="mb-6">
                    <p className="text-text-secondary mb-4">
                        Are you sure you want to delete scheduler <span className="font-semibold text-text">"{schedulerToDelete.name}"</span>?
                    </p>
                    <p className="text-text-secondary text-sm">
                        This will cancel future runs but will not delete past status history.
                    </p>
                </div>
                <div className="flex gap-2 justify-end">
                    <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => {
                            setShowDeleteSchedulerConfirm(false)
                            setSchedulerToDelete(null)
                        }}
                    >
                        Cancel
                    </Button>
                    <Button
                        variant="danger"
                        size="sm"
                        onClick={confirmDeleteScheduler}
                    >
                        Delete
                    </Button>
                </div>
            </SecondaryModal>
        )}
        
        {/* Render background upload popup even when main modal is closed */}
        {showBackgroundUploadPopup && backgroundUploadPopup}
        </>
    )
}

// Scheduler Card Component
function SchedulerCard({ scheduler, onTrigger, onEdit, onDelete }: {
    scheduler: any,
    onTrigger: () => void,
    onEdit: () => void,
    onDelete: () => void
}) {
    const enabledSources = (scheduler.sources || []).filter((s: any) => s.is_enabled !== false)
    const disabledSources = (scheduler.sources || []).filter((s: any) => s.is_enabled === false)

    return (
        <div className="p-4 bg-[#0a1020] rounded-lg border border-[#1f2a44]">
            <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                        <h4 className="text-sm font-semibold text-text-primary">{scheduler.name}</h4>
                        <span className={`text-[10px] px-1.5 py-0.5 rounded ${scheduler.is_active
                            ? 'bg-success/10 text-success'
                            : 'bg-gray-500/10 text-gray-500'
                            }`}>
                            {scheduler.is_active ? 'Active' : 'Inactive'}
                        </span>
                    </div>
                    {scheduler.description && (
                        <p className="text-xs text-text-secondary mb-2">{scheduler.description}</p>
                    )}
                    <div className="text-xs text-text-secondary space-y-0.5">
                        <div>
                            <span className="font-medium">Schedule:</span>{' '}
                            {scheduler.mode === 'INTERVAL' && `Every ${scheduler.interval_value} ${scheduler.interval_unit}`}
                            {scheduler.mode === 'CRON' && `Cron: ${scheduler.cron_expression}`}
                            {scheduler.mode === 'RUN_ONCE' && 'Run Once (Manual)'}
                        </div>
                        {scheduler.last_run_at && (
                            <div>
                                <span className="font-medium">Last run:</span>{' '}
                                {new Date(scheduler.last_run_at).toLocaleString()}
                            </div>
                        )}
                        {scheduler.next_run_at && (
                            <div>
                                <span className="font-medium">Next run:</span>{' '}
                                {new Date(scheduler.next_run_at).toLocaleString()}
                            </div>
                        )}
                        <div>
                            <span className="font-medium">Sources:</span>{' '}
                            {enabledSources.length} enabled, {disabledSources.length} disabled
                        </div>
                    </div>
                </div>
                <div className="flex gap-2 flex-shrink-0">
                    <Button size="sm" variant="secondary" onClick={onTrigger} title="Run scheduler now">
                        Run Now
                    </Button>
                    <Button size="sm" variant="ghost" onClick={onDelete} title="Delete scheduler">
                        Delete
                    </Button>
                </div>
            </div>

            {/* Sources List */}
            {scheduler.sources && scheduler.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[#1f2a44]">
                    <div className="text-xs font-medium text-text-secondary mb-2">Sources:</div>
                    <div className="space-y-1">
                        {scheduler.sources.map((source: any, idx: number) => (
                            <div key={source.id || idx} className="flex items-center justify-between text-xs">
                                <div className="flex items-center gap-2">
                                    <span className={`w-2 h-2 rounded-full ${source.is_enabled !== false ? 'bg-success' : 'bg-gray-500'
                                        }`}></span>
                                    <span className="text-text-primary">{source.name}</span>
                                    <span className="text-text-secondary">({source.source_type === 'DOWNLOADABLE_URL' ? 'File' : 'API'})</span>
                                </div>
                                {source.last_status && (
                                    <span className={`text-[10px] ${source.last_status === 'SUCCESS' ? 'text-success' :
                                        source.last_status === 'FAILED' ? 'text-error' :
                                            'text-warning'
                                        }`}>
                                        {source.last_status}
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    )
}

// Source Form Modal Component
function SourceFormModal({ source, onSave, onCancel }: { source: any, onSave: (data: any) => void, onCancel: () => void }) {
    const [name, setName] = useState(source?.name || '')
    const [sourceType, setSourceType] = useState<'DOWNLOADABLE_URL' | 'API_ENDPOINT'>(source?.source_type || 'DOWNLOADABLE_URL')
    const [url, setUrl] = useState(source?.url || '')
    const [headers, setHeaders] = useState<Record<string, string>>(source?.headers ? (typeof source.headers === 'string' ? JSON.parse(source.headers) : source.headers) : {})
    const [authType, setAuthType] = useState<'token' | 'key' | 'basic' | ''>(source?.auth_type || '')
    const [authValue, setAuthValue] = useState(source?.auth_value || '')
    const [isEnabled, setIsEnabled] = useState(source?.is_enabled !== false)
    const [headerKey, setHeaderKey] = useState('')
    const [headerValue, setHeaderValue] = useState('')

    const handleAddHeader = () => {
        if (headerKey && headerValue) {
            setHeaders({ ...headers, [headerKey]: headerValue })
            setHeaderKey('')
            setHeaderValue('')
        }
    }

    const handleRemoveHeader = (key: string) => {
        const newHeaders = { ...headers }
        delete newHeaders[key]
        setHeaders(newHeaders)
    }

    const handleSave = () => {
        if (!name.trim() || !url.trim()) {
            return
        }
        onSave({
            name,
            source_type: sourceType,
            url,
            headers: Object.keys(headers).length > 0 ? headers : undefined,
            auth_type: authType || undefined,
            auth_value: authValue || undefined,
            is_enabled: isEnabled
        })
    }

    return (
        <>
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-[#0f1623] border border-[#1f2a44] rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                <h3 className="text-lg font-bold text-text-primary mb-4">
                    {source ? 'Edit Source' : 'Add Source'}
                </h3>

                <div className="space-y-4">
                    <div>
                        <label className="text-xs text-text-secondary mb-1 block">Source Name</label>
                        <Input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="e.g. NSE Symbols API"
                        />
                    </div>

                    <div>
                        <label className="text-xs text-text-secondary mb-1 block">Source Type</label>
                        <select
                            className="w-full bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                            value={sourceType}
                            onChange={(e) => setSourceType(e.target.value as any)}
                        >
                            <option value="DOWNLOADABLE_URL">Downloadable URL (File)</option>
                            <option value="API_ENDPOINT">API Endpoint (JSON/Stream)</option>
                        </select>
                    </div>

                    <div>
                        <label className="text-xs text-text-secondary mb-1 block">URL / Endpoint</label>
                        <Input
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="https://api.example.com/symbols.csv"
                        />
                    </div>

                    <div>
                        <label className="text-xs text-text-secondary mb-1 block">Headers (Optional)</label>
                        <div className="flex gap-2 mb-2">
                            <Input
                                value={headerKey}
                                onChange={(e) => setHeaderKey(e.target.value)}
                                placeholder="Header Key"
                                className="flex-1"
                            />
                            <Input
                                value={headerValue}
                                onChange={(e) => setHeaderValue(e.target.value)}
                                placeholder="Header Value"
                                className="flex-1"
                            />
                            <Button size="sm" onClick={handleAddHeader}>Add</Button>
                        </div>
                        {Object.keys(headers).length > 0 && (
                            <div className="space-y-1">
                                {Object.entries(headers).map(([key, value]) => (
                                    <div key={key} className="flex items-center justify-between p-2 bg-[#0a1020] rounded">
                                        <span className="text-xs text-text-primary">{key}: {value}</span>
                                        <Button size="sm" variant="ghost" onClick={() => handleRemoveHeader(key)}>Remove</Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <div>
                        <label className="text-xs text-text-secondary mb-1 block">Authentication (Optional)</label>
                        <div className="grid grid-cols-2 gap-2">
                            <select
                                className="bg-[#121b2f] border border-[#1f2a44] rounded px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-primary"
                                value={authType}
                                onChange={(e) => setAuthType(e.target.value as any)}
                            >
                                <option value="">None</option>
                                <option value="token">Bearer Token</option>
                                <option value="key">API Key</option>
                                <option value="basic">Basic Auth</option>
                            </select>
                            {authType && (
                                <Input
                                    value={authValue}
                                    onChange={(e) => setAuthValue(e.target.value)}
                                    placeholder={authType === 'token' ? 'Token' : authType === 'key' ? 'API Key' : 'username:password'}
                                    type={authType === 'basic' ? 'text' : 'password'}
                                />
                            )}
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <input
                            type="checkbox"
                            id="source-enabled"
                            checked={isEnabled}
                            onChange={(e) => setIsEnabled(e.target.checked)}
                            className="w-4 h-4 text-primary bg-[#0a1020] border-[#1f2a44] rounded focus:ring-primary"
                        />
                        <label htmlFor="source-enabled" className="text-xs text-text-primary cursor-pointer">
                            Enable this source
                        </label>
                    </div>
                </div>

                <div className="flex justify-end gap-2 mt-6">
                    <Button variant="secondary" onClick={onCancel}>Cancel</Button>
                    <Button onClick={handleSave} disabled={!name.trim() || !url.trim()}>Save</Button>
                </div>
            </div>
        </div>
        </>
    )
}
