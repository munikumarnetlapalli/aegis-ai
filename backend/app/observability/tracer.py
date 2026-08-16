"""AegisTracer — High-resolution monotonic RAG execution tracer.

Manages ContextVar-bound request traces and nested span measurements using
time.perf_counter_ns(). Tracing errors are isolated and never break user requests.
"""
from __future__ import annotations

import contextvars
import logging
import time
import uuid
from contextlib import contextmanager
from typing import Any, Generator

from app.observability.cost import calculate_token_cost
from app.observability.privacy import compute_query_hash, sanitize_trace_metadata
from app.observability.schema import PipelineSpan, RequestTrace

logger = logging.getLogger(__name__)

# ContextVar storing active RequestTrace across async tasks
_current_trace_var: contextvars.ContextVar[RequestTrace | None] = contextvars.ContextVar(
    "current_request_trace", default=None
)


class AegisTracer:
    """Singleton tracer for measuring end-to-end RAG pipeline telemetry."""

    def __init__(self, enabled: bool = True) -> None:
        self.enabled = enabled

    def start_trace(
        self,
        *,
        query: str,
        request_id: str | None = None,
        session_id: str | None = None,
        user_role: str | None = None,
        jurisdiction: str | None = None,
    ) -> RequestTrace:
        """Initialize and bind a new RequestTrace to the current async context."""
        req_id = request_id.strip() if request_id and request_id.strip() else str(uuid.uuid4())
        query_hash = compute_query_hash(query)

        trace = RequestTrace(
            request_id=req_id,
            session_id=session_id,
            query_hash=query_hash,
            user_role=user_role,
            jurisdiction=jurisdiction,
        )
        _current_trace_var.set(trace)
        return trace

    def get_current_trace(self) -> RequestTrace | None:
        """Return the active RequestTrace bound to the current context, or None."""
        return _current_trace_var.get()

    @contextmanager
    def span(
        self,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Generator[PipelineSpan | None, None, None]:
        """Context manager measuring monotonic duration of a single execution span.

        Guarantees:
        - Uses time.perf_counter_ns() for clock-drift immunity.
        - Sanitizes attached metadata.
        - Exception-isolated (will never raise if tracing fails).
        """
        if not self.enabled:
            yield None
            return

        trace = _current_trace_var.get()
        req_id = trace.request_id if trace else "unbound"
        span_obj = PipelineSpan(
            request_id=req_id,
            name=name,
            start_time_ns=time.perf_counter_ns(),
            end_time_ns=0,
            latency_ms=0.0,
            status="OK",
            metadata=sanitize_trace_metadata(metadata or {}),
        )

        try:
            yield span_obj
        except Exception as exc:
            span_obj.status = "ERROR"
            span_obj.metadata["error_type"] = type(exc).__name__
            raise
        finally:
            end_ns = time.perf_counter_ns()
            span_obj.end_time_ns = end_ns
            span_obj.latency_ms = round((end_ns - span_obj.start_time_ns) / 1_000_000.0, 3)
            # Re-sanitize metadata in case caller updated span_obj.metadata during execution
            span_obj.metadata = sanitize_trace_metadata(span_obj.metadata)

            if trace is not None:
                trace.spans.append(span_obj)
                trace.latency_breakdown_ms[name] = span_obj.latency_ms

    def record_llm_usage(
        self,
        *,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        token_source: str = "exact",
    ) -> None:
        """Record token usage and calculate estimated cost on current trace."""
        trace = _current_trace_var.get()
        if trace is None:
            return

        trace.tokens_and_cost = calculate_token_cost(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            token_source="exact" if token_source == "exact" else "estimated",
        )

    def finish_trace(
        self,
        *,
        retrieved_chunk_ids: list[str] | None = None,
        top_reranker_score: float | None = None,
        citation_count: int = 0,
        citation_status: str = "NONE",
        abstained: bool = False,
        guardrail_blocked: bool = False,
        error: str | None = None,
    ) -> RequestTrace | None:
        """Finalize and compute total latency for the current trace."""
        trace = _current_trace_var.get()
        if trace is None:
            return None

        if retrieved_chunk_ids:
            trace.retrieved_chunk_ids = [str(cid) for cid in retrieved_chunk_ids]
        if top_reranker_score is not None:
            trace.top_reranker_score = round(float(top_reranker_score), 4)

        trace.citation_count = max(0, citation_count)
        trace.citation_status = "PASS" if citation_status == "PASS" else ("FAIL" if citation_status == "FAIL" else "NONE")
        trace.abstained = abstained
        trace.guardrail_blocked = guardrail_blocked
        trace.error = error

        # Calculate total latency as sum of root spans or span breakdown
        if trace.spans:
            # Total latency is max span end - min span start, or sum of main stages
            min_start = min(s.start_time_ns for s in trace.spans)
            max_end = max(s.end_time_ns for s in trace.spans)
            trace.total_latency_ms = round((max_end - min_start) / 1_000_000.0, 3)
        else:
            trace.total_latency_ms = 0.0

        return trace


# Global singleton instance
_tracer_instance: AegisTracer | None = None


def get_tracer() -> AegisTracer:
    """Return the global AegisTracer singleton."""
    global _tracer_instance  # noqa: PLW0603
    if _tracer_instance is None:
        _tracer_instance = AegisTracer(enabled=True)
    return _tracer_instance
