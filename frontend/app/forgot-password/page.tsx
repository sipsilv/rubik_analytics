'use client'

import { useState } from 'react'
import Link from 'next/link'
import { authAPI } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { getErrorMessage } from '@/lib/error-utils'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await authAPI.forgotPassword(email)
      setSuccess(true)
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to send reset email'))
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm">
          <div className="bg-card rounded border border-border shadow-sm p-6 text-center">
            <div className="mb-4 text-2xl font-sans text-success">✓</div>
            <h1 className="text-2xl font-sans font-semibold text-text-primary mb-2 tracking-tight">
              Check your email
            </h1>
            <p className="text-xs font-sans text-text-secondary mb-4">
              We've sent password reset instructions to {email}
            </p>
            <Link href="/login" className="block">
              <Button variant="primary" size="sm" className="w-full">
                Back to Login
              </Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="bg-card rounded border border-border shadow-sm p-6">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1 tracking-tight">
              Forgot Password
            </h1>
            <p className="text-xs font-sans text-text-secondary">
              Enter your email to receive reset instructions
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              placeholder="Enter your email"
            />

            <ErrorMessage error={error} />

            <Button
              type="submit"
              size="sm"
              className="w-full"
              disabled={loading}
            >
              {loading ? 'Sending...' : 'Send Reset Link'}
            </Button>
          </form>

          <div className="mt-4 text-center">
            <Link
              href="/login"
              className="text-sm font-sans text-text-secondary hover:text-primary transition-colors duration-fast"
            >
              Back to Login
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}
