/**
 * API service layer — all network calls live here, never in presentation components.
 *
 * Handles:
 * - JWT authentication token persistence and header injection
 * - Health checks
 * - Document upload, listing, chunk inspection, and deletion
 * - Grounded Q&A /answer calls with citation validation and abstention metadata
 * - Raw vector/BM25 /query search
 */

import type { UserProfile, TokenResponse } from '../types/auth'
import type { AnswerResponse, Citation } from '../types/chat'
import type {
  DocumentItem,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentChunkItem,
  DocumentChunksResponse,
  DocumentDeleteResponse,
} from '../types/documents'

export type {
  UserProfile,
  TokenResponse,
  AnswerResponse,
  Citation,
  DocumentItem,
  DocumentListResponse,
  DocumentUploadResponse,
  DocumentChunkItem,
  DocumentChunksResponse,
  DocumentDeleteResponse,
}

const API_BASE =
  ((import.meta as unknown as { env?: { VITE_API_BASE_URL?: string } }).env
    ?.VITE_API_BASE_URL) ?? ''

const TOKEN_KEY = 'aegis_auth_token'
const USER_KEY = 'aegis_user_profile'

// ── Auth Token Management ──────────────────────────────────────────────────────

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function getStoredUser(): UserProfile | null {
  const data = localStorage.getItem(USER_KEY)
  if (!data) return null
  try {
    return JSON.parse(data) as UserProfile
  } catch {
    return null
  }
}

export function setStoredUser(user: UserProfile): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearStoredAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

/** Helper to build request headers with optional Bearer token */
function getAuthHeaders(isJson: boolean = true): Record<string, string> {
  const headers: Record<string, string> = {}
  if (isJson) {
    headers['Content-Type'] = 'application/json'
  }
  const token = getStoredToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

// ── Authentication API ─────────────────────────────────────────────────────────

export async function loginUser(email: string, password: string): Promise<TokenResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Login failed' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Login failed: ${res.status}`)
  }

  const tokenData = (await res.json()) as TokenResponse
  setStoredToken(tokenData.access_token)
  setStoredUser({
    id: tokenData.user_id,
    email: tokenData.email,
    role: tokenData.role,
    jurisdiction: tokenData.jurisdiction,
    is_active: true,
  })
  return tokenData
}

export async function registerUser(
  email: string,
  password: string,
  jurisdiction: string = 'GLOBAL'
): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, jurisdiction }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Registration failed' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Registration failed: ${res.status}`)
  }

  return res.json() as Promise<UserProfile>
}

export async function getCurrentUser(): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: getAuthHeaders(true),
  })

  if (!res.ok) {
    clearStoredAuth()
    throw new Error('Session expired or unauthorized')
  }

  const profile = (await res.json()) as UserProfile
  setStoredUser(profile)
  return profile
}

// ── Health API ─────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'healthy' | 'unhealthy'
  database: 'connected' | 'unreachable'
  version: string
}

export async function healthCheck(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok && res.status !== 503) {
    throw new Error(`Unexpected status ${res.status}`)
  }
  return res.json() as Promise<HealthResponse>
}

// ── Document Management API ────────────────────────────────────────────────────

export async function listDocuments(): Promise<DocumentListResponse> {
  const res = await fetch(`${API_BASE}/documents`, {
    headers: getAuthHeaders(true),
  })
  if (!res.ok) {
    throw new Error(`Failed to list documents: ${res.status}`)
  }
  return res.json() as Promise<DocumentListResponse>
}

export async function uploadDocument(
  file: File,
  jurisdiction: string = 'GLOBAL',
  allowedRoles: string = ''
): Promise<DocumentUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('jurisdiction', jurisdiction)
  formData.append('allowed_roles', allowedRoles)

  const headers = getAuthHeaders(false)

  const res = await fetch(`${API_BASE}/documents`, {
    method: 'POST',
    headers,
    body: formData,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Upload failed' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Upload failed: ${res.status}`)
  }

  return res.json() as Promise<DocumentUploadResponse>
}

export async function getDocumentChunks(documentId: string): Promise<DocumentChunksResponse> {
  const res = await fetch(`${API_BASE}/documents/${documentId}/chunks`, {
    headers: getAuthHeaders(true),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Failed to fetch chunks' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Failed to fetch chunks: ${res.status}`)
  }

  return res.json() as Promise<DocumentChunksResponse>
}

export async function deleteDocument(documentId: string): Promise<DocumentDeleteResponse> {
  const res = await fetch(`${API_BASE}/documents/${documentId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(true),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Failed to delete document' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Failed to delete document: ${res.status}`)
  }

  return res.json() as Promise<DocumentDeleteResponse>
}

// ── Q&A Answer API (M3/M4/M5) ──────────────────────────────────────────────────

export async function answerQuery(
  query: string,
  topK: number = 5,
  jurisdiction?: string
): Promise<AnswerResponse> {
  const payload: Record<string, unknown> = {
    query,
    top_k: topK,
  }
  if (jurisdiction) {
    payload['jurisdiction'] = jurisdiction
  }

  const res = await fetch(`${API_BASE}/answer`, {
    method: 'POST',
    headers: getAuthHeaders(true),
    body: JSON.stringify(payload),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Answer generation failed' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Answer query failed: ${res.status}`)
  }

  return res.json() as Promise<AnswerResponse>
}

// ── Raw Query API (M2) ─────────────────────────────────────────────────────────

export interface Provenance {
  document_id: string
  filename: string
  page: number
  section: string
  jurisdiction: string
  chunk_index: number
}

export interface ChunkResult {
  chunk_id: string
  content: string
  score: number
  provenance: Provenance
}

export interface QueryResponse {
  query: string
  results: ChunkResult[]
  result_count: number
  message: string
}

export async function queryDocuments(
  query: string,
  jurisdiction?: string,
  topK: number = 10
): Promise<QueryResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: getAuthHeaders(true),
    body: JSON.stringify({ query, jurisdiction: jurisdiction || null, top_k: topK }),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Query failed' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Query failed: ${res.status}`)
  }

  return res.json() as Promise<QueryResponse>
}

// ── Observability & Telemetry API (M7) ─────────────────────────────────────────

import type {
  ObservabilityOverview,
  DriftReport,
  RequestTrace,
} from '../types/observability'

export type { ObservabilityOverview, DriftReport, RequestTrace }

export async function getObservabilityOverview(): Promise<ObservabilityOverview> {
  const res = await fetch(`${API_BASE}/observability/overview`, {
    method: 'GET',
    headers: getAuthHeaders(false),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Failed to fetch observability overview' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Observability overview failed: ${res.status}`)
  }

  return res.json() as Promise<ObservabilityOverview>
}

export async function getDriftReport(thresholdPct?: number): Promise<DriftReport> {
  const url = thresholdPct
    ? `${API_BASE}/observability/drift?threshold_pct=${thresholdPct}`
    : `${API_BASE}/observability/drift`

  const res = await fetch(url, {
    method: 'GET',
    headers: getAuthHeaders(false),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Failed to fetch drift report' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Drift report failed: ${res.status}`)
  }

  return res.json() as Promise<DriftReport>
}

export async function getRecentTraces(limit = 50): Promise<RequestTrace[]> {
  const res = await fetch(`${API_BASE}/observability/recent?limit=${limit}`, {
    method: 'GET',
    headers: getAuthHeaders(false),
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: { message: 'Failed to fetch recent traces' } }))
    const msg = typeof err.detail === 'object' ? err.detail.message : err.detail
    throw new Error(msg ?? `Recent traces failed: ${res.status}`)
  }

  return res.json() as Promise<RequestTrace[]>
}

