"""Security tests for user authentication, password hashing, and privilege escalation defense.

Verifies:
- Password hashing generates distinct hashes for identical passwords
- Correct password verification succeeds; incorrect fails
- JWT token generation, expiration, and tampering detection
- Public registration cannot escalate to admin (strictly assigns safe 'viewer' role)
- Role modification and user provisioning require admin credentials
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app
from app.models.user import User
from app.security.auth import create_access_token, decode_access_token
from app.security.password import hash_password, verify_password


def test_password_hashing_and_verification():
    plain = "SuperSecretPassword123!"
    hashed = hash_password(plain)

    assert hashed.startswith("pbkdf2_sha256$")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_password_unique_salts():
    plain = "SamePasswordAcrossUsers"
    hash1 = hash_password(plain)
    hash2 = hash_password(plain)

    assert hash1 != hash2, "Identical passwords must produce distinct salt hashes"
    assert verify_password(plain, hash1) is True
    assert verify_password(plain, hash2) is True


def test_jwt_token_flow():
    user_id = uuid.uuid4()
    email = "compliance@aegis.local"
    role = "compliance_officer"
    jurisdiction = "EU"

    token = create_access_token(
        user_id=user_id,
        email=email,
        role=role,
        jurisdiction=jurisdiction,
        expires_delta=timedelta(minutes=15),
    )

    payload = decode_access_token(token)
    assert payload.sub == str(user_id)
    assert payload.email == email
    assert payload.role == role
    assert payload.jurisdiction == jurisdiction


def test_jwt_tampered_token_rejected():
    user_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        email="test@aegis.local",
        role="viewer",
        jurisdiction="US",
    )

    tampered_token = token[:-4] + "fake"
    with pytest.raises(ValueError):
        decode_access_token(tampered_token)


def test_jwt_expired_token_rejected():
    user_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        email="test@aegis.local",
        role="viewer",
        jurisdiction="US",
        expires_delta=timedelta(seconds=-10),  # expired in past
    )

    with pytest.raises(TimeoutError):
        decode_access_token(token)


# ── Privilege Escalation Regression Tests ──────────────────────────────────────

@pytest.mark.asyncio
async def test_public_registration_blocks_admin_escalation():
    """Regression test: Sending role='admin' to /auth/register must NOT grant admin role."""
    db = AsyncMock()
    # Mock no existing user
    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = None
    db.execute.return_value = select_result

    created_users = []

    def capture_add(user):
        created_users.append(user)

    db.add = capture_add
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    app.dependency_overrides[get_db] = lambda: db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/auth/register",
            json={
                "email": "attacker@test.local",
                "password": "TestPassword123!",
                "role": "admin",  # Attacker attempts privilege escalation
                "jurisdiction": "EU",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "viewer", "Public registration must assign safe default 'viewer' role"
    assert created_users[0].role == "viewer"


@pytest.mark.asyncio
async def test_admin_provisioning_requires_admin_role():
    """Non-admin users cannot provision users with elevated roles."""
    db = AsyncMock()
    viewer_user = User(
        id=uuid.uuid4(),
        email="viewer@aegis.local",
        hashed_password="hash",
        role="viewer",
        jurisdiction="GLOBAL",
        is_active=True,
    )
    viewer_token = create_access_token(
        user_id=viewer_user.id,
        email=viewer_user.email,
        role=viewer_user.role,
        jurisdiction=viewer_user.jurisdiction,
    )

    select_result = MagicMock()
    select_result.scalar_one_or_none.return_value = viewer_user
    db.execute.return_value = select_result

    app.dependency_overrides[get_db] = lambda: db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/auth/provision",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "email": "new_admin@test.local",
                "password": "TestPassword123!",
                "role": "admin",
            },
        )

    app.dependency_overrides.clear()

    assert response.status_code == 403, "Non-admin must be forbidden from provisioning users"
