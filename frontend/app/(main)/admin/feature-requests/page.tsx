'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'

export default function FeatureRequestsPage() {
  const router = useRouter()
  
  useEffect(() => {
    router.replace('/admin/requests-feedback')
  }, [router])

  return null
}
