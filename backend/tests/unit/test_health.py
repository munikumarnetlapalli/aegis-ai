"""Unit tests for the health check endpoint.

Tests run without Docker — they mock the database layer.
Integration tests (with a real DB) live in tests/integration/.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.main import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_returns_200_when_database_is_reachable(self, client: TestClient) -> None:
        """Health check must return 200 and healthy status when DB is reachable."""
        mock_execute = AsyncMock()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = mock_execute

        with patch("app.api.health.AsyncSessionLocal", return_value=mock_session):
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["database"] == "connected"
        assert "version" in body

    def test_returns_503_when_database_is_unreachable(self, client: TestClient) -> None:
        """Health check must return 503 when the database cannot be reached."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(
            side_effect=OperationalError("connection refused", None, None)
        )

        with patch("app.api.health.AsyncSessionLocal", return_value=mock_session):
            response = client.get("/health")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["database"] == "unreachable"

    def test_response_contains_version(self, client: TestClient) -> None:
        """Health response must always include the application version."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()

        with patch("app.api.health.AsyncSessionLocal", return_value=mock_session):
            response = client.get("/health")

        assert "version" in response.json()
