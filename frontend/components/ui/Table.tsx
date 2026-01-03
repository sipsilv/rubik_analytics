import { ReactNode } from 'react'

interface TableProps {
  children: ReactNode
  className?: string
}

export function Table({ children, className = '' }: TableProps) {
  return (
    <div className="overflow-x-auto bg-[#121b2f]">
      <table
        className={`w-full border-collapse bg-[#121b2f] ${className}`}
      >
        {children}
      </table>
    </div>
  )
}

export function TableHeader({ children, className = '' }: TableProps) {
  return (
    <thead className="bg-[#f1f5f9] dark:bg-[#121b2f] sticky top-0 z-20 border-b border-border dark:border-[#1f2a44]">
      <tr>{children}</tr>
    </thead>
  )
}

export function TableHeaderCell({
  children,
  className = '',
  numeric = false,
}: TableProps & { numeric?: boolean }) {
  return (
    <th
      className={`px-3 py-2.5 ${numeric ? 'text-right' : 'text-left'} font-sans font-semibold text-xs text-text-secondary dark:text-[#9ca3af] bg-[#f1f5f9] dark:bg-[#121b2f] ${className}`}
    >
      {children}
    </th>
  )
}

export function TableBody({ children, className = '' }: TableProps) {
  return <tbody className={className}>{children}</tbody>
}

export function TableRow({
  children,
  className = '',
  hover = true,
  index,
}: TableProps & { hover?: boolean; index?: number }) {
  return (
    <tr
      className={`${
        index !== undefined && index % 2 === 0 
          ? 'bg-[#fafafa] dark:bg-[#0e1628]/30' 
                  : 'bg-[#121b2f]'
      } ${
        hover ? 'hover:bg-[#f1f5f9] dark:hover:bg-[#182447]/40 transition-colors duration-200' : ''
      } ${className}`}
    >
      {children}
    </tr>
  )
}

export function TableCell({ children, className = '', numeric = false, colSpan }: TableProps & { numeric?: boolean; colSpan?: number }) {
  return (
    <td 
      colSpan={colSpan}
      className={`px-3 py-2 text-sm font-sans text-text-primary dark:text-[#e5e7eb] ${numeric ? 'text-right' : 'text-left'} ${className}`}
    >
      {children}
    </td>
  )
}
