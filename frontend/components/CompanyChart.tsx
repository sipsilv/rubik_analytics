'use client'

import { useState, useMemo } from 'react'
import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { 
  LineChart, 
  Line, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  ComposedChart
} from 'recharts'
import { Bell, Download, MoreVertical } from 'lucide-react'

interface ChartDataPoint {
  date: string
  price: number
  volume: number
  dma50?: number
  dma200?: number
}

interface CompanyChartProps {
  symbol: string
  companyName?: string
  data?: ChartDataPoint[]
  currentPrice?: number
  priceChange?: number
  priceChangePercent?: number
}

const timeRanges = [
  { label: '1M', value: '1M', days: 30 },
  { label: '6M', value: '6M', days: 180 },
  { label: '1Yr', value: '1Yr', days: 365 },
  { label: '3Yr', value: '3Yr', days: 1095 },
  { label: '5Yr', value: '5Yr', days: 1825 },
  { label: '10Yr', value: '10Yr', days: 3650 },
  { label: 'Max', value: 'Max', days: Infinity }
]

const chartTypes = ['Price', 'PE Ratio', 'More']

export function CompanyChart({ 
  symbol, 
  companyName, 
  data = [], 
  currentPrice,
  priceChange,
  priceChangePercent 
}: CompanyChartProps) {
  const [selectedRange, setSelectedRange] = useState('1Yr')
  const [selectedChartType, setSelectedChartType] = useState('Price')
  const [showDMA50, setShowDMA50] = useState(false)
  const [showDMA200, setShowDMA200] = useState(false)
  const [showVolume, setShowVolume] = useState(true)

  // Filter data based on selected time range
  const filteredData = useMemo(() => {
    if (!data || data.length === 0) return []
    
    const range = timeRanges.find(r => r.value === selectedRange)
    if (!range || range.days === Infinity) return data
    
    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - range.days)
    
    return data.filter(point => {
      const pointDate = new Date(point.date)
      return pointDate >= cutoffDate
    })
  }, [data, selectedRange])

  // Calculate min/max for Y-axes
  const priceRange = useMemo(() => {
    if (filteredData.length === 0) return { min: 0, max: 1000 }
    const prices = filteredData.map(d => d.price).filter(p => p != null)
    const volumes = filteredData.map(d => d.volume).filter(v => v != null)
    return {
      priceMin: Math.min(...prices) * 0.95,
      priceMax: Math.max(...prices) * 1.05,
      volumeMax: Math.max(...volumes) * 1.1
    }
  }, [filteredData])

  // Format date for display
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
  }

  // Format price
  const formatPrice = (value: number) => {
    return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
  }

  // Format volume
  const formatVolume = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`
    if (value >= 1000) return `${(value / 1000).toFixed(1)}k`
    return value.toString()
  }

  return (
    <Card className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-xl font-semibold text-text-primary">
            {companyName || symbol}
          </h3>
          {currentPrice !== undefined && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-2xl font-bold text-text-primary">
                ₹{currentPrice.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
              </span>
              {priceChangePercent !== undefined && (
                <span className={`text-sm font-medium ${
                  priceChangePercent >= 0 ? 'text-success' : 'text-error'
                }`}>
                  {priceChangePercent >= 0 ? '+' : ''}{priceChangePercent.toFixed(2)}%
                </span>
              )}
              {priceChange !== undefined && (
                <span className={`text-sm ${
                  priceChange >= 0 ? 'text-success' : 'text-error'
                }`}>
                  ({priceChange >= 0 ? '+' : ''}₹{priceChange.toFixed(2)})
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm">
            <Bell className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm">
            <Download className="w-4 h-4" />
          </Button>
          <Button variant="ghost" size="sm">
            <MoreVertical className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* Time Range Selector */}
      <div className="flex items-center gap-2 mb-4">
        {timeRanges.map(range => (
          <Button
            key={range.value}
            variant={selectedRange === range.value ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setSelectedRange(range.value)}
            className="px-3 py-1 text-xs"
          >
            {range.label}
          </Button>
        ))}
      </div>

      {/* Chart Type Selector */}
      <div className="flex items-center gap-2 mb-4">
        {chartTypes.map(type => (
          <Button
            key={type}
            variant={selectedChartType === type ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setSelectedChartType(type)}
            className="px-3 py-1 text-xs"
          >
            {type}
          </Button>
        ))}
      </div>

      {/* Chart */}
      <div className="h-96 mb-4">
        {filteredData.length === 0 ? (
          <div className="flex items-center justify-center h-full text-text-secondary">
            <p>No chart data available</p>
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={filteredData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2a44" />
              <XAxis 
                dataKey="date" 
                tickFormatter={formatDate}
                stroke="#9ca3af"
                style={{ fontSize: '12px' }}
              />
              <YAxis 
                yAxisId="price"
                orientation="right"
                domain={[priceRange.priceMin, priceRange.priceMax]}
                tickFormatter={formatPrice}
                stroke="#9ca3af"
                style={{ fontSize: '12px' }}
                label={{ value: 'Price on BSE', angle: -90, position: 'insideRight', style: { textAnchor: 'middle', fill: '#9ca3af' } }}
              />
              <YAxis 
                yAxisId="volume"
                orientation="left"
                domain={[0, priceRange.volumeMax]}
                tickFormatter={formatVolume}
                stroke="#9ca3af"
                style={{ fontSize: '12px' }}
                label={{ value: 'Volume', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle', fill: '#9ca3af' } }}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#121b2f', 
                  border: '1px solid #1f2a44',
                  borderRadius: '8px'
                }}
                labelStyle={{ color: '#e5e7eb' }}
                formatter={(value: any, name: string) => {
                  if (name === 'price' || name === 'dma50' || name === 'dma200') {
                    return formatPrice(value)
                  }
                  return formatVolume(value)
                }}
              />
              <Legend />
              {showVolume && (
                <Bar 
                  yAxisId="volume" 
                  dataKey="volume" 
                  fill="#9333ea" 
                  opacity={0.3}
                  name="Volume"
                />
              )}
              <Line 
                yAxisId="price" 
                type="monotone" 
                dataKey="price" 
                stroke="#9333ea" 
                strokeWidth={2}
                dot={false}
                name="Price on BSE"
              />
              {showDMA50 && (
                <Line 
                  yAxisId="price" 
                  type="monotone" 
                  dataKey="dma50" 
                  stroke="#3b82f6" 
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={false}
                  name="50 DMA"
                />
              )}
              {showDMA200 && (
                <Line 
                  yAxisId="price" 
                  type="monotone" 
                  dataKey="dma200" 
                  stroke="#10b981" 
                  strokeWidth={1}
                  strokeDasharray="5 5"
                  dot={false}
                  name="200 DMA"
                />
              )}
            </ComposedChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Legend/Checkboxes */}
      <div className="flex items-center gap-4 flex-wrap">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={true}
            readOnly
            className="w-4 h-4 text-primary bg-background border-border rounded focus:ring-primary"
          />
          <span className="text-sm text-text-secondary">Price on BSE</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showDMA50}
            onChange={(e) => setShowDMA50(e.target.checked)}
            className="w-4 h-4 text-primary bg-background border-border rounded focus:ring-primary"
          />
          <span className="text-sm text-text-secondary">50 DMA</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showDMA200}
            onChange={(e) => setShowDMA200(e.target.checked)}
            className="w-4 h-4 text-primary bg-background border-border rounded focus:ring-primary"
          />
          <span className="text-sm text-text-secondary">200 DMA</span>
        </label>
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={showVolume}
            onChange={(e) => setShowVolume(e.target.checked)}
            className="w-4 h-4 text-primary bg-background border-border rounded focus:ring-primary"
          />
          <span className="text-sm text-text-secondary">Volume</span>
        </label>
      </div>
    </Card>
  )
}

