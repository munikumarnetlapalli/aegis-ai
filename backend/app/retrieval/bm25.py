"""BM25 sparse retrieval — in-memory, backed by rank_bm25.

Complements dense pgvector retrieval for M3 hybrid pipeline.

Design decisions:
- In-memory index: rebuilt from the filtered chunk set on every call.
  Fast enough for M3 document sets (< 50k chunks) and keeps the DB as
  the single source of truth.  Swap to pg ts_vector / Elasticsearch later
  without changing the public interface.
- Authorization filters (jurisdiction, allowed_roles) are applied in SQL,
  exactly the same contract as the dense retriever.  Unauthorized content
  never reaches the BM25 index.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.service import Provenance, RetrievalResult

logger = logging.getLogger(__name__)

# Simple whitespace + punctuation tokeniser — good enough for BM25.
_TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")


def _tokenise(text_: str) -> list[str]:
    return _TOKEN_RE.findall(text_.lower())


class BM25Retriever:
    """Retrieve document chunks using BM25 sparse scoring.

    Authorization rule (non-negotiable):
        Jurisdiction and role filters are applied INSIDE the SQL query.
        The BM25 index is only built over chunks the caller is allowed to see.
    """

    async def retrieve(
        self,
        *,
        query: str,
        jurisdiction: str | None = None,
        allowed_roles: list[str] | None = None,
        top_k: int = 20,
        db: AsyncSession,
    ) -> list[RetrievalResult]:
        """Return the top-k chunks ranked by BM25 score.

        Parameters mirror those of RetrievalService.retrieve() for a
        consistent interface across retrieval backends.
        """
        # ── 1. Load authorized chunks from DB ─────────────────────────────────
        where_clauses: list[str] = ["c.content IS NOT NULL"]
        params: dict = {}

        if jurisdiction:
            where_clauses.append(
                "(c.jurisdiction = :jurisdiction OR c.jurisdiction = 'GLOBAL')"
            )
            params["jurisdiction"] = jurisdiction

        if allowed_roles:
            where_clauses.append(
                "(c.allowed_roles = '{}' OR c.allowed_roles && :allowed_roles)"
            )
            params["allowed_roles"] = allowed_roles

        where_sql = " AND ".join(where_clauses)

        sql = text(
            f"""
            SELECT
                c.id           AS chunk_id,
                c.content      AS content,
                c.document_id  AS document_id,
                c.filename     AS filename,
                c.page         AS page,
                c.section      AS section,
                c.jurisdiction AS jurisdiction,
                c.chunk_index  AS chunk_index
            FROM chunks c
            WHERE {where_sql}
            """
        )

        rows = (await db.execute(sql, params)).mappings().all()

        if not rows:
            logger.info("BM25: no chunks in the authorized corpus — returning empty")
            return []

        # ── 2. Build BM25 index ────────────────────────────────────────────────
        try:
            from rank_bm25 import BM25Plus  # noqa: PLC0415
        except ImportError as exc:
            raise ImportError(
                "rank-bm25 is required for M3 BM25 retrieval. "
                "Run: pip install rank-bm25"
            ) from exc

        corpus_tokens = [_tokenise(row["content"]) for row in rows]
        bm25 = BM25Plus(corpus_tokens)

        # ── 3. Score and rank ─────────────────────────────────────────────────
        query_tokens = _tokenise(query)
        scores = bm25.get_scores(query_tokens)

        # Pair scores with row indices, sort descending, take top_k
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]

        # Normalise scores to [0, 1] — highest score in this result set = 1.0
        max_score = ranked[0][1] if ranked and ranked[0][1] > 0 else 1.0

        results = []
        for idx, raw_score in ranked:
            if raw_score <= 0:
                break  # BM25 scores are 0 for unmatched queries
            row = rows[idx]
            results.append(
                RetrievalResult(
                    chunk_id=row["chunk_id"],
                    content=row["content"],
                    score=float(raw_score / max_score),
                    provenance=Provenance(
                        document_id=row["document_id"],
                        filename=row["filename"],
                        page=row["page"],
                        section=row["section"],
                        jurisdiction=row["jurisdiction"],
                        chunk_index=row["chunk_index"],
                    ),
                )
            )

        logger.info(
            "BM25: query=%r jurisdiction=%r top_k=%d → %d results",
            query[:80],
            jurisdiction,
            top_k,
            len(results),
        )
        return results
