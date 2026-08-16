"""Structured security audit logging.

Outputs machine-readable JSON logs for all security-sensitive events:
- Authentication success / failures
- Authorization denials & cross-jurisdiction blocks
- Adversarial prompt-injection attempts
- PII redactions
- Document uploads & queries
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aegis.audit")


def audit_log(
    event_type: str,
    *,
    user_id: str | None = None,
    email: str | None = None,
    role: str | None = None,
    jurisdiction: str | None = None,
    ip_address: str | None = None,
    status: str = "SUCCESS",
    details: dict[str, Any] | None = None,
) -> None:
    """Emit a structured security audit log record."""
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "audit_event": event_type,
        "user_id": user_id or "anonymous",
        "email": email or "anonymous",
        "role": role or "anonymous",
        "jurisdiction": jurisdiction or "GLOBAL",
        "ip_address": ip_address or "unknown",
        "status": status,
        "details": details or {},
    }
    logger.info(json.dumps(record))
