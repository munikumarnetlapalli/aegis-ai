/**
 * M7 Observability, Tracing, and Drift types.
 */

export interface ObservabilityOverview {
  total_requests: number
  latency_p50_ms: number
  latency_p95_ms: number
  latency_p99_ms: number
  total_tokens: number
  total_cost_usd: number
  abstention_rate: number
  guardrail_block_rate: number
  mean_top_reranker_score: number
}

export interface MetricDriftItem {
  metric_name: string
  baseline_value: number
  current_value: number
  delta: number
  delta_pct: number
  threshold_pct: number
  drift_detected: boolean
  status: 'STABLE' | 'DRIFT_ALERT' | 'INSUFFICIENT_DATA'
  direction: 'higher_is_better' | 'lower_is_better' | 'range_bound'
}

export interface DriftReport {
  report_timestamp: string
  baseline_version: string
  sample_count: number
  min_samples_required: number
  metrics: MetricDriftItem[]
  overall_drift_status: 'HEALTHY' | 'WARNING' | 'DRIFT_DETECTED' | 'INSUFFICIENT_DATA'
}

export interface PipelineSpan {
  span_id: string
  request_id: string
  name: string
  start_time_ns: number
  end_time_ns: number
  latency_ms: number
  status: 'OK' | 'ERROR' | 'BLOCKED' | 'SKIPPED'
  metadata: Record<string, any>
}

export interface RequestTrace {
  request_id: string
  session_id?: string | null
  query_hash: string
  user_role?: string | null
  jurisdiction?: string | null
  total_latency_ms: number
  spans: PipelineSpan[]
  latency_breakdown_ms: Record<string, number>
  tokens_and_cost: {
    provider: string
    model: string
    input_tokens: number
    output_tokens: number
    total_tokens: number
    estimated_cost_usd: number
  }
  retrieved_chunk_ids: string[]
  top_reranker_score?: number | null
  citation_count: number
  citation_status: 'PASS' | 'FAIL' | 'NONE'
  abstained: boolean
  guardrail_blocked: boolean
  created_at: string
}
