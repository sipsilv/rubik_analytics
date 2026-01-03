'use client'

import { useState, useEffect } from 'react'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { ErrorMessage } from './ui/ErrorMessage'
import { userAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X, Lightbulb, Info, Target, Users, Zap } from 'lucide-react'

interface FeatureRequestModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function FeatureRequestModal({ isOpen, onClose, onSuccess }: FeatureRequestModalProps) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [page, setPage] = useState('')
  const [module, setModule] = useState('')
  const [issueType, setIssueType] = useState('')
  const [priority, setPriority] = useState('')
  const [useCase, setUseCase] = useState('')
  const [benefits, setBenefits] = useState('')
  const [alternatives, setAlternatives] = useState('')
  const [userImpact, setUserImpact] = useState('')
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

    if (!title.trim() || title.trim().length < 3) {
      setError('Please provide a feature title (at least 3 characters)')
      setLoading(false)
      return
    }

    if (description.trim().length < 10) {
      setError('Please provide a detailed description (at least 10 characters)')
      setLoading(false)
      return
    }

    try {
      // Build detailed feature request
      let detailedDescription = description.trim()
      
      if (useCase) {
        detailedDescription += `\n\nUse Case:\n${useCase}`
      }
      if (benefits) {
        detailedDescription += `\n\nBenefits:\n${benefits}`
      }
      if (userImpact) {
        detailedDescription += `\n\nUser Impact:\n${userImpact}`
      }
      if (alternatives) {
        detailedDescription += `\n\nAlternative Solutions Considered:\n${alternatives}`
      }
      if (priority) {
        detailedDescription += `\n\nPriority: ${priority}`
      }

      const context: any = {}
      if (page) context.page = page
      if (module) context.module = module
      if (issueType) context.issue_type = issueType
      if (priority) context.priority = priority

      await userAPI.createFeatureRequest(detailedDescription.trim(), Object.keys(context).length > 0 ? context : undefined)
      
      setSuccess(true)
      setTimeout(() => {
        setTitle('')
        setDescription('')
        setPage('')
        setModule('')
        setIssueType('')
        setPriority('')
        setUseCase('')
        setBenefits('')
        setAlternatives('')
        setUserImpact('')
        setSuccess(false)
        onSuccess?.()
        onClose()
      }, 2000)
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to submit feature request'))
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    if (!loading) {
      setTitle('')
      setDescription('')
      setPage('')
      setModule('')
      setIssueType('')
      setPriority('')
      setUseCase('')
      setBenefits('')
      setAlternatives('')
      setUserImpact('')
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
              Request New Feature
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
                Request Submitted!
              </h3>
              <p className="text-sm font-sans text-text-secondary">
                Your feature request is being analyzed by AI. You'll be notified when the analysis is complete.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Basic Information Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-3">
                  <Lightbulb className="w-5 h-5 text-primary" />
                  <h3 className="text-base font-sans font-semibold text-text-primary">
                    Basic Information
                  </h3>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Feature Title <span className="text-error">*</span>
                  </label>
                  <Input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Brief, descriptive title for your feature request..."
                    required
                    disabled={loading}
                    maxLength={200}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {title.length}/200 characters
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Feature Description <span className="text-error">*</span>
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="Describe the feature or improvement you'd like to see. Be as detailed as possible about what you want and why..."
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={5}
                    required
                    disabled={loading}
                    maxLength={5000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {description.length}/5000 characters
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                      Page/Route
                    </label>
                    <Input
                      type="text"
                      value={page}
                      onChange={(e) => setPage(e.target.value)}
                      placeholder="e.g., Dashboard, Settings..."
                      disabled={loading}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                      Module
                    </label>
                    <Input
                      type="text"
                      value={module}
                      onChange={(e) => setModule(e.target.value)}
                      placeholder="e.g., Analytics, Reports..."
                      disabled={loading}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                      Type
                    </label>
                    <select
                      value={issueType}
                      onChange={(e) => setIssueType(e.target.value)}
                      className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
                      disabled={loading}
                    >
                      <option value="">Select type...</option>
                      <option value="Enhancement">Enhancement</option>
                      <option value="New Feature">New Feature</option>
                      <option value="Integration">Integration</option>
                      <option value="Workflow Improvement">Workflow Improvement</option>
                      <option value="UI/UX">UI/UX</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
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
                      <option value="Low">Low - Nice to have</option>
                      <option value="Medium">Medium - Would be helpful</option>
                      <option value="High">High - Important for workflow</option>
                      <option value="Critical">Critical - Blocks my work</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Use Case & Benefits Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-3">
                  <Target className="w-5 h-5 text-success" />
                  <h3 className="text-base font-sans font-semibold text-text-primary">
                    Use Case & Benefits
                  </h3>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Use Case / Scenario
                  </label>
                  <textarea
                    value={useCase}
                    onChange={(e) => setUseCase(e.target.value)}
                    placeholder="Describe a specific scenario or use case where this feature would be helpful..."
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={4}
                    disabled={loading}
                    maxLength={2000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {useCase.length}/2000 characters
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Benefits
                  </label>
                  <textarea
                    value={benefits}
                    onChange={(e) => setBenefits(e.target.value)}
                    placeholder="What benefits would this feature provide? How would it improve your workflow or experience?"
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={4}
                    disabled={loading}
                    maxLength={2000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {benefits.length}/2000 characters
                  </p>
                </div>
              </div>

              {/* Impact & Alternatives Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-3">
                  <Users className="w-5 h-5 text-info" />
                  <h3 className="text-base font-sans font-semibold text-text-primary">
                    Impact & Alternatives
                  </h3>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    User Impact
                  </label>
                  <textarea
                    value={userImpact}
                    onChange={(e) => setUserImpact(e.target.value)}
                    placeholder="Who would benefit from this feature? How many users might use it?"
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={3}
                    disabled={loading}
                    maxLength={1000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {userImpact.length}/1000 characters
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Alternative Solutions Considered
                  </label>
                  <textarea
                    value={alternatives}
                    onChange={(e) => setAlternatives(e.target.value)}
                    placeholder="Have you considered any workarounds or alternative solutions? Why aren't they sufficient?"
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={3}
                    disabled={loading}
                    maxLength={1000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {alternatives.length}/1000 characters
                  </p>
                </div>
              </div>

              {/* Helpful Tips */}
              <div className="p-3 bg-primary/10 dark:bg-[#3b82f6]/10 rounded-lg border border-primary/20">
                <div className="flex items-start gap-2">
                  <Zap className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  <div className="text-xs font-sans text-text-secondary">
                    <p className="font-medium text-text-primary mb-1">Tips for better feature requests:</p>
                    <ul className="list-disc list-inside space-y-1 ml-2">
                      <li>Be specific about what you want and why you need it</li>
                      <li>Describe real-world scenarios where this would be useful</li>
                      <li>Explain how it would improve your workflow</li>
                      <li>Consider if there are existing features that could be enhanced instead</li>
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
                  disabled={loading || !title.trim() || title.trim().length < 3 || description.trim().length < 10}
                >
                  {loading ? 'Submitting...' : 'Submit Request'}
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
