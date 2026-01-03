'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Search, X, ArrowLeft } from 'lucide-react'

export default function IndicatorsPage() {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  const indicators = [
    { id: '1', name: 'RSI', type: 'Momentum', parameters: { period: 14 }, is_active: true },
    { id: '2', name: 'MACD', type: 'Trend', parameters: { fast: 12, slow: 26, signal: 9 }, is_active: true },
    { id: '3', name: 'Bollinger Bands', type: 'Volatility', parameters: { period: 20, std: 2 }, is_active: true },
    { id: '4', name: 'SMA', type: 'Trend', parameters: { period: 50 }, is_active: true },
    { id: '5', name: 'EMA', type: 'Trend', parameters: { period: 20 }, is_active: false },
  ]

  // Update search input value only (no filtering)
  const handleSearchChange = (val: string) => {
    setSearch(val)
  }

  // Execute search only on button click
  const handleSearchClick = () => {
    setSearchQuery(search)
  }

  // Clear search and reset to default (unfiltered) state
  const handleClearSearch = () => {
    setSearch('')
    setSearchQuery('')
  }

  // Handle Enter key in search input
  const handleSearchKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearchClick()
    }
  }

  const filteredIndicators = indicators.filter(ind =>
    ind.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    ind.type.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <button
          onClick={() => router.push('/admin/reference-data')}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
            Indicators
          </h1>
          <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
            Manage technical indicators and their configurations
          </p>
        </div>
      </div>
      
      <div className="flex items-center justify-between">
        <div></div>
        <Button size="sm">Add Indicator</Button>
      </div>

      <Card compact>
        <div className="mb-4 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <div className="flex-1 max-w-md">
              <Input
                type="text"
                placeholder="Search indicators..."
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
                className="h-9 px-3 flex-shrink-0"
              >
                <X className="w-4 h-4 mr-1.5" />
                Clear
              </Button>
            )}
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableHeaderCell>Name</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>Parameters</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell className="text-right">Actions</TableHeaderCell>
          </TableHeader>
          <TableBody>
            {filteredIndicators.map((indicator, index) => (
              <TableRow key={indicator.id} index={index}>
                <TableCell className="font-sans font-semibold">{indicator.name}</TableCell>
                <TableCell className="text-text-secondary dark:text-[#9ca3af]">{indicator.type}</TableCell>
                <TableCell className="font-sans text-xs text-text-secondary dark:text-[#9ca3af]">
                  {JSON.stringify(indicator.parameters)}
                </TableCell>
                <TableCell>
                  <span className={`text-[10px] font-sans px-1.5 py-0.5 rounded uppercase ${
                    indicator.is_active 
                      ? 'bg-success/10 text-success' 
                      : 'bg-error/10 text-error'
                  }`}>
                    {indicator.is_active ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                </TableCell>
                <TableCell>
                  <div className="flex gap-1 justify-end">
                    <Button variant="ghost" size="sm">Edit</Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
