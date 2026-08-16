"""Chunk ORM model with pgvector embedding column.

Every chunk must have full provenance (document_id, page, section, jurisdiction,
allowed_roles).  A chunk without complete provenance MUST NOT be indexed —
it can never be cited and therefore has no value in the pipeline.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    from sqlalchemy.types import UserDefinedType

    class Vector(UserDefinedType):  # type: ignore[no-redef]
        def __init__(self, dim=None):
            self.dim = dim

from sqlalchemy import (
    ARRAY,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.document import Document


class Chunk(Base):
    """A single text chunk derived from a document, with embedding and provenance."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Provenance (non-negotiable — every chunk must carry all of these) ─────
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_version: Mapped[str] = mapped_column(
        String(64), nullable=False, default="1"
    )
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    section: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    jurisdiction: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, default="GLOBAL"
    )
    allowed_roles: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Content ───────────────────────────────────────────────────────────────
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Embedding (dimension configured in settings; default 384 for MiniLM) ─
    # The dimension here MUST match the embedding model in Settings.embedding_dim.
    # Changing it requires a new Alembic migration.
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="chunks")

    def __repr__(self) -> str:
        return (
            f"<Chunk id={self.id} doc={self.document_id} "
            f"page={self.page} idx={self.chunk_index}>"
        )
