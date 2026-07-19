import { useState, useCallback, useRef, useEffect } from 'react'
import { apiStreamPost, apiFetch } from '../api/client'
import { getSelectedAccount } from './usePortfolioStore'
import type { SSEContextEvent, SSETextDoneEvent } from '../api/client'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
}

export interface SessionSummary {
  id: string
  title: string
  account: string | null
  message_count: number
  updated_at: string
}

export interface UploadedDocument {
  filename: string
  text: string
  charCount: number
}

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

/**
 * Advisor chat with DB-backed session history and multi-account awareness.
 * Conversations persist per user in the DB; the portfolio context is drawn from
 * the currently-selected account (switching accounts refetches it). The backend
 * uses per-session prompt caching so follow-up turns are cheap.
 */
export function useAdvisorChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamingContent, setStreamingContent] = useState('')
  const [statusMessage, setStatusMessage] = useState('')
  const [documents, setDocuments] = useState<UploadedDocument[]>([])
  const [sessions, setSessions] = useState<SessionSummary[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)

  const portfolioContextRef = useRef<string | null>(null)
  const contextAccountRef = useRef<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const sessionIdRef = useRef<string | null>(null)

  const refreshSessions = useCallback(async () => {
    try {
      const r = await apiFetch<{ sessions: SessionSummary[] }>('/api/advisor/sessions')
      setSessions(r.sessions || [])
    } catch {
      /* ignore */
    }
  }, [])

  useEffect(() => { refreshSessions() }, [refreshSessions])

  // Persist the conversation to its DB session (creating the session lazily on
  // the first exchange).
  const saveSession = useCallback(async (msgs: ChatMessage[]) => {
    if (msgs.length === 0) return
    const payloadMsgs = msgs.map((m) => ({ role: m.role, content: m.content, timestamp: m.timestamp }))
    const account = getSelectedAccount()
    try {
      const sid = sessionIdRef.current
      if (!sid) {
        const r = await apiFetch<{ id: string }>('/api/advisor/sessions', {
          method: 'POST',
          body: JSON.stringify({ messages: payloadMsgs, account }),
        })
        sessionIdRef.current = r.id
        setCurrentSessionId(r.id)
      } else {
        await apiFetch(`/api/advisor/sessions/${sid}`, {
          method: 'PUT',
          body: JSON.stringify({ messages: payloadMsgs, account }),
        })
      }
      refreshSessions()
    } catch {
      /* ignore — chat still works without persistence */
    }
  }, [refreshSessions])

  const sendMessage = useCallback((text: string) => {
    if (!text.trim() || isStreaming) return

    // Account changed since the cached context was built → drop it so the
    // backend rebuilds context for the newly-selected account.
    const account = getSelectedAccount()
    if (contextAccountRef.current !== account) {
      portfolioContextRef.current = null
      contextAccountRef.current = account
    }

    const userMsg: ChatMessage = { id: generateId(), role: 'user', content: text.trim(), timestamp: Date.now() }
    const updatedMessages = [...messages, userMsg]
    setMessages(updatedMessages)
    setIsStreaming(true)
    setStreamingContent('')
    setStatusMessage('')

    const apiMessages = updatedMessages.map((m) => ({ role: m.role, content: m.content }))
    const docContext = documents.length > 0
      ? documents.map((d) => `## ${d.filename}\n\n${d.text}`).join('\n\n---\n\n')
      : null

    const controller = apiStreamPost(
      '/api/advisor/chat',
      {
        messages: apiMessages,
        portfolio_context: portfolioContextRef.current,
        document_context: docContext,
        account,
      },
      {
        onStatus: ({ message }) => setStatusMessage(message),
        onContext: (data: SSEContextEvent) => { portfolioContextRef.current = data.portfolio_context },
        onDelta: ({ text: delta }) => {
          setStreamingContent((prev) => prev + delta)
          setStatusMessage('')
        },
        onToolCall: ({ name, input }) => {
          if (name === 'get_stock_data') {
            const ticker = (input?.ticker as string) || ''
            setStatusMessage(`Looking up ${ticker.toUpperCase()} fundamentals...`)
          } else if (name === 'web_search') {
            const q = (input?.query as string) || ''
            setStatusMessage(`Searching the web${q ? `: "${q.slice(0, 60)}"` : ''}...`)
          } else {
            setStatusMessage(`Running ${name}...`)
          }
        },
        onToolResult: () => setStatusMessage('Analyzing results...'),
        onTextDone: (data: SSETextDoneEvent) => {
          const assistantMsg: ChatMessage = { id: generateId(), role: 'assistant', content: data.text, timestamp: Date.now() }
          const finalMessages = [...updatedMessages, assistantMsg]
          setMessages(finalMessages)
          setStreamingContent('')
          setStatusMessage('')
          setIsStreaming(false)
          abortRef.current = null
          saveSession(finalMessages)
        },
        onError: ({ message }) => {
          setStatusMessage(`Error: ${message}`)
          setIsStreaming(false)
          abortRef.current = null
          saveSession(updatedMessages)
        },
      },
    )

    abortRef.current = controller
  }, [messages, isStreaming, documents, saveSession])

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setIsStreaming(false)
    setStatusMessage('')
    if (streamingContent) {
      const partialMsg: ChatMessage = {
        id: generateId(),
        role: 'assistant',
        content: streamingContent + '\n\n*(Response was stopped)*',
        timestamp: Date.now(),
      }
      const updated = [...messages, partialMsg]
      setMessages(updated)
      setStreamingContent('')
      saveSession(updated)
    }
  }, [messages, streamingContent, saveSession])

  // Start a fresh conversation (a new session is created on the first message).
  const newSession = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    setMessages([])
    setIsStreaming(false)
    setStreamingContent('')
    setStatusMessage('')
    setDocuments([])
    portfolioContextRef.current = null
    contextAccountRef.current = null
    sessionIdRef.current = null
    setCurrentSessionId(null)
  }, [])

  const loadSession = useCallback(async (id: string) => {
    abortRef.current?.abort()
    abortRef.current = null
    try {
      const s = await apiFetch<{ id: string; title: string; account: string | null; messages: Array<{ role: string; content: string; timestamp?: number }> }>(
        `/api/advisor/sessions/${id}`,
      )
      const msgs: ChatMessage[] = (s.messages || []).map((m, i) => ({
        id: `${id}-${i}`,
        role: m.role === 'assistant' ? 'assistant' : 'user',
        content: m.content,
        timestamp: m.timestamp || Date.now(),
      }))
      setMessages(msgs)
      setStreamingContent('')
      setStatusMessage('')
      setIsStreaming(false)
      // Context isn't stored with the session — refetch for the current account
      // on the next message.
      portfolioContextRef.current = null
      contextAccountRef.current = null
      sessionIdRef.current = id
      setCurrentSessionId(id)
    } catch {
      /* ignore */
    }
  }, [])

  const deleteSession = useCallback(async (id: string) => {
    try {
      await apiFetch(`/api/advisor/sessions/${id}`, { method: 'DELETE' })
    } catch {
      /* ignore */
    }
    if (sessionIdRef.current === id) newSession()
    refreshSessions()
  }, [newSession, refreshSessions])

  const addDocument = useCallback((doc: UploadedDocument) => {
    setDocuments((prev) => [...prev, doc])
  }, [])

  const removeDocument = useCallback((filename: string) => {
    setDocuments((prev) => prev.filter((d) => d.filename !== filename))
  }, [])

  return {
    messages,
    isStreaming,
    streamingContent,
    statusMessage,
    documents,
    sessions,
    currentSessionId,
    sendMessage,
    stopStreaming,
    newSession,
    clearConversation: newSession, // alias kept for existing callers
    loadSession,
    deleteSession,
    refreshSessions,
    addDocument,
    removeDocument,
    hasPortfolioContext: !!portfolioContextRef.current,
  }
}
