'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'

interface ChangePasswordModalProps {
  isOpen: boolean
  onClose: () => void
  user: any
  onUpdate: () => void
}

export function ChangePasswordModal({ isOpen, onClose, user, onUpdate }: ChangePasswordModalProps) {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Reset form when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setNewPassword('')
      setConfirmPassword('')
      setError('')
    }
  }, [isOpen])

  if (!isOpen || !user) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validation
    if (!newPassword || newPassword.length < 6) {
      setError('Password must be at least 6 characters long')
      return
    }

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    setLoading(true)

    try {
      await adminAPI.changeUserPassword(user.id, newPassword)
      setNewPassword('')
      setConfirmPassword('')
      // Wait for update to complete, then refresh and close
      await onUpdate()
      onClose()
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to change password'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Change Password"
      maxWidth="max-w-md"
    >

        <div className="mb-4">
          <p className="text-sm font-sans text-[#9ca3af]">
            Changing password for: <span className="text-[#e5e7eb] font-medium">{user.username}</span>
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
            placeholder="Enter new password (min 6 characters)"
            minLength={6}
          />

          <Input
            label="Confirm Password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            placeholder="Confirm new password"
            minLength={6}
          />

          <ErrorMessage error={error} />

          <div className="flex gap-2 justify-end pt-2">
            <Button variant="secondary" onClick={onClose} disabled={loading} size="sm">
              Cancel
            </Button>
            <Button type="submit" disabled={loading} size="sm">
              {loading ? 'Changing...' : 'Change Password'}
            </Button>
          </div>
        </form>
    </Modal>
  )
}
