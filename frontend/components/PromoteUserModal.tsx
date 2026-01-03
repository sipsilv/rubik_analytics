'use client'

import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'

interface PromoteUserModalProps {
  isOpen: boolean
  onClose: () => void
  user: any
  onConfirm: () => void
  loading?: boolean
}

export function PromoteUserModal({ isOpen, onClose, user, onConfirm, loading = false }: PromoteUserModalProps) {
  if (!isOpen || !user) return null

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Promote to Super Admin"
      maxWidth="max-w-md"
    >

        <div className="space-y-4">
          <div>
            <p className="text-sm font-sans text-[#9ca3af] mb-2">
              Are you sure you want to promote this user to super_admin? They will have full system access.
            </p>
            <div className="bg-[#0a1020] border border-[#1f2a44] rounded-md p-3 space-y-1">
              <p className="text-sm font-sans text-[#e5e7eb]">
                <span className="text-[#9ca3af]">Username:</span> {user.username}
              </p>
              {user.name && (
                <p className="text-sm font-sans text-[#e5e7eb]">
                  <span className="text-[#9ca3af]">Name:</span> {user.name}
                </p>
              )}
              <p className="text-sm font-sans text-[#e5e7eb]">
                <span className="text-[#9ca3af]">Current Role:</span> <span className="uppercase">{user.role}</span>
              </p>
            </div>
            <div className="mt-3 p-3 bg-warning/10 border border-warning/20 rounded-md">
              <p className="text-xs font-sans text-warning">
                ⚠️ Super Admin users have unrestricted access to all system features and cannot be deactivated or have their roles changed.
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
              className="bg-warning hover:bg-warning/90 text-white"
            >
              {loading ? 'Promoting...' : 'Promote to Super Admin'}
            </Button>
          </div>
        </div>
    </Modal>
  )
}

