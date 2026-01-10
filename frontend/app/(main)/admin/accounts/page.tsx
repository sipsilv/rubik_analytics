'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { SmartTooltip } from '@/components/ui/SmartTooltip'
import { adminAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import { ViewUserModal } from '@/components/ViewUserModal'
import { EditUserModal } from '@/components/EditUserModal'
import { CreateUserModal } from '@/components/CreateUserModal'
import { ChangePasswordModal } from '@/components/ChangePasswordModal'
import { DeleteUserModal } from '@/components/DeleteUserModal'
import { PromoteUserModal } from '@/components/PromoteUserModal'
import { DemoteUserModal } from '@/components/DemoteUserModal'
import { SecondaryModal } from '@/components/ui/Modal'
import { getErrorMessage } from '@/lib/error-utils'
import { useWebSocketStatus, UserStatusUpdate } from '@/lib/useWebSocket'
import { Eye, Edit, Key, ArrowUp, ArrowDown, UserPlus, Trash2, AlertCircle, X, Search } from 'lucide-react'
import { createPortal } from 'react-dom'

export default function AccountsPage() {
  const { user: currentUser } = useAuthStore()
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedUser, setSelectedUser] = useState<any>(null)
  const [viewModalOpen, setViewModalOpen] = useState(false)
  const [editModalOpen, setEditModalOpen] = useState(false)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [changePasswordModalOpen, setChangePasswordModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [promoteModalOpen, setPromoteModalOpen] = useState(false)
  const [demoteModalOpen, setDemoteModalOpen] = useState(false)
  const [actionLoading, setActionLoading] = useState(false)
  const [showSelfDemoteAlert, setShowSelfDemoteAlert] = useState(false)
  const [errorModal, setErrorModal] = useState({ isOpen: false, message: '' })
  const isSuperAdmin = currentUser?.role === 'super_admin'

  // WebSocket connection for real-time status updates
  const handleStatusUpdate = (update: UserStatusUpdate) => {
    console.log('[Accounts] Status update received:', update)
    setUsers(prevUsers => 
      prevUsers.map(user => 
        user.id === update.user_id 
          ? { 
              ...user, 
              is_online: update.is_online,
              last_active_at: update.last_active_at || user.last_active_at
            }
          : user
      )
    )
  }

  const { isConnected: wsConnected } = useWebSocketStatus(handleStatusUpdate)

  const getLiveStatus = (user: any) => {
    // Use is_online from backend if available (real-time WebSocket status)
    // Fallback to calculated status based on last_active_at
    if (user.is_online !== undefined && user.is_online !== null) {
      return user.is_online ? 'LIVE' : 'OFFLINE'
    }
    
    // Fallback: Check if user is currently logged in and active
    // A user is considered "logged in" (LIVE) if:
    // 1. Account is active (is_active === true)
    // 2. Has recent authenticated activity (last_active_at within last 5 minutes)
    
    // First check: Account must be active
    if (!user.is_active) {
      return 'OFFLINE'
    }
    
    const now = Date.now()
    const fiveMinutes = 5 * 60 * 1000 // 5 minutes
    
    // Check last_active_at
    if (user.last_active_at) {
      try {
        const lastActiveTime = new Date(user.last_active_at).getTime()
        if (!isNaN(lastActiveTime)) {
          const timeDiff = now - lastActiveTime
          if (timeDiff >= 0 && timeDiff < fiveMinutes) {
            return 'LIVE'
          }
        }
      } catch (error) {
        console.error(`[Live Status] Error parsing last_active_at:`, error)
      }
    }
    
    return 'OFFLINE'
  }

  useEffect(() => {
    loadUsers()
    
    // Refresh status when page becomes visible (e.g., user switches back to tab)
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        loadUsers()
      }
    }
    
    document.addEventListener('visibilitychange', handleVisibilityChange)
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
    }
  }, [])

  // Show WebSocket connection status indicator (optional, for debugging)
  useEffect(() => {
    if (wsConnected) {
      console.log('[Accounts] WebSocket connected - real-time updates active')
    } else {
      console.log('[Accounts] WebSocket disconnected - using polling fallback')
    }
  }, [wsConnected])

  const loadUsers = async () => {
    try {
      setLoading(true)
      const data = await adminAPI.getUsers()
      console.log('[Accounts] Loaded users data:', data)
      console.log('[Accounts] First user sample:', data[0] ? {
        id: data[0].id,
        user_id: data[0].user_id,
        username: data[0].username,
        is_active: data[0].is_active,
        last_seen: data[0].last_seen,
        last_active_at: data[0].last_active_at,
        has_last_seen: !!data[0].last_seen,
        has_last_active_at: !!data[0].last_active_at
      } : 'No users')
      
      // Log super user details specifically
      const superUsers = data.filter((u: any) => u.role === 'super_admin')
      if (superUsers.length > 0) {
        console.log('[Accounts] Super users found:', superUsers.map((u: any) => ({
          id: u.id,
          username: u.username,
          role: u.role,
          is_active: u.is_active,
          last_active_at: u.last_active_at,
          last_seen: u.last_seen,
          status: getLiveStatus(u)
        })))
      }
      
      setUsers(data)
    } catch (error) {
      console.error('Failed to load users:', error)
      // Keep last known users instead of showing fallback data
      // This prevents status from being lost on temporary API failures
      if (users.length === 0) {
        // Only show fallback if we have no users at all
        setUsers([])
      }
    } finally {
      setLoading(false)
    }
  }

  const handleToggleStatus = async (id: string) => {
    const user = users.find(u => u.id === id)
    // Super User cannot be toggled
    if (user?.role === 'super_admin') {
      setErrorModal({ isOpen: true, message: 'Super User status cannot be toggled' })
      return
    }
    try {
      await adminAPI.toggleUserStatus(id)
      setUsers(users.map(u => u.id === id ? { ...u, is_active: !u.is_active } : u))
    } catch (error: any) {
      console.error('Failed to toggle user status:', error)
      setErrorModal({ isOpen: true, message: getErrorMessage(error, 'Failed to toggle user status') })
    }
  }

  const handlePromoteToSuperAdmin = async () => {
    if (!selectedUser) return
    setActionLoading(true)
    try {
      const updated = await adminAPI.promoteToSuperAdmin(String(selectedUser.id))
      setUsers(users.map(u => u.id === selectedUser.id ? updated : u))
      await loadUsers() // Reload to get fresh data
      setPromoteModalOpen(false)
      setSelectedUser(null)
    } catch (error: any) {
      console.error('Failed to promote user:', error)
      setErrorModal({ isOpen: true, message: getErrorMessage(error, 'Failed to promote user') })
    } finally {
      setActionLoading(false)
    }
  }

  const handleDemoteFromSuperAdmin = async () => {
    if (!selectedUser) return
    
    // Check if user is trying to demote themselves
    if (currentUser?.id === selectedUser.id || currentUser?.user_id === selectedUser.user_id) {
      setDemoteModalOpen(false)
      setShowSelfDemoteAlert(true)
      // No auto-close - user must manually close
      return
    }
    
    setActionLoading(true)
    try {
      const updated = await adminAPI.demoteFromSuperAdmin(String(selectedUser.id))
      setUsers(users.map(u => u.id === selectedUser.id ? updated : u))
      await loadUsers() // Reload to get fresh data
      setDemoteModalOpen(false)
      setSelectedUser(null)
    } catch (error: any) {
      console.error('Failed to demote user:', error)
      const errorMsg = getErrorMessage(error, 'Failed to demote user')
      // Check if error is about self-demotion
      if (errorMsg.toLowerCase().includes('cannot demote yourself') || 
          errorMsg.toLowerCase().includes('cannot demote yourself')) {
        setDemoteModalOpen(false)
        setShowSelfDemoteAlert(true)
        // No auto-close - user must manually close
      } else {
        setErrorModal({ isOpen: true, message: errorMsg })
      }
    } finally {
      setActionLoading(false)
    }
  }

  const handleDeleteUser = async () => {
    if (!selectedUser) return
    setActionLoading(true)
    try {
      await adminAPI.deleteUser(String(selectedUser.id))
      // Remove user from list
      setUsers(users.filter(u => u.id !== selectedUser.id))
      setDeleteModalOpen(false)
      setSelectedUser(null)
    } catch (error: any) {
      console.error('Failed to delete user:', error)
      setErrorModal({ isOpen: true, message: getErrorMessage(error, 'Failed to delete user') })
    } finally {
      setActionLoading(false)
    }
  }


  const getRoleLabel = (role: string) => {
    return role.replace('_', ' ').toUpperCase()
  }

  const getRoleColorClasses = (role: string) => {
    switch (role) {
      case 'super_admin':
        return 'bg-green-500/10 text-green-600 dark:text-green-400'
      case 'admin':
        return 'bg-blue-500/10 text-blue-600 dark:text-blue-400'
      case 'user':
        return 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
      default:
        return 'bg-text-muted/10 text-text-muted'
    }
  }

  // Update search input value only (no filtering)
  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  // Execute search only on button click
  const handleSearchClick = () => {
    setSearchQuery(search)
  }

  // Clear search and reset to default (unfiltered) state
  const handleClearSearch = () => {
    setSearch('')
    setSearchQuery('')
  }

  // Handle Enter key in search input
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  const filteredUsers = users.filter(user =>
    user.username?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.mobile?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.user_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
    String(user.id).includes(searchQuery)
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
            Accounts
          </h1>
          <p className="text-xs font-sans text-text-secondary">
            Manage user accounts and access
          </p>
        </div>
        <div className="flex gap-2">
          <RefreshButton
            variant="secondary"
            size="sm"
            onClick={async () => {
              await loadUsers()
            }}
          />
          <Button 
            size="sm" 
            onClick={() => setCreateModalOpen(true)}
            variant="primary"
          >
            <UserPlus className="w-4 h-4 mr-1.5 btn-icon-hover" aria-label="Create User" />
            Create User
          </Button>
        </div>
      </div>

      <Card compact>
        <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div className="flex-1 max-w-md">
              <Input
                type="text"
                placeholder="Search users..."
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                className="h-9"
              />
            </div>
            <Button
              variant="primary"
              onClick={handleSearchClick}
              size="sm"
              disabled={loading}
              className="h-9 px-4 flex-shrink-0"
            >
              <Search className="w-4 h-4 mr-1.5" />
              Search
            </Button>
            {search && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleClearSearch}
                disabled={loading}
                className="h-9 px-3 flex-shrink-0"
              >
                <X className="w-4 h-4 mr-1.5" />
                Clear
              </Button>
            )}
          </div>
        </div>

        {loading ? (
          <div className="text-center py-8 text-xs font-sans text-text-secondary">Loading...</div>
        ) : (
          <Table>
            <TableHeader>
              <TableHeaderCell className="min-w-[120px]">User ID</TableHeaderCell>
              <TableHeaderCell>Username</TableHeaderCell>
              <TableHeaderCell>Email</TableHeaderCell>
              <TableHeaderCell>Mobile</TableHeaderCell>
              <TableHeaderCell>Role</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Live</TableHeaderCell>
              <TableHeaderCell className="text-right">Actions</TableHeaderCell>
            </TableHeader>
            <TableBody>
              {filteredUsers.map((user, index) => {
                const liveStatus = getLiveStatus(user)
                return (
                  <TableRow key={user?.user_id || user?.id || index} index={index}>
                    <TableCell 
                      className="font-sans text-xs text-text-primary dark:text-[#e5e7eb] font-medium min-w-[120px] whitespace-nowrap"
                    >
                      {user?.user_id || user?.id || 'N/A'}
                    </TableCell>
                    <TableCell className="font-medium">{user.username}</TableCell>
                    <TableCell className="text-text-secondary">{user.email}</TableCell>
                    <TableCell className="text-text-secondary">{user.mobile || 'N/A'}</TableCell>
                    <TableCell>
                      <span className={`text-[10px] font-sans px-1.5 py-0.5 rounded font-semibold uppercase ${getRoleColorClasses(user.role)}`}>
                        {getRoleLabel(user.role)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <button
                        onClick={() => handleToggleStatus(user.id)}
                        disabled={user.role === 'super_admin'}
                        className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors duration-fast ${
                          user.is_active ? 'bg-success' : 'bg-border'
                        } ${
                          user.role === 'super_admin' 
                            ? 'opacity-50 cursor-not-allowed' 
                            : 'cursor-pointer'
                        }`}
                        title={user.role === 'super_admin' ? 'Super User status cannot be toggled' : ''}
                      >
                        <span
                          className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform duration-fast ${
                            user.is_active ? 'translate-x-3.5' : 'translate-x-0.5'
                          }`}
                        />
                      </button>
                    </TableCell>
                    <TableCell>
                      <span className={`text-[10px] font-sans px-1.5 py-0.5 rounded font-semibold uppercase ${
                        liveStatus === 'LIVE'
                          ? 'bg-green-500/10 text-green-600 dark:text-green-400' 
                          : 'bg-text-muted/10 text-text-muted'
                      }`}>
                        {liveStatus || 'OFFLINE'}
                      </span>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 justify-end">
                        <SmartTooltip text="View user details">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={(e) => {
                              e.preventDefault()
                              e.stopPropagation()
                              setSelectedUser(user)
                              setViewModalOpen(true)
                            }}
                            className="p-1.5"
                          >
                            <Eye className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" aria-label="View" />
                          </Button>
                        </SmartTooltip>
                        <SmartTooltip text="Edit user">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={(e) => {
                              e.preventDefault()
                              e.stopPropagation()
                              setSelectedUser(user)
                              setEditModalOpen(true)
                            }}
                            className="p-1.5"
                          >
                            <Edit className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" aria-label="Edit" />
                          </Button>
                        </SmartTooltip>
                        <SmartTooltip text="Change user password">
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={(e) => {
                              e.preventDefault()
                              e.stopPropagation()
                              setSelectedUser(user)
                              setChangePasswordModalOpen(true)
                            }}
                            className="p-1.5"
                          >
                            <Key className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" aria-label="Change password" />
                          </Button>
                        </SmartTooltip>
                        {isSuperAdmin && user.role !== 'super_admin' && (
                          <SmartTooltip text="Promote to super_admin">
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                setSelectedUser(user)
                                setPromoteModalOpen(true)
                              }}
                              className="p-1.5"
                            >
                              <ArrowUp className="w-4 h-4 btn-icon-hover icon-button icon-button-pulse" aria-label="Promote" />
                            </Button>
                          </SmartTooltip>
                        )}
                        {isSuperAdmin && user.role === 'super_admin' && currentUser?.id !== user.id && (
                          <SmartTooltip text="Demote from super_admin">
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                setSelectedUser(user)
                                setDemoteModalOpen(true)
                              }}
                              className="p-1.5"
                            >
                              <ArrowDown className="w-4 h-4 btn-icon-hover icon-button icon-button-pulse" aria-label="Demote" />
                            </Button>
                          </SmartTooltip>
                        )}
                        {isSuperAdmin && user.role !== 'super_admin' && (
                          <SmartTooltip text="Delete user">
                            <Button 
                              variant="ghost" 
                              size="sm"
                              onClick={(e) => {
                                e.preventDefault()
                                e.stopPropagation()
                                setSelectedUser(user)
                                setDeleteModalOpen(true)
                              }}
                              className="p-1.5 hover:text-error"
                            >
                              <Trash2 className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" aria-label="Delete" />
                            </Button>
                          </SmartTooltip>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        )}
      </Card>

      <ViewUserModal
        isOpen={viewModalOpen}
        onClose={() => {
          setViewModalOpen(false)
          setSelectedUser(null)
        }}
        user={selectedUser}
      />

      <EditUserModal
        isOpen={editModalOpen}
        onClose={() => {
          setEditModalOpen(false)
          setSelectedUser(null)
        }}
        user={selectedUser}
        onUpdate={async () => {
          await loadUsers()
        }}
      />

      <CreateUserModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onUpdate={() => {
          loadUsers()
        }}
      />

      <ChangePasswordModal
        isOpen={changePasswordModalOpen}
        onClose={() => {
          setChangePasswordModalOpen(false)
          setSelectedUser(null)
        }}
        user={selectedUser}
        onUpdate={() => {
          loadUsers()
        }}
      />

      <DeleteUserModal
        isOpen={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false)
          setSelectedUser(null)
        }}
        user={selectedUser}
        onConfirm={handleDeleteUser}
        loading={actionLoading}
      />

      <PromoteUserModal
        isOpen={promoteModalOpen}
        onClose={() => {
          setPromoteModalOpen(false)
          setSelectedUser(null)
        }}
        user={selectedUser}
        onConfirm={handlePromoteToSuperAdmin}
        loading={actionLoading}
      />

      <DemoteUserModal
        isOpen={demoteModalOpen}
        onClose={() => {
          setDemoteModalOpen(false)
          setSelectedUser(null)
        }}
        user={selectedUser}
        onConfirm={handleDemoteFromSuperAdmin}
        loading={actionLoading}
      />

      {/* Self-Demote Alert - Centered with Animation */}
      {showSelfDemoteAlert && (
        <SelfDemoteAlert 
          onClose={() => setShowSelfDemoteAlert(false)} 
        />
      )}

      {/* Error Modal - Centered */}
      <SecondaryModal
        isOpen={errorModal.isOpen}
        onClose={() => setErrorModal({ isOpen: false, message: '' })}
        title="Error"
        maxWidth="max-w-md"
      >
        <p className="text-text-secondary mb-6 whitespace-pre-wrap">
          {errorModal.message}
        </p>
        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={() => setErrorModal({ isOpen: false, message: '' })}
          >
            OK
          </Button>
        </div>
      </SecondaryModal>
    </div>
  )
}

