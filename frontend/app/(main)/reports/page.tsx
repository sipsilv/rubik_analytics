'use client'

import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'

export default function ReportsPage() {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
            Reports
          </h1>
          <p className="text-xs font-sans text-text-secondary">
            Generate and manage analytics reports
          </p>
        </div>
        <Button size="sm">Generate Report</Button>
      </div>

      <Card title="Recent Reports" compact>
        <Table>
          <TableHeader>
            <TableHeaderCell>Report Name</TableHeaderCell>
            <TableHeaderCell>Type</TableHeaderCell>
            <TableHeaderCell>Generated</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
            <TableHeaderCell className="text-right">Actions</TableHeaderCell>
          </TableHeader>
          <TableBody>
            <TableRow index={0}>
              <TableCell className="font-medium">Market Analysis Q1 2024</TableCell>
              <TableCell>
                <span className="text-[10px] font-sans uppercase text-text-secondary">Analytics</span>
              </TableCell>
              <TableCell className="text-text-secondary">2024-01-15 10:30</TableCell>
              <TableCell>
                <span className="text-[10px] font-sans px-1.5 py-0.5 bg-success/10 text-success rounded uppercase">
                  Complete
                </span>
              </TableCell>
              <TableCell>
                <div className="flex gap-1 justify-end">
                  <Button variant="ghost" size="sm">View</Button>
                  <Button variant="ghost" size="sm">Download</Button>
                </div>
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell className="font-medium">Signal Performance Report</TableCell>
              <TableCell>
                <span className="text-[10px] font-sans uppercase text-text-secondary">Performance</span>
              </TableCell>
              <TableCell className="text-text-secondary">2024-01-14 14:22</TableCell>
              <TableCell>
                <span className="text-[10px] font-sans px-1.5 py-0.5 bg-success/10 text-success rounded uppercase">
                  Complete
                </span>
              </TableCell>
              <TableCell>
                <div className="flex gap-1 justify-end">
                  <Button variant="ghost" size="sm">View</Button>
                  <Button variant="ghost" size="sm">Download</Button>
                </div>
              </TableCell>
            </TableRow>
            <TableRow index={2}>
              <TableCell className="font-medium">Daily Summary Report</TableCell>
              <TableCell>
                <span className="text-[10px] font-sans uppercase text-text-secondary">Summary</span>
              </TableCell>
              <TableCell className="text-text-secondary">2024-01-15 09:00</TableCell>
              <TableCell>
                <span className="text-[10px] font-sans px-1.5 py-0.5 bg-warning/10 text-warning rounded uppercase">
                  Processing
                </span>
              </TableCell>
              <TableCell>
                <div className="flex gap-1 justify-end">
                  <Button variant="ghost" size="sm" disabled>View</Button>
                </div>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Card>
    </div>
  )
}
