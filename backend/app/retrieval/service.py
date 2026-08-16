"""Retrieval service — dense vector search backed by pgvector.

Authorization rule (non-negotiable):
  Jurisdiction and role filters are applied INSIDE the SQL query.
  Unauthorized content never surfaces from the database, let alone reaches the LLM.

M2: Dense-only (cosine similarity via pgvector).
M3: HybridRetrievalService adds BM25 sparse retrieval + RRF fusion + cross-encoder reranking.
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.embedding import get_embedding_provider
from app.observability.tracer import get_tracer

logger = logging.getLogger(__name__)


# ── Query normalisation ────────────────────────────────────────────────────────
# Strips common definitional question prefixes before BM25 and cross-encoder
# reranker scoring. Dense embedding keeps the full natural-language query since
# all-MiniLM-L6-v2 was trained on complete sentence pairs.
_QUERY_PREFIX_RE = re.compile(
    r"^(?:"
    r"what is the rule or definition regarding\s+|"
    r"what is the definition of\s+|"
    r"what is the meaning of\s+|"
    r"what is the difference between\s+|"
    r"what are the\s+|"
    r"what is\s+(?:a\s+|an\s+|the\s+)?|"
    r"how does\s+|"
    r"how do\s+|"
    r"explain (?:the )?mechanism of\s+|"
    r"explain\s+|"
    r"describe\s+|"
    r"define\s+"
    r")",
    re.IGNORECASE,
)


def _normalize_query_for_retrieval(query: str) -> str:
    """Strip common definitional/interrogative prefixes for BM25 + reranker.

    Keeps content-bearing terms at the front of the query, which improves
    BM25 IDF scoring and cross-encoder relevance scoring.
    The original query is still passed to the dense embedding encoder.
    """
    stripped = _QUERY_PREFIX_RE.sub("", query.strip())
    return stripped if stripped else query




# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class Provenance:
    """Source attribution for a retrieved chunk."""

    document_id: uuid.UUID
    filename: str
    page: int
    section: str
    jurisdiction: str
    chunk_index: int


@dataclass
class RetrievalResult:
    """A single retrieved chunk with its similarity score and provenance."""

    chunk_id: uuid.UUID
    content: str
    score: float  # cosine similarity [0, 1]; higher = more similar
    provenance: Provenance = field(default_factory=lambda: Provenance(  # type: ignore[call-arg]
        document_id=uuid.uuid4(), filename="", page=0, section="",
        jurisdiction="", chunk_index=0
    ))


# ── Dense retrieval service ────────────────────────────────────────────────────

class RetrievalService:
    """Dense retrieval using pgvector cosine similarity."""

    async def retrieve(
        self,
        *,
        query: str,
        jurisdiction: str | None = None,
        allowed_roles: list[str] | None = None,
        top_k: int = 20,
        db: AsyncSession,
    ) -> list[RetrievalResult]:
        """Retrieve the top-k most similar chunks for a query.

        Authorization filters (jurisdiction, allowed_roles) are applied inside
        the SQL WHERE clause — not in Python after the query.

        Parameters
        ----------
        query : str
            The user's natural-language query.
        jurisdiction : str | None
            If provided, only chunks with this jurisdiction (or "GLOBAL") are returned.
        allowed_roles : list[str] | None
            If provided, only chunks whose allowed_roles overlap are returned.
        top_k : int
            Number of chunks to return.
        db : AsyncSession
            Active database session.
        """
        provider = get_embedding_provider()
        query_embedding = provider.embed_query(query)

        # Format the embedding as a pgvector literal: '[0.1, 0.2, ...]'
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        # ── Build parameterised query ─────────────────────────────────────────
        # Authorization filters are inside the WHERE clause — never post-filter.
        # We use raw SQL for pgvector operator support (<=>).
        where_clauses = ["c.embedding IS NOT NULL"]
        params: dict = {
            "embedding": embedding_str,
            "top_k": top_k,
        }

        if jurisdiction:
            where_clauses.append(
                "(c.jurisdiction = :jurisdiction OR c.jurisdiction = 'GLOBAL')"
            )
            params["jurisdiction"] = jurisdiction

        if allowed_roles:
            # Postgres array overlap: c.allowed_roles && ARRAY[...] OR empty = public
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
                c.chunk_index  AS chunk_index,
                1 - (c.embedding <=> :embedding ::vector) AS score
            FROM chunks c
            WHERE {where_sql}
            ORDER BY c.embedding <=> :embedding ::vector
            LIMIT :top_k
            """
        )

        rows = (await db.execute(sql, params)).mappings().all()

        results = [
            RetrievalResult(
                chunk_id=row["chunk_id"],
                content=row["content"],
                score=float(row["score"]),
                provenance=Provenance(
                    document_id=row["document_id"],
                    filename=row["filename"],
                    page=row["page"],
                    section=row["section"],
                    jurisdiction=row["jurisdiction"],
                    chunk_index=row["chunk_index"],
                ),
            )
            for row in rows
        ]

        logger.info(
            "Retrieval: query=%r jurisdiction=%r top_k=%d → %d results",
            query[:80],
            jurisdiction,
            top_k,
            len(results),
        )
        return results


