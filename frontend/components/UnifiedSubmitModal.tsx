'use client'

import { useState, useEffect } from 'react'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { ErrorMessage } from './ui/ErrorMessage'
import { userAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X, Lightbulb, MessageSquare, Info, AlertCircle, Target, Users, Zap, CheckCircle } from 'lucide-react'

interface UnifiedSubmitModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function UnifiedSubmitModal({ isOpen, onClose, onSuccess }: UnifiedSubmitModalProps) {
  // Common unified fields
  const [category, setCategory] = useState('')
  
  // Determine type based on category
  const getTypeFromCategory = (cat: string): 'feature_request' | 'feedback' => {
    const featureRequestCategories = ['Enhancement', 'Feature Request', 'Integration', 'Workflow', 'UI/UX']
    return featureRequestCategories.includes(cat) ? 'feature_request' : 'feedback'
  }
  
  const type = category ? getTypeFromCategory(category) : 'feature_request'
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [page, setPage] = useState('')
  const [module, setModule] = useState('')
  const [priority, setPriority] = useState('')
  const [userImpact, setUserImpact] = useState('')
  const [useCase, setUseCase] = useState('')
  const [benefits, setBenefits] = useState('')
  const [alternatives, setAlternatives] = useState('')
  const [stepsToReproduce, setStepsToReproduce] = useState('')
  const [expectedBehavior, setExpectedBehavior] = useState('')
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [isVisible, setIsVisible] = useState(false)

