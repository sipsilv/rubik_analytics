'use client'

import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'

interface ViewUserModalProps {
  isOpen: boolean
  onClose: () => void
  user: any
}

export function ViewUserModal({ isOpen, onClose, user }: ViewUserModalProps) {
  if (!isOpen || !user) return null

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="User Details"
      maxWidth="max-w-md"
    >

        <div className="space-y-3">
          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              User ID (Immutable)
            </label>
            <p className="text-sm font-mono text-[#e5e7eb] break-all">{user.user_id || user.id}</p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Username
            </label>
            <p className="text-sm font-sans text-[#e5e7eb]">{user.username}</p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Full Name
            </label>
            <p className="text-sm font-sans text-[#e5e7eb]">{user.name || 'Not set'}</p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Email
            </label>
            <p className="text-sm font-sans text-[#e5e7eb]">{user.email || 'Not set'}</p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Mobile Number (Required)
            </label>
            <p className="text-sm font-mono text-[#e5e7eb]">{user.mobile}</p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Role
            </label>
            <p className="text-sm font-sans text-[#e5e7eb]">{user.role?.replace('_', ' ').toUpperCase()}</p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Status
            </label>
            <p className={`text-sm font-sans font-medium uppercase ${({
                'ACTIVE': 'text-success',
                'INACTIVE': 'text-warning',
                'SUSPENDED': 'text-error',
                'DEACTIVATED': 'text-[#9ca3af]'
              } as Record<string, string>)[user.account_status || (user.is_active ? 'ACTIVE' : 'INACTIVE')] || 'text-[#9ca3af]'
              }`}>
              {user.account_status || (user.is_active ? 'ACTIVE' : 'INACTIVE')}
            </p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Live Status
            </label>
            <p className={`text-sm font-sans font-medium flex items-center gap-2 ${user.account_status === 'ACTIVE' && user.last_active_at
              ? (() => {
                const lastActiveTime = new Date(user.last_active_at).getTime()
                const now = Date.now()
                const thirtyMinutes = 30 * 60 * 1000
                return (now - lastActiveTime) < thirtyMinutes ? 'text-success' : 'text-[#9ca3af]'
              })()
              : 'text-[#9ca3af]'
              }`}>
              {(() => {
                if (user.account_status !== 'ACTIVE') return 'OFFLINE'
                if (!user.last_active_at) return 'OFFLINE'
                const lastActiveTime = new Date(user.last_active_at).getTime()
                const now = Date.now()
                const thirtyMinutes = 30 * 60 * 1000
                return (now - lastActiveTime) < thirtyMinutes ? (
                  <>
                    <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
                    ONLINE
                  </>
                ) : 'OFFLINE'
              })()}
            </p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Created Date
            </label>
            <p className="text-sm font-sans text-[#e5e7eb]">
              {user.created_at ? new Date(user.created_at).toLocaleString() : 'N/A'}
            </p>
          </div>

          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              Last Seen
            </label>
            <p className="text-sm font-sans text-[#e5e7eb]">
              {user.last_seen ? new Date(user.last_seen).toLocaleString() : 'Never'}
            </p>
          </div>
        </div>

        <div className="flex gap-2 justify-end pt-4 mt-4 border-t border-[#1f2a44]">
          <Button variant="secondary" onClick={onClose} size="sm">
            Close
          </Button>
        </div>
    </Modal>
  )
}