# ── Hybrid retrieval service (M3) ──────────────────────────────────────────────

class HybridRetrievalService:
    """Full M3 retrieval pipeline: dense + BM25 → RRF → cross-encoder reranker.

    Pipeline:
        query → dense top-K  ─┐
              → BM25 top-K   ─┼→ RRF merge → top-N → CrossEncoder → top-K_final
    """

    def __init__(self) -> None:
        self._dense = RetrievalService()

    async def retrieve(
        self,
        *,
        query: str,
        jurisdiction: str | None = None,
        allowed_roles: list[str] | None = None,
        top_k: int = 5,
        db: AsyncSession,
    ) -> list[RetrievalResult]:
        """Run the full hybrid retrieval pipeline.


        Parameters mirror RetrievalService.retrieve() — callers can swap
        between dense-only and hybrid without changing call sites.

        Parameters
        ----------
        top_k : int
            Final number of chunks to return after reranking.
            The intermediate BM25/dense stages retrieve more (configured in Settings).
        """
        from app.core.config import get_settings  # noqa: PLC0415
        from app.retrieval.bm25 import BM25Retriever  # noqa: PLC0415
        from app.retrieval.rrf import reciprocal_rank_fusion  # noqa: PLC0415
        from app.reranking.reranker import get_reranker  # noqa: PLC0415

        settings = get_settings()

        # Normalise query for BM25 and reranker (strip interrogative prefixes).
        # Dense embedding keeps the full query for better semantic coverage.
        retrieval_query = _normalize_query_for_retrieval(query)
        if retrieval_query != query:
            logger.debug(
                "HybridRetrieval: query normalised %r → %r",
                query[:60], retrieval_query[:60],
            )

        tracer = get_tracer()

        # ── 1. Dense retrieval ────────────────────────────────────────────────
        # Use the ORIGINAL query: all-MiniLM trained on full natural-language
        # sentence pairs; complete queries give better semantic coverage.
        with tracer.span("retrieval.dense", metadata={"top_k": settings.retrieval_top_k}) as dense_span:
            dense_results = await self._dense.retrieve(
                query=query,
                jurisdiction=jurisdiction,
                allowed_roles=allowed_roles,
                top_k=settings.retrieval_top_k,
                db=db,
            )
            if dense_span:
                dense_span.metadata["candidate_count"] = len(dense_results)

        # ── 2. BM25 retrieval ─────────────────────────────────────────────────
        # Use the NORMALISED query: keyword scoring benefits from removing
        # interrogative stop-words that dilute IDF signals.
        with tracer.span("retrieval.bm25", metadata={"top_k": settings.bm25_top_k}) as bm25_span:
            bm25_retriever = BM25Retriever()
            bm25_results = await bm25_retriever.retrieve(
                query=retrieval_query,
                jurisdiction=jurisdiction,
                allowed_roles=allowed_roles,
                top_k=settings.bm25_top_k,
                db=db,
            )
            if bm25_span:
                bm25_span.metadata["candidate_count"] = len(bm25_results)

        # ── 3. RRF fusion ─────────────────────────────────────────────────────
        with tracer.span("retrieval.rrf", metadata={"rrf_k": settings.rrf_k}) as rrf_span:
            fused = reciprocal_rank_fusion(
                dense_results,
                bm25_results,
                k=settings.rrf_k,
                top_n=settings.retrieval_top_k,  # cap before reranking
            )
            if rrf_span:
                rrf_span.metadata["fused_count"] = len(fused)

        if not fused:
            logger.info("HybridRetrieval: no results after RRF fusion")
            return []

        # ── 4. Cross-encoder reranking ────────────────────────────────────────
        # Use NORMALISED query: ms-marco-MiniLM scores query–passage relevance
        # more accurately on content-focused, non-interrogative queries.
        with tracer.span("reranking.cross_encoder", metadata={"top_k": top_k, "candidates": len(fused)}) as rerank_span:
            reranker = get_reranker()
            reranked = reranker.rerank(query=retrieval_query, results=fused, top_k=top_k)
            if rerank_span:
                rerank_span.metadata["result_count"] = len(reranked)
                if reranked:
                    rerank_span.metadata["top_score"] = round(reranked[0].score, 4)

        logger.info(
            "HybridRetrieval: query=%r → dense=%d bm25=%d fused=%d reranked=%d",
            query[:80],
            len(dense_results),
            len(bm25_results),
            len(fused),
            len(reranked),
        )
        return reranked


