'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { userAPI, adminAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { UnifiedSubmitModal } from '@/components/UnifiedSubmitModal'
import { ArrowLeft, X, Lightbulb, MessageSquare, Search } from 'lucide-react'

interface FeatureRequest {
  id: number
  user_id: number
  user_name: string
  description: string
  context: any
  status: string
  ai_analysis: any
  admin_note: string | null
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

export default function UnifiedFeatureFeedbackPage() {
  const router = useRouter()
  const { user } = useAuthStore()
  const [unifiedItems, setUnifiedItems] = useState<UnifiedItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedItem, setSelectedItem] = useState<UnifiedItem | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [isModalVisible, setIsModalVisible] = useState(false)
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('')

  useEffect(() => {
    loadUnifiedItems()
  }, [searchQuery, categoryFilter])

  useEffect(() => {
    if (selectedItem) {
      setIsModalVisible(false)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsModalVisible(true)
        })
      })
    } else {
      setIsModalVisible(false)
    }
  }, [selectedItem])

  const loadUnifiedItems = async () => {
    setLoading(true)
    try {
      const items: UnifiedItem[] = []
      
      // Load all items first
      try {
        const featureRequests = await userAPI.getMyFeatureRequests()
        items.push(...featureRequests.map((fr: FeatureRequest) => ({ ...fr, type: 'feature_request' as const })))
      } catch (e) {
        console.error('Failed to load feature requests:', e)
      }
      
      try {
        const allFeedback = await adminAPI.getFeedback()
        const userFeedback = allFeedback.filter((fb: Feedback) => 
          fb.user_id === user?.id || fb.user_id?.toString() === user?.id?.toString()
        )
        items.push(...userFeedback.map((fb: Feedback) => ({ ...fb, type: 'feedback' as const })))
      } catch (e) {
        console.error('Failed to load feedback:', e)
      }
      
      // Filter by category if specified
      let filtered = items
      if (categoryFilter) {
        filtered = items.filter(item => {
          const itemCategory = getItemCategory(item)
          return itemCategory === categoryFilter
        })
      }
      
      // Filter by search query
      if (searchQuery) {
        const query = searchQuery.toLowerCase()
        filtered = filtered.filter(item => {
          if (item.type === 'feature_request') {
            return (item as FeatureRequest).description.toLowerCase().includes(query)
          } else {
            return (item as Feedback).subject.toLowerCase().includes(query) || 
                   (item as Feedback).message.toLowerCase().includes(query)
          }
        })
      }
      
      filtered.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
      setUnifiedItems(filtered)
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

  // Get progress status (implementation status)
  const getProgressStatus = (status: string, type: 'feature_request' | 'feedback'): string => {
    const statusLower = status.toLowerCase()
    if (statusLower === 'implemented') {
      return 'Implemented'
    }
    if (statusLower === 'in_progress' || statusLower === 'in_review') {
      return 'In Progress'
    }
    if (statusLower === 'approved' || statusLower === 'resolved') {
      return type === 'feature_request' ? 'Not Started' : 'Completed'
    }
    if (statusLower === 'rejected') {
      return 'Not Applicable'
    }
    return 'Not Started'
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

  // Helper to get category from item
  const getItemCategory = (item: UnifiedItem): string => {
    if (item.type === 'feature_request') {
      const fr = item as FeatureRequest
      return fr.context?.issue_type || ''
    } else {
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
            onClick={() => router.push('/feature-feedback')}
            className="text-text-secondary hover:text-text-primary transition-colors"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
              Feature Requests & Feedback
            </h1>
            <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
              View and manage all your feature requests and feedback
            </p>
          </div>
        </div>
        <div className="flex justify-end">
          <Button
            variant="primary"
            size="sm"
            onClick={() => setShowModal(true)}
          >
            Submit New
          </Button>
        </div>
      </div>

      {loading ? (
        <Card compact>
          <div className="text-center py-8 text-text-secondary">Loading...</div>
        </Card>
      ) : unifiedItems.length === 0 ? (
        <Card compact>
          <div className="text-center py-8">
            <p className="text-text-secondary mb-4">You haven't submitted any feature requests or feedback yet.</p>
            <Button size="sm" onClick={() => setShowModal(true)}>
              Submit Your First Request or Feedback
            </Button>
          </div>
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
      {selectedItem && (
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
                <h2 className="text-xl font-sans font-semibold text-text-primary">
                  {getTypeLabel(selectedItem.type)} Details
                </h2>
              </div>

              <div className="space-y-4">
                {selectedItem.type === 'feature_request' ? (
                  <>
                    <div>
                      <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Status</label>
                      <p className={`text-sm font-sans font-semibold ${getStatusColor(selectedItem.status)}`}>
                        {(selectedItem as FeatureRequest).status.replace('_', ' ').toUpperCase()}
                      </p>
                    </div>
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
                    {(selectedItem as FeatureRequest).admin_note && (
                      <div className="border-t border-border pt-4">
                        <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Admin Note</label>
                        <p className="text-sm font-sans text-text-primary whitespace-pre-wrap">{(selectedItem as FeatureRequest).admin_note}</p>
                      </div>
                    )}
                  </>
                ) : (
                  <>
                    <div>
                      <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Status</label>
                      <p className={`text-sm font-sans font-semibold ${getStatusColor(selectedItem.status)}`}>
                        {(selectedItem as Feedback).status.replace('_', ' ').toUpperCase()}
                      </p>
                    </div>
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
              </div>
            </div>
          </div>
          </div>
        </div>
      )}

      <UnifiedSubmitModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSuccess={() => {
          loadUnifiedItems()
        }}
      />
    </div>
  )
}

