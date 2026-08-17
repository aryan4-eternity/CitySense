// ============================================================
// ChatPanel — CitySense AI chatbot panel
// Supports natural language queries + Google Maps URL analysis
// ============================================================

import { useState, useRef, useEffect, useCallback } from 'react'
import { Bot, Sparkles, X, RotateCcw, Send, MapPin } from 'lucide-react'
import { sendChatMessage } from '@/api/citysense'
import { useStore } from '@/store/useStore'
import type { ChatMessage } from '@/types'

// ----------------------------------------------------------------
// Suggested starter prompts
// ----------------------------------------------------------------
const SUGGESTIONS = [
  'Which areas have the highest flood risk?',
  'What is the average EHI across Mumbai?',
  'Show me the top 5 high priority cells',
  'Paste a Google Maps link to analyze a location',
]

// ----------------------------------------------------------------
// Markdown-lite renderer — bold, italic, bullets, headers, line breaks
// ----------------------------------------------------------------
function renderMarkdown(text: string): React.ReactNode[] {
  const lines = text.split('\n')
  return lines.map((line, i) => {
    // H3 headers (###)
    const h3Match = line.match(/^###\s+(.+)/)
    if (h3Match) {
      return (
        <div
          key={i}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 10,
            color: 'var(--glow-cyan)',
            textTransform: 'uppercase',
            letterSpacing: '0.10em',
            marginTop: 12,
            marginBottom: 5,
            textShadow: '0 0 8px var(--glow-cyan-dim)',
            borderBottom: '1px solid rgba(0,180,255,0.12)',
            paddingBottom: 3,
          }}
        >
          {renderInline(h3Match[1])}
        </div>
      )
    }
    // H2 headers (##)
    const h2Match = line.match(/^##\s+(.+)/)
    if (h2Match) {
      return (
        <div
          key={i}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--glow-cyan)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            marginTop: 10,
            marginBottom: 4,
            textShadow: '0 0 8px var(--glow-cyan-dim)',
          }}
        >
          {renderInline(h2Match[1])}
        </div>
      )
    }
    // H1 headers (#) — strip entirely, not needed
    const h1Match = line.match(/^#\s+(.+)/)
    if (h1Match) {
      return (
        <div
          key={i}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 12,
            color: 'var(--glow-cyan)',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
            marginTop: 10,
            marginBottom: 4,
            textShadow: '0 0 8px var(--glow-cyan-dim)',
          }}
        >
          {renderInline(h1Match[1])}
        </div>
      )
    }
    // Bullet points
    const bulletMatch = line.match(/^[\s]*[-*•]\s+(.+)/)
    if (bulletMatch) {
      return (
        <div key={i} style={{ display: 'flex', gap: 6, marginBottom: 3 }}>
          <span style={{ color: 'var(--glow-cyan)', flexShrink: 0, marginTop: 1 }}>▸</span>
          <span>{renderInline(bulletMatch[1])}</span>
        </div>
      )
    }
    // Horizontal rule
    if (line.match(/^---+$/)) {
      return <div key={i} className="divider" style={{ margin: '8px 0' }} />
    }
    // Empty line → spacing
    if (line.trim() === '') {
      return <div key={i} style={{ height: 6 }} />
    }
    // Regular paragraph
    return (
      <div key={i} style={{ marginBottom: 2 }}>
        {renderInline(line)}
      </div>
    )
  })
}

function renderInline(text: string): React.ReactNode {
  // Split on **bold**, *italic*, and `code` spans
  const parts = text.split(/(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} style={{ color: 'var(--text-bright)', fontWeight: 700 }}>
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
      return (
        <em key={i} style={{ color: 'var(--text-secondary)', fontStyle: 'italic' }}>
          {part.slice(1, -1)}
        </em>
      )
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.9em',
            color: 'var(--glow-cyan)',
            background: 'rgba(0,212,255,0.08)',
            padding: '0 4px',
            borderRadius: 3,
          }}
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}

// ----------------------------------------------------------------
// Typing indicator
// ----------------------------------------------------------------
function TypingIndicator() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        padding: '10px 12px',
      }}
    >
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: 'var(--glow-cyan)',
            opacity: 0.7,
            animation: `dot-blink 1.4s ease-in-out ${i * 0.2}s infinite`,
          }}
        />
      ))}
      <span
        style={{
          fontSize: 11,
          color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)',
          marginLeft: 4,
        }}
      >
        Analyzing…
      </span>
    </div>
  )
}

