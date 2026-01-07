'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { announcementsAPI } from '@/lib/api'
import { RefreshCw, ChevronDown, ChevronUp, ChevronLeft, ChevronRight, Search, X, Download, ExternalLink, FileText } from 'lucide-react'

interface Attachment {
  file_name: string
  file_url: string | null
  mime_type: string | null
}

interface Announcement {
  unique_hash: string
  announcement_datetime: string | null
  company_info: string
  company_name: string | null
  symbol_nse: string | null
  symbol_bse: string | null
  isin: string | null
  headline: string
  category: string | null
  attachments: Attachment[]
  source_link: string | null
  created_at: string | null
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

  // Live update state
  const [lastUpdateTime, setLastUpdateTime] = useState<Date | null>(null)
  const [newAnnouncementsCount, setNewAnnouncementsCount] = useState(0)
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const lastAnnouncementHashRef = useRef<string | null>(null)
  const fetchAnnouncementsRef = useRef<typeof fetchAnnouncements | null>(null)

  // Fetch announcements from DuckDB
  const fetchAnnouncements = useCallback(async (currentPage: number = page, currentPageSize: number = pageSize, searchTerm?: string, silent: boolean = false) => {
    if (!silent) {
      setLoading(true)
    }
    try {
      const offset = (currentPage - 1) * currentPageSize
      let effectiveSearchTerm: string | undefined
      if (searchTerm !== undefined) {
        effectiveSearchTerm = searchTerm && searchTerm.trim() ? searchTerm.trim() : undefined
      } else {
        effectiveSearchTerm = searchQuery && searchQuery.trim() ? searchQuery.trim() : undefined
      }

      console.log('[Announcements] Fetching:', {
        page: currentPage,
        pageSize: currentPageSize,
        offset,
        search: effectiveSearchTerm
      })

      const response = await announcementsAPI.getAnnouncements(currentPageSize, offset, effectiveSearchTerm)
      const newAnnouncements = response.announcements || []

      console.log('[Announcements] Response:', {
        count: newAnnouncements.length,
        total: response.total
      })

      // Check for new announcements (only on first page and when not searching)
      if (currentPage === 1 && !effectiveSearchTerm && newAnnouncements.length > 0) {
        const latestHash = newAnnouncements[0].unique_hash
        if (lastAnnouncementHashRef.current && lastAnnouncementHashRef.current !== latestHash) {
          const lastKnownIndex = newAnnouncements.findIndex((a: Announcement) => a.unique_hash === lastAnnouncementHashRef.current)
          if (lastKnownIndex > 0) {
            setNewAnnouncementsCount(lastKnownIndex)
            setTimeout(() => {
              setNewAnnouncementsCount(0)
            }, 3000)
          }
        }
        lastAnnouncementHashRef.current = latestHash
      }

      setAnnouncements(newAnnouncements)
      setTotal(response.total || 0)
      setTotalPages(Math.ceil((response.total || 0) / currentPageSize))
      setLastUpdateTime(new Date())
    } catch (error: any) {
      console.error('[Announcements] Error fetching:', error)
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
      setSearch('')
      setSearchQuery('')
      setPage(1)
      fetchAnnouncements(1, pageSize)
    }
  }, [activeTab])

