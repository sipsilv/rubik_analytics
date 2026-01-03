import { InputHTMLAttributes } from 'react'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string | any
}

export function Input({ label, error, className = '', ...props }: InputProps) {
  // Safely convert error to string
  const errorMessage = error 
    ? (typeof error === 'string' 
        ? error 
        : (error?.message || error?.msg || JSON.stringify(error)))
    : null

  return (
    <div className="w-full">
      {label && (
        <label className="block text-sm font-sans font-medium text-text-secondary mb-1.5">
          {label}
        </label>
      )}
      <input
        className={`w-full px-3 py-2 border border-[#1f2a44] rounded-lg bg-[#121b2f] text-[#e5e7eb] font-sans text-base placeholder:text-[#6b7280] focus:outline-none focus:ring-2 focus:ring-[#3b82f6]/30 focus:border-[#3b82f6] disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200 ${className} ${
          errorMessage ? 'border-error focus:ring-error/30 focus:border-error' : ''
        }`}
        {...props}
      />
      {errorMessage && (
        <p className="mt-1 text-sm font-sans text-error">{errorMessage}</p>
      )}
    </div>
  )
}
