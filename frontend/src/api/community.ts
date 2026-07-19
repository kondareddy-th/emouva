/**
 * Community API client — the community feed is CENTRAL (one shared room on
 * emouva.com), while trading runs on whatever instance serves this app.
 *
 * Two modes, decided at runtime:
 *  - LOCAL  — this app IS the community host (emouva.com itself, or a self-host
 *             that set VITE_COMMUNITY_HOST to its own origin): same-origin /api
 *             with the normal session JWT.
 *  - REMOTE — a self-hosted/local install: community calls go to the central
 *             host with a separate "community token" from an emouva.com login,
 *             stored in this browser. Trading data stays 100% local.
 */
import { apiFetch } from './client'

export const COMMUNITY_HOST: string =
  ((import.meta as any).env?.VITE_COMMUNITY_HOST as string) || 'https://emouva.com'

const norm = (h: string) => h.replace(/^www\./, '')
export const isRemoteCommunity: boolean = (() => {
  try {
    return norm(new URL(COMMUNITY_HOST).hostname) !== norm(window.location.hostname)
  } catch {
    return false
  }
})()

const R_TOKEN = 'emouva_community_token'
const R_USER = 'emouva_community_user'

export interface CommunityUser {
  id: string
  username: string
  display_name: string
  public_id?: string | null
}

export function getCommunityUser(): CommunityUser | null {
  try {
    const raw = localStorage.getItem(R_USER)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function communitySignedIn(): boolean {
  return !!localStorage.getItem(R_TOKEN)
}

export function communityLogout(): void {
  localStorage.removeItem(R_TOKEN)
  localStorage.removeItem(R_USER)
}

/** Sign in to the central community host with an emouva.com account. */
export async function communityLogin(username: string, password: string): Promise<CommunityUser> {
  const res = await fetch(`${COMMUNITY_HOST}/api/users/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Login failed')
  }
  const data = await res.json()
  localStorage.setItem(R_TOKEN, data.token)
  localStorage.setItem(R_USER, JSON.stringify(data.user))
  return data.user
}

/** Fetch against the community — same-origin in LOCAL mode, central host in REMOTE. */
export async function communityFetch<T>(path: string, options?: RequestInit): Promise<T> {
  if (!isRemoteCommunity) return apiFetch<T>(path, options)
  const cleanPath = path.startsWith('/api') ? path : `/api${path}`
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }
  const token = localStorage.getItem(R_TOKEN)
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${COMMUNITY_HOST}${cleanPath}`, { ...options, headers })
  if (!res.ok) {
    if (res.status === 401) communityLogout()
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || `Community request failed (${res.status})`)
  }
  return res.json()
}
