import { useState, useRef, useEffect, type KeyboardEvent, type ChangeEvent } from 'react'
import {
  MessageCircle,
  Send,
  Trash2,
  Loader2,
  Square,
  Sparkles,
  User,
  Bot,
  Paperclip,
  FileText,
  X,
  History,
  Plus,
} from 'lucide-react'
import clsx from 'clsx'
import ReactMarkdown from 'react-markdown'
import { useAdvisorChat, type ChatMessage, type UploadedDocument } from '../hooks/useAdvisorChat'
import AccountSwitcher from '../components/AccountSwitcher'
import ModeToggle from '../components/ModeToggle'

const API_BASE = '/api'

const STARTER_QUESTIONS = [
  'How is my portfolio positioned right now?',
  'Which stocks should I consider trimming?',
  'Am I too concentrated in any sector?',
  'What are my biggest risk exposures?',
  'Any tax-loss harvesting opportunities?',
  'What stocks should I add more of?',
]

function MessageBubble({
  message,
  isStreaming,
  streamingContent,
}: {
  message?: ChatMessage
  isStreaming?: boolean
  streamingContent?: string
}) {
  const isUser = message?.role === 'user'
  const content = isStreaming ? streamingContent : message?.content

  return (
    <div
      className={clsx(
        'flex gap-3 max-w-full',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={clsx(
          'w-7 h-7 rounded-[7px] flex items-center justify-center flex-shrink-0 mt-0.5 border',
          isUser
            ? 'bg-surface-2 border-[rgba(180,220,190,0.12)]'
            : 'bg-accent/[0.10] border-[rgba(207,174,98,0.25)]'
        )}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5 text-text-tertiary" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-accent" />
        )}
      </div>

      {/* Content */}
      <div className={clsx('min-w-0 max-w-[85%]', isUser ? 'items-end' : 'items-start')}>
        {/* Speaker label */}
        <div
          className={clsx(
            'font-mono text-[10px] uppercase tracking-[0.13em] mb-1',
            isUser
              ? 'text-text-tertiary text-right'
              : 'text-accent'
          )}
        >
          {isUser ? 'You' : 'The Partner'}
        </div>
        <div
          className={clsx(
            'rounded-[10px] px-4 py-3 min-w-0 border',
            isUser
              ? 'bg-surface-2 border-[rgba(180,220,190,0.12)] text-text-primary'
              : 'bg-surface-2 border-[rgba(207,174,98,0.20)] text-text-secondary'
          )}
        >
        {isUser ? (
          <p className="text-[13px] leading-relaxed whitespace-pre-wrap">
            {content}
          </p>
        ) : (
          <div className="text-[13px] leading-relaxed prose-advisor">
            <ReactMarkdown
              components={{
                p: ({ children }) => (
                  <p className="mb-2 last:mb-0">{children}</p>
                ),
                strong: ({ children }) => (
                  <strong className="text-text-primary font-semibold">
                    {children}
                  </strong>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-4 mb-2 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-4 mb-2 space-y-1">
                    {children}
                  </ol>
                ),
                li: ({ children }) => <li className="text-[13px]">{children}</li>,
                h1: ({ children }) => (
                  <h1 className="text-[15px] font-semibold text-text-primary mt-3 mb-1">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-[14px] font-semibold text-text-primary mt-3 mb-1">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-[13px] font-semibold text-text-primary mt-2 mb-1">
                    {children}
                  </h3>
                ),
                code: ({ children, className }) => {
                  const isBlock = className?.includes('language-')
                  if (isBlock) {
                    return (
                      <pre className="bg-base border border-[rgba(180,220,190,0.12)] rounded-[8px] px-3 py-2 my-2 overflow-x-auto">
                        <code className="font-mono text-[12px] text-text-secondary">
                          {children}
                        </code>
                      </pre>
                    )
                  }
                  return (
                    <code className="bg-base border border-[rgba(180,220,190,0.12)] px-1.5 py-0.5 rounded font-mono text-[12px] text-accent">
                      {children}
                    </code>
                  )
                },
                table: ({ children }) => (
                  <div className="overflow-x-auto my-2">
                    <table className="font-mono text-[12px] border-collapse w-full tabular-nums">
                      {children}
                    </table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="text-left text-text-primary font-mono text-[10px] uppercase tracking-[0.13em] font-medium px-2 py-1.5 border-b border-[rgba(180,220,190,0.10)]">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-2 py-1.5 border-b border-[rgba(180,220,190,0.06)]">
                    {children}
                  </td>
                ),
              }}
            >
              {content ?? ''}
            </ReactMarkdown>
            {isStreaming && (
              <span className="inline-block w-1.5 h-4 bg-accent/70 rounded-sm animate-pulse ml-0.5 align-text-bottom" />
            )}
          </div>
        )}
        </div>
      </div>
    </div>
  )
}

