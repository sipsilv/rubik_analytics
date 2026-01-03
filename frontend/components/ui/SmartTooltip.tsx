'use client'

import { ReactNode, useState, useRef, useEffect } from 'react'

interface SmartTooltipProps {
  children: ReactNode
  text: string
  delay?: number
}

export function SmartTooltip({ children, text, delay = 200 }: SmartTooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [position, setPosition] = useState<'top' | 'bottom' | 'left' | 'right'>('top')
  const [tooltipStyle, setTooltipStyle] = useState<React.CSSProperties>({})
  const timeoutId = useRef<NodeJS.Timeout | null>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLDivElement>(null)

  const handleMouseEnter = () => {
    const id = setTimeout(() => {
      setIsVisible(true)
      calculatePosition()
    }, delay)
    timeoutId.current = id
  }

  const handleMouseLeave = () => {
    if (timeoutId.current) {
      clearTimeout(timeoutId.current)
      timeoutId.current = null
    }
    setIsVisible(false)
  }

  const calculatePosition = () => {
    if (!triggerRef.current || !tooltipRef.current) return

    const triggerRect = triggerRef.current.getBoundingClientRect()
    const tooltipRect = tooltipRef.current.getBoundingClientRect()
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const padding = 8

    const spaceTop = triggerRect.top
    const spaceBottom = viewportHeight - triggerRect.bottom
    const spaceLeft = triggerRect.left
    const spaceRight = viewportWidth - triggerRect.right

    const tooltipHeight = tooltipRect.height || 32
    const tooltipWidth = tooltipRect.width || 100

    // Calculate aspect ratio and determine screen type
    const aspectRatio = viewportWidth / viewportHeight
    const isWideScreen = aspectRatio > 1.5
    const isUltraWide = aspectRatio > 2.0
    const isPortrait = aspectRatio < 1.0

    // Calculate available space scores for each position
    const positions: Array<{ pos: 'top' | 'bottom' | 'left' | 'right'; score: number; space: number }> = []

    // Score each position based on available space and aspect ratio preference
    if (spaceTop >= tooltipHeight + padding) {
      const score = spaceTop + (isPortrait ? 50 : 0) // Prefer top on portrait screens
      positions.push({ pos: 'top', score, space: spaceTop })
    }
    if (spaceBottom >= tooltipHeight + padding) {
      const score = spaceBottom + (isPortrait ? 50 : 0) // Prefer bottom on portrait screens
      positions.push({ pos: 'bottom', score, space: spaceBottom })
    }
    if (spaceRight >= tooltipWidth + padding) {
      const score = spaceRight + (isWideScreen ? 50 : 0) + (isUltraWide ? 30 : 0) // Prefer right on wide screens
      positions.push({ pos: 'right', score, space: spaceRight })
    }
    if (spaceLeft >= tooltipWidth + padding) {
      const score = spaceLeft + (isWideScreen ? 50 : 0) + (isUltraWide ? 30 : 0) // Prefer left on wide screens
      positions.push({ pos: 'left', score, space: spaceLeft })
    }

    // Sort by score (highest first) and pick the best position
    positions.sort((a, b) => b.score - a.score)
    const bestPosition = positions.length > 0 ? positions[0].pos : 'top'
    
    let style: React.CSSProperties = {}

    // Calculate horizontal/vertical offset based on chosen position
    if (bestPosition === 'top' || bestPosition === 'bottom') {
      const tooltipCenterX = triggerRect.left + triggerRect.width / 2
      const tooltipHalfWidth = tooltipWidth / 2
      
      // Adjust horizontal position to prevent overflow
      if (tooltipCenterX + tooltipHalfWidth > viewportWidth - padding) {
        style.right = `${Math.max(padding, viewportWidth - triggerRect.right - padding)}px`
        style.left = 'auto'
        style.transform = 'none'
      } else if (tooltipCenterX - tooltipHalfWidth < padding) {
        style.left = `${Math.max(padding, triggerRect.left - padding)}px`
        style.transform = 'none'
      } else {
        style.left = '50%'
        style.transform = 'translateX(-50%)'
      }
    } else {
      // For left/right positions, adjust vertical position
      const tooltipCenterY = triggerRect.top + triggerRect.height / 2
      const tooltipHalfHeight = tooltipHeight / 2
      
      if (tooltipCenterY + tooltipHalfHeight > viewportHeight - padding) {
        style.bottom = `${Math.max(padding, viewportHeight - triggerRect.bottom - padding)}px`
        style.top = 'auto'
        style.transform = 'none'
      } else if (tooltipCenterY - tooltipHalfHeight < padding) {
        style.top = `${Math.max(padding, triggerRect.top - padding)}px`
        style.transform = 'none'
      } else {
        style.top = '50%'
        style.transform = 'translateY(-50%)'
      }
    }

    setPosition(bestPosition)
    setTooltipStyle(style)
  }

  useEffect(() => {
    if (isVisible) {
      // Recalculate position after tooltip is rendered
      setTimeout(() => {
        calculatePosition()
      }, 10)
    }
  }, [isVisible])

  const getPositionClasses = (pos: 'top' | 'bottom' | 'left' | 'right') => {
    const baseClasses = {
      top: 'bottom-full mb-2',
      bottom: 'top-full mt-2',
      left: 'right-full mr-2',
      right: 'left-full ml-2',
    }
    return baseClasses[pos]
  }

  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-4 border-t-[#121b2f] border-l-4 border-l-transparent border-r-4 border-r-transparent',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-4 border-b-[#121b2f] border-l-4 border-l-transparent border-r-4 border-r-transparent',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-4 border-l-[#121b2f] border-t-4 border-t-transparent border-b-4 border-b-transparent',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-4 border-r-[#121b2f] border-t-4 border-t-transparent border-b-4 border-b-transparent',
  }

  return (
    <div 
      ref={triggerRef}
      className="relative inline-flex group/tooltip"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {isVisible && (
        <div 
          ref={tooltipRef}
          className={`absolute ${getPositionClasses(position)} px-2 py-1 bg-[#121b2f] border border-[#1f2a44] rounded-md text-[11px] font-sans font-normal text-[#e5e7eb] whitespace-nowrap z-50 shadow-xl pointer-events-none transition-opacity duration-150`}
          style={{
            ...tooltipStyle,
            ...(position === 'top' || position === 'bottom' 
              ? (tooltipStyle.left === undefined && tooltipStyle.right === undefined
                  ? { left: '50%', transform: 'translateX(-50%)' }
                  : {}
                )
              : { top: '50%', transform: tooltipStyle.transform || 'translateY(-50%)' }
            )
          }}
        >
          {text}
          <div className={`absolute ${arrowClasses[position]} w-0 h-0`} />
        </div>
      )}
    </div>
  )
}
