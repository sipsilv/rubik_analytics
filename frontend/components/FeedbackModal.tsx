'use client'

import { useState, useEffect } from 'react'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { ErrorMessage } from './ui/ErrorMessage'
import { userAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X, Info, AlertCircle, CheckCircle, MessageSquare } from 'lucide-react'

interface FeedbackModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function FeedbackModal({ isOpen, onClose, onSuccess }: FeedbackModalProps) {
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [category, setCategory] = useState('')
  const [priority, setPriority] = useState('')
  const [pageLocation, setPageLocation] = useState('')
  const [userImpact, setUserImpact] = useState('')
  const [stepsToReproduce, setStepsToReproduce] = useState('')
  const [expectedBehavior, setExpectedBehavior] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [isVisible, setIsVisible] = useState(false)

  // Animation state - sync with modal open/close
  useEffect(() => {
    if (isOpen) {
      // Reset visibility state first, then trigger animation after mount
      setIsVisible(false)
      // Use requestAnimationFrame for smoother animation start
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsVisible(true)
        })
      })
    } else {
      setIsVisible(false)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    if (subject.trim().length < 3) {
      setError('Please provide a subject (at least 3 characters)')
      setLoading(false)
      return
    }

    if (message.trim().length < 10) {
      setError('Please provide a detailed message (at least 10 characters)')
      setLoading(false)
      return
    }

    try {
      // Build detailed feedback message
      let detailedMessage = message.trim()
      
      if (category) {
        detailedMessage += `\n\nCategory: ${category}`
      }
      if (priority) {
        detailedMessage += `\nPriority: ${priority}`
      }
      if (pageLocation) {
        detailedMessage += `\nPage/Location: ${pageLocation}`
      }
      if (userImpact) {
        detailedMessage += `\nUser Impact: ${userImpact}`
      }
      if (stepsToReproduce) {
        detailedMessage += `\n\nSteps to Reproduce:\n${stepsToReproduce}`
      }
      if (expectedBehavior) {
        detailedMessage += `\n\nExpected Behavior:\n${expectedBehavior}`
      }

      await userAPI.createFeedback(subject.trim(), detailedMessage)
      
      setSuccess(true)
      setTimeout(() => {
        setSubject('')
        setMessage('')
        setSuccess(false)
        onSuccess?.()
        onClose()
      }, 2000)
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to submit feedback'))
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    if (!loading) {
      setSubject('')
      setMessage('')
      setCategory('')
      setPriority('')
      setPageLocation('')
      setUserImpact('')
      setStepsToReproduce('')
      setExpectedBehavior('')
      setError('')
      setSuccess(false)
      onClose()
    }
  }

  return (
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
        opacity: isVisible ? undefined : 0,
        animation: isVisible ? 'backdropFadeIn 0.3s ease-out' : 'none',
      }}
      onClick={(e) => {
        // Close modal when clicking backdrop
        if (e.target === e.currentTarget) {
          handleClose()
        }
      }}
    >
      <div 
        className="relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div 
          className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] relative"
          style={{
            zIndex: 10000,
            opacity: isVisible ? undefined : 0,
            transform: isVisible ? undefined : 'scale(0.95)',
            animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
          }}
        >
          {/* Close Button - Positioned outside modal at top-right, aligned with modal top */}
          <button 
            onClick={handleClose} 
            className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10001] flex items-center justify-center"
            title="Close"
            aria-label="Close"
            style={{
              animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
            }}
          >
            <X className="w-5 h-5" />
          </button>
        <div className="p-6 max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-sans font-semibold text-text-primary">
              Submit Feedback
            </h2>
          </div>

          {success ? (
            <div className="text-center py-8">
              <div className="mb-4">
                <svg className="w-16 h-16 mx-auto text-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-sans font-semibold text-text-primary mb-2">
                Feedback Submitted!
              </h3>
              <p className="text-sm font-sans text-text-secondary">
                Thank you for your feedback. We'll review it and get back to you if needed.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Basic Information Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-3">
                  <MessageSquare className="w-5 h-5 text-primary" />
                  <h3 className="text-base font-sans font-semibold text-text-primary">
                    Basic Information
                  </h3>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Subject <span className="text-error">*</span>
                  </label>
                  <Input
                    type="text"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="Brief summary of your feedback..."
                    required
                    disabled={loading}
                    maxLength={200}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {subject.length}/200 characters
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Category
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
                    disabled={loading}
                  >
                    <option value="">Select a category...</option>
                    <option value="Bug Report">Bug Report</option>
                    <option value="Feature Request">Feature Request</option>
                    <option value="UI/UX Improvement">UI/UX Improvement</option>
                    <option value="Performance Issue">Performance Issue</option>
                    <option value="Documentation">Documentation</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                      Priority
                    </label>
                    <select
                      value={priority}
                      onChange={(e) => setPriority(e.target.value)}
                      className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
                      disabled={loading}
                    >
                      <option value="">Select priority...</option>
                      <option value="Low">Low</option>
                      <option value="Medium">Medium</option>
                      <option value="High">High</option>
                      <option value="Critical">Critical</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                      Page/Location
                    </label>
                    <Input
                      type="text"
                      value={pageLocation}
                      onChange={(e) => setPageLocation(e.target.value)}
                      placeholder="e.g., Dashboard, Settings..."
                      disabled={loading}
                    />
                  </div>
                </div>
              </div>

              {/* Detailed Description Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-3">
                  <Info className="w-5 h-5 text-info" />
                  <h3 className="text-base font-sans font-semibold text-text-primary">
                    Detailed Description
                  </h3>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Message <span className="text-error">*</span>
                  </label>
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Describe your feedback, suggestion, or issue in detail. Include any relevant context..."
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={5}
                    required
                    disabled={loading}
                    maxLength={5000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {message.length}/5000 characters
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    User Impact
                  </label>
                  <textarea
                    value={userImpact}
                    onChange={(e) => setUserImpact(e.target.value)}
                    placeholder="How does this affect you or other users? (Optional)"
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={3}
                    disabled={loading}
                    maxLength={1000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {userImpact.length}/1000 characters
                  </p>
                </div>
              </div>

              {/* Additional Details Section (for bugs/issues) */}
              {(category === 'Bug Report' || category === 'Performance Issue') && (
                <div className="space-y-4 p-4 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border">
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className="w-5 h-5 text-warning" />
                    <h3 className="text-base font-sans font-semibold text-text-primary">
                      Issue Details
                    </h3>
                  </div>

                  <div>
                    <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                      Steps to Reproduce
                    </label>
                    <textarea
                      value={stepsToReproduce}
                      onChange={(e) => setStepsToReproduce(e.target.value)}
                      placeholder="1. Go to...\n2. Click on...\n3. See error..."
                      className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                      rows={4}
                      disabled={loading}
                      maxLength={2000}
                    />
                    <p className="mt-1 text-xs font-sans text-text-secondary">
                      {stepsToReproduce.length}/2000 characters
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                      Expected Behavior
                    </label>
                    <textarea
                      value={expectedBehavior}
                      onChange={(e) => setExpectedBehavior(e.target.value)}
                      placeholder="What should happen instead?"
                      className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                      rows={3}
                      disabled={loading}
                      maxLength={1000}
                    />
                    <p className="mt-1 text-xs font-sans text-text-secondary">
                      {expectedBehavior.length}/1000 characters
                    </p>
                  </div>
                </div>
              )}

              {/* Helpful Tips */}
              <div className="p-3 bg-info/10 dark:bg-[#06b6d4]/10 rounded-lg border border-info/20">
                <div className="flex items-start gap-2">
                  <Info className="w-4 h-4 text-info mt-0.5 flex-shrink-0" />
                  <div className="text-xs font-sans text-text-secondary">
                    <p className="font-medium text-text-primary mb-1">Tips for better feedback:</p>
                    <ul className="list-disc list-inside space-y-1 ml-2">
                      <li>Be specific and provide as much context as possible</li>
                      <li>Include screenshots or examples if relevant</li>
                      <li>Mention your browser and device if reporting a bug</li>
                      <li>Describe the impact on your workflow</li>
                    </ul>
                  </div>
                </div>
              </div>

              <ErrorMessage error={error} className="p-3" />

              <div className="flex gap-2 justify-end pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={handleClose}
                  disabled={loading}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  size="sm"
                  disabled={loading || subject.trim().length < 3 || message.trim().length < 10}
                >
                  {loading ? 'Submitting...' : 'Submit Feedback'}
                </Button>
              </div>
            </form>
          )}
        </div>
      </div>
      </div>
    </div>
  )
}

