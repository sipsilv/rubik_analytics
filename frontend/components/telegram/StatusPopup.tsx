'use client'

import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { Activity, CheckCircle, AlertCircle, Clock } from 'lucide-react'

interface StatusPopupProps {
    isOpen: boolean
    onClose: () => void
    channel: any
}

export function StatusPopup({ isOpen, onClose, channel }: StatusPopupProps) {
    if (!channel) return null

    const stats = [
        { label: 'Messages Fetched', value: channel.today_count || 0, icon: Activity, color: 'text-primary' },
        { label: 'Messages Parsed', value: 0, icon: CheckCircle, color: 'text-success' },
        { label: 'Pending AI', value: 0, icon: Clock, color: 'text-warning' },
        { label: 'Failed', value: 0, icon: AlertCircle, color: 'text-error' },
    ]

    return (
        <Modal isOpen={isOpen} onClose={onClose} title="Channel Status" maxWidth="max-w-sm">

            <div className="mt-2 mb-4">
                <h3 className="font-medium text-lg text-text-primary">{channel.title}</h3>
                <p className="text-sm text-text-secondary capitalize">{channel.type} • {channel.status}</p>
            </div>

            <div className="space-y-3">
                {stats.map((stat, i) => {
                    const Icon = stat.icon
                    return (
                        <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-secondary/10 border border-border">
                            <div className="flex items-center gap-3">
                                <Icon className={`w-5 h-5 ${stat.color}`} />
                                <span className="text-sm font-medium text-text-secondary">{stat.label}</span>
                            </div>
                            <span className="font-bold font-mono text-text-primary">{stat.value}</span>
                        </div>
                    )
                })}
            </div>

            <div className="mt-4 flex justify-end">
                <Button variant="secondary" onClick={onClose} className="w-full">Close</Button>
            </div>
        </Modal>
    )
}
