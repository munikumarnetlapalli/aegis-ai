/**
 * Chat, Citation, and Generation types for M5.
 */

export interface Citation {
  citation_number: number
  chunk_id: string
  filename: string
  section: string
  page: number
  excerpt: string
}

export type ConfidenceLevel = 'high' | 'medium' | 'low'

export interface AnswerTelemetry {
  request_id: string
  total_latency_ms: number
  retrieval_latency_ms: number
  llm_latency_ms: number
  latency_breakdown_ms?: Record<string, number>
  token_usage?: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
  }
  estimated_cost_usd: number
}

export interface AnswerResponse {
  query: string
  answer: string
  citations: Citation[]
  confidence: ConfidenceLevel
  abstained: boolean
  evidence_count: number
  telemetry?: AnswerTelemetry
}

export interface ChatMessage {
  id: string
  sender: 'user' | 'assistant'
  content: string
  timestamp: string
  citations?: Citation[]
  confidence?: ConfidenceLevel
  abstained?: boolean
  evidenceCount?: number
  isStreaming?: boolean
  error?: string
  telemetry?: AnswerTelemetry
}


export interface ChatSession {
  id: string
  title: string
  createdAt: string
  messages: ChatMessage[]
}
