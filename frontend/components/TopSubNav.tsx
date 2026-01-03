'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useNavigationStore } from '@/lib/store'

export function TopSubNav() {
  const pathname = usePathname()
  const { subItems } = useNavigationStore()

  // Don't render if no sub-items
  if (!subItems || subItems.length === 0) {
    return null
  }

  return (
    <div className="w-full bg-[#0e1628] border-b border-[#1f2a44] overflow-x-auto overflow-y-hidden scrollbar-hide">
      <div className="flex items-center gap-2 px-4 py-2.5 min-w-max">
        {subItems.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`px-4 py-1.5 rounded-lg text-sm font-sans font-medium whitespace-nowrap transition-all duration-200 active:scale-[0.98] focus:outline-none ${
                isActive
                  ? 'bg-primary dark:bg-[#3b82f6] text-white shadow-sm dark:shadow-[0_1px_2px_0_rgba(59,130,246,0.15)]'
                  : 'bg-[#f3f4f6] dark:bg-[#121b2f] text-text-secondary hover:bg-[#e5e7eb] dark:hover:bg-[#182447] hover:text-text-primary'
              }`}
            >
              {item.name}
            </Link>
          )
        })}
      </div>
    </div>
  )
}

