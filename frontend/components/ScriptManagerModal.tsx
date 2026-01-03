'use client'

import { useState, useEffect } from 'react'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { symbolsAPI } from '@/lib/api'
import { getErrorMessage } from '@/lib/error-utils'
import { X } from 'lucide-react'

interface ScriptManagerModalProps {
    isOpen: boolean
    onClose: () => void
}

export function ScriptManagerModal({ isOpen, onClose }: ScriptManagerModalProps) {
    const [scripts, setScripts] = useState<any[]>([])
    const [editingId, setEditingId] = useState<number | null>(null)

    // Editor State
    const [name, setName] = useState('')
    const [description, setDescription] = useState('')
    const [content, setContent] = useState(`# Python Transformation Script
# FULLY FLEXIBLE - Write ANY Python code you need!
# 
# INPUT/OUTPUT CONTRACT (ONLY RESTRICTION):
# - Input: Variable 'df' (pandas DataFrame) is provided by system
# - Output: Variable 'final_df' (pandas DataFrame) must be assigned
#
# YOU CAN:
# - Write any functions, loops, conditionals
# - Use any variable names
# - Include helper methods
# - Perform any transformations
# - Rename/drop/create columns
# - Apply business logic
#
# SECURITY RESTRICTIONS (sandbox-level):
# - os, sys, subprocess, socket, requests, filesystem, network are blocked

import pandas as pd
import numpy as np
from datetime import datetime

# Example: Flexible transformation with helper function
def normalize_symbols(df):
    """Helper function to normalize symbol data"""
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].str.upper().str.strip()
    if "exchange" in df.columns:
        df["exchange"] = df["exchange"].str.upper()
    return df

# Apply transformations
df = normalize_symbols(df)

# Add metadata if needed
df["processed_at"] = datetime.now()

# REQUIRED: Assign final result to final_df
final_df = df`)

    const [loading, setLoading] = useState(false)
    const [error, setError] = useState('')
    const [testing, setTesting] = useState(false)
    const [testResult, setTestResult] = useState<any>(null)
    const [deleting, setDeleting] = useState<number | null>(null)
    const [isVisible, setIsVisible] = useState(false)

    // Animation state - sync with modal open/close
    useEffect(() => {
        if (isOpen) {
            // Trigger animation after mount
            setTimeout(() => setIsVisible(true), 10)
            loadScripts()
        } else {
            setIsVisible(false)
        }
    }, [isOpen])

    const loadScripts = async () => {
        try {
            console.log('Loading scripts list...')
            const data = await symbolsAPI.getScripts()
            console.log('Scripts loaded:', data?.length || 0, 'scripts')
            setScripts(Array.isArray(data) ? data : [])
        } catch (e) { 
            console.error('Failed to load scripts:', e)
            setError(getErrorMessage(e, 'Failed to load scripts'))
        }
    }

    const handleTest = async () => {
        if (!name || !content.trim()) {
            setError('Please provide script name and content before testing')
            return
        }

        setTesting(true)
        setError('')
        setTestResult(null)

        try {
            // If editing, test the existing script
            if (editingId) {
                const result = await symbolsAPI.testScript(editingId)
                setTestResult(result)
            } else {
                // For new scripts, warn user they need to save first
                setError('Please save the script first before testing, or use a saved script')
                setTesting(false)
                return
            }
        } catch (e: any) {
            setError(getErrorMessage(e, 'Test failed'))
            setTestResult({ success: false, error: getErrorMessage(e) })
        } finally {
            setTesting(false)
        }
    }

    const handleDelete = async (e: React.MouseEvent, id: number, scriptName: string) => {
        e.stopPropagation() // Prevent selection
        if (!confirm(`Are you sure you want to delete script '${scriptName}'? This action cannot be undone.`)) {
            return
        }

        setDeleting(id)
        setError('')
        try {
            console.log('Deleting script:', { id, name: scriptName })
            
            // Make the API call
            const result = await symbolsAPI.deleteScript(id)
            console.log('Delete script API result:', result)
            
            // Check if deletion was successful
            // Backend returns: {"message": "...", "id": id, "success": true}
            if (result && result.id === id) {
                console.log('Script deletion confirmed, reloading list...')
                
                // Reload scripts list to reflect deletion
                await loadScripts()
                
                // Verify script was actually removed
                const updatedScripts = await symbolsAPI.getScripts()
                const scriptStillExists = updatedScripts.some((s: any) => s.id === id)
                
                if (scriptStillExists) {
                    console.warn('Script still exists after deletion, may be in use by scheduler')
                    setError('Script may still be in use by a scheduler. Please check and remove scheduler references first.')
                    alert('Script may still be in use by a scheduler. Please check and remove scheduler references first.')
                } else {
                    console.log('Script successfully deleted and removed from list')
                    // If we were editing the deleted script, reset the form
                    if (editingId === id) {
                        resetForm()
                    }
                }
            } else {
                throw new Error(result?.message || 'Delete operation did not return expected result')
            }
        } catch (e: any) {
            console.error('Delete script error:', e)
            console.error('Delete script error details:', {
                error: e,
                response: e?.response?.data,
                status: e?.response?.status,
                message: e?.message,
                stack: e?.stack
            })
            const errorMsg = getErrorMessage(e, 'Delete failed. Please check console for details.')
            setError(errorMsg)
            alert(`Failed to delete script: ${errorMsg}\n\nCheck browser console (F12) for more details.`) // Also show alert for visibility
        } finally {
            setDeleting(null)
        }
    }

    const handleSave = async () => {
        if (!name || !name.trim()) {
            setError('Script name is required')
            return
        }
        if (!content || !content.trim()) {
            setError('Script content is required')
            return
        }
        
        setLoading(true)
        setError('')
        setTestResult(null)
        try {
            const payload = { name: name.trim(), description: description.trim(), content: content.trim() }
            console.log('Saving script:', { editingId, payload: { ...payload, content: `${payload.content.substring(0, 50)}...` } })
            
            let savedScript
            if (editingId) {
                console.log('Updating script:', editingId)
                savedScript = await symbolsAPI.updateScript(editingId, payload)
                console.log('Script updated:', savedScript)
            } else {
                console.log('Creating new script')
                savedScript = await symbolsAPI.createScript(payload)
                console.log('Script created:', savedScript)
            }
            
            // Reload scripts to get updated list
            await loadScripts()
            
            // If update created a new version, select the new version
            if (editingId && savedScript && savedScript.id !== editingId) {
                console.log('New version created, selecting it:', savedScript.id)
                handleEdit(savedScript)
            } else {
                resetForm()
            }
        } catch (e: any) {
            console.error('Save script error:', e)
            const errorMsg = getErrorMessage(e, 'Save failed')
            setError(errorMsg)
            // Don't reset form on error - allow user to fix and retry
        } finally {
            setLoading(false)
        }
    }

    const handleEdit = (script: any) => {
        setEditingId(script.id)
        setName(script.name)
        setDescription(script.description || '')
        setContent(script.content)
    }

    const resetForm = () => {
        setEditingId(null)
        setName('')
        setDescription('')
        setContent(`# Python Transformation Script
# FULLY FLEXIBLE - Write ANY Python code you need!
# 
# INPUT/OUTPUT CONTRACT (ONLY RESTRICTION):
# - Input: Variable 'df' (pandas DataFrame) is provided by system
# - Output: Variable 'final_df' (pandas DataFrame) must be assigned
#
# YOU CAN:
# - Write any functions, loops, conditionals
# - Use any variable names
# - Include helper methods
# - Perform any transformations
# - Rename/drop/create columns
# - Apply business logic
#
# SECURITY RESTRICTIONS (sandbox-level):
# - os, sys, subprocess, socket, requests, filesystem, network are blocked

import pandas as pd
import numpy as np
from datetime import datetime

# Example: Flexible transformation with helper function
def normalize_symbols(df):
    """Helper function to normalize symbol data"""
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].str.upper().str.strip()
    if "exchange" in df.columns:
        df["exchange"] = df["exchange"].str.upper()
    return df

# Apply transformations
df = normalize_symbols(df)

# Add metadata if needed
df["processed_at"] = datetime.now()

# REQUIRED: Assign final result to final_df
final_df = df`)
        setError('')
    }

    if (!isOpen) return null

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div 
                className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-5xl mx-4 p-6 h-[85vh] flex flex-col relative"
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
                <div className="flex items-center justify-between mb-4 flex-shrink-0">
                    <h2 className="text-xl font-sans font-semibold text-[#e5e7eb]">
                        Python Transformation Scripts
                    </h2>
                </div>

                <div className="flex flex-1 gap-6 overflow-hidden">
                    {/* List View */}
                    <div className="w-1/3 border-r border-[#1f2a44] pr-4 overflow-y-auto">
                        <Button className="w-full mb-4" variant="secondary" onClick={resetForm}>+ New Script</Button>
                        <div className="space-y-2">
                            {scripts.map(s => (
                                <div key={s.id}
                                    className={`p-3 rounded cursor-pointer border ${editingId === s.id ? 'border-primary bg-primary/10' : 'border-transparent hover:bg-[#1f2a44]'}`}
                                    onClick={() => handleEdit(s)}
                                >
                                    <h4 className="font-bold text-sm text-text-primary">{s.name}</h4>
                                    <p className="text-xs text-text-secondary truncate">{s.description}</p>
                                    <div className="flex justify-between items-center mt-1">
                                        <span className="text-[10px] text-text-muted">v{s.version} • {new Date(s.created_at).toLocaleDateString()}</span>
                                        <button
                                            onClick={(e) => handleDelete(e, s.id, s.name)}
                                            disabled={deleting === s.id}
                                            className="text-gray-500 hover:text-red-500 p-1 rounded transition-colors"
                                            title="Delete Script"
                                        >
                                            {deleting === s.id ? '...' : '🗑️'}
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Editor View */}
                    <div className="w-2/3 flex flex-col gap-4">
                        <div className="flex gap-2">
                            <div className="flex-1">
                                <label className="text-xs text-text-secondary">Script Name</label>
                                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. NSE Normalizer" />
                            </div>
                            <div className="flex-1">
                                <label className="text-xs text-text-secondary">Description</label>
                                <Input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Optional description" />
                            </div>
                        </div>

                        <div className="flex-1 flex flex-col">
                            <label className="text-xs text-text-secondary mb-1">Python Code (Sandboxed)</label>
                            <textarea
                                className="flex-1 bg-[#0a1020] border border-[#1f2a44] rounded p-4 font-mono text-sm text-gray-300 focus:outline-none focus:border-primary resize-none"
                                value={content}
                                onChange={(e) => setContent(e.target.value)}
                                spellCheck={false}
                            />
                        </div>

                        {error && <p className="text-error text-sm">{error}</p>}

                        {/* Test Results */}
                        {testResult && (
                            <div className={`p-4 rounded border ${testResult.success ? 'bg-success/10 border-success/20' : 'bg-error/10 border-error/20'}`}>
                                <div className="flex items-center justify-between mb-2">
                                    <span className={`text-sm font-semibold ${testResult.success ? 'text-success' : 'text-error'}`}>
                                        {testResult.success ? '✓ Test Passed' : '✗ Test Failed'}
                                    </span>
                                </div>
                                {testResult.success && testResult.before && testResult.after && (
                                    <div className="grid grid-cols-2 gap-4 text-xs">
                                        <div>
                                            <p className="font-semibold mb-1">Before ({testResult.before.row_count} rows):</p>
                                            <div className="bg-[#0a1020] p-2 rounded max-h-32 overflow-auto">
                                                <pre className="text-[10px]">{JSON.stringify(testResult.before.rows, null, 2)}</pre>
                                            </div>
                                        </div>
                                        <div>
                                            <p className="font-semibold mb-1">After ({testResult.after.row_count} rows):</p>
                                            <div className="bg-[#0a1020] p-2 rounded max-h-32 overflow-auto">
                                                <pre className="text-[10px]">{JSON.stringify(testResult.after.rows, null, 2)}</pre>
                                            </div>
                                        </div>
                                    </div>
                                )}
                                {testResult.error && (
                                    <p className="text-error text-xs mt-2">{testResult.error}</p>
                                )}
                            </div>
                        )}

                        <div className="flex justify-between gap-2">
                            <div>
                                {editingId && (
                                    <Button
                                        variant="secondary"
                                        onClick={handleTest}
                                        disabled={testing || !content.trim()}
                                    >
                                        {testing ? 'Testing...' : 'Test Script'}
                                    </Button>
                                )}
                            </div>
                            <div className="flex gap-2">
                                {editingId && <Button variant="ghost" onClick={resetForm}>Cancel</Button>}
                                <Button onClick={handleSave} disabled={!name || loading}>
                                    {loading ? 'Saving...' : (editingId ? 'Update Script' : 'Create Script')}
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
