'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { authAPI } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { getErrorMessage } from '@/lib/error-utils'

export default function ForgotPasswordPage() {
  const router = useRouter()
  const [step, setStep] = useState<'identifier' | 'otp' | 'success'>('identifier')
  const [identifier, setIdentifier] = useState('')
  const [otp, setOtp] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await authAPI.forgotPassword(identifier)
      setStep('otp')
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to send OTP'))
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    // Validate passwords match
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }

    if (newPassword.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }

    setLoading(true)

    try {
      // Call reset password API with OTP
      await authAPI.resetPassword(identifier, otp, newPassword)
      setStep('success')
    } catch (err: any) {
      setError(getErrorMessage(err, 'Failed to reset password'))
    } finally {
      setLoading(false)
    }
  }

  // Success state
  if (step === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm">
          <div className="bg-card rounded border border-border shadow-sm p-6 text-center">
            <div className="mb-4 text-2xl font-sans text-success">✓</div>
            <h1 className="text-2xl font-sans font-semibold text-text-primary mb-2 tracking-tight">
              Password Reset Successful
            </h1>
            <p className="text-xs font-sans text-text-secondary mb-4">
              Your password has been reset successfully. You can now login with your new password.
            </p>
            <Link href="/login" className="block">
              <Button variant="primary" size="sm" className="w-full">
                Go to Login
              </Button>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  // OTP and New Password step
  if (step === 'otp') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background px-4">
        <div className="w-full max-w-sm">
          <div className="bg-card rounded border border-border shadow-sm p-6">
            <div className="text-center mb-6">
              <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1 tracking-tight">
                Reset Password
              </h1>
              <p className="text-xs font-sans text-text-secondary">
                Enter the OTP sent to your Telegram and create a new password
              </p>
            </div>

            <form onSubmit={handleResetPassword} className="space-y-4">
              <Input
                label="OTP Code"
                type="text"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
                required
                autoFocus
                placeholder="Enter 6-digit OTP"
                maxLength={6}
              />

              <Input
                label="New Password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
                placeholder="Enter new password"
              />

              <Input
                label="Confirm Password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                placeholder="Confirm new password"
              />

              <ErrorMessage error={error} />

              <Button
                type="submit"
                size="sm"
                className="w-full"
                disabled={loading}
              >
                {loading ? 'Resetting...' : 'Reset Password'}
              </Button>
            </form>

            <div className="mt-4 text-center">
              <button
                onClick={() => setStep('identifier')}
                className="text-sm font-sans text-text-secondary hover:text-primary transition-colors duration-fast"
              >
                Back
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Initial identifier step
  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="bg-card rounded border border-border shadow-sm p-6">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-sans font-semibold text-text-primary mb-1 tracking-tight">
              Forgot Password
            </h1>
            <p className="text-xs font-sans text-text-secondary">
              Enter your email, mobile number, or user ID
            </p>
          </div>

          <form onSubmit={handleSendOTP} className="space-y-4">
            <Input
              label="Email / Mobile / User ID"
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              required
              autoFocus
              placeholder="e.g., user@example.com or 1234567890"
            />

            <ErrorMessage error={error} />

            <Button
              type="submit"
              size="sm"
              className="w-full"
              disabled={loading}
            >
              {loading ? 'Sending...' : 'Send OTP'}
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
