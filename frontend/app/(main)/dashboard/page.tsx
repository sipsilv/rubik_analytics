'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'

export default function DashboardPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
            Dashboard
          </h1>
          <p className="text-xs font-sans text-text-secondary">
            System overview and analytics metrics
          </p>
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        <Card compact>
          <div className="space-y-1">
            <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">Total Symbols</p>
            <p className="text-xl font-sans font-semibold text-text-primary">1,234</p>
            <p className="text-[10px] font-sans text-success">+12% from last month</p>
          </div>
        </Card>

        <Card compact>
          <div className="space-y-1">
            <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">Active Signals</p>
            <p className="text-xl font-sans font-semibold text-text-primary">89</p>
            <p className="text-[10px] font-sans text-success">+5 new today</p>
          </div>
        </Card>

        <Card compact>
          <div className="space-y-1">
            <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">ML Models</p>
            <p className="text-xl font-sans font-semibold text-text-primary">12</p>
            <p className="text-[10px] font-sans text-text-secondary">All active</p>
          </div>
        </Card>

        <Card compact>
          <div className="space-y-1">
            <p className="text-xs font-sans text-text-secondary uppercase tracking-wider">Accuracy</p>
            <p className="text-xl font-sans font-semibold text-text-primary">87.5%</p>
            <p className="text-[10px] font-sans text-success">+2.3% improvement</p>
          </div>
        </Card>
      </div>

      {/* Data Tables */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Recent Activity" compact>
          <Table>
            <TableHeader>
              <TableHeaderCell>Event</TableHeaderCell>
              <TableHeaderCell className="text-right">Time</TableHeaderCell>
            </TableHeader>
            <TableBody>
              <TableRow index={0}>
                <TableCell>New signal generated</TableCell>
                <TableCell numeric className="text-text-secondary">2h ago</TableCell>
              </TableRow>
              <TableRow index={1}>
                <TableCell>AAPL - Buy signal</TableCell>
                <TableCell numeric className="text-text-secondary">2h ago</TableCell>
              </TableRow>
              <TableRow index={2}>
                <TableCell>Model updated</TableCell>
                <TableCell numeric className="text-text-secondary">5h ago</TableCell>
              </TableRow>
              <TableRow index={3}>
                <TableCell>RSI Indicator v2.1</TableCell>
                <TableCell numeric className="text-text-secondary">5h ago</TableCell>
              </TableRow>
              <TableRow index={4}>
                <TableCell>Data sync completed</TableCell>
                <TableCell numeric className="text-text-secondary">1d ago</TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </Card>

        <Card title="System Status" compact>
          <div className="space-y-2">
            <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
              <span className="text-xs font-sans text-text-secondary">Backend API</span>
              <span className="text-xs font-sans text-success">ONLINE</span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
              <span className="text-xs font-sans text-text-secondary">Database</span>
              <span className="text-xs font-sans text-success">CONNECTED</span>
            </div>
            <div className="flex items-center justify-between py-1.5 border-b border-border-subtle">
              <span className="text-xs font-sans text-text-secondary">Analytics Engine</span>
              <span className="text-xs font-sans text-success">ACTIVE</span>
            </div>
            <div className="flex items-center justify-between py-1.5">
              <span className="text-xs font-sans text-text-secondary">Last Sync</span>
              <span className="text-xs font-sans text-text-secondary">12:34:56</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
