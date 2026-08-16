"""Security package — authentication, RBAC, jurisdiction, PII, guardrails, audit."""
from __future__ import annotations

from app.security.audit import audit_log
from app.security.auth import TokenPayload, create_access_token, decode_access_token
from app.security.dependencies import (
    bearer_scheme,
    get_current_user,
    get_optional_user,
    require_roles,
)
from app.security.guardrails import sanitize_input, scan_prompt_injection
from app.security.password import hash_password, verify_password
from app.security.pii import (
    PII_BLOCKED_MESSAGE,
    apply_pii_policy,
    has_pii,
    redact_pii,
)
from app.security.rate_limit import (
    InMemorySlidingWindowRateLimiter,
    RateLimiter,
    check_rate_limit_or_raise,
    get_rate_limiter,
)

__all__ = [
    "InMemorySlidingWindowRateLimiter",
    "PII_BLOCKED_MESSAGE",
    "RateLimiter",
    "TokenPayload",
    "apply_pii_policy",
    "audit_log",
    "bearer_scheme",
    "check_rate_limit_or_raise",
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "get_optional_user",
    "get_rate_limiter",
    "has_pii",
    "hash_password",
    "redact_pii",
    "require_roles",
    "sanitize_input",
    "scan_prompt_injection",
    "verify_password",
]

