'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { adminAPI, telegramAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X } from 'lucide-react'

interface ConnectionModalProps {
    isOpen: boolean
    onClose: () => void
    connection?: any
    onUpdate: () => void
    category?: string
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

export function ConnectionModal({ isOpen, onClose, connection, onUpdate, category }: ConnectionModalProps) {
    // Filter connection types based on category
    const filteredConnectionTypes = CONNECTION_TYPES.filter(t => {
        if (category === 'SOCIAL') {
            return ['TELEGRAM_BOT', 'TELEGRAM_USER'].includes(t.value)
        }
        return true
    })

    const [formData, setFormData] = useState({
        name: '',
        connection_type: category === 'SOCIAL' ? 'TELEGRAM_BOT' : 'MARKET_DATA',
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

    // Telegram OTP State
    const [phone, setPhone] = useState('')
    const [otpCode, setOtpCode] = useState('')
    const [twoFaPassword, setTwoFaPassword] = useState('')
    const [phoneCodeHash, setPhoneCodeHash] = useState('')
    const [isOtpSent, setIsOtpSent] = useState(false)
    const [isVerified, setIsVerified] = useState(false)
    const [sessionString, setSessionString] = useState('')

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
                setSessionString(connection.details?.session_string || '')
                setPhone(connection.details?.phone || '')
                // If session string exists, assume verified
                if (connection.details?.session_string) {
                    setIsVerified(true)
                }
                if (connection.details?.session_string) {
                    setIsVerified(true)
                }
            } else if (connection.connection_type === 'AI_ML') {
                setApiKey('') // Masked
                setBaseUrl(connection.details?.base_url || '')

                // Determine if model is standard or custom
                const savedModel = connection.details?.model_name || ''
                const existingDetails = { ...connection.details }

                // Standard lists (flattened for check)
                const standardModels = [
                    'llama3', 'llama3:70b', 'llama2', 'mistral', 'mixtral', 'gemma', 'phi3', // Ollama
                    'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro', // Gemini
                    'llama-3.1-sonar-small-128k-online', 'llama-3.1-sonar-large-128k-online', 'llama-3.1-sonar-huge-128k-online', // Perplexity
                    'llama-3.1-sonar-small-128k-chat', 'llama-3.1-sonar-large-128k-chat'
                ]

                if (savedModel && !standardModels.includes(savedModel)) {
                    // It's a custom model
                    existingDetails.model_name = 'custom'
                    existingDetails.custom_model_name = savedModel
                } else {
                    existingDetails.model_name = savedModel
                }

                // Update formData details immediately so select renders correctly
                setFormData(prev => ({
                    ...prev,
                    details: existingDetails
                }))
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
            connection_type: category === 'SOCIAL' ? 'TELEGRAM_BOT' : 'MARKET_DATA',
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
        setPhone('')
        setOtpCode('')
        setTwoFaPassword('')
        setPhoneCodeHash('')
        setIsOtpSent(false)
        setIsVerified(false)
        setSessionString('')
        setError('')
    }

    if (!isOpen) return null

    const handleClose = () => {
        setIsVisible(false)
        // Reset OTP state on close
        setTimeout(() => {
            setIsOtpSent(false)
            setIsVerified(false)
            setPhoneCodeHash('')
            setOtpCode('')
        }, 300)
        onClose()
    }

    const handleRequestOtp = async () => {
        if (!apiKey || !apiSecret || !phone) {
            setError('Please enter API ID, API Hash, and Phone Number first')
            return
        }
        setLoading(true)
        setError('')
        try {
            const res = await telegramAPI.requestOtp(apiKey, apiSecret, phone)
            setPhoneCodeHash(res.phone_code_hash)
            setSessionString(res.session_string) // Store temp session string
            setIsOtpSent(true)
            setError('')
        } catch (err: any) {
            setError(getErrorMessage(err, 'Failed to send OTP'))
        } finally {
            setLoading(false)
        }
    }

    const handleVerifyOtp = async () => {
        if (!otpCode || !phoneCodeHash || !sessionString) {
            setError('Missing session data. Please Request OTP again.')
            return
        }
        setLoading(true)
        setError('')
        try {
            const res = await telegramAPI.verifyOtp(apiKey, apiSecret, phone, otpCode, phoneCodeHash, sessionString, twoFaPassword)
            setSessionString(res.session_string)
            setIsVerified(true)
            setError('')
        } catch (err: any) {
            setError(getErrorMessage(err, 'Verification failed'))
        } finally {
            setLoading(false)
        }
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
                if (sessionString) {
                    details.session_string = sessionString
                }
                if (phone && phone.trim()) {
                    details.phone = phone.trim()
                }
                // If we have a session path (legacy) keep it, but session_string is preferred
                if (baseUrl && baseUrl.trim()) {
                    details.session_path = baseUrl.trim()
                }
                if (baseUrl && baseUrl.trim()) {
                    details.session_path = baseUrl.trim()
                }
            } else if (formData.connection_type === 'AI_ML') {
                // AI Connections
                if (apiKey && apiKey.trim()) {
                    details.api_key = apiKey.trim()
                }
                if (baseUrl && baseUrl.trim()) {
                    details.base_url = baseUrl.trim()
                }

                // Handle Model Name Selection
                let model = formData.details?.model_name
                // If user selected 'custom', grab the value from custom_model_name
                if (model === 'custom' && formData.details?.custom_model_name) {
                    model = formData.details.custom_model_name
                }

                if (model) {
                    details.model_name = model
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
                                        {filteredConnectionTypes.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                                    </select>
                                </div>
                            </div>



                            <div className="grid grid-cols-2 gap-4">
                                {formData.connection_type === 'AI_ML' ? (
                                    <div className="w-full">
                                        <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">
                                            Provider <span className="text-red-400">*</span>
                                        </label>
                                        <select
                                            value={formData.provider}
                                            onChange={(e) => {
                                                const newProvider = e.target.value
                                                setFormData(prev => ({ ...prev, provider: newProvider }))
                                            }}
                                            className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                            required
                                        >
                                            <option value="">Select Provider</option>
                                            <option value="Ollama">Ollama</option>
                                            <option value="OpenAI">OpenAI</option>
                                            <option value="Gemini">Google Gemini</option>
                                            <option value="Perplexity">Perplexity</option>
                                            <option value="Anthropic">Anthropic</option>
                                            <option value="Custom">Custom</option>
                                        </select>
                                    </div>
                                ) : (
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
                                )}

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
                                            label="Phone Number"
                                            value={phone}
                                            onChange={(e) => setPhone(e.target.value)}
                                            placeholder="+919876543210"
                                            disabled={isVerified}
                                        />

                                        {!isVerified && !isOtpSent && (
                                            <div className="flex justify-end">
                                                <Button
                                                    type="button"
                                                    variant="secondary"
                                                    onClick={handleRequestOtp}
                                                    disabled={loading || !apiKey || !apiSecret || !phone}
                                                >
                                                    Request OTP
                                                </Button>
                                            </div>
                                        )}

                                        {isOtpSent && !isVerified && (
                                            <div className="space-y-4 p-4 border border-[#1f2a44] rounded bg-[#1f2a44]/30">
                                                <div className="text-sm text-green-400">OTP Sent! Please enter the code from Telegram.</div>
                                                <Input
                                                    label="OTP Code"
                                                    value={otpCode}
                                                    onChange={(e) => setOtpCode(e.target.value)}
                                                    placeholder="12345"
                                                />
                                                <Input
                                                    label="2FA Password (Optional)"
                                                    value={twoFaPassword}
                                                    onChange={(e) => setTwoFaPassword(e.target.value)}
                                                    type="password"
                                                    placeholder="Only if enabled"
                                                />
                                                <div className="flex justify-end">
                                                    <Button
                                                        type="button"
                                                        onClick={handleVerifyOtp}
                                                        disabled={loading || !otpCode}
                                                    >
                                                        Verify & Connect
                                                    </Button>
                                                </div>
                                            </div>
                                        )}

                                        {isVerified && (
                                            <div className="p-2 text-green-400 bg-green-400/10 border border-green-400/20 rounded text-sm text-center">
                                                ✅ Verified & Connected
                                            </div>
                                        )}
                                    </>
                                ) : formData.connection_type === 'AI_ML' ? (
                                    <>
                                        {/* AI/ML Specific Fields */}
                                        <Input
                                            label="Base URL"
                                            value={baseUrl}
                                            onChange={(e) => setBaseUrl(e.target.value)}
                                            placeholder={formData.provider?.toLowerCase().includes('ollama') ? "http://localhost:11434" : "Optional for Cloud Providers"}
                                            required={formData.provider?.toLowerCase().includes('ollama')}
                                        />

                                        <Input
                                            label="API Key"
                                            value={apiKey}
                                            onChange={(e) => setApiKey(e.target.value)}
                                            type="password"
                                            placeholder={connection ? "Leave blank to keep unchanged" : "Enter API Key (Optional for Local)"}
                                        />

                                        <div className="grid grid-cols-1 gap-4">
                                            <div className="w-full">
                                                <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">Model Name</label>
                                                <select
                                                    value={formData.details?.model_name || ''}
                                                    onChange={(e) => {
                                                        const val = e.target.value
                                                        setFormData(prev => ({ ...prev, details: { ...prev.details, model_name: val } }))
                                                    }}
                                                    className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                                    required
                                                >
                                                    <option value="" disabled>Select a Model</option>

                                                    {/* Show models based on selected provider */}
                                                    {formData.provider === 'Ollama' ? (
                                                        <>
                                                            <optgroup label="Llama">
                                                                <option value="llama3">llama3</option>
                                                                <option value="llama3:70b">llama3:70b</option>
                                                                <option value="llama2">llama2</option>
                                                            </optgroup>
                                                            <optgroup label="Mistral / Mixtral">
                                                                <option value="mistral">mistral</option>
                                                                <option value="mixtral">mixtral</option>
                                                            </optgroup>
                                                            <optgroup label="Other">
                                                                <option value="gemma">gemma</option>
                                                                <option value="phi3">phi3</option>
                                                                <option value="gpt-oss:120b">gpt-oss:120b</option>
                                                            </optgroup>
                                                            <option value="custom">Custom (Type manually below)</option>
                                                        </>
                                                    ) : formData.provider === 'Gemini' ? (
                                                        <>
                                                            <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                                                            <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                                                            <option value="gemini-1.0-pro">Gemini 1.0 Pro</option>
                                                            <option value="custom">Custom (Type manually below)</option>
                                                        </>
                                                    ) : formData.provider === 'Perplexity' ? (
                                                        <>
                                                            <optgroup label="Sonar Online">
                                                                <option value="llama-3.1-sonar-small-128k-online">Sonar Small Online (8B)</option>
                                                                <option value="llama-3.1-sonar-large-128k-online">Sonar Large Online (70B)</option>
                                                                <option value="llama-3.1-sonar-huge-128k-online">Sonar Huge Online (405B)</option>
                                                            </optgroup>
                                                            <optgroup label="Sonar Chat">
                                                                <option value="llama-3.1-sonar-small-128k-chat">Sonar Small Chat (8B)</option>
                                                                <option value="llama-3.1-sonar-large-128k-chat">Sonar Large Chat (70B)</option>
                                                            </optgroup>
                                                            <option value="custom">Custom (Type manually below)</option>
                                                        </>
                                                    ) : formData.provider === 'OpenAI' ? (
                                                        <>
                                                            <optgroup label="GPT-4">
                                                                <option value="gpt-4o">GPT-4o</option>
                                                                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                                                                <option value="gpt-4">GPT-4</option>
                                                            </optgroup>
                                                            <optgroup label="GPT-3.5">
                                                                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                                                            </optgroup>
                                                            <option value="custom">Custom (Type manually below)</option>
                                                        </>
                                                    ) : formData.provider === 'Anthropic' ? (
                                                        <>
                                                            <optgroup label="Claude 3">
                                                                <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                                                                <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
                                                                <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
                                                            </optgroup>
                                                            <option value="custom">Custom (Type manually below)</option>
                                                        </>
                                                    ) : (
                                                        <>
                                                            {/* Show all models if Custom or no provider selected */}
                                                            <optgroup label="Ollama Models">
                                                                <option value="llama3">llama3</option>
                                                                <option value="llama3:70b">llama3:70b</option>
                                                                <option value="llama2">llama2</option>
                                                                <option value="mistral">mistral</option>
                                                                <option value="mixtral">mixtral</option>
                                                                <option value="gemma">gemma</option>
                                                                <option value="phi3">phi3</option>
                                                                <option value="gpt-oss:120b">gpt-oss:120b</option>
                                                            </optgroup>
                                                            <optgroup label="Google Gemini">
                                                                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                                                                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                                                                <option value="gemini-1.0-pro">Gemini 1.0 Pro</option>
                                                            </optgroup>
                                                            <optgroup label="Perplexity">
                                                                <option value="llama-3.1-sonar-small-128k-online">Sonar Small Online (8B)</option>
                                                                <option value="llama-3.1-sonar-large-128k-online">Sonar Large Online (70B)</option>
                                                                <option value="llama-3.1-sonar-huge-128k-online">Sonar Huge Online (405B)</option>
                                                                <option value="llama-3.1-sonar-small-128k-chat">Sonar Small Chat (8B)</option>
                                                                <option value="llama-3.1-sonar-large-128k-chat">Sonar Large Chat (70B)</option>
                                                            </optgroup>
                                                            <optgroup label="OpenAI">
                                                                <option value="gpt-4o">GPT-4o</option>
                                                                <option value="gpt-4-turbo">GPT-4 Turbo</option>
                                                                <option value="gpt-4">GPT-4</option>
                                                                <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                                                            </optgroup>
                                                            <optgroup label="Anthropic Claude">
                                                                <option value="claude-3-opus-20240229">Claude 3 Opus</option>
                                                                <option value="claude-3-sonnet-20240229">Claude 3 Sonnet</option>
                                                                <option value="claude-3-haiku-20240307">Claude 3 Haiku</option>
                                                            </optgroup>
                                                            <option value="custom">Custom (Type manually below)</option>
                                                        </>
                                                    )}
                                                </select>
                                            </div>
                                        </div>

                                        {/* Allow custom input if 'custom' is selected */}
                                        {formData.details?.model_name === 'custom' && (
                                            <Input
                                                label="Custom Model Name"
                                                value={formData.details?.custom_model_name || ''}
                                                onChange={(e) => {
                                                    const val = e.target.value
                                                    setFormData(prev => ({ ...prev, details: { ...prev.details, custom_model_name: val } }))
                                                }}
                                                placeholder="Enter model name (e.g. my-finetune:v1)"
                                                required
                                            />
                                        )}

                                        <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-sm text-blue-400 mt-4">
                                            <p className="flex items-start gap-2">
                                                <span className="text-lg">ℹ️</span>
                                                <span>
                                                    <strong>Note:</strong> Advanced configuration (Prompt Template, Timeout, Active Status) can be set using the <strong>Config</strong> button after creating the connection.
                                                </span>
                                            </p>
                                        </div>
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
                            {/* Closing form and main content divs */}
                        </form>
                    </div>
                </div>
            </div>
        </div>
    )
}
