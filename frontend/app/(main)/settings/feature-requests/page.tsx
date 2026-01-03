'use client'

import { useState, useEffect } from 'react'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { userAPI } from '@/lib/api'
import Link from 'next/link'

interface FeatureRequest {
  id: number
  user_id: number
  user_name: string
  description: string
  context: any
  status: string
  ai_analysis: any
  admin_note: string | null
  created_at: string
  updated_at: string | null
}

export default function MyFeatureRequestsPage() {
  const [requests, setRequests] = useState<FeatureRequest[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRequest, setSelectedRequest] = useState<FeatureRequest | null>(null)

  useEffect(() => {
    loadRequests()
  }, [])

  const loadRequests = async () => {
    setLoading(true)
    try {
      const data = await userAPI.getMyFeatureRequests()
      setRequests(data)
    } catch (error) {
      console.error('Failed to load feature requests:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'approved':
        return 'text-success'
      case 'rejected':
        return 'text-error'
      case 'implemented':
        return 'text-primary'
      case 'in_review':
        return 'text-warning'
      default:
        return 'text-text-secondary'
    }
  }

  const getComplexityColor = (complexity?: string) => {
    switch (complexity) {
      case 'Low':
        return 'text-success'
      case 'Medium':
        return 'text-warning'
      case 'High':
        return 'text-error'
      default:
        return 'text-text-secondary'
    }
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1">
          My Feature Requests
        </h1>
        <p className="text-xs font-sans text-text-secondary">
          Track the status of your feature requests
        </p>
      </div>

      {loading ? (
        <Card compact>
          <div className="text-center py-8 text-text-secondary">Loading...</div>
        </Card>
      ) : requests.length === 0 ? (
        <Card compact>
          <div className="text-center py-8">
            <p className="text-text-secondary mb-4">You haven't submitted any feature requests yet.</p>
            <Link href="/settings">
              <Button size="sm">Request a Feature</Button>
            </Link>
          </div>
        </Card>
      ) : (
        <Card compact>
          <Table>
            <TableHeader>
              <TableHeaderCell>Description</TableHeaderCell>
              <TableHeaderCell>Category</TableHeaderCell>
              <TableHeaderCell>Complexity</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Submitted</TableHeaderCell>
              <TableHeaderCell className="text-right">Actions</TableHeaderCell>
            </TableHeader>
            <TableBody>
              {requests.map((request, index) => (
                <TableRow key={request.id} index={index}>
                  <TableCell className="max-w-xs">
                    <div className="truncate text-text-secondary" title={request.description}>
                      {request.description.substring(0, 60)}...
                    </div>
                  </TableCell>
                  <TableCell className="text-text-secondary">
                    {request.ai_analysis?.category || 'Analyzing...'}
                  </TableCell>
                  <TableCell>
                    <span className={getComplexityColor(request.ai_analysis?.complexity)}>
                      {request.ai_analysis?.complexity || 'Analyzing...'}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className={`font-medium ${getStatusColor(request.status)}`}>
                      {request.status.replace('_', ' ').toUpperCase()}
                    </span>
                  </TableCell>
                  <TableCell className="font-sans text-xs text-text-secondary">
                    {new Date(request.created_at).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1 justify-end">
                      <Button
                        size="sm"
                        onClick={() => setSelectedRequest(request)}
                      >
                        View
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      {/* Detail Modal */}
      {selectedRequest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 dark:bg-black/70" onClick={() => setSelectedRequest(null)}>
          <div 
            className="bg-card dark:bg-card border border-border rounded-lg shadow-lg w-full max-w-3xl max-h-[90vh] overflow-y-auto m-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-sans font-semibold text-text-primary">
                  Feature Request Details
                </h2>
                <button
                  onClick={() => setSelectedRequest(null)}
                  className="text-text-secondary hover:text-text-primary transition-colors"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Status</label>
                  <p className={`text-sm font-sans font-semibold ${getStatusColor(selectedRequest.status)}`}>
                    {selectedRequest.status.replace('_', ' ').toUpperCase()}
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Description</label>
                  <p className="text-sm font-sans text-text-primary whitespace-pre-wrap">{selectedRequest.description}</p>
                </div>

                {selectedRequest.context && (
                  <div>
                    <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Context</label>
                    <div className="text-sm font-sans text-text-secondary space-y-1">
                      {selectedRequest.context.page && <div>Page: {selectedRequest.context.page}</div>}
                      {selectedRequest.context.module && <div>Module: {selectedRequest.context.module}</div>}
                      {selectedRequest.context.issue_type && <div>Type: {selectedRequest.context.issue_type}</div>}
                    </div>
                  </div>
                )}

                {selectedRequest.ai_analysis ? (
                  <div className="border-t border-border pt-4">
                    <h3 className="text-sm font-sans font-semibold text-text-primary mb-3">AI Analysis</h3>
                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Summary</label>
                        <p className="text-sm font-sans text-text-primary">{selectedRequest.ai_analysis.summary}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Category</label>
                          <p className="text-sm font-sans text-text-primary">{selectedRequest.ai_analysis.category}</p>
                        </div>
                        <div>
                          <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Complexity</label>
                          <p className={`text-sm font-sans font-medium ${getComplexityColor(selectedRequest.ai_analysis.complexity)}`}>
                            {selectedRequest.ai_analysis.complexity}
                          </p>
                        </div>
                      </div>
                      {selectedRequest.ai_analysis.impacted_modules && selectedRequest.ai_analysis.impacted_modules.length > 0 && (
                        <div>
                          <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Impacted Modules</label>
                          <ul className="list-disc list-inside text-sm font-sans text-text-primary">
                            {selectedRequest.ai_analysis.impacted_modules.map((module: string, idx: number) => (
                              <li key={idx}>{module}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {selectedRequest.ai_analysis.suggested_steps && selectedRequest.ai_analysis.suggested_steps.length > 0 && (
                        <div>
                          <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Suggested Implementation Steps</label>
                          <ol className="list-decimal list-inside text-sm font-sans text-text-primary space-y-1">
                            {selectedRequest.ai_analysis.suggested_steps.map((step: string, idx: number) => (
                              <li key={idx}>{step}</li>
                            ))}
                          </ol>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="border-t border-border pt-4">
                    <div className="text-center py-4">
                      <p className="text-sm font-sans text-text-secondary">AI analysis is being processed...</p>
                    </div>
                  </div>
                )}

                {selectedRequest.admin_note && (
                  <div className="border-t border-border pt-4">
                    <label className="block text-xs font-sans font-medium text-text-secondary mb-1">Admin Note</label>
                    <p className="text-sm font-sans text-text-primary whitespace-pre-wrap">{selectedRequest.admin_note}</p>
                  </div>
                )}

                <div className="flex gap-2 justify-end pt-4 border-t border-border">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setSelectedRequest(null)}
                  >
                    Close
                  </Button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
