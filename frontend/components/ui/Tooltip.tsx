'use client'

import { ReactNode, useState } from 'react'

interface TooltipProps {
  children: ReactNode
  text: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

export function Tooltip({ children, text, position = 'top', delay = 200 }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false)
  const [timeoutId, setTimeoutId] = useState<NodeJS.Timeout | null>(null)

  const handleMouseEnter = () => {
    const id = setTimeout(() => {
      setIsVisible(true)
    }, delay)
    setTimeoutId(id)
  }

  const handleMouseLeave = () => {
    if (timeoutId) {
      clearTimeout(timeoutId)
      setTimeoutId(null)
    }
    setIsVisible(false)
  }

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  }

  const arrowClasses = {
    top: 'top-full left-1/2 -translate-x-1/2 border-t-4 border-t-[#121b2f] border-l-4 border-l-transparent border-r-4 border-r-transparent',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-4 border-b-[#121b2f] border-l-4 border-l-transparent border-r-4 border-r-transparent',
    left: 'left-full top-1/2 -translate-y-1/2 border-l-4 border-l-[#121b2f] border-t-4 border-t-transparent border-b-4 border-b-transparent',
    right: 'right-full top-1/2 -translate-y-1/2 border-r-4 border-r-[#121b2f] border-t-4 border-t-transparent border-b-4 border-b-transparent',
  }

  return (
    <div 
      className="relative inline-flex group/tooltip"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {children}
      {isVisible && (
        <div 
          className={`absolute ${positionClasses[position]} px-2 py-1 bg-[#121b2f] border border-[#1f2a44] rounded-md text-[11px] font-sans font-normal text-[#e5e7eb] whitespace-nowrap z-50 shadow-xl pointer-events-none transition-opacity duration-150`}
        >
          {text}
          <div className={`absolute ${arrowClasses[position]} w-0 h-0`} />
        </div>
      )}
    </div>
  )
}

