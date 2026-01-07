'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { announcementsAPI } from '@/lib/api'
import { RefreshCw, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Search, X, Download, ExternalLink } from 'lucide-react'

interface Announcement {
  announcement_id: string
  symbol: string
  symbol_nse: string
  symbol_bse: string
  exchange: string
  headline: string
  description: string
  category: string
  announcement_datetime: string
  received_at: string
  attachment_id: string | null
  link: string | null
  company_name: string | null
  price?: number
  price_change?: number
}


export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'overview' | 'announcements'>('overview')
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(false)
  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)

  // Search state
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  // Expanded rows state
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  
  // Track which descriptions are actually truncated (need show more button)
  const [truncatedDescriptions, setTruncatedDescriptions] = useState<Set<string>>(new Set())
  const descriptionRefs = useRef<Map<string, HTMLDivElement>>(new Map())

  // Live update state
  const [lastUpdateTime, setLastUpdateTime] = useState<Date | null>(null)
  const [newAnnouncementsCount, setNewAnnouncementsCount] = useState(0)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const lastAnnouncementIdRef = useRef<string | null>(null)
  const fetchAnnouncementsRef = useRef<typeof fetchAnnouncements | null>(null)

  // Fetch announcements from DuckDB
  const fetchAnnouncements = useCallback(async (currentPage: number = page, currentPageSize: number = pageSize, searchTerm?: string, silent: boolean = false) => {
    if (!silent) {
      setLoading(true)
    }
    try {
      const offset = (currentPage - 1) * currentPageSize
      // Use searchTerm if provided, otherwise use searchQuery state
      // Only pass non-empty strings to the API
      // If searchTerm is explicitly undefined, it means clear search - use undefined
      // If searchTerm is a string (even empty), use it
      // Otherwise fall back to searchQuery state
      let effectiveSearchTerm: string | undefined
      if (searchTerm !== undefined) {
        // searchTerm was explicitly passed - if it's empty string or falsy, convert to undefined
        // This handles the case when clear button passes '' to explicitly clear
        effectiveSearchTerm = searchTerm && searchTerm.trim() ? searchTerm.trim() : undefined
      } else {
        // Use searchQuery from state (fallback)
        effectiveSearchTerm = searchQuery && searchQuery.trim() ? searchQuery.trim() : undefined
      }

      console.log('[Announcements] Fetching:', {
        page: currentPage,
        pageSize: currentPageSize,
        offset,
        search: effectiveSearchTerm,
        searchQuery,
        searchTerm
      })

      const response = await announcementsAPI.getAnnouncements(currentPageSize, offset, effectiveSearchTerm)
      const newAnnouncements = response.announcements || []

      console.log('[Announcements] Response:', {
        count: newAnnouncements.length,
        total: response.total,
        hasData: newAnnouncements.length > 0
      })

      // Debug: Log sample data to check symbols and company names
      if (newAnnouncements.length > 0) {
        console.log('[Announcements] Sample announcement:', {
          announcement_id: newAnnouncements[0].announcement_id,
          symbol_nse: newAnnouncements[0].symbol_nse,
          symbol_bse: newAnnouncements[0].symbol_bse,
          symbol: newAnnouncements[0].symbol,
          company_name: newAnnouncements[0].company_name,
          attachment_id: newAnnouncements[0].attachment_id,
          headline: newAnnouncements[0].headline?.substring(0, 50)
        })
      }

      // Check for new announcements (only on first page and when not searching)
      if (currentPage === 1 && !effectiveSearchTerm && newAnnouncements.length > 0) {
        const latestId = newAnnouncements[0].announcement_id
        if (lastAnnouncementIdRef.current && lastAnnouncementIdRef.current !== latestId) {
          // Count new announcements by finding where the last known ID appears
          const lastKnownIndex = newAnnouncements.findIndex(a => a.announcement_id === lastAnnouncementIdRef.current)
          if (lastKnownIndex > 0) {
            // New announcements found - update count and show notification
            setNewAnnouncementsCount(lastKnownIndex)
            // Clear notification after 3 seconds
            setTimeout(() => {
              setNewAnnouncementsCount(0)
            }, 3000)
          }
        } else if (!lastAnnouncementIdRef.current) {
          // First load - just set the reference
          lastAnnouncementIdRef.current = latestId
        }
      }

      // Update the reference if we're on first page without search
      if (currentPage === 1 && !effectiveSearchTerm && newAnnouncements.length > 0 && !lastAnnouncementIdRef.current) {
        lastAnnouncementIdRef.current = newAnnouncements[0].announcement_id
      }

      setAnnouncements(newAnnouncements)
      setTotal(response.total || 0)
      setTotalPages(Math.ceil((response.total || 0) / currentPageSize))
      setLastUpdateTime(new Date())
    } catch (error: any) {
      console.error('[Announcements] Error fetching:', error)
      console.error('[Announcements] Error details:', {
        message: error?.message,
        response: error?.response?.data,
        status: error?.response?.status
      })
      if (!silent) {
        setAnnouncements([])
        setTotal(0)
        setTotalPages(1)
      }
    } finally {
      if (!silent) {
        setLoading(false)
      }
    }
  }, [page, pageSize, searchQuery])

  // Keep ref updated with latest fetch function
  useEffect(() => {
    fetchAnnouncementsRef.current = fetchAnnouncements
  }, [fetchAnnouncements])

  // Initial load when announcements tab is active
  useEffect(() => {
    if (activeTab === 'announcements') {
      // Reset search when switching to announcements tab
      setSearch('')
      setSearchQuery('')
      setPage(1)
      fetchAnnouncements(1, pageSize)
    }
  }, [activeTab])

  // Live polling for new announcements (only when on first page and not searching)
  useEffect(() => {
    // Clear any existing polling
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }

    // Start polling only when on announcements tab, first page, and no search
    if (activeTab === 'announcements' && page === 1 && !searchQuery) {
      // Poll every 10 seconds for new announcements
      pollingIntervalRef.current = setInterval(() => {
        if (fetchAnnouncementsRef.current) {
          fetchAnnouncementsRef.current(1, pageSize, undefined, true) // Silent fetch
        }
      }, 10000) // 10 seconds

      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
      }
    }
  }, [activeTab, page, searchQuery, pageSize]) // Removed fetchAnnouncements from deps to avoid restart

  // Handle search
  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  const handleSearchClick = () => {
    const searchValue = search.trim()
    if (searchValue === searchQuery) {
      // Already searching for this term, just refresh
      fetchAnnouncements(page, pageSize, searchValue || undefined)
      return
    }
    setSearchQuery(searchValue)
    setPage(1)
    // Pass undefined if empty, otherwise pass the search value
    fetchAnnouncements(1, pageSize, searchValue || undefined, false)
  }

  const handleClearSearch = () => {
    // Clear all search-related state immediately
    setSearch('')
    setSearchQuery('')
    setPage(1)
    // Reset the last announcement ID reference when clearing search
    lastAnnouncementIdRef.current = null

    // Force fetch with empty string - this will be converted to undefined in fetchAnnouncements
    // We pass empty string explicitly to override any stale searchQuery in the closure
    fetchAnnouncements(1, pageSize, '', false)
  }

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  // Handle attachment download
  const handleDownloadAttachment = async (announcementId: string) => {
    try {
      const response = await announcementsAPI.downloadAttachment(announcementId)

      // Extract filename from Content-Disposition header if available
      let filename = `announcement_${announcementId}.pdf`
      try {
        // Axios normalizes headers to lowercase
        const disposition = response.headers?.['content-disposition'] || response.headers?.['Content-Disposition']
        if (disposition) {
          // Try to extract filename from Content-Disposition header
          // Format: attachment; filename="filename.pdf" or attachment; filename=filename.pdf
          const filenameMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, '').trim()
            // Decode URI if needed
            try {
              filename = decodeURIComponent(filename)
            } catch {
              // If decoding fails, use as-is
            }
          }
        }
      } catch (headerError) {
        // If header parsing fails, use default filename
        console.debug('Could not parse filename from headers:', headerError)
      }

      const blob = response.data instanceof Blob ? response.data : new Blob([response.data])
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (error) {
      console.error('Error downloading attachment:', error)
      alert('Failed to download attachment. Please try again.')
    }
  }

  // Handle page change
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages) {
      setPage(newPage)
      fetchAnnouncements(newPage, pageSize)
    }
  }

  // Handle page size change
  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(1)
    fetchAnnouncements(1, newPageSize)
  }

  // Toggle row expansion
  const toggleRowExpansion = (id: string) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev)
      if (newSet.has(id)) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      return newSet
    })
  }

  // Check truncation for all descriptions after render
  useEffect(() => {
    // Use a small delay to ensure DOM is fully rendered
    const timeoutId = setTimeout(() => {
      const newTruncated = new Set<string>()
      
      descriptionRefs.current.forEach((element, id) => {
        // Skip if row is expanded
        if (expandedRows.has(id)) {
          return
        }
        
        if (element) {
          // Check if content is actually truncated (scrollHeight > clientHeight)
          const isTruncated = element.scrollHeight > element.clientHeight
          if (isTruncated) {
            newTruncated.add(id)
          }
        }
      })
      
      // Only update state if there's a change
      setTruncatedDescriptions(prev => {
        // Check if sets are different
        if (prev.size !== newTruncated.size) {
          return newTruncated
        }
        for (const id of prev) {
          if (!newTruncated.has(id)) {
            return newTruncated
          }
        }
        for (const id of newTruncated) {
          if (!prev.has(id)) {
            return newTruncated
          }
        }
        return prev // No change
      })
    }, 150)

    return () => clearTimeout(timeoutId)
  }, [announcements, expandedRows])

  // Generate page numbers with ellipsis (same as symbols page)
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


  const formatDate = (dateString: string | null | undefined) => {
    if (!dateString) return null
    try {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return null
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    } catch {
      return null
    }
  }

  const formatDateTime = (dateString: string | null | undefined) => {
    if (!dateString) return null
    try {
      const date = new Date(dateString)
      if (isNaN(date.getTime())) return null
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    } catch {
      return null
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
            Dashboard
          </h1>
          <p className="text-xs font-sans text-text-secondary">
            System overview and analytics metrics
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-[#1f2a44] mb-6">
        <button
          className={`pb-2 px-1 text-sm font-medium transition-colors ${activeTab === 'overview'
            ? 'text-primary border-b-2 border-primary'
            : 'text-text-secondary hover:text-text-primary'
            }`}
          onClick={() => setActiveTab('overview')}
        >
          Overview
        </button>
        <button
          className={`pb-2 px-1 text-sm font-medium transition-colors ${activeTab === 'announcements'
            ? 'text-primary border-b-2 border-primary'
            : 'text-text-secondary hover:text-text-primary'
            }`}
          onClick={() => setActiveTab('announcements')}
        >
          Latest Corporate Announcements
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' && (
        <>
          {/* Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            <Card compact>
              <div className="space-y-1">
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">Total Symbols</p>
                <p className="text-xl font-sans font-semibold text-text-primary">1,234</p>
                <p className="text-[10px] font-sans text-success">+12% from last month</p>
              </div>
            </Card>

            <Card compact>
              <div className="space-y-1">
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">Active Signals</p>
                <p className="text-xl font-sans font-semibold text-text-primary">89</p>
                <p className="text-[10px] font-sans text-success">+5 new today</p>
              </div>
            </Card>

            <Card compact>
              <div className="space-y-1">
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">ML Models</p>
                <p className="text-xl font-sans font-semibold text-text-primary">12</p>
                <p className="text-[10px] font-sans text-text-secondary">All active</p>
              </div>
            </Card>

            <Card compact>
              <div className="space-y-1">
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">Accuracy</p>
                <p className="text-xl font-sans font-semibold text-text-primary">87.5%</p>
                <p className="text-[10px] font-sans text-success">+2.3% improvement</p>
              </div>
            </Card>
          </div>

          {/* Data Tables */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card title="Recent Activity" compact>
              <Table>
                <TableHeader>
                  <TableHeaderCell>Event</TableHeaderCell>
                  <TableHeaderCell className="text-right">Time</TableHeaderCell>
                </TableHeader>
                <TableBody>
                  <TableRow index={0}>
                    <TableCell>New signal generated</TableCell>
                    <TableCell numeric className="text-text-secondary">2h ago</TableCell>
                  </TableRow>
                  <TableRow index={1}>
                    <TableCell>AAPL - Buy signal</TableCell>
                    <TableCell numeric className="text-text-secondary">2h ago</TableCell>
                  </TableRow>
                  <TableRow index={2}>
                    <TableCell>Model updated</TableCell>
                    <TableCell numeric className="text-text-secondary">5h ago</TableCell>
                  </TableRow>
                  <TableRow index={3}>
                    <TableCell>RSI Indicator v2.1</TableCell>
                    <TableCell numeric className="text-text-secondary">5h ago</TableCell>
                  </TableRow>
                  <TableRow index={4}>
                    <TableCell>Data sync completed</TableCell>
                    <TableCell numeric className="text-text-secondary">1d ago</TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </Card>

            <Card title="System Status" compact>
              <div className="space-y-2">
                <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
                  <span className="text-xs font-sans text-text-secondary">Backend API</span>
                  <span className="text-xs font-sans text-success">ONLINE</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
                  <span className="text-xs font-sans text-text-secondary">Database</span>
                  <span className="text-xs font-sans text-success">CONNECTED</span>
                </div>
                <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
                  <span className="text-xs font-sans text-text-secondary">Analytics Engine</span>
                  <span className="text-xs font-sans text-success">ACTIVE</span>
                </div>
                <div className="flex items-center justify-between py-1.5">
                  <span className="text-xs font-sans text-text-secondary">Last Sync</span>
                  <span className="text-xs font-sans text-text-secondary">12:34:56</span>
                </div>
              </div>
            </Card>
          </div>
        </>
      )}

      {activeTab === 'announcements' && (
        <div className="space-y-4">
          {/* Header with Refresh Button */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-sans font-semibold text-text-primary">
                Latest Corporate Announcements
              </h2>
              {lastUpdateTime && (
                <span className="text-xs text-text-secondary">
                  Updated {lastUpdateTime.toLocaleTimeString()}
                </span>
              )}
              {newAnnouncementsCount > 0 && (
                <span className="px-2 py-1 text-xs font-medium bg-success/20 text-success rounded-full animate-pulse">
                  {newAnnouncementsCount} new
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              {page === 1 && !searchQuery && (
                <span className="text-xs text-text-secondary flex items-center gap-1">
                  <span className="w-2 h-2 bg-success rounded-full animate-pulse"></span>
                  Live
                </span>
              )}
              <RefreshButton
                variant="secondary"
                onClick={async () => {
                  await fetchAnnouncements(page, pageSize, searchQuery)
                }}
                size="sm"
                disabled={loading}
              />
            </div>
          </div>

          {/* Search Box */}
          <div className="flex items-center gap-2">
            <div className="flex-1 max-w-md">
              <Input
                type="text"
                placeholder="Search by symbol, company name, or headline..."
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                className="h-9"
              />
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSearchClick}
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

          <Card compact>
            {loading ? (
              <div className="flex items-center justify-center py-12">
                <RefreshCw className="w-6 h-6 animate-spin text-primary" />
                <span className="ml-3 text-sm font-medium text-text-primary">Loading announcements...</span>
              </div>
            ) : announcements.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-text-secondary mb-2">
                  {searchQuery ? `No announcements found for "${searchQuery}"` : 'No announcements available'}
                </p>
                {searchQuery && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleClearSearch}
                    className="mt-2"
                  >
                    Clear search
                  </Button>
                )}
              </div>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableHeaderCell className="w-36">Date & Time</TableHeaderCell>
                      <TableHeaderCell className="w-40">Company</TableHeaderCell>
                      <TableHeaderCell className="w-32">Symbol</TableHeaderCell>
                      <TableHeaderCell className="min-w-[400px] max-w-none">Headline</TableHeaderCell>
                      <TableHeaderCell className="w-32">Category</TableHeaderCell>
                      <TableHeaderCell className="w-40">Attachment & Link</TableHeaderCell>
                    </TableHeader>
                    <TableBody>
                      {announcements.map((announcement, index) => {
                        const isExpanded = expandedRows.has(announcement.announcement_id)
                        const isFirstRow = index === 0
                        return (
                          <TableRow key={announcement.announcement_id} index={index}>
                            <TableCell className="text-sm">
                              {(() => {
                                const annDate = formatDateTime(announcement.announcement_datetime || announcement.received_at)
                                const receivedDate = formatDateTime(announcement.received_at)

                                if (annDate || receivedDate) {
                                  return (
                                    <div>
                                      {annDate && (
                                        <div className="font-medium text-text-primary">
                                          {annDate}
                                        </div>
                                      )}
                                      {receivedDate && receivedDate !== annDate && (
                                        <div className="text-xs text-text-secondary mt-0.5">
                                          Received: {receivedDate}
                                        </div>
                                      )}
                                    </div>
                                  )
                                }
                                return null
                              })()}
                            </TableCell>
                            <TableCell className="text-sm text-text-primary">
                              <div>
                                <div className="font-medium">
                                  {announcement.company_name && announcement.company_name.trim() ? announcement.company_name : '-'}
                                </div>
                                {isFirstRow && (announcement.price !== undefined || announcement.price_change !== undefined) && (
                                  <div className="text-xs mt-1">
                                    {announcement.price !== undefined && (
                                      <span className="text-text-primary">₹{announcement.price.toFixed(2)}</span>
                                    )}
                                    {announcement.price_change !== undefined && (
                                      <span className={`ml-2 ${announcement.price_change >= 0 ? 'text-success' : 'text-error'}`}>
                                        {announcement.price_change >= 0 ? '+' : ''}{announcement.price_change.toFixed(2)}%
                                      </span>
                                    )}
                                  </div>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="text-sm">
                              <div className="flex flex-col gap-1">
                                {announcement.symbol_nse && announcement.symbol_nse.trim() && (
                                  <span className="font-mono text-xs text-primary">NSE: {announcement.symbol_nse}</span>
                                )}
                                {announcement.symbol_bse && announcement.symbol_bse.trim() && (
                                  <span className="font-mono text-xs text-primary">BSE: {announcement.symbol_bse}</span>
                                )}
                                {announcement.symbol && announcement.symbol.trim() &&
                                  (!announcement.symbol_nse || !announcement.symbol_nse.trim()) &&
                                  (!announcement.symbol_bse || !announcement.symbol_bse.trim()) && (
                                    <span className="font-mono text-xs text-primary">{announcement.symbol}</span>
                                  )}
                                {(!announcement.symbol_nse || !announcement.symbol_nse.trim()) &&
                                  (!announcement.symbol_bse || !announcement.symbol_bse.trim()) &&
                                  (!announcement.symbol || !announcement.symbol.trim()) && (
                                    <span className="text-xs text-text-secondary">-</span>
                                  )}
                              </div>
                            </TableCell>
                            <TableCell className="text-sm text-text-primary">
                              <div>
                                <div className="font-medium break-words whitespace-normal overflow-wrap-anywhere">
                                  {announcement.headline && announcement.headline.trim() ? announcement.headline : '-'}
                                </div>
                                {announcement.description && (
                                  <div className="mt-1">
                                    <div 
                                      ref={(el) => {
                                        if (el) {
                                          descriptionRefs.current.set(announcement.announcement_id, el)
                                        } else {
                                          descriptionRefs.current.delete(announcement.announcement_id)
                                        }
                                      }}
                                      className={`text-xs text-text-secondary transition-all duration-200 ${isExpanded ? 'whitespace-pre-wrap' : 'line-clamp-2'
                                        }`}
                                    >
                                      {announcement.description}
                                    </div>
                                    {(isExpanded || truncatedDescriptions.has(announcement.announcement_id)) && (
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          toggleRowExpansion(announcement.announcement_id)
                                        }}
                                        className="mt-1 text-xs text-primary hover:text-primary/80 hover:underline flex items-center gap-1 transition-colors"
                                        title={isExpanded ? 'Collapse description' : 'Expand description'}
                                      >
                                        {isExpanded ? (
                                          <>
                                            <ChevronUp className="w-3 h-3" />
                                            <span>Show less</span>
                                          </>
                                        ) : (
                                          <>
                                            <ChevronDown className="w-3 h-3" />
                                            <span>Show more</span>
                                          </>
                                        )}
                                      </button>
                                    )}
                                  </div>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="text-sm text-text-secondary">
                              {announcement.category || '-'}
                            </TableCell>
                            <TableCell className="text-sm">
                              <div className="flex items-center gap-3">
                                {announcement.attachment_id &&
                                  announcement.attachment_id.trim() &&
                                  announcement.attachment_id.trim() !== '' &&
                                  announcement.attachment_id.trim().toLowerCase() !== 'null' &&
                                  announcement.attachment_id.trim().toLowerCase() !== 'none' ? (
                                  <button
                                    onClick={() => handleDownloadAttachment(announcement.announcement_id)}
                                    className="text-primary hover:text-primary/80 hover:underline flex items-center gap-1.5 transition-colors"
                                    title="Download attachment"
                                  >
                                    <Download className="w-4 h-4" />
                                    <span className="text-xs">Download</span>
                                  </button>
                                ) : null}
                                {announcement.link &&
                                  announcement.link.trim() &&
                                  announcement.link.trim() !== '' &&
                                  announcement.link.trim().toLowerCase() !== 'null' &&
                                  announcement.link.trim().toLowerCase() !== 'none' ? (
                                  <a
                                    href={announcement.link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="text-primary hover:text-primary/80 hover:underline flex items-center gap-1.5 transition-colors"
                                    title="Open link in new tab"
                                  >
                                    <ExternalLink className="w-4 h-4" />
                                    <span className="text-xs">Open</span>
                                  </a>
                                ) : null}
                                {(!announcement.attachment_id || 
                                  announcement.attachment_id.trim() === '' ||
                                  announcement.attachment_id.trim().toLowerCase() === 'null' ||
                                  announcement.attachment_id.trim().toLowerCase() === 'none') &&
                                 (!announcement.link ||
                                  announcement.link.trim() === '' ||
                                  announcement.link.trim().toLowerCase() === 'null' ||
                                  announcement.link.trim().toLowerCase() === 'none') && (
                                  <span className="text-xs text-text-secondary">-</span>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        )
                      })}
                    </TableBody>
                  </Table>
                </div>


                {/* Pagination Controls */}
                {totalPages > 0 && (
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
                        onClick={() => handlePageChange(page - 1)}
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
                            onClick={() => handlePageChange(pageNumValue)}
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
                        onClick={() => handlePageChange(page + 1)}
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
                          of <span className="font-semibold text-text-primary">{total}</span>
                        </>
                      ) : (
                        'No results'
                      )}
                    </div>
                  </div>
                )}
              </>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
