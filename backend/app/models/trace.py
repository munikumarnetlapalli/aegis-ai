"""Pipeline trace ORM model for M7 persistent observability."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PipelineTraceModel(Base):
    """Stores sanitized telemetry traces for historical analysis and drift detection.

    GUARANTEE: Raw user queries, chunk contents, prompts, secrets, and raw PII are NEVER stored.
    """

    __tablename__ = "pipeline_traces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(64), nullable=True)

    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    retrieval_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reranker_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    llm_latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    top_reranker_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    citation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    abstained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    guardrail_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