// Animated Alert Component for Self-Demote Prevention
function SelfDemoteAlert({ onClose }: { onClose: () => void }) {
  const [mounted, setMounted] = useState(false)
  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    setMounted(true)
    // Trigger animation after mount
    setTimeout(() => setIsVisible(true), 10)
  }, [])

  // No auto-close - removed closing animation logic

  if (!mounted) return null

  const alertContent = (
    <div
      className="fixed inset-0 z-[10000] flex items-center justify-center pointer-events-none"
      style={{
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(4px)',
      }}
      onClick={onClose}
    >
      <div
        className="bg-[#121b2f] border-2 border-warning/50 rounded-lg shadow-2xl p-6 max-w-md mx-4 pointer-events-auto transform"
        onClick={(e) => e.stopPropagation()}
        style={{
          animation: isVisible ? 'slideInBounce 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)' : 'none',
        }}
      >
        <div className="flex items-start gap-4">
          <div className="flex-shrink-0">
            <AlertCircle className="w-8 h-8 text-warning animate-pulse" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-[#e5e7eb] mb-2">
              Cannot Demote Yourself
            </h3>
            <p className="text-sm text-[#9ca3af] mb-4">
              You cannot demote yourself from super_admin. Please ask another super_admin to perform this action.
            </p>
            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-warning/20 hover:bg-warning/30 text-warning rounded-md text-sm font-medium transition-colors flex items-center gap-2"
              >
                <X className="w-4 h-4" />
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
      
      <style dangerouslySetInnerHTML={{__html: `
        @keyframes slideInBounce {
          0% {
            transform: scale(0.8) translateY(-30px);
            opacity: 0;
          }
          50% {
            transform: scale(1.05) translateY(5px);
            opacity: 0.9;
          }
          100% {
            transform: scale(1) translateY(0);
            opacity: 1;
          }
        }
      `}} />
    </div>
  )

  return createPortal(alertContent, document.body)
}