function DocumentChip({
  doc,
  onRemove,
}: {
  doc: UploadedDocument
  onRemove: () => void
}) {
  const sizeLabel =
    doc.charCount > 10000
      ? `${Math.round(doc.charCount / 1000)}k chars`
      : `${doc.charCount.toLocaleString()} chars`

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 rounded-[8px] bg-surface-2 border border-[rgba(207,174,98,0.25)] text-[12px] group">
      <FileText className="w-3.5 h-3.5 text-accent flex-shrink-0" />
      <span className="text-text-primary truncate max-w-[140px]" title={doc.filename}>
        {doc.filename}
      </span>
      <span className="font-mono text-[11px] text-text-tertiary">{sizeLabel}</span>
      <button
        onClick={onRemove}
        className="ml-0.5 p-0.5 rounded hover:bg-[rgba(180,220,190,0.08)] text-text-tertiary hover:text-loss transition-colors"
        title="Remove document"
      >
        <X className="w-3 h-3" />
      </button>
    </div>
  )
}

export default function Advisor() {
  const {
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
    loadSession,
    deleteSession,
    addDocument,
    removeDocument,
  } = useAdvisorChat()

  const [input, setInput] = useState('')
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll to bottom on new messages or streaming content
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent, statusMessage])

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }, [input])

  const handleSend = () => {
    if (!input.trim() || isStreaming) return
    sendMessage(input)
    setInput('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleStarterClick = (question: string) => {
    sendMessage(question)
  }

  const handleFileUpload = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    // Reset the input so the same file can be re-uploaded
    e.target.value = ''

    // Check if already uploaded
    if (documents.some((d) => d.filename === file.name)) {
      setUploadError(`"${file.name}" is already attached.`)
      setTimeout(() => setUploadError(''), 3000)
      return
    }

    setUploading(true)
    setUploadError('')

    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await fetch(`${API_BASE}/advisor/documents`, {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || `Upload failed: ${res.status}`)
      }

      const data = await res.json()
      addDocument({
        filename: data.filename,
        text: data.text,
        charCount: data.char_count,
      })
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed')
      setTimeout(() => setUploadError(''), 5000)
    } finally {
      setUploading(false)
    }
  }

  const isEmpty = messages.length === 0 && !isStreaming

  return (
    <div className="flex flex-col h-[calc(100vh-0px)] max-h-screen">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-[rgba(180,220,190,0.12)] bg-surface-1/90 backdrop-blur-sm">
        <div className="px-5 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-[8px] bg-accent/[0.10] border border-[rgba(207,174,98,0.25)] flex items-center justify-center">
              <MessageCircle className="w-4 h-4 text-accent" />
            </div>
            <div>
              <h1 className="font-serif text-[19px] font-medium tracking-tight text-text-primary leading-tight">
                Portfolio Advisor
              </h1>
              <p className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mt-0.5">
                The Partner · your portfolio, considered
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <ModeToggle active="risk" variant="navy" />
            {/* Account whose portfolio the advisor reasons about */}
            <AccountSwitcher />

            {/* Session history */}
            <div className="relative">
              <button
                onClick={() => setShowHistory((v) => !v)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] text-text-secondary hover:text-accent rounded-[6px] border border-[rgba(180,220,190,0.12)] hover:border-[rgba(180,220,190,0.30)] transition-colors"
                title="Chat history"
              >
                <History className="w-3.5 h-3.5 text-text-tertiary" />
                <span className="hidden sm:inline">History</span>
              </button>
              {showHistory && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowHistory(false)} />
                  <div className="absolute right-0 mt-1.5 w-72 max-h-[26rem] overflow-y-auto rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] shadow-xl z-50 p-1.5">
                    <div className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary px-2 py-1.5">
                      Past conversations
                    </div>
                    {sessions.length === 0 ? (
                      <div className="px-3 py-4 text-[12px] text-text-tertiary text-center">No past conversations</div>
                    ) : (
                      sessions.map((s) => (
                        <div
                          key={s.id}
                          className={clsx(
                            'group flex items-center gap-2 px-2 py-2 rounded-[7px] hover:bg-[rgba(180,220,190,0.05)] transition-colors',
                            s.id === currentSessionId && 'bg-accent/[0.08] border border-[rgba(207,174,98,0.25)]'
                          )}
                        >
                          <button
                            onClick={() => { loadSession(s.id); setShowHistory(false) }}
                            className="flex-1 min-w-0 text-left"
                          >
                            <p className="text-[13px] text-text-primary truncate">{s.title}</p>
                            <p className="font-mono text-[10px] text-text-tertiary mt-0.5">
                              {new Date(s.updated_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                              {' · '}{s.message_count} msg{s.message_count === 1 ? '' : 's'}
                            </p>
                          </button>
                          <button
                            onClick={() => deleteSession(s.id)}
                            className="opacity-0 group-hover:opacity-100 p-1 text-text-tertiary hover:text-loss transition-all"
                            title="Delete conversation"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </div>

            {/* New chat */}
            <button
              onClick={() => { newSession(); setShowHistory(false) }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] text-text-secondary hover:text-accent rounded-[6px] border border-[rgba(180,220,190,0.12)] hover:border-[rgba(180,220,190,0.30)] transition-colors"
              title="New conversation"
            >
              <Plus className="w-3.5 h-3.5 text-text-tertiary" />
              <span className="hidden sm:inline">New</span>
            </button>
          </div>
        </div>
        <div
          className="h-px"
          style={{
            background:
              'linear-gradient(90deg, transparent, rgba(207,174,98,0.35) 25%, rgba(207,174,98,0.35) 75%, transparent)',
          }}
        />
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {/* Empty state */}
        {isEmpty && (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-14 h-14 rounded-[12px] bg-accent/[0.10] border border-[rgba(207,174,98,0.25)] flex items-center justify-center mb-5">
              <Sparkles className="w-7 h-7 text-accent" />
            </div>
            <h2 className="font-serif text-[22px] font-medium text-text-primary mb-2">
              Portfolio Advisor
            </h2>
            <p className="text-[13px] leading-relaxed text-text-secondary mb-7 max-w-sm">
              Ask me about your portfolio, individual stocks, risk exposure,
              rebalancing, or investment strategy. I'll use your real-time
              portfolio data to give specific advice.
            </p>
            <div className="font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary mb-3">
              A few places to start
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleStarterClick(q)}
                  className="flex items-center gap-2.5 text-left px-3.5 py-2.5 rounded-[10px] bg-surface-2 border border-[rgba(180,220,190,0.12)] text-[12px] text-text-secondary hover:text-text-primary hover:border-[rgba(180,220,190,0.30)] transition-all duration-150"
                >
                  <span
                    className="flex-none"
                    style={{
                      width: 6,
                      height: 6,
                      background: '#CFAE62',
                      transform: 'rotate(45deg)',
                    }}
                  />
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Message bubbles */}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {/* Streaming assistant message */}
        {isStreaming && streamingContent && (
          <MessageBubble
            isStreaming
            streamingContent={streamingContent}
          />
        )}

        {/* Status message (data gathering) */}
        {isStreaming && statusMessage && !streamingContent && (
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-[7px] bg-accent/[0.10] border border-[rgba(207,174,98,0.25)] flex items-center justify-center flex-shrink-0">
              <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
            </div>
            <div className="bg-surface-2 border border-[rgba(207,174,98,0.20)] rounded-[10px] px-4 py-3">
              <p className="text-[13px] text-text-tertiary italic">{statusMessage}</p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-[rgba(180,220,190,0.12)] bg-surface-1/90 backdrop-blur-sm px-4 py-3">
        {/* Document chips */}
        {(documents.length > 0 || uploading || uploadError) && (
          <div className="flex flex-wrap items-center gap-2 mb-2 max-w-3xl mx-auto">
            {documents.map((doc) => (
              <DocumentChip
                key={doc.filename}
                doc={doc}
                onRemove={() => removeDocument(doc.filename)}
              />
            ))}
            {uploading && (
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-[8px] bg-surface-2 border border-[rgba(180,220,190,0.12)] text-[12px] text-text-tertiary">
                <Loader2 className="w-3.5 h-3.5 animate-spin text-accent" />
                Parsing document...
              </div>
            )}
            {uploadError && (
              <div className="text-[12px] text-loss">{uploadError}</div>
            )}
          </div>
        )}

        <div className="flex items-end gap-2 max-w-3xl mx-auto">
          {/* Upload button */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.txt,.md,.csv"
            onChange={handleFileUpload}
            className="hidden"
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading || isStreaming}
            className={clsx(
              'flex-shrink-0 w-10 h-10 rounded-[8px] flex items-center justify-center border transition-colors',
              uploading || isStreaming
                ? 'bg-surface-2 border-[rgba(180,220,190,0.12)] text-text-tertiary cursor-not-allowed'
                : 'bg-surface-2 border-[rgba(180,220,190,0.12)] text-text-secondary hover:border-[rgba(180,220,190,0.30)] hover:text-accent'
            )}
            title="Upload research document (PDF, TXT, MD, CSV)"
          >
            <Paperclip className="w-4 h-4" />
          </button>

          <div className="flex-1 relative">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                documents.length > 0
                  ? 'Ask about your portfolio or uploaded documents...'
                  : 'Ask about your portfolio...'
              }
              disabled={isStreaming}
              rows={1}
              className={clsx(
                'w-full resize-none rounded-[10px] bg-base border border-[rgba(180,220,190,0.12)] px-4 py-3 pr-12',
                'text-[13px] text-text-primary placeholder:text-text-tertiary',
                'focus:outline-none focus:border-[rgba(207,174,98,0.40)] focus:ring-1 focus:ring-[rgba(207,174,98,0.20)]',
                'transition-colors duration-150',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            />
          </div>
          {isStreaming ? (
            <button
              onClick={stopStreaming}
              className="flex-shrink-0 w-10 h-10 rounded-[8px] bg-surface-2 border border-[rgba(242,147,127,0.30)] hover:border-[rgba(242,147,127,0.50)] flex items-center justify-center transition-colors"
              title="Stop generating"
            >
              <Square className="w-4 h-4 text-loss" fill="currentColor" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className={clsx(
                'flex-shrink-0 w-10 h-10 rounded-[8px] flex items-center justify-center border transition-colors',
                input.trim()
                  ? 'bg-accent hover:bg-accent-hover border-accent text-base'
                  : 'bg-surface-2 border-[rgba(180,220,190,0.12)] text-text-tertiary cursor-not-allowed'
              )}
              title="Send message"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
        <p className="text-center font-mono text-[10px] uppercase tracking-[0.13em] text-text-tertiary/60 mt-2.5">
          Shift+Enter for new line · Powered by Claude
        </p>
      </div>
    </div>
  )
}
