"""Integration tests for M7 Observability pipeline and API routes."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.generation.citations import Citation as CitationObj
from app.generation.service import AnswerResponse as GenAnswerResponse
from app.main import app
from app.models.user import User
from app.observability.privacy import compute_query_hash
from app.retrieval.service import Provenance, RetrievalResult
from app.security.auth import create_access_token


@pytest.mark.asyncio
class TestObservabilityAPIIntegration:
    """Integration test suite connecting RAG query execution to observability telemetry."""

    async def test_answer_endpoint_attaches_telemetry_and_records_trace(self):
        user_id = uuid.uuid4()
        admin_user = User(
            id=user_id,
            email="admin@aegis.local",
            hashed_password="hash",
            role="admin",
            jurisdiction="GLOBAL",
            is_active=True,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = admin_user
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        mock_chunk_id = uuid.uuid4()
        mock_retrieval_result = [
            RetrievalResult(
                chunk_id=mock_chunk_id,
                content="Claim filing deadline is 60 days.",
                score=4.2,
                provenance=Provenance(
                    document_id=uuid.uuid4(),
                    filename="policy.pdf",
                    page=1,
                    section="§1",
                    jurisdiction="GLOBAL",
                    chunk_index=0,
                ),
            )
        ]

        mock_gen_response = GenAnswerResponse(
            query="What is the claim filing deadline under standard terms?",
            answer="Claim filing deadline is 60 days [1].",
            citations=[
                CitationObj(
                    citation_number=1,
                    chunk_id=mock_chunk_id,
                    filename="policy.pdf",
                    section="§1",
                    page=1,
                    excerpt="Claim filing deadline is 60 days.",
                )
            ],
            confidence="high",
            abstained=False,
            evidence_count=1,
        )

        try:
            token = create_access_token(
                user_id=admin_user.id,
                email=admin_user.email,
                role="admin",
                jurisdiction="GLOBAL",
            )
            headers = {"Authorization": f"Bearer {token}", "X-Request-ID": "test-req-m7-integration-001"}

            payload = {
                "query": "What is the claim filing deadline under standard terms?",
                "jurisdiction": "GLOBAL",
                "top_k": 3,
            }

            with patch("app.api.answer._hybrid_retrieval.retrieve", AsyncMock(return_value=mock_retrieval_result)), \
                 patch("app.api.answer._generation_service.answer", AsyncMock(return_value=mock_gen_response)):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    res = await client.post("/answer", json=payload, headers=headers)
                    assert res.status_code == 200
                    data = res.json()

                    # Verify telemetry attached to AnswerResponse
                    assert "telemetry" in data
                    telemetry = data["telemetry"]
                    assert telemetry is not None
                    assert telemetry["request_id"] == "test-req-m7-integration-001"
                    assert telemetry["total_latency_ms"] >= 0.0
                    assert "input_tokens" in telemetry["token_usage"]

                    # Query recent traces from observability endpoint
                    res_recent = await client.get("/observability/recent?limit=10", headers=headers)
                    assert res_recent.status_code == 200
                    traces = res_recent.json()
                    assert len(traces) > 0

                    # Verify the trace recorded matches the query hash
                    expected_hash = compute_query_hash(payload["query"])
                    matching = [t for t in traces if t["query_hash"] == expected_hash]
                    assert len(matching) > 0
                    assert matching[0]["request_id"] == "test-req-m7-integration-001"
        finally:
            app.dependency_overrides.pop(get_db, None)

    async def test_observability_drift_report_endpoint(self):
        user_id = uuid.uuid4()
        admin_user = User(
            id=user_id,
            email="admin@aegis.local",
            hashed_password="hash",
            role="admin",
            jurisdiction="GLOBAL",
            is_active=True,
        )

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = admin_user
        mock_db.execute.return_value = mock_result
        app.dependency_overrides[get_db] = lambda: mock_db

        try:
            token = create_access_token(
                user_id=admin_user.id,
                email=admin_user.email,
                role="admin",
                jurisdiction="GLOBAL",
            )
            headers = {"Authorization": f"Bearer {token}"}


            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                res = await client.get("/observability/drift?threshold_pct=5.0", headers=headers)
                assert res.status_code == 200
                drift = res.json()

                assert "baseline_version" in drift
                assert drift["baseline_version"] == "v1.0-m6"
                assert "metrics" in drift
                assert len(drift["metrics"]) > 0

                metric_names = [m["metric_name"] for m in drift["metrics"]]
                assert "faithfulness" in metric_names
                assert "abstention_accuracy" in metric_names
                assert "mean_top_reranker_score" in metric_names
        finally:
            app.dependency_overrides.pop(get_db, None)
