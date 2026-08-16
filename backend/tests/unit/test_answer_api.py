"""Unit tests for POST /answer API route.

Verifies that:
- /answer invokes hybrid retrieval and generation service
- Returns structured AnswerResponse with citations and metadata
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.generation.citations import Citation as CitationObj
from app.generation.service import AnswerResponse as GenAnswerResponse
from app.main import app
from app.retrieval.service import Provenance, RetrievalResult


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_answer_endpoint_success(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db

    mock_chunk_id = uuid.uuid4()
    mock_retrieval_result = [
        RetrievalResult(
            chunk_id=mock_chunk_id,
            content="Payment is due within 30 days.",
            score=4.2,
            provenance=Provenance(
                document_id=uuid.uuid4(),
                filename="billing.pdf",
                page=2,
                section="§2.1",
                jurisdiction="EU",
                chunk_index=0,
            ),
        )
    ]

    mock_gen_response = GenAnswerResponse(
        query="When is payment due?",
        answer="Payment is due within 30 days [1].",
        citations=[
            CitationObj(
                citation_number=1,
                chunk_id=mock_chunk_id,
                filename="billing.pdf",
                section="§2.1",
                page=2,
                excerpt="Payment is due within 30 days.",
            )
        ],
        confidence="medium",
        abstained=False,
        evidence_count=1,
    )

    with patch(
        "app.api.answer._hybrid_retrieval.retrieve",
        new_callable=AsyncMock,
        return_value=mock_retrieval_result,
    ), patch(
        "app.api.answer._generation_service.answer",
        new_callable=AsyncMock,
        return_value=mock_gen_response,
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            response = await ac.post(
                "/answer",
                json={
                    "query": "When is payment due?",
                    "jurisdiction": "EU",
                    "top_k": 5,
                },
            )

    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "When is payment due?"
    assert "30 days" in data["answer"]
    assert data["abstained"] is False
    assert len(data["citations"]) == 1
    assert data["citations"][0]["citation_number"] == 1
    assert data["citations"][0]["filename"] == "billing.pdf"


def test_answer_endpoint_in_openapi_schema():
    """Verify that /answer is registered and visible in OpenAPI docs alongside all existing endpoints."""
    schema = app.openapi()
    paths = schema["paths"]
    assert "/answer" in paths, "POST /answer must be present in OpenAPI schema"
    assert "post" in paths["/answer"]
    assert "/query" in paths, "Existing POST /query must be preserved in OpenAPI schema"
    assert "post" in paths["/query"]
    assert "/health" in paths, "GET /health must be preserved"
    assert "/documents" in paths, "POST/GET /documents must be preserved"
    assert "post" in paths["/documents"]
    assert "/auth/register" in paths, "POST /auth/register must be present in OpenAPI schema"
    assert "post" in paths["/auth/register"]
    assert "/auth/login" in paths, "POST /auth/login must be present in OpenAPI schema"
    assert "post" in paths["/auth/login"]
    assert "/auth/me" in paths, "GET /auth/me must be present in OpenAPI schema"
    assert "get" in paths["/auth/me"]



