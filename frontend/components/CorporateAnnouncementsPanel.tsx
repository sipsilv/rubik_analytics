'use client'

import React, { useState, useEffect, useMemo } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { announcementsAPI } from '@/lib/api'
import { useWebSocketStatus, AnnouncementUpdate } from '@/lib/useWebSocket'
import { ChevronDown, ChevronRight } from 'lucide-react'

interface Announcement {
  id: string
  trade_date?: string
  symbol_nse?: string
  symbol_bse?: string
  company_name?: string
  news_headline?: string
  descriptor_name?: string
  announcement_type?: string
}

interface AnnouncementsResponse {
  announcements: Announcement[]
  total: number
  limit?: number
  offset: number
}

interface GroupedAnnouncement {
  key: string
  dateTime: string
  headline: string
  symbol: string
  companyName: string
  descriptor: string
  type: string
  items: Announcement[]
  isExpanded: boolean
}

export function CorporateAnnouncementsPanel() {
  const [announcements, setAnnouncements] = useState<Announcement[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedAnnouncement, setSelectedAnnouncement] = useState<Announcement | null>(null)
  const [showDetails, setShowDetails] = useState(false)
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())

  // Handle real-time announcements from WebSocket
  const handleNewAnnouncement = (newAnnouncement: AnnouncementUpdate) => {
    // Convert AnnouncementUpdate to Announcement format
    const announcement: Announcement = {
      id: newAnnouncement.id,
      trade_date: newAnnouncement.trade_date,
      symbol_nse: newAnnouncement.symbol_nse,
      symbol_bse: newAnnouncement.symbol_bse,
      company_name: newAnnouncement.company_name,
      news_headline: newAnnouncement.news_headline,
      descriptor_name: newAnnouncement.descriptor_name,
      announcement_type: newAnnouncement.announcement_type,
    }

    // Add to the beginning of the list (most recent first)
    setAnnouncements((prev) => {
      // Check if announcement already exists (avoid duplicates)
      const exists = prev.some((ann) => ann.id === announcement.id)
      if (exists) {
        return prev
      }
      // Insert at the beginning
      return [announcement, ...prev]
    })
  }

  // Connect to WebSocket for real-time updates
  useWebSocketStatus(undefined, handleNewAnnouncement)

  useEffect(() => {
    loadAnnouncements()
  }, [])

  const loadAnnouncements = async () => {
    try {
      setLoading(true)
      setError(null)
      const response: AnnouncementsResponse = await announcementsAPI.getAnnouncements({
        limit: 50
      })
      setAnnouncements(response.announcements || [])
    } catch (err: any) {
      setError(err.message || 'Failed to load announcements')
      console.error('Error loading announcements:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'N/A'
    try {
      const date = new Date(dateStr)
      // Explicitly use Asia/Kolkata timezone to match Windows server timezone
      const formatter = new Intl.DateTimeFormat('en-IN', {
        timeZone: 'Asia/Kolkata',
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
      return formatter.format(date)
    } catch {
      return dateStr
    }
  }

  const getSymbol = (ann: Announcement) => {
    return ann.symbol_nse || ann.symbol_bse || 'N/A'
  }

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

  // Group announcements by date/time and headline (or symbol if headline is same)
  const groupedAnnouncements = useMemo(() => {
    const groups = new Map<string, GroupedAnnouncement>()
    
    announcements.forEach((ann) => {
      const normalizedDateTime = normalizeDateTime(ann.trade_date)
      const headline = (ann.news_headline || '').trim().toLowerCase()
      const symbol = getSymbol(ann)
      
      // Create group key: date + headline (normalized)
      // If headline is empty or same, group by date+headline
      // This will group items with same date/time and same headline together
      const groupKey = headline 
        ? `${normalizedDateTime}|${headline}`
        : `${normalizedDateTime}|symbol:${symbol}`
      
      if (!groups.has(groupKey)) {
        const firstAnn = ann
        groups.set(groupKey, {
          key: groupKey,
          dateTime: firstAnn.trade_date || '',
          headline: firstAnn.news_headline || 'N/A',
          symbol: symbol,
          companyName: firstAnn.company_name || 'N/A',
          descriptor: firstAnn.descriptor_name || 'N/A',
          type: firstAnn.announcement_type || 'N/A',
          items: [ann],
          isExpanded: expandedGroups.has(groupKey),
        })
      } else {
        const group = groups.get(groupKey)!
        group.items.push(ann)
        // Keep the first symbol, or update if we find a more descriptive one
        if (symbol !== 'N/A' && group.symbol === 'N/A') {
          group.symbol = symbol
        } else if (symbol !== 'N/A' && (symbol.includes('NSE:') || symbol.includes('BSE:')) && !group.symbol.includes('NSE:') && !group.symbol.includes('BSE:')) {
          group.symbol = symbol
        }
        // Update company name if we find one that's not N/A
        if (ann.company_name && ann.company_name.trim() !== '' && ann.company_name !== 'N/A' && (group.companyName === 'N/A' || group.companyName === '')) {
          group.companyName = ann.company_name
        }
      }
    })
    
    return Array.from(groups.values()).sort((a, b) => {
      // Sort by date (most recent first)
      const dateA = new Date(a.dateTime).getTime()
      const dateB = new Date(b.dateTime).getTime()
      return dateB - dateA
    })
  }, [announcements, expandedGroups])

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

  const handleRowClick = async (announcement: Announcement) => {
    try {
      const fullAnnouncement = await announcementsAPI.getAnnouncement(announcement.id)
      setSelectedAnnouncement(fullAnnouncement)
      setShowDetails(true)
    } catch (err: any) {
      setError(err.message || 'Failed to load announcement details')
    }
  }

  if (loading) {
    return (
      <Card title="Corporate Announcements" compact>
        <div className="flex flex-col items-center justify-center py-12 gap-2">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
          <p className="text-text-secondary">Loading announcements...</p>
        </div>
      </Card>
    )
  }

  if (error) {
    return (
      <Card title="Corporate Announcements" compact>
        <div className="flex items-center justify-center py-8">
          <p className="text-xs font-sans text-error">{error}</p>
        </div>
      </Card>
    )
  }

  if (showDetails && selectedAnnouncement) {
    return (
      <Card title="Announcement Details" compact>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => {
                setShowDetails(false)
                setSelectedAnnouncement(null)
              }}
              className="text-xs font-sans text-primary hover:text-primary-dark"
            >
              ← Back to List
            </button>
          </div>

          <div className="space-y-3">
            <div>
              <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Date / Time</p>
              <p className="text-sm font-sans text-text-primary">{formatDate(selectedAnnouncement.trade_date)}</p>
            </div>

            <div>
              <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Symbol</p>
              <p className="text-sm font-sans text-text-primary">{getSymbol(selectedAnnouncement)}</p>
            </div>

            <div>
              <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Company Name</p>
              <p className="text-sm font-sans text-text-primary">{selectedAnnouncement.company_name || 'N/A'}</p>
            </div>

            <div>
              <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Headline</p>
              <p className="text-sm font-sans text-text-primary">{selectedAnnouncement.news_headline || 'N/A'}</p>
            </div>

            {(selectedAnnouncement as any).news_subhead && (
              <div>
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Sub-heading</p>
                <p className="text-sm font-sans text-text-primary">{(selectedAnnouncement as any).news_subhead}</p>
              </div>
            )}

            {(selectedAnnouncement as any).news_body && (
              <div>
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Body</p>
                <div className="text-sm font-sans text-text-primary whitespace-pre-wrap max-h-96 overflow-y-auto p-3 bg-panel rounded border border-border-subtle">
                  {(selectedAnnouncement as any).news_body}
                </div>
              </div>
            )}

            {selectedAnnouncement.descriptor_name && (
              <div>
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Descriptor</p>
                <p className="text-sm font-sans text-text-primary">{selectedAnnouncement.descriptor_name}</p>
              </div>
            )}

            {selectedAnnouncement.announcement_type && (
              <div>
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Announcement Type</p>
                <p className="text-sm font-sans text-text-primary">{selectedAnnouncement.announcement_type}</p>
              </div>
            )}

            {(selectedAnnouncement as any).date_of_meeting && (
              <div>
                <p className="text-xs font-sans text-text-secondary uppercase tracking-wider mb-1">Meeting Date</p>
                <p className="text-sm font-sans text-text-primary">{formatDate((selectedAnnouncement as any).date_of_meeting)}</p>
              </div>
            )}

            <div className="pt-2">
              <button
                onClick={async () => {
                  try {
                    const blob = await announcementsAPI.getAttachment(selectedAnnouncement.id)
                    const url = window.URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `announcement-${selectedAnnouncement.id}.pdf`
                    document.body.appendChild(a)
                    a.click()
                    window.URL.revokeObjectURL(url)
                    document.body.removeChild(a)
                  } catch (err: any) {
                    // Handle different error types with user-friendly messages
                    if (err.response?.status === 404) {
                      // File not found - don't show error, just silently fail
                      // (attachment may not be available for this announcement)
                      return
                    } else if (err.response?.status === 504 || err.response?.status === 503) {
                      // Timeout or service unavailable
                      setError(
                        err.response?.data?.detail || 
                        'Connection timed out. Please try again in a moment.'
                      )
                    } else if (err.response?.status >= 500) {
                      // Server error
                      setError(
                        err.response?.data?.detail || 
                        'Server error. Please try again later.'
                      )
                    } else {
                      // Other errors
                      const errorMsg = err.response?.data?.detail || err.message || 'Failed to download attachment'
                      setError(errorMsg)
                    }
                  }
                }}
                className="text-xs font-sans text-primary hover:text-primary-dark"
              >
                Download Attachment (if available)
              </button>
            </div>
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card title="Corporate Announcements" compact>
      {announcements.length === 0 ? (
        <div className="flex items-center justify-center py-8">
          <p className="text-xs font-sans text-text-secondary">No announcements available</p>
        </div>
      ) : (
        <Table>
          <TableHeader>
            <TableHeaderCell>Date / Time</TableHeaderCell>
            <TableHeaderCell>Symbol</TableHeaderCell>
            <TableHeaderCell>Company Name</TableHeaderCell>
            <TableHeaderCell>Headline</TableHeaderCell>
            <TableHeaderCell>Descriptor</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
          </TableHeader>
          <TableBody>
            {groupedAnnouncements.map((group, groupIndex) => {
              const isExpanded = expandedGroups.has(group.key)
              const hasMultipleItems = group.items.length > 1
              
              return (
                <React.Fragment key={group.key}>
                  {/* Group Header Row */}
                  <TableRow
                    index={groupIndex}
                    className="cursor-pointer hover:bg-panel-hover"
                    onClick={() => {
                      if (hasMultipleItems) {
                        // Toggle expand/collapse for grouped items
                        toggleGroup(group.key)
                      } else {
                        // Single item, open details directly
                        handleRowClick(group.items[0])
                      }
                    }}
                  >
                    <TableCell className="text-text-secondary">
                      <div className="flex items-center gap-2">
                        {hasMultipleItems && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation()
                              toggleGroup(group.key)
                            }}
                            className="p-0.5 hover:bg-panel rounded transition-colors"
                          >
                            {isExpanded ? (
                              <ChevronDown className="w-3 h-3" />
                            ) : (
                              <ChevronRight className="w-3 h-3" />
                            )}
                          </button>
                        )}
                        {formatDate(group.dateTime)}
                      </div>
                    </TableCell>
                    <TableCell>
                      {hasMultipleItems ? (
                        <span className="flex items-center gap-1">
                          {group.symbol}
                          <span className="text-xs text-text-secondary bg-panel px-1.5 py-0.5 rounded">
                            {group.items.length}
                          </span>
                        </span>
                      ) : (
                        group.symbol
                      )}
                    </TableCell>
                    <TableCell className="max-w-xs truncate">
                      {group.companyName}
                    </TableCell>
                    <TableCell className="max-w-md truncate">
                      {group.headline}
                    </TableCell>
                    <TableCell>{group.descriptor}</TableCell>
                    <TableCell>{group.type}</TableCell>
                  </TableRow>
                  
                  {/* Expanded Individual Items */}
                  {isExpanded && hasMultipleItems && group.items.map((ann, itemIndex) => (
                    <TableRow
                      key={ann.id}
                      index={groupIndex * 1000 + itemIndex}
                      onClick={() => handleRowClick(ann)}
                      className="cursor-pointer hover:bg-panel-hover bg-panel/50"
                    >
                      <TableCell className="text-text-secondary pl-8">
                        {formatDate(ann.trade_date)}
                      </TableCell>
                      <TableCell>{getSymbol(ann)}</TableCell>
                      <TableCell className="max-w-xs truncate">
                        {ann.company_name || 'N/A'}
                      </TableCell>
                      <TableCell className="max-w-md truncate">
                        {ann.news_headline || 'N/A'}
                      </TableCell>
                      <TableCell>{ann.descriptor_name || 'N/A'}</TableCell>
                      <TableCell>{ann.announcement_type || 'N/A'}</TableCell>
                    </TableRow>
                  ))}
                </React.Fragment>
              )
            })}
          </TableBody>
        </Table>
      )}
    </Card>
  )
}

