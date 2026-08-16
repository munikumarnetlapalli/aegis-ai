"""M7 Observability Pydantic schemas for spans, traces, costs, and drift."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


class PipelineSpan(BaseModel):
    """An individual operation span within a RAG execution trace."""

    span_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str
    name: str = Field(
        description="Span identifier (e.g., 'security.guardrail', 'retrieval.dense', 'generation.llm')"
    )
    start_time_ns: int = Field(description="Monotonic start timestamp in nanoseconds.")
    end_time_ns: int = Field(description="Monotonic end timestamp in nanoseconds.")
    latency_ms: float = Field(description="Elapsed duration in milliseconds.")
    status: Literal["OK", "ERROR", "BLOCKED", "SKIPPED"] = "OK"
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized metadata dictionary (NO raw queries, chunks, prompts, or PII).",
    )


class TokenCostSummary(BaseModel):
    """Token consumption and estimated USD cost for model execution."""

    provider: str = "unknown"
    model: str = "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    input_cost_usd: float = 0.0
    output_cost_usd: float = 0.0
    estimated_cost_usd: float = 0.0
    token_source: Literal["exact", "estimated"] = "exact"


class RequestTrace(BaseModel):
    """Complete sanitized end-to-end trace for a query interaction."""

    request_id: str
    session_id: str | None = None
    query_hash: str = Field(
        description="Deterministic SHA-256 hex digest of the normalized query. Raw query is NEVER stored."
    )
    user_role: str | None = None
    jurisdiction: str | None = None
    total_latency_ms: float = 0.0
    spans: list[PipelineSpan] = Field(default_factory=list)
    latency_breakdown_ms: dict[str, float] = Field(default_factory=dict)
    tokens_and_cost: TokenCostSummary = Field(default_factory=TokenCostSummary)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    top_reranker_score: float | None = None
    citation_count: int = 0
    citation_status: Literal["PASS", "FAIL", "NONE"] = "NONE"
    abstained: bool = False
    guardrail_blocked: bool = False
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MetricDriftItem(BaseModel):
    """Statistical drift comparison for a single evaluation metric."""

    metric_name: str
    baseline_value: float
    current_value: float
    delta: float
    delta_pct: float
    threshold_pct: float = 5.0
    drift_detected: bool
    status: Literal["STABLE", "DRIFT_ALERT", "INSUFFICIENT_DATA"]
    direction: Literal["higher_is_better", "lower_is_better", "range_bound"] = "higher_is_better"


class DriftReport(BaseModel):
    """System-wide drift assessment comparing active metrics to the M6 baseline."""

    report_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_version: str = "v1.0-m6"
    sample_count: int = 0
    min_samples_required: int = 10
    metrics: list[MetricDriftItem] = Field(default_factory=list)
    overall_drift_status: Literal["HEALTHY", "WARNING", "DRIFT_DETECTED", "INSUFFICIENT_DATA"] = "HEALTHY"