// ----------------------------------------------------------------
// Message bubble
// ----------------------------------------------------------------
function MessageBubble({ msg }: { msg: ChatMessage }) {
  const isUser = msg.role === 'user'
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start',
        marginBottom: 12,
        animation: 'fadeIn 0.25s ease-out',
      }}
    >
      {/* Role label */}
      <div
        style={{
          fontSize: 9.5,
          fontFamily: 'var(--font-mono)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: isUser ? 'var(--glow-cyan-dim)' : 'rgba(0,255,159,0.7)',
          marginBottom: 4,
          paddingInline: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 4,
        }}
      >
        {isUser ? (
          'You'
        ) : (
          <>
            <Bot size={11} color="var(--glow-cyan)" />
            <span>CitySense AI</span>
          </>
        )}
      </div>

      {/* Bubble */}
      <div
        style={{
          maxWidth: '92%',
          padding: '12px 16px',
          borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
          background: isUser
            ? 'rgba(0, 212, 255, 0.14)'
            : 'rgba(8, 22, 48, 0.95)',
          border: `1px solid ${isUser ? 'rgba(0,212,255,0.32)' : 'rgba(0,180,255,0.18)'}`,
          fontSize: 13.5,
          lineHeight: 1.6,
          color: 'var(--text-primary)',
          wordBreak: 'break-word',
          boxShadow: isUser ? '0 2px 10px rgba(0,212,255,0.10)' : '0 4px 16px rgba(0,0,0,0.4)',
        }}
      >
        {isUser ? (
          <span>{msg.content}</span>
        ) : (
          <div>{renderMarkdown(msg.content)}</div>
        )}
      </div>

      {/* Cell highlight button — shown when bot resolves a location */}
      {!isUser && msg.cell_id && (
        <button
          type="button"
          onClick={() => setSelectedCellId(msg.cell_id!)}
          style={{
            marginTop: 6,
            padding: '5px 12px',
            fontSize: 11,
            fontFamily: 'var(--font-mono)',
            letterSpacing: '0.06em',
            background: 'rgba(0,212,255,0.12)',
            border: '1px solid rgba(0,212,255,0.4)',
            borderRadius: 5,
            color: 'var(--glow-cyan)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(0,212,255,0.22)'
            e.currentTarget.style.boxShadow = '0 0 10px var(--glow-cyan-dim)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(0,212,255,0.12)'
            e.currentTarget.style.boxShadow = 'none'
          }}
        >
          <MapPin size={12} /> View {msg.cell_id} on map
        </button>
      )}
    </div>
  )
}

