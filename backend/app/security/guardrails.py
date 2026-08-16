"""Prompt injection defense and adversarial input guardrails.

Detects attacks aimed at:
- System prompt extraction
- Instruction override ("ignore previous instructions")
- Role-play / jailbreaks (DAN, Developer Mode)
- Hidden delimiter injection
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Heuristic patterns matching common adversarial injection attempts
_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|commands|prompts|directions)", re.IGNORECASE),
        "Instruction override attempt",
    ),
    (
        re.compile(r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|commands|prompts|directions)", re.IGNORECASE),
        "Instruction disregard attempt",
    ),
    (
        re.compile(r"(?:reveal|print|show|repeat|display|output)\s+(?:your\s+)?(?:system\s+prompt|initial\s+instructions|system\s+instructions)", re.IGNORECASE),
        "System prompt extraction attempt",
    ),
    (
        re.compile(r"(?:you\s+are\s+now|act\s+as|pretend\s+to\s+be)\s+(?:DAN|developer\s+mode|unfiltered\s+ai|an\s+unrestricted)", re.IGNORECASE),
        "Jailbreak / persona hijack attempt",
    ),
    (
        re.compile(r"(?:bypass|disable|turn\s+off)\s+(?:safety|security|jurisdiction|guardrails|rbac|filters)", re.IGNORECASE),
        "Guardrail bypass attempt",
    ),
    (
        re.compile(r"\[\s*SYSTEM\s*\]|\<\s*system\s*\>|```\s*system", re.IGNORECASE),
        "System delimiter injection attempt",
    ),
]


def scan_prompt_injection(text: str) -> tuple[bool, str]:
    """Scan query text for adversarial prompt-injection patterns.

    Returns:
        (is_flagged: bool, reason: str)
    """
    if not text:
        return False, ""

    for pattern, reason in _INJECTION_PATTERNS:
        if pattern.search(text):
            logger.warning("Prompt injection detected: %s in text: %r", reason, text[:120])
            return True, reason

    return False, ""


def sanitize_input(text: str) -> str:
    """Strip dangerous control characters while preserving standard punctuation."""
    if not text:
        return ""
    # Remove non-printable control characters except newline and tab
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or (32 <= ord(ch) <= 126) or ord(ch) > 127)
    return cleaned.strip()
