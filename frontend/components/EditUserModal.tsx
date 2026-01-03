'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { useAuthStore } from '@/lib/store'

interface EditUserModalProps {
  isOpen: boolean
  onClose: () => void
  user: any
  onUpdate: () => void
}

export function EditUserModal({ isOpen, onClose, user, onUpdate }: EditUserModalProps) {
  const { user: currentUser } = useAuthStore()
  const isSuperAdmin = currentUser?.role === 'super_admin'
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    mobile: '',
    role: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (user) {
      setFormData({
        name: user.name || '',
        email: user.email || '',
        mobile: user.mobile || '',
        role: user.role || 'user',
      })
    }
  }, [user])

  if (!isOpen || !user) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Only include role if user is super_admin and target user is not super_admin
      const updateData: any = {
        name: formData.name,
        email: formData.email || null,
        mobile: formData.mobile,
      }
      
      // Only include role if super_admin is editing a non-super_admin user
      if (isSuperAdmin && user.role !== 'super_admin' && formData.role) {
        updateData.role = formData.role
      }
      
      await adminAPI.updateUser(user.id, updateData)
      onUpdate()
      onClose()
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to update user'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Edit User"
      maxWidth="max-w-md"
    >

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
              User ID (Immutable)
            </label>
            <p className="text-sm font-mono text-[#6b7280] break-all">{user.user_id || user.id}</p>
          </div>

          <Input
            label="Full Name"
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Enter full name"
          />

          <Input
            label="Email (Optional)"
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            placeholder="Enter email (optional)"
          />

          <Input
            label="Mobile Number (Required)"
            type="tel"
            value={formData.mobile}
            onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
            required
            placeholder="Enter mobile number"
          />

          {isSuperAdmin && user.role !== 'super_admin' && (
            <div>
              <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
                Role
              </label>
              <select
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                className="w-full px-3 py-2 bg-[#0a1020] border border-[#1f2a44] rounded-md text-sm font-sans text-[#e5e7eb] focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary transition-colors"
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
              <p className="text-xs text-[#6b7280] mt-1">Note: Cannot change super_admin role here. Use promote/demote buttons.</p>
            </div>
          )}

          <ErrorMessage error={error} />

          <div className="flex gap-2 justify-end pt-2">
            <Button variant="secondary" onClick={onClose} disabled={loading} size="sm">
              Cancel
            </Button>
            <Button type="submit" disabled={loading} size="sm">
              {loading ? 'Saving...' : 'Save Changes'}
            </Button>
          </div>
        </form>
    </Modal>
  )
}
