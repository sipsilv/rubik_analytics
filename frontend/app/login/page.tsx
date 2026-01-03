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
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showContactModal, setShowContactModal] = useState(false)

  useEffect(() => {
    // On login page mount, check if already authenticated
    // Only redirect if we have valid authenticated state
    if (isAuthenticated && user) {
      const token = Cookies.get('auth_token')
      if (token) {
        // User is already authenticated with valid token, redirect to dashboard
        router.push('/dashboard')
        return
      } else {
        // Token missing but user state exists - clear it
        setUser(null)
      }
    }
  }, [isAuthenticated, user, router, setUser])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      // Clear any existing auth state before login
      Cookies.remove('auth_token')
      Cookies.remove('user')
      setUser(null)
      
      const response = await authAPI.login(identifier, password)
      
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
      setError(errorMessage)
      
      // Clear any partial auth state on error
      Cookies.remove('auth_token')
      Cookies.remove('user')
      setUser(null)
      
      // If it's an inactive account error, provide more helpful message
      if (errorMessage.includes('inactive')) {
        console.warn('Account inactive error - this should not happen for Super User')
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
            <Input
              label="Email / Mobile / User ID"
              type="text"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              required
              autoFocus
              placeholder="Enter email, mobile number, or user ID"
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Enter password"
            />

            <ErrorMessage error={error} />

            <Button
              type="submit"
              size="sm"
              className="w-full"
              disabled={loading}
            >
              {loading ? 'Authenticating...' : 'Sign In'}
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
