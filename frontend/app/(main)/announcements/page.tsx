'use client'

import React, { useState, useEffect, useRef, useMemo } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { announcementsAPI } from '@/lib/api'
import { useAnnouncementsWebSocket } from '@/lib/useAnnouncementsWebSocket'
import { ChevronLeft, ChevronRight, ChevronDown, ChevronRight as ChevronRightIcon, Eye, Download, AlertCircle, Radio, Search, Calendar } from 'lucide-react'

}

interface Announcement {
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
  links?: Link[]
  // Note: attachments are NOT in payload - must be fetched on-demand
}

interface AnnouncementsResponse {
  announcements: Announcement[]
  total: number
  page?: number
  page_size?: number
  total_pages?: number
  limit?: number
  offset: number
}

interface GroupedAnnouncement {
  key: string
  dateTime: string
  headline: string
  items: Announcement[]
}

export default function AnnouncementsPage() {
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [openLinksMenu, setOpenLinksMenu] = useState<string | null>(null)
  const [needsExpansionMap, setNeedsExpansionMap] = useState<Map<string, boolean>>(new Map())
  const [downloadingAttachment, setDownloadingAttachment] = useState<Set<string>>(new Set())
  const [viewingAttachment, setViewingAttachment] = useState<Set<string>>(new Set())
  const [attachmentErrors, setAttachmentErrors] = useState<Map<string, string>>(new Map())
  
  const MAX_VISIBLE_LINES = 3
  const descriptionRefs = useRef<Map<string, HTMLDivElement>>(new Map())
  
  // Pagination state
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)
  
  // Search state (input values)
  const [searchInput, setSearchInput] = useState('')
  const [searchFromDateInput, setSearchFromDateInput] = useState('')
  const [searchToDateInput, setSearchToDateInput] = useState('')
  
  // Active filter state (applied filters)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchFromDate, setSearchFromDate] = useState('')
  const [searchToDate, setSearchToDate] = useState('')
  
  // Normalize date/time to the same format for grouping (round to minute for grouping)
  const normalizeDateTime = (dateStr?: string): string => {
    if (!dateStr) return ''
    try {
      const date = new Date(dateStr)
      // Round to minute level for grouping
      date.setSeconds(0, 0)
      return date.toISOString()
    } catch {
      return dateStr
    }
  }

  // WebSocket for real-time updates
  const { isConnected: wsConnected } = useAnnouncementsWebSocket((newAnnouncement) => {
    // Add new announcement to the top of the list (only if on first page and no filters)
    if (page === 1 && !searchQuery && !searchFromDate && !searchToDate) {
      setAnnouncements(prev => {
        // Check if announcement already exists (avoid duplicates)
        const exists = prev.some(ann => ann.id === newAnnouncement.id)
        if (exists) {
          return prev
        }
        // Add to top - total will be recalculated when grouped
        // Keep only the first pageSize groups worth of announcements
        // This ensures pagination stays correct (25 groups visible)
        const updated = [newAnnouncement, ...prev]
        
        // Group the updated list to see how many groups we have
        // We'll limit to pageSize groups worth of items
        const tempGroups = new Map<string, Announcement[]>()
        updated.forEach((ann) => {
          const normalizedDateTime = normalizeDateTime(ann.trade_date)
          const headline = (ann.news_headline || '').trim().toLowerCase()
          const groupKey = headline 
            ? `${normalizedDateTime}|${headline}`
            : `${normalizedDateTime}|id:${ann.id}`
          
          if (!tempGroups.has(groupKey)) {
            tempGroups.set(groupKey, [ann])
          } else {
            tempGroups.get(groupKey)!.push(ann)
          }
        })
        
        // If we have more groups than pageSize, truncate to keep only enough items for pageSize groups
        const sortedGroups = Array.from(tempGroups.values()).sort((a, b) => {
          const dateA = new Date(a[0].trade_date || 0).getTime()
          const dateB = new Date(b[0].trade_date || 0).getTime()
          return dateB - dateA
        })
        
        // Update total count (total announcements, not groups)
        setTotal(prevTotal => prevTotal + 1)
        
        if (sortedGroups.length > pageSize) {
          // Keep only items from the first pageSize groups
          const itemsToKeep: Announcement[] = []
          for (let i = 0; i < pageSize && i < sortedGroups.length; i++) {
            itemsToKeep.push(...sortedGroups[i])
          }
          return itemsToKeep
        }
        
        return updated
      })
      setLastRefresh(new Date())
    }
  })

  useEffect(() => {
    loadAnnouncements()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, searchQuery, searchFromDate, searchToDate])

  // Handle search button click
  const handleSearch = () => {
    setSearchQuery(searchInput)
    setSearchFromDate(searchFromDateInput)
    setSearchToDate(searchToDateInput)
    setPage(1) // Reset to first page on search
  }

  // Handle clear all
  const handleClearAll = () => {
    setSearchInput('')
    setSearchFromDateInput('')
    setSearchToDateInput('')
    setSearchQuery('')
    setSearchFromDate('')
    setSearchToDate('')
    setPage(1)
    loadAnnouncements()
  }

  // Debug: Log when announcements state changes
  useEffect(() => {
    console.log('Announcements state changed:', {
      count: announcements.length,
      total: total,
      loading: loading,
      error: error,
      firstAnnouncement: announcements[0] || null
    })
  }, [announcements, total, loading, error])

  // Close links menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (openLinksMenu && !(event.target as Element).closest('.links-menu-container')) {
        setOpenLinksMenu(null)
      }
    }
    
    if (openLinksMenu) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [openLinksMenu])


  const loadAnnouncements = async () => {
    try {
      setLoading(true)
      setError(null)

      const params: any = {}
      
      // If we have filters, use backend pagination
      // If no filters, load all announcements and paginate groups client-side
      if (searchQuery || searchFromDate || searchToDate) {
        // With filters: use backend pagination
        params.page = page
        params.page_size = pageSize
      } else {
        // No filters: load all announcements for client-side grouping and pagination
        // Request a large limit to get all announcements (backend might have a max, but try to get all)
        params.limit = 10000 // Large limit to get all announcements
        params.offset = 0
        // We'll paginate groups on the client side, not announcements
      }
      
      // Add search filters - backend will search entire database
      if (searchQuery && searchQuery.trim()) {
        params.search = searchQuery.trim()
      }
      if (searchFromDate) {
        params.from_date = searchFromDate
      }
      if (searchToDate) {
        params.to_date = searchToDate
      }

      const response = await announcementsAPI.getAnnouncements(params)
      
      console.log('API Response:', response)
      console.log('API Response type:', typeof response)
      console.log('API Response keys:', Object.keys(response || {}))
      console.log('Announcements array:', response.announcements)
      console.log('Announcements type:', Array.isArray(response.announcements))
      console.log('Total:', response.total)
      
      // Handle different response structures
      let data: Announcement[] = []
      if (response && response.announcements) {
        if (Array.isArray(response.announcements)) {
          data = response.announcements
        } else {
          console.warn('response.announcements is not an array:', response.announcements)
          data = []
        }
      } else if (response && Array.isArray(response)) {
        // Response might be the array directly
        data = response
      } else {
        console.warn('Unexpected response structure:', response)
        data = []
      }
      
      console.log('Setting announcements data:', data)
      console.log('Data length:', data.length)
      
      if (data.length > 0) {
        console.log('First announcement:', data[0])
        console.log('First announcement type:', typeof data[0])
        console.log('First announcement keys:', Object.keys(data[0] || {}))
        console.log('First announcement trade_date:', data[0].trade_date)
        console.log('First announcement trade_date type:', typeof data[0].trade_date)
      } else {
        console.warn('No announcements in data array, but total might be:', response.total)
      }
      
      // Backend handles all search filtering - no client-side filtering needed
      setAnnouncements(data)
      setTotal(response.total || 0)
      
      // If we have filters, use backend pagination
      // If no filters, we'll paginate groups client-side (setTotalPages will be updated in useEffect)
      if (searchQuery || searchFromDate || searchToDate) {
        setTotalPages(response.total_pages || Math.ceil((response.total || 0) / pageSize) || 1)
      }
      
      setLastRefresh(new Date())
    } catch (err: any) {
      console.error('Error:', err)
      setError(err.response?.data?.detail || err.message || 'Failed to load')
    } finally {
      setLoading(false)
    }
  }

  // Format date as DD Jan YYYY on first line, hh:mm AM/PM on second line
  const formatDate = (dateStr?: string) => {
    if (!dateStr) return { date: 'N/A', time: '' }
    try {
      // Handle multiple date formats
      let date: Date
      
      if (typeof dateStr === 'string') {
        // Try parsing as ISO string first
        date = new Date(dateStr)
        
        // If invalid, try other formats
        if (isNaN(date.getTime())) {
          // Try parsing with explicit timezone handling
          // Remove timezone info and add Z for UTC if no timezone specified
          let normalizedDateStr = dateStr.trim()
          if (!normalizedDateStr.includes('T')) {
            // If no time component, add midnight
            normalizedDateStr = normalizedDateStr + 'T00:00:00'
          }
          if (!normalizedDateStr.includes('Z') && !normalizedDateStr.match(/[+-]\d{2}:\d{2}$/)) {
            // No timezone, treat as UTC
            normalizedDateStr = normalizedDateStr + 'Z'
          }
          date = new Date(normalizedDateStr)
        }
        
        // If still invalid, return the string as-is
        if (isNaN(date.getTime())) {
          console.warn('Failed to parse date:', dateStr)
          return { date: dateStr, time: '' }
        }
      } else {
        date = new Date(dateStr)
        if (isNaN(date.getTime())) {
          console.warn('Failed to parse date:', dateStr)
          return { date: String(dateStr), time: '' }
        }
      }
      
      const day = String(date.getDate()).padStart(2, '0')
      const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
      const month = monthNames[date.getMonth()]
      const year = date.getFullYear()
      const datePart = `${day} ${month} ${year}`
      
      const hours = date.getHours()
      const minutes = date.getMinutes()
      const ampm = hours >= 12 ? 'PM' : 'AM'
      const displayHours = hours % 12 || 12
      const timePart = `${String(displayHours).padStart(2, '0')}:${String(minutes).padStart(2, '0')} ${ampm}`
      
      return { date: datePart, time: timePart }
    } catch (error) {
      console.error('Error formatting date:', dateStr, error)
      return { date: String(dateStr || 'N/A'), time: '' }
    }
  }

  // Format symbol as stacked NSE/BSE
  // BSE should show numeric code (script_code), not symbol
  const formatSymbol = (ann: Announcement) => {
    const nse = ann.symbol_nse
    // Use script_code for BSE (numeric code), fallback to symbol_bse without _BSE suffix
    const bse = ann.script_code?.toString() || ann.symbol_bse?.replace('_BSE', '')
    
    if (nse && bse) {
      return { nse, bse }
    } else if (nse) {
      return { nse, bse: null }
    } else if (bse) {
      return { nse: null, bse }
    }
    return { nse: null, bse: null }
  }

  // Check if description actually overflows (using DOM measurements)
  const checkDescriptionOverflow = (id: string, description: string) => {
    if (!description.trim()) {
      setNeedsExpansionMap(prev => {
        const newMap = new Map(prev)
        newMap.set(id, false)
        return newMap
      })
      return
    }

    const element = descriptionRefs.current.get(id)
    if (!element) {
      // Element not yet rendered, will check after render
      return
    }

    // Check if scrollHeight > clientHeight (actual overflow)
    const hasOverflow = element.scrollHeight > element.clientHeight
    
    setNeedsExpansionMap(prev => {
      const newMap = new Map(prev)
      newMap.set(id, hasOverflow)
      return newMap
    })
  }

  // Check overflow for all descriptions after render
  useEffect(() => {
    const checkAllOverflows = () => {
      announcements.forEach(ann => {
        if (ann.news_body && !expandedRows.has(ann.id)) {
          // Use setTimeout to ensure DOM is rendered
          setTimeout(() => {
            checkDescriptionOverflow(ann.id, ann.news_body || '')
          }, 0)
        }
      })
    }

    checkAllOverflows()

    // Also check on window resize (debounced)
    let resizeTimeout: NodeJS.Timeout
    const handleResize = () => {
      clearTimeout(resizeTimeout)
      resizeTimeout = setTimeout(() => {
        checkAllOverflows()
      }, 150)
    }

    window.addEventListener('resize', handleResize)
    return () => {
      window.removeEventListener('resize', handleResize)
      clearTimeout(resizeTimeout)
    }
  }, [announcements, expandedRows])
  
  // Check if announcement has links
  // Note: Attachments are NOT in payload - they must be fetched on-demand
  const hasLinks = (ann: Announcement) => {
    const links = ann.links || []
    return links.length > 0 && links.some(l => l.url)
  }

  // Group announcements by date/time, headline, AND company name
  // Only group if they have the same company name (or similar company names like "bank")
  const groupedAnnouncements = useMemo(() => {
    const groups = new Map<string, GroupedAnnouncement>()
    
    // Helper to normalize company name for grouping
    const normalizeCompanyName = (companyName: string): string => {
      if (!companyName) return ''
      // Convert to lowercase and trim
      const normalized = companyName.trim().toLowerCase()
      // Extract key words for similar company matching (e.g., "bank", "ltd", etc.)
      // Remove common suffixes and extract meaningful parts
      const cleaned = normalized
        .replace(/\s+(ltd|limited|inc|incorporated|corp|corporation|pvt|private)\s*\.?$/i, '')
        .replace(/\s+/g, ' ')
        .trim()
      return cleaned
    }
    
    // Helper to check if two company names are similar enough to group
    const areSimilarCompanies = (name1: string, name2: string): boolean => {
      const norm1 = normalizeCompanyName(name1)
      const norm2 = normalizeCompanyName(name2)
      
      // Exact match
      if (norm1 === norm2) return true
      
      // If both contain same key words (like "bank", "credit", etc.)
      if (norm1 && norm2) {
        const keywords1 = norm1.split(/\s+/).filter(w => w.length >= 4)
        const keywords2 = norm2.split(/\s+/).filter(w => w.length >= 4)
        
        // If they share at least one meaningful keyword, consider similar
        const commonKeywords = keywords1.filter(k => keywords2.includes(k))
        if (commonKeywords.length > 0) {
          return true
        }
      }
      
      return false
    }
    
    announcements.forEach((ann) => {
      const normalizedDateTime = normalizeDateTime(ann.trade_date)
      const headline = (ann.news_headline || '').trim().toLowerCase()
      const companyName = normalizeCompanyName(ann.company_name || '')
      
      // Create group key: date + headline + company name
      // Only group announcements with the same company name (or similar)
      const groupKey = headline && companyName
        ? `${normalizedDateTime}|${headline}|${companyName}`
        : headline
        ? `${normalizedDateTime}|${headline}`
        : `${normalizedDateTime}|id:${ann.id}`
      
      // Check if there's an existing group with similar company name
      let foundGroup = false
      if (companyName) {
        for (const [key, group] of groups.entries()) {
          // Check if same date, headline, and similar company
          if (key.startsWith(`${normalizedDateTime}|${headline}|`)) {
            const existingCompany = group.items[0]?.company_name || ''
            if (areSimilarCompanies(companyName, existingCompany)) {
              group.items.push(ann)
              foundGroup = true
              break
            }
          }
        }
      }
      
      if (!foundGroup) {
        if (!groups.has(groupKey)) {
          groups.set(groupKey, {
            key: groupKey,
            dateTime: ann.trade_date || '',
            headline: ann.news_headline || 'N/A',
            items: [ann],
          })
        } else {
          groups.get(groupKey)!.items.push(ann)
        }
      }
    })
    
    return Array.from(groups.values()).sort((a, b) => {
      // Sort by date (most recent first)
      const dateA = new Date(a.dateTime).getTime()
      const dateB = new Date(b.dateTime).getTime()
      return dateB - dateA
    })
  }, [announcements])

  // Calculate pagination based on GROUPS (not individual announcements)
  // Each group counts as 1 row for pagination
  const groupedCount = groupedAnnouncements.length
  const groupedTotalPages = Math.ceil(groupedCount / pageSize)
  
  // Paginate grouped announcements (show only pageSize groups per page)
  const paginatedGroups = useMemo(() => {
    const startIndex = (page - 1) * pageSize
    const endIndex = startIndex + pageSize
    return groupedAnnouncements.slice(startIndex, endIndex)
  }, [groupedAnnouncements, page, pageSize])
  
  // Update total pages based on groups, not individual announcements
  useEffect(() => {
    // Only update if we're not using backend pagination (i.e., showing all announcements)
    // When using filters, backend provides total_pages which we use
    if (!searchQuery && !searchFromDate && !searchToDate) {
      setTotalPages(Math.max(1, groupedTotalPages)) // At least 1 page
    }
  }, [groupedTotalPages, searchQuery, searchFromDate, searchToDate])

  const toggleGroup = (groupKey: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupKey)) {
        next.delete(groupKey)
      } else {
        next.add(groupKey)
      }
      return next
    })
  }
  
  // Handle attachment download (on-demand fetch from external API)
  const handleDownloadAttachment = async (announcementId: string) => {
    if (downloadingAttachment.has(announcementId) || viewingAttachment.has(announcementId)) {
      return // Already processing
    }
    
    // Clear any previous error
    setAttachmentErrors(prev => {
      const newMap = new Map(prev)
      newMap.delete(announcementId)
      return newMap
    })
    
    try {
      setDownloadingAttachment(prev => new Set(prev).add(announcementId))
      
      // Fetch attachment on-demand (DB-first, then external API)
      const blob = await announcementsAPI.getAttachment(announcementId)
      
      // Create download link
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `announcement-${announcementId}.pdf`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
    } catch (err: any) {
      // Handle different error types with user-friendly messages
      let errorMsg = 'Failed to download attachment'
      
      if (err.response?.status === 404) {
        // File not found - show friendly message
        errorMsg = 'Attachment not available for this announcement'
      } else if (err.response?.status === 504) {
        // Timeout
        errorMsg = err.response?.data?.detail || 'Request timed out. Please try again in a moment.'
      } else if (err.response?.status === 503) {
        // Service unavailable
        errorMsg = err.response?.data?.detail || 'Unable to connect to the server. Please check your connection and try again.'
      } else if (err.response?.status >= 500) {
        // Server error
        errorMsg = err.response?.data?.detail || 'Server error. Please try again later.'
      } else if (err.response?.data?.detail) {
        errorMsg = err.response.data.detail
      } else if (err.message) {
        errorMsg = err.message
      }
      
      setAttachmentErrors(prev => new Map(prev).set(announcementId, errorMsg))
      console.error('Error downloading attachment:', err)
    } finally {
      setDownloadingAttachment(prev => {
        const newSet = new Set(prev)
        newSet.delete(announcementId)
        return newSet
      })
    }
  }
  
  // Handle attachment view (open in new tab)
  const handleViewAttachment = async (announcementId: string) => {
    if (downloadingAttachment.has(announcementId) || viewingAttachment.has(announcementId)) {
      return // Already processing
    }
    
    // Clear any previous error
    setAttachmentErrors(prev => {
      const newMap = new Map(prev)
      newMap.delete(announcementId)
      return newMap
    })
    
    try {
      setViewingAttachment(prev => new Set(prev).add(announcementId))
      
      // Fetch attachment on-demand (DB-first, then external API)
      const blob = await announcementsAPI.getAttachment(announcementId)
      
      // Create blob URL and open in new tab
      const url = window.URL.createObjectURL(blob)
      window.open(url, '_blank')
      // Note: URL will be revoked when tab closes or after a delay
      setTimeout(() => window.URL.revokeObjectURL(url), 1000)
    } catch (err: any) {
      // Handle different error types with user-friendly messages
      let errorMsg = 'Failed to view attachment'
      
      if (err.response?.status === 404) {
        // File not found - show friendly message
        errorMsg = 'Attachment not available for this announcement'
      } else if (err.response?.status === 504) {
        // Timeout
        errorMsg = err.response?.data?.detail || 'Request timed out. Please try again in a moment.'
      } else if (err.response?.status === 503) {
        // Service unavailable
        errorMsg = err.response?.data?.detail || 'Unable to connect to the server. Please check your connection and try again.'
      } else if (err.response?.status >= 500) {
        // Server error
        errorMsg = err.response?.data?.detail || 'Server error. Please try again later.'
      } else if (err.response?.data?.detail) {
        errorMsg = err.response.data.detail
      } else if (err.message) {
        errorMsg = err.message
      }
      
      setAttachmentErrors(prev => new Map(prev).set(announcementId, errorMsg))
      console.error('Error viewing attachment:', err)
    } finally {
      setViewingAttachment(prev => {
        const newSet = new Set(prev)
        newSet.delete(announcementId)
        return newSet
      })
    }
  }

  const toggleExpand = (id: string, description: string) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev)
      const wasExpanded = newSet.has(id)
      if (wasExpanded) {
        newSet.delete(id)
      } else {
        newSet.add(id)
      }
      
      // Re-check overflow after state update
      setTimeout(() => {
        if (!wasExpanded) {
          // Just expanded, no need to check (it's now fully visible)
          setNeedsExpansionMap(prev => {
            const newMap = new Map(prev)
            newMap.set(id, true) // Keep expander visible for collapse button
            return newMap
          })
        } else {
          // Just collapsed, re-check if overflow still exists
          checkDescriptionOverflow(id, description)
        }
      }, 0)
      
      return newSet
    })
  }


  const handlePageChange = (newPage: number) => {
    // Use grouped total pages for pagination
    const maxPage = searchQuery || searchFromDate || searchToDate ? totalPages : groupedTotalPages
    if (newPage >= 1 && newPage <= maxPage) {
      setPage(newPage)
    }
  }

  const handlePageSizeChange = (newPageSize: number) => {
    setPageSize(newPageSize)
    setPage(1) // Reset to first page
  }

  const getPageNumbers = () => {
    const pages: (number | string)[] = []
    const maxVisible = 5
    // Use grouped total pages when no filters, otherwise use backend total_pages
    const currentTotalPages = searchQuery || searchFromDate || searchToDate ? totalPages : groupedTotalPages

    if (currentTotalPages <= maxVisible) {
      for (let i = 1; i <= currentTotalPages; i++) {
        pages.push(i)
      }
    } else {
      pages.push(1)

      if (page <= 3) {
        for (let i = 2; i <= 4; i++) {
          pages.push(i)
        }
        pages.push('ellipsis')
        pages.push(currentTotalPages)
      } else if (page >= currentTotalPages - 2) {
        pages.push('ellipsis')
        for (let i = currentTotalPages - 3; i <= currentTotalPages; i++) {
          pages.push(i)
        }
      } else {
        pages.push('ellipsis')
        for (let i = page - 1; i <= page + 1; i++) {
          pages.push(i)
        }
        pages.push('ellipsis')
        pages.push(currentTotalPages)
      }
    }

    return pages
  }


  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h1 className="text-2xl font-sans font-semibold text-text-primary">
                Corporate Announcements
              </h1>
              <div className="flex items-center gap-1.5 px-2 py-0.5 bg-success/10 rounded-full">
                <Radio className={`w-3 h-3 text-success ${wsConnected ? 'animate-pulse' : ''}`} />
                <span className="text-[10px] font-sans text-success font-medium uppercase tracking-wider">
                  {wsConnected ? 'LIVE' : 'OFFLINE'}
                </span>
              </div>
            </div>
            <p className="text-xs font-sans text-text-secondary">
              Real-time corporate announcements
              {lastRefresh && (
                <span className="ml-2">
                  • Last updated: {lastRefresh.toLocaleTimeString()}
                </span>
              )}
            </p>
          </div>
        </div>
        
        {/* Search and Filters */}
        <div className="flex flex-wrap items-center gap-3 p-4 bg-panel border border-border rounded">
          {/* Search Input */}
          <div className="relative flex-1 min-w-[200px]">
            <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-secondary" />
            <input
              type="text"
              placeholder="Search by headline or symbol"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleSearch()
                }
              }}
              className="w-full pl-8 pr-3 py-2 text-sm border border-border rounded bg-background text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>

          {/* Search Button */}
          <Button
            variant="primary"
            size="sm"
            onClick={handleSearch}
            className="px-4 whitespace-nowrap"
          >
            Search
          </Button>

          {/* Date Range */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <input
                type="date"
                value={searchFromDateInput}
                onChange={(e) => setSearchFromDateInput(e.target.value)}
                className="px-3 py-2 pr-8 text-sm border border-border rounded bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary/30 [color-scheme:light] [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
                style={{
                  WebkitAppearance: 'none',
                  MozAppearance: 'textfield'
                } as React.CSSProperties}
                title="From Date"
                id="from-date-input"
              />
              <label
                htmlFor="from-date-input"
                className="absolute right-2 top-1/2 transform -translate-y-1/2 cursor-pointer z-10 pointer-events-auto"
                onClick={(e) => {
                  e.preventDefault()
                  document.getElementById('from-date-input')?.showPicker?.() || document.getElementById('from-date-input')?.focus()
                }}
              >
                <Calendar className="w-4 h-4 text-white drop-shadow-md" />
              </label>
            </div>
            <span className="text-text-secondary text-sm">to</span>
            <div className="relative">
              <input
                type="date"
                value={searchToDateInput}
                onChange={(e) => setSearchToDateInput(e.target.value)}
                className="px-3 py-2 pr-8 text-sm border border-border rounded bg-white text-gray-900 focus:outline-none focus:ring-2 focus:ring-primary/30 [color-scheme:light] [&::-webkit-calendar-picker-indicator]:hidden [&::-webkit-calendar-picker-indicator]:appearance-none"
                style={{
                  WebkitAppearance: 'none',
                  MozAppearance: 'textfield'
                } as React.CSSProperties}
                title="To Date"
                id="to-date-input"
              />
              <label
                htmlFor="to-date-input"
                className="absolute right-2 top-1/2 transform -translate-y-1/2 cursor-pointer z-10 pointer-events-auto"
                onClick={(e) => {
                  e.preventDefault()
                  document.getElementById('to-date-input')?.showPicker?.() || document.getElementById('to-date-input')?.focus()
                }}
              >
                <Calendar className="w-4 h-4 text-white drop-shadow-md" />
              </label>
            </div>
          </div>

          {/* Clear All Button - Always visible when any filter is active */}
          {(searchQuery || searchFromDate || searchToDate || searchInput || searchFromDateInput || searchToDateInput) && (
            <Button
              variant="secondary"
              size="sm"
              onClick={handleClearAll}
              className="px-4 whitespace-nowrap"
            >
              Clear All
            </Button>
          )}
        </div>

      {/* Announcements Table */}
      <Card compact>
        <Table>
          <TableHeader>
            <TableHeaderCell>Date / Time</TableHeaderCell>
            <TableHeaderCell>Symbol</TableHeaderCell>
            <TableHeaderCell>Company Name</TableHeaderCell>
            <TableHeaderCell>Headline</TableHeaderCell>
            <TableHeaderCell>Links & Attachments</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
          </TableHeader>
          <TableBody>
            {error ? (
              <TableRow index={0}>
                <TableCell colSpan={6} className="text-center py-8 text-error">
                  {error}
                </TableCell>
              </TableRow>
            ) : loading && announcements.length === 0 ? (
              <TableRow index={0}>
                <TableCell colSpan={6} className="px-3 py-12 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    <p className="text-text-secondary">Loading announcements...</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : announcements.length === 0 && !loading ? (
              <TableRow index={0}>
                <TableCell colSpan={6} className="text-center py-8 text-text-secondary">
                  No announcements available
                </TableCell>
              </TableRow>
            ) : paginatedGroups.map((group, groupIndex) => {
                const hasMultipleItems = group.items.length > 1
                const isGroupExpanded = expandedGroups.has(group.key)
                const firstAnn = group.items[0]
                const dateTime = formatDate(group.dateTime)
                
                // Helper to render date/time cell with consistent arrow alignment
                const renderDateTimeCell = (dateTimeValue: ReturnType<typeof formatDate>, showArrow: boolean, isExpanded: boolean, onToggle: () => void) => (
                  <TableCell className="text-text-secondary align-top py-2">
                    <div className="flex items-center gap-2">
                      <div className="w-5 flex items-center justify-center flex-shrink-0">
                        {showArrow && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              onToggle()
                            }}
                            className="p-0.5 hover:bg-panel rounded transition-colors"
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4" />
                            ) : (
                              <ChevronRightIcon className="w-4 h-4" />
                            )}
                          </button>
                        )}
                      </div>
                      <div className="text-xs leading-tight">
                        <div>{dateTimeValue.date}</div>
                        {dateTimeValue.time && <div className="text-[10px] mt-0.5">{dateTimeValue.time}</div>}
                      </div>
                    </div>
                  </TableCell>
                )
                
                // Helper to render a single announcement row
                const renderAnnouncementRow = (ann: Announcement, index: number, isSubRow: boolean = false) => {
                  const annDateTime = formatDate(ann.trade_date)
                  const annSymbol = formatSymbol(ann)
                  const isExpanded = expandedRows.has(ann.id)
                  const shouldShowExpand = needsExpansionMap.get(ann.id) || false
                  const headline = ann.news_headline || 'N/A'
                  const description = ann.news_body || ''
                  const announcementHasLinks = hasLinks(ann)
                  const links = ann.links || []
                  
                  return (
                    <TableRow
                      key={ann.id}
                      index={index}
                      className={`hover:bg-panel-hover ${isSubRow ? 'bg-blue-500/12 border-l-[3px] border-l-blue-500/50' : ''}`}
                    >
                      {/* Date / Time - Perfect alignment for expanded rows (no extra indentation) */}
                      {isSubRow ? (
                        // Sub-rows align exactly with parent rows - no extra padding
                        renderDateTimeCell(annDateTime, false, false, () => {})
                      ) : (
                        renderDateTimeCell(annDateTime, false, false, () => {})
                      )}
                      
                      {/* Symbol - Stacked NSE/BSE */}
                      <TableCell className="align-top py-2">
                        <div className="text-xs leading-tight">
                          {annSymbol.nse && <div>NSE: {annSymbol.nse}</div>}
                          {annSymbol.bse && <div className="mt-0.5">BSE: {annSymbol.bse}</div>}
                          {!annSymbol.nse && !annSymbol.bse && <div className="text-text-secondary">N/A</div>}
                        </div>
                      </TableCell>
                      
                      {/* Company Name */}
                      <TableCell className="align-top py-2">
                        <div className="text-xs text-text-primary break-words max-w-[150px]">
                          {ann.company_name || ''}
                        </div>
                      </TableCell>
                      
                      {/* Headline + Description - Description-only expansion */}
                      <TableCell className="align-top py-2 max-w-md">
                        <div className="text-sm">
                          {/* Headline - Always fully visible */}
                          <div className="font-semibold break-words mb-1">{headline}</div>
                          
                          {/* Description */}
                          {description ? (
                            <>
                              {isExpanded ? (
                                <>
                                  <div className="text-xs text-text-secondary whitespace-pre-wrap break-words">
                                    {description}
                                  </div>
                                  {shouldShowExpand && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        toggleExpand(ann.id, description)
                                      }}
                                      className="mt-1 text-xs text-primary hover:text-primary-dark flex items-center gap-1"
                                    >
                                      <ChevronDown className="w-3 h-3" />
                                      Collapse
                                    </button>
                                  )}
                                </>
                              ) : (
                                <>
                                  <div
                                    ref={(el) => {
                                      if (el) {
                                        descriptionRefs.current.set(ann.id, el)
                                        // Check overflow after ref is set
                                        setTimeout(() => {
                                          checkDescriptionOverflow(ann.id, description)
                                        }, 0)
                                      } else {
                                        descriptionRefs.current.delete(ann.id)
                                      }
                                    }}
                                    className="text-xs text-text-secondary whitespace-pre-wrap break-words"
                                    style={{
                                      display: '-webkit-box',
                                      WebkitLineClamp: MAX_VISIBLE_LINES,
                                      WebkitBoxOrient: 'vertical',
                                      overflow: 'hidden'
                                    }}
                                  >
                                    {description}
                                  </div>
                                  {shouldShowExpand && (
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        toggleExpand(ann.id, description)
                                      }}
                                      className="mt-1 text-xs text-primary hover:text-primary-dark flex items-center gap-1"
                                    >
                                      <ChevronRightIcon className="w-3 h-3" />
                                      Expand
                                    </button>
                                  )}
                                </>
                              )}
                            </>
                          ) : null}
                        </div>
                      </TableCell>
                      
                      {/* Links & Attachments */}
                      <TableCell className="align-top py-2">
                        <div className="flex flex-col gap-1">
                          {/* Links - always show if available */}
                          {announcementHasLinks ? (
                            <div className="relative links-menu-container">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setOpenLinksMenu(openLinksMenu === ann.id ? null : ann.id)
                                }}
                                className="text-xs text-primary hover:text-primary-dark flex items-center gap-1"
                              >
                                Links ({links.filter(l => l.url).length})
                              </button>
                              
                              {openLinksMenu === ann.id && (
                                <div 
                                  className="absolute right-0 mt-1 bg-panel border border-border rounded shadow-lg z-50 min-w-[200px] max-w-[300px]"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <div className="p-2 max-h-64 overflow-y-auto">
                                    {links.filter(l => l.url).map((link, idx) => (
                                      <a
                                        key={idx}
                                        href={link.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="block py-1.5 px-2 text-xs text-text-primary hover:bg-panel-hover rounded break-words"
                                      >
                                        {link.title || link.url}
                                      </a>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          ) : null}
                          
                          {/* Attachments - always show, fetch on-demand */}
                          <div className="flex flex-col gap-1">
                            {attachmentErrors.has(ann.id) ? (
                              <div className="text-xs text-red-400 flex items-center gap-1">
                                <AlertCircle className="w-3 h-3" />
                                <span className="max-w-[150px] truncate" title={attachmentErrors.get(ann.id)}>
                                  {attachmentErrors.get(ann.id)}
                                </span>
                              </div>
                            ) : (
                              <>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleViewAttachment(ann.id)
                                  }}
                                  disabled={viewingAttachment.has(ann.id) || downloadingAttachment.has(ann.id)}
                                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1.5 disabled:opacity-50 transition-colors"
                                  title="View attachment in new tab"
                                >
                                  {viewingAttachment.has(ann.id) ? (
                                    <>
                                      <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                                      Loading...
                                    </>
                                  ) : (
                                    <>
                                      <Eye className="w-3.5 h-3.5 text-blue-400" />
                                      <span className="text-blue-400">View</span>
                                    </>
                                  )}
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    handleDownloadAttachment(ann.id)
                                  }}
                                  disabled={downloadingAttachment.has(ann.id) || viewingAttachment.has(ann.id)}
                                  className="text-xs text-green-400 hover:text-green-300 flex items-center gap-1.5 disabled:opacity-50 transition-colors"
                                  title="Download attachment"
                                >
                                  {downloadingAttachment.has(ann.id) ? (
                                    <>
                                      <div className="w-3 h-3 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                                      Downloading...
                                    </>
                                  ) : (
                                    <>
                                      <Download className="w-3.5 h-3.5 text-green-400" />
                                      <span className="text-green-400">Download</span>
                                    </>
                                  )}
                                </button>
                              </>
                            )}
                          </div>
                        </div>
                      </TableCell>
                      
                      {/* Type */}
                      <TableCell className="align-top py-2 text-xs text-text-secondary">
                        {ann.announcement_type || 'N/A'}
                      </TableCell>
                    </TableRow>
                  )
                }

                // If only 1 item in group, render it directly with arrow placeholder for alignment
                if (!hasMultipleItems) {
                  const singleRowDateTime = formatDate(firstAnn.trade_date)
                  return (
                    <TableRow
                      key={firstAnn.id}
                      index={groupIndex}
                      className="hover:bg-panel-hover"
                    >
                      {renderDateTimeCell(singleRowDateTime, false, false, () => {})}
                      {(() => {
                        const symbol = formatSymbol(firstAnn)
                        const isExpanded = expandedRows.has(firstAnn.id)
                        const shouldShowExpand = needsExpansionMap.get(firstAnn.id) || false
                        const headline = firstAnn.news_headline || 'N/A'
                        const description = firstAnn.news_body || ''
                        const announcementHasLinks = hasLinks(firstAnn)
                        const links = firstAnn.links || []
                        
                        return (
                          <>
                            {/* Symbol - Stacked NSE/BSE */}
                            <TableCell className="align-top py-2">
                              <div className="text-xs leading-tight">
                                {symbol.nse && <div>NSE: {symbol.nse}</div>}
                                {symbol.bse && <div className="mt-0.5">BSE: {symbol.bse}</div>}
                                {!symbol.nse && !symbol.bse && <div className="text-text-secondary">N/A</div>}
                              </div>
                            </TableCell>
                            
                            {/* Company Name */}
                            <TableCell className="align-top py-2">
                              <div className="text-xs text-text-primary break-words max-w-[150px]">
                                {firstAnn.company_name || ''}
                              </div>
                            </TableCell>
                            
                            {/* Headline + Description */}
                            <TableCell className="align-top py-2 max-w-md">
                              <div className="text-sm">
                                <div className="font-semibold break-words mb-1">{headline}</div>
                                {description ? (
                                  <>
                                    {isExpanded ? (
                                      <>
                                        <div className="text-xs text-text-secondary whitespace-pre-wrap break-words">
                                          {description}
                                        </div>
                                        {shouldShowExpand && (
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              toggleExpand(firstAnn.id, description)
                                            }}
                                            className="mt-1 text-xs text-primary hover:text-primary-dark flex items-center gap-1"
                                          >
                                            <ChevronDown className="w-3 h-3" />
                                            Collapse
                                          </button>
                                        )}
                                      </>
                                    ) : (
                                      <>
                                        <div
                                          ref={(el) => {
                                            if (el) {
                                              descriptionRefs.current.set(firstAnn.id, el)
                                              setTimeout(() => {
                                                checkDescriptionOverflow(firstAnn.id, description)
                                              }, 0)
                                            } else {
                                              descriptionRefs.current.delete(firstAnn.id)
                                            }
                                          }}
                                          className="text-xs text-text-secondary whitespace-pre-wrap break-words"
                                          style={{
                                            display: '-webkit-box',
                                            WebkitLineClamp: MAX_VISIBLE_LINES,
                                            WebkitBoxOrient: 'vertical',
                                            overflow: 'hidden'
                                          }}
                                        >
                                          {description}
                                        </div>
                                        {shouldShowExpand && (
                                          <button
                                            onClick={(e) => {
                                              e.stopPropagation()
                                              toggleExpand(firstAnn.id, description)
                                            }}
                                            className="mt-1 text-xs text-primary hover:text-primary-dark flex items-center gap-1"
                                          >
                                            <ChevronRightIcon className="w-3 h-3" />
                                            Expand
                                          </button>
                                        )}
                                      </>
                                    )}
                                  </>
                                ) : null}
                              </div>
                            </TableCell>
                            
                            {/* Links & Attachments */}
                            <TableCell className="align-top py-2">
                              <div className="flex flex-col gap-1">
                                {announcementHasLinks ? (
                                  <div className="relative links-menu-container">
                                    <button
                                      onClick={(e) => {
                                        e.stopPropagation()
                                        setOpenLinksMenu(openLinksMenu === firstAnn.id ? null : firstAnn.id)
                                      }}
                                      className="text-xs text-primary hover:text-primary-dark flex items-center gap-1"
                                    >
                                      Links ({links.filter(l => l.url).length})
                                    </button>
                                    
                                    {openLinksMenu === firstAnn.id && (
                                      <div 
                                        className="absolute right-0 mt-1 bg-panel border border-border rounded shadow-lg z-50 min-w-[200px] max-w-[300px]"
                                        onClick={(e) => e.stopPropagation()}
                                      >
                                        <div className="p-2 max-h-64 overflow-y-auto">
                                          {links.filter(l => l.url).map((link, idx) => (
                                            <a
                                              key={idx}
                                              href={link.url}
                                              target="_blank"
                                              rel="noopener noreferrer"
                                              className="block py-1.5 px-2 text-xs text-text-primary hover:bg-panel-hover rounded break-words"
                                            >
                                              {link.title || link.url}
                                            </a>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                ) : null}
                                
                                <div className="flex flex-col gap-1">
                                  {attachmentErrors.has(firstAnn.id) ? (
                                    <div className="text-xs text-red-400 flex items-center gap-1">
                                      <AlertCircle className="w-3 h-3" />
                                      <span className="max-w-[150px] truncate" title={attachmentErrors.get(firstAnn.id)}>
                                        {attachmentErrors.get(firstAnn.id)}
                                      </span>
                                    </div>
                                  ) : (
                                    <>
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          handleViewAttachment(firstAnn.id)
                                        }}
                                        disabled={viewingAttachment.has(firstAnn.id) || downloadingAttachment.has(firstAnn.id)}
                                        className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1.5 disabled:opacity-50 transition-colors"
                                        title="View attachment in new tab"
                                      >
                                        {viewingAttachment.has(firstAnn.id) ? (
                                          <>
                                            <div className="w-3 h-3 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
                                            Loading...
                                          </>
                                        ) : (
                                          <>
                                            <Eye className="w-3.5 h-3.5 text-blue-400" />
                                            <span className="text-blue-400">View</span>
                                          </>
                                        )}
                                      </button>
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          handleDownloadAttachment(firstAnn.id)
                                        }}
                                        disabled={downloadingAttachment.has(firstAnn.id) || viewingAttachment.has(firstAnn.id)}
                                        className="text-xs text-green-400 hover:text-green-300 flex items-center gap-1.5 disabled:opacity-50 transition-colors"
                                        title="Download attachment"
                                      >
                                        {downloadingAttachment.has(firstAnn.id) ? (
                                          <>
                                            <div className="w-3 h-3 border-2 border-green-400 border-t-transparent rounded-full animate-spin" />
                                            Downloading...
                                          </>
                                        ) : (
                                          <>
                                            <Download className="w-3.5 h-3.5 text-green-400" />
                                            <span className="text-green-400">Download</span>
                                          </>
                                        )}
                                      </button>
                                    </>
                                  )}
                                </div>
                              </div>
                            </TableCell>
                            
                            {/* Type */}
                            <TableCell className="align-top py-2 text-xs text-text-secondary">
                              {firstAnn.announcement_type || 'N/A'}
                            </TableCell>
                          </>
                        )
                      })()}
                    </TableRow>
                  )
                }

                // Multiple items - render group header with expand/collapse
                return (
                  <React.Fragment key={group.key}>
                    {/* Group Header Row */}
                    <TableRow
                      index={groupIndex}
                      className="hover:bg-panel-hover cursor-pointer"
                      onClick={() => toggleGroup(group.key)}
                    >
                      {/* Date / Time with expander - using helper for consistent alignment */}
                      {renderDateTimeCell(dateTime, true, isGroupExpanded, () => toggleGroup(group.key))}
                      
                      {/* Symbol column - show only count for grouped items with LIVE indicator style */}
                      <TableCell className="align-top py-2">
                        <div className="inline-flex items-center justify-center gap-1.5 px-2 py-0.5 bg-success/10 border border-success/30 rounded-full text-xs font-medium text-success whitespace-nowrap">
                          Group {group.items.length}
                        </div>
                      </TableCell>
                      
                      {/* Company Name */}
                      <TableCell className="align-top py-2">
                        <div className="text-xs text-text-primary break-words max-w-[150px]">
                          {firstAnn.company_name || ''}
                        </div>
                      </TableCell>
                      
                      {/* Headline */}
                      <TableCell className="align-top py-2 max-w-md">
                        <div className="text-sm">
                          <div className="font-semibold break-words mb-1">{group.headline}</div>
                          <div className="text-xs text-text-secondary">
                            {isGroupExpanded ? 'Click to collapse' : `${group.items.length} similar announcements`}
                          </div>
                        </div>
                      </TableCell>
                      
                      {/* Links & Attachments placeholder */}
                      <TableCell className="align-top py-2">
                        <div className="text-xs text-text-secondary">
                          {isGroupExpanded ? '' : 'Expand to view'}
                        </div>
                      </TableCell>
                      
                      {/* Type */}
                      <TableCell className="align-top py-2 text-xs text-text-secondary">
                        {firstAnn.announcement_type || 'N/A'}
                      </TableCell>
                    </TableRow>
                    
                      {/* Expanded sub-rows */}
                      {isGroupExpanded && group.items.map((ann, itemIndex) => 
                        renderAnnouncementRow(ann, (page - 1) * pageSize + groupIndex * 1000 + itemIndex, true)
                      )}
                  </React.Fragment>
                )
              })}
          </TableBody>
        </Table>

        {/* Pagination Controls */}
        {(total > 0 || groupedCount > 0) && (
          <div className="mt-4 pt-4 border-t border-border flex items-center justify-between flex-wrap gap-4">
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

            {(searchQuery || searchFromDate || searchToDate ? totalPages >= 1 : groupedTotalPages >= 1) && (
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

                {getPageNumbers().map((pageNum, idx) => {
                  if (pageNum === 'ellipsis') {
                    return (
                      <span key={`ellipsis-${idx}`} className="px-2 text-text-secondary">
                        ...
                      </span>
                    )
                  }
                  const pageNumValue = pageNum as number
                  const isCurrentPage = pageNumValue === page
                  const isLoading = loading && pageNumValue === page
                  return (
                    <Button
                      key={pageNumValue}
                      variant={isCurrentPage ? 'primary' : 'ghost'}
                      size="sm"
                      onClick={() => handlePageChange(pageNumValue)}
                      disabled={loading}
                      className="min-w-[2rem] px-2 relative"
                    >
                      {isLoading ? (
                        <div className="flex items-center justify-center gap-1.5">
                          <div className="w-3 h-3 border-2 border-current border-t-transparent rounded-full animate-spin" />
                          <span>{pageNumValue}</span>
                        </div>
                      ) : (
                        pageNumValue
                      )}
                    </Button>
                  )
                })}

                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handlePageChange(page + 1)}
                  disabled={loading || page === (searchQuery || searchFromDate || searchToDate ? totalPages : groupedTotalPages)}
                  className="px-2"
                >
                  Next
                  <ChevronRight className="w-4 h-4" />
                </Button>
              </div>
            )}

            <div className="text-sm text-text-secondary">
              Showing{' '}
              <span className="font-semibold text-text-primary">
                {searchQuery || searchFromDate || searchToDate 
                  ? `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, total)}`
                  : groupedCount === 0 
                    ? '0' 
                    : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, groupedCount)}`
                }
              </span>{' '}
              of{' '}
              <span className="font-semibold text-text-primary">
                {searchQuery || searchFromDate || searchToDate 
                  ? total.toLocaleString() 
                  : groupedCount.toLocaleString()
                }
              </span>{' '}
              {searchQuery || searchFromDate || searchToDate 
                ? 'announcements'
                : `groups (${total.toLocaleString()} total announcements)`
              }
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
