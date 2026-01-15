'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { UserCheck, MessageSquare, Settings, ArrowRight } from 'lucide-react'
import { adminAPI } from '@/lib/api'

export default function RequestsFeedbackPage() {
  const router = useRouter()
  const [requestsStats, setRequestsStats] = useState({
    total: 0,
    approved: 0,
    rejected: 0,
    pending: 0
  })
  const [unifiedStats, setUnifiedStats] = useState({
    total: 0,
    featureRequests: 0,
    feedback: 0,
    pending: 0
  })
  const [loading, setLoading] = useState(true)
  const hasLoadedRef = useRef(false)

  useEffect(() => {
    // Prevent double call in React Strict Mode
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true

    loadStats()
    loadUnifiedStats()
  }, [])

  const loadStats = async () => {
    try {
      const allRequests = await adminAPI.getRequests()
      const total = allRequests.length || 0
      const approved = allRequests.filter((r: any) => r.status === 'approved' || r.status === 'APPROVED').length
      const rejected = allRequests.filter((r: any) => r.status === 'rejected' || r.status === 'REJECTED').length
      const pending = allRequests.filter((r: any) => r.status === 'pending' || r.status === 'PENDING').length

      setRequestsStats({
        total,
        approved,
        rejected,
        pending
      })
    } catch (e) {
      console.error('Failed to load requests stats:', e)
    }
  }

  const loadUnifiedStats = async () => {
    try {
      setLoading(true)
      const [featureRequests, feedback] = await Promise.all([
        adminAPI.getFeatureRequests().catch(() => []),
        adminAPI.getFeedback().catch(() => [])
      ])

      const totalFR = featureRequests.length || 0
      const totalFB = feedback.length || 0
      const total = totalFR + totalFB

      const pending = [
        ...featureRequests.filter((fr: any) => fr.status === 'pending'),
        ...feedback.filter((fb: any) => fb.status === 'open' || fb.status === 'pending')
      ].length

      setUnifiedStats({
        total,
        featureRequests: totalFR,
        feedback: totalFB,
        pending
      })
    } catch (e) {
      console.error('Failed to load unified stats:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleCardClick = (filterType?: string) => {
    if (filterType) {
      router.push(`/admin/requests?filter=${filterType}`)
    } else {
      router.push('/admin/requests')
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
          Request and Feedback
        </h1>
        <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
          Manage access requests, feature requests, and user feedback for the platform
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-6 items-stretch">
        {/* Access Request Card */}
        <Card className="hover:shadow-lg hover:border-primary/30 transition-all duration-200 border-2 w-full max-w-sm">
          <div className="p-6 flex flex-col h-full">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-primary/10 dark:bg-[#3b82f6]/20 rounded-xl">
                  <UserCheck className="w-6 h-6 text-primary dark:text-[#3b82f6]" />
                </div>
                <div>
                  <h3 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
                    Access Request
                  </h3>
                  <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-0.5">
                    Review and manage user access requests
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleCardClick()
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleCardClick()
                  }
                }}
                className="text-center p-4 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 dark:hover:bg-primary/10 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-primary/30"
                aria-label="View all requests"
              >
                <div className="text-3xl font-bold font-sans text-text-primary dark:text-[#e5e7eb] mb-1">
                  {requestsStats.total?.toLocaleString() || 0}
                </div>
                <div className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] uppercase tracking-wider">
                  Total Requests
                </div>
              </button>

              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleCardClick('approved')
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleCardClick('approved')
                  }
                }}
                className="text-center p-4 bg-success/10 dark:bg-[#10b981]/10 rounded-lg border border-success/20 hover:border-success/50 hover:bg-success/20 dark:hover:bg-success/20 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-success/30"
                aria-label="View approved requests"
              >
                <div className="text-3xl font-bold font-sans text-success mb-1">
                  {requestsStats.approved || 0}
                </div>
                <div className="text-xs font-sans text-success uppercase tracking-wider">
                  Approved
                </div>
              </button>

              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleCardClick('rejected')
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleCardClick('rejected')
                  }
                }}
                className="text-center p-4 bg-error/10 dark:bg-[#ef4444]/10 rounded-lg border border-error/20 hover:border-error/50 hover:bg-error/20 dark:hover:bg-error/20 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-error/30"
                aria-label="View rejected requests"
              >
                <div className="text-3xl font-bold font-sans text-error mb-1">
                  {requestsStats.rejected || 0}
                </div>
                <div className="text-xs font-sans text-error uppercase tracking-wider">
                  Rejected
                </div>
              </button>

              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  handleCardClick('pending')
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    handleCardClick('pending')
                  }
                }}
                className="text-center p-4 bg-warning/10 dark:bg-[#f59e0b]/10 rounded-lg border border-warning/20 hover:border-warning/50 hover:bg-warning/20 dark:hover:bg-warning/20 transition-all cursor-pointer focus:outline-none focus:ring-2 focus:ring-warning/30"
                aria-label="View pending requests"
              >
                <div className="text-3xl font-bold font-sans text-warning mb-1">
                  {requestsStats.pending || 0}
                </div>
                <div className="text-xs font-sans text-warning uppercase tracking-wider">
                  Pending
                </div>
              </button>
            </div>

            <p className="text-sm font-sans text-text-secondary dark:text-[#9ca3af] mb-4">
              Review and approve or reject new user access requests. Manage user onboarding and access control.
            </p>
            <Button
              variant="primary"
              size="sm"
              className="w-full"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                router.push('/admin/requests')
              }}
            >
              <Settings className="w-4 h-4" />
              Manage Access Requests
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </Card>

        {/* Feature Request & Feedback Card */}
        <Card className="hover:shadow-lg hover:border-success/30 transition-all duration-200 border-2 w-full max-w-sm">
          <div className="p-6 flex flex-col h-full">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-success/10 dark:bg-[#10b981]/20 rounded-xl">
                  <MessageSquare className="w-6 h-6 text-success" />
                </div>
                <div>
                  <h3 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
                    Feature Request & Feedback
                  </h3>
                  <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-0.5">
                    User feature requests and feedback
                  </p>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 mb-6">
              <div className="text-center p-4 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border">
                <div className="text-3xl font-bold font-sans text-text-primary dark:text-[#e5e7eb] mb-1">
                  {unifiedStats.total?.toLocaleString() || 0}
                </div>
                <div className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] uppercase tracking-wider">
                  Total Items
                </div>
              </div>

              <div className="text-center p-4 bg-primary/10 dark:bg-[#3b82f6]/10 rounded-lg border border-primary/20">
                <div className="text-3xl font-bold font-sans text-primary mb-1">
                  {unifiedStats.featureRequests || 0}
                </div>
                <div className="text-xs font-sans text-primary uppercase tracking-wider">
                  Feature Requests
                </div>
              </div>

              <div className="text-center p-4 bg-info/10 dark:bg-[#06b6d4]/10 rounded-lg border border-info/20">
                <div className="text-3xl font-bold font-sans text-info mb-1">
                  {unifiedStats.feedback || 0}
                </div>
                <div className="text-xs font-sans text-info uppercase tracking-wider">
                  Feedback
                </div>
              </div>

              <div className="text-center p-4 bg-warning/10 dark:bg-[#f59e0b]/10 rounded-lg border border-warning/20">
                <div className="text-3xl font-bold font-sans text-warning mb-1">
                  {unifiedStats.pending || 0}
                </div>
                <div className="text-xs font-sans text-warning uppercase tracking-wider">
                  Pending
                </div>
              </div>
            </div>

            <p className="text-sm font-sans text-text-secondary dark:text-[#9ca3af] mb-4">
              View and manage feature requests and feedback submitted by users. Track suggestions and improvements.
            </p>
            <Button
              variant="primary"
              size="sm"
              className="w-full"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                router.push('/admin/requests-feedback/details')
              }}
            >
              <Settings className="w-4 h-4" />
              Manage Feature Requests & Feedback
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}
