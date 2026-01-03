'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, Search, X } from 'lucide-react'
import { symbolsAPI } from '@/lib/api'

export default function SymbolsPage() {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [symbols, setSymbols] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [total, setTotal] = useState(0)
  const [totalPages, setTotalPages] = useState(1)

  // Load symbols from API
  const loadSymbols = async () => {
    setLoading(true)
    try {
      const params: any = { page_size: pageSize, page: page }
      if (searchQuery.trim()) {
        params.search = searchQuery.trim()
      }
      console.log('[ReferenceDataSymbols] Loading symbols with params:', params)
      const data = await symbolsAPI.getSymbols(params)
      console.log('[ReferenceDataSymbols] API response:', {
        has_items: !!data.items,
        items_count: data.items?.length || 0,
        total: data.total || 0,
        page: data.page || 1
      })
      if (data.items) {
        setSymbols(data.items)
        setTotal(data.total || 0)
        setTotalPages(data.total_pages || 1)
        setPage(data.page || 1)
      } else {
        setSymbols(Array.isArray(data) ? data : [])
        setTotal(Array.isArray(data) ? data.length : 0)
        setTotalPages(1)
      }
    } catch (e: any) {
      console.error('[ReferenceDataSymbols] Error loading symbols:', e)
      console.error('[ReferenceDataSymbols] Error details:', {
        message: e?.message,
        response: e?.response?.data,
        status: e?.response?.status
      })
      setSymbols([])
      setTotal(0)
      setTotalPages(1)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSymbols()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, searchQuery])

  // Update search input value only (no API call)
  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  // Execute search only on button click
  const handleSearchClick = () => {
    setSearchQuery(search)
    setPage(1) // reset to page 1 on search
  }

  // Clear search and reset to default (unfiltered) state
  const handleClearSearch = () => {
    setSearch('')
    setSearchQuery('')
    setPage(1)
  }

  // Handle Enter key in search input
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  const filteredSymbols = symbols

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push('/admin/reference-data')}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
            Symbols
          </h1>
          <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
            Manage stock symbols and reference data
          </p>
        </div>
      </div>
      
      <div className="flex items-center justify-between">
        <div></div>
        <Button size="sm">Add Symbol</Button>
      </div>

      <Card compact>
        <div className="mb-3 flex items-center gap-2">
          <div className="flex-1 max-w-md">
            <Input
              type="text"
              placeholder="Search symbols..."
              value={search}
              onChange={(e) => handleSearchChange(e.target.value)}
              onKeyDown={handleSearchKeyDown}
              className="h-9"
            />
          </div>
          <Button
            variant="primary"
            onClick={handleSearchClick}
            size="sm"
            disabled={loading}
            className="h-9 px-4 flex-shrink-0"
          >
            <Search className="w-4 h-4 mr-1.5" />
            Search
          </Button>
          {search && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearSearch}
              disabled={loading}
              className="h-9 px-3 flex-shrink-0"
            >
              <X className="w-4 h-4 mr-1.5" />
              Clear
            </Button>
          )}
        </div>

        <Table>
          <TableHeader>
            <TableHeaderCell>Symbol</TableHeaderCell>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Exchange</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell className="text-right">Actions</TableHeaderCell>
          </TableHeader>
          <TableBody>
            {loading && symbols.length === 0 ? (
              <TableRow>
                <td colSpan={6} className="px-3 py-12 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                    <p className="text-text-secondary">Loading symbols...</p>
                  </div>
                </td>
              </TableRow>
            ) : (
              <>
                {filteredSymbols.map((symbol, index) => (
                  <TableRow key={symbol.id || index} index={index}>
                    <TableCell className="font-mono text-xs text-primary font-semibold">
                      {symbol.trading_symbol || symbol.symbol || '-'}
                    </TableCell>
                    <TableCell className="text-xs max-w-[150px] truncate">
                      <span title={symbol.name || ''}>{symbol.name || '-'}</span>
                    </TableCell>
                    <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                      {symbol.exchange || '-'}
                    </TableCell>
                    <TableCell className="text-text-secondary dark:text-[#9ca3af] text-xs">
                      {symbol.instrument_type || '-'}
                    </TableCell>
                    <TableCell>
                      {(() => {
                        const rawStatus = symbol.status || 'ACTIVE'
                        const statusUpper = String(rawStatus).trim().toUpperCase()
                        const isActive = statusUpper === 'ACTIVE'
                        return (
                          <span className={`text-[10px] font-sans px-1.5 py-0.5 rounded uppercase ${
                            isActive 
                              ? 'bg-success/10 text-success' 
                              : 'bg-error/10 text-error'
                          }`}>
                            {statusUpper}
                          </span>
                        )
                      })()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1 justify-end">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => router.push(`/admin/symbols?symbol=${encodeURIComponent(symbol.trading_symbol || symbol.symbol || '')}`)}
                        >
                          View
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {symbols.length === 0 && !loading && (
                  <TableRow>
                    <td colSpan={6} className="px-3 py-12 text-center">
                      <div className="flex flex-col items-center gap-2">
                        <p className="text-text-secondary">No symbols found</p>
                        {searchQuery && (
                          <p className="text-xs text-text-secondary">
                            No symbols found matching "{searchQuery}"
                          </p>
                        )}
                      </div>
                    </td>
                  </TableRow>
                )}
              </>
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
