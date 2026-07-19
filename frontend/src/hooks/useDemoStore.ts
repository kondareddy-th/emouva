/**
 * Demo access state management.
 * Tracks: demo token, email, usage count, modal visibility.
 * Token stored in localStorage as `emouva_demo_token`.
 */

import { useSyncExternalStore } from 'react'

const DEMO_TOKEN_KEY = 'emouva_demo_token'
const DEMO_EMAIL_KEY = 'emouva_demo_email'
const DAILY_LIMIT = 3 // full analyses (each ≈ 5 API calls)

interface DemoState {
  token: string | null
  email: string | null
  analysesUsedToday: number
  showEmailModal: boolean
  showLimitModal: boolean
  pendingTicker: string | null
  submitting: boolean
  submitError: string | null
}

let state: DemoState = {
  token: localStorage.getItem(DEMO_TOKEN_KEY),
  email: localStorage.getItem(DEMO_EMAIL_KEY),
  analysesUsedToday: 0,
  showEmailModal: false,
  showLimitModal: false,
  pendingTicker: null,
  submitting: false,
  submitError: null,
}

const listeners = new Set<() => void>()
function emit() {
  listeners.forEach((fn) => fn())
}
function setState(updates: Partial<DemoState>) {
  state = { ...state, ...updates }
  emit()
}
function getSnapshot(): DemoState {
  return state
}
function subscribe(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

/** Check if user needs demo gating (no real JWT) */
export function isDemoMode(): boolean {
  if (localStorage.getItem('emouva_jwt')) return false
  return true
}

/** Get the demo token for API headers */
export function getDemoToken(): string | null {
  return localStorage.getItem(DEMO_TOKEN_KEY)
}

/** Get the demo email (for pre-filling signup) */
export function getDemoEmail(): string | null {
  return localStorage.getItem(DEMO_EMAIL_KEY)
}

/** Submit email and get demo token */
async function submitEmail(email: string): Promise<void> {
  setState({ submitting: true, submitError: null })
  try {
    const res = await fetch('/api/demo/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Something went wrong' }))
      throw new Error(err.detail)
    }
    const data = await res.json()
    localStorage.setItem(DEMO_TOKEN_KEY, data.token)
    localStorage.setItem(DEMO_EMAIL_KEY, data.email)
    setState({
      token: data.token,
      email: data.email,
      showEmailModal: false,
      submitting: false,
      analysesUsedToday: 0,
    })
  } catch (err: unknown) {
    setState({
      submitting: false,
      submitError: err instanceof Error ? err.message : 'Failed to start demo',
    })
  }
}

/** Refresh usage count from backend */
async function refreshUsage(): Promise<void> {
  const token = localStorage.getItem(DEMO_TOKEN_KEY)
  if (!token) return
  try {
    const res = await fetch('/api/demo/usage', {
      headers: { 'X-Demo-Token': token },
    })
    if (res.ok) {
      const data = await res.json()
      // Backend counts raw endpoint calls (~5 per analysis), convert to full analyses
      const analysesUsed = Math.floor(data.used / 5)
      setState({ analysesUsedToday: analysesUsed })
    }
  } catch {
    // Non-critical — silently fail
  }
}

/** Called BEFORE running an analysis. Returns gate status. */
function checkAndGate(ticker: string): 'allowed' | 'needs_email' | 'limit_reached' {
  // Not in demo mode (has real JWT)
  if (!isDemoMode()) return 'allowed'

  // No demo token yet — need email first
  if (!state.token) {
    setState({ showEmailModal: true, pendingTicker: ticker })
    return 'needs_email'
  }

  // Hit daily limit
  if (state.analysesUsedToday >= DAILY_LIMIT) {
    setState({ showLimitModal: true })
    return 'limit_reached'
  }

  return 'allowed'
}

/** Called AFTER a successful analysis to update local count */
function recordAnalysis(): void {
  if (!isDemoMode()) return
  const newCount = state.analysesUsedToday + 1
  setState({ analysesUsedToday: newCount })
  // Refresh from backend for accuracy
  refreshUsage()
}

/** Dismiss modals */
function dismissEmailModal() {
  setState({ showEmailModal: false, pendingTicker: null })
}
function dismissLimitModal() {
  setState({ showLimitModal: false })
}

/** Clear demo state (called on signup/login) */
export function clearDemo(): void {
  localStorage.removeItem(DEMO_TOKEN_KEY)
  localStorage.removeItem(DEMO_EMAIL_KEY)
  setState({
    token: null,
    email: null,
    analysesUsedToday: 0,
    showEmailModal: false,
    showLimitModal: false,
    pendingTicker: null,
  })
}

/** How many analyses remain today */
function remaining(): number {
  return Math.max(0, DAILY_LIMIT - state.analysesUsedToday)
}

export function useDemoStore() {
  const snapshot = useSyncExternalStore(subscribe, getSnapshot)
  return {
    ...snapshot,
    isDemoMode: isDemoMode(),
    remaining: remaining(),
    submitEmail,
    refreshUsage,
    checkAndGate,
    recordAnalysis,
    dismissEmailModal,
    dismissLimitModal,
    clearDemo,
  }
}
