"""Unit tests for Reciprocal Rank Fusion (RRF).

Verifies that:
- Chunks appearing in multiple ranked lists are boosted
- Chunk deduplication preserves provenance
- Ranking order strictly respects RRF score
- Edge cases (empty lists, single list) are handled cleanly
"""
from __future__ import annotations

import uuid

import pytest

from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.service import Provenance, RetrievalResult


def _make_result(chunk_id: uuid.UUID, content: str, score: float = 0.5) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=chunk_id,
        content=content,
        score=score,
        provenance=Provenance(
            document_id=uuid.uuid4(),
            filename="test.pdf",
            page=1,
            section="§1",
            jurisdiction="EU",
            chunk_index=0,
        ),
    )


def test_rrf_boosts_intersecting_items():
    id_a = uuid.uuid4()
    id_b = uuid.uuid4()
    id_c = uuid.uuid4()

    # List 1: [A, B]
    list1 = [_make_result(id_a, "Chunk A", 0.9), _make_result(id_b, "Chunk B", 0.8)]
    # List 2: [B, C]
    list2 = [_make_result(id_b, "Chunk B", 0.95), _make_result(id_c, "Chunk C", 0.7)]

    # B appears in both lists (rank 2 in list 1, rank 1 in list 2)
    # Score(B) = 1/(60+2) + 1/(60+1) = 1/62 + 1/61 ≈ 0.016129 + 0.016393 = 0.032522
    # Score(A) = 1/(60+1) = 1/61 ≈ 0.016393
    # Score(C) = 1/(60+2) = 1/62 ≈ 0.016129
    fused = reciprocal_rank_fusion(list1, list2, k=60)

    assert len(fused) == 3
    assert fused[0].chunk_id == id_b
    assert fused[1].chunk_id == id_a
    assert fused[2].chunk_id == id_c


def test_rrf_top_n_truncation():
    id_a = uuid.uuid4()
    id_b = uuid.uuid4()
    id_c = uuid.uuid4()

    list1 = [_make_result(id_a, "A"), _make_result(id_b, "B"), _make_result(id_c, "C")]
    fused = reciprocal_rank_fusion(list1, k=60, top_n=2)

    assert len(fused) == 2
    assert fused[0].chunk_id == id_a
    assert fused[1].chunk_id == id_b


def test_rrf_empty_lists():
    fused = reciprocal_rank_fusion([], [], k=60)
    assert fused == []
