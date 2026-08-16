"""Password hashing and verification.

Uses PBKDF2-HMAC-SHA256 with 100,000 iterations and a cryptographically
random 16-byte salt. Timing-safe comparisons via `hmac.compare_digest`.

Format: `pbkdf2_sha256$iterations$salt_hex$hash_hex`
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

_ITERATIONS = 100_000
_ALGORITHM = "sha256"


def hash_password(password: str) -> str:
    """Hash a plaintext password with a random salt."""
    if not password:
        raise ValueError("Password cannot be empty")
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        _ALGORITHM, password.encode("utf-8"), salt, _ITERATIONS
    )
    return f"pbkdf2_{_ALGORITHM}${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2 hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != f"pbkdf2_{_ALGORITHM}":
            return False
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected_hash = bytes.fromhex(parts[3])

        candidate_hash = hashlib.pbkdf2_hmac(
            _ALGORITHM, plain_password.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(candidate_hash, expected_hash)
    except Exception:
        return False