  // Animation state - sync with modal open/close
  useEffect(() => {
    if (isOpen) {
      setIsVisible(false)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          setIsVisible(true)
        })
      })
    } else {
      setIsVisible(false)
      // Reset form when closing
      setCategory('')
      setTitle('')
      setDescription('')
      setPage('')
      setModule('')
      setPriority('')
      setUserImpact('')
      setUseCase('')
      setBenefits('')
      setAlternatives('')
      setStepsToReproduce('')
      setExpectedBehavior('')
      setError('')
      setSuccess(false)
    }
  }, [isOpen])

  if (!isOpen) return null


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    // Common validation
    if (!category.trim()) {
      setError('Please select a category')
      setLoading(false)
      return
    }

    if (!title.trim() || title.trim().length < 3) {
      setError('Please provide a title (at least 3 characters)')
      setLoading(false)
      return
    }

    if (description.trim().length < 10) {
      setError('Please provide a detailed description (at least 10 characters)')
      setLoading(false)
      return
    }

    try {
      if (type === 'feature_request') {
        // Build detailed feature request
        let detailedDescription = description.trim()
        
        if (category) {
          detailedDescription += `\n\nCategory: ${category}`
        }
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
        if (category) context.issue_type = category
        if (priority) context.priority = priority

        await userAPI.createFeatureRequest(detailedDescription.trim(), Object.keys(context).length > 0 ? context : undefined)
      } else {
        // Build detailed feedback message
        let detailedMessage = description.trim()
        
        if (category) {
          detailedMessage += `\n\nCategory: ${category}`
        }
        if (priority) {
          detailedMessage += `\nPriority: ${priority}`
        }
        if (page) {
          detailedMessage += `\nPage/Location: ${page}`
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

        await userAPI.createFeedback(title.trim(), detailedMessage)
      }
      
      setSuccess(true)
      setTimeout(() => {
        resetForm()
        onSuccess?.()
        onClose()
      }, 2000)
    } catch (err: any) {
      setError(getErrorMessage(err, `Failed to submit ${type === 'feature_request' ? 'feature request' : 'feedback'}`))
    } finally {
      setLoading(false)
    }
  }

  const resetForm = () => {
    setCategory('')
    setTitle('')
    setDescription('')
    setPage('')
    setModule('')
    setPriority('')
    setUserImpact('')
    setUseCase('')
    setBenefits('')
    setAlternatives('')
    setStepsToReproduce('')
    setExpectedBehavior('')
    setError('')
    setSuccess(false)
  }

  const handleClose = () => {
    if (!loading) {
      resetForm()
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
          className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl relative"
          style={{
            zIndex: 10000,
            width: 'min(90vw, 900px)',
            maxWidth: '900px',
            maxHeight: '90vh',
            minHeight: 'min(600px, 80vh)',
            margin: '0 auto',
            opacity: isVisible ? undefined : 0,
            transform: isVisible ? undefined : 'scale(0.95)',
            animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
            display: 'flex',
            flexDirection: 'column',
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
        <div className="p-6 overflow-y-auto flex-1" style={{ maxHeight: 'calc(90vh - 0px)', overflowX: 'hidden' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-sans font-semibold text-text-primary">
              Feature Requests & Feedback
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
                {type === 'feature_request' ? 'Feature Request Submitted!' : 'Feedback Submitted!'}
              </h3>
              <p className="text-sm font-sans text-text-secondary">
                {type === 'feature_request' 
                  ? "Your feature request is being analyzed by AI. You'll be notified when the analysis is complete."
                  : "Thank you for your feedback. We'll review it and get back to you if needed."}
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
                    Category <span className="text-error">*</span>
                  </label>
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] transition-all duration-200"
                    disabled={loading}
                    required
                  >
                    <option value="">Select a category...</option>
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

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    Title <span className="text-error">*</span>
                  </label>
                  <Input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder={type === 'feature_request' ? "Brief, descriptive title for your feature request..." : "Brief summary of your feedback..."}
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
                    Description <span className="text-error">*</span>
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder={type === 'feature_request' ? "Describe the feature or improvement you'd like to see. Be as detailed as possible about what you want and why..." : "Describe your feedback, suggestion, or issue in detail. Include any relevant context..."}
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
                      Page/Location
                    </label>
                    <Input
                      type="text"
                      value={page}
                      onChange={(e) => setPage(e.target.value)}
                      placeholder="e.g., Dashboard, Settings..."
                      disabled={loading}
                    />
                  </div>
                  {type === 'feature_request' && (
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
                  )}
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
                </div>
              </div>

              {/* Additional Details Section */}
              <div className="space-y-4">
                <div className="flex items-center gap-2 mb-3">
                  <Info className="w-5 h-5 text-info" />
                  <h3 className="text-base font-sans font-semibold text-text-primary">
                    Additional Details
                  </h3>
                </div>

                {type === 'feature_request' && (
                  <>
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
                  </>
                )}

                <div>
                  <label className="block text-sm font-sans font-medium text-text-primary mb-2">
                    User Impact
                  </label>
                  <textarea
                    value={userImpact}
                    onChange={(e) => setUserImpact(e.target.value)}
                    placeholder={type === 'feature_request' ? "Who would benefit from this feature? How many users might use it?" : "How does this affect you or other users? (Optional)"}
                    className="w-full px-3 py-2 border border-border dark:border-[#1f2a44] rounded-lg bg-[#f9fafb] dark:bg-[#121b2f] text-text-primary font-sans text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:border-primary dark:focus:border-[#3b82f6] resize-none transition-all duration-200"
                    rows={3}
                    disabled={loading}
                    maxLength={1000}
                  />
                  <p className="mt-1 text-xs font-sans text-text-secondary">
                    {userImpact.length}/1000 characters
                  </p>
                </div>

                {/* Bug Report Specific Fields */}
                {type === 'feedback' && (category === 'Bug Report' || category === 'Performance') && (
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
              </div>

              {/* Helpful Tips */}
              <div className={`p-3 rounded-lg border ${type === 'feature_request' ? 'bg-primary/10 dark:bg-[#3b82f6]/10 border-primary/20' : 'bg-info/10 dark:bg-[#06b6d4]/10 border-info/20'}`}>
                <div className="flex items-start gap-2">
                  {type === 'feature_request' ? (
                    <Zap className="w-4 h-4 text-primary mt-0.5 flex-shrink-0" />
                  ) : (
                    <Info className="w-4 h-4 text-info mt-0.5 flex-shrink-0" />
                  )}
                  <div className="text-xs font-sans text-text-secondary">
                    <p className="font-medium text-text-primary mb-1">
                      {type === 'feature_request' ? 'Tips for better feature requests:' : 'Tips for better feedback:'}
                    </p>
                    <ul className="list-disc list-inside space-y-1 ml-2">
                      {type === 'feature_request' ? (
                        <>
                          <li>Be specific about what you want and why you need it</li>
                          <li>Describe real-world scenarios where this would be useful</li>
                          <li>Explain how it would improve your workflow</li>
                          <li>Consider if there are existing features that could be enhanced instead</li>
                        </>
                      ) : (
                        <>
                          <li>Be specific and provide as much context as possible</li>
                          <li>Include screenshots or examples if relevant</li>
                          <li>Mention your browser and device if reporting a bug</li>
                          <li>Describe the impact on your workflow</li>
                        </>
                      )}
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
                  {loading ? 'Submitting...' : 'Submit'}
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

