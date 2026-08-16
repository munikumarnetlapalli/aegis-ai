"""Optional Arize Phoenix collector for retrieval and drift monitoring.

Emits non-blocking HTTP telemetry payloads to Phoenix server if configured.
"""
from __future__ import annotations

import logging
import httpx

from app.observability.collectors.base import BaseTraceCollector
from app.observability.schema import RequestTrace

logger = logging.getLogger(__name__)


class PhoenixCollector(BaseTraceCollector):
    """Arize Phoenix collector emitting structured RAG spans over HTTP."""

    def __init__(self, host: str | None = None, timeout: float = 1.0) -> None:
        self.host = host.rstrip("/") if host else None
        self.timeout = timeout
        self._enabled = bool(self.host)
        if self._enabled:
            logger.info("Phoenix collector configured @ %s", self.host)

    async def emit_trace(self, trace: RequestTrace) -> None:
        """Send sanitized trace metadata to Phoenix endpoint without blocking."""
        if not self._enabled or not self.host:
            return

        payload = {
            "trace_id": trace.request_id,
            "name": "aegis_rag_query",
            "attributes": {
                "query_hash": trace.query_hash,
                "role": trace.user_role,
                "jurisdiction": trace.jurisdiction,
                "total_latency_ms": trace.total_latency_ms,
                "input_tokens": trace.tokens_and_cost.input_tokens,
                "output_tokens": trace.tokens_and_cost.output_tokens,
                "estimated_cost_usd": trace.tokens_and_cost.estimated_cost_usd,
                "top_reranker_score": trace.top_reranker_score,
                "citation_count": trace.citation_count,
                "abstained": trace.abstained,
                "guardrail_blocked": trace.guardrail_blocked,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                await client.post(f"{self.host}/v1/traces", json=payload)
        except Exception as exc:
            logger.debug("Phoenix trace emission skipped/failed: %s", exc)

    async def flush(self) -> None:
        pass

    def health_check(self) -> bool:
        return self._enabled
