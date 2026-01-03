'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'

export default function AnalyticsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-[#e5e7eb] mb-1">
          Analytics
        </h1>
        <p className="text-xs font-sans text-[#9ca3af]">
          Deep dive into market data and trends
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Market Overview" compact>
          <div className="space-y-3">
            <div className="h-48 bg-[#121b2f] rounded border border-[#1f2a44] flex items-center justify-center">
              <p className="text-xs font-sans text-[#9ca3af]">Chart visualization</p>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="text-center p-3 bg-[#121b2f] rounded border border-[#1f2a44]">
                <p className="text-lg font-sans font-semibold text-[#e5e7eb]">1,234</p>
                <p className="text-[10px] font-sans text-[#9ca3af] mt-1">Total Symbols</p>
              </div>
              <div className="text-center p-3 bg-[#121b2f] rounded border border-[#1f2a44]">
                <p className="text-lg font-sans font-semibold text-success">89</p>
                <p className="text-[10px] font-sans text-[#9ca3af] mt-1">Buy Signals</p>
              </div>
              <div className="text-center p-3 bg-[#121b2f] rounded border border-[#1f2a44]">
                <p className="text-lg font-sans font-semibold text-error">23</p>
                <p className="text-[10px] font-sans text-[#9ca3af] mt-1">Sell Signals</p>
              </div>
            </div>
          </div>
        </Card>

        <Card title="Performance Metrics" compact>
          <div className="space-y-3">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-sans text-[#9ca3af]">Model Accuracy</span>
                <span className="text-sm font-sans font-semibold text-[#e5e7eb]">87.5%</span>
              </div>
              <div className="w-full bg-[#0e1628] rounded-full h-1.5 border border-[#1f2a44]">
                <div className="bg-success h-1.5 rounded-full" style={{ width: '87.5%' }}></div>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-sans text-[#9ca3af]">Signal Quality</span>
                <span className="text-sm font-sans font-semibold text-[#e5e7eb]">92.3%</span>
              </div>
              <div className="w-full bg-[#0e1628] rounded-full h-1.5 border border-[#1f2a44]">
                <div className="bg-primary h-1.5 rounded-full" style={{ width: '92.3%' }}></div>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-sans text-[#9ca3af]">Data Completeness</span>
                <span className="text-sm font-sans font-semibold text-[#e5e7eb]">98.1%</span>
              </div>
              <div className="w-full bg-[#0e1628] rounded-full h-1.5 border border-[#1f2a44]">
                <div className="bg-success h-1.5 rounded-full" style={{ width: '98.1%' }}></div>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <Card title="Recent Signals" compact>
        <Table>
          <TableHeader>
            <TableHeaderCell>Symbol</TableHeaderCell>
            <TableHeaderCell>Signal</TableHeaderCell>
            <TableHeaderCell numeric>Price</TableHeaderCell>
            <TableHeaderCell numeric>Confidence</TableHeaderCell>
            <TableHeaderCell className="text-right">Time</TableHeaderCell>
          </TableHeader>
          <TableBody>
            <TableRow index={0}>
              <TableCell className="font-sans font-semibold">AAPL</TableCell>
              <TableCell>
                <span className="text-xs font-sans px-1.5 py-0.5 bg-success/10 text-success rounded uppercase">
                  BUY
                </span>
              </TableCell>
              <TableCell numeric>$175.23</TableCell>
              <TableCell numeric>87%</TableCell>
              <TableCell className="text-right text-[#9ca3af]">2h ago</TableCell>
            </TableRow>
            <TableRow index={1}>
              <TableCell className="font-sans font-semibold">MSFT</TableCell>
              <TableCell>
                <span className="text-xs font-sans px-1.5 py-0.5 bg-success/10 text-success rounded uppercase">
                  BUY
                </span>
              </TableCell>
              <TableCell numeric>$420.15</TableCell>
              <TableCell numeric>91%</TableCell>
              <TableCell className="text-right text-[#9ca3af]">4h ago</TableCell>
            </TableRow>
            <TableRow index={2}>
              <TableCell className="font-sans font-semibold">GOOGL</TableCell>
              <TableCell>
                <span className="text-xs font-sans px-1.5 py-0.5 bg-error/10 text-error rounded uppercase">
                  SELL
                </span>
              </TableCell>
              <TableCell numeric>$142.50</TableCell>
              <TableCell numeric>76%</TableCell>
              <TableCell className="text-right text-[#9ca3af]">6h ago</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
