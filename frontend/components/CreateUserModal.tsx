'use client'

import { useState } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Modal } from '@/components/ui/Modal'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'

interface CreateUserModalProps {
  isOpen: boolean
  onClose: () => void
  onUpdate: () => void
}

export function CreateUserModal({ isOpen, onClose, onUpdate }: CreateUserModalProps) {
  const [formData, setFormData] = useState({
    username: '',
    name: '',
    email: '',
    mobile: '',
    password: '',
    role: 'user' as 'user' | 'admin',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    
    // Frontend validation - check all required fields
    const missingFields: string[] = []
    if (!formData.username || !formData.username.trim()) {
      missingFields.push('Username')
    }
    if (!formData.email || !formData.email.trim()) {
      missingFields.push('Email')
    }
    if (!formData.mobile || !formData.mobile.trim()) {
      missingFields.push('Mobile Number')
    }
    if (!formData.password || !formData.password.trim()) {
      missingFields.push('Password')
    }
    
    if (missingFields.length > 0) {
      setError(`Fields mandatory: ${missingFields.join(', ')}`)
      return
    }
    
    setLoading(true)

    try {
      // Trim all fields before sending
      const dataToSend = {
        username: formData.username.trim(),
        name: formData.name.trim() || undefined,
        email: formData.email.trim(), // Required field
        mobile: formData.mobile.trim(),
        password: formData.password,
        role: formData.role,
      }
      
      console.log('[CreateUserModal] Sending user data:', { ...dataToSend, password: '***' })
      await adminAPI.createUser(dataToSend)
      console.log('[CreateUserModal] User created successfully')
      
      setFormData({
        username: '',
        name: '',
        email: '',
        mobile: '',
        password: '',
        role: 'user',
      })
      onUpdate()
      onClose()
    } catch (err: any) {
      console.error('[CreateUserModal] Error creating user:', err)
      const errorMsg = getErrorMessage(err, 'Failed to create user')
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Create User"
      maxWidth="max-w-md"
    >

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Username"
            type="text"
            value={formData.username}
            onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            required
            placeholder="Enter username"
          />

          <Input
            label="Full Name"
            type="text"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Enter full name"
          />

          <Input
            label="Email"
            type="email"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            required
            placeholder="Enter email"
          />

          <Input
            label="Mobile Number (Required)"
            type="tel"
            value={formData.mobile}
            onChange={(e) => setFormData({ ...formData, mobile: e.target.value })}
            required
            placeholder="Enter mobile number"
          />

          <Input
            label="Password"
            type="password"
            value={formData.password}
            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            required
            placeholder="Enter password"
          />

          <div className="w-full">
            <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">
              Role
            </label>
            <select
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] font-sans text-base focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/30 focus:border-[#3b82f6] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>

          <ErrorMessage error={error} />

          <div className="flex gap-2 justify-end pt-2">
            <Button variant="secondary" onClick={onClose} disabled={loading} size="sm">
              Cancel
            </Button>
            <Button type="submit" disabled={loading} size="sm">
              {loading ? 'Creating...' : 'Create User'}
            </Button>
          </div>
        </form>
    </Modal>
  )
}
