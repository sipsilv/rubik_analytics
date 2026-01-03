import { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
  compact?: boolean
  onClick?: () => void
}

export function Card({ children, className = '', title, compact = false, onClick }: CardProps) {
  return (
    <div
      className={`bg-card rounded-lg border border-border dark:border-[#1f2a44] ${className}`}
      onClick={onClick}
    >
      {title && (
        <div className={`px-4 border-b border-border-subtle ${compact ? 'py-2' : 'py-3'}`}>
          <h3 className="text-sm font-sans font-semibold text-text-primary dark:text-[#e5e7eb]">
            {title}
          </h3>
        </div>
      )}
      <div className={compact ? 'p-3' : 'p-4'}>{children}</div>
    </div>
  )
}