  // Live polling for new announcements
  useEffect(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current)
      pollingIntervalRef.current = null
    }

    if (activeTab === 'announcements' && page === 1 && !searchQuery) {
      pollingIntervalRef.current = setInterval(() => {
        if (fetchAnnouncementsRef.current) {
          fetchAnnouncementsRef.current(1, pageSize, undefined, true)
        }
      }, 10000)

      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current)
          pollingIntervalRef.current = null
        }
      }
    }
  }, [activeTab, page, searchQuery, pageSize])

  // Handle search
  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  const handleSearchClick = () => {
    const searchValue = search.trim()
    if (searchValue === searchQuery) {
      fetchAnnouncements(page, pageSize, searchValue || undefined)
      return
    }
    setSearchQuery(searchValue)
    setPage(1)
    fetchAnnouncements(1, pageSize, searchValue || undefined, false)
  }

  const handleClearSearch = () => {
    setSearch('')
    setSearchQuery('')
    setPage(1)
    lastAnnouncementHashRef.current = null
    fetchAnnouncements(1, pageSize, '', false)
  }

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  // Handle attachment download
  const handleDownloadAttachment = async (uniqueHash: string, attachmentIndex: number = 0) => {
    try {
      // Try new endpoint format first, fallback to legacy
      const response = await announcementsAPI.downloadAttachment(uniqueHash)

      let filename = `attachment_${uniqueHash.slice(0, 8)}.pdf`
      try {
        const disposition = response.headers?.['content-disposition'] || response.headers?.['Content-Disposition']
        if (disposition) {
          const filenameMatch = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, '').trim()
            try {
              filename = decodeURIComponent(filename)
            } catch {
              // If decoding fails, use as-is
            }
          }
        }
      } catch (headerError) {
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

  // Generate page numbers with ellipsis
  const getPageNumbers = () => {
    const pages: (number | string)[] = []
    const maxVisible = 5

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i)
      }
    } else {
      pages.push(1)

      if (page <= 3) {
        for (let i = 2; i <= 4; i++) {
          pages.push(i)
        }
        pages.push('ellipsis')
        pages.push(totalPages)
      } else if (page >= totalPages - 2) {
        pages.push('ellipsis')
        for (let i = totalPages - 3; i <= totalPages; i++) {
          pages.push(i)
        }
      } else {
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

  // Build company subtext (NSE | BSE | ISIN)
  const buildCompanySubtext = (announcement: Announcement) => {
    const parts: string[] = []
    if (announcement.symbol_nse) parts.push(`NSE: ${announcement.symbol_nse}`)
    if (announcement.symbol_bse) parts.push(`BSE: ${announcement.symbol_bse}`)
    if (announcement.isin) parts.push(`ISIN: ${announcement.isin}`)
    return parts.join(' | ') || null
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
                placeholder="Search by company, headline, or category..."
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
                      <TableHeaderCell className="w-52">Company</TableHeaderCell>
                      <TableHeaderCell className="min-w-[350px] max-w-none">Headline</TableHeaderCell>
                      <TableHeaderCell className="w-32">Category</TableHeaderCell>
                      <TableHeaderCell className="w-32">Attachments</TableHeaderCell>
                      <TableHeaderCell className="w-28">Source Link</TableHeaderCell>
                    </TableHeader>
                    <TableBody>
                      {announcements.map((announcement, index) => {
                        const isExpanded = expandedRows.has(announcement.unique_hash)
                        const companySubtext = buildCompanySubtext(announcement)
                        const hasAttachments = announcement.attachments && announcement.attachments.length > 0
                        
                        return (
                          <TableRow key={announcement.unique_hash} index={index}>
                            {/* Column 1: Date & Time */}
                            <TableCell className="text-sm">
                              {(() => {
                                const annDate = formatDateTime(announcement.announcement_datetime)
                                if (annDate) {
                                  return (
                                    <div className="font-medium text-text-primary">
                                      {annDate}
                                    </div>
                                  )
                                }
                                return <span className="text-text-secondary">-</span>
                              })()}
                            </TableCell>
                            
                            {/* Column 2: Company (Name + NSE|BSE|ISIN) */}
                            <TableCell className="text-sm text-text-primary">
                              <div>
                                <div className="font-medium">
                                  {announcement.company_name || '-'}
                                </div>
                                {companySubtext && (
                                  <div className="text-xs text-text-secondary mt-0.5 font-mono">
                                    {companySubtext}
                                  </div>
                                )}
                              </div>
                            </TableCell>
                            
                            {/* Column 3: Headline */}
                            <TableCell className="text-sm text-text-primary">
                              <div>
                                <div 
                                  className={`font-medium break-words whitespace-normal ${
                                    isExpanded ? '' : 'line-clamp-2'
                                  }`}
                                >
                                  {announcement.headline || '-'}
                                </div>
                                {announcement.headline && announcement.headline.length > 150 && (
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      toggleRowExpansion(announcement.unique_hash)
                                    }}
                                    className="mt-1 text-xs text-primary hover:text-primary/80 hover:underline flex items-center gap-1 transition-colors"
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
                            </TableCell>
                            
                            {/* Column 4: Category */}
                            <TableCell className="text-sm text-text-secondary">
                              {announcement.category || '-'}
                            </TableCell>
                            
                            {/* Column 5: Attachments */}
                            <TableCell className="text-sm">
                              {hasAttachments ? (
                                <div className="flex flex-col gap-1">
                                  {announcement.attachments.map((att, attIndex) => (
                                    <button
                                      key={attIndex}
                                      onClick={() => handleDownloadAttachment(announcement.unique_hash, attIndex)}
                                      className="text-primary hover:text-primary/80 hover:underline flex items-center gap-1.5 transition-colors text-xs"
                                      title={`Download ${att.file_name}`}
                                    >
                                      <FileText className="w-3.5 h-3.5" />
                                      <span className="truncate max-w-[100px]">
                                        {att.file_name || 'Attachment'}
                                      </span>
                                      <Download className="w-3 h-3" />
                                    </button>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-text-secondary">-</span>
                              )}
                            </TableCell>
                            
                            {/* Column 6: Source Link */}
                            <TableCell className="text-sm">
                              {announcement.source_link ? (
                                <a
                                  href={announcement.source_link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary hover:text-primary/80 hover:underline flex items-center gap-1.5 transition-colors"
                                  title="Open source link"
                                >
                                  <ExternalLink className="w-4 h-4" />
                                  <span className="text-xs">Open</span>
                                </a>
                              ) : (
                                <span className="text-text-secondary">-</span>
                              )}
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
