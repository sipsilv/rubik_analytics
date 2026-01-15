'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X, Save, AlertTriangle } from 'lucide-react'

interface AIEnrichmentConfigModalProps {
    isOpen: boolean
    onClose: () => void
    onUpdate: () => void
}

export function AIEnrichmentConfigModal({ isOpen, onClose, onUpdate }: AIEnrichmentConfigModalProps) {
    const [formData, setFormData] = useState({
        connection_id: '',
        model_name: '',
        prompt_text: '',
        is_active: true // Always active since we removed the toggle
    })

    const [aiConnections, setAiConnections] = useState<any[]>([])
    const [existingConfig, setExistingConfig] = useState<any>(null)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [isVisible, setIsVisible] = useState(false)

    // Animation state
    useEffect(() => {
        if (isOpen) {
            setIsVisible(false)
            requestAnimationFrame(() => {
                requestAnimationFrame(() => setIsVisible(true))
            })
        } else {
            setIsVisible(false)
        }
    }, [isOpen])

    // Load AI connections and existing config
    useEffect(() => {
        if (isOpen) {
            loadData()
        }
    }, [isOpen])

    const loadData = async () => {
        try {
            setLoading(true)

            // Fetch AI connections
            const connections = await adminAPI.getConnections()
            console.log('All connections:', connections)
            const aiConns = connections.filter((c: any) => c.connection_type === 'AI_ML')
            console.log('AI connections:', aiConns)
            setAiConnections(aiConns)

            // Fetch existing config
            const configData = await adminAPI.getAIEnrichmentConfig()
            if (configData.active_config) {
                setExistingConfig(configData.active_config)
                setFormData({
                    connection_id: String(configData.active_config.connection_id),
                    model_name: configData.active_config.model_name,
                    prompt_text: configData.active_config.prompt_text,
                    is_active: configData.active_config.is_active
                })
            } else {
                // Set default prompt if no config exists
                setFormData(prev => ({
                    ...prev,
                    prompt_text: `You are a financial news content extraction engine.

Your task is to analyze the provided TEXT and extract structured NEWS CONTENT.
The system already knows all metadata. You must NOT generate metadata.

RULES:
1. Output ONLY valid JSON
2. No markdown, no explanations
3. Do NOT invent facts, companies, tickers, exchanges, URLs, or dates
4. If information is not explicit, use empty string ""
5. Do NOT generate IDs, timestamps, or source fields
6. Do NOT guess links — links are handled separately
7. Be conservative — leave fields empty if unsure
8. Use neutral, factual language only
9. ALL dates/times mentioned MUST be in IST (Asia/Kolkata)

ALLOWED CATEGORY CODES:
RESULTS, CORPORATE_ACTION, M_AND_A, ORDER_WIN, REGULATORY, POLICY, MANAGEMENT, CAPEX, LITIGATION, DEFAULT, MACRO, MARKET, OTHER

OUTPUT JSON (EXACT):
{
  "category_code": "",
  "sub_type_code": "",
  "company_name": "",
  "ticker": "",
  "exchange": "",
  "country_code": "",
  "headline": "",
  "summary": "",
  "sentiment": "",
  "language_code": ""
}

TEXT TO ANALYZE:
"""
{{COMBINED_TEXT}}
"""`
                }))
            }
        } catch (err: any) {
            setError(getErrorMessage(err, 'Failed to load configuration data'))
        } finally {
            setLoading(false)
        }
    }

    if (!isOpen) return null

    const handleClose = () => {
        setIsVisible(false)
        onClose()
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()

        if (!formData.connection_id) {
            setError("Please select an AI Connection")
            return
        }
        if (!formData.model_name) {
            setError("Please select a Model")
            return
        }
        if (!formData.prompt_text.trim()) {
            setError("Prompt text is required")
            return
        }

        setLoading(true)
        setError('')

        try {
            const payload = {
                connection_id: parseInt(formData.connection_id),
                model_name: formData.model_name,
                prompt_text: formData.prompt_text,
                is_active: formData.is_active
            }

            if (existingConfig) {
                await adminAPI.updateAIEnrichmentConfig(String(existingConfig.config_id), payload)
            } else {
                await adminAPI.createAIEnrichmentConfig(payload)
            }

            onUpdate()
            handleClose()
        } catch (err: any) {
            setError(getErrorMessage(err, 'Failed to save configuration'))
        } finally {
            setLoading(false)
        }
    }

    // Get selected connection details
    const selectedConnection = aiConnections.find(c => String(c.id) === String(formData.connection_id))

    // Determine available models - show all common models for now
    const availableModels = [
        // Ollama models
        { value: 'llama3', label: 'Llama 3' },
        { value: 'llama3:70b', label: 'Llama 3 70B' },
        { value: 'llama2', label: 'Llama 2' },
        { value: 'mistral', label: 'Mistral' },
        { value: 'mixtral', label: 'Mixtral' },
        { value: 'gemma', label: 'Gemma' },
        { value: 'phi3', label: 'Phi-3' },
        { value: 'gpt-oss:120b', label: 'GPT-OSS 120B' },
        // Gemini models
        { value: 'gemini-1.5-flash', label: 'Gemini 1.5 Flash' },
        { value: 'gemini-1.5-pro', label: 'Gemini 1.5 Pro' },
        { value: 'gemini-1.0-pro', label: 'Gemini 1.0 Pro' },
        // Perplexity models
        { value: 'llama-3.1-sonar-small-128k-online', label: 'Sonar Small Online (8B)' },
        { value: 'llama-3.1-sonar-large-128k-online', label: 'Sonar Large Online (70B)' },
        { value: 'llama-3.1-sonar-huge-128k-online', label: 'Sonar Huge Online (405B)' },
        { value: 'llama-3.1-sonar-small-128k-chat', label: 'Sonar Small Chat (8B)' },
        { value: 'llama-3.1-sonar-large-128k-chat', label: 'Sonar Large Chat (70B)' },
        // OpenAI models
        { value: 'gpt-4o', label: 'GPT-4o' },
        { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
        { value: 'gpt-4', label: 'GPT-4' },
        { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
    ]

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
                                AI Enrichment Configuration
                            </h2>
                        </div>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            {/* AI Connection Selection */}
                            <div className="w-full">
                                <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">
                                    AI Connection <span className="text-red-400">*</span>
                                </label>
                                <select
                                    value={formData.connection_id}
                                    onChange={(e) => {
                                        const selectedConn = aiConnections.find(c => String(c.id) === e.target.value)
                                        setFormData(prev => ({
                                            ...prev,
                                            connection_id: e.target.value,
                                            model_name: selectedConn?.details?.model_name || '' // Auto-populate model from connection
                                        }))
                                    }}
                                    className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                    required
                                >
                                    <option value="">Select AI Connection</option>
                                    {aiConnections.map(conn => (
                                        <option key={conn.id} value={conn.id}>
                                            {conn.name} ({conn.provider}) - {conn.details?.model_name || 'No model'}
                                        </option>
                                    ))}
                                </select>
                                <p className="text-xs text-[#9ca3af] mt-1">
                                    Select an existing AI connection. The model will be automatically set from the connection.
                                </p>
                            </div>

                            {/* Model Display (Read-only) */}
                            <div className="w-full">
                                <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">
                                    Model <span className="text-red-400">*</span>
                                </label>
                                <input
                                    type="text"
                                    value={formData.model_name}
                                    className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#0f1623] text-[#6b7280] cursor-not-allowed outline-none"
                                    disabled
                                    placeholder="Select a connection to see the model"
                                />
                                <p className="text-xs text-[#9ca3af] mt-1">
                                    Model is configured in the selected AI connection and cannot be changed here.
                                </p>
                            </div>

                            {/* Prompt Configuration */}
                            <div className="w-full">
                                <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">
                                    AI Prompt Template <span className="text-red-400">*</span>
                                </label>
                                <textarea
                                    value={formData.prompt_text}
                                    onChange={(e) => setFormData(prev => ({ ...prev, prompt_text: e.target.value }))}
                                    className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#0f1623] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none font-mono text-xs leading-relaxed"
                                    rows={10}
                                    placeholder="Enter the AI prompt template here..."
                                    required
                                />
                                <p className="text-xs text-[#9ca3af] mt-1 flex items-center gap-1">
                                    <AlertTriangle className="w-3 h-3 text-yellow-500" />
                                    Prompt is saved exactly as entered. No validation or modification is performed.
                                </p>
                            </div>



                            {error && (
                                <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-lg text-sm flex items-start gap-2">
                                    <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                    {error}
                                </div>
                            )}

                            <div className="flex justify-end gap-2 pt-4 border-t border-[#1f2a44]">
                                <Button variant="secondary" onClick={handleClose} type="button">Cancel</Button>
                                <Button type="submit" disabled={loading}>
                                    {loading ? 'Saving...' : 'Save Configuration'}
                                </Button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    )
}
