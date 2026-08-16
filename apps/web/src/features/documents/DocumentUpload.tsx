import { useState, useRef } from 'react'
import { uploadDocument, type DocumentUploadResponse } from '../../services/api'

interface Props {
  onSuccess: () => void
}

export function DocumentUpload({ onSuccess }: Props) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<DocumentUploadResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [jurisdiction, setJurisdiction] = useState('GLOBAL')
  const [roles, setRoles] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = async (file: File) => {
    setUploading(true)
    setResult(null)
    setError(null)
    try {
      const res = await uploadDocument(file, jurisdiction, roles)
      setResult(res)
      onSuccess()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <div className="upload-card">
      <h2 className="upload-title">Upload Document</h2>

      <div className="upload-meta">
        <label className="meta-label" htmlFor="jurisdiction-select">
          Jurisdiction
        </label>
        <select
          id="jurisdiction-select"
          className="meta-select"
          value={jurisdiction}
          onChange={(e) => setJurisdiction(e.target.value)}
        >
          <option value="GLOBAL">GLOBAL</option>
          <option value="EU">EU</option>
          <option value="US">US</option>
          <option value="HIPAA">HIPAA</option>
          <option value="UK">UK</option>
        </select>

        <label className="meta-label" htmlFor="roles-input">
          Allowed Roles <span className="meta-hint">(comma-separated)</span>
        </label>
        <input
          id="roles-input"
          className="meta-input"
          type="text"
          placeholder="admin, analyst (blank = all roles)"
          value={roles}
          onChange={(e) => setRoles(e.target.value)}
        />
      </div>

      <div
        id="drop-zone"
        className={`drop-zone ${dragging ? 'drop-zone--active' : ''} ${uploading ? 'drop-zone--uploading' : ''}`}
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        role="button"
        tabIndex={0}
        aria-label="Drop zone for document upload"
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.html,.txt"
          style={{ display: 'none' }}
          onChange={onFileChange}
          id="file-input"
        />
        {uploading ? (
          <div className="drop-content">
            <div className="spinner" />
            <p>Processing document…</p>
          </div>
        ) : (
          <div className="drop-content">
            <div className="drop-icon">📄</div>
            <p className="drop-label">
              {dragging ? 'Drop to upload' : 'Drag & drop or click to select'}
            </p>
            <p className="drop-hint">PDF, DOCX, HTML, TXT — max 50 MB</p>
          </div>
        )}
      </div>

      {result && (
        <div className="upload-result upload-result--success">
          <span className="result-icon">✓</span>
          <div>
            <strong>{result.filename}</strong> indexed successfully
            <div className="result-meta">
              {result.chunk_count} chunks · {result.page_count} pages
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="upload-result upload-result--error">
          <span className="result-icon">✗</span>
          <div>{error}</div>
        </div>
      )}
    </div>
  )
}
