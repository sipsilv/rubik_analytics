import { useState, useEffect, useRef } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import { Table, TableHeader, TableHeaderCell, TableBody, TableRow, TableCell } from '@/components/ui/Table'
import { RefreshCw, Search } from 'lucide-react'
import { telegramChannelsAPI } from '@/lib/api'
import { Input } from '@/components/ui/Input'
import { getErrorMessage } from '@/lib/error-utils'

interface AddChannelsModalProps {
    isOpen: boolean
    onClose: () => void
    connectionId: number
    onAdded: () => void
}

type SearchMode = 'MY_CHATS' | 'GLOBAL_SEARCH'

export function AddChannelsModal({ isOpen, onClose, connectionId, onAdded }: AddChannelsModalProps) {
    const [channels, setChannels] = useState<any[]>([])
    const [loading, setLoading] = useState(false)
    const [selectedIds, setSelectedIds] = useState<number[]>([])
    const [error, setError] = useState<string | null>(null)

    // Search State
    const [mode, setMode] = useState<SearchMode>('MY_CHATS')
    const [searchQuery, setSearchQuery] = useState('')

    // Reset state when opened
    useEffect(() => {
        if (isOpen && connectionId) {
            setMode('MY_CHATS')
            setSearchQuery('')
            discoverChannels()
            setSelectedIds([])
            setError(null)
        }
    }, [isOpen, connectionId])

    // Track active mode to prevent race conditions
    const modeRef = useRef(mode)
    modeRef.current = mode

    const discoverChannels = async () => {
        setLoading(true)
        setError(null)
        try {
            const data = await telegramChannelsAPI.discoverChannels(connectionId)
            if (modeRef.current === 'MY_CHATS') {
                setChannels(data)
            }
        } catch (e: any) {
            console.error(e)
            if (modeRef.current === 'MY_CHATS') {
                setError(getErrorMessage(e, 'Discovery failed'))
                setChannels([])
            }
        } finally {
            if (modeRef.current === 'MY_CHATS') {
                setLoading(false)
            }
        }
    }

    const handleSearch = async () => {
        if (!searchQuery.trim()) return

        setLoading(true)
        setError(null)
        try {
            const data = await telegramChannelsAPI.searchChannels(connectionId, searchQuery)
            if (modeRef.current === 'GLOBAL_SEARCH') {
                setChannels(data)
            }
        } catch (e: any) {
            console.error(e)
            if (modeRef.current === 'GLOBAL_SEARCH') {
                setError(getErrorMessage(e, 'Search failed'))
                setChannels([])
            }
        } finally {
            if (modeRef.current === 'GLOBAL_SEARCH') {
                setLoading(false)
            }
        }
    }


    // Effect to switch modes
    useEffect(() => {
        if (!isOpen) return

        setChannels([]) // Clear current list on mode switch
        setError(null)

        if (mode === 'MY_CHATS') {
            discoverChannels()
        } else {
            // For global search, wait for user input
        }
    }, [mode, isOpen])

    const handleSelect = (id: number) => {
        if (selectedIds.includes(id)) {
            setSelectedIds(selectedIds.filter(x => x !== id))
        } else {
            setSelectedIds([...selectedIds, id])
        }
    }

    const handleRegister = async () => {
        try {
            const selectedChannels = channels.filter(c => selectedIds.includes(c.id))
            await telegramChannelsAPI.registerChannels(connectionId, selectedChannels)

            onAdded()
            onClose()
        } catch (e) {
            console.error(e)
            setError('Failed to register channels')
        }
    }

    return (
        <Modal
            isOpen={isOpen}
            onClose={onClose}
            title="Discover Telegram Channels"
            maxWidth="max-w-4xl"
            scrollable={false}
        >

            <div className="flex flex-col gap-4 mb-4 shrink-0">
                <div className="flex border-b border-border">
                    <button
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${mode === 'MY_CHATS' ? 'border-primary text-primary' : 'border-transparent text-text-secondary hover:text-text-primary'}`}
                        onClick={() => setMode('MY_CHATS')}
                    >
                        My Chats
                    </button>
                    <button
                        className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${mode === 'GLOBAL_SEARCH' ? 'border-primary text-primary' : 'border-transparent text-text-secondary hover:text-text-primary'}`}
                        onClick={() => setMode('GLOBAL_SEARCH')}
                    >
                        Global Search
                    </button>
                </div>

                {mode === 'GLOBAL_SEARCH' && (
                    <div className="flex gap-2 items-end">
                        <Input
                            placeholder="Search public channels (e.g. 'Stock Market')"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                        />
                        <Button onClick={handleSearch} disabled={loading || !searchQuery.trim()}>
                            <Search className="w-4 h-4" />
                        </Button>
                    </div>
                )}
            </div>

            <div className="flex-1 overflow-auto h-[50vh] border rounded-lg border-border/50 min-h-0 relative">
                {loading ? (
                    <div className="flex flex-col items-center justify-center h-64 text-text-secondary">
                        <RefreshCw className="w-8 h-8 animate-spin mb-2" />
                        <p>{mode === 'MY_CHATS' ? 'Loading chats...' : 'Searching global directory...'}</p>
                    </div>
                ) : error ? (
                    <div className="flex flex-col items-center justify-center h-64 text-error">
                        <p className="font-semibold">{mode === 'MY_CHATS' ? 'Discovery Failed' : 'Search Failed'}</p>
                        <p className="text-sm mt-1">{error}</p>
                        <Button variant="secondary" size="sm" onClick={mode === 'MY_CHATS' ? discoverChannels : handleSearch} className="mt-4">
                            Retry
                        </Button>
                    </div>
                ) : (
                    <table className="w-full border-collapse">
                        <TableHeader>
                            <TableHeaderCell className="w-12">Select</TableHeaderCell>
                            <TableHeaderCell>Name</TableHeaderCell>
                            <TableHeaderCell>Type</TableHeaderCell>
                            <TableHeaderCell>Participants</TableHeaderCell>
                            <TableHeaderCell>Status</TableHeaderCell>
                        </TableHeader>
                        <TableBody>
                            {(() => {
                                const visibleChannels = channels.filter(c => c.status !== 'ALREADY_ADDED')

                                if (visibleChannels.length === 0) {
                                    return (
                                        <TableRow>
                                            <td colSpan={5} className="text-center py-8 text-text-secondary">
                                                {channels.length > 0
                                                    ? "All discovered channels are already added."
                                                    : (mode === 'MY_CHATS'
                                                        ? "No channels or groups found in your account."
                                                        : "No results found. Try a different query.")
                                                }
                                            </td>
                                        </TableRow>
                                    )
                                }

                                return visibleChannels.map(channel => (
                                    <TableRow key={channel.id}>
                                        <TableCell>
                                            <Checkbox
                                                checked={selectedIds.includes(channel.id)}
                                                onCheckedChange={() => handleSelect(channel.id)}
                                            />
                                        </TableCell>
                                        <TableCell className="font-medium">
                                            {channel.title}
                                            {channel.username && <div className="text-xs text-text-secondary">@{channel.username}</div>}
                                        </TableCell>
                                        <TableCell className="capitalize">{channel.type}</TableCell>
                                        <TableCell>{channel.participants_count?.toLocaleString() || '-'}</TableCell>
                                        <TableCell>
                                            <span className="text-xs text-success font-mono">New</span>
                                        </TableCell>
                                    </TableRow>
                                ))
                            })()}
                        </TableBody>
                    </table>
                )}
            </div>

            <div className="mt-4 border-t pt-4 shrink-0">
                <div className="flex justify-between w-full items-center">
                    <div className="text-sm text-text-secondary">
                        {selectedIds.length} channel(s) selected
                    </div>
                    <div className="flex gap-2">
                        <Button variant="secondary" onClick={onClose}>Cancel</Button>
                        <Button onClick={handleRegister} disabled={selectedIds.length === 0}>
                            Add Selected
                        </Button>
                    </div>
                </div>
            </div>
        </Modal >
    )
}
