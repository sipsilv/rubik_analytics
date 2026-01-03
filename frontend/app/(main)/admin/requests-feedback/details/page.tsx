'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ArrowLeft, Search, X, Lightbulb, MessageSquare } from 'lucide-react'
import { createPortal } from 'react-dom'
import { adminAPI } from '@/lib/api'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { UnifiedSubmitModal } from '@/components/UnifiedSubmitModal'

interface FeatureRequest {
  id: number
  user_id: number
  user_name: string
  description: string
  context: any
  status: string
  ai_analysis: any
  admin_note: string | null
  reviewed_by: number | null
  reviewed_at: string | null
  created_at: string
  updated_at: string | null
}

interface Feedback {
  id: number
  user_id: number
  user_name: string
  subject: string
  message: string
  status: string
  created_at: string
}

type UnifiedItem = (FeatureRequest & { type: 'feature_request' }) | (Feedback & { type: 'feedback' })

export default function RequestsFeedbackDetailsPage() {
  const router = useRouter()
  const [unifiedItems, setUnifiedItems] = useState<UnifiedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [categoryFilter, setCategoryFilter] = useState<string>('')
  const [acceptanceStatusFilter, setAcceptanceStatusFilter] = useState<string>('')
  const [progressStatusFilter, setProgressStatusFilter] = useState<string>('')
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedItem, setSelectedItem] = useState<UnifiedItem | null>(null)
  const [adminNote, setAdminNote] = useState('')
  const [selectedStatus, setSelectedStatus] = useState<string>('')
  const [selectedProgressStatus, setSelectedProgressStatus] = useState<string>('')
  const [updating, setUpdating] = useState(false)
  const [isModalVisible, setIsModalVisible] = useState(false)

  useEffect(() => {
    loadUnifiedItems()
  }, [acceptanceStatusFilter, progressStatusFilter, categoryFilter, searchQuery])

  useEffect(() => {
    if (selectedItem) {
      // Reset visibility state first, then trigger animation after mount
      setIsModalVisible(false)
      // Set initial status values - map current status to acceptance status
      const currentStatus = selectedItem.status.toLowerCase()
      let acceptanceStatus = 'pending'
      if (currentStatus === 'approved' || currentStatus === 'implemented') {
        acceptanceStatus = 'approved'
      } else if (currentStatus === 'rejected') {
        acceptanceStatus = 'rejected'
      } else if (currentStatus === 'open' && selectedItem.type === 'feedback') {
        acceptanceStatus = 'open'
      } else {
        acceptanceStatus = 'pending'
      }
      
      setSelectedStatus(acceptanceStatus)
      const initialProgressStatus = getProgressStatus(selectedItem.status, selectedItem.type)
      setSelectedProgressStatus(initialProgressStatus)
      // Use requestAnimationFrame for smoother animation start
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsModalVisible(true)
        })
      })
    } else {
      setIsModalVisible(false)
      setSelectedStatus('')
      setSelectedProgressStatus('')
    }
  }, [selectedItem])

  // Validate and update progress status based on acceptance status
  useEffect(() => {
    if (!selectedStatus || !selectedItem) return

    // If status is rejected, progress status must be "Not Applicable"
    if (selectedStatus === 'rejected') {
      setSelectedProgressStatus('Not Applicable')
      return
    }

    // If status is pending, progress status should be "Not Started"
    if (selectedStatus === 'pending' || selectedStatus === 'open') {
      if (selectedProgressStatus !== 'Not Started' && selectedProgressStatus !== 'Not Applicable') {
        setSelectedProgressStatus('Not Started')
      }
      return
    }

    // If status is approved, ensure progress status is valid
    if (selectedStatus === 'approved') {
      // If current progress is "Not Applicable", change to "Not Started"
      if (selectedProgressStatus === 'Not Applicable') {
        setSelectedProgressStatus('Not Started')
      }
    }
  }, [selectedStatus, selectedItem])

  // Helper to get category from item
  const getItemCategory = (item: UnifiedItem): string => {
    if (item.type === 'feature_request') {
      const fr = item as FeatureRequest
      return fr.context?.issue_type || ''
    } else {
      // For feedback, category might be in the message or we need to extract it
      // For now, we'll check if it's mentioned in the message
      const fb = item as Feedback
      const message = fb.message || ''
      const categories = ['Enhancement', 'Feature Request', 'Integration', 'Workflow', 'UI/UX', 'Bug Report', 'Performance', 'Documentation']
      for (const cat of categories) {
        if (message.includes(`Category: ${cat}`)) {
          return cat
        }
      }
      return ''
    }
  }

  // Helper to determine type from category
  const getTypeFromCategory = (category: string): 'feature_request' | 'feedback' | null => {
    const featureRequestCategories = ['Enhancement', 'Integration', 'Workflow', 'UI/UX']
    if (featureRequestCategories.includes(category)) {
      return 'feature_request'
    }
    const feedbackCategories = ['Bug Report', 'Performance', 'Documentation']
    if (feedbackCategories.includes(category)) {
      return 'feedback'
    }
    // 'Feature Request' and 'Other' can be either
    if (category === 'Feature Request' || category === 'Other') {
      return null // Show both
    }
    return null
  }

  const loadUnifiedItems = async () => {
    setLoading(true)
    try {
      const items: UnifiedItem[] = []
      
      // Determine which types to load based on category filter
      const categoryType = categoryFilter ? getTypeFromCategory(categoryFilter) : null
      const loadFeatureRequests = !categoryFilter || categoryType === null || categoryType === 'feature_request'
      const loadFeedback = !categoryFilter || categoryType === null || categoryType === 'feedback'
      
      if (loadFeatureRequests) {
        try {
          const featureRequests = await adminAPI.getFeatureRequests(
            undefined, // Don't filter by status on API, we'll filter client-side
            searchQuery || undefined
          )
          items.push(...featureRequests.map((fr: FeatureRequest) => ({ ...fr, type: 'feature_request' as const })))
        } catch (e) {
          console.error('Failed to load feature requests:', e)
        }
      }
      
      if (loadFeedback) {
        try {
          const feedback = await adminAPI.getFeedback(
            searchQuery || undefined,
            undefined // Don't filter by status on API, we'll filter client-side
          )
          items.push(...feedback.map((fb: Feedback) => ({ ...fb, type: 'feedback' as const })))
        } catch (e) {
          console.error('Failed to load feedback:', e)
        }
      }
      
      // Filter by category if specified
      let filteredItems = items
      if (categoryFilter) {
        filteredItems = items.filter(item => {
          const itemCategory = getItemCategory(item)
          return itemCategory === categoryFilter
        })
      }
      
      // Filter by acceptance status if specified
      if (acceptanceStatusFilter) {
        filteredItems = filteredItems.filter(item => {
          const acceptanceStatus = getAcceptanceStatus(item.status)
          return acceptanceStatus.toLowerCase() === acceptanceStatusFilter.toLowerCase()
        })
      }
      
      // Filter by progress status if specified
      if (progressStatusFilter) {
        filteredItems = filteredItems.filter(item => {
          const progressStatus = getProgressStatus(item.status, item.type)
          return progressStatus === progressStatusFilter
        })
      }
      
      filteredItems.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      setUnifiedItems(filteredItems)
    } catch (error) {
      console.error('Failed to load items:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  const handleSearchClick = () => {
    setSearchQuery(search)
  }

  const handleClearSearch = () => {
    setSearch('')
    setSearchQuery('')
  }

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  // Map progress status and acceptance status to actual status values
  const getFinalStatus = (acceptanceStatus: string, progressStatus: string, type: 'feature_request' | 'feedback'): string => {
    // If rejected, always return rejected
    if (acceptanceStatus === 'rejected') {
      return 'rejected'
    }
    
    // If progress is "Not Applicable", it means rejected
    if (progressStatus === 'Not Applicable') {
      return 'rejected'
    }
    
    // If progress is "Implemented", return implemented for feature requests, resolved for feedback
    if (progressStatus === 'Implemented') {
      return type === 'feature_request' ? 'implemented' : 'resolved'
    }
    
    // If progress is "Completed", return resolved
    if (progressStatus === 'Completed') {
      return 'resolved'
    }
    
    // If progress is "In Progress", return in_progress
    if (progressStatus === 'In Progress') {
      return 'in_progress'
    }
    
    // If approved but not started, keep approved for feature requests, map to in_progress for feedback
    if (acceptanceStatus === 'approved' && progressStatus === 'Not Started') {
      return type === 'feature_request' ? 'approved' : 'in_progress'
    }
    
    // If pending and not started, return pending for feature requests, open for feedback
    if (acceptanceStatus === 'pending' && progressStatus === 'Not Started') {
      return type === 'feature_request' ? 'pending' : 'open'
    }
    
    // Default to acceptance status, but map approved to in_progress for feedback
    if (type === 'feedback' && acceptanceStatus === 'approved') {
      return 'in_progress'
    }
    
    // Map implemented to resolved for feedback
    if (type === 'feedback' && acceptanceStatus === 'implemented') {
      return 'resolved'
    }
    
    return acceptanceStatus
  }

  // Validate status and progress status combination
  const validateStatusCombination = (acceptanceStatus: string, progressStatus: string): { valid: boolean; message?: string } => {
    // If rejected, progress must be "Not Applicable"
    if (acceptanceStatus === 'rejected' && progressStatus !== 'Not Applicable') {
      return { valid: false, message: 'Rejected items must have "Not Applicable" progress status.' }
    }

    // If pending, progress should be "Not Started" or "Not Applicable"
    if ((acceptanceStatus === 'pending' || acceptanceStatus === 'open') && 
        progressStatus !== 'Not Started' && progressStatus !== 'Not Applicable') {
      return { valid: false, message: 'Pending items can only have "Not Started" or "Not Applicable" progress status.' }
    }

    // If approved, progress cannot be "Not Applicable"
    if (acceptanceStatus === 'approved' && progressStatus === 'Not Applicable') {
      return { valid: false, message: 'Approved items cannot have "Not Applicable" progress status.' }
    }

    return { valid: true }
  }

  const handleStatusChange = async () => {
    if (!selectedItem) return
    
    // Validate the combination
    const validation = validateStatusCombination(selectedStatus, selectedProgressStatus)
    if (!validation.valid) {
      alert(validation.message)
      return
    }
    
    setUpdating(true)
    try {
      // Determine the final status based on selected status and progress status
      const finalStatus = getFinalStatus(selectedStatus, selectedProgressStatus, selectedItem.type)
      
      if (selectedItem.type === 'feature_request') {
        await adminAPI.updateFeatureRequest(selectedItem.id.toString(), {
          status: finalStatus,
          admin_note: adminNote || (selectedItem as FeatureRequest).admin_note || undefined
        })
      } else {
        await adminAPI.updateFeedbackStatus(selectedItem.id.toString(), finalStatus)
      }
      await loadUnifiedItems()
      setSelectedItem(null)
      setAdminNote('')
      setSelectedStatus('')
      setSelectedProgressStatus('')
    } catch (error) {
      console.error('Failed to update item:', error)
    } finally {
      setUpdating(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved':
      case 'resolved':
        return 'text-success'
      case 'rejected':
        return 'text-error'
      case 'implemented':
        return 'text-primary'
      case 'in_review':
      case 'in_progress':
        return 'text-warning'
      case 'pending':
      case 'open':
        return 'text-text-secondary'
      default:
        return 'text-text-secondary'
    }
  }

  const getAcceptanceStatusBadgeClasses = (status: string) => {
    switch (status.toLowerCase()) {
      case 'approved':
        return 'bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20'
      case 'rejected':
        return 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20'
      case 'pending':
      default:
        return 'bg-yellow-500/10 text-yellow-600 dark:text-yellow-400 border border-yellow-500/20'
    }
  }

  // Get acceptance status (approved/rejected/pending)
  const getAcceptanceStatus = (status: string): string => {
    const statusLower = status.toLowerCase()
    if (statusLower === 'approved' || statusLower === 'resolved') {
      return 'Approved'
    }
    if (statusLower === 'rejected') {
      return 'Rejected'
    }
    return 'Pending'
  }

  // Get progress status (implementation status) - validates against acceptance status
  const getProgressStatus = (status: string, type: 'feature_request' | 'feedback'): string => {
    const statusLower = status.toLowerCase()
    
    // If rejected, progress is always "Not Applicable"
    if (statusLower === 'rejected') {
      return 'Not Applicable'
    }
    
    // If implemented, return "Implemented"
    if (statusLower === 'implemented') {
      return 'Implemented'
    }
    
    // If in progress or in review, return "In Progress"
    if (statusLower === 'in_progress' || statusLower === 'in_review') {
      return 'In Progress'
    }
    
    // If resolved (for feedback), return "Completed"
    if (statusLower === 'resolved' && type === 'feedback') {
      return 'Completed'
    }
    
    // If approved, check if it's implemented or just approved
    if (statusLower === 'approved') {
      // For approved items, default to "Not Started" unless already implemented
      return 'Not Started'
    }
    
    // For pending/open, progress should be "Not Started"
    if (statusLower === 'pending' || statusLower === 'open') {
      return 'Not Started'
    }
    
    // Default to "Not Started"
    return 'Not Started'
  }

  const getProgressStatusBadgeClasses = (progressStatus: string) => {
    switch (progressStatus) {
      case 'Implemented':
      case 'Completed':
        return 'bg-green-500/10 text-green-600 dark:text-green-400 border border-green-500/20'
      case 'In Progress':
        return 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20'
      case 'Not Started':
        return 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border border-gray-500/20'
      case 'Not Applicable':
        return 'bg-red-500/10 text-red-600 dark:text-red-400 border border-red-500/20'
      default:
        return 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border border-gray-500/20'
    }
  }

  const getTypeLabel = (type: string) => {
    return type === 'feature_request' ? 'Feature Request' : 'Feedback'
  }

  const getTypeIcon = (type: string) => {
    return type === 'feature_request' ? Lightbulb : MessageSquare
  }

  return (
    <div className="space-y-4">
      <div className="mb-4">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => router.push('/admin/requests-feedback')}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
              Feature Request & Feedback
            </h1>
            <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
              View and manage all feature requests and feedback
            </p>
          </div>
        </div>
        <div className="flex justify-end">
          <RefreshButton
            variant="secondary"
            onClick={loadUnifiedItems}
            size="sm"
            disabled={loading}
          />
        </div>
      </div>

      {loading ? (
        <Card compact>
          <div className="text-center py-8 text-text-secondary">Loading...</div>
        </Card>
      ) : unifiedItems.length === 0 ? (
        <Card compact>
          <div className="text-center py-8 text-text-secondary">No items found</div>
        </Card>
      ) : (
        <Card compact>
          <div className="mb-4 flex items-end gap-2 flex-wrap">
            <div className="flex items-center gap-2 flex-1 min-w-0">
              <div className="flex-1 max-w-md">
                <Input
                  type="text"
                  value={search}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  placeholder="Search by description, subject, or message..."
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
            <div className="w-48">
              <label className="block text-xs font-sans font-medium text-text-primary mb-1">
                Category
              </label>
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
              >
                <option value="">All Categories</option>
                <option value="Enhancement">Enhancement</option>
                <option value="Feature Request">Feature Request</option>
                <option value="Integration">Integration</option>
                <option value="Workflow">Workflow</option>
                <option value="UI/UX">UI/UX</option>
                <option value="Bug Report">Bug Report</option>
                <option value="Performance">Performance</option>
                <option value="Documentation">Documentation</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div className="w-40">
              <label className="block text-xs font-sans font-medium text-text-primary mb-1">
                Acceptance Status
              </label>
              <select
                value={acceptanceStatusFilter}
                onChange={(e) => setAcceptanceStatusFilter(e.target.value)}
                className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
              >
                <option value="">All</option>
                <option value="Pending">Pending</option>
                <option value="Approved">Approved</option>
                <option value="Rejected">Rejected</option>
              </select>
            </div>
            <div className="w-44">
              <label className="block text-xs font-sans font-medium text-text-primary mb-1">
                Progress Status
              </label>
              <select
                value={progressStatusFilter}
                onChange={(e) => setProgressStatusFilter(e.target.value)}
                className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
              >
                <option value="">All</option>
                <option value="Not Started">Not Started</option>
                <option value="In Progress">In Progress</option>
                <option value="Implemented">Implemented</option>
                <option value="Completed">Completed</option>
                <option value="Not Applicable">Not Applicable</option>
              </select>
            </div>
          </div>
          <Table>
            <TableHeader>
              <TableHeaderCell>Category</TableHeaderCell>
              <TableHeaderCell>Subject/Description</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Progress Status</TableHeaderCell>
              <TableHeaderCell>Created</TableHeaderCell>
              <TableHeaderCell className="text-right">Actions</TableHeaderCell>
            </TableHeader>
            <TableBody>
              {unifiedItems.map((item, index) => {
                const displayText = item.type === 'feature_request' 
                  ? (item as FeatureRequest).description.substring(0, 60) + '...'
                  : (item as Feedback).subject
                const category = getItemCategory(item)
                return (
                  <TableRow key={`${item.type}-${item.id}`} index={index}>
                    <TableCell>
                      <span className="text-sm font-sans text-text-primary">
                        {category || 'Other'}
                      </span>
                    </TableCell>
                    <TableCell className="max-w-xs">
                      <div className="truncate text-text-secondary" title={item.type === 'feature_request' ? (item as FeatureRequest).description : (item as Feedback).message}>
                        {displayText}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${getAcceptanceStatusBadgeClasses(getAcceptanceStatus(item.status))}`}>
                        {getAcceptanceStatus(item.status)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${getProgressStatusBadgeClasses(getProgressStatus(item.status, item.type))}`}>
                        {getProgressStatus(item.status, item.type)}
                      </span>
                    </TableCell>
                    <TableCell className="font-sans text-xs text-text-secondary">
                      {new Date(item.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 justify-end">
                        <Button
                          size="sm"
                          onClick={() => setSelectedItem(item)}
                        >
                          View
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Detail Modal */}
      {selectedItem && typeof window !== 'undefined' && createPortal(
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
            MozBackdropFilter: 'blur(12px)',
            opacity: isModalVisible ? undefined : 0,
            animation: isModalVisible ? 'backdropFadeIn 0.3s ease-out' : 'none',
          }}
          onClick={() => setSelectedItem(null)}
        >
          <div 
            className="relative"
            onClick={(e) => e.stopPropagation()}
          >
            <div
              className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] relative"
              style={{
                zIndex: 10000,
                opacity: isModalVisible ? undefined : 0,
                transform: isModalVisible ? undefined : 'scale(0.95)',
                animation: isModalVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
              }}
            >
              {/* Close Button - Positioned outside modal at top-right, aligned with modal top */}
              <button
                onClick={() => setSelectedItem(null)}
                className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10001] flex items-center justify-center"
                title="Close"
                aria-label="Close"
                style={{
                  animation: isModalVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
                }}
              >
                <X className="w-5 h-5" />
              </button>
              <div className="p-6 max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
                    {getTypeLabel(selectedItem.type)} Details
                  </h2>
                </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-sans font-medium text-text-secondary mb-1">User</label>
                  <p className="text-sm font-sans text-text-primary">{selectedItem.user_name}</p>
                </div>

                {selectedItem.type === 'feature_request' ? (
                  <>
                    <div>
                      <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Description</label>
                      <p className="text-sm font-sans text-text-primary whitespace-pre-wrap">{(selectedItem as FeatureRequest).description}</p>
                    </div>

                    {(selectedItem as FeatureRequest).context && (
                      <div>
                        <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Context</label>
                        <div className="text-sm font-sans text-text-secondary space-y-1">
                          {(selectedItem as FeatureRequest).context.page && <div>Page: {(selectedItem as FeatureRequest).context.page}</div>}
                          {(selectedItem as FeatureRequest).context.module && <div>Module: {(selectedItem as FeatureRequest).context.module}</div>}
                          {(selectedItem as FeatureRequest).context.issue_type && <div>Type: {(selectedItem as FeatureRequest).context.issue_type}</div>}
                        </div>
                      </div>
                    )}

                    {(selectedItem as FeatureRequest).ai_analysis && (
                      <div className="border-t border-border pt-4">
                        <h3 className="text-sm font-sans font-semibold text-text-primary mb-3">AI Analysis</h3>
                        <div className="space-y-3">
                          <div>
                            <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Summary</label>
                            <p className="text-sm font-sans text-text-primary">{(selectedItem as FeatureRequest).ai_analysis.summary}</p>
                          </div>
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Category</label>
                              <p className="text-sm font-sans text-text-primary">{(selectedItem as FeatureRequest).ai_analysis.category}</p>
                            </div>
                            <div>
                              <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Complexity</label>
                              <p className="text-sm font-sans text-text-primary">{(selectedItem as FeatureRequest).ai_analysis.complexity}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <div>
                      <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Subject</label>
                      <p className="text-sm font-sans text-text-primary">{(selectedItem as Feedback).subject}</p>
                    </div>
                    <div>
                      <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Message</label>
                      <p className="text-sm font-sans text-text-primary whitespace-pre-wrap">{(selectedItem as Feedback).message}</p>
                    </div>
                  </>
                )}

                <div className="border-t border-border pt-4 space-y-4">
                  <div>
                    <label className="block text-xs font-sans font-medium text-text-secondary mb-2">
                      Status (Acceptance) <span className="text-error">*</span>
                    </label>
                    <select
                      value={selectedStatus}
                      onChange={(e) => setSelectedStatus(e.target.value)}
                      className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
                      disabled={updating}
                    >
                      <option value="pending">Pending</option>
                      <option value="approved">Approved</option>
                      <option value="rejected">Rejected</option>
                      {selectedItem.type === 'feedback' && <option value="open">Open</option>}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-sans font-medium text-text-secondary mb-2">
                      Progress Status <span className="text-error">*</span>
                    </label>
                    <select
                      value={selectedProgressStatus}
                      onChange={(e) => setSelectedProgressStatus(e.target.value)}
                      className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
                      disabled={updating || selectedStatus === 'rejected'}
                    >
                      {selectedStatus === 'rejected' ? (
                        <option value="Not Applicable">Not Applicable</option>
                      ) : selectedStatus === 'pending' || selectedStatus === 'open' ? (
                        <>
                          <option value="Not Started">Not Started</option>
                          <option value="Not Applicable">Not Applicable</option>
                        </>
                      ) : selectedStatus === 'approved' ? (
                        selectedItem.type === 'feature_request' ? (
                          <>
                            <option value="Not Started">Not Started</option>
                            <option value="In Progress">In Progress</option>
                            <option value="Implemented">Implemented</option>
                          </>
                        ) : (
                          <>
                            <option value="Not Started">Not Started</option>
                            <option value="In Progress">In Progress</option>
                            <option value="Completed">Completed</option>
                          </>
                        )
                      ) : (
                        selectedItem.type === 'feature_request' ? (
                          <>
                            <option value="Not Started">Not Started</option>
                            <option value="In Progress">In Progress</option>
                            <option value="Implemented">Implemented</option>
                            <option value="Not Applicable">Not Applicable</option>
                          </>
                        ) : (
                          <>
                            <option value="Not Started">Not Started</option>
                            <option value="In Progress">In Progress</option>
                            <option value="Completed">Completed</option>
                            <option value="Not Applicable">Not Applicable</option>
                          </>
                        )
                      )}
                    </select>
                    {selectedStatus === 'rejected' && (
                      <p className="text-xs text-text-secondary mt-1">
                        Progress status is automatically set to "Not Applicable" when status is rejected.
                      </p>
                    )}
                    {selectedStatus === 'pending' && (
                      <p className="text-xs text-text-secondary mt-1">
                        Pending items can only be "Not Started" or "Not Applicable".
                      </p>
                    )}
                  </div>

                  <div>
                    <label className="block text-xs font-sans font-medium text-text-secondary mb-2">
                      {selectedItem.type === 'feature_request' ? 'Admin Note' : 'Notes'}
                    </label>
                    <textarea
                      value={adminNote || (selectedItem.type === 'feature_request' ? (selectedItem as FeatureRequest).admin_note || '' : '')}
                      onChange={(e) => setAdminNote(e.target.value)}
                      className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200 placeholder:text-text-muted dark:placeholder:text-[#6b7280]"
                      rows={3}
                      placeholder="Add a note about this item..."
                      disabled={updating}
                    />
                  </div>
                </div>

                <div className="flex gap-2 justify-end pt-4 border-t border-border">
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      setSelectedItem(null)
                      setAdminNote('')
                      setSelectedStatus('')
                      setSelectedProgressStatus('')
                    }}
                    disabled={updating}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleStatusChange}
                    disabled={updating || !selectedStatus || !selectedProgressStatus}
                  >
                    {updating ? 'Updating...' : 'Update Status'}
                  </Button>
                </div>
              </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

    </div>
  )
}

