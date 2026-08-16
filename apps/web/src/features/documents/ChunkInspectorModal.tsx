import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getDocumentChunks } from '../../services/api'
import type { DocumentChunkItem } from '../../types/documents'

interface Props {
  documentId: string | null
  filename: string | null
  onClose: () => void
}

function ChunkItemCard({ chunk }: { chunk: DocumentChunkItem }) {
  const [expanded, setExpanded] = useState(true)
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(chunk.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
    }
  }

  return (
    <div className="inspector-chunk-card">
      <div className="inspector-chunk-header">
        <div className="inspector-chunk-tags">
          <span className="chunk-badge chunk-badge--index">
            Chunk #{chunk.chunk_index + 1}
          </span>
          <span className="chunk-badge">Page {chunk.page + 1}</span>
          {chunk.section && (
            <span className="chunk-badge chunk-badge--section">
              § {chunk.section}
            </span>
          )}
          <span className="chunk-badge chunk-badge--jur">{chunk.jurisdiction}</span>
          <span className="chunk-char-count">{chunk.char_count} chars</span>
        </div>
        <div className="inspector-chunk-actions">
          <button
            className="copy-btn"
            onClick={handleCopy}
            title="Copy chunk text"
          >
            {copied ? '✓ Copied' : '📋 Copy'}
          </button>
          <button
            className="toggle-btn"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
          >
            {expanded ? '▲ Collapse' : '▼ Expand'}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="inspector-chunk-body">
          <p className="inspector-chunk-text">{chunk.content}</p>
          <div className="inspector-chunk-meta">
            <span>
              Chunk ID: <code>{chunk.chunk_id}</code>
            </span>
            {chunk.allowed_roles && chunk.allowed_roles.length > 0 && (
              <span>
                Roles: <code>{chunk.allowed_roles.join(', ')}</code>
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function ChunkInspectorModal({ documentId, filename, onClose }: Props) {
  const [search, setSearch] = useState('')

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['document_chunks', documentId],
    queryFn: () => (documentId ? getDocumentChunks(documentId) : null),
    enabled: !!documentId,
  })

  if (!documentId) return null

  const chunks = data?.chunks ?? []
  const filteredChunks = search.trim()
    ? chunks.filter((c) =>
        c.content.toLowerCase().includes(search.toLowerCase()) ||
        (c.section && c.section.toLowerCase().includes(search.toLowerCase()))
      )
    : chunks

  return (
    <div className="modal-overlay" onClick={onClose} role="dialog" aria-modal="true">
      <div className="chunk-inspector-modal" onClick={(e) => e.stopPropagation()}>
        {/* ── Header ──────────────────────────────────────────────────── */}
        <div className="modal-header">
          <div className="modal-title-group">
            <span className="doc-type-icon">📑</span>
            <div>
              <h3 className="modal-title">Document Chunks & Provenance</h3>
              <div className="modal-subtitle">
                {filename ?? 'Document'} · {chunks.length} total chunk
                {chunks.length !== 1 ? 's' : ''}
              </div>
            </div>
          </div>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close inspector">
            ✕
          </button>
        </div>

        {/* ── Search bar ──────────────────────────────────────────────── */}
        <div className="inspector-search-row">
          <input
            type="text"
            className="form-input"
            placeholder="Search chunk text or section…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button className="search-clear-btn" onClick={() => setSearch('')}>
              Clear
            </button>
          )}
        </div>

        {/* ── Chunk list ──────────────────────────────────────────────── */}
        <div className="inspector-chunks-container">
          {isLoading && (
            <div className="doc-list-empty">
              <div className="spinner" />
              <p>Loading document chunks…</p>
            </div>
          )}

          {isError && (
            <div className="doc-list-empty doc-list-empty--error">
              {error instanceof Error ? error.message : 'Failed to retrieve document chunks.'}
            </div>
          )}

          {!isLoading && !isError && filteredChunks.length === 0 && (
            <div className="doc-list-empty">
              {search ? 'No chunks match your search query.' : 'No chunks found for this document.'}
            </div>
          )}

          {!isLoading &&
            !isError &&
            filteredChunks.map((chunk) => (
              <ChunkItemCard key={chunk.chunk_id} chunk={chunk} />
            ))}
        </div>

        {/* ── Footer ──────────────────────────────────────────────────── */}
        <div className="modal-footer">
          <span className="footer-meta-note">
            Showing {filteredChunks.length} of {chunks.length} chunks (Provenance & Content only)
          </span>
          <button className="btn btn--secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
