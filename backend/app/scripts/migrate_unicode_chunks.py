"""Safe in-place Unicode normalization migration for existing PostgreSQL chunks and documents.

Requirement 8 & 9:
- Existing indexed data is NOT deleted or dropped.
- In-place repair of mojibake, PUA characters, and double-encoded text across chunks and documents.
- Preserves primary keys, embeddings, timestamps, and foreign key relationships.

Usage:
    python -m app.scripts.migrate_unicode_chunks
"""
from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.ingestion.normalizer import normalize_unicode_text
from app.models.chunk import Chunk
from app.models.document import Document

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aegis.migrate_unicode")


async def migrate_unicode_data(db: AsyncSession) -> dict[str, int]:
    """Inspect and normalize all existing chunk content, section provenance, and filenames."""
    stats = {
        "documents_checked": 0,
        "documents_updated": 0,
        "chunks_checked": 0,
        "chunks_updated": 0,
    }

    # ── 1. Migrate documents ──────────────────────────────────────────────────
    doc_stmt = select(Document)
    docs = (await db.execute(doc_stmt)).scalars().all()
    stats["documents_checked"] = len(docs)

    for doc in docs:
        norm_filename = normalize_unicode_text(doc.filename)
        if norm_filename != doc.filename:
            logger.info("Normalizing document %s filename: %r -> %r", doc.id, doc.filename, norm_filename)
            doc.filename = norm_filename
            stats["documents_updated"] += 1

    # ── 2. Migrate chunks ─────────────────────────────────────────────────────
    chunk_stmt = select(Chunk)
    chunks = (await db.execute(chunk_stmt)).scalars().all()
    stats["chunks_checked"] = len(chunks)

    for chunk in chunks:
        changed = False

        norm_content = normalize_unicode_text(chunk.content)
        if norm_content != chunk.content:
            chunk.content = norm_content
            changed = True

        if chunk.section:
            norm_section = normalize_unicode_text(chunk.section)
            if norm_section != chunk.section:
                chunk.section = norm_section
                changed = True

        norm_filename = normalize_unicode_text(chunk.filename)
        if norm_filename != chunk.filename:
            chunk.filename = norm_filename
            changed = True

        if changed:
            stats["chunks_updated"] += 1

    if stats["chunks_updated"] > 0 or stats["documents_updated"] > 0:
        await db.commit()
        logger.info(
            "Migration complete: %d chunks updated, %d documents updated",
            stats["chunks_updated"],
            stats["documents_updated"],
        )
    else:
        logger.info("All existing chunks and documents are already clean and normalized.")

    return stats


async def main() -> None:
    logger.info("Starting safe in-place Unicode normalization migration...")
    async with AsyncSessionLocal() as db:
        stats = await migrate_unicode_data(db)
        print("\n=== Unicode Migration Summary ===")
        print(f"Documents checked: {stats['documents_checked']}")
        print(f"Documents updated: {stats['documents_updated']}")
        print(f"Chunks checked:    {stats['chunks_checked']}")
        print(f"Chunks updated:    {stats['chunks_updated']}")
        print("=================================\n")


if __name__ == "__main__":
    asyncio.run(main())
