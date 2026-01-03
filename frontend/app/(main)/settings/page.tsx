'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Input } from '@/components/ui/Input'
import { Button } from '@/components/ui/Button'
import { useAuthStore, useThemeStore } from '@/lib/store'
import { userAPI } from '@/lib/api'

export default function SettingsPage() {
  const { user } = useAuthStore()
  const { theme, setTheme } = useThemeStore()
  const [email, setEmail] = useState(user?.email || '')
  const [mobile, setMobile] = useState(user?.mobile || '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [themeLoading, setThemeLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [mounted, setMounted] = useState(false)
  
  // Prevent hydration mismatch by only rendering user-dependent content after mount
  useEffect(() => {
    setMounted(true)
  }, [])
  
  // Initialize theme from user preference
  useEffect(() => {
    if (user?.theme_preference && (user.theme_preference === 'dark' || user.theme_preference === 'light')) {
      setTheme(user.theme_preference as 'dark' | 'light')
    }
  }, [user, setTheme])
  
  const handleThemeToggle = async () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark'
    setThemeLoading(true)
    try {
      await userAPI.updateTheme(newTheme)
      setTheme(newTheme)
      // Update user in store
      if (user) {
        useAuthStore.getState().setUser({ ...user, theme_preference: newTheme })
      }
    } catch (error) {
      console.error('Failed to update theme:', error)
    } finally {
      setThemeLoading(false)
    }
  }

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setMessage('')
    // TODO: Implement profile update API call
    setTimeout(() => {
      setMessage('Profile updated successfully')
      setLoading(false)
    }, 1000)
  }

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()
    if (newPassword !== confirmPassword) {
      setMessage('Passwords do not match')
      return
    }
    setLoading(true)
    setMessage('')
    // TODO: Implement password change API call
    setTimeout(() => {
      setMessage('Password changed successfully')
      setLoading(false)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    }, 1000)
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
          Settings
        </h1>
        <p className="text-xs font-sans text-text-secondary">
          Manage your account settings and preferences
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Profile Information" compact>
          <form onSubmit={handleProfileUpdate} className="space-y-3">
            <Input
              label="Username"
              type="text"
              value={user?.username || ''}
              disabled
            />
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <Input
              label="Mobile"
              type="tel"
              value={mobile}
              onChange={(e) => setMobile(e.target.value)}
            />
            {message && (
              <div className="bg-success/10 border border-success rounded-sm p-2.5">
                <p className="text-xs font-sans text-success">{message}</p>
              </div>
            )}
            <div className="flex justify-end">
              <Button type="submit" disabled={loading} size="sm">
                {loading ? 'Updating...' : 'Update Profile'}
              </Button>
            </div>
          </form>
        </Card>

        <Card title="Change Password" compact>
          <form onSubmit={handlePasswordChange} className="space-y-3">
            <Input
              label="Current Password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
            />
            <Input
              label="New Password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            <Input
              label="Confirm New Password"
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
            {message && (
              <div className={`rounded-sm p-2.5 ${
                message.includes('match') 
                  ? 'bg-error/10 border border-error' 
                  : 'bg-success/10 border border-success'
              }`}>
                <p className={`text-xs font-sans ${
                  message.includes('match') ? 'text-error' : 'text-success'
                }`}>{message}</p>
              </div>
            )}
            <div className="flex justify-end">
              <Button type="submit" disabled={loading} size="sm">
                {loading ? 'Changing...' : 'Change Password'}
              </Button>
            </div>
          </form>
        </Card>
      </div>

      <Card title="Appearance" compact>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <label className="text-sm font-sans font-medium text-text-primary block mb-1">
                Theme
              </label>
              <p className="text-xs font-sans text-text-secondary">
                Choose between dark and light theme
              </p>
            </div>
            <button
              onClick={handleThemeToggle}
              disabled={themeLoading}
              className="relative inline-flex h-6 w-11 items-center rounded-full bg-[#d1d5db] dark:bg-[#1f2a44] transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Toggle theme"
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform duration-200 ${
                  theme === 'dark' ? 'translate-x-6' : 'translate-x-1'
                }`}
              />
            </button>
          </div>
          <div className="flex items-center gap-2 text-xs font-sans text-text-secondary">
            <span className={theme === 'dark' ? 'text-text-primary font-medium' : ''}>
              Dark
            </span>
            <span>/</span>
            <span className={theme === 'light' ? 'text-text-primary font-medium' : ''}>
              Light
            </span>
          </div>
        </div>
      </Card>

      <Card title="Account Information" compact>
        <div className="space-y-2">
          <div className="flex items-center justify-between py-2 border-b border-border-subtle">
            <span className="text-xs font-sans text-text-secondary">Role</span>
            <span className="text-sm font-sans font-semibold text-text-primary capitalize">
              {mounted && user?.role ? user.role.replace('_', ' ') : '—'}
            </span>
          </div>
          <div className="flex items-center justify-between py-2 border-b border-border-subtle">
            <span className="text-xs font-sans text-text-secondary">Status</span>
            <span className={`text-xs font-sans font-semibold ${
              mounted && user?.is_active ? 'text-success' : 'text-error'
            }`}>
              {mounted && user?.is_active ? 'ACTIVE' : 'INACTIVE'}
            </span>
          </div>
          <div className="flex items-center justify-between py-2">
            <span className="text-xs font-sans text-text-secondary">User ID</span>
            <span className="text-xs font-sans text-text-primary">{mounted && user?.id ? user.id : '—'}</span>
          </div>
        </div>
      </Card>
    </div>
  )
}
