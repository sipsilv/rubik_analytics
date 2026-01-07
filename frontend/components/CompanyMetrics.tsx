'use client'

import { Card } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { ExternalLink, Plus, Edit } from 'lucide-react'

interface CompanyMetricsProps {
  symbol: string
  companyName?: string
  website?: string
  exchangeCode?: string
  metrics?: {
    marketCap?: number
    currentPrice?: number
    high?: number
    low?: number
    stockPE?: number
    bookValue?: number
    dividendYield?: number
    roce?: number
    roe?: number
    faceValue?: number
  }
  about?: string
  keyPoints?: string[]
}

export function CompanyMetrics({
  symbol,
  companyName,
  website,
  exchangeCode,
  metrics = {},
  about,
  keyPoints = []
}: CompanyMetricsProps) {
  const formatCurrency = (value?: number) => {
    if (value === undefined || value === null) return '-'
    if (value >= 10000000) return `₹${(value / 10000000).toFixed(2)} Cr.`
    if (value >= 100000) return `₹${(value / 100000).toFixed(2)} L`
    return `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
  }

  const formatPercent = (value?: number) => {
    if (value === undefined || value === null) return '-'
    return `${value.toFixed(2)}%`
  }

  const formatNumber = (value?: number) => {
    if (value === undefined || value === null) return '-'
    return value.toLocaleString('en-IN', { maximumFractionDigits: 2 })
  }

  return (
    <div className="space-y-4">
      {/* Company Header */}
      <Card className="p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-text-primary mb-2">
              {companyName || symbol}
            </h2>
            <div className="flex items-center gap-4 text-sm text-text-secondary">
              {website && (
                <a 
                  href={website.startsWith('http') ? website : `https://${website}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 hover:text-primary transition-colors"
                >
                  {website}
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
              {exchangeCode && (
                <span className="flex items-center gap-1">
                  {exchangeCode}
                  <ExternalLink className="w-3 h-3" />
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm">
              <Plus className="w-4 h-4 mr-2" />
              EXPORT TO EXCEL
            </Button>
            <Button variant="primary" size="sm">
              <Plus className="w-4 h-4 mr-2" />
              + FOLLOW
            </Button>
          </div>
        </div>
      </Card>

      {/* Key Financial Metrics */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-text-primary mb-4">
          Key Financial Metrics
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          <div>
            <p className="text-xs text-text-secondary mb-1">Market Cap</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatCurrency(metrics.marketCap)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">Current Price</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatCurrency(metrics.currentPrice)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">High / Low</p>
            <p className="text-sm font-semibold text-text-primary">
              {metrics.high && metrics.low 
                ? `${formatCurrency(metrics.high)} / ${formatCurrency(metrics.low)}`
                : '-'
              }
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">Stock P/E</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatNumber(metrics.stockPE)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">Book Value</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatCurrency(metrics.bookValue)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">Dividend Yield</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatPercent(metrics.dividendYield)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">ROCE</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatPercent(metrics.roce)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">ROE</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatPercent(metrics.roe)}
            </p>
          </div>
          <div>
            <p className="text-xs text-text-secondary mb-1">Face Value</p>
            <p className="text-sm font-semibold text-text-primary">
              {formatCurrency(metrics.faceValue)}
            </p>
          </div>
        </div>
        
        {/* Add ratio input */}
        <div className="mt-6 pt-4 border-t border-border">
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="eg. Promoter holding"
              className="flex-1 px-3 py-2 text-sm border border-border rounded-lg bg-background text-text-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <Button variant="ghost" size="sm">
              <Edit className="w-4 h-4 mr-2" />
              EDIT RATIOS
            </Button>
          </div>
        </div>
      </Card>

      {/* About Section */}
      {about && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-3">ABOUT</h3>
          <p className="text-sm text-text-secondary leading-relaxed">
            {about}
          </p>
        </Card>
      )}

      {/* Key Points Section */}
      {keyPoints.length > 0 && (
        <Card className="p-6">
          <h3 className="text-lg font-semibold text-text-primary mb-3">KEY POINTS</h3>
          <ul className="space-y-2">
            {keyPoints.map((point, index) => (
              <li key={index} className="text-sm text-text-secondary">
                {point}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  )
}

