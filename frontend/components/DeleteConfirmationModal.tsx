'use client'

import React from 'react'
import { SecondaryModal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { AlertTriangle } from 'lucide-react'

interface DeleteConfirmationModalProps {
    isOpen: boolean
    onClose: () => void
    onConfirm: () => void
    connectionName?: string
    isLoading?: boolean
}

export function DeleteConfirmationModal({
    isOpen,
    onClose,
    onConfirm,
    connectionName,
    isLoading = false
}: DeleteConfirmationModalProps) {
    return (
        <SecondaryModal
            isOpen={isOpen}
            onClose={onClose}
            title="Delete Connection"
            maxWidth="max-w-md"
        >
            <div className="flex flex-col gap-4">
                <div className="flex items-start gap-3 p-4 bg-warning/10 border border-warning/20 rounded-lg">
                    <AlertTriangle className="w-5 h-5 text-warning shrink-0 mt-0.5" />
                    <div className="text-sm text-text-secondary">
                        <p className="font-semibold text-text-primary mb-1">Warning</p>
                        Are you sure you want to delete <span className="text-text-primary font-medium">{connectionName || 'this connection'}</span>? This action cannot be undone.
                    </div>
                </div>

                <div className="flex justify-end gap-3 mt-2">
                    <Button
                        variant="ghost"
                        onClick={onClose}
                        disabled={isLoading}
                    >
                        Cancel
                    </Button>
                    <Button
                        variant="danger"
                        onClick={onConfirm}
                        disabled={isLoading}
                    >
                        {isLoading ? 'Deleting...' : 'Delete Connection'}
                    </Button>
                </div>
            </div>
        </SecondaryModal>
    )
}