// ----------------------------------------------------------------
// Main ChatPanel component
// ----------------------------------------------------------------
export function ChatPanel() {
  const chatOpen        = useStore((s) => s.chatOpen)
  const setChatOpen     = useStore((s) => s.setChatOpen)
  const setSelectedCellId = useStore((s) => s.setSelectedCellId)

  const [messages, setMessages]     = useState<ChatMessage[]>([
    {
      role: 'assistant',
      content:
        "Hello! I'm **CitySense AI**, your urban environmental analyst for Mumbai.\n\nYou can ask me about environmental health, flood risk, urban heat, planning interventions — or paste a **Google Maps link** to analyze any location in Mumbai.",
    },
  ])
  const [input, setInput]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState<string | null>(null)

  const bottomRef   = useRef<HTMLDivElement>(null)
  const inputRef    = useRef<HTMLTextAreaElement>(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // Focus input when panel opens
  useEffect(() => {
    if (chatOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [chatOpen])

  const sendMessage = useCallback(async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || loading) return

    const userMsg: ChatMessage = { role: 'user', content: trimmed }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)
    setError(null)

    try {
      const response = await sendChatMessage({
        messages: nextMessages.map((m) => ({ role: m.role, content: m.content })),
      })

      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: response.reply,
        cell_id: response.cell_id,
      }
      setMessages((prev) => [...prev, assistantMsg])

      // Auto-highlight the resolved cell on the map
      if (response.cell_id) {
        setSelectedCellId(response.cell_id)
      }
    } catch (err) {
      const rawMsg = err instanceof Error ? err.message : 'Unknown error'
      console.error('[CitySense AI Chat Error]:', err)

      let cleanMsg = rawMsg
      if (
        rawMsg.includes('{') ||
        rawMsg.includes('RESOURCE_EXHAUSTED') ||
        rawMsg.includes('QuotaFailure') ||
        rawMsg.includes('500') ||
        rawMsg.includes('503') ||
        rawMsg.includes('429') ||
        rawMsg.includes('Traceback')
      ) {
        cleanMsg =
          'The AI assistant is temporarily rate-limited or experiencing high demand. Please wait a few seconds and try again.'
      }

      setError(cleanMsg)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: `⚠️ ${cleanMsg}`,
        },
      ])
    } finally {
      setLoading(false)
    }
  }, [messages, loading, setSelectedCellId])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  const clearChat = () => {
    setMessages([
      {
        role: 'assistant',
        content:
          "Chat cleared. Ask me anything about Mumbai's environment, or paste a Google Maps link!",
      },
    ])
    setError(null)
  }

  if (!chatOpen) return null

  return (
    <div
      className="panel animate-slide-right"
      style={{
        position: 'fixed',
        right: 18,
        bottom: 74,
        width: 'min(540px, calc(100vw - 32px))',
        height: 'min(720px, calc(100vh - 85px))',
        zIndex: 110,
        borderRadius: 14,
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
        boxShadow: '0 16px 56px rgba(0,0,0,0.85), 0 0 0 1px rgba(0,212,255,0.25)',
        backdropFilter: 'blur(16px)',
      }}
      role="dialog"
      aria-label="CitySense AI Chat"
    >
      {/* ── Header ── */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
          background: 'rgba(0,20,45,0.75)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {/* Animated AI bot icon indicator */}
          <div style={{ position: 'relative', width: 32, height: 32 }}>
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: '50%',
                background: 'linear-gradient(135deg, rgba(0,212,255,0.2), rgba(0,120,255,0.1))',
                border: '1px solid rgba(0,212,255,0.45)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'var(--glow-cyan)',
                boxShadow: '0 0 12px rgba(0,212,255,0.25)',
              }}
            >
              <Bot size={18} />
            </div>
            <span
              className="animate-dot-blink"
              style={{
                position: 'absolute',
                top: -1,
                right: -1,
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: 'var(--glow-green)',
                boxShadow: '0 0 8px var(--glow-green)',
              }}
            />
          </div>
          <div>
            <div
              className="font-mono text-glow"
              style={{ fontSize: 13, fontWeight: 700, letterSpacing: '0.06em', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              CITYSENSE AI <Sparkles size={12} color="var(--glow-amber)" />
            </div>
            <div
              style={{ fontSize: 9.5, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}
            >
              Urban Intelligence Assistant
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6 }}>
          {/* Clear button */}
          <button
            type="button"
            onClick={clearChat}
            title="Clear chat"
            aria-label="Clear chat history"
            style={iconBtnStyle}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--glow-amber)'
              e.currentTarget.style.color = 'var(--glow-amber)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.color = 'var(--text-secondary)'
            }}
          >
            <RotateCcw size={13} />
          </button>
          {/* Close button */}
          <button
            type="button"
            onClick={() => setChatOpen(false)}
            title="Close chat"
            aria-label="Close chat panel"
            style={iconBtnStyle}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--glow-red)'
              e.currentTarget.style.color = 'var(--glow-red)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--border)'
              e.currentTarget.style.color = 'var(--text-secondary)'
            }}
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* ── Messages ── */}
      <div
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '14px 14px 4px',
          display: 'flex',
          flexDirection: 'column',
        }}
        role="log"
        aria-live="polite"
        aria-label="Chat messages"
      >
        {messages.map((msg, i) => (
          <MessageBubble key={i} msg={msg} />
        ))}
        {loading && <TypingIndicator />}
        <div ref={bottomRef} />
      </div>

      {/* ── Suggestions (shown when only welcome message present) ── */}
      {messages.length === 1 && !loading && (
        <div
          style={{
            padding: '0 14px 10px',
            display: 'flex',
            flexDirection: 'column',
            gap: 5,
            flexShrink: 0,
          }}
        >
          <div
            style={{
              fontSize: 9,
              color: 'var(--text-muted)',
              fontFamily: 'var(--font-mono)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              marginBottom: 2,
            }}
          >
            Try asking
          </div>
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => sendMessage(s)}
              style={{
                padding: '6px 10px',
                fontSize: 11,
                textAlign: 'left',
                background: 'rgba(0,180,255,0.05)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 5,
                color: 'var(--text-secondary)',
                cursor: 'pointer',
                transition: 'all 0.2s',
                fontFamily: 'var(--font-ui)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'rgba(0,180,255,0.10)'
                e.currentTarget.style.borderColor = 'var(--border)'
                e.currentTarget.style.color = 'var(--text-primary)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'rgba(0,180,255,0.05)'
                e.currentTarget.style.borderColor = 'var(--border-subtle)'
                e.currentTarget.style.color = 'var(--text-secondary)'
              }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* ── Input area ── */}
      <div
        style={{
          padding: '10px 12px',
          borderTop: '1px solid var(--border)',
          flexShrink: 0,
          background: 'rgba(0,10,25,0.5)',
        }}
      >
        {error && (
          <div
            style={{
              fontSize: 10,
              color: 'var(--glow-red)',
              marginBottom: 6,
              fontFamily: 'var(--font-mono)',
            }}
          >
            ⚠ {error}
          </div>
        )}

        <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about Mumbai's environment, or paste a Google Maps link…"
            disabled={loading}
            rows={2}
            aria-label="Chat input"
            style={{
              flex: 1,
              resize: 'none',
              background: 'var(--bg-input)',
              border: '1px solid var(--border)',
              borderRadius: 6,
              padding: '8px 10px',
              fontSize: 12,
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-ui)',
              lineHeight: 1.5,
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--glow-cyan-dim)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border)')}
          />
          <button
            type="button"
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            aria-label="Send message"
            style={{
              width: 38,
              height: 38,
              borderRadius: 6,
              border: '1px solid var(--border)',
              background: input.trim() && !loading
                ? 'rgba(0,212,255,0.20)'
                : 'transparent',
              color: input.trim() && !loading
                ? 'var(--glow-cyan)'
                : 'var(--text-muted)',
              cursor: input.trim() && !loading ? 'pointer' : 'not-allowed',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexShrink: 0,
              transition: 'all 0.2s',
              boxShadow: input.trim() && !loading
                ? '0 0 10px rgba(0,212,255,0.25)'
                : 'none',
            }}
          >
            {loading ? '…' : <Send size={15} />}
          </button>
        </div>

        <div
          style={{
            marginTop: 5,
            fontSize: 9,
            color: 'var(--text-muted)',
            fontFamily: 'var(--font-mono)',
            textAlign: 'right',
          }}
        >
          Enter to send · Shift+Enter for newline
        </div>
      </div>
    </div>
  )
}

