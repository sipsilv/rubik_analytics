import { getErrorMessage } from '@/lib/error-utils'

interface ErrorMessageProps {
  error?: string | any
  className?: string
}

/**
 * Safe error message component that always renders a string
 * Prevents "Objects are not valid as a React child" errors
 */
export function ErrorMessage({ error, className = '' }: ErrorMessageProps) {
  if (!error) return null

  // Always convert to string using getErrorMessage
  const errorText = typeof error === 'string' ? error : getErrorMessage(error, 'An error occurred')

  return (
    <div className={`bg-error/10 border border-error rounded-sm p-2.5 ${className}`}>
      <p className="text-sm font-sans text-error">{errorText}</p>
    </div>
  )
}
