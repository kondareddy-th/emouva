import { getAuthToken, triggerAuthExpired } from '../hooks/useAuth'
import { getItem } from '../hooks/useCredentialStore'

const API_BASE = '/api'

// Simple in-memory GET response cache (30s TTL) so navigating between pages
// that use the same hooks (Dashboard → Portfolio) is instant.
const responseCache = new Map<string, { data: unknown; timestamp: number }>()
const CACHE_TTL = 30_000

// BYOK guard: these endpoints run Claude and require the user's own key (Settings → AI Token).
const AI_PREFIXES = ['/analysis', '/advisor']
const NO_AI_KEY_MSG = 'Add your Anthropic API key in Settings → AI Token to use AI features.'
function needsAiKey(cleanPath: string): boolean {
  return AI_PREFIXES.some((p) => cleanPath.startsWith(p)) && !getItem('anthropic_key')
}

export async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  // Hooks call paths like '/api/portfolio/summary' — strip the '/api' prefix
  const cleanPath = path.startsWith('/api') ? path.slice(4) : path
  const token = getAuthToken()

  const isGet = !options?.method || options.method === 'GET'

  // Return cached response for GET requests within TTL
  if (isGet) {
    const cached = responseCache.get(cleanPath)
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
      return cached.data as T
    }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  } else {
    // Demo mode: send demo token if no JWT
    const demoToken = localStorage.getItem('emouva_demo_token')
    if (demoToken) {
      headers['X-Demo-Token'] = demoToken
    }
  }
  // BYOK: AI endpoints require the user's own Anthropic key (Settings → AI Token).
  if (needsAiKey(cleanPath)) throw new Error(NO_AI_KEY_MSG)
  const aiKey = getItem('anthropic_key')
  if (aiKey) headers['X-Anthropic-Key'] = aiKey

  const res = await fetch(`${API_BASE}${cleanPath}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    if (res.status === 429) {
      const body = await res.json().catch(() => ({ detail: '' }))
      throw new Error(body.detail || 'Daily limit reached. Add your own Anthropic API key in Settings → AI Token for unlimited use.')
    }
    if (res.status === 401) {
      // Distinguish JWT expiry from other auth issues
      const body = await res.json().catch(() => ({ detail: '' }))
      const detail = (body.detail || '').toLowerCase()
      const isJwtIssue =
        detail.includes('not authenticated') ||
        detail.includes('expired token') ||
        detail.includes('invalid token') ||
        detail.includes('user not found')
      if (isJwtIssue) {
        triggerAuthExpired()
        throw new Error('Session expired. Please log in again.')
      }
      throw new Error(body.detail || 'Authentication required. Please sign in.')
    }
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  const data = await res.json()

  // Cache successful GET responses, but skip caching disconnected/error states
  // so reconnection attempts aren't blocked by stale cached data
  if (isGet) {
    const isDisconnected =
      data && typeof data === 'object' && 'source' in data && data.source === 'disconnected'
    if (!isDisconnected) {
      responseCache.set(cleanPath, { data, timestamp: Date.now() })
    }
  } else {
    // A mutation (PUT/POST/DELETE) invalidates cached reads — otherwise a refetch
    // right after a write returns the up-to-30s-stale copy (this is what made the
    // circle-of-competence change persist in the DB but revert in the UI).
    responseCache.clear()
  }

  return data as T
}


/** SSE event types from the streaming brief endpoint */
export interface SSEStatusEvent {
  message: string
}
export interface SSEDeltaEvent {
  text: string
}
export interface SSEDoneEvent {
  result: Record<string, unknown>
  elapsed_seconds: number
}
export interface SSEErrorEvent {
  message: string
}

export interface SSEContextEvent {
  portfolio_context: string
}
export interface SSETextDoneEvent {
  text: string
  elapsed_seconds: number
  tools_used?: number
}

export interface SSEToolCallEvent {
  name: string
  input: Record<string, unknown>
}

export interface SSEToolResultEvent {
  name: string
  status: 'ok' | 'error'
}

export type SSEEventHandlers = {
  onStatus?: (data: SSEStatusEvent) => void
  onDelta?: (data: SSEDeltaEvent) => void
  onDone?: (data: SSEDoneEvent) => void
  onError?: (data: SSEErrorEvent) => void
  onContext?: (data: SSEContextEvent) => void
  onTextDone?: (data: SSETextDoneEvent) => void
  onToolCall?: (data: SSEToolCallEvent) => void
  onToolResult?: (data: SSEToolResultEvent) => void
}

/**
 * Connect to an SSE streaming endpoint. Returns an AbortController to cancel.
 * Uses fetch (not EventSource) so we can pass custom headers.
 */
export function apiStream(path: string, handlers: SSEEventHandlers): AbortController {
  const cleanPath = path.startsWith('/api') ? path.slice(4) : path
  const token = getAuthToken()

  const url = new URL(`${API_BASE}${cleanPath}`, window.location.origin)
  const controller = new AbortController()

  const headers: Record<string, string> = {}
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  } else {
    const demoToken = localStorage.getItem('emouva_demo_token')
    if (demoToken) {
      headers['X-Demo-Token'] = demoToken
    }
  }
  // BYOK: AI endpoints require the user's own Anthropic key (Settings → AI Token).
  if (needsAiKey(cleanPath)) { handlers.onError?.({ message: NO_AI_KEY_MSG }); return controller }
  const aiKey = getItem('anthropic_key')
  if (aiKey) headers['X-Anthropic-Key'] = aiKey

  fetch(url.toString(), {
    headers,
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        if (res.status === 429) {
          const body = await res.json().catch(() => ({ detail: '' }))
          handlers.onError?.({ message: body.detail || 'Daily limit reached. Add your own Anthropic API key in Settings → AI Token for unlimited use.' })
        } else {
          handlers.onError?.({ message: `API error: ${res.status} ${res.statusText}` })
        }
        return
      }
      const reader = res.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      let buffer = ''
      let receivedDone = false
      // Track currentEvent OUTSIDE the loop — event: and data: may arrive in different chunks
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events from buffer
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const raw = line.slice(6)
            try {
              const data = JSON.parse(raw)
              switch (currentEvent) {
                case 'status':
                  handlers.onStatus?.(data)
                  break
                case 'delta':
                  handlers.onDelta?.(data)
                  break
                case 'context':
                  handlers.onContext?.(data)
                  break
                case 'done':
                  receivedDone = true
                  handlers.onDone?.(data)
                  handlers.onTextDone?.(data)
                  break
                case 'error':
                  handlers.onError?.(data)
                  break
                case 'tool_call':
                  handlers.onToolCall?.(data)
                  break
                case 'tool_result':
                  handlers.onToolResult?.(data)
                  break
              }
            } catch {
              // ignore malformed JSON
            }
            currentEvent = ''
          }
        }
      }

      // Stream ended — if we never got a 'done' event, the connection was cut
      if (!receivedDone) {
        handlers.onError?.({ message: 'Stream ended unexpectedly. The analysis may have been too large — try again.' })
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        handlers.onError?.({ message: err.message || 'Stream connection failed' })
      }
    })

  return controller
}

/**
 * POST-based SSE streaming. Same event parsing as apiStream but sends a JSON body.
 * Used for endpoints like advisor/chat where message history goes in the request body.
 */
export function apiStreamPost(
  path: string,
  body: Record<string, unknown>,
  handlers: SSEEventHandlers,
): AbortController {
  const cleanPath = path.startsWith('/api') ? path.slice(4) : path
  const token = getAuthToken()
  const controller = new AbortController()

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  } else {
    const demoToken = localStorage.getItem('emouva_demo_token')
    if (demoToken) {
      headers['X-Demo-Token'] = demoToken
    }
  }
  // BYOK: AI endpoints require the user's own Anthropic key (Settings → AI Token).
  if (needsAiKey(cleanPath)) { handlers.onError?.({ message: NO_AI_KEY_MSG }); return controller }
  const aiKey = getItem('anthropic_key')
  if (aiKey) headers['X-Anthropic-Key'] = aiKey

  fetch(`${API_BASE}${cleanPath}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        if (res.status === 429) {
          const body = await res.json().catch(() => ({ detail: '' }))
          handlers.onError?.({ message: body.detail || 'Daily limit reached. Add your own Anthropic API key in Settings → AI Token for unlimited use.' })
        } else {
          handlers.onError?.({ message: `API error: ${res.status} ${res.statusText}` })
        }
        return
      }
      const reader = res.body?.getReader()
      if (!reader) return
      const decoder = new TextDecoder()
      let buffer = ''
      let receivedDone = false
      let currentEvent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const raw = line.slice(6)
            try {
              const data = JSON.parse(raw)
              switch (currentEvent) {
                case 'status':
                  handlers.onStatus?.(data)
                  break
                case 'delta':
                  handlers.onDelta?.(data)
                  break
                case 'context':
                  handlers.onContext?.(data)
                  break
                case 'done':
                  receivedDone = true
                  handlers.onDone?.(data)
                  handlers.onTextDone?.(data)
                  break
                case 'error':
                  handlers.onError?.(data)
                  break
                case 'tool_call':
                  handlers.onToolCall?.(data)
                  break
                case 'tool_result':
                  handlers.onToolResult?.(data)
                  break
              }
            } catch {
              // ignore malformed JSON
            }
            currentEvent = ''
          }
        }
      }

      if (!receivedDone) {
        handlers.onError?.({ message: 'Stream ended unexpectedly. Try again.' })
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') {
        handlers.onError?.({ message: err.message || 'Stream connection failed' })
      }
    })

  return controller
}
