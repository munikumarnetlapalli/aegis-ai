import { useState, useRef, useEffect } from 'react'
import { answerQuery } from '../../services/api'
import type { ChatMessage, Citation } from '../../types/chat'
import type { UserProfile } from '../../types/auth'

interface Props {
  currentUser: UserProfile | null
  onOpenCitation: (citation: Citation) => void
  onOpenAuth: () => void
}

const SUGGESTED_QUERIES = [
  'What does comprehensive auto insurance cover?',
  'What information may an insurer request when providing an auto insurance quote?',
  'What is the claim settlement timeline under insurance policy standards?',
  'Explain the grace period for annual policy premium payments.',
]

/**
 * Lightweight parser that formats text with bold, italics, code, bullet lists,
 * and converts [1], [2] citation markers into interactive buttons.
 */
function MarkdownWithCitations({
  text,
  citations = [],
  onCitationClick,
}: {
  text: string
  citations?: Citation[]
  onCitationClick: (citation: Citation) => void
}) {
  // Regex to split by citation patterns [1], [2], etc.
  const citationRegex = /\[(\d+)\]/g
  const parts: React.ReactNode[] = []
  let lastIndex = 0
  let match: RegExpExecArray | null

  while ((match = citationRegex.exec(text)) !== null) {
    const preText = text.slice(lastIndex, match.index)
    if (preText) {
      parts.push(renderFormattedLines(preText, `pre-${match.index}`))
    }

    const citationNum = parseInt(match[1], 10)
    const matchedCitation = citations.find((c) => c.citation_number === citationNum)

    if (matchedCitation) {
      parts.push(
        <button
          key={`cite-${match.index}`}
          className="citation-badge"
          onClick={() => onCitationClick(matchedCitation)}
          title={`Click to view source excerpt from ${matchedCitation.filename}`}
          aria-label={`Citation ${citationNum}: ${matchedCitation.filename}`}
        >
          [{citationNum}]
        </button>
      )
    } else {
      parts.push(
        <span key={`cite-plain-${match.index}`} className="citation-badge citation-badge--unresolved">
          [{citationNum}]
        </span>
      )
    }

    lastIndex = match.index + match[0].length
  }

  if (lastIndex < text.length) {
    parts.push(renderFormattedLines(text.slice(lastIndex), `post-${lastIndex}`))
  }

  return <div className="formatted-message">{parts}</div>
}

function renderFormattedLines(raw: string, keyPrefix: string): React.ReactNode {
  const lines = raw.split('\n')
  return (
    <span key={keyPrefix}>
      {lines.map((line, idx) => {
        // Bullet list
        if (line.trim().startsWith('* ') || line.trim().startsWith('• ') || line.trim().startsWith('- ')) {
          return (
            <span key={`${keyPrefix}-line-${idx}`} className="bullet-item">
              <span className="bullet-dot">•</span>
              <span>{formatInline(line.trim().slice(2))}</span>
            </span>
          )
        }
        return (
          <span key={`${keyPrefix}-line-${idx}`}>
            {formatInline(line)}
            {idx < lines.length - 1 && <br />}
          </span>
        )
      })}
    </span>
  )
}

function formatInline(str: string): React.ReactNode {
  // Simple inline formatting for bold **text**
  const boldParts = str.split(/(\*\*.*?\*\*)/g)
  return boldParts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    return part
  })
}

