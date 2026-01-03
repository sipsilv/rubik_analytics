'use client'

import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/components/ui/Button'
import { X } from 'lucide-react'

interface ApproveRequestModalProps {
  isOpen: boolean
  onClose: () => void
  onConfirm: () => void
  loading?: boolean
  request?: {
    name: string
    email: string | null
    mobile: string
    company: string | null
  }
  successData?: {
    user_id: string
    username: string
    email: string | null
    mobile: string
    role: string
    temp_password: string
  }
}

export function ApproveRequestModal({ isOpen, onClose, onConfirm, loading = false, request, successData }: ApproveRequestModalProps) {
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

  const isSuccess = !!successData

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
      onClick={onClose}
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
            onClick={onClose} 
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
            {isSuccess ? 'Request Approved' : 'Approve Request'}
          </h2>
        </div>

        {isSuccess ? (
          <div className="space-y-4">
            <div className="text-center py-4">
              <div className="mb-4">
                <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: '#10b981', stroke: '#10b981' }}>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <h3 className="text-lg font-sans font-semibold text-[#e5e7eb] mb-2">
                Account Created Successfully!
              </h3>
            </div>

            <div className="bg-[#0a1020] border border-[#1f2a44] rounded-md p-4 space-y-2">
              <p className="text-sm font-sans text-[#9ca3af] mb-2 font-semibold">User Details:</p>
              <div className="space-y-1.5">
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">User ID:</span> <span className="font-mono">{successData.user_id}</span>
                </p>
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">Username:</span> {successData.username}
                </p>
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">Email:</span> {successData.email || 'N/A'}
                </p>
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">Mobile:</span> {successData.mobile}
                </p>
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">Role:</span> {successData.role}
                </p>
                <div className="mt-3 pt-3 border-t border-[#1f2a44]">
                  <p className="text-sm font-sans text-[#e5e7eb] mb-1">
                    <span className="text-[#9ca3af]">Temporary Password:</span>
                  </p>
                  <p className="text-sm font-mono font-semibold text-yellow-400 bg-[#1f2a44] p-2 rounded break-all">
                    {successData.temp_password}
                  </p>
                </div>
              </div>
            </div>

            <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-md">
              <p className="text-xs font-sans text-yellow-400">
                ⚠️ <span className="font-semibold">IMPORTANT:</span> Share the temporary password with the user securely. User must change password after first login.
              </p>
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Button variant="primary" onClick={onClose} size="sm">
                OK
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <p className="text-sm font-sans text-[#9ca3af] mb-2">
                Are you sure you want to approve this request and create a user account?
              </p>
              {request && (
                <div className="bg-[#0a1020] border border-[#1f2a44] rounded-md p-3 space-y-1">
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
              <div className="mt-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded-md">
                <p className="text-xs font-sans text-blue-400 mb-1 font-semibold">This will:</p>
                <ul className="text-xs font-sans text-[#9ca3af] space-y-0.5 list-disc list-inside">
                  <li>Generate a unique User ID</li>
                  <li>Create the user account</li>
                  <li>Set account status to ACTIVE</li>
                  <li>Generate a temporary password</li>
                </ul>
              </div>
            </div>

            <div className="flex gap-2 justify-end pt-2">
              <Button variant="secondary" onClick={onClose} disabled={loading} size="sm">
                Cancel
              </Button>
              <Button 
                onClick={onConfirm} 
                disabled={loading} 
                size="sm"
              >
                {loading ? 'Approving...' : 'Approve & Create Account'}
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

