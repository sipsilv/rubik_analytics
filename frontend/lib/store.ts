import { create } from 'zustand'
import Cookies from 'js-cookie'

interface User {
  id: number | string
  user_id?: string  // Unique immutable user ID from backend
  username: string
  name?: string
  email: string
  mobile?: string
  role: 'user' | 'admin' | 'super_admin'
  is_active: boolean
  account_status?: 'ACTIVE' | 'INACTIVE' | 'SUSPENDED' | 'DEACTIVATED'
  theme_preference?: string
  created_at?: string
  updated_at?: string
  last_seen?: string
  last_active_at?: string
  is_online?: boolean
}

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  logout: () => void
}

const AUTH_STORAGE_KEY = 'rubik_auth_sync'

export const useAuthStore = create<AuthState>((set, get) => {
  // Initialize from cookies if available
  let initialUser: User | null = null
  let initialAuth = false
  
  if (typeof window !== 'undefined') {
    try {
      const userStr = Cookies.get('user')
      const token = Cookies.get('auth_token')
      if (userStr && token) {
        initialUser = JSON.parse(userStr)
        initialAuth = true
      }
    } catch (e) {
      // Clear invalid cookies
      Cookies.remove('user')
      Cookies.remove('auth_token')
    }

    // Listen for storage events from other tabs to sync auth state
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === AUTH_STORAGE_KEY && e.newValue !== null) {
        try {
          const authData = JSON.parse(e.newValue)
          const { user, isAuthenticated } = authData
          
          // Only update if the state actually changed
          const currentState = get()
          if (currentState.isAuthenticated !== isAuthenticated || 
              JSON.stringify(currentState.user) !== JSON.stringify(user)) {
            set({ user, isAuthenticated })
            
            // Sync cookies if needed (should already be in sync, but ensure consistency)
            if (isAuthenticated && user) {
              Cookies.set('user', JSON.stringify(user), { 
                expires: 1, 
                sameSite: 'lax',
                secure: window.location.protocol === 'https:'
              })
            } else {
              Cookies.remove('user')
              Cookies.remove('auth_token')
            }
          }
        } catch (error) {
          console.error('Error syncing auth state from storage:', error)
        }
      } else if (e.key === AUTH_STORAGE_KEY && e.newValue === null) {
        // Auth was cleared in another tab
        const currentState = get()
        if (currentState.isAuthenticated) {
          Cookies.remove('auth_token')
          Cookies.remove('user')
          set({ user: null, isAuthenticated: false })
        }
      }
    }

    window.addEventListener('storage', handleStorageChange)
  }
  
  return {
    user: initialUser,
    isAuthenticated: initialAuth,
    setUser: (user) => {
      if (user) {
        Cookies.set('user', JSON.stringify(user), { 
          expires: 1, 
          sameSite: 'lax',
          secure: typeof window !== 'undefined' && window.location.protocol === 'https:'
        })
        set({ user, isAuthenticated: true })
        
        // Sync to localStorage to notify other tabs
        if (typeof window !== 'undefined') {
          try {
            localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify({ 
              user, 
              isAuthenticated: true 
            }))
          } catch (error) {
            console.error('Error syncing auth state to localStorage:', error)
          }
        }
      } else {
        Cookies.remove('user')
        set({ user: null, isAuthenticated: false })
        
        // Sync to localStorage to notify other tabs
        if (typeof window !== 'undefined') {
          try {
            localStorage.removeItem(AUTH_STORAGE_KEY)
          } catch (error) {
            console.error('Error clearing auth state from localStorage:', error)
          }
        }
      }
    },
    logout: () => {
      Cookies.remove('auth_token')
      Cookies.remove('user')
      set({ user: null, isAuthenticated: false })
      
      // Sync to localStorage to notify other tabs
      if (typeof window !== 'undefined') {
        try {
          localStorage.removeItem(AUTH_STORAGE_KEY)
        } catch (error) {
          console.error('Error clearing auth state from localStorage:', error)
        }
        window.location.href = '/login'
      }
    },
  }
})

interface SessionState {
  sessionExpiry: number | null
  idleTimeout: number | null
  lastActivity: number
  updateActivity: () => void
  setSessionExpiry: (expiry: number) => void
  setIdleTimeout: (timeout: number) => void
}

export const useSessionStore = create<SessionState>((set) => ({
  sessionExpiry: null,
  idleTimeout: null,
  lastActivity: Date.now(),
  updateActivity: () => set({ lastActivity: Date.now() }),
  setSessionExpiry: (expiry) => set({ sessionExpiry: expiry }),
  setIdleTimeout: (timeout) => set({ idleTimeout: timeout }),
}))

interface SubNavItem {
  name: string
  href: string
  icon?: React.ComponentType<{ className?: string }>
  color?: string
}

interface NavigationState {
  subItems: SubNavItem[]
  setSubItems: (items: SubNavItem[]) => void
  clearSubItems: () => void
}

export const useNavigationStore = create<NavigationState>((set) => ({
  subItems: [],
  setSubItems: (items) => set({ subItems: items }),
  clearSubItems: () => set({ subItems: [] }),
}))

interface ThemeState {
  theme: 'dark' | 'light'
  setTheme: (theme: 'dark' | 'light') => void
  initializeTheme: (userTheme?: string) => void
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: 'dark', // Default to dark
  setTheme: (theme) => {
    set({ theme })
    // Apply theme class to html element
    if (typeof window !== 'undefined') {
      const html = document.documentElement
      html.classList.remove('light', 'dark')
      html.classList.add(theme)
      // Store in localStorage for persistence
      localStorage.setItem('theme', theme)
    }
  },
  initializeTheme: (userTheme) => {
    // Priority: user preference > localStorage > default (dark)
    let theme: 'dark' | 'light' = 'dark'
    
    if (userTheme && (userTheme === 'dark' || userTheme === 'light')) {
      theme = userTheme as 'dark' | 'light'
    } else if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('theme')
      if (stored === 'dark' || stored === 'light') {
        theme = stored as 'dark' | 'light'
      }
    }
    
    set({ theme })
    // Apply theme class to html element before render
    if (typeof window !== 'undefined') {
      const html = document.documentElement
      html.classList.remove('light', 'dark')
      html.classList.add(theme)
      localStorage.setItem('theme', theme)
    }
  },
}))
