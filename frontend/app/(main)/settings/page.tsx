'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useAuthStore } from '@/lib/store'
import { userAPI } from '@/lib/api'
import { EditProfileModal } from '@/components/EditProfileModal'
import { UserChangePasswordModal } from '@/components/UserChangePasswordModal'
import { Edit, Key, User, Mail, Phone, UserCircle, Shield, Hash, Calendar } from 'lucide-react'
import { SmartTooltip } from '@/components/ui/SmartTooltip'

export default function SettingsPage() {
  const { user, setUser } = useAuthStore()
  const [mounted, setMounted] = useState(false)
  const [editProfileModalOpen, setEditProfileModalOpen] = useState(false)
  const [changePasswordModalOpen, setChangePasswordModalOpen] = useState(false)
  
  // Prevent hydration mismatch by only rendering user-dependent content after mount
  useEffect(() => {
    setMounted(true)
  }, [])
  
  // Refresh user data on mount to ensure we have latest data
  useEffect(() => {
    const refreshUserData = async () => {
      try {
        const updatedUser = await userAPI.getCurrentUser()
        setUser(updatedUser)
      } catch (error) {
        console.error('Failed to refresh user data:', error)
      }
    }
    refreshUserData()
  }, [setUser])

  const handleProfileUpdate = async () => {
    // Refresh user data after profile update
    try {
      const updatedUser = await userAPI.getCurrentUser()
      setUser(updatedUser)
    } catch (error) {
      console.error('Failed to refresh user data:', error)
    }
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

      <Card title="Account Management" compact>
        <div className="space-y-3">
          {/* Profile Information Cards - Same as Admin View */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 hover:shadow-md transition-all duration-200">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/20 dark:border-primary/30">
                <Hash className="w-4.5 h-4.5 text-primary dark:text-[#60a5fa]" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">User ID (Immutable)</span>
                <span className="text-xs font-sans font-semibold text-text-primary font-mono truncate" suppressHydrationWarning>
                  {user?.user_id || (user?.id ? String(user.id) : '—')}
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 hover:shadow-md transition-all duration-200">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/20 dark:border-primary/30">
                <User className="w-4.5 h-4.5 text-primary dark:text-[#60a5fa]" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">Username</span>
                <span className="text-xs font-sans font-semibold text-text-primary truncate" suppressHydrationWarning>
                  {user?.username || '—'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 hover:shadow-md transition-all duration-200">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/20 dark:border-primary/30">
                <UserCircle className="w-4.5 h-4.5 text-primary dark:text-[#60a5fa]" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">Full Name</span>
                <span className="text-xs font-sans font-semibold text-text-primary truncate" suppressHydrationWarning>
                  {user?.name || 'Not set'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 hover:shadow-md transition-all duration-200">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/20 dark:border-primary/30">
                <Mail className="w-4.5 h-4.5 text-primary dark:text-[#60a5fa]" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">Email</span>
                <span className="text-xs font-sans font-semibold text-text-primary truncate" suppressHydrationWarning>
                  {user?.email || 'Not set'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 hover:shadow-md transition-all duration-200">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/20 dark:border-primary/30">
                <Phone className="w-4.5 h-4.5 text-primary dark:text-[#60a5fa]" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">Mobile Number (Required)</span>
                <span className="text-xs font-sans font-semibold text-text-primary font-mono truncate" suppressHydrationWarning>
                  {user?.mobile || '—'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 hover:shadow-md transition-all duration-200">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/20 dark:border-primary/30">
                <Shield className="w-4.5 h-4.5 text-primary dark:text-[#60a5fa]" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">Role</span>
                <span className="text-xs font-sans font-semibold text-text-primary uppercase" suppressHydrationWarning>
                  {user?.role ? user.role.replace('_', ' ').toUpperCase() : '—'}
                </span>
              </div>
            </div>
          </div>

          {/* Created Date */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
            <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 hover:shadow-md transition-all duration-200">
              <div className="flex-shrink-0 w-9 h-9 rounded-lg bg-primary/10 dark:bg-primary/15 flex items-center justify-center border border-primary/20 dark:border-primary/30">
                <Calendar className="w-4.5 h-4.5 text-primary dark:text-[#60a5fa]" />
              </div>
              <div className="flex-1 min-w-0">
                <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">Created Date</span>
                <span className="text-xs font-sans font-semibold text-text-primary truncate" suppressHydrationWarning>
                  {user?.created_at 
                    ? (mounted ? new Date(user.created_at).toLocaleString() : 'Loading...')
                    : 'N/A'}
                </span>
              </div>
            </div>
          </div>

          {/* Action Buttons Row */}
          <div className="flex items-center gap-2 justify-end pt-1 border-t border-border-subtle">
            <Button 
              variant="primary" 
              size="sm"
              onClick={() => setEditProfileModalOpen(true)}
              className="px-3 py-1.5 text-xs"
            >
              <Edit className="w-3.5 h-3.5 mr-1.5 btn-icon-hover icon-button icon-button-bounce" aria-label="Edit Profile" />
              Edit Profile
            </Button>
            <Button 
              variant="primary" 
              size="sm"
              onClick={() => setChangePasswordModalOpen(true)}
              className="px-3 py-1.5 text-xs"
            >
              <Key className="w-3.5 h-3.5 mr-1.5 btn-icon-hover icon-button icon-button-bounce" aria-label="Change Password" />
              Change Password
            </Button>
          </div>
        </div>
      </Card>

      <EditProfileModal
        isOpen={editProfileModalOpen}
        onClose={() => setEditProfileModalOpen(false)}
        user={user}
        onUpdate={handleProfileUpdate}
      />

      <UserChangePasswordModal
        isOpen={changePasswordModalOpen}
        onClose={() => setChangePasswordModalOpen(false)}
        user={user}
        onUpdate={() => {}}
      />
    </div>
  )
}