// ----------------------------------------------------------------
// Chat toggle button (fixed to bottom-right)
// ----------------------------------------------------------------
export function ChatToggleButton() {
  const chatOpen    = useStore((s) => s.chatOpen)
  const setChatOpen = useStore((s) => s.setChatOpen)

  return (
    <button
      type="button"
      onClick={() => setChatOpen(!chatOpen)}
      aria-label={chatOpen ? 'Close AI chat' : 'Open AI chat'}
      title={chatOpen ? 'Close AI chat' : 'Open CitySense AI Assistant'}
      style={{
        position: 'fixed',
        right: 18,
        bottom: 18,
        width: 50,
        height: 50,
        borderRadius: '50%',
        border: `1px solid ${chatOpen ? 'rgba(0,212,255,0.7)' : 'rgba(0,212,255,0.4)'}`,
        background: chatOpen
          ? 'rgba(0,212,255,0.22)'
          : 'linear-gradient(135deg, rgba(8,24,52,0.95), rgba(2,12,30,0.95))',
        color: 'var(--glow-cyan)',
        cursor: 'pointer',
        zIndex: 200,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        boxShadow: chatOpen
          ? '0 0 24px rgba(0,212,255,0.45), 0 4px 20px rgba(0,0,0,0.6)'
          : '0 0 16px rgba(0,212,255,0.25), 0 4px 20px rgba(0,0,0,0.6)',
        transition: 'all 0.25s cubic-bezier(0.22,1,0.36,1)',
        backdropFilter: 'blur(12px)',
      }}
      onMouseEnter={(e) => {
        if (!chatOpen) {
          e.currentTarget.style.background = 'rgba(0,212,255,0.18)'
          e.currentTarget.style.boxShadow = '0 0 22px rgba(0,212,255,0.40), 0 4px 20px rgba(0,0,0,0.6)'
          e.currentTarget.style.transform = 'scale(1.06)'
        }
      }}
      onMouseLeave={(e) => {
        if (!chatOpen) {
          e.currentTarget.style.background = 'linear-gradient(135deg, rgba(8,24,52,0.95), rgba(2,12,30,0.95))'
          e.currentTarget.style.boxShadow = '0 0 16px rgba(0,212,255,0.25), 0 4px 20px rgba(0,0,0,0.6)'
          e.currentTarget.style.transform = 'scale(1)'
        }
      }}
    >
      {chatOpen ? <X size={22} /> : <Bot size={24} />}
    </button>
  )
}

// ----------------------------------------------------------------
// Shared style constants
// ----------------------------------------------------------------
const iconBtnStyle: React.CSSProperties = {
  width: 26,
  height: 26,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  border: '1px solid var(--border)',
  borderRadius: 4,
  background: 'transparent',
  color: 'var(--text-secondary)',
  cursor: 'pointer',
  fontSize: 15,
  fontWeight: 300,
  transition: 'all 0.2s',
}
