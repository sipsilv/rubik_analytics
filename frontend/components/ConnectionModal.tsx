'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X } from 'lucide-react'

interface ConnectionModalProps {
    isOpen: boolean
    onClose: () => void
    connection?: any
    onUpdate: () => void
}

const CONNECTION_TYPES = [
    { value: 'MARKET_DATA', label: 'Market Data' },
    { value: 'BROKER', label: 'Broker / Trading' },
    { value: 'AI_ML', label: 'AI / ML Model' },
    { value: 'NEWS', label: 'News & Events' },
    { value: 'SOCIAL', label: 'Social / Sentiment' },
    { value: 'INTERNAL', label: 'Internal System' },
    { value: 'TELEGRAM_BOT', label: 'Telegram Bot' },
    { value: 'TELEGRAM_USER', label: 'Telegram User' },
]

const ENVIRONMENTS = [
    { value: 'PROD', label: 'Production' },
    { value: 'SANDBOX', label: 'Sandbox' },
]

export function ConnectionModal({ isOpen, onClose, connection, onUpdate }: ConnectionModalProps) {
    const [formData, setFormData] = useState({
        name: '',
        connection_type: 'MARKET_DATA',
        provider: '',
        description: '',
        environment: 'PROD',
        is_enabled: false,
        details: {} as Record<string, any>
    })

    // Dynamic fields state
    const [apiKey, setApiKey] = useState('')
    const [apiSecret, setApiSecret] = useState('')
    const [baseUrl, setBaseUrl] = useState('')

    // TrueData token fields
    const [authType, setAuthType] = useState<'API_KEY' | 'TOKEN'>('API_KEY')
    const [username, setUsername] = useState('')
    const [password, setPassword] = useState('')
    const [authUrl, setAuthUrl] = useState('https://auth.truedata.in/token')
    const [websocketPort, setWebsocketPort] = useState('8086')

    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [isVisible, setIsVisible] = useState(false)

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
        if (connection) {
            setFormData({
                name: connection.name,
                connection_type: connection.connection_type,
                provider: connection.provider,
                description: connection.description || '',
                environment: connection.environment,
                is_enabled: connection.is_enabled,
                details: connection.details || {}
            })

            // Check if this is a TrueData connection (normalize provider name like backend)
            const providerNormalized = connection.provider?.toUpperCase().replace(/\s+/g, '').replace(/_/g, '').replace(/-/g, '') || ''
            if (providerNormalized === 'TRUEDATA') {
                setAuthType('TOKEN')
                // Load existing URL and port from connection if available
                setAuthUrl(connection.details?.auth_url || connection.url || 'https://auth.truedata.in/token')
                setWebsocketPort(connection.details?.websocket_port || connection.port || '8086')
                setUsername(connection.details?.username || '')
                // Don't populate password - user must re-enter for updates
                setPassword('')
            } else if (connection.connection_type === 'TELEGRAM_BOT') {
                // Don't pre-fill bot token (it's masked) - user must re-enter to update
                setApiKey('')
                setApiSecret('')
            } else if (connection.connection_type === 'TELEGRAM_USER') {
                setApiKey(connection.details?.api_id || '')
                setBaseUrl(connection.details?.session_path || '')
                // api_hash is masked, don't populate - user must re-enter to update
                setApiSecret('')
            } else {
                setAuthType('API_KEY')
                // For generic connections, don't populate secrets
                setApiKey('')
                setApiSecret('')
                setBaseUrl(connection.details?.base_url || '')
            }
        } else {
            resetForm()
        }
    }, [connection, isOpen])

    const resetForm = () => {
        setFormData({
            name: '',
            connection_type: 'MARKET_DATA',
            provider: '',
            description: '',
            environment: 'PROD',
            is_enabled: false,
            details: {}
        })
        setApiKey('')
        setApiSecret('')
        setBaseUrl('')
        setAuthType('API_KEY')
        setUsername('')
        setPassword('')
        setAuthUrl('https://auth.truedata.in/token')
        setWebsocketPort('8086')
        setError('')
    }

    if (!isOpen) return null

    const handleClose = () => {
        setIsVisible(false)
        onClose()
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        setLoading(true)
        setError('')

        try {
            // Build details based on auth type
            const details: Record<string, any> = {}

            // Normalize provider name like backend
            const providerNormalized = formData.provider?.toUpperCase().replace(/\s+/g, '').replace(/_/g, '').replace(/-/g, '') || ''
            if (authType === 'TOKEN' || providerNormalized === 'TRUEDATA') {
                // TrueData token authentication
                // For NEW connections, username and password are required
                if (!connection) {
                    if (!username || !username.trim() || !password || !password.trim()) {
                        setError('Username and password are required for TrueData connections')
                        setLoading(false)
                        return
                    }
                    details.username = username.trim()
                    details.password = password.trim()
                } else {
                    // For UPDATES, only include if provided (backend will merge with existing)
                    if (username && username.trim()) {
                        details.username = username.trim()
                    }
                    if (password && password.trim()) {
                        details.password = password.trim()
                    }
                }
                // Always include auth_url and websocket_port
                details.auth_url = authUrl || 'https://auth.truedata.in/token'
                if (websocketPort && websocketPort.trim()) {
                    details.websocket_port = websocketPort.trim()
                }
            } else if (formData.connection_type === 'TELEGRAM_BOT') {
                // Telegram Bot: apiKey -> bot_token
                if (apiKey && apiKey.trim()) {
                    details.bot_token = apiKey.trim()
                }
            } else if (formData.connection_type === 'TELEGRAM_USER') {
                // Telegram User: apiKey -> api_id, apiSecret -> api_hash, baseUrl -> session_path
                if (apiKey && apiKey.trim()) {
                    details.api_id = apiKey.trim()
                }
                if (apiSecret && apiSecret.trim()) {
                    details.api_hash = apiSecret.trim()
                }
                if (baseUrl && baseUrl.trim()) {
                    details.session_path = baseUrl.trim()
                }
            } else {
                // Standard API key authentication
                if (apiKey && apiKey.trim()) {
                    details.api_key = apiKey.trim()
                }
                if (apiSecret && apiSecret.trim()) {
                    details.api_secret = apiSecret.trim()
                }
                if (baseUrl && baseUrl.trim()) {
                    details.base_url = baseUrl.trim()
                }
            }

            const payload: any = {
                ...formData
            }

            // Always include details (backend will handle merging for updates)
            payload.details = details
            console.log('[ConnectionModal] Sending payload with details keys:', Object.keys(details))

            if (connection) {
                await adminAPI.updateConnection(String(connection.id), payload)
            } else {
                await adminAPI.createConnection(payload)
            }
            onUpdate()
            onClose()
        } catch (err: any) {
            setError(getErrorMessage(err, 'Failed to save connection'))
        } finally {
            setLoading(false)
        }
    }

    // Dynamic Fields logic could be more complex based on type
    // For now, standard API Key/Secret fields for all

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
                    handleClose()
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
                    {/* Close Button - Positioned outside modal at top-right, aligned with modal top */}
                    <button
                        onClick={handleClose}
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
                                {connection ? 'Edit Connection' : 'Add New Connection'}
                            </h2>
                        </div>

                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="grid grid-cols-2 gap-4">
                                <Input
                                    label="Connection Name"
                                    value={formData.name}
                                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                                    required
                                    placeholder={formData.provider?.toUpperCase() === 'TRUEDATA' ? 'TrueData' : 'e.g. Binance Production'}
                                />

                                <div className="w-full">
                                    <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">Type</label>
                                    <select
                                        value={formData.connection_type}
                                        onChange={(e) => setFormData({ ...formData, connection_type: e.target.value })}
                                        className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                        disabled={!!connection} // Type usually immutable?
                                    >
                                        {CONNECTION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                                    </select>
                                </div>
                            </div>


                            <div className="grid grid-cols-2 gap-4">
                                <Input
                                    label="Provider"
                                    value={formData.provider}
                                    onChange={(e) => {
                                        const newProvider = e.target.value
                                        setFormData(prev => ({ ...prev, provider: newProvider }))
                                        // Auto-detect TrueData and switch to TOKEN auth (normalize like backend)
                                        const providerNormalized = newProvider.toUpperCase().replace(/\s+/g, '').replace(/_/g, '').replace(/-/g, '')
                                        if (providerNormalized === 'TRUEDATA') {
                                            setAuthType('TOKEN')
                                        } else if (authType === 'TOKEN') {
                                            setAuthType('API_KEY')
                                        }
                                    }}
                                    required
                                    placeholder="e.g. Binance, OpenAI, TrueData"
                                />

                                <div className="grid grid-cols-2 gap-4">
                                    <div className="w-full">
                                        <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">Environment</label>
                                        <select
                                            value={formData.environment}
                                            onChange={(e) => setFormData({ ...formData, environment: e.target.value })}
                                            className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                        >
                                            {ENVIRONMENTS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                                        </select>
                                    </div>

                                    <div className="w-full flex items-end pb-2">
                                        <label className="flex items-center gap-3 cursor-pointer">
                                            <div className="relative">
                                                <input
                                                    type="checkbox"
                                                    className="sr-only"
                                                    checked={formData.is_enabled}
                                                    onChange={(e) => setFormData({ ...formData, is_enabled: e.target.checked })}
                                                />
                                                <div className={`w-10 h-6 rounded-full shadow-inner transition-colors ${formData.is_enabled ? 'bg-success' : 'bg-gray-700'}`}></div>
                                                <div className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full shadow transition-transform ${formData.is_enabled ? 'translate-x-4' : 'translate-x-0'}`}></div>
                                            </div>
                                            <span className="text-sm font-sans font-medium text-[#9ca3af]">
                                                {formData.is_enabled ? 'Enabled' : 'Disabled'}
                                            </span>
                                        </label>
                                    </div>
                                </div>
                            </div>

                            <div className="w-full">
                                <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">Description</label>
                                <textarea
                                    value={formData.description}
                                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                                    className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                    rows={2}
                                />
                            </div>

                            {/* Dynamic Configuration Section */}
                            <div className="border border-[#1f2a44] p-4 rounded-lg space-y-4 bg-secondary/5 mt-4">
                                <h3 className="text-sm font-semibold text-text-primary uppercase tracking-wider">Configuration</h3>

                                {/* Auto-detect auth type for TrueData */}
                                {(() => {
                                    const providerNormalized = formData.provider?.toUpperCase().replace(/\s+/g, '').replace(/_/g, '').replace(/-/g, '') || ''
                                    return providerNormalized === 'TRUEDATA' || authType === 'TOKEN'
                                })() ? (
                                    <>
                                        <div className="w-full">
                                            <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">Authentication Type</label>
                                            <select
                                                value={authType}
                                                onChange={(e) => setAuthType(e.target.value as 'API_KEY' | 'TOKEN')}
                                                className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                                disabled={!!connection}
                                            >
                                                <option value="TOKEN">Token</option>
                                            </select>
                                        </div>

                                        <Input
                                            label="Base Auth URL"
                                            value={authUrl}
                                            onChange={(e) => setAuthUrl(e.target.value)}
                                            placeholder="https://auth.truedata.in/token"
                                        />

                                        <Input
                                            label="Username"
                                            value={username}
                                            onChange={(e) => setUsername(e.target.value)}
                                            required={!connection}
                                            placeholder={connection ? "Enter username to update" : "Enter username"}
                                        />

                                        <Input
                                            label="Password"
                                            value={password}
                                            onChange={(e) => setPassword(e.target.value)}
                                            type="password"
                                            required={!connection}
                                            placeholder={connection ? "Enter password to update (leave blank to keep existing)" : "Enter password"}
                                        />

                                        <Input
                                            label="WebSocket Port"
                                            value={websocketPort}
                                            onChange={(e) => setWebsocketPort(e.target.value)}
                                            type="number"
                                            min="1"
                                            placeholder="8086"
                                        />
                                    </>
                                ) : formData.connection_type === 'TELEGRAM_BOT' ? (
                                    <>
                                        <Input
                                            label="Bot Token"
                                            value={apiKey}
                                            onChange={(e) => setApiKey(e.target.value)}
                                            type="password"
                                            placeholder={connection ? "Leave blank to keep unchanged" : "Enter Telegram Bot Token"}
                                        />
                                    </>
                                ) : formData.connection_type === 'TELEGRAM_USER' ? (
                                    <>
                                        <Input
                                            label="API ID"
                                            value={apiKey}
                                            onChange={(e) => setApiKey(e.target.value)}
                                            placeholder={connection ? "Leave blank to keep unchanged" : "Enter API ID (e.g. 12345)"}
                                        />

                                        <Input
                                            label="API Hash"
                                            value={apiSecret}
                                            onChange={(e) => setApiSecret(e.target.value)}
                                            type="password"
                                            placeholder={connection ? "Leave blank to keep unchanged" : "Enter API Hash"}
                                        />

                                        <Input
                                            label="Session File Path"
                                            value={baseUrl}
                                            onChange={(e) => setBaseUrl(e.target.value)}
                                            placeholder="e.g. mysession.session (relative to connections dir) or absolute path"
                                        />
                                    </>
                                ) : (
                                    <>
                                        <Input
                                            label="API Key / Client ID"
                                            value={apiKey}
                                            onChange={(e) => setApiKey(e.target.value)}
                                            type="password"
                                            placeholder={connection ? "Leave blank to keep unchanged" : "Enter API Key"}
                                        />

                                        <Input
                                            label="API Secret / Client Secret"
                                            value={apiSecret}
                                            onChange={(e) => setApiSecret(e.target.value)}
                                            type="password"
                                            placeholder={connection ? "Leave blank to keep unchanged" : "Enter API Secret"}
                                        />

                                        <Input
                                            label="Base URL (Optional)"
                                            value={baseUrl}
                                            onChange={(e) => setBaseUrl(e.target.value)}
                                            placeholder="https://api.example.com"
                                        />
                                    </>
                                )}
                            </div>

                            {error && <ErrorMessage error={error} />}

                            <div className="flex justify-end gap-2 pt-4 border-t border-[#1f2a44]">
                                <Button variant="secondary" onClick={handleClose} type="button">Cancel</Button>
                                <Button type="submit" disabled={loading}>
                                    {loading ? 'Saving...' : connection ? 'Update Connection' : 'Create Connection'}
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            </div >
        </div >
    )
}
