import { ButtonHTMLAttributes, ReactNode, useState } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  children,
  onClick,
  ...props
}: ButtonProps) {
  const [isAnimating, setIsAnimating] = useState(false)

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    // Trigger animation on every click - small flash effect
    setIsAnimating(true)
    setTimeout(() => setIsAnimating(false), 300) // Reset after animation completes (matches 0.3s animation)
    
    // Call original onClick if provided
    if (onClick) {
      onClick(e)
    }
  }

  const baseClasses =
    'inline-flex items-center justify-center font-sans font-medium transition-all duration-200 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed whitespace-nowrap rounded-lg'

  // Theme-aware button variants using CSS variables and theme tokens
  const variantClasses = {
    primary:
      'bg-primary dark:bg-[#3b82f6] text-white dark:text-white border border-primary dark:border-[#3b82f6] hover:bg-[#1d4ed8] dark:hover:bg-[#4a90f5] hover:border-[#1d4ed8] dark:hover:border-[#4a90f5] focus:ring-primary/30 dark:focus:ring-[#3b82f6]/30 shadow-sm dark:shadow-[0_1px_2px_0_rgba(59,130,246,0.15)] disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:border-gray-400 dark:disabled:border-gray-600',
    secondary:
      'bg-[#f3f4f6] dark:bg-[#121b2f] border border-[#d1d5db] dark:border-[#1f2a44] text-text-primary dark:text-text-primary hover:bg-[#e5e7eb] dark:hover:bg-[#182447] hover:border-[#d1d5db] dark:hover:border-[#1f2a44] focus:ring-border/30 dark:focus:ring-[#1f2a44]/30 disabled:bg-gray-200 dark:disabled:bg-[#0a1020] disabled:border-gray-300 dark:disabled:border-[#0f1620] disabled:text-gray-400 dark:disabled:text-[#6b7280]',
    ghost:
      'bg-transparent border-transparent text-text-secondary dark:text-text-secondary hover:text-text-primary dark:hover:text-text-primary hover:bg-[#f3f4f6] dark:hover:bg-[#182447]/50 focus:ring-border/30 dark:focus:ring-[#1f2a44]/30 disabled:text-gray-400 dark:disabled:text-[#6b7280] disabled:hover:bg-transparent',
    danger:
      'bg-error dark:bg-error border border-error dark:border-error text-white dark:text-white hover:bg-[#dc2626] dark:hover:bg-[#dc2626] hover:border-[#dc2626] dark:hover:border-[#dc2626] focus:ring-error/30 dark:focus:ring-error/30 shadow-sm disabled:bg-gray-400 dark:disabled:bg-gray-600 disabled:border-gray-400 dark:disabled:border-gray-600',
  }

  const sizeClasses = {
    sm: 'px-3 py-1.5 text-sm gap-1.5',      // Compact for filters, table actions
    md: 'px-4 py-2 text-base gap-2',         // Default for most actions
    lg: 'px-6 py-2.5 text-lg gap-2.5',      // Primary CTAs (use sparingly)
  }

  // Check if w-full is in className and adjust base classes accordingly
  const isFullWidth = className.includes('w-full')
  const adjustedBaseClasses = isFullWidth 
    ? baseClasses.replace('inline-flex', 'flex')
    : baseClasses

  return (
    <button
      className={`${adjustedBaseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${isAnimating ? 'button-click-animation' : ''} ${className}`}
      onClick={handleClick}
      {...props}
    >
      {children}
    </button>
  )
}
