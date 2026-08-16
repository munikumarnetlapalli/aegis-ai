"""Unit tests for BM25Retriever.

Verifies that:
- Authorization and jurisdiction filters are always applied in SQL
- Tokenization and BM25 scoring accurately rank matching chunks
- Chunks without keyword matches are handled gracefully
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.retrieval.bm25 import BM25Retriever, _tokenise
from app.retrieval.service import RetrievalResult


def test_tokenise():
    tokens = _tokenise("Hello World! Policy §8.2 (2026)")
    assert tokens == ["hello", "world", "policy", "8", "2", "2026"]


class TestBM25Retriever:
    @pytest.mark.asyncio
    async def test_jurisdiction_filter_in_sql(self):
        retriever = BM25Retriever()
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

        await retriever.retrieve(query="settlement", jurisdiction="EU", db=db)

        assert len(captured_sql) == 1
        assert "jurisdiction" in captured_sql[0].lower()

    @pytest.mark.asyncio
    async def test_roles_filter_in_sql(self):
        retriever = BM25Retriever()
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

        await retriever.retrieve(
            query="settlement", allowed_roles=["compliance_officer"], db=db
        )

        assert len(captured_sql) == 1
        assert "allowed_roles" in captured_sql[0].lower()

    @pytest.mark.asyncio
    async def test_bm25_ranking(self):
        retriever = BM25Retriever()
        db = AsyncMock()

        doc_id = uuid.uuid4()
        chunk1_id = uuid.uuid4()
        chunk2_id = uuid.uuid4()

        rows = [
            {
                "chunk_id": chunk1_id,
                "content": "The claim settlement period is 30 days.",
                "document_id": doc_id,
                "filename": "policy.pdf",
                "page": 1,
                "section": "§1",
                "jurisdiction": "EU",
                "chunk_index": 0,
            },
            {
                "chunk_id": chunk2_id,
                "content": "Premium payments must be made annually.",
                "document_id": doc_id,
                "filename": "policy.pdf",
                "page": 2,
                "section": "§2",
                "jurisdiction": "EU",
                "chunk_index": 1,
            },
        ]

        mappings = MagicMock()
        mappings.all.return_value = rows
        execute_result = MagicMock()
        execute_result.mappings.return_value = mappings
        db.execute = AsyncMock(return_value=execute_result)

        results = await retriever.retrieve(query="claim settlement", top_k=5, db=db)

        assert len(results) >= 1
        assert results[0].chunk_id == chunk1_id
        assert results[0].score > 0.0

    @pytest.mark.asyncio
    async def test_empty_corpus_returns_empty(self):
        retriever = BM25Retriever()
        db = AsyncMock()

        mappings = MagicMock()
        mappings.all.return_value = []
        execute_result = MagicMock()
        execute_result.mappings.return_value = mappings
        db.execute = AsyncMock(return_value=execute_result)

        results = await retriever.retrieve(query="nonexistent", db=db)
        assert results == []
