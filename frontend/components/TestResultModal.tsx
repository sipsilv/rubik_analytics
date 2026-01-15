'use client'

import React from 'react'
import { SecondaryModal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { CheckCircle, XCircle } from 'lucide-react'

interface TestResultModalProps {
    isOpen: boolean
    onClose: () => void
    success: boolean
    message: string
}

export function TestResultModal({
    isOpen,
    onClose,
    success,
    message
}: TestResultModalProps) {
    return (
        <SecondaryModal
            isOpen={isOpen}
            onClose={onClose}
            title={success ? "Connection Successful" : "Connection Failed"}
            maxWidth="max-w-md"
        >
            <div className="flex flex-col gap-4">
                <div className={`flex items-start gap-3 p-4 border rounded-lg ${success
                        ? 'bg-success/10 border-success/20'
                        : 'bg-error/10 border-error/20'
                    }`}>
                    {success ? (
                        <CheckCircle className="w-5 h-5 text-success shrink-0 mt-0.5" />
                    ) : (
                        <XCircle className="w-5 h-5 text-error shrink-0 mt-0.5" />
                    )}
                    <div className="text-sm text-text-secondary">
                        <p className={`font-semibold mb-1 ${success ? 'text-success' : 'text-error'
                            }`}>
                            {success ? 'Success' : 'Failed'}
                        </p>
                        {message}
                    </div>
                </div>

                <div className="flex justify-end gap-3 mt-2">
                    <Button
                        onClick={onClose}
                    >
                        Close
                    </Button>
                </div>
            </div>
        </SecondaryModal>
    )
}
