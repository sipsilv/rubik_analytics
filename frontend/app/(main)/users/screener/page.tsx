'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useState, useEffect, useRef, useMemo } from 'react'
import { Search, X, BarChart3, ArrowLeft, ChevronDown } from 'lucide-react'
import { screenerAPI, symbolsAPI } from '@/lib/api'
import { CompanyChart } from '@/components/CompanyChart'
import { CompanyMetrics } from '@/components/CompanyMetrics'

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
  const [symbolDropdownOpen, setSymbolDropdownOpen] = useState(false)
  const [symbolSearchTerm, setSymbolSearchTerm] = useState('')
  const [viewMode, setViewMode] = useState<'list' | 'detail'>('list')
  const [selectedCompany, setSelectedCompany] = useState<string | null>(null)

  const periodTypes = ['ANNUAL', 'SNAPSHOT', 'EVENT']
  const statementGroups = ['MARKET', 'PROFIT_LOSS', 'BALANCE_SHEET', 'CASH_FLOW', 'RATIOS', 'PEER', 'NEWS', 'CORPORATE_ACTION']

  const hasLoadedSymbolsRef = useRef(false)
  const symbolDropdownRef = useRef<HTMLDivElement>(null)

  // Load symbols for dropdown
  useEffect(() => {
    // Prevent double call in React Strict Mode
    if (hasLoadedSymbolsRef.current) return
    hasLoadedSymbolsRef.current = true
    
    const loadSymbols = async () => {
      try {
        const result = await symbolsAPI.getSymbols({ page_size: 1000, page: 1, status: 'ACTIVE' })
        const items = result.items || result
        setSymbols(Array.isArray(items) ? items.filter((s: any) => s.status === 'ACTIVE') : [])
      } catch (e) {
        console.error('Failed to load symbols:', e)
      }
    }
    loadSymbols()
  }, [])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (symbolDropdownRef.current && !symbolDropdownRef.current.contains(event.target as Node)) {
        setSymbolDropdownOpen(false)
      }
    }

    if (symbolDropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [symbolDropdownOpen])

  // Filter symbols based on search term
  const filteredSymbols = useMemo(() => {
    if (!symbolSearchTerm) return symbols.slice(0, 50) // Show first 50 if no search
    const term = symbolSearchTerm.toLowerCase()
    return symbols
      .filter((s: any) => {
        const tradingSymbol = (s.trading_symbol || '').toLowerCase()
        const name = (s.name || '').toLowerCase()
        return tradingSymbol.includes(term) || name.includes(term)
      })
      .slice(0, 50) // Limit to 50 results
  }, [symbols, symbolSearchTerm])

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
    setSymbolSearchTerm('')
  }

  const handleSymbolSelect = (symbol: string) => {
    setSelectedSymbol(symbol)
    setSearch(symbol)
    setSearchQuery(symbol)
    setSymbolDropdownOpen(false)
    setSymbolSearchTerm('')
    // Automatically switch to detail view when symbol is selected
    setSelectedCompany(symbol)
    setViewMode('detail')
  }

  const handleSymbolDropdownToggle = () => {
    setSymbolDropdownOpen(!symbolDropdownOpen)
    if (!symbolDropdownOpen) {
      setSymbolSearchTerm('')
    }
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

  // Get unique companies from data
  const companies = useMemo(() => {
    const companyMap = new Map<string, any>()
    filteredData.forEach(item => {
      if (item.symbol && !companyMap.has(item.symbol)) {
        companyMap.set(item.symbol, {
          symbol: item.symbol,
          exchange: item.exchange
        })
      }
    })
    return Array.from(companyMap.values())
  }, [filteredData])

  // Get metrics for selected company
  const companyMetrics = useMemo(() => {
    if (!selectedCompany) return null
    
    const companyData = filteredData.filter(item => item.symbol === selectedCompany)
    const metrics: any = {}
    
    companyData.forEach(item => {
      const value = item.metric_value
      if (typeof value === 'number') {
        switch (item.metric_name?.toUpperCase()) {
          case 'MARKET CAP':
          case 'MARKET CAPITALIZATION':
            metrics.marketCap = value
            break
          case 'CURRENT PRICE':
          case 'PRICE':
            metrics.currentPrice = value
            break
          case 'HIGH':
            metrics.high = value
            break
          case 'LOW':
            metrics.low = value
            break
          case 'P/E':
          case 'PE RATIO':
          case 'PRICE TO EARNINGS':
            metrics.stockPE = value
            break
          case 'BOOK VALUE':
            metrics.bookValue = value
            break
          case 'DIVIDEND YIELD':
            metrics.dividendYield = value
            break
          case 'ROCE':
          case 'RETURN ON CAPITAL EMPLOYED':
            metrics.roce = value
            break
          case 'ROE':
          case 'RETURN ON EQUITY':
            metrics.roe = value
            break
          case 'FACE VALUE':
            metrics.faceValue = value
            break
        }
      }
    })
    
    return metrics
  }, [selectedCompany, filteredData])

  // Get company info from symbols list
  const selectedCompanyInfo = useMemo(() => {
    if (!selectedCompany) return null
    return symbols.find((s: any) => s.trading_symbol === selectedCompany)
  }, [selectedCompany, symbols])

  // Generate mock chart data (in real implementation, this would come from API)
  const generateChartData = (symbol: string) => {
    const data: any[] = []
    const basePrice = companyMetrics?.currentPrice || 1000
    const baseVolume = 10000
    const today = new Date()
    const prices: number[] = []
    
    // Generate price data first
    for (let i = 365; i >= 0; i--) {
      const date = new Date(today)
      date.setDate(date.getDate() - i)
      
      // Generate realistic price movement with trend
      const trend = (365 - i) / 365 * 0.1 // 10% overall trend
      const randomChange = (Math.random() - 0.5) * 0.02
      const price = basePrice * (1 - trend + randomChange)
      prices.push(price)
      
      // Generate volume with some spikes
      const volumeMultiplier = Math.random() > 0.9 ? 3 + Math.random() * 2 : 0.5 + Math.random()
      const volume = baseVolume * volumeMultiplier
      
      data.push({
        date: date.toISOString().split('T')[0],
        price: Math.round(price * 100) / 100,
        volume: Math.round(volume)
      })
    }
    
    // Calculate moving averages
    data.forEach((point, index) => {
      // 50 DMA
      if (index >= 49) {
        const slice50 = prices.slice(index - 49, index + 1)
        point.dma50 = Math.round((slice50.reduce((a, b) => a + b, 0) / 50) * 100) / 100
      }
      
      // 200 DMA
      if (index >= 199) {
        const slice200 = prices.slice(index - 199, index + 1)
        point.dma200 = Math.round((slice200.reduce((a, b) => a + b, 0) / 200) * 100) / 100
      }
    })
    
    return data
  }

  const handleCompanyClick = (symbol: string) => {
    setSelectedCompany(symbol)
    setViewMode('detail')
  }

  const handleBackToList = () => {
    setViewMode('list')
    setSelectedCompany(null)
  }

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
          {/* Symbol Dropdown */}
          <div className="relative" ref={symbolDropdownRef}>
            <label className="block text-xs font-sans font-medium text-text-secondary dark:text-[#9ca3af] mb-2">
              Symbol
            </label>
            <div className="relative">
              <button
                type="button"
                onClick={handleSymbolDropdownToggle}
                className="w-full px-3 py-2 text-sm border border-border dark:border-[#1f2a44] rounded-lg bg-background dark:bg-[#121b2f] text-text-primary dark:text-[#e5e7eb] focus:outline-none focus:ring-2 focus:ring-primary/30 flex items-center justify-between"
              >
                <span className={selectedSymbol ? 'text-text-primary' : 'text-text-secondary'}>
                  {selectedSymbol || 'Select symbol...'}
                </span>
                <ChevronDown className={`w-4 h-4 text-text-secondary transition-transform ${symbolDropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              
              {symbolDropdownOpen && (
                <div className="absolute z-50 w-full mt-1 bg-background dark:bg-[#121b2f] border border-border dark:border-[#1f2a44] rounded-lg shadow-lg max-h-64 overflow-hidden">
                  {/* Search input inside dropdown */}
                  <div className="p-2 border-b border-border dark:border-[#1f2a44]">
                    <div className="relative">
                      <Search className="absolute left-2 top-1/2 transform -translate-y-1/2 w-4 h-4 text-text-secondary" />
                      <Input
                        type="text"
                        placeholder="Search symbols..."
                        value={symbolSearchTerm}
                        onChange={(e) => setSymbolSearchTerm(e.target.value)}
                        className="pl-8 pr-8 text-sm"
                        autoFocus
                      />
                      {symbolSearchTerm && (
                        <button
                          onClick={() => setSymbolSearchTerm('')}
                          className="absolute right-2 top-1/2 transform -translate-y-1/2 text-text-secondary hover:text-text-primary"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {/* Symbol list */}
                  <div className="overflow-y-auto max-h-48">
                    {filteredSymbols.length === 0 ? (
                      <div className="px-3 py-2 text-sm text-text-secondary text-center">
                        No symbols found
                      </div>
                    ) : (
                      filteredSymbols.map((symbol: any) => (
                        <button
                          key={symbol.id || symbol.trading_symbol}
                          type="button"
                          onClick={() => handleSymbolSelect(symbol.trading_symbol)}
                          className={`w-full px-3 py-2 text-sm text-left hover:bg-background/50 dark:hover:bg-[#1f2a44] transition-colors ${
                            selectedSymbol === symbol.trading_symbol
                              ? 'bg-primary/10 text-primary'
                              : 'text-text-primary'
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-medium">{symbol.trading_symbol}</span>
                            {symbol.name && (
                              <span className="text-xs text-text-secondary ml-2 truncate max-w-[200px]">
                                {symbol.name}
                              </span>
                            )}
                          </div>
                          {symbol.exchange && (
                            <div className="text-xs text-text-secondary mt-0.5">
                              {symbol.exchange}
                            </div>
                          )}
                        </button>
                      ))
                    )}
                  </div>
                  
                  {/* Clear selection */}
                  {selectedSymbol && (
                    <div className="p-2 border-t border-border dark:border-[#1f2a44]">
                      <button
                        type="button"
                        onClick={() => {
                          handleSymbolSelect('')
                          handleClearSearch()
                        }}
                        className="w-full px-3 py-2 text-sm text-center text-text-secondary hover:text-text-primary hover:bg-background/50 dark:hover:bg-[#1f2a44] rounded transition-colors"
                      >
                        Clear Selection
                      </button>
                    </div>
                  )}
                </div>
              )}
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

      {/* View Mode Toggle */}
      {viewMode === 'list' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="text-sm font-sans text-text-secondary dark:text-[#9ca3af]">
              Showing {filteredData.length} of {total} records
            </div>
            {companies.length > 0 && (
              <div className="text-sm font-sans text-text-secondary dark:text-[#9ca3af]">
                {companies.length} companies found
              </div>
            )}
          </div>
        </div>
      )}

      {/* Company Detail View */}
      {viewMode === 'detail' && selectedCompany && (
        <div className="space-y-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBackToList}
            className="mb-4"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to List
          </Button>

          {/* Chart */}
          <CompanyChart
            symbol={selectedCompany}
            companyName={selectedCompanyInfo?.name || selectedCompany}
            data={generateChartData(selectedCompany)}
            currentPrice={companyMetrics?.currentPrice}
            priceChange={companyMetrics?.currentPrice && companyMetrics?.low 
              ? companyMetrics.currentPrice - companyMetrics.low 
              : undefined
            }
            priceChangePercent={companyMetrics?.currentPrice && companyMetrics?.low
              ? ((companyMetrics.currentPrice - companyMetrics.low) / companyMetrics.low) * 100
              : undefined
            }
          />

          {/* Metrics */}
          <CompanyMetrics
            symbol={selectedCompany}
            companyName={selectedCompanyInfo?.name || selectedCompany}
            website={selectedCompanyInfo?.website}
            exchangeCode={selectedCompanyInfo?.exchange ? `${selectedCompanyInfo.exchange}: ${selectedCompanyInfo.trading_symbol}` : filteredData.find(d => d.symbol === selectedCompany)?.exchange}
            metrics={companyMetrics || {}}
            about={selectedCompanyInfo?.description || `Company information for ${selectedCompanyInfo?.name || selectedCompany}. ${selectedCompanyInfo?.exchange ? `Listed on ${selectedCompanyInfo.exchange}.` : ''} This is a publicly traded company with operations in the Indian market.`}
            keyPoints={[
              `Business Profile: ${selectedCompanyInfo?.name || selectedCompany} is a publicly traded company.`,
              selectedCompanyInfo?.exchange ? `Listed on ${selectedCompanyInfo.exchange}.` : 'Listed on NSE/BSE.',
              selectedCompanyInfo?.instrument_type ? `Instrument Type: ${selectedCompanyInfo.instrument_type}.` : 'Equity instrument.'
            ]}
          />
        </div>
      )}

      {/* Data Table (List View) */}
      {viewMode === 'list' && (
        <div className="space-y-4">
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
                    <TableRow 
                      key={idx} 
                      index={idx}
                      className="cursor-pointer hover:bg-background/50"
                      onClick={() => row.symbol && handleCompanyClick(row.symbol)}
                    >
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
      )}
    </div>
  )
}

