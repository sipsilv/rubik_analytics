'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X } from 'lucide-react'

interface User {
    id: number
    username: string
    account_status?: string
}

interface StatusChangeModalProps {
    isOpen: boolean
    onClose: () => void
    user: User | null
    onUpdate: () => void
}

export function StatusChangeModal({ isOpen, onClose, user, onUpdate }: StatusChangeModalProps) {
    const [loading, setLoading] = useState(false)
    const [status, setStatus] = useState<string>('ACTIVE')
    const [reason, setReason] = useState('')
    const [error, setError] = useState('')
    const [isVisible, setIsVisible] = useState(false)

    // Animation state - sync with modal open/close
    useEffect(() => {
        if (isOpen) {
            // Trigger animation after mount
            setTimeout(() => setIsVisible(true), 10)
        } else {
            setIsVisible(false)
        }
    }, [isOpen])

    if (!isOpen || !user) return null

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError('')

        try {
            await adminAPI.updateUserStatus(String(user.id), status, reason)
            onUpdate()
            onClose()
            setReason('')
            setStatus('ACTIVE')
        } catch (err: any) {
            setError(getErrorMessage(err, 'Failed to update status'))
        } finally {
            setLoading(false)
        }
    }

    const currentStatus = user.account_status || 'ACTIVE'

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm px-4">
            <div 
                className="bg-card w-full max-w-md rounded-lg border border-border shadow-xl p-6 relative"
                style={{
                    animation: isVisible ? 'modalSlideIn 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55)' : 'none',
                }}
            >
                {/* Close Button - Positioned outside modal at top-right with padding */}
                <button 
                    onClick={onClose} 
                    className="absolute top-0 -right-14 z-[100] w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors flex items-center justify-center"
                    title="Close"
                    style={{
                        animation: isVisible ? 'modalSlideIn 0.3s cubic-bezier(0.68, -0.55, 0.265, 1.55)' : 'none',
                    }}
                >
                    <X className="w-5 h-5" />
                </button>
                <h2 className="text-xl font-sans font-semibold text-text-primary mb-1">
                    Change Account Status
                </h2>
                <p className="text-sm font-sans text-text-secondary mb-4">
                    Update status for <span className="font-mono text-primary">{user.username}</span>
                </p>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                        <label className="block text-sm font-sans font-medium text-text-secondary mb-1.5">
                            New Status
                        </label>
                        <select
                            value={status}
                            onChange={(e) => setStatus(e.target.value)}
                            className="w-full px-3 py-2 bg-background border border-border rounded-md text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50"
                        >
                            <option value="ACTIVE">ACTIVE - Full Access</option>
                            <option value="SUSPENDED">SUSPENDED - Temporary Block</option>
                            <option value="DEACTIVATED">DEACTIVATED - No Access</option>
                            <option value="INACTIVE">INACTIVE - Pending Activation</option>
                        </select>
                    </div>

                    <div>
                        <label className="block text-sm font-sans font-medium text-text-secondary mb-1.5">
                            Reason (Required for Audit Log)
                        </label>
                        <textarea
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            required
                            rows={3}
                            placeholder="Why are you changing this status?"
                            className="w-full px-3 py-2 bg-background border border-border rounded-md text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/50 resize-none"
                        />
                    </div>

                    {error && (
                        <div className="p-2 bg-error/10 border border-error rounded text-xs text-error">
                            {error}
                        </div>
                    )}

                    <div className="flex justify-end gap-2 pt-2">
                        <Button variant="ghost" type="button" onClick={onClose} disabled={loading}>
                            Cancel
                        </Button>
                        <Button variant="primary" type="submit" disabled={loading}>
                            {loading ? 'Updating...' : 'Update Status'}
                        </Button>
                    </div>
                </form>
            </div>
        </div>
    )
}
