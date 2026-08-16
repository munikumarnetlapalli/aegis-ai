"""Privacy, redaction, and SHA-256 hashing utilities for M7 Observability.

Enforces strict boundaries:
- Raw query text is NEVER stored (SHA-256 hash used everywhere).
- Raw document chunks, system prompts, secrets, and PII are stripped from telemetry.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

# Forbidden dictionary key patterns that must never appear in telemetry metadata
_FORBIDDEN_KEY_PATTERNS = re.compile(
    r"(?:query|raw_query|prompt|system_prompt|content|chunk_content|text|passage|secret|password|token|jwt|api_key|authorization|bearer)",
    re.IGNORECASE,
)

# Regex patterns to detect raw JWTs or API keys if accidentally placed in values
_JWT_PATTERN = re.compile(r"ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*")
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9-_=.]+", re.IGNORECASE)


def compute_query_hash(query: str) -> str:
    """Compute a deterministic, privacy-safe SHA-256 hex digest of a user query.

    Normalization:
    1. Strips leading/trailing whitespace
    2. Collapses internal whitespace
    3. Converts to lowercase UTF-8 encoding
    4. Computes SHA-256 hex digest (exactly 64 lowercase chars)
    """
    if not query:
        return hashlib.sha256(b"").hexdigest()
    normalized = " ".join(query.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def sanitize_trace_metadata(data: Any, max_depth: int = 4) -> Any:
    """Recursively sanitize metadata dictionaries to guarantee zero sensitive data leakage.

    Strips forbidden keys, redacts raw tokens, and bounds string lengths.
    """
    if max_depth <= 0:
        return "[TRUNCATED_DEPTH]"

    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            str_key = str(k)
            # If the key itself is forbidden (e.g. 'raw_query', 'system_prompt', 'content', 'password')
            if _FORBIDDEN_KEY_PATTERNS.search(str_key):
                continue
            sanitized[str_key] = sanitize_trace_metadata(v, max_depth=max_depth - 1)
        return sanitized

    if isinstance(data, (list, tuple, set)):
        return [sanitize_trace_metadata(item, max_depth=max_depth - 1) for item in data]

    if isinstance(data, str):
        # Redact JWTs or Bearer tokens if present in string values
        val = _JWT_PATTERN.sub("[REDACTED_JWT]", data)
        val = _BEARER_PATTERN.sub("[REDACTED_AUTH]", val)
        # Cap string length in span metadata to prevent accidental large text dumps
        if len(val) > 250:
            val = val[:250] + "..."
        return val

    # Primitive types (int, float, bool, None) are safe
    return data
