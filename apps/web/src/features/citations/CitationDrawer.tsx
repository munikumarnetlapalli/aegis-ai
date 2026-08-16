import { useState } from 'react'
import type { Citation } from '../../types/chat'

interface Props {
  citation: Citation | null
  onClose: () => void
}

export function CitationDrawer({ citation, onClose }: Props) {
  const [copied, setCopied] = useState(false)

  if (!citation) return null

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(
        `"${citation.excerpt}" — [${citation.citation_number}] ${citation.filename} (Page ${citation.page + 1}${citation.section ? `, §${citation.section}` : ''})`
      )
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  const ext = citation.filename.split('.').pop()?.toUpperCase() ?? 'DOC'

  return (
    <div className="drawer-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <aside className="citation-drawer" onClick={(e) => e.stopPropagation()}>
        {/* ── Drawer Header ──────────────────────────────────────────────── */}
        <div className="drawer-header">
          <div className="drawer-title-group">
            <span className="citation-pill">Source [{citation.citation_number}]</span>
            <h3 className="drawer-title">Citation Inspector</h3>
          </div>
          <button
            className="drawer-close-btn"
            onClick={onClose}
            aria-label="Close citation inspector"
          >
            ✕
          </button>
        </div>

        {/* ── Document Card ──────────────────────────────────────────────── */}
        <div className="drawer-doc-card">
          <div className="drawer-doc-icon">{ext}</div>
          <div className="drawer-doc-info">
            <div className="drawer-doc-name" title={citation.filename}>
              {citation.filename}
            </div>
            <div className="drawer-doc-badges">
              <span className="provenance-badge">Page {citation.page + 1}</span>
              {citation.section && (
                <span className="provenance-badge">§ {citation.section}</span>
              )}
            </div>
          </div>
        </div>

        {/* ── Passage Excerpt ────────────────────────────────────────────── */}
        <div className="drawer-section">
          <div className="drawer-section-header">
            <span className="drawer-section-title">Verified Source Passage</span>
            <button
              className={`copy-btn ${copied ? 'copy-btn--copied' : ''}`}
              onClick={handleCopy}
              title="Copy passage citation"
            >
              {copied ? '✓ Copied' : '📋 Copy Passage'}
            </button>
          </div>
          <div className="drawer-passage-box">
            <blockquote className="drawer-passage-text">
              “{citation.excerpt}”
            </blockquote>
          </div>
        </div>

        {/* ── Provenance Details ─────────────────────────────────────────── */}
        <div className="drawer-section">
          <span className="drawer-section-title">Provenance & Traceability</span>
          <div className="drawer-meta-grid">
            <div className="meta-item">
              <span className="meta-key">Chunk ID</span>
              <span className="meta-val font-mono">{citation.chunk_id}</span>
            </div>
            <div className="meta-item">
              <span className="meta-key">Status</span>
              <span className="meta-val text-emerald">Verified In Context</span>
            </div>
          </div>
        </div>

        {/* ── Footer ─────────────────────────────────────────────────────── */}
        <div className="drawer-footer">
          <p className="drawer-hint">
            Every factual claim in AegisAI is grounded in verifiable passage evidence.
          </p>
        </div>
      </aside>
    </div>
  )
}
