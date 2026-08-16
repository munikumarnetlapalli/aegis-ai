/**
 * Document management and chunk inspection types.
 */

export interface DocumentItem {
  document_id: string
  filename: string
  content_type: string
  jurisdiction: string
  allowed_roles: string[]
  status: 'pending' | 'processing' | 'indexed' | 'failed'
  chunk_count: number | null
  page_count: number | null
  created_at: string
}

export interface DocumentListResponse {
  documents: DocumentItem[]
  total: number
}

export interface DocumentUploadResponse {
  document_id: string
  filename: string
  status: string
  chunk_count: number
  page_count: number
  message: string
}

export interface DocumentChunkItem {
  chunk_id: string
  document_id: string
  filename: string
  chunk_index: number
  page: number
  section: string
  jurisdiction: string
  allowed_roles: string[]
  content: string
  char_count: number
}

export interface DocumentChunksResponse {
  document_id: string
  filename: string
  total_chunks: number
  chunks: DocumentChunkItem[]
}

export interface DocumentDeleteResponse {
  document_id: string
  filename: string
  deleted: boolean
  message: string
}
