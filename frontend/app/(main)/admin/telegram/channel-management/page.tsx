'use client'

import { useState, useEffect, Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { adminAPI, telegramChannelsAPI } from '@/lib/api'
import { Card } from '@/components/ui/Card'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { Button } from '@/components/ui/Button'
import { RefreshButton } from '@/components/ui/RefreshButton'
import { ArrowLeft, Plus, Trash2, StopCircle, RefreshCw, BarChart2 } from 'lucide-react'
import { Switch } from '@/components/ui/Switch'
import { Modal } from '@/components/ui/Modal'
import { AddChannelsModal } from '@/components/telegram/AddChannelsModal'
import { StatusPopup } from '@/components/telegram/StatusPopup'

// For now using `any` for the API calls in this file to avoid TS errors until api.ts is updated.
// const api = adminAPI as any

export default function ChannelManagementPage() {
    return (
        <Suspense fallback={<div>Loading...</div>}>
            <ChannelManagementContent />
        </Suspense>
    )
}

function ChannelManagementContent() {
    const router = useRouter()
    const searchParams = useSearchParams()
    const connectionId = searchParams.get('connectionId')
    const connectionName = searchParams.get('name')

    const [channels, setChannels] = useState<any[]>([])
    const [loading, setLoading] = useState(true)
    const [isAddOpen, setIsAddOpen] = useState(false)
    const [selectedChannel, setSelectedChannel] = useState<any>(null)
    const [isStatusOpen, setIsStatusOpen] = useState(false)
    const [channelToDelete, setChannelToDelete] = useState<any>(null)

    useEffect(() => {
        if (!connectionId) {
            router.push('/admin/connections')
            return
        }
        loadChannels()
    }, [connectionId])

    const loadChannels = async () => {
        if (!connectionId) return
        try {
            setLoading(true)
            const data = await telegramChannelsAPI.getChannels(parseInt(connectionId))
            setChannels(data)
        } catch (e) {
            console.error('Error loading channels:', e)
        } finally {
            setLoading(false)
        }
    }

    const handleToggle = async (channel: any) => {
        try {
            // Optimistic update
            const updatedChannels = channels.map(c =>
                c.id === channel.id ? { ...c, is_enabled: !c.is_enabled } : c
            )
            setChannels(updatedChannels)

            await telegramChannelsAPI.toggleChannel(channel.id, !channel.is_enabled)
        } catch (e) {
            console.error('Error toggling channel:', e)
            loadChannels() // Revert
        }
    }

    const handleDeleteClick = (channel: any) => {
        setChannelToDelete(channel)
    }

    const confirmDelete = async () => {
        if (!channelToDelete) return
        try {
            await telegramChannelsAPI.deleteChannel(channelToDelete.id)
            setChannels(channels.filter(c => c.id !== channelToDelete.id))
            setChannelToDelete(null)
        } catch (e) {
            console.error('Error deleting channel:', e)
            alert('Failed to delete channel')
        }
    }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-3">
                <button
                    onClick={() => router.back()}
                    className="text-text-secondary hover:text-text-primary transition-colors"
                >
                    <ArrowLeft className="w-5 h-5" />
                </button>
                <div>
                    <h1 className="text-2xl font-sans font-semibold text-text-primary dark:text-[#e5e7eb] mb-1">
                        Channel Management
                    </h1>
                    <p className="text-xs font-sans text-text-secondary dark:text-[#9ca3af]">
                        Manage channels for {connectionName || 'Telegram Connection'}
                    </p>
                </div>
            </div>

            <div className="flex items-center justify-between">
                <div></div>
                <div className="flex gap-2">
                    <RefreshButton
                        variant="secondary"
                        onClick={loadChannels}
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
                        Add Channels
                    </Button>
                </div>
            </div>

            <Card>
                <Table>
                    <TableHeader>
                        <TableHeaderCell>Channel Name</TableHeaderCell>
                        <TableHeaderCell>Type</TableHeaderCell>
                        <TableHeaderCell>Members</TableHeaderCell>
                        <TableHeaderCell>Enabled</TableHeaderCell>
                        <TableHeaderCell>Status</TableHeaderCell>
                        <TableHeaderCell className="text-right">Actions</TableHeaderCell>
                    </TableHeader>
                    <TableBody>
                        {loading ? (
                            <TableRow>
                                <td colSpan={6} className="px-3 py-12 text-center text-text-secondary">
                                    Loading channels...
                                </td>
                            </TableRow>
                        ) : channels.length === 0 ? (
                            <TableRow>
                                <td colSpan={6} className="px-3 py-12 text-center text-text-secondary">
                                    No channels added yet. Click "Add Channels" to discover.
                                </td>
                            </TableRow>
                        ) : (
                            channels.map((channel) => (
                                <TableRow key={channel.id}>
                                    <TableCell className="font-medium text-text-primary">
                                        {channel.title}
                                        {channel.username && <span className="text-xs text-text-secondary ml-2">@{channel.username}</span>}
                                    </TableCell>
                                    <TableCell>
                                        <span className="capitalize text-sm">{channel.type}</span>
                                    </TableCell>
                                    <TableCell>{channel.member_count?.toLocaleString() || '-'}</TableCell>
                                    <TableCell>
                                        <Switch
                                            checked={channel.is_enabled}
                                            onCheckedChange={() => handleToggle(channel)}
                                        />
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex flex-col items-start gap-1">
                                            <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${channel.status === 'ACTIVE' ? 'bg-success/10 text-success' :
                                                    channel.status === 'ERROR' ? 'bg-error/10 text-error' :
                                                        'bg-secondary text-text-secondary'
                                                }`}>
                                                {channel.status}
                                            </span>
                                            {/* Show today count if active or generally available */}
                                            {channel.today_count !== undefined && (
                                                <span className="text-[10px] text-text-secondary pl-1">
                                                    Today: {channel.today_count}
                                                </span>
                                            )}
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <div className="flex items-center justify-end gap-2">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                onClick={() => {
                                                    setSelectedChannel(channel)
                                                    setIsStatusOpen(true)
                                                }}
                                                title={`View Status (Today: ${channel.today_count || 0})`}
                                            >
                                                <BarChart2 className="w-4 h-4" />
                                            </Button>
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="text-error hover:text-error hover:bg-error/10"
                                                onClick={() => handleDeleteClick(channel)}
                                                title="Delete Channel"
                                            >
                                                <Trash2 className="w-4 h-4" />
                                            </Button>
                                        </div>
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </Card>

            <AddChannelsModal
                isOpen={isAddOpen}
                onClose={() => setIsAddOpen(false)}
                connectionId={connectionId ? parseInt(connectionId) : 0}
                onAdded={loadChannels}
            />

            <StatusPopup
                isOpen={isStatusOpen}
                onClose={() => setIsStatusOpen(false)}
                channel={selectedChannel}
            />

            <Modal
                isOpen={!!channelToDelete}
                onClose={() => setChannelToDelete(null)}
                title="Delete Channel"
            >
                <div>
                    <p className="text-text-secondary mb-6">
                        Are you sure you want to delete <strong>{channelToDelete?.title}</strong>? This action cannot be undone.
                    </p>
                    <div className="flex justify-end gap-3">
                        <Button
                            variant="secondary"
                            onClick={() => setChannelToDelete(null)}
                        >
                            Cancel
                        </Button>
                        <Button
                            variant="danger"
                            onClick={confirmDelete}
                        >
                            Delete
                        </Button>
                    </div>
                </div>
            </Modal>

        </div>
    )
}


