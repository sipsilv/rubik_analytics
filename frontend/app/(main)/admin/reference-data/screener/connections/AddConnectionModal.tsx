'use client'

import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { screenerAPI } from '@/lib/api'
import { X } from 'lucide-react'

type ConnectionType = 'WEBSITE_SCRAPING' | 'API_CONNECTION'
type AuthType = 'NONE' | 'KEY' | 'TOKEN'

interface AddConnectionModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export function AddConnectionModal({ isOpen, onClose, onSuccess }: AddConnectionModalProps) {
  const [mounted, setMounted] = useState(false)
  const [isVisible, setIsVisible] = useState(false)
  const [connectionType, setConnectionType] = useState<ConnectionType>('WEBSITE_SCRAPING')
  const [connectionName, setConnectionName] = useState('')
  const [baseUrl, setBaseUrl] = useState('https://www.screener.in/company/{symbol}/consolidated/')
  const [apiProviderName, setApiProviderName] = useState('')
  const [authType, setAuthType] = useState<AuthType>('NONE')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    setMounted(true)
    if (isOpen) {
      setTimeout(() => setIsVisible(true), 10)
    }
    return () => {
      setMounted(false)
      setIsVisible(false)
    }
  }, [isOpen])

  // Prevent body scroll
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isOpen])

  // Handle ESC key
  useEffect(() => {
    if (!isOpen) return
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen, onClose])

  if (!isOpen || !mounted) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!connectionName.trim()) {
      alert('Connection name is required')
      return
    }

    if (connectionType === 'WEBSITE_SCRAPING' && !baseUrl.trim()) {
      alert('Base URL is required for Website Scraping connections')
      return
    }

    setSaving(true)
    try {
      const connectionData: any = {
        connection_name: connectionName.trim(),
        connection_type: connectionType
      }

      if (connectionType === 'WEBSITE_SCRAPING') {
        const url = baseUrl.trim() || 'https://www.screener.in/company/{symbol}/consolidated/'
        if (!url || url.length === 0) {
          alert('Base URL cannot be empty')
          setSaving(false)
          return
        }
        connectionData.base_url = url
      } else if (connectionType === 'API_CONNECTION') {
        connectionData.api_provider_name = apiProviderName.trim() || ''
        connectionData.auth_type = authType || 'NONE'
      }

      await screenerAPI.createConnection(connectionData)
      onSuccess()
      onClose()
      
      // Reset form
      setConnectionName('')
      setBaseUrl('https://www.screener.in/company/{symbol}/consolidated/')
      setApiProviderName('')
      setAuthType('NONE')
      setConnectionType('WEBSITE_SCRAPING')
    } catch (e: any) {
      console.error('Failed to create connection:', e)
      const errorMessage = e?.response?.data?.detail || e?.message || 'Failed to create connection. Please try again.'
      alert(errorMessage)
    } finally {
      setSaving(false)
    }
  }

  const modalContent = (
    <div
      className="fixed inset-0 flex items-center justify-center modal-backdrop"
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
        MozBackdropFilter: 'blur(12px)',
        zIndex: 10000,
      }}
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
          className="bg-[#121b2f] border border-[#1f2a44] rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[90vh] relative secondary-modal-content"
          style={{ 
            zIndex: 10001,
            minWidth: '400px',
            width: 'auto',
            maxWidth: 'min(100%, calc(100vw - 2rem))',
            animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
          }}
        >
          {/* Close Button */}
          <button
            onClick={onClose}
            className="absolute top-0 -right-12 w-8 h-8 p-0 bg-transparent hover:bg-red-600 rounded text-red-600 hover:text-white transition-colors z-[10002] flex items-center justify-center secondary-modal-close-button"
            title="Close"
            aria-label="Close"
            style={{
              animation: isVisible ? 'modalFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
            }}
          >
            <X className="w-5 h-5" />
          </button>
          
          <div className="p-6 max-h-[90vh] overflow-y-auto">
            <h2 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-4">
              Add Connection
            </h2>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Connection Type */}
            <div>
              <label className="block text-sm font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
                Connection Type
              </label>
              <select
                value={connectionType}
                onChange={(e) => setConnectionType(e.target.value as ConnectionType)}
                className="w-full px-3 py-2 text-sm border border-border dark:border-[#1f2a44] rounded-lg bg-background dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="WEBSITE_SCRAPING">Website Scraping</option>
                <option value="API_CONNECTION">API Connection</option>
              </select>
            </div>

            {/* Connection Name */}
            <div>
              <label className="block text-sm font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
                Connection Name *
              </label>
              <Input
                type="text"
                value={connectionName}
                onChange={(e) => setConnectionName(e.target.value)}
                placeholder="Enter connection name"
                required
                className="w-full"
              />
            </div>

            {/* Connection Type Specific Configuration */}
            {connectionType === 'WEBSITE_SCRAPING' && (
              <div className="space-y-4 pt-2 border-t border-border dark:border-[#1f2a44]">
                <div>
                  <h3 className="text-sm font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-3">
                    Website Scraping Configuration
                  </h3>
                </div>
                <div>
                  <label className="block text-sm font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
                    Base URL *
                  </label>
                  <Input
                    type="text"
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://www.screener.in/company/{symbol}/consolidated/"
                    required
                    className="w-full"
                  />
                  <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-1">
                    Use {'{symbol}'} as placeholder for the symbol name
                  </p>
                </div>
              </div>
            )}

            {connectionType === 'API_CONNECTION' && (
              <div className="space-y-4 pt-2 border-t border-border dark:border-[#1f2a44]">
                <div>
                  <h3 className="text-sm font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-3">
                    API Connection Configuration
                  </h3>
                </div>
                <div>
                  <label className="block text-sm font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
                    API Provider Name
                  </label>
                  <Input
                    type="text"
                    value={apiProviderName}
                    onChange={(e) => setApiProviderName(e.target.value)}
                    placeholder="Enter API provider name"
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
                    Authentication Type
                  </label>
                  <select
                    value={authType}
                    onChange={(e) => setAuthType(e.target.value as AuthType)}
                    className="w-full px-3 py-2 text-sm border border-border dark:border-[#1f2a44] rounded-lg bg-background dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] focus:outline-none focus:ring-2 focus:ring-primary/30"
                  >
                    <option value="NONE">None</option>
                    <option value="KEY">Key</option>
                    <option value="TOKEN">Token</option>
                  </select>
                </div>
              </div>
            )}

            <div className="flex gap-2 justify-end pt-4">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onClose}
                disabled={saving}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={saving}
              >
                {saving ? 'Creating...' : 'Create Connection'}
              </Button>
            </div>
          </form>
          </div>
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}

