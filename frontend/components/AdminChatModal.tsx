'use client'

import { useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Send, MessageSquare } from 'lucide-react'
import { adminAPI } from '@/lib/api'

interface AdminChatModalProps {
    isOpen: boolean
    onClose: () => void
    user: any
    loading?: boolean
}

export function AdminChatModal({ isOpen, onClose, user, loading = false }: AdminChatModalProps) {
    const [message, setMessage] = useState('')
    const [sending, setSending] = useState(false)
    const [success, setSuccess] = useState(false)

    const handleSend = async () => {
        if (!message.trim() || !user) return
        setSending(true)
        setSuccess(false)
        try {
            await adminAPI.sendMessage(user.id, message)
            setMessage('')
            setSuccess(true)
            // Close modal after 1 second to show success message
            setTimeout(() => {
                setSuccess(false)
                onClose()
            }, 1000)
        } catch (error: any) {
            console.error('Failed to send message:', error)
            // Even on error, close the modal after showing error
            setTimeout(() => {
                onClose()
            }, 2000)
        } finally {
            setSending(false)
        }
    }

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    if (!isOpen || !user) return null

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            title={`Send Message to ${user.username}`}
            maxWidth="max-w-md"
        >
            <div className="space-y-4">
                {/* Info Banner */}
                <div className="p-3 rounded-lg bg-primary/10 border border-primary/20 flex gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                        <MessageSquare className="w-4 h-4 text-primary" />
                    </div>
                    <div className="text-xs text-text-secondary leading-relaxed">
                        <p className="mb-1">
                            <strong>User:</strong> {user.username} ({user.mobile})
                        </p>
                        <p>
                            Messages will be sent to the user's Telegram account. You will receive their replies in your Telegram.
                        </p>
                    </div>
                </div>

                {/* Message Input */}
                <div>
                    <label className="block text-xs font-sans font-medium text-text-secondary mb-1.5">
                        Message Content
                    </label>
                    <textarea
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="Type your message here..."
                        className="w-full h-32 px-3 py-2 bg-background border border-border rounded-lg focus:outline-none focus:ring-1 focus:ring-primary text-sm font-sans text-text-primary resize-none placeholder:text-text-muted transition-colors"
                        disabled={sending || !user.telegram_chat_id}
                        autoFocus
                    />
                </div>

                {/* Success Message */}
                {success && (
                    <div className="p-2 rounded-lg bg-success/10 border border-success/20 text-success text-xs">
                        ✓ Message sent successfully
                    </div>
                )}

                {/* Warning if not connected */}
                {!user.telegram_chat_id && (
                    <div className="p-2 rounded-lg bg-warning/10 border border-warning/20 text-warning text-xs">
                        User has not connected Telegram yet
                    </div>
                )}

                {/* Actions */}
                <div className="flex justify-end gap-2 pt-2">
                    <Button
                        variant="ghost"
                        onClick={onClose}
                        disabled={sending}
                        size="sm"
                    >
                        Close
                    </Button>
                    <Button
                        variant="primary"
                        onClick={handleSend}
                        disabled={sending || !message.trim() || !user.telegram_chat_id}
                        size="sm"
                    >
                        {sending ? 'Sending...' : (
                            <>
                                <Send className="w-4 h-4 mr-1.5" />
                                Send Message
                            </>
                        )}
                    </Button>
                </div>
            </div>
        </Modal>
    )
}
