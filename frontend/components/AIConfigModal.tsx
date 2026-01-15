'use client'

import React, { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { adminAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X, Save, Play, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react'
import { SmartTooltip } from '@/components/ui/SmartTooltip'

interface AIConfigModalProps {
    isOpen: boolean
    onClose: () => void
    connection: any
    onUpdate: () => void
}

export function AIConfigModal({ isOpen, onClose, connection, onUpdate }: AIConfigModalProps) {
    const [formData, setFormData] = useState({
        model_name: '',
        timeout_seconds: 30,
        ai_prompt_template: '',
        is_active: false
    })

    // Custom model input state
    const [isCustomModel, setIsCustomModel] = useState(false)
    const [customModelName, setCustomModelName] = useState('')

    const [loading, setLoading] = useState(false)
    const [testing, setTesting] = useState(false)
    const [error, setError] = useState('')
    const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null)

    const [isVisible, setIsVisible] = useState(false)
    const [availableModels, setAvailableModels] = useState<string[]>([])

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

    useEffect(() => {
        if (connection && connection.details) {
            const details = connection.details
            setFormData({
                model_name: details.model_name || '',
                timeout_seconds: details.timeout_seconds || 30,
                ai_prompt_template: details.ai_prompt_template || `You are a financial news content extraction engine.

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
"""`,
                is_active: details.is_active || false
            })

            // Check if model is custom
            const standardModels = [
                'llama3', 'llama3:70b', 'llama2', 'mistral', 'mixtral', 'gemma', 'phi3', 'gpt-oss:120b',
                'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-1.0-pro',
                'llama-3.1-sonar-small-128k-online', 'llama-3.1-sonar-large-128k-online', 'llama-3.1-sonar-huge-128k-online',
                'llama-3.1-sonar-small-128k-chat', 'llama-3.1-sonar-large-128k-chat'
            ]

            if (details.model_name && !standardModels.includes(details.model_name)) {
                setIsCustomModel(true)
                setCustomModelName(details.model_name)
            } else {
                setIsCustomModel(false)
                setCustomModelName('')
            }
        }
        setError('')
        setTestResult(null)
    }, [connection, isOpen])

    if (!isOpen || !connection) return null

    const handleClose = () => {
        setIsVisible(false)
        onClose()
    }

    const handleTest = async () => {
        setTesting(true)
        setTestResult(null)
        try {
            const res = await adminAPI.testConnection(connection.id)
            setTestResult(res)
            if (res.success) {
                onUpdate() // Refresh status in list
            }
        } catch (err: any) {
            setTestResult({
                success: false,
                message: getErrorMessage(err, "Test failed")
            })
        } finally {
            setTesting(false)
        }
    }

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault()
        if (!formData.ai_prompt_template.trim()) {
            setError("AI Prompt Template is required.")
            return
        }

        setLoading(true)
        setError('')

        try {
            const payload = {
                details: {
                    ...connection.details, // Keep existing details (like base_url, api_key)
                    model_name: isCustomModel ? customModelName : formData.model_name,
                    timeout_seconds: formData.timeout_seconds,
                    ai_prompt_template: formData.ai_prompt_template,
                    is_active: formData.is_active
                }
            }

            await adminAPI.updateConnection(String(connection.id), payload)
            onUpdate()
            handleClose()
        } catch (err: any) {
            setError(getErrorMessage(err, 'Failed to save configuration'))
        } finally {
            setLoading(false)
        }
    }

    const isOllama = connection.provider?.toLowerCase().includes('ollama')
    const isGemini = connection.provider?.toLowerCase().includes('gemini')
    const isPerplexity = connection.provider?.toLowerCase().includes('perplexity')

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
                if (e.target === e.currentTarget) handleClose()
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
                    {/* Close Button - Positioned outside modal at top-right */}
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
                            <div>
                                <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
                                    AI Configuration
                                </h2>
                                <p className="text-xs text-[#9ca3af] mt-0.5">
                                    Manage model settings and prompt for {connection.name}
                                </p>
                            </div>
                        </div>
                        {/* Read-only Section */}
                        <div className="grid grid-cols-2 gap-4 bg-[#1f2a44]/30 p-4 rounded-lg border border-[#1f2a44]/50">
                            <div>
                                <label className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-1 block">Connection Name</label>
                                <div className="text-sm font-medium text-[#e5e7eb] font-mono">{connection.name}</div>
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-1 block">Provider Type</label>
                                <div className="text-sm font-medium text-[#e5e7eb] font-mono">{connection.provider}</div>
                            </div>
                            <div className="col-span-2">
                                <label className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider mb-1 block">Base URL</label>
                                <div className="text-sm font-medium text-[#e5e7eb] font-mono truncate" title={connection.details?.base_url}>
                                    {connection.details?.base_url || 'N/A'}
                                </div>
                            </div>
                        </div>

                        <form id="ai-config-form" onSubmit={handleSubmit} className="space-y-6">
                            {/* Model Selection */}
                            <div className="grid grid-cols-2 gap-4">
                                <div className="w-full">
                                    <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">Model</label>
                                    <select
                                        value={isCustomModel ? 'custom' : formData.model_name}
                                        onChange={(e) => {
                                            const val = e.target.value
                                            if (val === 'custom') {
                                                setIsCustomModel(true)
                                                // Don't clear customModelName if switching back and forth
                                            } else {
                                                setIsCustomModel(false)
                                                setFormData(prev => ({ ...prev, model_name: val }))
                                            }
                                        }}
                                        className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                    >
                                        <option value="" disabled>Select a Model</option>
                                        {isOllama && (
                                            <>
                                                {availableModels.length > 0 ? (
                                                    <optgroup label="Ollama (Fetched)">
                                                        {availableModels.map(m => (
                                                            <option key={m} value={m}>{m}</option>
                                                        ))}
                                                    </optgroup>
                                                ) : (
                                                    <>
                                                        <optgroup label="Ollama Models">
                                                            <option value="llama3">Llama 3</option>
                                                            <option value="llama3:70b">Llama 3 70B</option>
                                                            <option value="llama2">Llama 2</option>
                                                            <option value="mistral">Mistral</option>
                                                            <option value="mixtral">Mixtral</option>
                                                            <option value="gemma">Gemma</option>
                                                            <option value="phi3">Phi-3</option>
                                                            <option value="gpt-oss:120b">GPT-OSS 120B</option>
                                                        </optgroup>
                                                    </>
                                                )}
                                            </>
                                        )}
                                        {isGemini && (
                                            <>
                                                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                                                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                                                <option value="gemini-1.0-pro">Gemini 1.0 Pro</option>
                                            </>
                                        )}
                                        {isPerplexity && (
                                            <>
                                                <optgroup label="Llama 3.1">
                                                    <option value="llama-3.1-sonar-small-128k-online">Sonar Small Online (8B)</option>
                                                    <option value="llama-3.1-sonar-large-128k-online">Sonar Large Online (70B)</option>
                                                    <option value="llama-3.1-sonar-huge-128k-online">Sonar Huge Online (405B)</option>
                                                </optgroup>
                                                <optgroup label="Llama 3.1 Chat">
                                                    <option value="llama-3.1-sonar-small-128k-chat">Sonar Small Chat (8B)</option>
                                                    <option value="llama-3.1-sonar-large-128k-chat">Sonar Large Chat (70B)</option>
                                                </optgroup>
                                            </>
                                        )}
                                        <option value="custom">Custom (Type manually)</option>
                                    </select>
                                </div>

                                <div className="w-full">
                                    <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">Timeout (seconds)</label>
                                    <input
                                        type="number"
                                        value={formData.timeout_seconds}
                                        onChange={(e) => setFormData(prev => ({ ...prev, timeout_seconds: parseInt(e.target.value) || 30 }))}
                                        className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none"
                                        min="1"
                                    />
                                </div>
                            </div>

                            {/* Custom Model Name Input */}
                            {isCustomModel && (
                                <div className="animate-in fade-in slide-in-from-top-2 duration-200">
                                    <Input
                                        label="Custom Model Name"
                                        value={customModelName}
                                        onChange={(e) => setCustomModelName(e.target.value)}
                                        placeholder="Enter model name (e.g. my-finetuned-v1)"
                                        required
                                    />
                                </div>
                            )}

                            {/* Is Active Toggle */}
                            <div className="border border-[#1f2a44] p-4 rounded-lg bg-[#1f2a44]/20 hover:bg-[#1f2a44]/30 transition-colors">
                                <label className="flex items-center justify-between cursor-pointer">
                                    <div>
                                        <span className="text-sm font-sans font-medium text-[#e5e7eb] flex items-center gap-2">
                                            Set as Active AI
                                            {formData.is_active && <span className="text-[10px] bg-blue-500/20 text-blue-400 px-1.5 py-0.5 rounded border border-blue-500/30">CURRENTLY ACTIVE</span>}
                                        </span>
                                        <p className="text-xs text-[#9ca3af] mt-1">
                                            Only one AI connection can be active. Enabling this disables others.
                                        </p>
                                    </div>
                                    <div className="relative">
                                        <input
                                            type="checkbox"
                                            className="sr-only"
                                            checked={formData.is_active}
                                            onChange={(e) => setFormData(prev => ({ ...prev, is_active: e.target.checked }))}
                                        />
                                        <div className={`w-11 h-6 rounded-full shadow-inner transition-colors duration-200 ease-in-out ${formData.is_active ? 'bg-blue-600' : 'bg-gray-700'}`}></div>
                                        <div className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full shadow transition-transform duration-200 ease-in-out ${formData.is_active ? 'translate-x-5' : 'translate-x-0'}`}></div>
                                    </div>
                                </label>
                            </div>

                            {/* Prompt Template */}
                            <div className="w-full">
                                <label className="block text-sm font-sans font-medium text-[#9ca3af] mb-1.5">
                                    AI Prompt Template <span className="text-red-400">*</span>
                                </label>
                                <textarea
                                    value={formData.ai_prompt_template}
                                    onChange={(e) => setFormData(prev => ({ ...prev, ai_prompt_template: e.target.value }))}
                                    className="w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#0f1623] text-[#e5e7eb] focus:ring-2 focus:ring-primary/30 outline-none font-mono text-xs leading-relaxed"
                                    rows={10}
                                    placeholder="Enter the system prompt here. Use {{COMBINED_TEXT}} as the placeholder."
                                    required
                                />
                                <p className="text-xs text-[#9ca3af] mt-1 flex items-center gap-1">
                                    <AlertTriangle className="w-3 h-3 text-yellow-500" />
                                    Must be a valid prompt template containing instructions for the AI. Use <code>{`{{COMBINED_TEXT}}`}</code> to insert news content.
                                </p>
                            </div>
                        </form>

                        {/* Error Message */}
                        {error && (
                            <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-lg text-sm flex items-start gap-2">
                                <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                                {error}
                            </div>
                        )}

                        {/* Test Result */}
                        {testResult && (
                            <div className={`px-4 py-3 rounded-lg text-sm flex items-start gap-2 border ${testResult.success ? 'bg-green-500/10 border-green-500/20 text-green-400' : 'bg-red-500/10 border-red-500/20 text-red-400'}`}>
                                {testResult.success ? <CheckCircle className="w-4 h-4 mt-0.5 flex-shrink-0" /> : <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0" />}
                                <div>
                                    <span className="font-bold block mb-0.5">{testResult.success ? 'Connection Successful' : 'Connection Failed'}</span>
                                    {testResult.message}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="px-6 py-4 bg-[#1a2332]/50 border-t border-[#1f2a44] flex items-center justify-between">
                        <Button
                            type="button"
                            variant="secondary"
                            onClick={handleTest}
                            disabled={testing || loading}
                            className="gap-2"
                        >
                            {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                            Test Connection
                        </Button>

                        <div className="flex items-center gap-3">
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={handleClose}
                                disabled={loading}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                form="ai-config-form"
                                disabled={loading}
                                className="bg-blue-600 hover:bg-blue-700 text-white gap-2"
                            >
                                {loading ? 'Saving...' : (
                                    <>
                                        <Save className="w-4 h-4" />
                                        Save Changes
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
