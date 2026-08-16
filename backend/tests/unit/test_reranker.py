"""Unit tests for CrossEncoderReranker.

Verifies that:
- Reranker sorts results according to predicted cross-encoder scores
- Candidate list is properly truncated by top_k
- Empty candidate list returns empty without error
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.reranking.reranker import CrossEncoderReranker, Reranker
from app.retrieval.service import Provenance, RetrievalResult


def _make_result(content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        content=content,
        score=0.1,
        provenance=Provenance(
            document_id=uuid.uuid4(),
            filename="doc.pdf",
            page=1,
            section="§1",
            jurisdiction="EU",
            chunk_index=0,
        ),
    )


class TestCrossEncoderReranker:
    def test_rerank_sorts_and_updates_scores(self):
        reranker = CrossEncoderReranker(model_name="dummy-model")

        r1 = _make_result("Doc 1 content")
        r2 = _make_result("Doc 2 content")
        candidates = [r1, r2]

        mock_model = MagicMock()
        # predict returns scores where doc 2 is more relevant than doc 1
        mock_model.predict.return_value = [1.2, 5.8]

        with patch.object(reranker, "_get_model", return_value=mock_model):
            reranked = reranker.rerank(query="test query", results=candidates, top_k=5)

        assert len(reranked) == 2
        assert reranked[0].chunk_id == r2.chunk_id
        assert reranked[0].score == pytest.approx(5.8)
        assert reranked[1].chunk_id == r1.chunk_id
        assert reranked[1].score == pytest.approx(1.2)

    def test_rerank_top_k_limit(self):
        reranker = CrossEncoderReranker(model_name="dummy-model")
        r1 = _make_result("Doc 1")
        r2 = _make_result("Doc 2")
        r3 = _make_result("Doc 3")

        mock_model = MagicMock()
        mock_model.predict.return_value = [2.0, 4.0, 1.0]

        with patch.object(reranker, "_get_model", return_value=mock_model):
            reranked = reranker.rerank(query="query", results=[r1, r2, r3], top_k=2)

        assert len(reranked) == 2
        assert reranked[0].chunk_id == r2.chunk_id
        assert reranked[1].chunk_id == r1.chunk_id

    def test_rerank_empty_results(self):
        reranker = CrossEncoderReranker(model_name="dummy-model")
        assert reranker.rerank(query="query", results=[]) == []
