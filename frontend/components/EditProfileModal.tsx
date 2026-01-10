'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { userAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { useAuthStore } from '@/lib/store'

interface EditProfileModalProps {
  isOpen: boolean
  onClose: () => void
  user: any
  onUpdate: () => void
}

export function EditProfileModal({ isOpen, onClose, user, onUpdate }: EditProfileModalProps) {
  const { setUser } = useAuthStore()
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    mobile: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (user && isOpen) {
      setFormData({
        name: user.name || '',
        email: user.email || '',
        mobile: user.mobile || '',
      })
      setError('') // Reset error when modal opens
    }
  }, [user, isOpen])

  if (!isOpen || !user) return null

  const validateEmail = (email: string): boolean => {
    if (!email || email.trim() === '') return true // Email is optional
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    return emailRegex.test(email.trim())
  }

  const validateMobile = (mobile: string): boolean => {
    if (!mobile || mobile.trim() === '') {
      return false // Mobile is required
    }
    // Basic mobile validation - digits only, at least 10 characters
    const mobileRegex = /^[0-9]{10,15}$/
    return mobileRegex.test(mobile.trim().replace(/[\s-]/g, ''))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    // Validation
    if (formData.email && formData.email.trim() && !validateEmail(formData.email)) {
      setError('Please enter a valid email address')
      return
    }

    if (!formData.mobile || !formData.mobile.trim()) {
      setError('Mobile number is required')
      return
    }

    if (!validateMobile(formData.mobile)) {
      setError('Please enter a valid mobile number (10-15 digits)')
      return
    }

    setLoading(true)

    try {
      const updateData: any = {
        name: formData.name?.trim() || null,
        email: formData.email?.trim() || null,
        mobile: formData.mobile.trim(),
      }
      
      await userAPI.updateProfile(updateData)
      
      // Refresh full user data from API to get all latest fields
      const refreshedUser = await userAPI.getCurrentUser()
      // Update user in store with complete refreshed data
      setUser(refreshedUser)
      
      // Call onUpdate callback to refresh parent component
      onUpdate()
      onClose()
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to update profile'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Edit Profile"
      maxWidth="max-w-md"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
            User ID (Immutable)
          </label>
          <p className="text-sm font-mono text-[#6b7280] break-all">{user.user_id || user.id}</p>
        </div>

        <div>
          <label className="block text-xs font-sans font-medium text-[#9ca3af] mb-1">
            Username (Immutable)
          </label>
          <p className="text-sm font-mono text-[#6b7280]">{user.username}</p>
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
          placeholder="Enter mobile number"
          required
        />

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

