'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { adminAPI } from '@/lib/api'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { ArrowLeft, Settings, Trash2, Search, Plus, Eye, Edit, PlayCircle } from 'lucide-react'
import { Switch } from '@/components/ui/Switch'
import { SmartTooltip } from '@/components/ui/SmartTooltip'
import { ConnectionModal } from '@/components/ConnectionModal'
import { ViewConnectionModal } from '@/components/ViewConnectionModal'
import { DeleteConfirmationModal } from '@/components/DeleteConfirmationModal'
import { AIConfigModal } from '@/components/AIConfigModal'
import { TestResultModal } from '@/components/TestResultModal'

function ConnectionListContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const categoryParam = searchParams.get('category')

    const [connections, setConnections] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    // Format date helper
    const formatDateTime = (dateString: string | null | undefined): string => {
        if (!dateString) return '-'
        try {
            // Check if it's already a clean string or needs parsing
            const date = new Date(dateString)
            if (isNaN(date.getTime())) return dateString || '-'

            return new Intl.DateTimeFormat('en-IN', {
                day: '2-digit',
                month: 'short',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            }).format(date)
        } catch (e) {
            return dateString || '-'
        }
    }

    // Modals
    const [selectedConn, setSelectedConn] = useState<any>(null)
    const [isAddOpen, setIsAddOpen] = useState(false)
    const [isEditOpen, setIsEditOpen] = useState(false)
    const [isAIConfigOpen, setIsAIConfigOpen] = useState(false)
    const [isViewOpen, setIsViewOpen] = useState(false)

    // Delete Confirmation
    const [deleteModalOpen, setDeleteModalOpen] = useState(false)
    const [connToDelete, setConnToDelete] = useState<any>(null)
    const [isDeleting, setIsDeleting] = useState(false)

    // Test Result Modal
    const [testResultOpen, setTestResultOpen] = useState(false)
    const [testResult, setTestResult] = useState<{ success: boolean, message: string } | null>(null)

    // Filtered connections
    const filteredConnections = connections.filter(c => {
        if (!categoryParam) return true // Show all if no category
        if (categoryParam === 'SOCIAL') {
            return ['SOCIAL', 'TELEGRAM_BOT', 'TELEGRAM_USER'].includes(c.connection_type)
        }
        return c.connection_type === categoryParam
    })

    const loadConnections = async () => {
        try {
            setLoading(true)
            const data = await adminAPI.getConnections()
            setConnections(data || [])
        } catch (e) {
            console.error('Error loading connections:', e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadConnections()
    }, [])

    const handleDeleteClick = (conn: any) => {
        setConnToDelete(conn)
        setDeleteModalOpen(true)
    }


    const handleConfirmDelete = async () => {
        if (!connToDelete) return

        try {
            setIsDeleting(true)
            await adminAPI.deleteConnection(connToDelete.id)
            setDeleteModalOpen(false)
            setConnToDelete(null)
            loadConnections()
        } catch (e) {
            console.error('Error deleting connection:', e)
            alert('Failed to delete connection')
        } finally {
            setIsDeleting(false)
        }
    }


    const handleDelete = async (id: string) => {
        // Deprecated - kept for reference if needed, but replaced by handleDeleteClick flow
    }

    const handleToggle = async (id: string) => {
        try {
            await adminAPI.toggleConnection(id)
            loadConnections()
        } catch (e) {
            console.error('Error toggling connection:', e)
            alert('Failed to toggle connection status')
        }
    }

    const handleTestConnection = async (id: string) => {
        try {
            const result = await adminAPI.testConnection(id)
            setTestResult({
                success: result.success,
                message: result.message || (result.success ? 'Connection successful!' : 'Connection failed')
            })
            setTestResultOpen(true)
            loadConnections()
        } catch (e: any) {
            console.error('Error testing connection:', e)
            setTestResult({
                success: false,
                message: e.message || 'Failed to test connection'
            })
            setTestResultOpen(true)
        }
    }

    const handleSettingsClick = (conn: any) => {
        if (conn.status !== 'CONNECTED' && conn.status !== 'HEALTHY') {
            // Basic alert for now, can be improved to a proper modal if needed or reuse existing warning pattern
            alert("Connection is not healthy. Please resolve connection issues first.")
            return
        }
        router.push(`/admin/telegram/channel-management?connectionId=${conn.id}&name=${encodeURIComponent(conn.name)}`)
    }

    const getCategoryLabel = (key: string | null) => {
        if (!key) return 'All Connections'
        const labels: Record<string, string> = {
            'INTERNAL': 'Database Connections',
            'BROKER': 'Broker APIs',
            'NEWS': 'News Channels',
            'SOCIAL': 'Telegram',
            'MARKET_DATA': 'Market Data',
            'AI_ML': 'AI / ML Models',
            'TRUEDATA': 'TrueData'
        }
        return labels[key] || key
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <button
                    onClick={() => router.push('/admin/connections')}
                    className="text-text-secondary hover:text-text-primary transition-colors"
                >
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                    <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
                        {getCategoryLabel(categoryParam)}
                    </h1>
                    <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
                        Manage {categoryParam ? categoryParam.toLowerCase().replace('_', ' ') : 'all'} connections
                    </p>
                </div>
            </div>

            <div className="flex items-center justify-between">
                <div></div>
                <div className="flex gap-2">
                    <RefreshButton
                        variant="secondary"
                        onClick={loadConnections}
                        size="sm"
                        disabled={loading}
                    >
                        Refresh
                    </RefreshButton>
                    <Button
                        onClick={() => setIsAddOpen(true)}
                        size="sm"
                    >
                        <Plus className="w-4 h-4 mr-1.5" />
                        Add Connection
                    </Button>
                </div>
            </div>

            <Card>
                <Table>
                    <TableHeader>
                        <TableHeaderCell>Name</TableHeaderCell>
                        <TableHeaderCell>Provider</TableHeaderCell>
                        <TableHeaderCell>Type</TableHeaderCell>
                        <TableHeaderCell>Enabled</TableHeaderCell>
                        <TableHeaderCell>Status</TableHeaderCell>
                        <TableHeaderCell>Health</TableHeaderCell>
                        <TableHeaderCell className="text-right">Actions</TableHeaderCell>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <td colSpan={7} className="px-3 py-12 text-center text-text-secondary">
                                    Loading connections...
                                </td>
                            </TableRow>
                        ) : filteredConnections.length === 0 ? (
                            <TableRow>
                                <td colSpan={7} className="px-3 py-12 text-center text-text-secondary">
                                    No connections found in this category.
                                </td>
                            </TableRow>
                        ) : (
                            filteredConnections.map((conn) => (
                                <TableRow key={conn.id}>
                                    <TableCell className="font-medium text-text-primary">
                                        {conn.name}
                                    </TableCell>
                                    <TableCell>{conn.provider}</TableCell>
                                    <TableCell>
                                        <span className="text-xs px-2 py-1 bg-secondary/10 rounded-full font-mono">
                                            {conn.connection_type}
                                        </span>
                                    </TableCell>
                                    <TableCell>
                                        <div onClick={(e) => e.stopPropagation()}>
                                            <Switch
                                                checked={conn.is_enabled}
                                                onCheckedChange={() => handleToggle(conn.id)}
                                            />
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex flex-col gap-1 items-start">
                                            <span className={`text-xs px-2 py-1 rounded-full font-bold ${conn.status === 'CONNECTED' ? 'bg-success/10 text-success' :
                                                conn.status === 'ERROR' ? 'bg-error/10 text-error' :
                                                    'bg-warning/10 text-warning'
                                                }`}>
                                                {conn.status}
                                            </span>
                                            {conn.connection_type === 'AI_ML' && conn.details?.is_active && (
                                                <span className="text-[10px] px-2 py-0.5 rounded-full font-bold bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                                    ACTIVE MODEL
                                                </span>
                                            )}
                                        </div>
                                    </TableCell>
                                    <TableCell>
                                        <span className={`text-xs ${conn.health === 'HEALTHY' ? 'text-success' :
                                            conn.health === 'DOWN' ? 'text-error' :
                                                'text-warning'
                                            }`}>
                                            {conn.health || '-'}
                                        </span>
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex justify-end gap-1">
                                            <SmartTooltip text="View Details">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => {
                                                        setSelectedConn(conn)
                                                        setIsViewOpen(true)
                                                    }}
                                                    className="p-1.5"
                                                >
                                                    <Eye className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                                                </Button>
                                            </SmartTooltip>

                                            {conn.connection_type === 'TELEGRAM_USER' && (
                                                <SmartTooltip text="Channel Settings">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => handleSettingsClick(conn)}
                                                        className="p-1.5"
                                                    >
                                                        <Settings className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                                                    </Button>
                                                </SmartTooltip>
                                            )}

                                            {/* AI Test Button */}
                                            {conn.connection_type === 'AI_ML' && (
                                                <SmartTooltip text="Test Connection">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => handleTestConnection(conn.id)}
                                                        className="p-1.5 text-green-400 hover:text-green-300 hover:bg-green-400/10"
                                                    >
                                                        <PlayCircle className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                                                    </Button>
                                                </SmartTooltip>
                                            )}


                                            <SmartTooltip text="Edit">

                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => {
                                                        setSelectedConn(conn)
                                                        setIsEditOpen(true)
                                                    }}
                                                    className="p-1.5"
                                                >
                                                    <Edit className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                                                </Button>
                                            </SmartTooltip>
                                            <SmartTooltip text="Delete">
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => handleDeleteClick(conn)}
                                                    className="p-1.5 text-error hover:text-error hover:bg-error/10"
                                                >
                                                    <Trash2 className="w-4 h-4 btn-icon-hover icon-button icon-button-bounce" />
                                                </Button>
                                            </SmartTooltip>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </Card>


            <AIConfigModal
                isOpen={isAIConfigOpen}
                onClose={() => { setIsAIConfigOpen(false); setSelectedConn(null) }}
                connection={selectedConn}
                onUpdate={loadConnections}
            />

            <ConnectionModal
                isOpen={isAddOpen}
                onClose={() => setIsAddOpen(false)}
                onUpdate={loadConnections}
                category={categoryParam || undefined}
            />

            <ConnectionModal
                isOpen={isEditOpen}
                onClose={() => { setIsEditOpen(false); setSelectedConn(null) }}
                connection={selectedConn}
                onUpdate={loadConnections}
            />

            <ViewConnectionModal
                isOpen={isViewOpen}
                onClose={() => { setIsViewOpen(false); setSelectedConn(null) }}
                connection={selectedConn}
            />

            <DeleteConfirmationModal
                isOpen={deleteModalOpen}
                onClose={() => { if (!isDeleting) setDeleteModalOpen(false) }}
                onConfirm={handleConfirmDelete}
                connectionName={connToDelete?.name}
                isLoading={isDeleting}
            />

            {/* Test Result Modal */}
            {testResult && (
                <TestResultModal
                    isOpen={testResultOpen}
                    onClose={() => setTestResultOpen(false)}
                    success={testResult.success}
                    message={testResult.message}
                />
            )}
        </div>
    )
}

export default function ConnectionListPage() {
    return (
        <Suspense fallback={<div className="p-6 text-center text-text-secondary">Loading connections...</div>}>
            <ConnectionListContent />
        </Suspense>
    )
}
