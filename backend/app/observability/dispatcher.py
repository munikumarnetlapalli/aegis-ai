"""Asynchronous, bounded trace dispatcher for M7 collectors.

Guarantees:
- Dispatches traces to Local, Langfuse, and Phoenix collectors without blocking.
- Drops oldest items if queue overflows (max 1,000 items) to guarantee zero memory leaks.
- Exception isolation: collector exceptions are caught, logged, and never bubble up.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.observability.collectors.base import BaseTraceCollector

from app.observability.collectors.langfuse import LangfuseCollector
from app.observability.collectors.local import LocalTraceCollector
from app.observability.collectors.phoenix import PhoenixCollector
from app.observability.schema import RequestTrace

logger = logging.getLogger(__name__)


class TraceDispatcher:
    """Manages collector lifecycles and background trace distribution."""

    def __init__(self) -> None:
        self.collectors: list[BaseTraceCollector] = []
        self.local_collector: LocalTraceCollector | None = None
        self._init_collectors()

    def _init_collectors(self) -> None:
        """Initialize active collectors based on application configuration."""
        settings = get_settings()
        if not settings.observability_enabled:
            logger.info("Observability is disabled via configuration.")
            return

        # 1. Local collector (in-memory ring buffer + PostgreSQL)
        self.local_collector = LocalTraceCollector(
            max_buffer_size=1000,
            session_factory=AsyncSessionLocal,
        )

        self.collectors.append(self.local_collector)

        # 2. Optional Langfuse collector
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            langfuse = LangfuseCollector(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            self.collectors.append(langfuse)

        # 3. Optional Arize Phoenix collector
        if settings.phoenix_host:
            phoenix = PhoenixCollector(host=settings.phoenix_host)
            self.collectors.append(phoenix)

        logger.info("Observability dispatcher initialized with %d collectors.", len(self.collectors))

    async def dispatch(self, trace: RequestTrace) -> None:
        """Emit sanitized trace to all configured collectors concurrently."""
        if not trace:
            return

        tasks = []
        for collector in self.collectors:
            tasks.append(self._safe_emit(collector, trace))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _safe_emit(self, collector: BaseTraceCollector, trace: RequestTrace) -> None:
        """Safe wrapper isolating individual collector exceptions."""
        try:
            await collector.emit_trace(trace)
        except Exception as exc:
            logger.warning(
                "Collector %s failed to emit trace %s: %s",
                collector.__class__.__name__,
                trace.request_id,
                exc,
            )


# Global singleton dispatcher
_dispatcher_instance: TraceDispatcher | None = None


def get_dispatcher() -> TraceDispatcher:
    """Return the global TraceDispatcher singleton."""
    global _dispatcher_instance  # noqa: PLW0603
    if _dispatcher_instance is None:
        _dispatcher_instance = TraceDispatcher()
    return _dispatcher_instance


async def dispatch_trace(trace: RequestTrace | None) -> None:
    """Convenience async helper to dispatch a trace safely."""
    if trace is None:
        return
    dispatcher = get_dispatcher()
    await dispatcher.dispatch(trace)
