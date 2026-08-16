"""PII detection, redaction, and blocking engine.

Detects and processes regulated PII and sensitive identifiers:
- Social Security Numbers (SSN) and Tax IDs (TIN / EIN)
- Email addresses
- Phone numbers (domestic and international)
- Physical street addresses and PO Boxes
- Financial identifiers (Credit Cards, IBANs, Bank Routing/Account numbers)
- Government IDs (Driver's Licenses, Passports, National IDs)
- Vehicle Identification Numbers (VIN)
- IP Addresses (IPv4 and IPv6)

Supports two policies:
- 'redact': Replaces detected PII values with typed tokens (e.g. [SSN_REDACTED])
- 'block': Replaces the entire content with a security refusal message
"""
from __future__ import annotations

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

PII_BLOCKED_MESSAGE = "This response was blocked because it contains protected personal data (PII)."

# Presidio-class regular expressions for comprehensive PII detection
_PII_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    # ── 1. SSN & Tax Identifiers ───────────────────────────────────────────────
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "SSN",
        "[SSN_REDACTED]",
    ),
    (
        re.compile(r"\b\d{3}\s\d{2}\s\d{4}\b"),
        "SSN",
        "[SSN_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:social\s+security\s+number|social\s+security\s+no\.?)\b"
        ),
        "SSN",
        "[SSN_REDACTED]",
    ),
    (
        re.compile(r"\b\d{2}-\d{7}\b"),  # US EIN
        "TAX_ID",
        "[TAX_ID_REDACTED]",
    ),

    # ── 2. Email Addresses ────────────────────────────────────────────────────
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"),
        "EMAIL",
        "[EMAIL_REDACTED]",
    ),

    # ── 3. Phone Numbers ──────────────────────────────────────────────────────
    (
        re.compile(
            r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
        ),
        "PHONE",
        "[PHONE_REDACTED]",
    ),
    (
        re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"),
        "PHONE",
        "[PHONE_REDACTED]",
    ),

    # ── 4. Financial Identifiers (Credit Cards, IBAN, Bank Accounts) ──────────
    (
        re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b|\b\d{15,16}\b"),
        "CREDIT_CARD",
        "[FINANCIAL_ID_REDACTED]",
    ),
    (
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{4,30}\b"),
        "IBAN",
        "[FINANCIAL_ID_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:routing|aba|bank\s*account)\s*(?:number|no|#)?\s*[:\s]?\s*(\d{8,17})\b"
        ),
        "BANK_ACCOUNT",
        "[FINANCIAL_ID_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:credit\s*card\s*number|bank\s*account\s*number)\b"
        ),
        "FINANCIAL_ID",
        "[FINANCIAL_ID_REDACTED]",
    ),

    # ── 5. Government & Vehicle IDs (VIN, Driver License, Passport) ───────────
    (
        re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b"),  # Standard 17-character VIN
        "VIN",
        "[VIN_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:vehicle(?:'s)?\s+VIN(?:\s*\([^)]*\))?|VIN\s*\([^)]*vehicle\s*identification\s*number[^)]*\)|vehicle\s+identification\s+number)\b"
        ),
        "VIN",
        "[VIN_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:vin)\s*[:#]\s*([A-HJ-NPR-Z0-9-]{10,20})\b"
        ),
        "VIN",
        "[VIN_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:driver'?s?\s*license|dl|license\s*no)\s*(?:number|no|#)?\s*[:\s]?\s*([A-Z0-9-]{5,18})\b"
        ),
        "DRIVER_LICENSE",
        "[GOV_ID_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:passport)\s*(?:number|no|#)?\s*[:\s]?\s*([A-Z0-9]{6,12})\b"
        ),
        "PASSPORT",
        "[GOV_ID_REDACTED]",
    ),
    (
        re.compile(
            r"(?i)\b(?:national\s*id|identity\s*card|gov(?:ernment)?\s*id)\s*[:#]?\s*([A-Z0-9-]{6,20})\b"
        ),
        "GOV_ID",
        "[GOV_ID_REDACTED]",
    ),

    # ── 6. Physical Addresses & PO Boxes ──────────────────────────────────────
    (
        re.compile(
            r"\b\d{1,5}\s+(?:[A-Z][a-zA-Z0-9\.]*\s+){1,4}(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Way|Court|Ct|Circle|Cir|Highway|Hwy|Place|Pl|Terrace|Ter|Trail|Trl|Parkway|Pkwy|Suite|Ste|Apt|Unit)\b\.?"
        ),
        "ADDRESS",
        "[ADDRESS_REDACTED]",
    ),
    (
        re.compile(r"\b(?:P\.?O\.?\s*Box\s+\d+)\b", re.IGNORECASE),
        "ADDRESS",
        "[ADDRESS_REDACTED]",
    ),

    # ── 7. IP Addresses (IPv4 & IPv6) ─────────────────────────────────────────
    (
        re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        ),
        "IP_ADDRESS",
        "[IP_REDACTED]",
    ),
    (
        re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b"),
        "IP_ADDRESS",
        "[IP_REDACTED]",
    ),
]


def redact_pii(text: str) -> tuple[str, list[dict]]:
    """Scan and redact sensitive PII entities from text.

    Returns:
        (redacted_text: str, detected_entities: list[dict])
    """
    if not text:
        return "", []

    redacted = text
    detected = []

    for pattern, entity_type, replacement in _PII_PATTERNS:
        for match in pattern.finditer(text):
            val = match.group()
            # Basic validation to avoid false positives on small numbers for phone
            if entity_type == "PHONE" and len(re.sub(r"\D", "", val)) < 10:
                continue
            detected.append(
                {
                    "type": entity_type,
                    "value": val,
                    "start": match.start(),
                    "end": match.end(),
                }
            )

        redacted = pattern.sub(replacement, redacted)

    if detected:
        logger.info("PII detection: %d entities found and redacted", len(detected))

    return redacted, detected


def apply_pii_policy(
    text: str, policy: Literal["redact", "block"] = "redact"
) -> tuple[str, bool, list[dict]]:
    """Apply the configured PII defense policy to text.

    Returns:
        (filtered_text: str, is_blocked: bool, detected_entities: list[dict])
    """
    if not text:
        return "", False, []

    redacted_text, detected = redact_pii(text)

    if not detected:
        return text, False, []

    if policy == "block":
        logger.warning(
            "PII policy=BLOCK triggered for text containing %d entities",
            len(detected),
        )
        return PII_BLOCKED_MESSAGE, True, detected

    # Default policy: redact
    return redacted_text, False, detected


def has_pii(text: str) -> bool:
    """Return True if any regulated PII entities are present in text."""
    _, detected = redact_pii(text)
    return len(detected) > 0
