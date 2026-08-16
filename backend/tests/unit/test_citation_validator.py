"""Unit tests for citation validation.

Verifies that:
- Valid citation markers [N] resolve to the correct context chunks
- Hallucinated / out-of-range markers are stripped and rejected
- Duplicate citation markers are properly deduplicated
"""
from __future__ import annotations

import uuid

from app.generation.citations import validate_citations
from app.retrieval.service import Provenance, RetrievalResult


def _make_result(filename: str, page: int, section: str, content: str) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        content=content,
        score=0.9,
        provenance=Provenance(
            document_id=uuid.uuid4(),
            filename=filename,
            page=page,
            section=section,
            jurisdiction="EU",
            chunk_index=0,
        ),
    )


def test_validate_citations_resolves_correctly():
    c1 = _make_result("Policy2026.pdf", 12, "§8.2", "The settlement period is 30 days.")
    c2 = _make_result("Rules.pdf", 4, "§1.1", "Claims must be filed within 1 year.")

    context = [c1, c2]
    response_text = "The settlement is 30 days [1] and filed in 1 year [2]."

    cleaned, citations = validate_citations(response_text, context)

    assert len(citations) == 2
    assert citations[0].citation_number == 1
    assert citations[0].filename == "Policy2026.pdf"
    assert citations[0].page == 12
    assert citations[0].section == "§8.2"
    assert citations[0].chunk_id == c1.chunk_id

    assert citations[1].citation_number == 2
    assert citations[1].filename == "Rules.pdf"
    assert citations[1].page == 4
    assert citations[1].section == "§1.1"
    assert citations[1].chunk_id == c2.chunk_id


def test_validate_citations_rejects_hallucinated_markers():
    c1 = _make_result("Policy2026.pdf", 12, "§8.2", "Settlement period is 30 days.")
    context = [c1]

    # [99] is hallucinated / out of range
    response_text = "Settlement is 30 days [1] and fee is waived [99]."

    cleaned, citations = validate_citations(response_text, context)

    assert len(citations) == 1
    assert citations[0].citation_number == 1
    assert "[99]" not in cleaned
    assert "[1]" in cleaned


def test_validate_citations_deduplicates():
    c1 = _make_result("Policy2026.pdf", 12, "§8.2", "Settlement period is 30 days.")
    context = [c1]

    response_text = "Claim is 30 days [1]. Yes, exactly 30 days [1]."

    cleaned, citations = validate_citations(response_text, context)

    assert len(citations) == 1
    assert citations[0].citation_number == 1
