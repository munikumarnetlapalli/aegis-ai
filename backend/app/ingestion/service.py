"""Ingestion service — orchestrates the full document pipeline.

Pipeline:
  Upload → Validate → Insert Document row → Parse → Chunk
         → Embed (batch) → Bulk-insert Chunks → Mark indexed

Route handlers call only this service — they must not call the parser,
chunker, or embedding provider directly.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.ingestion.chunker import Chunker
from app.ingestion.embedding import get_embedding_provider
from app.ingestion.normalizer import normalize_unicode_text
from app.ingestion.parser import DocumentParser
from app.models.chunk import Chunk
from app.models.document import Document

logger = logging.getLogger(__name__)


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class DocumentIngestionResult:
    document_id: uuid.UUID
    filename: str
    status: str
    chunk_count: int
    page_count: int


@dataclass
class IngestionError:
    """Structured ingestion error returned instead of raising in some contexts."""
    message: str
    detail: str = ""


# ── Ingestion service ─────────────────────────────────────────────────────────

class IngestionService:
    """Orchestrates document ingestion end-to-end."""

    def __init__(self) -> None:
        self._parser = DocumentParser()
        settings = get_settings()
        self._chunker = Chunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )

    async def ingest(
        self,
        *,
        file_bytes: bytes,
        filename: str,
        content_type: str,
        jurisdiction: str,
        allowed_roles: list[str],
        db: AsyncSession,
    ) -> DocumentIngestionResult:
        """Ingest a document: validate, parse, chunk, embed, and index.

        Raises ValueError for invalid input.
        All other exceptions are caught, logged, and re-raised after marking
        the document as 'failed' in the database.
        """
        settings = get_settings()
        self._validate(file_bytes, filename, settings)

        # ── 1. Insert Document row ────────────────────────────────────────────
        document = Document(
            filename=filename,
            content_type=content_type,
            jurisdiction=jurisdiction,
            allowed_roles=allowed_roles,
            status="processing",
        )
        db.add(document)
        await db.flush()  # get the generated ID without committing
        doc_id = document.id
        logger.info("Ingesting document %s (%r)", doc_id, filename)

        try:
            # ── 2. Parse ──────────────────────────────────────────────────────
            parse_result = self._parser.parse(file_bytes, filename, content_type)
            if not parse_result.pages:
                raise ValueError(f"No content extracted from {filename!r}")

            document.page_count = parse_result.page_count

            # ── 3. Chunk ──────────────────────────────────────────────────────
            raw_chunks = self._chunker.chunk_pages(parse_result.pages)
            if not raw_chunks:
                raise ValueError(f"Chunker produced zero chunks for {filename!r}")

            logger.info(
                "Document %s: %d pages → %d chunks",
                doc_id,
                parse_result.page_count,
                len(raw_chunks),
            )

            # ── 4. Embed in batches ───────────────────────────────────────────
            provider = get_embedding_provider()
            batch_size = 64
            texts = [c.content for c in raw_chunks]
            embeddings: list[list[float]] = []

            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                embeddings.extend(provider.embed_documents(batch))

            # ── 5. Bulk-insert Chunk rows ─────────────────────────────────────
            # Every chunk MUST have complete provenance — validation is implicit
            # because all fields are sourced from the document and chunk metadata.
            chunk_models = [
                Chunk(
                    document_id=doc_id,
                    document_version="1",
                    filename=normalize_unicode_text(filename),
                    page=rc.page,
                    section=normalize_unicode_text(rc.section),
                    jurisdiction=jurisdiction,
                    allowed_roles=allowed_roles,
                    chunk_index=rc.chunk_index,
                    content=normalize_unicode_text(rc.content),
                    embedding=embedding,
                )
                for rc, embedding in zip(raw_chunks, embeddings)
            ]
            db.add_all(chunk_models)

            # ── 6. Mark indexed ───────────────────────────────────────────────
            document.status = "indexed"
            document.chunk_count = len(chunk_models)
            await db.commit()

            logger.info(
                "Document %s indexed successfully: %d chunks",
                doc_id,
                len(chunk_models),
            )
            return DocumentIngestionResult(
                document_id=doc_id,
                filename=filename,
                status="indexed",
                chunk_count=len(chunk_models),
                page_count=parse_result.page_count,
            )

        except Exception as exc:
            logger.exception("Ingestion failed for document %s: %s", doc_id, exc)
            document.status = "failed"
            document.error_message = str(exc)
            await db.commit()
            raise

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _validate(file_bytes: bytes, filename: str, settings) -> None:
        """Validate file size and extension before any processing."""
        if len(file_bytes) > settings.upload_max_bytes:
            raise ValueError(
                f"File too large: {len(file_bytes) / 1024 / 1024:.1f} MB "
                f"(max {settings.upload_max_mb} MB)"
            )
        ext = os.path.splitext(filename.lower())[1]
        if ext not in settings.allowed_extensions:
            raise ValueError(
                f"Unsupported file type: {ext!r}.  "
                f"Allowed: {settings.allowed_extensions}"
            )
