"""Abstract interface for M7 trace and telemetry collectors."""
from __future__ import annotations

from abc import ABC, abstractmethod

from app.observability.schema import RequestTrace


class BaseTraceCollector(ABC):
    """Interface that all trace and telemetry collectors must implement."""

    @abstractmethod
    async def emit_trace(self, trace: RequestTrace) -> None:
        """Emit a completed and sanitized RequestTrace to the collector."""
        ...

    @abstractmethod
    async def flush(self) -> None:
        """Flush any pending buffered traces."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if collector is healthy and reachable."""
        ...
