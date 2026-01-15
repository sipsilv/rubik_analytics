'use client'

import { useState, useEffect, useRef } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { adminAPI } from '@/lib/api'
import { ConnectionModal } from '@/components/ConnectionModal'
import { ViewConnectionModal } from '@/components/ViewConnectionModal'
import { TrueDataConnectionCard } from '@/components/TrueDataConnectionCard'
import { Plus, Database, TrendingUp, Newspaper, MessageSquare, Brain, Settings, ArrowRight, BarChart3 } from 'lucide-react'
import { useRouter } from 'next/navigation'

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const router = useRouter()

  // Modals use separate state
  const [selectedConn, setSelectedConn] = useState<any>(null)
  const [isAddOpen, setIsAddOpen] = useState(false)
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isViewOpen, setIsViewOpen] = useState(false)
  const hasLoadedRef = useRef(false)

  // Find TrueData connection (normalize spaces and handle variations)
  const trueDataConnection = connections.find(c => {
    if (!c.provider) return false
    const provider = c.provider.toUpperCase().replace(/\s+/g, '').replace(/[_-]/g, '')
    return provider === 'TRUEDATA' || provider.includes('TRUEDATA')
  })

  // Debug: Log connections to console
  useEffect(() => {
    if (connections.length > 0) {
      console.log('[Connections] All connections:', connections.map(c => ({
        id: c.id,
        name: c.name,
        provider: c.provider,
        type: c.connection_type,
        status: c.status
      })))
      console.log('[Connections] TrueData connection found:', trueDataConnection)
    }
  }, [connections, trueDataConnection])

  useEffect(() => {
    // Prevent double call in React Strict Mode
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true

    loadConnections()
  }, [])

  const loadConnections = async () => {
    try {
      setLoading(true)
      const data = await adminAPI.getConnections()
      console.log('[Connections Page] Loaded connections from API:', data)
      console.log('[Connections Page] Connection count:', data?.length || 0)
      setConnections(data || [])
    } catch (e) {
      console.error('[Connections Page] Error loading connections:', e)
    } finally {
      setLoading(false)
    }
  }

  // Stats
  const stats = {
    total: connections.length,
    active: connections.filter(c => c.status === 'CONNECTED').length,
    inactive: connections.filter(c => c.status === 'DISCONNECTED').length,
    failed: connections.filter(c => c.status === 'ERROR').length,
  }

  // Category stats
  const categoryStats = {
    INTERNAL: {
      total: connections.filter(c => c.connection_type === 'INTERNAL').length,
      connected: connections.filter(c => c.connection_type === 'INTERNAL' && c.status === 'CONNECTED').length,
      label: 'Database Connections',
      description: 'Internal database connections (SQLite, DuckDB, PostgreSQL)',
      icon: Database,
      color: 'primary'
    },
    BROKER: {
      total: connections.filter(c => c.connection_type === 'BROKER').length,
      connected: connections.filter(c => c.connection_type === 'BROKER' && c.status === 'CONNECTED').length,
      label: 'Broker APIs',
      description: 'Trading and broker API integrations',
      icon: TrendingUp,
      color: 'success'
    },
    NEWS: {
      total: connections.filter(c => c.connection_type === 'NEWS').length,
      connected: connections.filter(c => c.connection_type === 'NEWS' && c.status === 'CONNECTED').length,
      label: 'News Channels',
      description: 'News feeds and event data sources',
      icon: Newspaper,
      color: 'info'
    },
    SOCIAL: {
      total: connections.filter(c => ['SOCIAL', 'TELEGRAM_BOT', 'TELEGRAM_USER'].includes(c.connection_type)).length,
      connected: connections.filter(c => ['SOCIAL', 'TELEGRAM_BOT', 'TELEGRAM_USER'].includes(c.connection_type) && c.status === 'CONNECTED').length,
      label: 'Telegram',
      description: 'Telegram, social media, and messaging integrations',
      icon: MessageSquare,
      color: 'warning'
    },
    MARKET_DATA: {
      total: connections.filter(c => c.connection_type === 'MARKET_DATA').length,
      connected: connections.filter(c => c.connection_type === 'MARKET_DATA' && c.status === 'CONNECTED').length,
      label: 'Market Data',
      description: 'Real-time market data providers',
      icon: BarChart3,
      color: 'primary'
    },
    AI_ML: {
      total: connections.filter(c => c.connection_type === 'AI_ML').length,
      connected: connections.filter(c => c.connection_type === 'AI_ML' && c.status === 'CONNECTED').length,
      label: 'AI / ML Models',
      description: 'AI and machine learning model endpoints',
      icon: Brain,
      color: 'success'
    }
  }

  // TrueData category (special - always show, even if no connection exists)
  // Always show the card so user can create a connection
  const trueDataCategory = {
    key: 'TRUEDATA' as const,
    total: trueDataConnection ? 1 : 0,
    connected: trueDataConnection && trueDataConnection.status === 'CONNECTED' ? 1 : 0,
    label: 'TrueData',
    description: trueDataConnection
      ? 'Master token provider for multiple app connections'
      : 'Create TrueData connection to enable token-based authentication',
    icon: BarChart3,
    color: 'primary'
  }

  const connectionCategories = [
    { key: 'INTERNAL' as const, ...categoryStats.INTERNAL },
    { key: 'BROKER' as const, ...categoryStats.BROKER },
    { key: 'NEWS' as const, ...categoryStats.NEWS },
    { key: 'SOCIAL' as const, ...categoryStats.SOCIAL },
    { key: 'MARKET_DATA' as const, ...categoryStats.MARKET_DATA },
    trueDataCategory,
  ]


  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
          Connections
        </h1>
        <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
          Manage external integrations and API gateways
        </p>
      </div>

      {/* Connection Categories - Similar to Reference Data */}
      <div className="flex flex-wrap justify-center gap-6 items-stretch">
        {connectionCategories.map((category) => {
          const IconComponent = category.icon

          // Special handling for TrueData - show the detailed card
          if (category.key === 'TRUEDATA' && trueDataConnection) {
            return (
              <TrueDataConnectionCard
                key={category.key}
                connection={trueDataConnection}
                onConfigure={() => {
                  setSelectedConn(trueDataConnection)
                  setIsEditOpen(true)
                }}
                onViewDetails={() => router.push('/admin/connections/truedata')}
                onUpdate={loadConnections}
              />
            )
          }

          return (
            <Card key={category.key} className="hover:shadow-lg transition-all duration-200 flex flex-col w-full max-w-sm">
              <div className="p-6 flex flex-col h-full">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                  <div className="flex items-center gap-3">
                    <div className="p-3 rounded-xl">
                      <IconComponent className="w-6 h-6 text-text-primary dark:text-[#e5e7eb]" />
                    </div>
                    <div>
                      <h3 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
                        {category.label}
                      </h3>
                      <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-0.5">
                        {category.description}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Stats Grid */}
                {loading ? (
                  <div className="py-8 text-center text-text-secondary">Loading...</div>
                ) : (
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    {/* Total */}
                    <div className="text-center p-4 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border">
                      <div className="text-3xl font-bold font-sans text-text-primary dark:text-[#e5e7eb] mb-1">
                        {category.total}
                      </div>
                      <div className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] uppercase tracking-wider">
                        Total
                      </div>
                    </div>

                    {/* Connected */}
                    <div className={`text-center p-4 rounded-lg border ${category.connected > 0
                      ? 'bg-success/10 dark:bg-[#10b981]/10 border-success/20'
                      : 'bg-text-secondary/10 dark:bg-[#6b7280]/10 border-text-secondary/20'
                      }`}>
                      <div className={`text-3xl font-bold font-sans mb-1 ${category.connected > 0 ? 'text-success' : 'text-text-secondary dark:text-[#9ca3af]'
                        }`}>
                        {category.connected}
                      </div>
                      <div className={`text-xs font-sans uppercase tracking-wider ${category.connected > 0 ? 'text-success' : 'text-text-secondary dark:text-[#9ca3af]'
                        }`}>
                        Connected
                      </div>
                    </div>
                  </div>
                )}

                <p className="text-sm font-sans text-text-secondary dark:text-[#9ca3af] mb-4">
                  {category.key === 'INTERNAL' && 'Manage database connections for authentication, analytics, and reference data.'}
                  {category.key === 'BROKER' && 'Configure trading platforms and broker API integrations for automated trading.'}
                  {category.key === 'NEWS' && 'Connect to news feeds and event data sources for market analysis.'}
                  {category.key === 'SOCIAL' && 'Integrate with messaging platforms and social media for sentiment analysis.'}
                  {category.key === 'TRUEDATA' && 'Configure TrueData as a central token provider. Tokens are generated and refreshed automatically.'}
                </p>
                {category.key === 'TRUEDATA' ? (
                  !trueDataConnection && (
                    <Button
                      variant="primary"
                      size="sm"
                      className="w-full"
                      onClick={() => {
                        setIsAddOpen(true)
                        // Pre-fill TrueData in the modal
                        setTimeout(() => {
                          const event = new CustomEvent('prefill-truedata')
                          window.dispatchEvent(event)
                        }, 100)
                      }}
                    >
                      <Plus className="w-4 h-4" />
                      Create TrueData Connection
                    </Button>
                  )
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    className="w-full"
                    onClick={() => {
                      // Navigate to list view
                      router.push(`/admin/connections/list?category=${category.key}`)
                    }}
                  >
                    <Settings className="w-4 h-4" />
                    View {category.label}
                    <ArrowRight className="w-4 h-4" />
                  </Button>
                )}
              </div>
            </Card>
          )
        })}
      </div>


      <ConnectionModal
        isOpen={isAddOpen}
        onClose={() => setIsAddOpen(false)}
        onUpdate={loadConnections}
      />

      <ConnectionModal
        isOpen={isEditOpen}
        onClose={() => { setIsEditOpen(false); setSelectedConn(null) }}
        connection={selectedConn}
        onUpdate={loadConnections}
      />

      <ViewConnectionModal
        isOpen={isViewOpen}
        onClose={() => { setIsViewOpen(false); setSelectedConn(null) }}
        connection={selectedConn}
      />
    </div>
  )
}
