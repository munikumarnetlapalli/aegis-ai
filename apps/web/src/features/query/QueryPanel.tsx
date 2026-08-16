import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { queryDocuments, type ChunkResult } from '../../services/api'

function ChunkCard({ chunk, index }: { chunk: ChunkResult; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const pct = Math.round(chunk.score * 100)
  const scoreClass =
    pct >= 80 ? 'score-bar--high' : pct >= 50 ? 'score-bar--mid' : 'score-bar--low'

  return (
    <div className="chunk-card">
      <div className="chunk-header">
        <span className="chunk-index">#{index + 1}</span>
        <div className="chunk-source">
          <span className="chunk-filename">{chunk.provenance.filename}</span>
          {chunk.provenance.section && (
            <span className="chunk-section">§ {chunk.provenance.section}</span>
          )}
          <span className="chunk-page">p.{chunk.provenance.page + 1}</span>
        </div>
        <div className="score-pill">
          <div className={`score-bar ${scoreClass}`} style={{ width: `${pct}%` }} />
          <span className="score-label">{pct}%</span>
        </div>
        <button
          id={`chunk-toggle-${index}`}
          className="chunk-toggle"
          onClick={() => setExpanded(!expanded)}
          aria-expanded={expanded}
          aria-label={expanded ? 'Collapse chunk' : 'Expand chunk'}
        >
          {expanded ? '▲' : '▼'}
        </button>
      </div>

      <p className={`chunk-content ${expanded ? 'chunk-content--expanded' : ''}`}>
        {chunk.content}
      </p>

      {expanded && (
        <div className="chunk-provenance">
          <span>Doc ID: <code>{chunk.provenance.document_id.slice(0, 8)}…</code></span>
          <span>Jurisdiction: <code>{chunk.provenance.jurisdiction}</code></span>
          <span>Chunk #<code>{chunk.provenance.chunk_index}</code></span>
        </div>
      )}
    </div>
  )
}

export function QueryPanel() {
  const [query, setQuery] = useState('')
  const [submitted, setSubmitted] = useState('')
  const [jurisdiction, setJurisdiction] = useState('')

  const { data, isFetching, isError } = useQuery({
    queryKey: ['query', submitted, jurisdiction],
    queryFn: () => queryDocuments(submitted, jurisdiction || undefined, 10),
    enabled: !!submitted,
    retry: false,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (query.trim()) setSubmitted(query.trim())
  }

  return (
    <div className="query-panel">
      <h2 className="query-title">Retrieval Query</h2>
      <p className="query-subtitle">
        Search for evidence across indexed documents. Results show raw chunks with provenance.
      </p>

      <form className="query-form" onSubmit={handleSubmit} id="query-form">
        <div className="query-row">
          <input
            id="query-input"
            className="query-input"
            type="text"
            placeholder="e.g. What is the claim settlement period?"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            id="query-jurisdiction"
            className="meta-select"
            value={jurisdiction}
            onChange={(e) => setJurisdiction(e.target.value)}
            title="Filter by jurisdiction"
          >
            <option value="">All jurisdictions</option>
            <option value="GLOBAL">GLOBAL</option>
            <option value="EU">EU</option>
            <option value="US">US</option>
            <option value="HIPAA">HIPAA</option>
            <option value="UK">UK</option>
          </select>
          <button
            id="query-submit"
            type="submit"
            className="query-btn"
            disabled={!query.trim() || isFetching}
          >
            {isFetching ? '…' : 'Search'}
          </button>
        </div>
      </form>

      {isError && (
        <div className="query-error">Query failed — check that documents are indexed.</div>
      )}

      {data && (
        <div className="query-results">
          <div className="results-header">
            <span>{data.result_count} chunk{data.result_count !== 1 ? 's' : ''} found</span>
            <span className="results-message">{data.message}</span>
          </div>
          {data.results.length === 0 ? (
            <div className="doc-list-empty">
              No matching chunks found. Try a different query or upload relevant documents.
            </div>
          ) : (
            data.results.map((chunk, i) => (
              <ChunkCard key={chunk.chunk_id} chunk={chunk} index={i} />
            ))
          )}
        </div>
      )}
    </div>
  )
}
