'use client'

import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import Link from 'next/link'
import { Hash, Activity, Settings, ArrowRight, BarChart3 } from 'lucide-react'
import { symbolsAPI, screenerAPI } from '@/lib/api'

export default function ReferenceDataPage() {
  const router = useRouter()
  const [symbolsStats, setSymbolsStats] = useState<any>({
    total: 0,
    expiring_today: 0,
    skipped_symbols: 0,
    last_updated: null,
    last_status: null,
    last_run_datetime: null,
    last_upload_type: null,
    last_triggered_by: null,
    last_updated_rows: 0,
    last_inserted_rows: 0
  })
  const [loading, setLoading] = useState(true)
  const [screenerStats, setScreenerStats] = useState<any>({
    total_records: 0,
    unique_symbols: 0,
    last_status: null,
    last_run_datetime: null,
    last_triggered_by: null,
    last_total_symbols: 0,
    last_symbols_processed: 0,
    last_symbols_succeeded: 0,
    last_symbols_failed: 0,
    last_records_inserted: 0
  })
  const [screenerLoading, setScreenerLoading] = useState(true)
  const hasLoadedRef = useRef(false)

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never'
    try {
      const date = new Date(dateString)
      const day = date.getDate()
      const month = date.toLocaleString('default', { month: 'short' })
      const year = date.getFullYear()
      const hours = date.getHours().toString().padStart(2, '0')
      const minutes = date.getMinutes().toString().padStart(2, '0')
      return `${day} ${month} ${year}, ${hours}:${minutes}`
    } catch (e) {
      return dateString
    }
  }

  useEffect(() => {
    // Prevent double call in React Strict Mode
    if (hasLoadedRef.current) return
    hasLoadedRef.current = true

    const loadAllStats = async () => {
      try {
        // Load both stats in parallel but only once
        const [symbolsStatsData, screenerStatsData] = await Promise.all([
          symbolsAPI.getStats(),
          screenerAPI.getStats()
        ])
        setSymbolsStats(symbolsStatsData)
        setScreenerStats(screenerStatsData)
      } catch (e) {
        console.error('Failed to load stats:', e)
      } finally {
        setLoading(false)
        setScreenerLoading(false)
      }
    }
    loadAllStats()
  }, [])


  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
          Reference Data
        </h1>
        <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
          Manage symbols, indicators, and other reference data for the analytics platform
        </p>
      </div>

      <div className="flex flex-wrap justify-center gap-6 items-stretch">
        <Card className="hover:shadow-lg hover:border-primary/30 transition-all duration-200 border-2 w-full max-w-sm">
          <div className="p-6 flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <div className="p-3 bg-primary/10 dark:bg-[#3b82f6]/20 rounded-xl">
                  <Hash className="w-6 h-6 text-primary dark:text-[#3b82f6]" />
                </div>
                <div>
                  <h3 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
                    Symbols
                  </h3>
                  <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-0.5">
                    Stock symbols and reference data
                  </p>
                </div>
              </div>
            </div>

            {/* Stats Grid - 4 Cards */}
            {loading ? (
              <div className="py-8 text-center text-text-secondary">Loading...</div>
            ) : (
              <div className="grid grid-cols-2 gap-4 mb-6">
                {/* Total Symbols - CLICKABLE */}
                <button
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    router.push('/admin/symbols')
                  }}
                  className="text-center p-4 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border hover:border-primary/50 hover:bg-primary/5 transition-all cursor-pointer w-full"
                >
                  <div className="text-3xl font-bold font-sans text-text-primary dark:text-[#e5e7eb] mb-1">
                    {symbolsStats.total?.toLocaleString() || 0}
                  </div>
                  <div className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] uppercase tracking-wider">
                    Total Symbols
                  </div>
                </button>

                {/* Last Run - NON-CLICKABLE with Status inside */}
                <div className={`text-center p-4 rounded-lg border ${symbolsStats.last_status === 'Completed' || symbolsStats.last_status === 'Completed (Partial)'
                  ? 'bg-success/10 dark:bg-[#10b981]/10 border-success/20'
                  : symbolsStats.last_status === 'Failed' || symbolsStats.last_status === 'Crashed'
                    ? 'bg-danger/10 dark:bg-[#ef4444]/10 border-danger/20'
                    : symbolsStats.last_status === 'Running' || symbolsStats.last_status === 'Queued'
                      ? 'bg-primary/10 dark:bg-[#3b82f6]/10 border-primary/20'
                      : symbolsStats.last_status === 'Cancelled'
                        ? 'bg-warning/10 dark:bg-[#f59e0b]/10 border-warning/20'
                        : 'bg-text-secondary/10 dark:bg-[#6b7280]/10 border-text-secondary/20'
                  }`}>
                  {/* Status at the top */}
                  <div className={`text-sm font-bold font-sans mb-2 ${symbolsStats.last_status === 'Completed' || symbolsStats.last_status === 'Completed (Partial)'
                    ? 'text-success'
                    : symbolsStats.last_status === 'Failed' || symbolsStats.last_status === 'Crashed'
                      ? 'text-danger'
                      : symbolsStats.last_status === 'Running' || symbolsStats.last_status === 'Queued'
                        ? 'text-primary'
                        : symbolsStats.last_status === 'Cancelled'
                          ? 'text-warning'
                          : 'text-text-secondary dark:text-[#9ca3af]'
                    }`}>
                    {symbolsStats.last_status || symbolsStats.last_updated?.status || 'N/A'}
                  </div>
                  {/* Date below status */}
                  <div className={`text-sm font-bold font-sans mb-1 ${symbolsStats.last_status === 'Completed' || symbolsStats.last_status === 'Completed (Partial)'
                    ? 'text-success'
                    : symbolsStats.last_status === 'Failed' || symbolsStats.last_status === 'Crashed'
                      ? 'text-danger'
                      : symbolsStats.last_status === 'Running' || symbolsStats.last_status === 'Queued'
                        ? 'text-primary'
                        : symbolsStats.last_status === 'Cancelled'
                          ? 'text-warning'
                          : 'text-text-secondary dark:text-[#9ca3af]'
                    }`}>
                    {symbolsStats.last_run_datetime ? formatDate(symbolsStats.last_run_datetime) : 'Never'}
                  </div>
                  <div className={`text-xs font-sans ${symbolsStats.last_status === 'Completed' || symbolsStats.last_status === 'Completed (Partial)'
                    ? 'text-success/80'
                    : symbolsStats.last_status === 'Failed' || symbolsStats.last_status === 'Crashed'
                      ? 'text-danger/80'
                      : symbolsStats.last_status === 'Running' || symbolsStats.last_status === 'Queued'
                        ? 'text-primary/80'
                        : symbolsStats.last_status === 'Cancelled'
                          ? 'text-warning/80'
                          : 'text-text-secondary/80 dark:text-[#9ca3af]/80'
                    }`}>
                    <span className="uppercase tracking-wider">Last Run by</span>{' '}
                    {(() => {
                      const uploadType = symbolsStats.last_upload_type === 'AUTO' ? 'Auto' : symbolsStats.last_upload_type === 'MANUAL' ? 'Manual' : (symbolsStats.last_upload_type || 'N/A')
                      const triggeredBy = symbolsStats.last_triggered_by || ''
                      const isScheduler = triggeredBy && triggeredBy.toLowerCase().startsWith('scheduler')
                      const triggerSource = isScheduler ? 'Scheduler' : (triggeredBy && triggeredBy !== 'system' ? 'User' : 'N/A')
                      return `${uploadType} - ${triggerSource}`
                    })()}
                  </div>
                </div>

                {/* Skipped Symbols - CLICKABLE */}
                <button
                  onClick={(e) => {
                    e.preventDefault()
                    e.stopPropagation()
                    router.push('/admin/symbols?expiry=skipped')
                  }}
                  className="text-center p-4 bg-info/10 dark:bg-[#3b82f6]/10 rounded-lg border border-info/20 hover:border-info/50 hover:bg-info/20 transition-all cursor-pointer w-full"
                >
                  <div className="text-3xl font-bold font-sans text-info mb-1">
                    {symbolsStats.skipped_symbols?.toLocaleString() || 0}
                  </div>
                  <div className="text-xs font-sans text-info uppercase tracking-wider">
                    Skipped Symbols
                  </div>
                </button>

                {/* New Inserted Symbols - NON-CLICKABLE */}
                <div className="text-center p-4 bg-success/10 dark:bg-[#10b981]/10 rounded-lg border border-success/20">
                  <div className="text-3xl font-bold font-sans text-success mb-1">
                    {symbolsStats.last_inserted_rows?.toLocaleString() || 0}
                  </div>
                  <div className="text-xs font-sans text-success uppercase tracking-wider">
                    New Inserted
                  </div>
                </div>
              </div>
            )}

            <p className="text-sm font-sans text-text-secondary dark:text-[#9ca3af] mb-4">
              Manage stock symbols, exchanges, sectors, and other symbol-related reference data used throughout the platform.
            </p>
            <Button
              variant="primary"
              size="sm"
              className="w-full"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                router.push('/admin/symbols')
              }}
            >
              <Settings className="w-4 h-4" />
              Manage Symbols
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </Card>

        <Link href="/admin/reference-data/indicators" className="block w-full max-w-sm">
          <Card className="hover:shadow-lg hover:border-success/30 transition-all duration-200 cursor-pointer h-full border-2">
            <div className="p-6 flex flex-col h-full">
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-success/10 dark:bg-[#10b981]/20 rounded-xl">
                    <Activity className="w-6 h-6 text-success" />
                  </div>
                  <div>
                    <h3 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
                      Indicators
                    </h3>
                    <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-0.5">
                      Technical indicators and configurations
                    </p>
                  </div>
                </div>
              </div>

              {/* Placeholder for future stats */}
              <div className="grid grid-cols-1 gap-4 mb-6">
                <div className="text-center p-6 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border">
                  <div className="text-2xl font-bold font-sans text-text-secondary dark:text-[#9ca3af] mb-1">
                    Coming Soon
                  </div>
                  <div className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
                    Indicator statistics will be displayed here
                  </div>
                </div>
              </div>

              <p className="text-sm font-sans text-text-secondary dark:text-[#9ca3af] mb-4">
                Configure technical indicators, their parameters, and settings used in analytics and reporting.
              </p>
              <Button variant="primary" size="sm" className="w-full">
                <Settings className="w-4 h-4" />
                Manage Indicators
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </Card>
        </Link>

        <Link href="/admin/reference-data/screener/connections" className="block w-full max-w-sm">
          <Card className="hover:shadow-lg hover:border-info/30 transition-all duration-200 cursor-pointer h-full border-2">
            <div className="p-6 flex flex-col h-full">
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="p-3 bg-info/10 dark:bg-[#06b6d4]/20 rounded-xl">
                    <BarChart3 className="w-6 h-6 text-info" />
                  </div>
                  <div>
                    <h3 className="text-lg font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
                      Screener
                    </h3>
                    <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] mt-0.5">
                      Company fundamentals, news & corporate actions
                    </p>
                  </div>
                </div>
              </div>

              {/* Stats Grid - 4 Cards */}
              {screenerLoading ? (
                <div className="py-8 text-center text-text-secondary">Loading...</div>
              ) : (
                <div className="grid grid-cols-2 gap-4 mb-6">
                  {/* Total Records - CLICKABLE */}
                  <button
                    onClick={(e) => {
                      e.preventDefault()
                      e.stopPropagation()
                      router.push('/users/screener')
                    }}
                    className="text-center p-4 bg-background/50 dark:bg-[#121b2f]/50 rounded-lg border border-border hover:border-info/50 hover:bg-info/5 transition-all cursor-pointer w-full"
                  >
                    <div className="text-3xl font-bold font-sans text-text-primary dark:text-[#e5e7eb] mb-1">
                      {screenerStats.total_records?.toLocaleString() || 0}
                    </div>
                    <div className="text-xs font-sans text-text-secondary dark:text-[#9ca3af] uppercase tracking-wider">
                      Total Records
                    </div>
                  </button>

                  {/* Last Run - NON-CLICKABLE with Status inside */}
                  <div className={`text-center p-4 rounded-lg border ${screenerStats.last_status === 'COMPLETED' || screenerStats.last_status === 'COMPLETED (Partial)'
                    ? 'bg-success/10 dark:bg-[#10b981]/10 border-success/20'
                    : screenerStats.last_status === 'FAILED'
                      ? 'bg-danger/10 dark:bg-[#ef4444]/10 border-danger/20'
                      : screenerStats.last_status === 'PROCESSING'
                        ? 'bg-primary/10 dark:bg-[#3b82f6]/10 border-primary/20'
                        : 'bg-text-secondary/10 dark:bg-[#6b7280]/10 border-text-secondary/20'
                    }`}>
                    {/* Status at the top */}
                    <div className={`text-sm font-bold font-sans mb-2 ${screenerStats.last_status === 'COMPLETED' || screenerStats.last_status === 'COMPLETED (Partial)'
                      ? 'text-success'
                      : screenerStats.last_status === 'FAILED'
                        ? 'text-danger'
                        : screenerStats.last_status === 'PROCESSING'
                          ? 'text-primary'
                          : 'text-text-secondary dark:text-[#9ca3af]'
                      }`}>
                      {screenerStats.last_status || 'N/A'}
                    </div>
                    {/* Date below status */}
                    <div className={`text-sm font-bold font-sans mb-1 ${screenerStats.last_status === 'COMPLETED' || screenerStats.last_status === 'COMPLETED (Partial)'
                      ? 'text-success'
                      : screenerStats.last_status === 'FAILED'
                        ? 'text-danger'
                        : screenerStats.last_status === 'PROCESSING'
                          ? 'text-primary'
                          : 'text-text-secondary dark:text-[#9ca3af]'
                      }`}>
                      {screenerStats.last_run_datetime ? formatDate(screenerStats.last_run_datetime) : 'Never'}
                    </div>
                    <div className={`text-xs font-sans ${screenerStats.last_status === 'COMPLETED' || screenerStats.last_status === 'COMPLETED (Partial)'
                      ? 'text-success/80'
                      : screenerStats.last_status === 'FAILED'
                        ? 'text-danger/80'
                        : screenerStats.last_status === 'PROCESSING'
                          ? 'text-primary/80'
                          : 'text-text-secondary/80 dark:text-[#9ca3af]/80'
                      }`}>
                      <span className="uppercase tracking-wider">Last Run by</span>{' '}
                      {screenerStats.last_triggered_by || 'N/A'}
                    </div>
                  </div>

                  {/* Symbols Succeeded - NON-CLICKABLE */}
                  <div className="text-center p-4 bg-success/10 dark:bg-[#10b981]/10 rounded-lg border border-success/20">
                    <div className="text-3xl font-bold font-sans text-success mb-1">
                      {screenerStats.last_symbols_succeeded?.toLocaleString() || 0}
                    </div>
                    <div className="text-xs font-sans text-success uppercase tracking-wider">
                      Succeeded
                    </div>
                  </div>

                  {/* Records Inserted - NON-CLICKABLE */}
                  <div className="text-center p-4 bg-info/10 dark:bg-[#06b6d4]/10 rounded-lg border border-info/20">
                    <div className="text-3xl font-bold font-sans text-info mb-1">
                      {screenerStats.last_records_inserted?.toLocaleString() || 0}
                    </div>
                    <div className="text-xs font-sans text-info uppercase tracking-wider">
                      Records
                    </div>
                  </div>
                </div>
              )}

              <p className="text-sm font-sans text-text-secondary dark:text-[#9ca3af] mb-4">
                Scrape company fundamentals, financial statements, ratios, news, and corporate actions from Screener.in.
              </p>
              <Button variant="primary" size="sm" className="w-full">
                <Settings className="w-4 h-4" />
                Configure Screener
                <ArrowRight className="w-4 h-4" />
              </Button>
            </div>
          </Card>
        </Link>
      </div>
    </div>
  )
}
