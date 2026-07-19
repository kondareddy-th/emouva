import { useState, useCallback, useEffect, useRef } from 'react'

const TOKEN_KEY = 'emouva_jwt'
const USER_KEY = 'emouva_user'

export interface User {
  id: string
  username: string
  display_name: string
  robinhood_connected: boolean
  tier: 'free' | 'premium'
  // False only on a personal hosted instance for non-owner accounts (community-only).
  // Absent/undefined (older stored users, self-host) means full access.
  full_access?: boolean
}

interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  verifying: boolean
}

function getStoredAuth(): AuthState {
  const token = localStorage.getItem(TOKEN_KEY)
  const userJson = localStorage.getItem(USER_KEY)
  const user = userJson ? JSON.parse(userJson) : null
  // If token exists, start in verifying state — we need to check it's still valid
  return { token, user, isAuthenticated: false, verifying: !!token }
}

/** Read the JWT token synchronously (used by API client for headers) */
export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

/** Clear all emouva_ cache keys from localStorage (except credentials) */
function clearSessionData() {
  const keysToRemove: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (!key) continue
    // Clear caches and conversations, but keep credentials (emouva_cred_*)
    if (key.startsWith('emouva_') && !key.startsWith('emouva_cred_') && key !== TOKEN_KEY && key !== USER_KEY) {
      keysToRemove.push(key)
    }
  }
  keysToRemove.forEach((k) => localStorage.removeItem(k))
}

// ── Global auth-expired handler ──
// The API client calls this when it gets a JWT 401 to trigger logout
let _authExpiredHandler: (() => void) | null = null

export function setAuthExpiredHandler(handler: (() => void) | null) {
  _authExpiredHandler = handler
}

export function triggerAuthExpired() {
  _authExpiredHandler?.()
}

export default function useAuth() {
  const [state, setState] = useState<AuthState>(getStoredAuth)
  const hasVerified = useRef(false)

  // Register this hook as the auth-expired handler
  const forceLogout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    clearSessionData()
    setState({ token: null, user: null, isAuthenticated: false, verifying: false })
    // Navigate to login — use window.location since we may not have router context
    window.location.href = '/login'
  }, [])

  useEffect(() => {
    setAuthExpiredHandler(forceLogout)
    return () => setAuthExpiredHandler(null)
  }, [forceLogout])

  // Boot-time token verification
  useEffect(() => {
    if (hasVerified.current) return
    hasVerified.current = true

    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) {
      setState((prev) => ({ ...prev, verifying: false }))
      return
    }

    // Verify token with the server
    fetch('/api/users/verify', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json()
          // Update user data from server (may have changed)
          const user = data.user as User
          localStorage.setItem(USER_KEY, JSON.stringify(user))
          setState({ token, user, isAuthenticated: true, verifying: false })
          // Re-check Robinhood status now that token is verified
          import('./usePortfolioStore').then(m => m.resetAuthCheck()).catch(() => {})
        } else {
          // Token expired or invalid — clear it
          localStorage.removeItem(TOKEN_KEY)
          localStorage.removeItem(USER_KEY)
          clearSessionData()
          setState({ token: null, user: null, isAuthenticated: false, verifying: false })
        }
      })
      .catch(() => {
        // Network error — optimistically keep the token (user might be offline)
        // but mark as authenticated based on stored data
        const userJson = localStorage.getItem(USER_KEY)
        const user = userJson ? JSON.parse(userJson) : null
        setState({ token, user, isAuthenticated: !!user, verifying: false })
      })
  }, [])

  // Sync across tabs
  useEffect(() => {
    const handler = () => {
      const stored = getStoredAuth()
      // If another tab cleared the token, reflect that
      if (!stored.token) {
        setState({ token: null, user: null, isAuthenticated: false, verifying: false })
      }
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [])

  const setAuth = useCallback((token: string, user: User) => {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
    setState({ token, user, isAuthenticated: true, verifying: false })
    // Re-check Robinhood status now that we have a valid auth token
    import('./usePortfolioStore').then(m => m.resetAuthCheck()).catch(() => {})
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    const res = await fetch('/api/users/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Login failed')
    }
    const data = await res.json()
    setAuth(data.token, data.user)
    return data.user
  }, [setAuth])

  const signup = useCallback(async (username: string, password: string, displayName: string, email: string) => {
    const res = await fetch('/api/users/signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, display_name: displayName, email }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Signup failed')
    }
    const data = await res.json()
    setAuth(data.token, data.user)
    return data.user
  }, [setAuth])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    clearSessionData()
    setState({ token: null, user: null, isAuthenticated: false, verifying: false })
  }, [])

  // Re-fetch the user from the server (e.g. after a plan change so `tier` updates
  // without a full reload). Returns the fresh user, or null if it couldn't refresh.
  const refreshUser = useCallback(async (): Promise<User | null> => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) return null
    try {
      const res = await fetch('/api/users/verify', { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) return null
      const data = await res.json()
      const user = data.user as User
      localStorage.setItem(USER_KEY, JSON.stringify(user))
      setState((prev) => ({ ...prev, user, isAuthenticated: true }))
      return user
    } catch {
      return null
    }
  }, [])

  return {
    ...state,
    login,
    signup,
    logout,
    refreshUser,
  }
}
