'use client'

import { useState, useEffect } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { symbolsAPI } from '@/lib/api'
import { UploadSymbolModal } from '@/components/UploadSymbolModal'
import { UploadStatusModal } from '@/components/UploadStatusModal'
import { SecondaryModal } from '@/components/ui/Modal'
import { Trash2, Power, Play, RefreshCw, Search, ChevronLeft, ChevronRight, BarChart3, Upload, Clock, CheckCircle2, XCircle, AlertTriangle, AlertCircle, Loader2, X, ArrowLeft } from 'lucide-react'
import { RefreshButton } from '@/components/ui/RefreshButton'

export default function SymbolsPage() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const [symbols, setSymbols] = useState<any[]>([])
    const [stats, setStats] = useState<any>({ total: 0, active: 0, inactive: 0, last_upload: null })
    const [loading, setLoading] = useState(true)
    const [search, setSearch] = useState('')
    // Initialize status - will be set from most recent job
    const [currentStatus, setCurrentStatus] = useState<string>('Status')

    // Filters from query params (card click-through)
    const [statusFilter, setStatusFilter] = useState<string | null>(null)
    const [expiryFilter, setExpiryFilter] = useState<string | null>(null)
    const [sortBy, setSortBy] = useState<string | null>(null)

    // Pagination state
    const [page, setPage] = useState(1)
    const [pageSize, setPageSize] = useState(25)
    const [total, setTotal] = useState(0)
    const [totalPages, setTotalPages] = useState(1)

    // Modals
    const [isUploadOpen, setIsUploadOpen] = useState(false)
    const [isStatusOpen, setIsStatusOpen] = useState(false)
    const [uploadLogsRefreshTrigger, setUploadLogsRefreshTrigger] = useState(0) // Trigger to refresh upload logs
    const [isDeleteAllOpen, setIsDeleteAllOpen] = useState(false)
    const [deleteAllLoading, setDeleteAllLoading] = useState(false)
    const [deleteConfirmText, setDeleteConfirmText] = useState('')
    const [isBulkDeleteOpen, setIsBulkDeleteOpen] = useState(false)
    const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false)

    // Bulk Selection
    const [selectedIds, setSelectedIds] = useState<number[]>([])

    // Series lookup reload state
    const [reloadingSeries, setReloadingSeries] = useState(false)
    const [seriesReloadMessage, setSeriesReloadMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

    // Load current status - show most recent job status (all statuses, not just running)
    const loadCurrentStatus = async () => {
        try {
            // Fetch more logs to ensure we get the most recent status
            const response = await symbolsAPI.getUploadLogs(50, 1)
            
            if (!response) {
                setCurrentStatus('Status')
                return
            }
            
            const logs = Array.isArray(response.logs) ? response.logs : []
            
            if (logs.length === 0) {
                setCurrentStatus('Status')
                return
            }
            
            // Define active statuses (jobs that are currently running)
            const ACTIVE_STATUSES = ['QUEUED', 'RUNNING', 'PENDING']
            // Define terminal statuses (jobs that have finished)
            const TERMINAL_STATUSES = ['SUCCESS', 'COMPLETED', 'FAILED', 'CRASHED', 'INTERRUPTED', 'CANCELLED', 'PARTIAL', 'COMPLETED_WITH_WARNINGS', 'STOPPED']
            
            // Find active jobs (running, queued, processing)
            const activeJobs = logs.filter((log: any) => {
                if (!log || !log.status) return false
                const statusUpper = String(log.status).trim().toUpperCase()
                return ACTIVE_STATUSES.includes(statusUpper)
            })
            
            // Find terminal jobs (completed, crashed, interrupted, etc.)
            const terminalJobs = logs.filter((log: any) => {
                if (!log || !log.status) return false
                const statusUpper = String(log.status).trim().toUpperCase()
                return TERMINAL_STATUSES.includes(statusUpper)
            })
            
            let jobToShow: any = null
            
            // Priority 1: If there are active jobs, show the most recent active job
            if (activeJobs.length > 0) {
                // Sort by started_at (most recent first) or use first one
                jobToShow = activeJobs.sort((a: any, b: any) => {
                    const aTime = a.started_at ? new Date(a.started_at).getTime() : 0
                    const bTime = b.started_at ? new Date(b.started_at).getTime() : 0
                    return bTime - aTime
                })[0]
            } 
            // Priority 2: If no active jobs, show the most recent terminal job
            else if (terminalJobs.length > 0) {
                // Sort by ended_at or started_at (most recent first)
                jobToShow = terminalJobs.sort((a: any, b: any) => {
                    const aTime = a.ended_at ? new Date(a.ended_at).getTime() : (a.started_at ? new Date(a.started_at).getTime() : 0)
                    const bTime = b.ended_at ? new Date(b.ended_at).getTime() : (b.started_at ? new Date(b.started_at).getTime() : 0)
                    return bTime - aTime
                })[0]
            }
            // Priority 3: Fallback to first log if no categorized jobs
            else {
                jobToShow = logs[0]
            }
            
            if (jobToShow && jobToShow.status) {
                const statusUpper = String(jobToShow.status).trim().toUpperCase()
                
                // Map status to display name
                if (statusUpper === 'QUEUED') {
                    setCurrentStatus('Queued')
                } else if (statusUpper === 'RUNNING') {
                    setCurrentStatus('Running')
                } else if (statusUpper === 'PENDING') {
                    setCurrentStatus('Processing')
                } else if (statusUpper === 'SUCCESS' || statusUpper === 'COMPLETED') {
                    setCurrentStatus('Completed')
                } else if (statusUpper === 'FAILED') {
                    setCurrentStatus('Failed')
                } else if (statusUpper === 'CRASHED') {
                    setCurrentStatus('Crashed')
                } else if (statusUpper === 'INTERRUPTED') {
                    setCurrentStatus('Interrupted')
                } else if (statusUpper === 'CANCELLED') {
                    setCurrentStatus('Cancelled')
                } else if (statusUpper === 'PARTIAL') {
                    setCurrentStatus('Partial')
                } else if (statusUpper === 'COMPLETED_WITH_WARNINGS') {
                    setCurrentStatus('Completed (with warnings)')
                } else if (statusUpper === 'STOPPED') {
                    setCurrentStatus('Stopped')
                } else {
                    setCurrentStatus(jobToShow.status)
                }
            } else {
                setCurrentStatus('Status')
            }
        } catch (error) {
            console.error('Failed to load status:', error)
            setCurrentStatus('Status')
        }
    }

    // Reload series lookup data
    const handleReloadSeriesLookup = async () => {
        setReloadingSeries(true)
        setSeriesReloadMessage(null)
        try {
            const result = await symbolsAPI.reloadSeriesLookup(true)
            if (result.success) {
                const message = result.reloaded 
                    ? `Successfully reloaded ${result.entries_count || 0} series entries`
                    : result.message || 'Series lookup data is up to date'
                setSeriesReloadMessage({ type: 'success', text: message })
                // Reload symbols to show updated descriptions
                await loadData(false, false)
            } else {
                setSeriesReloadMessage({ type: 'error', text: result.message || 'Failed to reload series lookup data' })
            }
        } catch (error: any) {
            console.error('Failed to reload series lookup:', error)
            setSeriesReloadMessage({ 
                type: 'error', 
                text: error?.response?.data?.detail || error?.message || 'Failed to reload series lookup data' 
            })
        } finally {
            setReloadingSeries(false)
            // Auto-hide message after 5 seconds
            setTimeout(() => {
                setSeriesReloadMessage(null)
            }, 5000)
        }
    }

    // Load status on mount
    useEffect(() => {
        loadCurrentStatus()
        // NO auto-refresh - user must manually click Refresh button
    }, [])

    // Read filters from query params and load data when params change
    useEffect(() => {
        // Extract params inside useEffect to ensure we get fresh values
        const statusParam = searchParams.get('status')
        const expiryParam = searchParams.get('expiry')
        const sortByParam = searchParams.get('sort_by')
        const searchParamsString = searchParams.toString()

        console.log('Symbols page - Query params changed:', { 
            statusParam, 
            expiryParam, 
            sortByParam,
            searchParamsString,
            fullUrl: typeof window !== 'undefined' ? window.location.href : 'N/A'
        })

        const newStatusFilter = statusParam && ['ACTIVE', 'INACTIVE'].includes(statusParam.toUpperCase())
            ? statusParam.toUpperCase()
            : null
        const newExpiryFilter = expiryParam && ['today', 'skipped'].includes(expiryParam.toLowerCase())
            ? expiryParam.toLowerCase()
            : null
        const newSortBy = sortByParam || null

        // Update filter states
        setStatusFilter(newStatusFilter)
        setExpiryFilter(newExpiryFilter)
        setSortBy(newSortBy)

        // Load data with the appropriate filters
        const loadWithFilter = async () => {
            setLoading(true)
            setSelectedIds([])
            setSearch('')
            setPage(1)
            setPageSize(25)
            try {
                const params: any = { page_size: 25, page: 1 }
                if (newStatusFilter) {
                    params.status = newStatusFilter
                }
                if (newExpiryFilter) {
                    params.expiry = newExpiryFilter
                }
                if (newSortBy) {
                    params.sort_by = newSortBy
                }
                console.log('Loading symbols with params:', params)
                const [symData, statsData] = await Promise.all([
                    symbolsAPI.getSymbols(params),
                    symbolsAPI.getStats()
                ])
                console.log('Symbols API response:', {
                    items_count: symData.items?.length || 0,
                    total: symData.total || 0,
                    page: symData.page || 1,
                    sample_item: symData.items?.[0]
                })
                if (symData.items) {
                    setSymbols(symData.items)
                    setTotal(symData.total)
                    setTotalPages(symData.total_pages)
                    setPage(symData.page)
                } else {
                    console.warn('Unexpected API response format:', symData)
                    setSymbols(Array.isArray(symData) ? symData : [])
                }
                setStats(statsData)
            } catch (e) {
                console.error('Error loading symbols with filters:', e)
            } finally {
                setLoading(false)
            }
        }

        loadWithFilter()
    }, [searchParams])

    const loadData = async (resetPage: boolean = true, clearStatusFilter: boolean = false) => {
        setLoading(true)
        setSelectedIds([]) // clear selection
        if (resetPage) {
            setSearch('') // clear search input on refresh
            setPage(1) // reset to page 1
            setPageSize(25) // reset to default page size
        }
        if (clearStatusFilter) {
            setStatusFilter(null)
            setExpiryFilter(null)
            setSortBy(null)
            // Clear filters from URL
            router.push('/admin/symbols', { scroll: false })
        }
        try {
            const currentPage = resetPage ? 1 : page
            const currentPageSize = resetPage ? 25 : pageSize
            const params: any = { page_size: currentPageSize, page: currentPage }
            // Apply filters if present
            if (statusFilter && !clearStatusFilter) {
                params.status = statusFilter
            }
            if (expiryFilter && !clearStatusFilter) {
                params.expiry = expiryFilter
            }
            if (sortBy && !clearStatusFilter) {
                params.sort_by = sortBy
            }
            // Include search term if present (preserve search on refresh)
            if (!resetPage && search.trim()) {
                const searchTerms = parseSearchTerms(search)
                if (searchTerms.length > 0) {
                    params.search = searchTerms.join(';')
                }
            }
            console.log('Loading symbols with params:', params)
            const [symData, statsData] = await Promise.all([
                symbolsAPI.getSymbols(params),
                symbolsAPI.getStats()
            ])
            
            // Update current status after loading data
            await loadCurrentStatus()
            console.log('Symbols API response:', {
                has_items: !!symData.items,
                items_count: symData.items?.length || 0,
                total: symData.total || 0,
                page: symData.page || 1,
                total_pages: symData.total_pages || 1,
                sample_item: symData.items?.[0] ? {
                    id: symData.items[0].id,
                    exchange: symData.items[0].exchange,
                    trading_symbol: symData.items[0].trading_symbol,
                    name: symData.items[0].name,
                    status: symData.items[0].status,
                    all_keys: Object.keys(symData.items[0])
                } : null
            })
            // Handle paginated response
            if (symData.items) {
                setSymbols(symData.items)
                setTotal(symData.total || 0)
                setTotalPages(symData.total_pages || 1)
                // Always update page from response (handles cases where current page becomes invalid)
                setPage(symData.page || 1)
                console.log(`Loaded ${symData.items.length} symbols, total: ${symData.total}`)
            } else {
                // Fallback for non-paginated response
                console.warn('Unexpected API response format:', symData)
                const symbolsArray = Array.isArray(symData) ? symData : []
                setSymbols(symbolsArray)
                setTotal(symbolsArray.length)
                setTotalPages(1)
                console.log(`Fallback: Loaded ${symbolsArray.length} symbols as array`)
            }
            setStats(statsData)
        } catch (e: any) {
            console.error('Error loading symbols:', e)
            console.error('Error details:', {
                message: e?.message,
                response: e?.response?.data,
                status: e?.response?.status
            })
            // Handle specific error cases gracefully
            if (e?.response?.status === 503 && e?.response?.data?.detail?.includes('not initialized')) {
                // Symbols database not initialized - show empty state
                setSymbols([])
                setTotal(0)
                setTotalPages(1)
                // Don't show error - empty state is expected
            } else {
                // Other errors - show empty state but log error
            setSymbols([])
            setTotal(0)
            setTotalPages(1)
            }
        } finally {
            setLoading(false)
        }
    }

    // Load data with current pagination (for page changes) - SERVER-SIDE PAGINATION
    const loadPage = async (newPage: number, newPageSize?: number) => {
        if (newPage < 1) return

        const currentPageSize = newPageSize || pageSize
        setLoading(true)
        setSelectedIds([]) // clear selection on page change
        try {
            // Always send page_size and page to backend - triggers DB query
            const params: any = { page_size: currentPageSize, page: newPage }
            // Apply filters if present
            if (statusFilter) {
                params.status = statusFilter
            }
            if (expiryFilter) {
                params.expiry = expiryFilter
            }
            if (sortBy) {
                params.sort_by = sortBy
            }
            if (search.trim()) {
                params.search = search.trim()
            }

            // Single API call to fetch ONLY the current page data
            const symData = await symbolsAPI.getSymbols(params)
            if (symData.items) {
                setSymbols(symData.items)
                setTotal(symData.total)
                setTotalPages(symData.total_pages)
                setPage(symData.page)
                if (newPageSize) {
                    setPageSize(newPageSize)
                }
            }
        } catch (e) {
            console.error('Failed to load page:', e)
        } finally {
            setLoading(false)
        }
    }

    // Update search input value only (no API call)
    const handleSearchChange = (val: string) => {
        setSearch(val)
    }

    // Parse search input for semicolon-separated terms
    const parseSearchTerms = (input: string): string[] => {
        if (!input || !input.trim()) {
            return []
        }
        // Split by semicolon, trim, convert to lowercase, filter out empty strings
        return input
            .split(';')
            .map(term => term.trim().toLowerCase())
            .filter(term => term.length > 0)
    }

    // Execute search only on button click
    const handleSearchClick = async () => {
        setLoading(true)
        setSelectedIds([]) // clear selection
        setPage(1) // reset to page 1 on search (preserves page_size)
        try {
            const params: any = { page_size: pageSize, page: 1 }

            // Apply filters if present (search works with filters)
            if (statusFilter) {
                params.status = statusFilter
            }
            if (expiryFilter) {
                params.expiry = expiryFilter
            }
            if (sortBy) {
                params.sort_by = sortBy
            }

            const searchTerms = parseSearchTerms(search)
            // If search terms exist, add to params
            if (searchTerms.length > 0) {
                // Join terms with semicolon for backend combination search (AND logic)
                // Backend requires ALL terms to be present in the same row
                params.search = searchTerms.join(';')
            }
            // If no search terms, params.search is undefined - backend returns all (with pagination)

            // Single API call - server-side pagination with search
            const res = await symbolsAPI.getSymbols(params)
            console.log('Search response:', {
                items_count: res.items?.length || 0,
                total: res.total || 0,
                params
            })
            if (res.items) {
                setSymbols(res.items)
                setTotal(res.total)
                setTotalPages(res.total_pages)
                setPage(res.page)
            } else {
                console.warn('Unexpected API response format in search:', res)
                setSymbols(Array.isArray(res) ? res : [])
            }
        } catch (e) {
            console.error('Search failed:', e)
        } finally {
            setLoading(false)
        }
    }

    // Handle rows per page change
    const handlePageSizeChange = (newPageSize: number) => {
        setPage(1) // reset to page 1
        loadPage(1, newPageSize) // load with new page size
    }

    // Handle Enter key in search input
    const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter') {
            e.preventDefault()
            handleSearchClick()
        }
    }

    // Clear search and reset to default (unfiltered) state
    const handleClearSearch = async () => {
        setSearch('')
        setLoading(true)
        setSelectedIds([]) // clear selection
        setPage(1) // reset to page 1
        try {
            const params: any = { page_size: pageSize, page: 1 }
            // Apply filters if present (but no search)
            if (statusFilter) {
                params.status = statusFilter
            }
            if (expiryFilter) {
                params.expiry = expiryFilter
            }
            if (sortBy) {
                params.sort_by = sortBy
            }
            // No search param - backend returns all (with pagination)
            const res = await symbolsAPI.getSymbols(params)
            if (res.items) {
                setSymbols(res.items)
                setTotal(res.total)
                setTotalPages(res.total_pages)
                setPage(res.page)
            } else {
                setSymbols(Array.isArray(res) ? res : [])
            }
        } catch (e) {
            console.error('Clear search failed:', e)
        } finally {
            setLoading(false)
        }
    }

    // Bulk Logic
    const toggleSelectAll = () => {
        if (selectedIds.length === symbols.length && symbols.length > 0) {
            setSelectedIds([])
        } else {
            setSelectedIds(symbols.map(s => s.id))
        }
    }

    // Generate page numbers with ellipsis
    const getPageNumbers = () => {
        const pages: (number | string)[] = []
        const maxVisible = 5

        if (totalPages <= maxVisible) {
            // Show all pages if total is small
            for (let i = 1; i <= totalPages; i++) {
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
                pages.push(totalPages)
            } else if (page >= totalPages - 2) {
                // Near the end
                pages.push('ellipsis')
                for (let i = totalPages - 3; i <= totalPages; i++) {
                    pages.push(i)
                }
            } else {
                // In the middle
                pages.push('ellipsis')
                for (let i = page - 1; i <= page + 1; i++) {
                    pages.push(i)
                }
                pages.push('ellipsis')
                pages.push(totalPages)
            }
        }

        return pages
    }

    const toggleSelect = (id: number) => {
        if (selectedIds.includes(id)) {
            setSelectedIds(selectedIds.filter(i => i !== id))
        } else {
            setSelectedIds([...selectedIds, id])
        }
    }

    const handleBulkDelete = async () => {
        // Open the confirmation modal instead of using browser confirm
        setIsBulkDeleteOpen(true)
    }

    const confirmBulkDelete = async () => {
        try {
            setBulkDeleteLoading(true)
            await symbolsAPI.bulkDelete(selectedIds, true) // Hard delete - permanently remove
            setSelectedIds([]) // Clear selection
            setIsBulkDeleteOpen(false) // Close modal
            // Reload current page to reflect deletions
            loadPage(page, pageSize)
        } catch (e: any) {
            alert(`Delete operation failed: ${e?.response?.data?.detail || e.message || 'Unknown error'}`)
        } finally {
            setBulkDeleteLoading(false)
        }
    }

    const handleBulkStatus = async (status: string) => {
        const action = status === 'ACTIVE' ? 'activate' : 'deactivate'
        const confirmed = confirm(
            `Are you sure you want to ${action} ${selectedIds.length} symbol(s)?\n\nDeactivated symbols will remain visible in the table.`
        )
        if (!confirmed) return

        try {
            await symbolsAPI.bulkStatus(selectedIds, status)
            setSelectedIds([]) // Clear selection
            // Reload current page - rows stay visible, status badge updates
            loadPage(page, pageSize)
        } catch (e) {
            alert(`Failed to ${action} symbols`)
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <button
                    onClick={() => router.push('/admin/reference-data')}
                    className="text-text-secondary hover:text-text-primary transition-colors"
                >
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                    <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
                        Symbols Master
                    </h1>
                    <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
                        Manage tradable instruments and contracts
                    </p>
                </div>
            </div>

            <div className="flex items-center justify-between">
                <div></div>
                <div className="flex gap-2 items-center">
                    {/* 1️⃣ Refresh - FIRST */}
                    <RefreshButton
                        variant="secondary"
                        onClick={async () => {
                            try {
                                // Refresh without resetting page, search, or filters - just reload current state
                                await loadData(false, false)
                            } catch (error) {
                                console.error('Refresh failed:', error)
                            }
                        }}
                        size="sm"
                        disabled={loading}
                    />
                    {/* Series Lookup Reload Button */}
                    <Button
                        variant="secondary"
                        onClick={handleReloadSeriesLookup}
                        size="sm"
                        disabled={reloadingSeries || loading}
                        title="Reload series descriptions from CSV"
                    >
                        {reloadingSeries ? (
                            <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                        ) : (
                            <RefreshCw className="w-4 h-4 mr-1.5" />
                        )}
                        Reload Series
                    </Button>
                    {/* 2️⃣ Status Button - Shows "Status" text, icon changes based on job status */}
                    {(() => {
                        const statusValue = currentStatus
                        const statusUpper = String(statusValue).trim().toUpperCase()
                        
                        // Determine icon and color based on status (text always "Status")
                        let IconComponent = BarChart3
                        let iconColor = 'text-[#6b7280] dark:text-[#9ca3af]' // Default gray
                        
                        if (statusUpper === 'QUEUED') {
                            IconComponent = Loader2
                            iconColor = 'text-[#3b82f6] dark:text-[#60a5fa]'
                        } else if (statusUpper === 'RUNNING' || statusUpper === 'PROCESSING') {
                            IconComponent = Loader2
                            iconColor = 'text-[#3b82f6] dark:text-[#60a5fa]'
                        } else if (statusUpper === 'CANCELLED') {
                            IconComponent = AlertCircle
                            iconColor = 'text-[#f59e0b] dark:text-[#fbbf24]'
                        } else if (statusUpper === 'CRASHED') {
                            IconComponent = XCircle
                            iconColor = 'text-[#ef4444] dark:text-[#f87171]'
                        } else if (statusUpper === 'FAILED') {
                            IconComponent = XCircle
                            iconColor = 'text-[#ef4444] dark:text-[#f87171]'
                        } else if (statusUpper === 'INTERRUPTED') {
                            IconComponent = XCircle
                            iconColor = 'text-[#ef4444] dark:text-[#f87171]'
                        } else if (statusUpper === 'COMPLETED' || statusUpper === 'SUCCESS' || statusUpper.includes('COMPLETED')) {
                            IconComponent = CheckCircle2
                            iconColor = 'text-[#10b981] dark:text-[#34d399]'
                        } else if (statusUpper === 'PARTIAL') {
                            IconComponent = AlertCircle
                            iconColor = 'text-[#f59e0b] dark:text-[#fbbf24]'
                        } else if (statusUpper === 'STOPPED') {
                            IconComponent = AlertCircle
                            iconColor = 'text-[#f59e0b] dark:text-[#fbbf24]'
                        }
                        // Default: BarChart3 icon with gray color for "Status" or no jobs
                        
                        const isSpinning = statusUpper === 'RUNNING' || statusUpper === 'PROCESSING' || statusUpper === 'QUEUED'
                        
                        return (
                            <Button
                                variant="secondary"
                                onClick={() => setIsStatusOpen(true)}
                                size="sm"
                            >
                                <IconComponent 
                                    className={`w-4 h-4 mr-1.5 ${iconColor} ${isSpinning ? 'animate-spin' : ''}`} 
                                    aria-hidden="true"
                                />
                                Status
                            </Button>
                        )
                    })()}
                    {/* 3️⃣ Upload Symbols - THIRD */}
                    <Button
                        onClick={() => setIsUploadOpen(true)}
                        size="sm"
                    >
                        <Upload className="w-4 h-4 mr-1.5" />
                        Upload Symbols
                    </Button>
                    {/* 4️⃣ Delete All Symbols - DANGEROUS - Only for super admin */}
                    <Button
                        variant="danger"
                        onClick={() => setIsDeleteAllOpen(true)}
                        size="sm"
                    >
                        <Trash2 className="w-4 h-4 mr-1.5" />
                        Delete All
                    </Button>
                </div>
            </div>

            {/* Series Reload Message */}
            {seriesReloadMessage && (
                <div className={`mb-4 p-3 rounded-md flex items-center justify-between ${
                    seriesReloadMessage.type === 'success' 
                        ? 'bg-success/10 border border-success/20 text-success' 
                        : 'bg-error/10 border border-error/20 text-error'
                }`}>
                    <div className="flex items-center gap-2">
                        {seriesReloadMessage.type === 'success' ? (
                            <CheckCircle2 className="w-4 h-4" />
                        ) : (
                            <XCircle className="w-4 h-4" />
                        )}
                        <span className="text-sm">{seriesReloadMessage.text}</span>
                    </div>
                    <button
                        onClick={() => setSeriesReloadMessage(null)}
                        className="text-current opacity-70 hover:opacity-100"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>
            )}

            <Card>
                {/* Filter Indicator */}
                {(statusFilter || expiryFilter || sortBy) && (
                    <div className="mb-3 px-3 py-2 bg-primary/10 dark:bg-primary/20 border border-primary/30 rounded-md flex items-center justify-between">
                        <span className="text-xs font-medium text-text-secondary dark:text-[#9ca3af]">
                            {statusFilter && (
                                <>Filtered by: <span className="text-primary font-semibold">{statusFilter === 'ACTIVE' ? 'Active' : 'Inactive'} symbols</span></>
                            )}
                            {expiryFilter && (
                                <>Filtered by: <span className="text-primary font-semibold">
                                    {expiryFilter === 'today' ? 'Expiring Today' : 'Skipped Symbols'}
                                </span></>
                            )}
                            {sortBy && !statusFilter && !expiryFilter && (
                                <>Sorted by: <span className="text-primary font-semibold">Last Updated</span></>
                            )}
                        </span>
                        <button
                            onClick={() => {
                                setStatusFilter(null)
                                setExpiryFilter(null)
                                setSortBy(null)
                                router.push('/admin/symbols', { scroll: false })
                                loadData(true, true)
                            }}
                            className="text-xs text-text-secondary hover:text-text-primary transition-colors"
                        >
                            Clear filter
                        </button>
                    </div>
                )}

                <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
                    {/* Search Input and Button - Left Side */}
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                        <div className="flex-1 max-w-md">
                            <Input
                                placeholder="Search symbols (use ; for combined search)"
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

                    {/* Bulk Actions - Right Side (Inline with Search) */}
                    {selectedIds.length > 0 && (
                        <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-sm font-medium text-text-secondary whitespace-nowrap">{selectedIds.length} Selected</span>
                            <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => handleBulkStatus('ACTIVE')}
                                className="h-9"
                            >
                                Activate
                            </Button>
                            <Button
                                size="sm"
                                variant="secondary"
                                className="text-warning hover:bg-warning/20 h-9"
                                onClick={() => handleBulkStatus('INACTIVE')}
                            >
                                Deactivate
                            </Button>
                            <Button
                                size="sm"
                                variant="danger"
                                onClick={handleBulkDelete}
                                className="h-9"
                            >
                                <Trash2 className="w-4 h-4 mr-1" />
                                Delete
                            </Button>
                        </div>
                    )}
                </div>

                <div className="overflow-x-auto">
                    <Table>
                        <TableHeader>
                            <TableHeaderCell className="w-10">
                                <input type="checkbox"
                                    className="rounded border-gray-600 bg-transparent text-primary focus:ring-primary"
                                    checked={symbols.length > 0 && selectedIds.length === symbols.length}
                                    onChange={toggleSelectAll}
                                />
                            </TableHeaderCell>
                            <TableHeaderCell>Details</TableHeaderCell>
                            <TableHeaderCell>Symbol</TableHeaderCell>
                            <TableHeaderCell>Name</TableHeaderCell>
                            <TableHeaderCell>Type</TableHeaderCell>
                            <TableHeaderCell>Segment</TableHeaderCell>
                            <TableHeaderCell>Series</TableHeaderCell>
                            <TableHeaderCell>ISIN</TableHeaderCell>
                            <TableHeaderCell>Expiry</TableHeaderCell>
                            <TableHeaderCell>Strike</TableHeaderCell>
                            <TableHeaderCell>Lot</TableHeaderCell>
                            <TableHeaderCell>Source</TableHeaderCell>
                            <TableHeaderCell>Status</TableHeaderCell>
                            <TableHeaderCell>Last Updated</TableHeaderCell>
                        </TableHeader>
                        <TableBody>
                            {loading && symbols.length === 0 ? (
                                <TableRow>
                                    <td colSpan={14} className="px-3 py-12 text-center">
                                        <div className="flex flex-col items-center gap-2">
                                            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                                            <p className="text-text-secondary">Loading symbols...</p>
                                        </div>
                                    </td>
                                </TableRow>
                            ) : (
                                <>
                                    {symbols.map((sym, i) => (
                                        <TableRow key={sym.id || i} index={i} className={selectedIds.includes(sym.id) ? 'bg-primary/5' : ''}>
                                            <TableCell>
                                                <input type="checkbox"
                                                    className="rounded border-gray-600 bg-transparent text-primary focus:ring-primary"
                                                    checked={selectedIds.includes(sym.id)}
                                                    onChange={() => toggleSelect(sym.id)}
                                                />
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex flex-col">
                                                    <span className="font-bold text-xs">{sym.exchange || '-'}</span>
                                                    {sym.exchange_token && <span className="text-[10px] text-text-muted">{sym.exchange_token}</span>}
                                                </div>
                                            </TableCell>
                                            <TableCell className="font-mono text-xs text-primary">{sym.trading_symbol || '-'}</TableCell>
                                            <TableCell className="text-xs max-w-[150px] truncate">
                                                <span title={sym.name || ''}>{sym.name || '-'}</span>
                                            </TableCell>
                                            <TableCell className="text-xs">{sym.instrument_type || '-'}</TableCell>
                                            <TableCell className="text-xs text-text-secondary">{sym.segment || '-'}</TableCell>
                                            <TableCell>
                                                <div className="flex flex-col">
                                                    <span className="font-bold text-xs">{sym.series || '-'}</span>
                                                    {sym.series_description && <span className="text-[10px] text-text-muted">{sym.series_description}</span>}
                                                </div>
                                            </TableCell>
                                            <TableCell className="text-xs text-text-secondary font-mono">{sym.isin || '-'}</TableCell>
                                            <TableCell className="text-xs text-text-secondary">
                                                {sym.expiry_date ? (() => {
                                                    try {
                                                        const date = new Date(sym.expiry_date)
                                                        // Use a consistent format to avoid hydration mismatches
                                                        return date.toISOString().split('T')[0]
                                                    } catch {
                                                        return '-'
                                                    }
                                                })() : '-'}
                                            </TableCell>
                                            <TableCell className="text-xs text-text-secondary">
                                                {sym.strike_price != null ? sym.strike_price.toLocaleString() : '-'}
                                            </TableCell>
                                            <TableCell className="text-xs">{sym.lot_size != null ? sym.lot_size : '-'}</TableCell>
                                            <TableCell className="text-[10px] text-text-muted">{sym.source || 'MANUAL'}</TableCell>
                                            <TableCell>
                                                {(() => {
                                                    // Normalize status - ensure it's ACTIVE or INACTIVE
                                                    const rawStatus = sym.status || 'ACTIVE'
                                                    const statusUpper = String(rawStatus).trim().toUpperCase()
                                                    
                                                    // Map to valid status values
                                                    let normalizedStatus = 'ACTIVE'
                                                    if (statusUpper === 'INACTIVE') {
                                                        normalizedStatus = 'INACTIVE'
                                                    } else if (statusUpper === 'ACTIVE') {
                                                        normalizedStatus = 'ACTIVE'
                                                    } else {
                                                        // If status is something else, default to ACTIVE
                                                        normalizedStatus = 'ACTIVE'
                                                    }
                                                    
                                                    const isActive = normalizedStatus === 'ACTIVE'
                                                    
                                                    return (
                                                        <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded ${isActive ? 'bg-success/10 text-success' : 'bg-gray-500/10 text-gray-500'}`}>
                                                            {normalizedStatus}
                                                        </span>
                                                    )
                                                })()}
                                            </TableCell>
                                            <TableCell className="text-xs text-text-secondary">
                                                {sym.last_updated_at ? (() => {
                                                    try {
                                                        // Parse the timestamp - if it's UTC (from backend), JavaScript Date will handle it correctly
                                                        // The timestamp from API should be ISO format with timezone info
                                                        const date = new Date(sym.last_updated_at)
                                                        
                                                        // Format: YYYY-MM-DD HH:MM:SS in LOCAL timezone (converted from UTC)
                                                        // Date object automatically converts UTC to local time when formatting
                                                        const year = date.getFullYear()
                                                        const month = String(date.getMonth() + 1).padStart(2, '0')
                                                        const day = String(date.getDate()).padStart(2, '0')
                                                        const hours = String(date.getHours()).padStart(2, '0')  // Local hours
                                                        const minutes = String(date.getMinutes()).padStart(2, '0')
                                                        const seconds = String(date.getSeconds()).padStart(2, '0')
                                                        const formatted = `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
                                                        
                                                        // Show UTC time in tooltip for reference
                                                        return (
                                                            <span title={`UTC: ${date.toISOString()}\nLocal: ${formatted}`}>
                                                                {formatted}
                                                            </span>
                                                        )
                                                    } catch {
                                                        return '-'
                                                    }
                                                })() : (
                                                    sym.created_at ? (() => {
                                                        try {
                                                            const date = new Date(sym.created_at)
                                                            // Use consistent format: YYYY-MM-DD HH:MM (avoid hydration mismatch)
                                                            const year = date.getFullYear()
                                                            const month = String(date.getMonth() + 1).padStart(2, '0')
                                                            const day = String(date.getDate()).padStart(2, '0')
                                                            const hours = String(date.getHours()).padStart(2, '0')
                                                            const minutes = String(date.getMinutes()).padStart(2, '0')
                                                            const formatted = `${year}-${month}-${day} ${hours}:${minutes}`
                                                            return (
                                                                <span title={date.toISOString()}>
                                                                    {formatted}
                                                                </span>
                                                            )
                                                        } catch {
                                                            return '-'
                                                        }
                                                    })() : '-'
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                    {symbols.length === 0 && !loading && (
                                        <TableRow>
                                            <td colSpan={14} className="px-3 py-12 text-center">
                                                <div className="flex flex-col items-center gap-2">
                                                    <p className="text-text-secondary">No symbols found</p>
                                                    <Button variant="secondary" size="sm" onClick={() => setIsUploadOpen(true)}>
                                                        Upload Symbols
                                                    </Button>
                                                </div>
                                            </td>
                                        </TableRow>
                                    )}
                                </>
                            )}
                        </TableBody>
                    </Table>
                </div>

                {/* Pagination Controls */}
                <div className="mt-4 pt-4 border-t border-border flex items-center justify-between flex-wrap gap-4">
                    {/* Rows per page selector */}
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-text-secondary">Rows per page:</span>
                        <select
                            value={pageSize}
                            onChange={(e) => handlePageSizeChange(Number(e.target.value))}
                            className="px-2 py-1 text-sm border border-border rounded bg-background text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                            disabled={loading}
                        >
                            <option value={10}>10</option>
                            <option value={25}>25</option>
                            <option value={50}>50</option>
                            <option value={100}>100</option>
                        </select>
                    </div>

                    {/* Page navigation */}
                    <div className="flex items-center gap-1">
                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => loadPage(page - 1)}
                            disabled={loading || page === 1}
                            className="px-2"
                        >
                            <ChevronLeft className="w-4 h-4" />
                            Previous
                        </Button>

                        {/* Page numbers */}
                        {getPageNumbers().map((pageNum, idx) => {
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
                                    onClick={() => loadPage(pageNumValue)}
                                    disabled={loading}
                                    className="min-w-[2rem] px-2"
                                >
                                    {pageNumValue}
                                </Button>
                            )
                        })}

                        <Button
                            variant="secondary"
                            size="sm"
                            onClick={() => loadPage(page + 1)}
                            disabled={loading || page === totalPages}
                            className="px-2"
                        >
                            Next
                            <ChevronRight className="w-4 h-4" />
                        </Button>
                    </div>

                    {/* Page summary */}
                    <div className="text-sm text-text-secondary">
                        {total > 0 ? (
                            <>
                                Showing{' '}
                                <span className="font-semibold text-text-primary">
                                    {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, total)}
                                </span>{' '}
                                of{' '}
                                <span className="font-semibold text-text-primary">
                                    {total.toLocaleString()}
                                </span>{' '}
                                symbols
                            </>
                        ) : (
                            'No symbols found'
                        )}
                    </div>
                </div>
            </Card>

            <UploadSymbolModal
                isOpen={isUploadOpen}
                onClose={() => {
                    setIsUploadOpen(false)
                    // Don't refresh here - onSuccess will handle it once when upload completes
                    // This prevents duplicate refreshes
                }}
                onSuccess={async () => {
                    // Refresh the symbols table after successful upload - ONLY ONCE
                    console.log('Upload successful, refreshing symbols table once...')
                    // Add a small delay to ensure backend has committed all data
                    await new Promise(resolve => setTimeout(resolve, 1500))
                    // Force refresh - go to page 1 to see newly uploaded symbols
                    await loadData(true, false)
                    console.log('Symbols table refreshed once')
                    
                    // Trigger upload logs refresh immediately when upload status becomes finished
                    // Refresh happens as soon as status is SUCCESS/PARTIAL/FAILED - no delays
                    console.log('Triggering upload logs refresh immediately after upload completion...')
                    setUploadLogsRefreshTrigger(prev => prev + 1)
                    
                    // Second refresh after a short delay to ensure we get the latest entry
                    setTimeout(() => {
                        console.log('Triggering second upload logs refresh...')
                        setUploadLogsRefreshTrigger(prev => prev + 1)
                    }, 2000)
                }}
            />

            <UploadStatusModal
                isOpen={isStatusOpen}
                onClose={() => setIsStatusOpen(false)}
                refreshTrigger={uploadLogsRefreshTrigger}
            />

            {/* Bulk Delete Confirmation Modal */}
            <SecondaryModal
                isOpen={isBulkDeleteOpen}
                onClose={() => {
                    if (!bulkDeleteLoading) {
                        setIsBulkDeleteOpen(false)
                    }
                }}
                title=""
                maxWidth="max-w-md"
                closeOnBackdropClick={!bulkDeleteLoading}
            >
                <div className="space-y-4">
                    {/* Warning Icon and Header */}
                    <div className="flex items-start gap-4">
                        <div className="flex-shrink-0">
                            <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                                <AlertTriangle className="w-6 h-6 text-red-500" />
                            </div>
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-semibold text-[#e5e7eb] mb-2">
                                Delete {selectedIds.length} Symbol{selectedIds.length !== 1 ? 's' : ''}
                            </h3>
                            <p className="text-sm text-[#9ca3af]">
                                This action will permanently delete <strong className="text-[#e5e7eb]">{selectedIds.length} selected symbol{selectedIds.length !== 1 ? 's' : ''}</strong> from the database.
                            </p>
                        </div>
                    </div>

                    {/* Warning Message */}
                    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                        <div className="flex items-start gap-3">
                            <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="text-sm font-semibold text-red-400 mb-1">
                                    This action cannot be undone!
                                </p>
                                <p className="text-xs text-[#9ca3af]">
                                    All deleted symbols and their data cannot be returned. This is a permanent deletion.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 justify-end pt-2">
                        <Button
                            variant="secondary"
                            onClick={() => {
                                if (!bulkDeleteLoading) {
                                    setIsBulkDeleteOpen(false)
                                }
                            }}
                            disabled={bulkDeleteLoading}
                            size="sm"
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="danger"
                            onClick={confirmBulkDelete}
                            disabled={bulkDeleteLoading}
                            size="sm"
                        >
                            {bulkDeleteLoading ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                                    Deleting...
                                </>
                            ) : (
                                <>
                                    <Trash2 className="w-4 h-4 mr-1.5" />
                                    Delete {selectedIds.length} Symbol{selectedIds.length !== 1 ? 's' : ''}
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </SecondaryModal>

            {/* Delete All Symbols Confirmation Modal */}
            <SecondaryModal
                isOpen={isDeleteAllOpen}
                onClose={() => {
                    setIsDeleteAllOpen(false)
                    setDeleteConfirmText('')
                }}
                title=""
                maxWidth="max-w-md"
            >
                <div className="space-y-4">
                    {/* Warning Icon and Header */}
                    <div className="flex items-start gap-4">
                        <div className="flex-shrink-0">
                            <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                                <AlertTriangle className="w-6 h-6 text-red-500" />
                            </div>
                        </div>
                        <div className="flex-1">
                            <h3 className="text-lg font-semibold text-[#e5e7eb] mb-2">
                                Delete All Symbols
                            </h3>
                            <p className="text-sm text-[#9ca3af]">
                                This action will permanently delete <strong className="text-[#e5e7eb]">ALL symbols</strong> and upload history from the database.
                            </p>
                        </div>
                    </div>

                    {/* Warning Message */}
                    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                        <div className="flex items-start gap-3">
                            <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                            <div>
                                <p className="text-sm font-semibold text-red-400 mb-1">
                                    This action cannot be undone!
                                </p>
                                <p className="text-xs text-[#9ca3af]">
                                    All deleted symbols and their data cannot be returned. This is a permanent deletion.
                                </p>
                            </div>
                        </div>
                    </div>

                    {/* Confirmation Input */}
                    <div>
                        <label className="block text-sm font-medium text-[#9ca3af] mb-2">
                            Type <span className="font-mono text-red-400">DELETE</span> to confirm:
                        </label>
                        <Input
                            type="text"
                            value={deleteConfirmText}
                            onChange={(e) => setDeleteConfirmText(e.target.value)}
                            placeholder="Type DELETE to confirm"
                            className="w-full"
                        />
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2 justify-end pt-2">
                        <Button
                            variant="secondary"
                            onClick={() => {
                                setIsDeleteAllOpen(false)
                                setDeleteConfirmText('')
                            }}
                            disabled={deleteAllLoading}
                            size="sm"
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="danger"
                            onClick={async () => {
                                if (deleteConfirmText !== 'DELETE') {
                                    return
                                }
                                setDeleteAllLoading(true)
                                try {
                                    await symbolsAPI.deleteAllSymbols()
                                    setIsDeleteAllOpen(false)
                                    setDeleteConfirmText('')
                                    await loadData(true, true)
                                } catch (e: any) {
                                    alert(`Failed to delete all symbols: ${e?.response?.data?.detail || e.message}`)
                                } finally {
                                    setDeleteAllLoading(false)
                                }
                            }}
                            disabled={deleteConfirmText !== 'DELETE' || deleteAllLoading}
                            size="sm"
                        >
                            {deleteAllLoading ? (
                                <>
                                    <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />
                                    Deleting...
                                </>
                            ) : (
                                <>
                                    <Trash2 className="w-4 h-4 mr-1.5" />
                                    Delete All
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </SecondaryModal>

        </div>
    )
}
