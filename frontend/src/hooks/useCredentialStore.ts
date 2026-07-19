/**
 * Browser-side credential storage using localStorage.
 * Keys are base64-encoded to prevent casual inspection.
 * Cleared on explicit user action only.
 */

const STORE_PREFIX = 'emouva_cred_'

export interface Credentials {
  robinhoodUsername: string
  robinhoodPassword: string
}

export function getCredentials(): Credentials {
  return {
    robinhoodUsername: getItem('rh_username'),
    robinhoodPassword: getItem('rh_password'),
  }
}

export function setCredential(key: string, value: string): void {
  try {
    if (value) {
      localStorage.setItem(`${STORE_PREFIX}${key}`, btoa(value))
    } else {
      localStorage.removeItem(`${STORE_PREFIX}${key}`)
    }
  } catch {
    // localStorage full or unavailable
  }
}

export function getItem(key: string): string {
  try {
    const val = localStorage.getItem(`${STORE_PREFIX}${key}`)
    return val ? atob(val) : ''
  } catch {
    return ''
  }
}

export function clearCredentials(): void {
  const keys = Object.keys(localStorage).filter(k => k.startsWith(STORE_PREFIX))
  keys.forEach(k => localStorage.removeItem(k))
}

export function hasRobinhoodCreds(): boolean {
  return !!getItem('rh_username') && !!getItem('rh_password')
}