export function ChatPanel({ currentUser, onOpenCitation, onOpenAuth }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome-1',
      sender: 'assistant',
      content:
        'Welcome to **AegisAI Policy & Compliance Intelligence**.\n\nAsk questions about your regulated insurance documents, claims procedures, or compliance policies. Every answer is grounded in verifiable passage citations and safeguarded by real-time PII redaction.',
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [topK, setTopK] = useState(5)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, loading])

  const handleSend = async (queryText?: string) => {
    const textToSend = (queryText ?? input).trim()
    if (!textToSend || loading) return

    const userMsgId = `user-${Date.now()}`
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

    const userMessage: ChatMessage = {
      id: userMsgId,
      sender: 'user',
      content: textToSend,
      timestamp: timeStr,
    }

    setMessages((prev) => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const response = await answerQuery(textToSend, topK)
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: 'assistant',
        content: response.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: response.citations,
        confidence: response.confidence,
        abstained: response.abstained,
        evidenceCount: response.evidence_count,
        telemetry: response.telemetry,
      }
      setMessages((prev) => [...prev, assistantMessage])

    } catch (err: unknown) {
      const errorMessage: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: 'assistant',
        content: '',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        error: err instanceof Error ? err.message : 'Unable to complete request.',
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const clearChat = () => {
    if (window.confirm('Clear current conversation?')) {
      setMessages([
        {
          id: 'welcome-reset',
          sender: 'assistant',
          content: 'Conversation reset. Ask any question regarding regulated policy documents.',
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    }
  }

  return (
    <div className="chat-container">
      {/* ── Chat Header ──────────────────────────────────────────────────── */}
      <div className="chat-header">
        <div className="chat-header-info">
          <div className="chat-header-title-row">
            <h2 className="chat-header-title">Grounded Policy Assistant</h2>
            <span className="live-pill">Live RAG</span>
          </div>
          <p className="chat-header-desc">
            Multi-stage retrieval (BM25 + Dense + RRF + Cross-Encoder) with strict citation validation.
          </p>
        </div>
        <div className="chat-header-controls">
          <div className="topk-selector" title="Number of reranked passages to consider">
            <span className="topk-label">Top-K:</span>
            <select
              className="topk-select"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
            >
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={8}>8</option>
              <option value={10}>10</option>
            </select>
          </div>
          <button className="chat-action-btn" onClick={clearChat} title="Clear conversation">
            🔄 Clear
          </button>
        </div>
      </div>

      {/* ── Active User Context Bar ──────────────────────────────────────── */}
      <div className="chat-context-bar">
        {currentUser ? (
          <div className="context-bar-inner">
            <span className="context-user-tag">
              👤 <strong>{currentUser.email}</strong>
            </span>
            <span className="context-badge context-badge--role">
              Role: {currentUser.role}
            </span>
            <span className="context-badge context-badge--jur">
              Jurisdiction: {currentUser.jurisdiction}
            </span>
            <span className="context-security-note">
              🛡 Server-side RBAC & jurisdiction filters active in retrieval SQL.
            </span>
          </div>
        ) : (
          <div className="context-bar-inner context-bar-inner--anon">
            <span>
              🔒 Unauthenticated mode. Answers derive from public <code>GLOBAL</code> policies only.
            </span>
            <button className="btn-link" onClick={onOpenAuth}>
              Sign In to unlock regional roles →
            </button>
          </div>
        )}
      </div>

      {/* ── Messages List ────────────────────────────────────────────────── */}
      <div className="chat-messages-scroll">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`chat-message-row ${
              msg.sender === 'user' ? 'chat-message-row--user' : 'chat-message-row--assistant'
            }`}
          >
            <div className="message-avatar">
              {msg.sender === 'user' ? '👤' : '⚖'}
            </div>

            <div className="message-bubble-wrapper">
              <div className="message-meta-row">
                <span className="message-author">
                  {msg.sender === 'user' ? 'You' : 'AegisAI Intelligence'}
                </span>
                <span className="message-time">{msg.timestamp}</span>
              </div>

              {/* ── Error Message ───────────────────────────────────────── */}
              {msg.error && (
                <div className="message-error-card">
                  <span className="error-icon">⚠️</span>
                  <div>
                    <strong>Request Failed</strong>
                    <p>{msg.error}</p>
                  </div>
                </div>
              )}

              {/* ── Abstention Card ─────────────────────────────────────── */}
              {msg.abstained && !msg.error && (
                <div className="abstention-card">
                  <div className="abstention-header">
                    <span className="abstention-icon">🛡</span>
                    <div>
                      <strong className="abstention-title">Policy Abstention Notice</strong>
                      <span className="confidence-pill confidence-pill--low">
                        Confidence: Low ({msg.evidenceCount ?? 0} evidence chunks)
                      </span>
                    </div>
                  </div>
                  <p className="abstention-body">{msg.content}</p>
                  <p className="abstention-hint">
                    AegisAI will never hallucinate or invent answers when supporting document evidence is below the required threshold.
                  </p>
                </div>
              )}

              {/* ── Grounded Answer Message ─────────────────────────────── */}
              {!msg.abstained && !msg.error && (
                <div className="message-content">
                  <MarkdownWithCitations
                    text={msg.content}
                    citations={msg.citations}
                    onCitationClick={onOpenCitation}
                  />

                  {/* ── Citation Cards Tray ──────────────────────────────── */}
                  {msg.citations && msg.citations.length > 0 && (
                    <div className="message-citations-tray">
                      <span className="tray-label">Verified Sources:</span>
                      <div className="citation-chips-list">
                        {msg.citations.map((c) => (
                          <button
                            key={c.citation_number}
                            className="citation-chip-btn"
                            onClick={() => onOpenCitation(c)}
                          >
                            <span className="chip-num">[{c.citation_number}]</span>
                            <span className="chip-name" title={c.filename}>
                              {c.filename}
                            </span>
                            <span className="chip-page">p.{c.page + 1}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* ── Confidence & Telemetry Footer ────────────────────────────────── */}
                  <div className="message-footer-meta">
                    {msg.confidence && (
                      <span
                        className={`confidence-indicator confidence-indicator--${msg.confidence}`}
                      >
                        ● Confidence: {msg.confidence.toUpperCase()}
                      </span>
                    )}
                    <span>· {msg.evidenceCount ?? msg.citations?.length ?? 0} evidence chunks</span>
                    {msg.telemetry && (
                      <span className="telemetry-pill" title={`Latency: ${msg.telemetry.total_latency_ms.toFixed(0)}ms | Retrieval: ${msg.telemetry.retrieval_latency_ms.toFixed(0)}ms | LLM: ${msg.telemetry.llm_latency_ms.toFixed(0)}ms`}>
                        ⚡ {(msg.telemetry.total_latency_ms / 1000).toFixed(2)}s · {msg.telemetry.token_usage?.total_tokens ?? 0} tokens · ${msg.telemetry.estimated_cost_usd.toFixed(4)}
                      </span>
                    )}
                  </div>
                </div>
              )}

            </div>
          </div>
        ))}

        {/* ── Loading / Streaming State ──────────────────────────────────── */}
        {loading && (
          <div className="chat-message-row chat-message-row--assistant">
            <div className="message-avatar">⚖</div>
            <div className="message-bubble-wrapper">
              <div className="message-meta-row">
                <span className="message-author">AegisAI Intelligence</span>
                <span className="message-time">Generating answer…</span>
              </div>
              <div className="loading-state-bubble">
                <div className="typing-dots">
                  <span />
                  <span />
                  <span />
                </div>
                <span className="loading-text">
                  Retrieving evidence across documents & running Cross-Encoder reranking…
                </span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Suggested Quick Prompts ──────────────────────────────────────── */}
      {messages.length <= 2 && (
        <div className="suggested-prompts-tray">
          <span className="suggested-label">Suggested Questions:</span>
          <div className="suggested-chips">
            {SUGGESTED_QUERIES.map((q) => (
              <button
                key={q}
                className="suggested-prompt-chip"
                onClick={() => handleSend(q)}
                disabled={loading}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Chat Input Bar ──────────────────────────────────────────────── */}
      <div className="chat-input-bar">
        <form
          className="chat-input-form"
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
        >
          <textarea
            ref={inputRef}
            className="chat-textarea"
            placeholder="Ask a policy question… (e.g. What is the claim settlement period?)"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            type="submit"
            className="chat-send-btn"
            disabled={!input.trim() || loading}
            aria-label="Send message"
          >
            {loading ? <div className="spinner-small" /> : '➔'}
          </button>
        </form>
      </div>
    </div>
  )
}
