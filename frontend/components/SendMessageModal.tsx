'use client'

import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Send, AlertTriangle } from 'lucide-react'

interface SendMessageModalProps {
    isOpen: boolean
    onClose: () => void
    user: any
    onSend: (userId: string, message: string) => Promise<void>
    loading?: boolean
}

export function SendMessageModal({ isOpen, onClose, user, onSend, loading = false }: SendMessageModalProps) {
    const [message, setMessage] = useState('')

    const handleSend = async () => {
        if (!message.trim()) return
        await onSend(user.id, message)
        setMessage('')
    }

    if (!isOpen || !user) return null

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            title={`Message ${user.username}`}
            maxWidth="max-w-md"
        >
            <div className="space-y-4">
                {/* Info Banner */}
                <div className="p-3 rounded-lg bg-primary/10 border border-primary/20 flex gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                        <Send className="w-4 h-4 text-primary" />
                    </div>
                    <div className="text-xs text-text-secondary leading-relaxed">
                        This message will be sent directly to the user's connected Telegram account.
                    </div>
                </div>

                <div>
                    <label className="block text-xs font-sans font-medium text-text-secondary mb-1.5">
                        Message Content
                    </label>
                    <textarea
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Type your message here..."
                        className="w-full h-32 px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-primary text-sm font-sans text-text-primary resize-none placeholder:text-text-muted transition-colors"
                        autoFocus
                    />
                </div>

                <div className="flex justify-end gap-2 pt-2">
                    <Button
                        variant="ghost"
                        onClick={onClose}
                        disabled={loading}
                        size="sm"
                    >
                        Cancel
                    </Button>
                    <Button
                        variant="primary"
                        onClick={handleSend}
                        disabled={loading || !message.trim()}
                        size="sm"
                    >
                        {loading ? 'Sending...' : 'Send Message'}
                    </Button>
                </div>
            </div>
        </Modal>
    )
}
