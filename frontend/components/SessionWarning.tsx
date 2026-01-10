'use client'

import { useState, useEffect } from 'react'
import { useSessionStore } from '@/lib/store'

interface SessionWarningProps {
  collapsed: boolean
}

export function SessionWarning({ collapsed }: SessionWarningProps) {
  const { sessionExpiry, idleTimeout, lastActivity, updateActivity } =
    useSessionStore()
  const [timeRemaining, setTimeRemaining] = useState<number | null>(null)
  const [warningType, setWarningType] = useState<'idle' | 'session' | null>(
    null
  )

  useEffect(() => {
    const checkSession = () => {
      if (!sessionExpiry && !idleTimeout) return

      const now = Date.now()
      const idleDeadline = lastActivity + (idleTimeout || 0) * 60 * 1000
      const sessionDeadline = sessionExpiry || 0

      // Check if within last 10 minutes of expiry
      const tenMinutes = 10 * 60 * 1000
      const timeUntilIdle = idleDeadline - now
      const timeUntilSession = sessionDeadline - now

      if (timeUntilSession > 0 && timeUntilSession <= tenMinutes) {
        setWarningType('session')
        setTimeRemaining(Math.floor(timeUntilSession / 1000))
      } else if (timeUntilIdle > 0 && timeUntilIdle <= tenMinutes) {
        setWarningType('idle')
        setTimeRemaining(Math.floor(timeUntilIdle / 1000))
      } else {
        setWarningType(null)
        setTimeRemaining(null)
      }
    }

    // Check immediately on mount
    checkSession()

    // Update timer every second for real-time countdown
    const interval = setInterval(() => {
      checkSession()
    }, 1000)

    // Track user activity
    const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart']
    const handleActivity = () => updateActivity()

    events.forEach((event) => {
      document.addEventListener(event, handleActivity, { passive: true })
    })

    return () => {
      clearInterval(interval)
      events.forEach((event) => {
        document.removeEventListener(event, handleActivity)
      })
    }
  }, [sessionExpiry, idleTimeout, lastActivity, updateActivity])

  if (!warningType || timeRemaining === null) return null

  const minutes = Math.floor(timeRemaining / 60)
  const seconds = timeRemaining % 60
  const formattedTime = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`

  const isWarning = warningType === 'idle'
  const isError = warningType === 'session'

  return (
    <div
      className={`border rounded-sm px-3 py-2 mx-2 mb-2 flex-shrink-0 ${
        isError
          ? 'bg-error/10 border-error text-error'
          : 'bg-warning/10 border-warning text-warning'
      } ${collapsed ? 'text-center' : ''}`}
    >
      {!collapsed && (
        <div className="text-[10px] font-sans mb-0.5 uppercase tracking-wider">
          {isError ? 'Session' : 'Idle'}
        </div>
      )}
      <div className="text-xs font-sans font-semibold">{formattedTime}</div>
    </div>
  )
}
