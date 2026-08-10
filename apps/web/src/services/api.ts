/**
 * API service layer — all network calls live here, never in components.
 *
 * Components must use TanStack Query hooks that call these functions.
 * Never put fetch() calls directly in React components.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export interface HealthResponse {
  status: 'healthy' | 'unhealthy'
  database: 'connected' | 'unreachable'
  version: string
}

/**
 * Check backend health.
 * Calls GET /health and returns the structured response.
 * Throws on network error or non-2xx/5xx response.
 */
export async function healthCheck(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`)

  if (!res.ok && res.status !== 503) {
    throw new Error(`Unexpected status ${res.status}`)
  }

  const data = await res.json()
  return data as HealthResponse
}
