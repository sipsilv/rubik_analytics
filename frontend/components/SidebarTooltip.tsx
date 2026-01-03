'use client'

import { ReactNode, useState, useRef, useEffect } from 'react'

interface TooltipProps {
  children: ReactNode
  text: string
  collapsed: boolean
}

export function SidebarTooltip({ children, text, collapsed }: TooltipProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [position, setPosition] = useState<'top' | 'bottom' | 'left' | 'right'>('right')
  const tooltipRef = useRef<HTMLDivElement>(null)
  const triggerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isHovered && collapsed && triggerRef.current) {
      const calculatePosition = () => {
        if (!triggerRef.current) return

        const triggerRect = triggerRef.current.getBoundingClientRect()
        const viewportWidth = window.innerWidth
        const viewportHeight = window.innerHeight
        const padding = 8
        const estimatedTooltipHeight = 32
        const estimatedTooltipWidth = 100

        const spaceTop = triggerRect.top
        const spaceBottom = viewportHeight - triggerRect.bottom
        const spaceLeft = triggerRect.left
        const spaceRight = viewportWidth - triggerRect.right

        // Calculate aspect ratio
        const aspectRatio = viewportWidth / viewportHeight
        const isWideScreen = aspectRatio > 1.5
        const isPortrait = aspectRatio < 1.0

        // Score each position
        const positions: Array<{ pos: 'top' | 'bottom' | 'left' | 'right'; score: number }> = []

        if (spaceTop >= estimatedTooltipHeight + padding) {
          positions.push({ pos: 'top', score: spaceTop + (isPortrait ? 50 : 0) })
        }
        if (spaceBottom >= estimatedTooltipHeight + padding) {
          positions.push({ pos: 'bottom', score: spaceBottom + (isPortrait ? 50 : 0) })
        }
        if (spaceRight >= estimatedTooltipWidth + padding) {
          positions.push({ pos: 'right', score: spaceRight + (isWideScreen ? 50 : 0) })
        }
        if (spaceLeft >= estimatedTooltipWidth + padding) {
          positions.push({ pos: 'left', score: spaceLeft + (isWideScreen ? 50 : 0) })
        }

        // Pick best position
        positions.sort((a, b) => b.score - a.score)
        const bestPosition = positions.length > 0 ? positions[0].pos : 'right'
        setPosition(bestPosition)
      }

      // Calculate position immediately
      calculatePosition()
    }
  }, [isHovered, collapsed])

  const getTooltipStyle = (): React.CSSProperties => {
    if (!triggerRef.current) {
      return { display: 'none' }
    }

    const triggerRect = triggerRef.current.getBoundingClientRect()
    const baseStyle: React.CSSProperties = {
      position: 'fixed',
      zIndex: 99999,
      opacity: 1,
    }

    switch (position) {
      case 'right':
        return {
          ...baseStyle,
          left: `${triggerRect.right + 8}px`,
          top: `${triggerRect.top + triggerRect.height / 2}px`,
          transform: 'translateY(-50%)',
        }
      case 'left':
        return {
          ...baseStyle,
          right: `${window.innerWidth - triggerRect.left + 8}px`,
          top: `${triggerRect.top + triggerRect.height / 2}px`,
          transform: 'translateY(-50%)',
        }
      case 'top':
        return {
          ...baseStyle,
          bottom: `${window.innerHeight - triggerRect.top + 8}px`,
          left: `${triggerRect.left + triggerRect.width / 2}px`,
          transform: 'translateX(-50%)',
        }
      case 'bottom':
        return {
          ...baseStyle,
          top: `${triggerRect.bottom + 8}px`,
          left: `${triggerRect.left + triggerRect.width / 2}px`,
          transform: 'translateX(-50%)',
        }
      default:
        return {
          ...baseStyle,
          left: `${triggerRect.right + 8}px`,
          top: `${triggerRect.top + triggerRect.height / 2}px`,
          transform: 'translateY(-50%)',
        }
    }
  }

  const getArrowStyle = (): React.CSSProperties => {
    const baseStyle: React.CSSProperties = {
      width: 0,
      height: 0,
      position: 'absolute',
    }

    switch (position) {
      case 'right':
        return {
          ...baseStyle,
          left: '-4px',
          top: '50%',
          transform: 'translateY(-50%)',
          borderRight: '4px solid #121b2f',
          borderTop: '4px solid transparent',
          borderBottom: '4px solid transparent',
        }
      case 'left':
        return {
          ...baseStyle,
          right: '-4px',
          top: '50%',
          transform: 'translateY(-50%)',
          borderLeft: '4px solid #121b2f',
          borderTop: '4px solid transparent',
          borderBottom: '4px solid transparent',
        }
      case 'top':
        return {
          ...baseStyle,
          bottom: '-4px',
          left: '50%',
          transform: 'translateX(-50%)',
          borderTop: '4px solid #121b2f',
          borderLeft: '4px solid transparent',
          borderRight: '4px solid transparent',
        }
      case 'bottom':
        return {
          ...baseStyle,
          top: '-4px',
          left: '50%',
          transform: 'translateX(-50%)',
          borderBottom: '4px solid #121b2f',
          borderLeft: '4px solid transparent',
          borderRight: '4px solid transparent',
        }
      default:
        return {
          ...baseStyle,
          left: '-4px',
          top: '50%',
          transform: 'translateY(-50%)',
          borderRight: '4px solid #121b2f',
          borderTop: '4px solid transparent',
          borderBottom: '4px solid transparent',
        }
    }
  }

  if (!text) return <>{children}</>

  return (
    <div 
      ref={triggerRef}
      className="relative w-full"
      onMouseEnter={() => {
        if (collapsed) {
          setIsHovered(true)
        }
      }}
      onMouseLeave={() => {
        setIsHovered(false)
      }}
    >
      {children}
      {collapsed && isHovered && (
        <div 
          ref={tooltipRef}
          className="px-2 py-1 bg-[#121b2f] border border-[#1f2a44] rounded-md text-[11px] font-sans font-normal text-[#e5e7eb] whitespace-nowrap shadow-xl pointer-events-none"
          style={getTooltipStyle()}
        >
          {text}
          <div style={getArrowStyle()} />
        </div>
      )}
    </div>
  )
}
