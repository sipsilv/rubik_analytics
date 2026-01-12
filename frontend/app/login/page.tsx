'use client'

import { useState, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore, useThemeStore } from '@/lib/store'
import { authAPI } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { ErrorMessage } from '@/components/ui/ErrorMessage'
import { ContactAdminModal } from '@/components/ContactAdminModal'
import { getErrorMessage } from '@/lib/error-utils'
import Cookies from 'js-cookie'
import Link from 'next/link'

export default function LoginPage() {
  const router = useRouter()
  const { user, setUser, isAuthenticated } = useAuthStore()
  const { initializeTheme } = useThemeStore()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [showOtp, setShowOtp] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showContactModal, setShowContactModal] = useState(false)

  // ... (useEffect remains same) ...

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Only clear cookie state if not in OTP flow
      if (!showOtp) {
        Cookies.remove('auth_token')
        Cookies.remove('user')
        setUser(null)
      }

      // Pass OTP if we have it
      const response = await authAPI.login(identifier, password, showOtp ? otp : undefined)

      // ... (success handling remains same) ...

      // Set new token and user with proper cookie settings
      Cookies.set('auth_token', response.access_token, {
        expires: 1,
        sameSite: 'lax',
        secure: typeof window !== 'undefined' && window.location.protocol === 'https:'
      })

      // Set user state - this will also set the user cookie
      setUser(response.user)

      // Initialize theme from user preference (defaults to dark for first-time users)
      initializeTheme(response.user.theme_preference || 'dark')

      // Wait a moment for state to propagate, then navigate
      setTimeout(() => {
        router.replace('/dashboard')
      }, 50)
    } catch (err: any) {
      const errorMessage = getErrorMessage(err, 'Invalid identifier or password')
      console.error('Login error:', err)

      // CHECK FOR OTP REQUIREMENT
      if (errorMessage.includes('OTP code sent') || (err.response?.status === 401 && err.response?.data?.detail?.includes('OTP'))) {
        setShowOtp(true)
        setError('Please enter the verification code sent to your Telegram.')
        // Don't clear fields - user needs to just enter OTP
      } else {
        setError(errorMessage)
        setShowOtp(false)
        setOtp('')

        // Clear any partial auth state on actual error
        Cookies.remove('auth_token')
        Cookies.remove('user')
        setUser(null)

        // If it's an inactive account error, provide more helpful message
        if (errorMessage.includes('inactive')) {
          console.warn('Account inactive error - this should not happen for Super User')
        }
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-sm">
        <div className="bg-card rounded border border-border shadow-sm p-6">
          <div className="text-center mb-6">
            <h1 className="text-3xl font-sans font-semibold text-text-primary mb-2 tracking-tight">
              RUBIK ANALYTICS
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {!showOtp ? (
              <>
                <Input
                  label="Email / Mobile / User ID"
                  type="text"
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  required
                  autoFocus
                  placeholder="Enter email, mobile number, or user ID"
                  disabled={loading}
                />

                <Input
                  label="Password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="Enter password"
                  disabled={loading}
                />
              </>
            ) : (
              <div className="animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="mb-4 p-3 bg-primary/10 border border-primary/20 rounded-md text-sm text-primary">
                  <p className="font-semibold mb-1">2-Step Verification</p>
                  <p>A code has been sent to your connected Telegram account.</p>
                </div>

                <Input
                  label="Telegram Verification Code"
                  type="text"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value)}
                  required
                  autoFocus
                  placeholder="Enter 6-digit code"
                  disabled={loading}
                  maxLength={6}
                  className="text-center text-lg tracking-widest"
                />

                <div className="text-right mt-1">
                  <button
                    type="button"
                    onClick={() => {
                      setShowOtp(false)
                      setOtp('')
                      setError('')
                    }}
                    className="text-xs text-text-secondary hover:text-primary underline"
                  >
                    Back to Login
                  </button>
                </div>
              </div>
            )}

            <ErrorMessage error={error} />

            <Button
              type="submit"
              size="sm"
              className="w-full"
              disabled={loading}
            >
              {loading ? 'Authenticating...' : (showOtp ? 'Verify & Login' : 'Sign In')}
            </Button>
          </form>

          <div className="mt-4 space-y-2 text-center">
            <Link
              href="/forgot-password"
              className="block text-sm font-sans text-text-secondary hover:text-primary transition-colors duration-fast"
            >
              Forgot password?
            </Link>
            <button
              onClick={() => setShowContactModal(true)}
              className="text-sm font-sans text-text-secondary hover:text-primary transition-colors duration-fast"
            >
              Contact admin for login requests
            </button>
          </div>
        </div>

        <div className="mt-4 text-center">
          <p className="text-sm font-sans text-text-muted">
            v1.0.0
          </p>
        </div>
      </div>

      <ContactAdminModal
        isOpen={showContactModal}
        onClose={() => setShowContactModal(false)}
      />
    </div>
  )
}
