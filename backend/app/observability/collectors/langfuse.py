"""Optional Langfuse trace collector for cloud/self-hosted LLM observability.

Observability failure must not break the request. The application remains
fully functional if Langfuse is unreachable or uninstalled.
"""
from __future__ import annotations

import logging

from app.observability.collectors.base import BaseTraceCollector
from app.observability.schema import RequestTrace

logger = logging.getLogger(__name__)


class LangfuseCollector(BaseTraceCollector):
    """Langfuse trace collector with non-blocking graceful degradation."""

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host or "http://localhost:3010"
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        """Attempt to initialize Langfuse SDK if credentials are present."""
        if not (self.public_key and self.secret_key):
            logger.debug("Langfuse credentials not configured — collector disabled.")
            return

        try:
            from langfuse import Langfuse  # noqa: PLC0415

            self._client = Langfuse(
                public_key=self.public_key,
                secret_key=self.secret_key,
                host=self.host,
            )
            logger.info("Langfuse collector initialized @ %s", self.host)
        except Exception as exc:
            logger.warning("Langfuse initialization failed: %s (continuing without Langfuse)", exc)
            self._client = None

    async def emit_trace(self, trace: RequestTrace) -> None:
        """Emit sanitized trace to Langfuse without blocking."""
        if self._client is None:
            return

        try:
            # Langfuse trace payload uses query_hash, NEVER raw query
            self._client.trace(
                id=trace.request_id,
                name="rag_answer",
                session_id=trace.session_id,
                user_id=trace.user_role,
                metadata={
                    "query_hash": trace.query_hash,
                    "jurisdiction": trace.jurisdiction,
                    "latency_ms": trace.total_latency_ms,
                    "tokens": trace.tokens_and_cost.total_tokens,
                    "cost_usd": trace.tokens_and_cost.estimated_cost_usd,
                    "citations": trace.citation_count,
                    "abstained": trace.abstained,
                    "guardrail_blocked": trace.guardrail_blocked,
                },
            )
        except Exception as exc:
            logger.warning("Langfuse trace emission failed: %s (ignoring)", exc)

    async def flush(self) -> None:
        if self._client is not None:
            try:
                self._client.flush()
            except Exception as exc:
                logger.warning("Langfuse flush failed: %s", exc)

    def health_check(self) -> bool:
        return self._client is not None
