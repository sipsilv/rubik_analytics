'use client'

import { useState, useRef } from 'react'
import { RefreshCw } from 'lucide-react'
import { Button } from './Button'

interface RefreshButtonProps {
  onClick: () => Promise<void> | void
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  className?: string
  children?: React.ReactNode
}

export function RefreshButton({ 
  onClick, 
  disabled = false, 
  size = 'sm',
  variant = 'secondary',
  className = '',
  children 
}: RefreshButtonProps) {
  const [isRefreshing, setIsRefreshing] = useState(false)
  const startTimeRef = useRef<number | null>(null)
  const timeoutRef = useRef<NodeJS.Timeout | null>(null)

  const handleClick = async () => {
    // Prevent multiple clicks while refreshing
    if (isRefreshing) return
    
    setIsRefreshing(true)
    startTimeRef.current = Date.now()
    
    try {
      // Execute the refresh action (handle both async and sync functions)
      const result = onClick()
      if (result && typeof result.then === 'function') {
        await result
      }
      
      // Calculate elapsed time
      const elapsed = Date.now() - (startTimeRef.current || 0)
      const remaining = Math.max(0, 4000 - elapsed) // Minimum 4 seconds
      
      // Wait for remaining time if needed
      if (remaining > 0) {
        await new Promise(resolve => {
          timeoutRef.current = setTimeout(resolve, remaining)
        })
      }
    } catch (error) {
      // On error, still wait for minimum 4 seconds
      const elapsed = Date.now() - (startTimeRef.current || 0)
      const remaining = Math.max(0, 4000 - elapsed)
      
      if (remaining > 0) {
        await new Promise(resolve => {
          timeoutRef.current = setTimeout(resolve, remaining)
        })
      }
      
      // Re-throw error so parent can handle it
      throw error
    } finally {
      // Clean up timeout if still active
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
      
      setIsRefreshing(false)
      startTimeRef.current = null
    }
  }

  return (
    <Button
      variant={variant}
      size={size}
      onClick={handleClick}
      disabled={disabled || isRefreshing}
      className={className}
    >
      <RefreshCw className={`w-4 h-4 mr-1.5 ${isRefreshing ? 'animate-spin' : ''}`} />
      {children || 'Refresh'}
    </Button>
  )
}

