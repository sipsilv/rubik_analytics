'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { userAPI, adminAPI } from '@/lib/api'
import { FeedbackModal } from '@/components/FeedbackModal'
import { ArrowLeft, X } from 'lucide-react'
import { useAuthStore } from '@/lib/store'

interface Feedback {
  id: number
  user_id: number
  user_name: string
  subject: string
  message: string
  status: string
  created_at: string
}

export default function FeedbackPage() {
  const router = useRouter()
  const { user } = useAuthStore()
  const [feedback, setFeedback] = useState<Feedback[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedFeedback, setSelectedFeedback] = useState<Feedback | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [isModalVisible, setIsModalVisible] = useState(false)

  useEffect(() => {
    loadFeedback()
  }, [])

  useEffect(() => {
    if (selectedFeedback) {
      // Reset visibility state first, then trigger animation after mount
      setIsModalVisible(false)
      // Use requestAnimationFrame for smoother animation start
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsModalVisible(true)
        })
      })
    } else {
      setIsModalVisible(false)
    }
  }, [selectedFeedback])

  const loadFeedback = async () => {
    setLoading(true)
    try {
      // Note: This uses admin API but filters client-side by user_id
      // In production, a dedicated user endpoint should be created
      const allFeedback = await adminAPI.getFeedback()
      const userFeedback = allFeedback.filter((fb: Feedback) => fb.user_id === user?.id || fb.user_id.toString() === user?.id?.toString())
      setFeedback(userFeedback)
    } catch (error) {
      console.error('Failed to load feedback:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'resolved':
        return 'text-success'
      case 'in_progress':
        return 'text-warning'
      case 'open':
        return 'text-text-secondary'
      default:
        return 'text-text-secondary'
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push('/feature-feedback')}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
            My Feedback
          </h1>
          <p className="text-xs font-sans text-text-secondary">
            Submit and track the status of your feedback
          </p>
        </div>
      </div>

      <div className="flex justify-end">
        <Button
          onClick={() => setShowModal(true)}
          size="sm"
        >
          Submit New Feedback
        </Button>
      </div>

      {loading ? (
        <Card compact>
          <div className="text-center py-8 text-text-secondary">Loading...</div>
        </Card>
      ) : feedback.length === 0 ? (
        <Card compact>
          <div className="text-center py-8">
            <p className="text-text-secondary mb-4">You haven't submitted any feedback yet.</p>
            <Button size="sm" onClick={() => setShowModal(true)}>
              Submit Your First Feedback
            </Button>
          </div>
        </Card>
      ) : (
        <Card compact>
          <Table>
            <TableHeader>
              <TableHeaderCell>Subject</TableHeaderCell>
              <TableHeaderCell>Message</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Submitted</TableHeaderCell>
              <TableHeaderCell className="text-right">Actions</TableHeaderCell>
            </TableHeader>
            <TableBody>
              {feedback.map((item, index) => (
                <TableRow key={item.id} index={index}>
                  <TableCell className="font-medium">{item.subject}</TableCell>
                  <TableCell className="max-w-md truncate text-text-secondary">{item.message}</TableCell>
                  <TableCell>
                    <span className={`text-[10px] font-sans px-1.5 py-0.5 rounded uppercase ${getStatusColor(item.status)}`}>
                      {item.status.replace('_', ' ')}
                    </span>
                  </TableCell>
                  <TableCell className="font-sans text-xs text-text-secondary">{new Date(item.created_at).toLocaleDateString()}</TableCell>
                  <TableCell>
                    <div className="flex gap-1 justify-end">
                      <Button variant="ghost" size="sm" onClick={() => setSelectedFeedback(item)}>View</Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Detail Modal */}
      {selectedFeedback && (
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
          onClick={() => setSelectedFeedback(null)}
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
                onClick={() => setSelectedFeedback(null)} 
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
                  Feedback Details
                </h2>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Status</label>
                  <p className={`text-sm font-sans font-semibold ${getStatusColor(selectedFeedback.status)}`}>
                    {selectedFeedback.status.replace('_', ' ').toUpperCase()}
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Subject</label>
                  <p className="text-sm font-sans text-text-primary">{selectedFeedback.subject}</p>
                </div>

                <div>
                  <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Message</label>
                  <p className="text-sm font-sans text-text-primary whitespace-pre-wrap">{selectedFeedback.message}</p>
                </div>

                <div>
                  <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Submitted</label>
                  <p className="text-sm font-sans text-text-secondary">{new Date(selectedFeedback.created_at).toLocaleString()}</p>
                </div>

                <div className="flex gap-2 justify-end pt-4 border-t border-border">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setSelectedFeedback(null)}
                  >
                    Close
                  </Button>
                </div>
              </div>
            </div>
          </div>
          </div>
        </div>
      )}

      <FeedbackModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        onSuccess={() => {
          loadFeedback()
        }}
      />
    </div>
  )
}

