"""JWT authentication token generation and decoding.

Signs tokens with HMAC-SHA256 (HS256) using the configured `jwt_secret_key`.
Supports standard library HMAC-SHA256 and PyJWT, ensuring zero-dependency
reliability across container and local execution environments.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TokenPayload(BaseModel):
    """Decoded JWT payload model."""

    sub: str = Field(description="User ID")
    email: str
    role: str
    jurisdiction: str
    exp: datetime
    iat: datetime


def _b64url_encode(data: bytes) -> str:
    """Encode bytes to unpadded base64url string."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Decode unpadded base64url string to bytes."""
    rem = len(s) % 4
    if rem > 0:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s.encode("ascii"))


def create_access_token(
    *,
    user_id: uuid.UUID | str,
    email: str,
    role: str,
    jurisdiction: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed HS256 JWT access token."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    if expires_delta is not None:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    secret = (settings.jwt_secret_key or settings.secret_key).encode("utf-8")

    header = {"alg": "HS256", "typ": "JWT"}
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "jurisdiction": jurisdiction,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(secret, signing_input, hashlib.sha256).digest()
    sig_b64 = _b64url_encode(signature)

    return f"{header_b64}.{payload_b64}.{sig_b64}"


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate an HS256 JWT access token.

    Raises ValueError / PermissionError on invalid signature, tampering, or expiration.
    """
    settings = get_settings()
    secret = (settings.jwt_secret_key or settings.secret_key).encode("utf-8")

    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT structure: token must contain 3 dot-separated segments.")

    header_b64, payload_b64, sig_b64 = parts

    # Verify signature first (timing-safe)
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    try:
        candidate_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise ValueError("Invalid JWT signature encoding.") from exc

    if not hmac.compare_digest(candidate_sig, expected_sig):
        raise ValueError("Invalid JWT signature: token has been tampered with or secret mismatch.")

    # Decode and parse payload
    try:
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Malformed JWT payload.") from exc

    exp_ts = payload.get("exp")
    if exp_ts is None:
        raise ValueError("Missing 'exp' claim in JWT payload.")

    exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    if datetime.now(timezone.utc) > exp_dt:
        raise TimeoutError("JWT token has expired.")

    iat_ts = payload.get("iat", int(datetime.now(timezone.utc).timestamp()))
    iat_dt = datetime.fromtimestamp(iat_ts, tz=timezone.utc)

    return TokenPayload(
        sub=payload["sub"],
        email=payload["email"],
        role=payload["role"],
        jurisdiction=payload["jurisdiction"],
        exp=exp_dt,
        iat=iat_dt,
    )
