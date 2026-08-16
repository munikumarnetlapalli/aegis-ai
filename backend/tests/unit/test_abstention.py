"""Unit tests for evidence threshold and abstention logic.

Verifies that:
- Insufficient chunk count triggers abstention
- Scores below the threshold trigger abstention
- Valid results above threshold do not trigger abstention
- Confidence label assignment matches expected score ranges
"""
from __future__ import annotations

import uuid

from app.generation.abstention import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    confidence_label,
    should_abstain,
)
from app.retrieval.service import Provenance, RetrievalResult


def _make_result(score: float) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        content="Evidence text",
        score=score,
        provenance=Provenance(
            document_id=uuid.uuid4(),
            filename="policy.pdf",
            page=1,
            section="§1",
            jurisdiction="EU",
            chunk_index=0,
        ),
    )


def test_should_abstain_on_empty_results():
    assert should_abstain([], threshold=0.0, min_chunks=1) is True


def test_should_abstain_on_insufficient_chunk_count():
    r1 = _make_result(5.0)
    assert should_abstain([r1], threshold=0.0, min_chunks=2) is True


def test_should_abstain_on_low_score():
    r1 = _make_result(-1.5)
    assert should_abstain([r1], threshold=0.0, min_chunks=1) is True


def test_should_not_abstain_when_valid():
    r1 = _make_result(2.5)
    assert should_abstain([r1], threshold=0.0, min_chunks=1) is False


def test_confidence_labels():
    assert confidence_label([]) == CONFIDENCE_LOW
    assert confidence_label([_make_result(6.0)]) == CONFIDENCE_HIGH
    assert confidence_label([_make_result(3.0)]) == CONFIDENCE_MEDIUM
    assert confidence_label([_make_result(0.5)]) == CONFIDENCE_LOW
