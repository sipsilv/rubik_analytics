'use client'

import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { X } from 'lucide-react'

interface RejectRequestModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: (reason?: string) => void
  loading?: boolean
  request?: {
    name: string
    email: string | null
    mobile: string
    company: string | null
  }
  success?: boolean
}

export function RejectRequestModal({ isOpen, onClose, onConfirm, loading = false, request, success = false }: RejectRequestModalProps) {
  const [reason, setReason] = useState('')
  const [isVisible, setIsVisible] = useState(false)

  // Animation state - sync with modal open/close
  useEffect(() => {
    if (isOpen) {
      // Trigger animation after mount
      setTimeout(() => setIsVisible(true), 10)
    } else {
      setIsVisible(false)
    }
  }, [isOpen])

  if (!isOpen) return null

  const handleConfirm = () => {
    onConfirm(reason.trim() || undefined)
  }

  const handleClose = () => {
    setReason('')
    onClose()
  }

  const modalContent = (
    <div 
      className="fixed inset-0 flex items-center justify-center"
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
        zIndex: 9999,
        transition: 'opacity 0.3s ease-in-out',
        opacity: isVisible ? 1 : 0,
      }}
      onClick={handleClose}
    >
      <div 
        className="relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div 
          className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-md mx-4 relative"
          style={{
            zIndex: 10000,
            animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
          }}
        >
          {/* Close Button */}
          <button 
            onClick={handleClose} 
            className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10001] flex items-center justify-center"
            title="Close"
            aria-label="Close"
            disabled={loading}
            style={{
              animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
            }}
          >
            <X className="w-5 h-5" />
          </button>
          <div className="p-6 max-h-[90vh] overflow-y-auto">
        
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
            {success ? 'Request Rejected' : 'Reject Request'}
          </h2>
        </div>

        {success ? (
          <div className="space-y-4">
            <div className="text-center py-4">
              <div className="mb-4">
                <svg className="w-16 h-16 mx-auto text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-sans font-semibold text-[#e5e7eb] mb-2">
                Request Rejected Successfully
              </h3>
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Button variant="primary" onClick={handleClose} size="sm">
                OK
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-sm font-sans text-[#9ca3af] mb-2">
                Are you sure you want to reject this request?
              </p>
              {request && (
                <div className="bg-[#0a1020] border border-[#1f2a44] rounded-md p-3 space-y-1 mb-3">
                  <p className="text-sm font-sans text-[#e5e7eb]">
                    <span className="text-[#9ca3af]">Name:</span> {request.name}
                  </p>
                  {request.email && (
                    <p className="text-sm font-sans text-[#e5e7eb]">
                      <span className="text-[#9ca3af]">Email:</span> {request.email}
                    </p>
                  )}
                  <p className="text-sm font-sans text-[#e5e7eb]">
                    <span className="text-[#9ca3af]">Mobile:</span> {request.mobile}
                  </p>
                  {request.company && (
                    <p className="text-sm font-sans text-[#e5e7eb]">
                      <span className="text-[#9ca3af]">Company:</span> {request.company}
                    </p>
                  )}
                </div>
              )}
              <div>
                <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">
                  Rejection Reason (Optional)
                </label>
                <Input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Enter rejection reason (optional)"
                  disabled={loading}
                />
              </div>
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Button variant="secondary" onClick={handleClose} disabled={loading} size="sm">
                Cancel
              </Button>
              <Button 
                onClick={handleConfirm} 
                disabled={loading} 
                size="sm"
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {loading ? 'Rejecting...' : 'Reject Request'}
              </Button>
            </div>
          </div>
        )}
          </div>
        </div>
      </div>
    </div>
  )

  return typeof window !== 'undefined' ? createPortal(modalContent, document.body) : null
}

