'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useState, useEffect, useRef } from 'react'
import { Search, X, BarChart3 } from 'lucide-react'
import { screenerAPI, symbolsAPI } from '@/lib/api'

export default function ScreenerPage() {
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [symbols, setSymbols] = useState<any[]>([])
  const [selectedSymbol, setSelectedSymbol] = useState<string>('')
  const [selectedPeriodType, setSelectedPeriodType] = useState<string>('')
  const [selectedStatementGroup, setSelectedStatementGroup] = useState<string>('')
  const [total, setTotal] = useState(0)

  const periodTypes = ['ANNUAL', 'SNAPSHOT', 'EVENT']
  const statementGroups = ['MARKET', 'PROFIT_LOSS', 'BALANCE_SHEET', 'CASH_FLOW', 'RATIOS', 'PEER', 'NEWS', 'CORPORATE_ACTION']

  const hasLoadedSymbolsRef = useRef(false)

  // Load symbols for dropdown
  useEffect(() => {
    // Prevent double call in React Strict Mode
    if (hasLoadedSymbolsRef.current) return
    hasLoadedSymbolsRef.current = true
    
    const loadSymbols = async () => {
      try {
        const result = await symbolsAPI.getSymbols({ page_size: 1000, page: 1 })
        const items = result.items || result
        setSymbols(Array.isArray(items) ? items : [])
      } catch (e) {
        console.error('Failed to load symbols:', e)
      }
    }
    loadSymbols()
  }, [])

  // Load data
  const loadData = async () => {
    setLoading(true)
    try {
      const params: any = {
        limit: 1000,
        offset: 0
      }
      if (selectedSymbol) params.symbol = selectedSymbol
      if (selectedPeriodType) params.period_type = selectedPeriodType
      if (selectedStatementGroup) params.statement_group = selectedStatementGroup
      
      const result = await screenerAPI.getData(params)
      setData(result.items || [])
      setTotal(result.total || 0)
    } catch (e: any) {
      console.error('Failed to load Screener data:', e)
      setData([])
      setTotal(0)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSymbol, selectedPeriodType, selectedStatementGroup])

  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  const handleSearchClick = () => {
    setSearchQuery(search)
    setSelectedSymbol(search.toUpperCase())
  }

  const handleClearSearch = () => {
    setSearch('')
    setSearchQuery('')
    setSelectedSymbol('')
  }

  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  const filteredData = data.filter(item => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      item.symbol?.toLowerCase().includes(query) ||
      item.metric_name?.toLowerCase().includes(query) ||
      item.statement_group?.toLowerCase().includes(query)
    )
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="p-2 bg-info/10 dark:bg-[#06b6d4]/20 rounded-lg">
          <BarChart3 className="w-5 h-5 text-info" />
        </div>
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
            Screener
          </h1>
          <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
            View company fundamentals, news, and corporate actions from Screener.in
          </p>
        </div>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Symbol Search */}
          <div>
            <label className="block text-xs font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
              Symbol
            </label>
            <div className="flex gap-2">
              <Input
                type="text"
                placeholder="Search symbol..."
                value={search}
                onChange={(e) => handleSearchChange(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                className="flex-1"
              />
              {search && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearSearch}
                  className="p-2"
                >
                  <X className="w-4 h-4" />
                </Button>
              )}
              <Button
                variant="primary"
                size="sm"
                onClick={handleSearchClick}
              >
                <Search className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Period Type Filter */}
          <div>
            <label className="block text-xs font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
              Period Type
            </label>
            <select
              value={selectedPeriodType}
              onChange={(e) => setSelectedPeriodType(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-border dark:border-[#1f2a44] rounded-lg bg-background dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="">All Period Types</option>
              {periodTypes.map(type => (
                <option key={type} value={type}>{type}</option>
              ))}
            </select>
          </div>

          {/* Statement Group Filter */}
          <div>
            <label className="block text-xs font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
              Statement Group
            </label>
            <select
              value={selectedStatementGroup}
              onChange={(e) => setSelectedStatementGroup(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-border dark:border-[#1f2a44] rounded-lg bg-background dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              <option value="">All Groups</option>
              {statementGroups.map(group => (
                <option key={group} value={group}>{group}</option>
              ))}
            </select>
          </div>

          {/* Clear Filters */}
          <div className="flex items-end">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setSelectedSymbol('')
                setSelectedPeriodType('')
                setSelectedStatementGroup('')
                setSearch('')
                setSearchQuery('')
              }}
              className="w-full"
            >
              Clear Filters
            </Button>
          </div>
        </div>
      </Card>

      {/* Data Table */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="text-sm font-sans text-text-secondary dark:text-[#9ca3af]">
            Showing {filteredData.length} of {total} records
          </div>
        </div>

        {loading ? (
          <Card compact>
            <div className="px-3 py-12 text-center">
              <div className="flex flex-col items-center gap-2">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                <p className="text-text-secondary">Loading data...</p>
              </div>
            </div>
          </Card>
        ) : filteredData.length === 0 ? (
          <Card compact>
            <div className="px-3 py-12 text-center">
              <div className="flex flex-col items-center gap-2">
                <p className="text-text-secondary">No data found</p>
                <p className="text-xs text-text-secondary">
                  Try adjusting your filters or scrape data from Reference Data.
                </p>
              </div>
            </div>
          </Card>
        ) : (
            <Card compact>
              <Table>
                <TableHeader>
                  <TableHeaderCell>Symbol</TableHeaderCell>
                  <TableHeaderCell>Exchange</TableHeaderCell>
                  <TableHeaderCell>Period Type</TableHeaderCell>
                  <TableHeaderCell>Period Key</TableHeaderCell>
                  <TableHeaderCell>Statement Group</TableHeaderCell>
                  <TableHeaderCell>Metric Name</TableHeaderCell>
                  <TableHeaderCell className="text-right" numeric>Metric Value</TableHeaderCell>
                  <TableHeaderCell>Unit</TableHeaderCell>
                  <TableHeaderCell>Entity Type</TableHeaderCell>
                </TableHeader>
                <TableBody>
                  {filteredData.map((row, idx) => (
                    <TableRow key={idx} index={idx}>
                      <TableCell className="font-sans font-semibold text-xs text-text-primary dark:text-[#e5e7eb] whitespace-nowrap">
                        {row.symbol || '-'}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                        {row.exchange || '-'}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                        {row.period_type || '-'}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs whitespace-nowrap">
                        {row.period_key || '-'}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                        {row.statement_group || '-'}
                      </TableCell>
                      <TableCell className="font-medium text-xs">
                        {row.metric_name || '-'}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs text-right" numeric>
                        {row.metric_value !== null && row.metric_value !== undefined
                          ? typeof row.metric_value === 'number'
                            ? row.metric_value.toLocaleString()
                            : row.metric_value
                          : '-'}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                        {row.unit || '-'}
                      </TableCell>
                      <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                        {row.entity_type || '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </Card>
          )}
      </div>
    </div>
  )
}

