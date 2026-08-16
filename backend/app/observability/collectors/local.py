"""Local trace collector storing traces in a bounded in-memory ring buffer and PostgreSQL."""
from __future__ import annotations

import collections
import logging
import statistics
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.observability.collectors.base import BaseTraceCollector
from app.observability.schema import RequestTrace

logger = logging.getLogger(__name__)


class LocalTraceCollector(BaseTraceCollector):
    """Local collector providing in-memory fast retrieval and PostgreSQL persistence."""

    def __init__(
        self,
        max_buffer_size: int = 1000,
        session_factory: Any = None,
    ) -> None:
        self._buffer: collections.deque[RequestTrace] = collections.deque(maxlen=max_buffer_size)
        self._session_factory = session_factory


    async def emit_trace(self, trace: RequestTrace) -> None:
        """Store trace in in-memory ring buffer and persist to PostgreSQL if DB available."""
        # 1. Store in memory buffer (thread-safe append on deque)
        self._buffer.append(trace)

        # 2. Persist to PostgreSQL if session factory is configured
        if self._session_factory is not None:
            try:
                from app.models.trace import PipelineTraceModel  # noqa: PLC0415

                async with self._session_factory() as session:
                    db_trace = PipelineTraceModel(
                        request_id=trace.request_id,
                        session_id=trace.session_id,
                        query_hash=trace.query_hash,
                        user_role=trace.user_role,
                        jurisdiction=trace.jurisdiction,
                        total_latency_ms=trace.total_latency_ms,
                        retrieval_latency_ms=trace.latency_breakdown_ms.get("retrieval.dense", 0.0)
                        + trace.latency_breakdown_ms.get("retrieval.bm25", 0.0),
                        reranker_latency_ms=trace.latency_breakdown_ms.get("reranking.cross_encoder", 0.0),
                        llm_latency_ms=trace.latency_breakdown_ms.get("generation.llm", 0.0),
                        top_reranker_score=trace.top_reranker_score,
                        input_tokens=trace.tokens_and_cost.input_tokens,
                        output_tokens=trace.tokens_and_cost.output_tokens,
                        estimated_cost_usd=trace.tokens_and_cost.estimated_cost_usd,
                        citation_count=trace.citation_count,
                        abstained=trace.abstained,
                        guardrail_blocked=trace.guardrail_blocked,
                        created_at=trace.created_at,
                    )
                    session.add(db_trace)
                    await session.commit()
            except Exception as exc:
                logger.warning("LocalTraceCollector: DB persist failed (continuing): %s", exc)

    async def flush(self) -> None:
        """No-op for local buffer."""
        pass

    def health_check(self) -> bool:
        """Local buffer is always healthy."""
        return True

    def get_recent(self, limit: int = 50) -> list[RequestTrace]:
        """Return the most recent N sanitized traces from the ring buffer (newest first)."""
        traces = list(self._buffer)
        traces.reverse()
        return traces[: max(1, limit)]

    def get_overview(self) -> dict[str, Any]:
        """Calculate aggregated KPI metrics across buffered traces."""
        traces = list(self._buffer)
        total_requests = len(traces)
        if total_requests == 0:
            return {
                "total_requests": 0,
                "latency_p50_ms": 0.0,
                "latency_p95_ms": 0.0,
                "latency_p99_ms": 0.0,
                "total_tokens": 0,
                "total_cost_usd": 0.0,
                "abstention_rate": 0.0,
                "guardrail_block_rate": 0.0,
                "mean_top_reranker_score": -0.230,
            }

        latencies = sorted([t.total_latency_ms for t in traces])
        reranker_scores = [t.top_reranker_score for t in traces if t.top_reranker_score is not None]

        def _percentile(data: list[float], pct: float) -> float:
            if not data:
                return 0.0
            idx = int(len(data) * pct)
            return data[min(idx, len(data) - 1)]

        p50 = _percentile(latencies, 0.50)
        p95 = _percentile(latencies, 0.95)
        p99 = _percentile(latencies, 0.99)

        total_tokens = sum(t.tokens_and_cost.total_tokens for t in traces)
        total_cost = sum(t.tokens_and_cost.estimated_cost_usd for t in traces)
        abstained_count = sum(1 for t in traces if t.abstained)
        blocked_count = sum(1 for t in traces if t.guardrail_blocked)
        mean_reranker = statistics.mean(reranker_scores) if reranker_scores else -0.230

        return {
            "total_requests": total_requests,
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "total_tokens": total_tokens,
            "total_cost_usd": round(total_cost, 6),
            "abstention_rate": round(abstained_count / total_requests, 4),
            "guardrail_block_rate": round(blocked_count / total_requests, 4),
            "mean_top_reranker_score": round(mean_reranker, 4),
        }
