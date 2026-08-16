"""Unit tests for RetrievalService.

Verifies that:
  - Authorization filters are always present in the SQL
  - The query embedding is always called
  - Results are correctly mapped to RetrievalResult objects
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.retrieval.service import (
    HybridRetrievalService,
    Provenance,
    RetrievalResult,
    RetrievalService,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def make_mock_row(
    chunk_id=None,
    content="Test content",
    document_id=None,
    filename="doc.pdf",
    page=1,
    section="§ 1",
    jurisdiction="EU",
    chunk_index=0,
    score=0.87,
):
    row = MagicMock()
    row.__getitem__ = lambda self, key: {
        "chunk_id": chunk_id or uuid.uuid4(),
        "content": content,
        "document_id": document_id or uuid.uuid4(),
        "filename": filename,
        "page": page,
        "section": section,
        "jurisdiction": jurisdiction,
        "chunk_index": chunk_index,
        "score": score,
    }[key]
    return row


# ── Tests ──────────────────────────────────────────────────────────────────────

class TestRetrievalService:
    @pytest.mark.asyncio
    async def test_always_calls_embed_query(self):
        """RetrievalService must always embed the query before executing SQL."""
        svc = RetrievalService()
        db = AsyncMock()

        mappings = MagicMock()
        mappings.all.return_value = []
        execute_result = MagicMock()
        execute_result.mappings.return_value = mappings
        db.execute = AsyncMock(return_value=execute_result)

        with patch("app.retrieval.service.get_embedding_provider") as mock_provider_fn:
            provider = MagicMock()
            provider.embed_query.return_value = [0.1] * 384
            mock_provider_fn.return_value = provider

            await svc.retrieve(query="test query", db=db)

        provider.embed_query.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_jurisdiction_filter_in_sql(self):
        """When jurisdiction is provided, it must appear in the SQL string."""
        svc = RetrievalService()
        db = AsyncMock()

        captured_sql = []
        mappings = MagicMock()
        mappings.all.return_value = []
        execute_result = MagicMock()
        execute_result.mappings.return_value = mappings

        async def capture_execute(sql, params=None):
            captured_sql.append(str(sql))
            return execute_result

        db.execute = capture_execute

        with patch("app.retrieval.service.get_embedding_provider") as mock_provider_fn:
            provider = MagicMock()
            provider.embed_query.return_value = [0.0] * 384
            mock_provider_fn.return_value = provider

            await svc.retrieve(query="claims", jurisdiction="EU", db=db)

        assert len(captured_sql) == 1
        assert "jurisdiction" in captured_sql[0].lower(), (
            "Jurisdiction filter must be inside the SQL, not post-filtered in Python"
        )

    @pytest.mark.asyncio
    async def test_roles_filter_in_sql(self):
        """When allowed_roles is provided, it must appear in the SQL."""
        svc = RetrievalService()
        db = AsyncMock()

        captured_sql = []
        mappings = MagicMock()
        mappings.all.return_value = []
        execute_result = MagicMock()
        execute_result.mappings.return_value = mappings

        async def capture_execute(sql, params=None):
            captured_sql.append(str(sql))
            return execute_result

        db.execute = capture_execute

        with patch("app.retrieval.service.get_embedding_provider") as mock_fn:
            provider = MagicMock()
            provider.embed_query.return_value = [0.0] * 384
            mock_fn.return_value = provider

            await svc.retrieve(
                query="policy", allowed_roles=["admin", "analyst"], db=db
            )

        assert "allowed_roles" in captured_sql[0].lower(), (
            "Role filter must be inside the SQL, not post-filtered in Python"
        )

    @pytest.mark.asyncio
    async def test_returns_retrieval_results(self):
        """Rows from the database must be correctly mapped to RetrievalResult objects."""
        svc = RetrievalService()
        db = AsyncMock()

        doc_id = uuid.uuid4()
        chunk_id = uuid.uuid4()
        fake_row = {
            "chunk_id": chunk_id,
            "content": "The claim settlement period is 30 days.",
            "document_id": doc_id,
            "filename": "policy2026.pdf",
            "page": 12,
            "section": "§ 8.2",
            "jurisdiction": "EU",
            "chunk_index": 42,
            "score": 0.93,
        }

        rows = MagicMock()
        rows.all.return_value = [fake_row]
        execute_result = MagicMock()
        execute_result.mappings.return_value = rows
        db.execute = AsyncMock(return_value=execute_result)

        with patch("app.retrieval.service.get_embedding_provider") as mock_fn:
            provider = MagicMock()
            provider.embed_query.return_value = [0.0] * 384
            mock_fn.return_value = provider

            results = await svc.retrieve(query="settlement period", db=db)

        assert len(results) == 1
        r = results[0]
        assert isinstance(r, RetrievalResult)
        assert r.chunk_id == chunk_id
        assert r.content == "The claim settlement period is 30 days."
        assert r.score == pytest.approx(0.93)
        assert r.provenance.document_id == doc_id
        assert r.provenance.filename == "policy2026.pdf"
        assert r.provenance.page == 12
        assert r.provenance.section == "§ 8.2"

    @pytest.mark.asyncio
    async def test_empty_results_returns_empty_list(self):
        svc = RetrievalService()
        db = AsyncMock()

        rows = MagicMock()
        rows.all.return_value = []
        execute_result = MagicMock()
        execute_result.mappings.return_value = rows
        db.execute = AsyncMock(return_value=execute_result)

        with patch("app.retrieval.service.get_embedding_provider") as mock_fn:
            provider = MagicMock()
            provider.embed_query.return_value = [0.0] * 384
            mock_fn.return_value = provider

            results = await svc.retrieve(query="nothing matches", db=db)

        assert results == []


class TestHybridRetrievalService:
    @pytest.mark.asyncio
    async def test_hybrid_retrieval_pipeline_flow(self):
        hybrid_svc = HybridRetrievalService()
        db = AsyncMock()

        chunk_id = uuid.uuid4()
        fake_result = RetrievalResult(
            chunk_id=chunk_id,
            content="Hybrid retrieved evidence",
            score=0.88,
            provenance=Provenance(
                document_id=uuid.uuid4(),
                filename="manual.pdf",
                page=1,
                section="§1",
                jurisdiction="EU",
                chunk_index=0,
            ),
        )

        mock_dense_retrieve = AsyncMock(return_value=[fake_result])
        mock_bm25_retrieve = AsyncMock(return_value=[fake_result])
        mock_reranker = MagicMock()
        mock_reranker.rerank.return_value = [fake_result]

        with patch.object(
            hybrid_svc._dense, "retrieve", mock_dense_retrieve
        ), patch(
            "app.retrieval.bm25.BM25Retriever.retrieve", mock_bm25_retrieve
        ), patch(
            "app.reranking.reranker.get_reranker", return_value=mock_reranker
        ):
            results = await hybrid_svc.retrieve(
                query="manual check", jurisdiction="EU", top_k=5, db=db
            )

        assert len(results) == 1
        assert results[0].chunk_id == chunk_id
        mock_dense_retrieve.assert_called_once()
        mock_bm25_retrieve.assert_called_once()
        mock_reranker.rerank.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_empty_returns_empty(self):
        hybrid_svc = HybridRetrievalService()
        db = AsyncMock()

        with patch.object(
            hybrid_svc._dense, "retrieve", new_callable=AsyncMock, return_value=[]
        ), patch(
            "app.retrieval.bm25.BM25Retriever.retrieve", new_callable=AsyncMock, return_value=[]
        ):
            results = await hybrid_svc.retrieve(
                query="nothing", db=db
            )

        assert results == []

