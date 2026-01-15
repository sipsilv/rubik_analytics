'use client'

import React, { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  children: React.ReactNode
  title?: string
  showCloseButton?: boolean
  closeOnBackdropClick?: boolean
  maxWidth?: string
  minWidth?: string
  zIndex?: number
  preventBodyScroll?: boolean
  scrollable?: boolean
}

/**
 * Standardized Modal Component
 * - Full-screen blur covering entire viewport (sidebar, header, content)
 * - Perfect center alignment (horizontal and vertical)
 * - Consistent styling matching UploadSymbolModal reference
 * - Prevents body scroll when open
 */
export function Modal({
  isOpen,
  onClose,
  children,
  title,
  showCloseButton = true,
  closeOnBackdropClick = true,
  maxWidth = 'max-w-2xl',
  minWidth = '400px',
  zIndex = 9999,
  preventBodyScroll = true,
  scrollable = true,
}: ModalProps) {
  const [mounted, setMounted] = useState(false)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Trigger animation after mount
    if (isOpen) {
      setTimeout(() => setIsVisible(true), 10)
    }
    return () => {
      setMounted(false)
      setIsVisible(false)
    }
  }, [isOpen])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen && preventBodyScroll) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen, preventBodyScroll])

  // Handle ESC key
  useEffect(() => {
    if (!isOpen) return

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  if (!isOpen || !mounted) return null

  const modalContent = (
    <div
      className="fixed inset-0 flex items-center justify-center modal-backdrop"
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
        zIndex: zIndex,
      } as React.CSSProperties}
      onClick={(e) => {
        if (closeOnBackdropClick && e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        className="relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className={`bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full ${maxWidth} mx-4 max-h-[90vh] relative modal-content`}
          style={{
            zIndex: zIndex + 1,
            minWidth: minWidth,
            width: 'auto',
            maxWidth: 'min(100%, calc(100vw - 2rem))', // Dynamic max width: adapts to viewport while respecting Tailwind class constraint
            animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
          }}
        >
          {/* Close Button - Positioned outside modal at top-right, aligned with modal top */}
          {showCloseButton && (
            <button
              onClick={onClose}
              className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10001] flex items-center justify-center modal-close-button"
              title="Close"
              aria-label="Close"
              style={{
                animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
              }}
            >
              <X className="w-5 h-5" />
            </button>
          )}
          {/* Modal Content */}
          <div className={`p-6 max-h-[90vh] ${scrollable ? 'overflow-y-auto' : 'flex flex-col overflow-hidden'}`}>
            {title && (
              <div className="flex items-center justify-between mb-6 shrink-0">
                <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
                  {title}
                </h2>
              </div>
            )}
            {children}
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}

/**
 * Secondary Modal Component (for confirmations, alerts, etc.)
 * - Same full-screen blur and center alignment
 * - Higher z-index to appear above primary modals
 */
export function SecondaryModal({
  isOpen,
  onClose,
  children,
  title,
  showCloseButton = true,
  closeOnBackdropClick = true,
  maxWidth = 'max-w-md',
  minWidth = '400px',
  preventBodyScroll = true,
  scrollable = true,
}: Omit<ModalProps, 'zIndex'>) {
  const [mounted, setMounted] = useState(false)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Trigger animation after mount
    if (isOpen) {
      setTimeout(() => setIsVisible(true), 10)
    }
    return () => {
      setMounted(false)
      setIsVisible(false)
    }
  }, [isOpen])

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen && preventBodyScroll) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen, preventBodyScroll])

  // Handle ESC key
  useEffect(() => {
    if (!isOpen) return

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  if (!isOpen || !mounted) return null

  const modalContent = (
    <div
      className="fixed inset-0 flex items-center justify-center modal-backdrop"
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
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
      onClick={(e) => {
        if (closeOnBackdropClick && e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        className="relative"
        onClick={(e) => e.stopPropagation()}
      >
        <div
          className={`bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full ${maxWidth} mx-4 max-h-[90vh] relative secondary-modal-content`}
          style={{
            zIndex: 10001,
            minWidth: minWidth,
            width: 'auto',
            maxWidth: 'min(100%, calc(100vw - 2rem))', // Dynamic max width: adapts to viewport while respecting Tailwind class constraint
            animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
          }}
        >
          {/* Close Button - Positioned outside modal at top-right, aligned with modal top */}
          {showCloseButton && (
            <button
              onClick={onClose}
              className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10002] flex items-center justify-center secondary-modal-close-button"
              title="Close"
              aria-label="Close"
              style={{
                animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
              }}
            >
              <X className="w-5 h-5" />
            </button>
          )}
          {/* Modal Content */}
          <div className={`p-6 max-h-[90vh] ${scrollable ? 'overflow-y-auto' : 'flex flex-col overflow-hidden'}`}>
            {title && (
              <div className="flex items-center justify-between mb-6 shrink-0">
                <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
                  {title}
                </h2>
              </div>
            )}
            {children}
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}

