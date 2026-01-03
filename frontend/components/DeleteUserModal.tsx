'use client'

import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { AlertTriangle } from 'lucide-react'

interface DeleteUserModalProps {
  isOpen: boolean
  onClose: () => void
  user: any
  onConfirm: () => void
  loading?: boolean
}

export function DeleteUserModal({ isOpen, onClose, user, onConfirm, loading = false }: DeleteUserModalProps) {
  if (!isOpen || !user) return null

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Delete User"
      maxWidth="max-w-md"
    >

        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/30 rounded-md">
            <AlertTriangle className="w-6 h-6 flex-shrink-0 mt-0.5" style={{ color: '#ef4444', stroke: '#ef4444', fill: 'rgba(239, 68, 68, 0.1)' }} strokeWidth={2.5} />
            <div className="flex-1">
              <p className="text-sm font-sans font-semibold text-red-500 mb-1">
                Warning: This action cannot be undone!
              </p>
              <p className="text-sm font-sans text-[#9ca3af]">
                Are you sure you want to delete this user? All associated data will be permanently removed.
              </p>
            </div>
          </div>
          <div>
            <div className="bg-[#0a1020] border border-[#1f2a44] rounded-md p-3 space-y-1">
              <p className="text-sm font-sans text-[#e5e7eb]">
                <span className="text-[#9ca3af]">Username:</span> {user.username}
              </p>
              {user.name && (
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">Name:</span> {user.name}
                </p>
              )}
              {user.email && (
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">Email:</span> {user.email}
                </p>
              )}
              <p className="text-sm font-sans text-[#e5e7eb]">
                <span className="text-[#9ca3af]">Mobile:</span> {user.mobile}
              </p>
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
              className="bg-error hover:bg-error/90 text-white"
            >
              {loading ? 'Deleting...' : 'Delete User'}
            </Button>
          </div>
        </div>
    </Modal>
  )
}

