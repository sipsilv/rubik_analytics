'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useState, useEffect } from 'react'
import { useSearchParams } from 'next/navigation'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { Search, Download, X, ArrowLeft } from 'lucide-react'
import { useRouter } from 'next/navigation'
import { ApproveRequestModal } from '@/components/ApproveRequestModal'
import { RejectRequestModal } from '@/components/RejectRequestModal'
import { RefreshButton } from '@/components/ui/RefreshButton'

interface AccessRequest {
  id: number
  name: string
  email: string | null
  mobile: string
  company: string | null
  reason: string
  requested_role: string
  request_type: string
  status: string
  created_at: string
  reviewed_by: number | null
  reviewed_at: string | null
}

export default function RequestsPage() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [requests, setRequests] = useState<AccessRequest[]>([])
  const [loading, setLoading] = useState(true)
  const urlFilter = searchParams?.get('filter') as 'all' | 'pending' | 'approved' | 'rejected' | null
  const [filter, setFilter] = useState<'all' | 'pending' | 'approved' | 'rejected'>(urlFilter || 'all')
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [approveModalOpen, setApproveModalOpen] = useState(false)
  const [rejectModalOpen, setRejectModalOpen] = useState(false)
  const [selectedRequest, setSelectedRequest] = useState<AccessRequest | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [approveSuccessData, setApproveSuccessData] = useState<any>(null)
  const [rejectSuccess, setRejectSuccess] = useState(false)

  // Update filter from URL params
  useEffect(() => {
    if (urlFilter && ['all', 'pending', 'approved', 'rejected'].includes(urlFilter)) {
      setFilter(urlFilter)
    }
  }, [urlFilter])

  useEffect(() => {
    loadRequests()
  }, [filter])

  const loadRequests = async () => {
    try {
      setLoading(true)
      const status = filter === 'all' ? undefined : filter
      const data = await adminAPI.getRequests(status)
      setRequests(data)
    } catch (error) {
      console.error('Failed to load requests:', error)
      setRequests([])
    } finally {
      setLoading(false)
    }
  }

  const handleApproveClick = (request: AccessRequest) => {
    setSelectedRequest(request)
    setApproveModalOpen(true)
  }

  const handleApprove = async () => {
    if (!selectedRequest) return
    setActionLoading(true)
    try {
      const result = await adminAPI.approveRequest(String(selectedRequest.id))
      const userInfo = result.user
      // Show success in the same modal
      setApproveSuccessData({
        user_id: userInfo.user_id,
        username: userInfo.username,
        email: userInfo.email,
        mobile: userInfo.mobile,
        role: userInfo.role,
        temp_password: userInfo.temp_password
      })
      loadRequests()
    } catch (error: any) {
      console.error('Failed to approve request:', error)
      setApproveModalOpen(false)
      setSelectedRequest(null)
      setApproveSuccessData(null)
      alert(getErrorMessage(error, 'Failed to approve request'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleApproveClose = () => {
    setApproveModalOpen(false)
    setSelectedRequest(null)
    setApproveSuccessData(null)
  }

  const handleRejectClick = (request: AccessRequest) => {
    setSelectedRequest(request)
    setRejectModalOpen(true)
  }

  const handleReject = async (reason?: string) => {
    if (!selectedRequest) return
    setActionLoading(true)
    try {
      await adminAPI.rejectRequest(String(selectedRequest.id), reason)
      // Show success in the same modal
      setRejectSuccess(true)
      loadRequests()
    } catch (error: any) {
      console.error('Failed to reject request:', error)
      setRejectModalOpen(false)
      setSelectedRequest(null)
      setRejectSuccess(false)
      alert(getErrorMessage(error, 'Failed to reject request'))
    } finally {
      setActionLoading(false)
    }
  }

  const handleRejectClose = () => {
    setRejectModalOpen(false)
    setSelectedRequest(null)
    setRejectSuccess(false)
  }

  const getStatusBadge = (status: string) => {
    const colors = {
      pending: 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400',
      approved: 'bg-success/10 text-success',
      rejected: 'bg-red-500/10 text-red-600 dark:text-red-400',
    }
    return (
      <span className={`text-[10px] font-sans px-1.5 py-0.5 rounded uppercase ${colors[status as keyof typeof colors] || 'bg-gray-500/10 text-gray-600'}`}>
        {status}
      </span>
    )
  }

  const getRoleBadge = (role: string) => {
    return (
      <span className="text-[10px] font-sans px-1.5 py-0.5 bg-primary/10 text-primary rounded uppercase">
        {role.toUpperCase()}
      </span>
    )
  }

  const filteredRequests = requests.filter(req => {
    // Apply status filter
    if (filter !== 'all' && req.status !== filter) {
      return false
    }
    
    // Apply search filter (use searchQuery - the applied search, not the input value)
    if (searchQuery.trim()) {
      const searchLower = searchQuery.toLowerCase().trim()
      
      // Format dates for searching
      const formatDateForSearch = (dateString: string) => {
        try {
          const date = new Date(dateString)
          // Multiple date formats for flexible searching
          const formats = [
            date.toLocaleDateString(), // e.g., "1/15/2024"
            date.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' }), // e.g., "01/15/2024"
            date.toISOString().split('T')[0], // e.g., "2024-01-15"
            date.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }), // e.g., "January 15, 2024"
            date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }), // e.g., "Jan 15, 2024"
            date.getFullYear().toString(), // e.g., "2024"
            (date.getMonth() + 1).toString().padStart(2, '0'), // e.g., "01"
            date.getDate().toString(), // e.g., "15"
            date.getDate().toString().padStart(2, '0'), // e.g., "15"
          ]
          return formats.map(f => f.toLowerCase()).join(' ')
        } catch {
          return ''
        }
      }
      
      // Check created_at date
      const createdDateSearch = req.created_at ? formatDateForSearch(req.created_at) : ''
      
      // Check reviewed_at date if exists
      const reviewedDateSearch = req.reviewed_at ? formatDateForSearch(req.reviewed_at) : ''
      
      return (
        req.name?.toLowerCase().includes(searchLower) ||
        req.email?.toLowerCase().includes(searchLower) ||
        req.mobile?.toLowerCase().includes(searchLower) ||
        req.company?.toLowerCase().includes(searchLower) ||
        req.reason?.toLowerCase().includes(searchLower) ||
        createdDateSearch.includes(searchLower) ||
        reviewedDateSearch.includes(searchLower)
      )
    }
    
    return true
  })
  
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

  const handleDownload = () => {
    // Use filtered requests (respects current filter and search)
    const dataToExport = filteredRequests.length > 0 ? filteredRequests : requests
    
    if (dataToExport.length === 0) {
      alert('No requests to download')
      return
    }

    // Create CSV headers
    const headers = [
      'ID',
      'Name',
      'Email',
      'Mobile',
      'Company',
      'Reason',
      'Requested Role',
      'Request Type',
      'Status',
      'Created At',
      'Reviewed At'
    ]

    // Convert requests to CSV rows
    const rows = dataToExport.map(request => [
      request.id.toString(),
      request.name || '',
      request.email || '',
      request.mobile || '',
      request.company || '',
      (request.reason || '').replace(/"/g, '""'), // Escape quotes in CSV
      request.requested_role || '',
      request.request_type || '',
      request.status || '',
      request.created_at ? new Date(request.created_at).toLocaleString() : '',
      request.reviewed_at ? new Date(request.reviewed_at).toLocaleString() : ''
    ])

    // Combine headers and rows
    const csvContent = [
      headers.map(h => `"${h}"`).join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n')

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const link = document.createElement('a')
    const url = URL.createObjectURL(blob)
    
    const timestamp = new Date().toISOString().split('T')[0]
    const filename = `access_requests_${filter !== 'all' ? filter + '_' : ''}${timestamp}.csv`
    
    link.setAttribute('href', url)
    link.setAttribute('download', filename)
    link.style.visibility = 'hidden'
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    // Clean up
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push('/admin/requests-feedback')}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
            Access Requests
          </h1>
          <p className="text-xs font-sans text-text-secondary">
            Review and manage new user access requests
          </p>
        </div>
      </div>
      
      <div className="flex items-center justify-between">
        <div></div>
        <div className="flex gap-2 items-center">
          <RefreshButton
            variant="secondary"
            onClick={async () => {
              await loadRequests()
            }}
            size="sm"
            disabled={loading}
          />
          <Button
            size="sm"
            variant={filter === 'all' ? 'primary' : 'ghost'}
            onClick={() => setFilter('all')}
          >
            All
          </Button>
          <Button
            size="sm"
            variant={filter === 'pending' ? 'primary' : 'ghost'}
            onClick={() => setFilter('pending')}
          >
            Pending
          </Button>
          <Button
            size="sm"
            variant={filter === 'approved' ? 'primary' : 'ghost'}
            onClick={() => setFilter('approved')}
          >
            Approved
          </Button>
          <Button
            size="sm"
            variant={filter === 'rejected' ? 'primary' : 'ghost'}
            onClick={() => setFilter('rejected')}
          >
            Rejected
          </Button>
          <Button
            size="sm"
            variant="primary"
            onClick={handleDownload}
            disabled={loading || (filteredRequests.length === 0 && requests.length === 0)}
            className="ml-2"
          >
            <Download className="w-4 h-4 mr-1.5" />
            Download
          </Button>
        </div>
      </div>

      <Card compact>
        {/* Search Input */}
        <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div className="flex-1 max-w-md">
              <Input
                type="text"
                placeholder="Search requests (name, email, mobile, company, reason, date)..."
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

        {loading ? (
          <div className="text-center py-8 text-xs font-sans text-text-secondary">Loading...</div>
        ) : filteredRequests.length === 0 ? (
          <div className="text-center py-8 text-xs font-sans text-text-secondary">
            {searchQuery ? (
              <>No requests found matching "{searchQuery}"</>
            ) : (
              <>No {filter !== 'all' ? filter : ''} requests found</>
            )}
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableHeaderCell>Name</TableHeaderCell>
              <TableHeaderCell>Email</TableHeaderCell>
              <TableHeaderCell>Mobile</TableHeaderCell>
              <TableHeaderCell>Company</TableHeaderCell>
              <TableHeaderCell>Requested Role</TableHeaderCell>
              <TableHeaderCell>Reason</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Requested</TableHeaderCell>
              <TableHeaderCell className="text-right">Actions</TableHeaderCell>
            </TableHeader>
            <TableBody>
              {filteredRequests.map((request, index) => (
                <TableRow key={request.id} index={index}>
                  <TableCell className="font-medium">{request.name}</TableCell>
                  <TableCell className="text-text-secondary">{request.email || 'N/A'}</TableCell>
                  <TableCell className="text-text-secondary font-mono text-xs">{request.mobile}</TableCell>
                  <TableCell className="text-text-secondary">{request.company || 'N/A'}</TableCell>
                  <TableCell>{getRoleBadge(request.requested_role)}</TableCell>
                  <TableCell className="max-w-xs truncate text-text-secondary">{request.reason}</TableCell>
                  <TableCell>{getStatusBadge(request.status)}</TableCell>
                  <TableCell className="font-sans text-xs text-text-secondary">
                    {new Date(request.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1 justify-end">
                      {request.status === 'pending' && (
                        <>
                          <Button 
                            variant="primary" 
                            size="sm"
                            onClick={() => handleApproveClick(request)}
                          >
                            Approve
                          </Button>
                          <Button 
                            variant="danger" 
                            size="sm"
                            onClick={() => handleRejectClick(request)}
                          >
                            Reject
                          </Button>
                        </>
                      )}
                      {request.status !== 'pending' && (
                        <span className="text-xs text-text-secondary">
                          {request.reviewed_at ? `Reviewed ${new Date(request.reviewed_at).toLocaleDateString()}` : 'N/A'}
                        </span>
                      )}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Card>

      <ApproveRequestModal
        isOpen={approveModalOpen}
        onClose={handleApproveClose}
        onConfirm={handleApprove}
        loading={actionLoading}
        request={selectedRequest ? {
          name: selectedRequest.name,
          email: selectedRequest.email,
          mobile: selectedRequest.mobile,
          company: selectedRequest.company
        } : undefined}
        successData={approveSuccessData}
      />

      <RejectRequestModal
        isOpen={rejectModalOpen}
        onClose={handleRejectClose}
        onConfirm={handleReject}
        loading={actionLoading}
        request={selectedRequest ? {
          name: selectedRequest.name,
          email: selectedRequest.email,
          mobile: selectedRequest.mobile,
          company: selectedRequest.company
        } : undefined}
        success={rejectSuccess}
      />
    </div>
  )
}
