'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { X } from 'lucide-react'

interface ViewConnectionModalProps {
    isOpen: boolean
    onClose: () => void
    connection: any
}

export function ViewConnectionModal({ isOpen, onClose, connection }: ViewConnectionModalProps) {
    const [isVisible, setIsVisible] = useState(false)
    const [testing, setTesting] = useState(false)
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)
    const [localConnection, setLocalConnection] = useState(connection)

    // Animation state - sync with modal open/close
    useEffect(() => {
        if (isOpen) {
            // Reset visibility state first, then trigger animation after mount
            setIsVisible(false)
            // Use requestAnimationFrame for smoother animation start
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    setIsVisible(true)
                })
            })
        } else {
            setIsVisible(false)
        }
    }, [isOpen])

    useEffect(() => {
        setLocalConnection(connection)
        setTestResult(null)
    }, [connection])

    const handleTest = async () => {
        if (!localConnection?.id) return
        setTesting(true)
        setTestResult(null)
        try {
            const { adminAPI } = require('@/lib/api') // Lazy load to avoid circular deps if any
            const res = await adminAPI.testConnection(String(localConnection.id))
            setTestResult({
                success: res.success,
                message: res.message
            })
            // Update local status if returned
            if (res.status) {
                setLocalConnection(prev => ({ ...prev, status: res.status }))
            }
        } catch (e: any) {
            setTestResult({
                success: false,
                message: e.message || 'Test failed'
            })
        } finally {
            setTesting(false)
        }
    }

    if (!isOpen || !localConnection) return null

    // Using same structure as ConnectionModal for consistency
    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                width: '100vw',
                height: '100dvh',
                minHeight: '100vh',
                margin: 0,
                padding: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.5)',
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                opacity: isVisible ? undefined : 0,
                animation: isVisible ? 'backdropFadeIn 0.3s ease-out' : 'none',
            } as React.CSSProperties}
            onClick={(e) => {
                if (e.target === e.currentTarget) {
                    onClose()
                }
            }}
        >
            <div
                className="relative"
                onClick={(e) => e.stopPropagation()}
            >
                <div
                    className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] relative modal-content"
                    style={{
                        opacity: isVisible ? undefined : 0,
                        transform: isVisible ? undefined : 'scale(0.95)',
                        animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
                    }}
                >
                    {/* Close Button - Positioned outside modal at top-right with padding */}
                    <button
                        onClick={onClose}
                        className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10001] flex items-center justify-center"
                        title="Close"
                        aria-label="Close"
                        style={{
                            animation: isVisible ? 'modalFadeIn 0.3s ease-out' : 'none',
                        }}
                    >
                        <X className="w-5 h-5" />
                    </button>

                    <div className="p-6 max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
                                Connection Details
                            </h2>
                            {['AI_ML', 'TELEGRAM_BOT'].includes(localConnection.connection_type) && (
                                <Button
                                    size="sm"
                                    onClick={handleTest}
                                    disabled={testing}
                                    variant={testing ? 'secondary' : 'primary'}
                                >
                                    {testing ? 'Testing...' : 'Test Connection'}
                                </Button>
                            )}
                        </div>

                        {testResult && (
                            <div className={`mb-6 p-3 rounded-lg border text-sm ${testResult.success
                                ? 'bg-success/10 border-success/20 text-success'
                                : 'bg-error/10 border-error/20 text-error'
                                }`}>
                                <div className="font-bold mb-1">
                                    {testResult.success ? '✓ Test Successful' : '✕ Test Failed'}
                                </div>
                                {testResult.message}
                            </div>
                        )}

                        <div className="space-y-6">
                            {/* Header Info */}
                            <div className="flex items-start justify-between">
                                <div>
                                    <h3 className="text-lg font-bold text-text-primary">{localConnection.name}</h3>
                                    <p className="text-sm text-text-secondary">{localConnection.provider} • {localConnection.connection_type}</p>
                                </div>
                                <div className="flex gap-2">
                                    <span className={`px-2 py-1 text-xs font-bold rounded uppercase ${localConnection.status === 'CONNECTED' ? 'bg-success/10 text-success' :
                                        localConnection.status === 'ERROR' ? 'bg-error/10 text-error' : 'bg-gray-500/10 text-gray-500'
                                        }`}>{localConnection.status}</span>
                                    <span className={`px-2 py-1 text-xs font-bold rounded uppercase ${localConnection.environment === 'PROD' ? 'bg-primary/10 text-primary' : 'bg-warning/10 text-warning'
                                        }`}>{localConnection.environment}</span>
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-6 bg-secondary/5 p-4 rounded-lg border border-[#1f2a44]">
                                <div>
                                    <label className="text-xs font-semibold text-text-secondary uppercase">Health</label>
                                    <div className={`mt-1 font-medium ${localConnection.health === 'HEALTHY' ? 'text-success' :
                                        localConnection.health === 'DOWN' ? 'text-error' : 'text-warning'
                                        }`}>{localConnection.health}</div>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-text-secondary uppercase">Last Checked</label>
                                    <div className="mt-1 text-text-primary text-sm">
                                        {localConnection.last_checked_at ? new Date(localConnection.last_checked_at).toLocaleString() : 'Never'}
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-text-secondary uppercase">Created At</label>
                                    <div className="mt-1 text-text-primary text-sm">
                                        {new Date(localConnection.created_at).toLocaleDateString()}
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-text-secondary uppercase">Enabled</label>
                                    <div className="mt-1 text-text-primary text-sm">
                                        {localConnection.is_enabled ? 'Yes' : 'No'}
                                    </div>
                                </div>
                            </div>

                            {/* AI Specific Details */}
                            {localConnection.connection_type === 'AI_ML' && (
                                <div className="bg-secondary/5 p-4 rounded-lg border border-[#1f2a44] space-y-3">
                                    <h4 className="text-sm font-semibold text-text-primary uppercase tracking-wider mb-2">AI Configuration</h4>

                                    <div className="grid grid-cols-2 gap-4">
                                        {localConnection.details?.model_name && (
                                            <div>
                                                <label className="text-xs font-semibold text-text-secondary uppercase">Model Name</label>
                                                <div className="text-sm text-text-primary mt-1 font-mono bg-background/30 px-2 py-1 rounded inline-block">
                                                    {localConnection.details.model_name}
                                                </div>
                                            </div>
                                        )}
                                        {localConnection.details?.base_url && (
                                            <div>
                                                <label className="text-xs font-semibold text-text-secondary uppercase">Base URL</label>
                                                <div className="text-sm text-text-primary mt-1 truncate" title={localConnection.details.base_url}>
                                                    {localConnection.details.base_url}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            <div>
                                <label className="text-xs font-semibold text-text-secondary uppercase mb-2 block">Description</label>
                                <p className="text-sm text-text-primary bg-background/50 p-3 rounded border border-border">
                                    {localConnection.description || 'No description provided.'}
                                </p>
                            </div>

                            {/* Logs Section */}
                            {localConnection.error_logs && (
                                <div className="bg-error/5 border border-error/20 rounded-lg p-4">
                                    <label className="text-xs font-semibold text-error uppercase mb-2 block">Latest Error Log</label>
                                    <pre className="text-xs font-mono text-error whitespace-pre-wrap">
                                        {localConnection.error_logs}
                                    </pre>
                                </div>
                            )}

                            <div className="flex justify-end pt-4 border-t border-[#1f2a44]">
                                <Button onClick={onClose}>Close</Button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
