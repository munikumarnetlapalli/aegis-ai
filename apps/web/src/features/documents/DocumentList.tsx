import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listDocuments, deleteDocument } from '../../services/api'
import type { DocumentItem } from '../../types/documents'
import { ChunkInspectorModal } from './ChunkInspectorModal'

interface Props {
  refreshKey: number
}

const STATUS_CONFIG: Record<string, { label: string; className: string }> = {
  indexed: { label: 'Indexed', className: 'status-badge status-badge--indexed' },
  processing: { label: 'Processing…', className: 'status-badge status-badge--processing' },
  pending: { label: 'Pending', className: 'status-badge status-badge--pending' },
  failed: { label: 'Failed', className: 'status-badge status-badge--failed' },
}

export function DocumentList({ refreshKey }: Props) {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [selectedJurisdiction, setSelectedJurisdiction] = useState('')
  const [inspectingDoc, setInspectingDoc] = useState<{ id: string; filename: string } | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['documents', refreshKey],
    queryFn: listDocuments,
    refetchInterval: 5000,
  })

  const deleteMutation = useMutation({
    mutationFn: (docId: string) => deleteDocument(docId),
    onSuccess: () => {
      setActionError(null)
      setDeletingId(null)
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (err: unknown) => {
      setDeletingId(null)
      setActionError(err instanceof Error ? err.message : 'Deletion failed')
    },
  })

  const handleDelete = (doc: DocumentItem) => {
    if (window.confirm(`Are you sure you want to permanently delete '${doc.filename}' and all its indexed chunks?`)) {
      setDeletingId(doc.document_id)
      deleteMutation.mutate(doc.document_id)
    }
  }

  const docs = data?.documents ?? []
  const filteredDocs = docs.filter((d) => {
    const matchesSearch = d.filename.toLowerCase().includes(search.toLowerCase())
    const matchesJur = selectedJurisdiction ? d.jurisdiction === selectedJurisdiction : true
    return matchesSearch && matchesJur
  })

  return (
    <div className="doc-list-container">
      <div className="doc-list-header-row">
        <div>
          <h2 className="doc-list-title">Indexed Documents</h2>
          <p className="doc-list-subtitle">
            Regulated policies, guidebooks, and legal instruments available for grounded search.
          </p>
        </div>
        <div className="doc-list-counts">
          <span className="count-badge">{docs.length} Total</span>
        </div>
      </div>

      {actionError && (
        <div className="auth-alert auth-alert--error mb-4">
          <span>{actionError}</span>
          <button className="alert-dismiss" onClick={() => setActionError(null)}>✕</button>
        </div>
      )}

      {/* ── Filters ────────────────────────────────────────────────────── */}
      <div className="doc-filters-bar">
        <input
          type="text"
          className="form-input filter-search"
          placeholder="Filter by filename…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="form-select filter-select"
          value={selectedJurisdiction}
          onChange={(e) => setSelectedJurisdiction(e.target.value)}
        >
          <option value="">All Jurisdictions</option>
          <option value="GLOBAL">GLOBAL</option>
          <option value="EU">EU (GDPR)</option>
          <option value="US">US</option>
          <option value="HIPAA">HIPAA</option>
          <option value="INDIA">INDIA</option>
        </select>
      </div>

      {/* ── Document List Items ────────────────────────────────────────── */}
      {isLoading && (
        <div className="doc-list-empty">
          <div className="spinner" />
          <p>Loading documents…</p>
        </div>
      )}

      {isError && (
        <div className="doc-list-empty doc-list-empty--error">
          {error instanceof Error ? error.message : 'Failed to load documents.'}
        </div>
      )}

      {!isLoading && !isError && filteredDocs.length === 0 && (
        <div className="doc-list-empty">
          <div className="empty-icon">📂</div>
          <p>
            {search || selectedJurisdiction
              ? 'No documents match your filter criteria.'
              : 'No documents indexed yet. Upload one above to begin.'}
          </p>
        </div>
      )}

      {!isLoading && !isError && filteredDocs.length > 0 && (
        <div className="doc-table-wrapper">
          <table className="doc-table">
            <thead>
              <tr>
                <th>Document</th>
                <th>Jurisdiction</th>
                <th>Chunks / Pages</th>
                <th>Status</th>
                <th>Indexed Date</th>
                <th className="text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDocs.map((doc) => {
                const cfg = STATUS_CONFIG[doc.status] ?? STATUS_CONFIG.pending
                const ext = doc.filename.split('.').pop()?.toUpperCase() ?? 'FILE'
                const date = new Date(doc.created_at).toLocaleDateString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                })

                return (
                  <tr key={doc.document_id} className="doc-table-row">
                    <td>
                      <div className="doc-cell-main">
                        <span className="doc-table-icon">{ext}</span>
                        <div className="doc-cell-text">
                          <span className="doc-cell-name" title={doc.filename}>
                            {doc.filename}
                          </span>
                          {doc.allowed_roles && doc.allowed_roles.length > 0 && (
                            <span className="doc-cell-roles">
                              Roles: {doc.allowed_roles.join(', ')}
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="table-jur-badge">{doc.jurisdiction}</span>
                    </td>
                    <td>
                      <span className="table-meta-text">
                        {doc.chunk_count != null ? `${doc.chunk_count} chunks` : '—'} ·{' '}
                        {doc.page_count != null ? `${doc.page_count} pages` : '—'}
                      </span>
                    </td>
                    <td>
                      <span className={cfg.className}>{cfg.label}</span>
                    </td>
                    <td>
                      <span className="table-date-text">{date}</span>
                    </td>
                    <td className="text-right">
                      <div className="table-actions-group">
                        <button
                          className="btn-action btn-action--inspect"
                          title="Inspect chunks & provenance"
                          onClick={() =>
                            setInspectingDoc({
                              id: doc.document_id,
                              filename: doc.filename,
                            })
                          }
                        >
                          🔍 Inspect
                        </button>
                        <button
                          className="btn-action btn-action--delete"
                          title="Delete document"
                          disabled={deletingId === doc.document_id}
                          onClick={() => handleDelete(doc)}
                        >
                          {deletingId === doc.document_id ? '…' : '🗑 Delete'}
                        </button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Chunk Inspector Modal ──────────────────────────────────────── */}
      <ChunkInspectorModal
        documentId={inspectingDoc?.id ?? null}
        filename={inspectingDoc?.filename ?? null}
        onClose={() => setInspectingDoc(null)}
      />
    </div>
  )
}
