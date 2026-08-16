"""Unit tests for GenerationService.

Verifies that:
- Insufficient evidence triggers abstention before calling LLM
- LLM response with ABSTAIN triggers abstention response
- Successful response builds prompt, calls LLM, and formats citations
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.generation.abstention import ABSTENTION_MESSAGE
from app.generation.service import AnswerResponse, GenerationService
from app.retrieval.service import Provenance, RetrievalResult


def _make_chunk(content: str = "Test chunk content", score: float = 3.5) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=uuid.uuid4(),
        content=content,
        score=score,
        provenance=Provenance(
            document_id=uuid.uuid4(),
            filename="terms.pdf",
            page=5,
            section="§3",
            jurisdiction="EU",
            chunk_index=0,
        ),
    )


class TestGenerationService:
    @pytest.mark.asyncio
    async def test_abstains_when_insufficient_evidence(self):
        svc = GenerationService()
        res = await svc.answer(
            query="What is the policy?",
            context_chunks=[],
            evidence_threshold=1.0,
            min_evidence_chunks=1,
        )

        assert res.abstained is True
        assert res.answer == ABSTENTION_MESSAGE
        assert res.citations == []

    @pytest.mark.asyncio
    async def test_abstains_when_llm_returns_abstain(self):
        svc = GenerationService()
        chunk = _make_chunk()

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "ABSTAIN\nInsufficient info."

        with patch("app.generation.service.get_llm_provider", return_value=mock_llm):
            res = await svc.answer(
                query="What is the penalty?",
                context_chunks=[chunk],
                evidence_threshold=0.0,
                min_evidence_chunks=1,
            )

        assert res.abstained is True
        assert res.answer == ABSTENTION_MESSAGE
        assert res.citations == []

    @pytest.mark.asyncio
    async def test_answers_with_citations(self):
        svc = GenerationService()
        chunk = _make_chunk("The grace period is 14 days.")

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "The policy allows a 14-day grace period [1]."

        with patch("app.generation.service.get_llm_provider", return_value=mock_llm):
            res = await svc.answer(
                query="What is the grace period?",
                context_chunks=[chunk],
                evidence_threshold=0.0,
                min_evidence_chunks=1,
            )

        assert res.abstained is False
        assert "14-day grace period" in res.answer
        assert len(res.citations) == 1
        assert res.citations[0].citation_number == 1
        assert res.citations[0].filename == "terms.pdf"
        assert res.citations[0].page == 5
        assert res.citations[0].section == "§3"
