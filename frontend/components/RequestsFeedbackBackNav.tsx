'use client'

import { useRouter } from 'next/navigation'
import { ArrowLeft } from 'lucide-react'

export function RequestsFeedbackBackNav() {
  const router = useRouter()

  return (
    <button
      onClick={() => router.push('/admin/requests-feedback')}
      className="text-xs text-text-secondary hover:text-text-primary transition-colors flex items-center gap-1 mb-2"
    >
      <ArrowLeft className="w-3 h-3" />
      Back to Request & Feedback
    </button>
  )
}

