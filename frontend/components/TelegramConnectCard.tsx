'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Send, CheckCircle, AlertTriangle, MessageSquare, Shield } from 'lucide-react'
import api from '@/lib/api'
import { useAuthStore } from '@/lib/store'

export function TelegramConnectCard() {
    const { user } = useAuthStore()
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState<string | null>(null)
    const [mounted, setMounted] = useState(false)

    // Prevent hydration mismatch by waiting for mount
    useEffect(() => {
        setMounted(true)
    }, [])

    if (!mounted) {
        return (
            <Card title="Security & Notifications" compact>
                <div className="animate-pulse space-y-4">
                    <div className="h-16 bg-gray-200 dark:bg-gray-800 rounded-lg"></div>
                    <div className="h-12 bg-gray-200 dark:bg-gray-800 rounded-lg"></div>
                </div>
            </Card>
        )
    }

    const isConnected = !!user?.telegram_chat_id
    const telegramChatId = user?.telegram_chat_id || '—'

    const handleConnect = async () => {
        setLoading(true)
        setError(null)
        try {
            // Direct API call to the new endpoint
            const response = await api.post('/telegram/connect-token')
            const { deep_link } = response.data

            // Open Telegram in new tab
            window.open(deep_link, '_blank')
        } catch (err: any) {
            console.error("Telegram Connect Error:", err)
            setError("Failed to generate connection link. Please try again.")
        } finally {
            setLoading(false)
        }
    }

    const handleDisconnect = async () => {
        if (!confirm('Are you sure you want to disconnect Telegram? You will no longer receive notifications.')) {
            return
        }

        setLoading(true)
        setError(null)
        try {
            const { userAPI } = await import('@/lib/api')
            await userAPI.disconnectTelegram()

            // Reload page to refresh user data
            window.location.reload()
        } catch (err: any) {
            console.error("Telegram Disconnect Error:", err)
            setError("Failed to disconnect. Please try again.")
        } finally {
            setLoading(false)
        }
    }

    return (
        <Card title="Security & Notifications" compact>
            <div className="space-y-4">

                {/* Connection Status Section */}
                <div className="flex items-center gap-2.5 p-3 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 transition-all duration-200">
                    <div className={`flex-shrink-0 w-10 h-10 rounded-lg flex items-center justify-center border ${isConnected
                        ? 'bg-success/10 border-success/20 text-success'
                        : 'bg-primary/10 border-primary/20 text-primary'
                        }`}>
                        <Send className="w-5 h-5" />
                    </div>

                    <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-0.5">
                            <span className="text-sm font-sans font-semibold text-text-primary">Telegram Notifications</span>
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wide border ${isConnected
                                ? 'bg-success/10 text-success border-success/20'
                                : 'bg-text-secondary/10 text-text-secondary border-text-secondary/20'
                                }`}>
                                {isConnected ? 'Connected' : 'Disconnected'}
                            </span>
                        </div>
                        <p className="text-xs font-sans text-text-secondary leading-relaxed">
                            {isConnected
                                ? "Your Telegram account is connected to receive OTPs and security alerts."
                                : "Connect your Telegram account to receive secure OTPs and instant notifications."
                            }
                        </p>
                    </div>

                    <div className="flex-shrink-0 self-center pl-2">
                        {!isConnected ? (
                            <Button
                                variant="primary"
                                size="sm"
                                onClick={handleConnect}
                                disabled={loading}
                                className="px-3 py-1.5 text-xs whitespace-nowrap"
                            >
                                {loading ? 'Connecting...' : 'Connect Telegram'}
                            </Button>
                        ) : (
                            <Button
                                variant="ghost"
                                size="sm"
                                onClick={handleDisconnect}
                                disabled={loading}
                                className="px-3 py-1.5 text-xs whitespace-nowrap text-error hover:text-error hover:bg-error/10"
                            >
                                {loading ? 'Disconnecting...' : 'Disconnect'}
                            </Button>
                        )}
                    </div>
                </div>

                {/* 2FA Toggle (Only visible when connected) */}
                {isConnected && (
                    <div className="flex items-center justify-between p-3 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle hover:border-primary/40 transition-all duration-200">
                        <div className="flex items-center gap-3">
                            <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center border ${user?.two_factor_enabled ? 'bg-success/10 border-success/20 text-success' : 'bg-text-secondary/10 border-text-secondary/20 text-text-secondary'
                                }`}>
                                <Shield className="w-4 h-4" />
                            </div>
                            <div>
                                <h4 className="text-sm font-sans font-medium text-text-primary">Two-Factor Authentication</h4>
                                <p className="text-xs text-text-secondary">Require OTP via Telegram for login</p>
                            </div>
                        </div>

                        <label className="relative inline-flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                className="sr-only peer"
                                checked={user?.two_factor_enabled || false}
                                onChange={async (e) => {
                                    const enabled = e.target.checked
                                    try {
                                        const { userAPI } = await import('@/lib/api')
                                        await userAPI.updateProfile({ two_factor_enabled: enabled })
                                        const { refreshUser } = useAuthStore.getState()
                                        await refreshUser()
                                    } catch (err) {
                                        console.error("Failed to update 2FA:", err)
                                    }
                                }}
                            />
                            <div className="w-9 h-5 bg-border peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary/20 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-success"></div>
                        </label>
                    </div>
                )}

                {/* Alternative: Direct Command with Mobile Number */}
                {!isConnected && user?.mobile && (
                    <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle">
                        <div className="flex-1 min-w-0">
                            <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-1">
                                Or Send This Command
                            </span>
                            <code className="text-xs font-mono text-primary bg-primary/10 px-2 py-1 rounded border border-primary/20">
                                /start {user.mobile}
                            </code>
                        </div>
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                navigator.clipboard.writeText(`/start ${user.mobile}`)
                            }}
                            className="flex-shrink-0 px-2 py-1 text-xs"
                        >
                            Copy
                        </Button>
                    </div>
                )}

                {/* Chat ID Display (Read-only) - Visible only if connected or for audit */}
                <div className="flex items-center gap-2.5 p-2.5 rounded-lg bg-[#1a2332]/30 dark:bg-[#1a2332]/20 border border-border-subtle">
                    <div className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center border ${isConnected
                        ? 'bg-primary/10 border-primary/20 text-primary'
                        : 'bg-text-secondary/10 border-text-secondary/20 text-text-secondary'}`}>
                        <MessageSquare className="w-4 h-4" />
                    </div>
                    <div className="flex-1 min-w-0">
                        <span className="block text-[10px] font-sans font-medium text-text-secondary uppercase tracking-wider mb-0.5">
                            Telegram Chat ID (Immutable)
                        </span>
                        <span className={`text-xs font-sans font-semibold font-mono truncate cursor-text select-text ${isConnected ? 'text-text-primary' : 'text-text-disabled'}`} suppressHydrationWarning>
                            {telegramChatId}
                        </span>
                    </div>
                </div>

                {error && (
                    <div className="flex items-center gap-2 text-xs text-error mt-2 px-1">
                        <AlertTriangle className="w-3.5 h-3.5" />
                        <span>{error}</span>
                    </div>
                )}
            </div>
        </Card>
    )
}
