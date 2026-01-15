'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { MessageSquare, Lightbulb, ArrowRight, Settings } from 'lucide-react'
import { userAPI, adminAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

export default function FeatureFeedbackPage() {
  const router = useRouter()
  const { user } = useAuthStore()
  const [stats, setStats] = useState({
    total: 0,
    featureRequests: 0,
    feedback: 0,
    pending: 0,
    rejected: 0,
    inProgress: 0,
    resolved: 0
  })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [])

  const loadStats = async () => {
    setLoading(true)
    try {
      const [featureRequests, allFeedback] = await Promise.all([
        userAPI.getMyFeatureRequests().catch(() => []),
        adminAPI.getFeedback().catch(() => [])
      ])

      const userFeedback = allFeedback.filter((fb: any) =>
        fb.user_id === user?.id || fb.user_id?.toString() === user?.id?.toString()
      )

      const totalFR = featureRequests.length || 0
      const totalFB = userFeedback.length || 0
      const total = totalFR + totalFB

      const pendingFR = featureRequests.filter((fr: any) =>
        fr.status === 'pending' || fr.status === 'in_review'
      ).length
      const pendingFB = userFeedback.filter((fb: any) =>
        fb.status === 'open' || fb.status === 'pending'
      ).length
      const pending = pendingFR + pendingFB

      const rejected = featureRequests.filter((fr: any) =>
        fr.status === 'rejected'
      ).length + userFeedback.filter((fb: any) =>
        fb.status === 'rejected'
      ).length

      const inProgress = featureRequests.filter((fr: any) =>
        fr.status === 'in_review' || fr.status === 'in_progress'
      ).length + userFeedback.filter((fb: any) =>
        fb.status === 'in_progress'
      ).length

      const resolved = userFeedback.filter((fb: any) =>
        fb.status === 'resolved'
      ).length

      setStats({
        total,
        featureRequests: totalFR,
        feedback: totalFB,
        pending,
        rejected,
        inProgress,
        resolved
      })
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
          Feature & Feedback
        </h1>
        <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
          Submit feedback, feature requests, and track their status
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-6 items-stretch">
        <Card className="hover:shadow-lg hover:border-primary/30 transition-all duration-200 border-2 w-full max-w-sm">
          <div className="p-6 flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-primary/10 dark:bg-[#3b82f6]/20 rounded-xl">
                  <MessageSquare className="w-6 h-6 text-primary dark:text-[#3b82f6]" />
                </div>
                <div>
                  <h3 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
                    Feature Requests & Feedback
                  </h3>
                  <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-0.5">
                    Submit feedback, feature requests, and track their status
                  </p>
                </div>
              </div>
            </div>

            {/* Stats Grid - 2x2 */}
            {loading ? (
              <div className="py-8 text-center text-text-secondary">Loading...</div>
            ) : (
              <div className="grid grid-cols-2 gap-4 mb-6">
                {/* Total Items */}
                <div className="text-center p-4 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border">
                  <div className="text-3xl font-bold font-sans text-text-primary dark:text-[#e5e7eb] mb-1">
                    {stats.total?.toLocaleString() || 0}
                  </div>
                  <div className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] uppercase tracking-wider">
                    Total Items
                  </div>
                </div>

                {/* Rejected */}
                <div className="text-center p-4 bg-error/10 dark:bg-[#ef4444]/10 rounded-lg border border-error/20">
                  <div className="text-3xl font-bold font-sans text-error mb-1">
                    {stats.rejected || 0}
                  </div>
                  <div className="text-xs font-sans text-error uppercase tracking-wider">
                    Rejected
                  </div>
                </div>

                {/* Resolved */}
                <div className="text-center p-4 bg-info/10 dark:bg-[#06b6d4]/10 rounded-lg border border-info/20">
                  <div className="text-3xl font-bold font-sans text-info mb-1">
                    {stats.resolved || 0}
                  </div>
                  <div className="text-xs font-sans text-info uppercase tracking-wider">
                    Resolved
                  </div>
                </div>

                {/* Pending */}
                <div className="text-center p-4 bg-warning/10 dark:bg-[#f59e0b]/10 rounded-lg border border-warning/20">
                  <div className="text-3xl font-bold font-sans text-warning mb-1">
                    {stats.pending || 0}
                  </div>
                  <div className="text-xs font-sans text-warning uppercase tracking-wider">
                    Pending
                  </div>
                </div>
              </div>
            )}

            <p className="text-sm font-sans text-text-secondary dark:text-[#9ca3af] mb-4">
              Submit feedback about the platform, report issues, or request new features and improvements. Our AI will analyze feature requests to help prioritize development.
            </p>
            <Button
              variant="primary"
              size="sm"
              className="w-full"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                router.push('/feature-feedback/unified')
              }}
            >
              <Settings className="w-4 h-4" />
              View & Submit Feature Requests & Feedback
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </Card>
      </div>
    </div>
  )
}

