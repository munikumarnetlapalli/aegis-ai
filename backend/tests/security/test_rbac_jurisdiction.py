"""Security tests for RBAC and jurisdiction isolation.

Verifies non-negotiable security requirements:
- EU users cannot retrieve US-only documents
- US users cannot retrieve EU-only documents
- Unauthorized roles are blocked inside the retrieval SQL query
- Client-supplied request body parameters cannot override trusted server-side user context
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.generation.service import AnswerResponse as GenAnswerResponse
from app.main import app
from app.models.user import User
from app.retrieval.service import RetrievalResult, RetrievalService
from app.security.auth import create_access_token
from app.security.dependencies import require_roles


class TestJurisdictionIsolation:
    @pytest.mark.asyncio
    async def test_eu_jurisdiction_filter_in_sql(self):
        """Retrieval query for EU user must enforce jurisdiction filter in SQL."""
        svc = RetrievalService()
        db = AsyncMock()

        captured_sql = []
        captured_params = []
        mappings = MagicMock()
        mappings.all.return_value = []
        execute_result = MagicMock()
        execute_result.mappings.return_value = mappings

        async def capture_execute(sql, params=None):
            captured_sql.append(str(sql))
            captured_params.append(params)
            return execute_result

        db.execute = capture_execute

        with patch("app.retrieval.service.get_embedding_provider") as mock_fn:
            provider = MagicMock()
            provider.embed_query.return_value = [0.0] * 384
            mock_fn.return_value = provider

            await svc.retrieve(
                query="settlement policies",
                jurisdiction="EU",
                allowed_roles=["compliance_officer"],
                db=db,
            )

        assert len(captured_sql) == 1
        assert "jurisdiction = :jurisdiction" in captured_sql[0].lower()
        assert captured_params[0]["jurisdiction"] == "EU"
        assert captured_params[0]["allowed_roles"] == ["compliance_officer"]

    @pytest.mark.asyncio
    async def test_us_jurisdiction_filter_in_sql(self):
        """Retrieval query for US user must enforce US jurisdiction in SQL."""
        svc = RetrievalService()
        db = AsyncMock()

        captured_params = []
        mappings = MagicMock()
        mappings.all.return_value = []
        execute_result = MagicMock()
        execute_result.mappings.return_value = mappings

        async def capture_execute(sql, params=None):
            captured_params.append(params)
            return execute_result

        db.execute = capture_execute

        with patch("app.retrieval.service.get_embedding_provider") as mock_fn:
            provider = MagicMock()
            provider.embed_query.return_value = [0.0] * 384
            mock_fn.return_value = provider

            await svc.retrieve(
                query="hipaa guidelines",
                jurisdiction="US",
                allowed_roles=["analyst"],
                db=db,
            )

        assert captured_params[0]["jurisdiction"] == "US"
        assert captured_params[0]["allowed_roles"] == ["analyst"]


class TestRBACPermissions:
    @pytest.mark.asyncio
    async def test_require_roles_grants_authorized_user(self):
        user = User(
            id=uuid.uuid4(),
            email="officer@aegis.local",
            hashed_password="hash",
            role="compliance_officer",
            jurisdiction="EU",
        )
        checker = require_roles(["compliance_officer", "admin"])
        result = await checker(current_user=user)
        assert result == user

    @pytest.mark.asyncio
    async def test_require_roles_blocks_unauthorized_user(self):
        user = User(
            id=uuid.uuid4(),
            email="regular@aegis.local",
            hashed_password="hash",
            role="user",
            jurisdiction="EU",
        )
        checker = require_roles(["compliance_officer"])
        with pytest.raises(Exception) as exc_info:
            await checker(current_user=user)
        assert "403" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_admin_can_update_user_role(self):
        """Admin can promote a viewer to compliance_officer."""
        db = AsyncMock()
        admin_user = User(
            id=uuid.uuid4(),
            email="admin@aegis.local",
            hashed_password="hash",
            role="admin",
            jurisdiction="GLOBAL",
            is_active=True,
        )
        target_user = User(
            id=uuid.uuid4(),
            email="promoted@aegis.local",
            hashed_password="hash",
            role="viewer",
            jurisdiction="EU",
            is_active=True,
        )

        admin_token = create_access_token(
            user_id=admin_user.id,
            email=admin_user.email,
            role=admin_user.role,
            jurisdiction=admin_user.jurisdiction,
        )

        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = admin_user
        db.execute.return_value = select_result
        db.get.return_value = target_user
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        app.dependency_overrides[get_db] = lambda: db

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            response = await ac.post(
                f"/auth/users/{target_user.id}/role",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"role": "compliance_officer", "jurisdiction": "EU"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "compliance_officer"
        assert target_user.role == "compliance_officer"



class TestServerSideContextOverridesClientBody:
    @pytest.mark.asyncio
    async def test_authenticated_user_overrides_client_body_jurisdiction(self):
        """When an EU user sends 'jurisdiction: US' in request body, server enforces 'EU'."""
        db = AsyncMock()
        app.dependency_overrides[get_db] = lambda: db

        eu_user = User(
            id=uuid.uuid4(),
            email="eu_user@aegis.local",
            hashed_password="hash",
            role="analyst",
            jurisdiction="EU",
            is_active=True,
        )

        token = create_access_token(
            user_id=eu_user.id,
            email=eu_user.email,
            role=eu_user.role,
            jurisdiction=eu_user.jurisdiction,
        )

        mock_gen_response = GenAnswerResponse(
            query="Test query",
            answer="Answer strictly from EU context.",
            citations=[],
            confidence="medium",
            abstained=False,
            evidence_count=1,
        )

        captured_retrieval_kwargs = {}

        async def capture_retrieve(**kwargs):
            captured_retrieval_kwargs.update(kwargs)
            return []

        # Mock DB select for User
        user_select_mock = MagicMock()
        user_select_mock.scalar_one_or_none.return_value = eu_user
        db.execute = AsyncMock(return_value=user_select_mock)

        with patch(
            "app.api.answer._hybrid_retrieval.retrieve", side_effect=capture_retrieve
        ), patch(
            "app.api.answer._generation_service.answer", new_callable=AsyncMock, return_value=mock_gen_response
        ):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                response = await ac.post(
                    "/answer",
                    headers={"Authorization": f"Bearer {token}"},
                    json={
                        "query": "What is the policy?",
                        # Attempt to spoof jurisdiction and role in request body
                        "jurisdiction": "US",
                        "allowed_roles": ["admin"],
                    },
                )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        # Verify server derived parameters from token, NOT request body
        assert captured_retrieval_kwargs.get("jurisdiction") == "EU"
        assert captured_retrieval_kwargs.get("allowed_roles") == ["analyst"]
