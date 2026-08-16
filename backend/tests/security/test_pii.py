"""Security tests for PII detection, redaction, and policy enforcement engine.

Verifies:
- SSN, Email, Phone, Credit Card, IP Address, VIN, Address, and Gov ID detection
- Policy enforcement (redact vs block)
- End-to-end integration test through GenerationService
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.generation.service import GenerationService
from app.retrieval.service import Provenance, RetrievalResult
from app.security.pii import (
    PII_BLOCKED_MESSAGE,
    apply_pii_policy,
    has_pii,
    redact_pii,
)


def test_redact_email():
    text = "Please send the settlement form to claim.officer@insurance-eu.org by Monday."
    redacted, matches = redact_pii(text)
    assert "[EMAIL_REDACTED]" in redacted
    assert "claim.officer@insurance-eu.org" not in redacted
    assert len(matches) == 1
    assert matches[0]["type"] == "EMAIL"


def test_redact_ssn():
    text = "The claimant identification number is SSN: 123-45-6789."
    redacted, matches = redact_pii(text)
    assert "[SSN_REDACTED]" in redacted
    assert "123-45-6789" not in redacted
    assert len(matches) == 1
    assert matches[0]["type"] == "SSN"


def test_redact_credit_card():
    text = "Refund will be credited to card 4532-8901-2345-6789."
    redacted, matches = redact_pii(text)
    assert "[FINANCIAL_ID_REDACTED]" in redacted
    assert "4532-8901-2345-6789" not in redacted
    assert len(matches) == 1
    assert matches[0]["type"] == "CREDIT_CARD"


def test_redact_phone():
    text = "Contact the adjuster at (555) 234-5678 or +1-800-555-0199."
    redacted, matches = redact_pii(text)
    assert "[PHONE_REDACTED]" in redacted
    assert "(555) 234-5678" not in redacted
    assert len(matches) >= 1


def test_redact_ip_address():
    text = "Origin server detected at 192.168.1.105 during the connection."
    redacted, matches = redact_pii(text)
    assert "[IP_REDACTED]" in redacted
    assert "192.168.1.105" not in redacted
    assert len(matches) == 1
    assert matches[0]["type"] == "IP_ADDRESS"


def test_redact_vin():
    text = "Insured vehicle has VIN: 1HGCR2F83HA123456 registered in EU."
    redacted, matches = redact_pii(text)
    assert "[VIN_REDACTED]" in redacted
    assert "1HGCR2F83HA123456" not in redacted
    assert len(matches) >= 1


def test_redact_physical_address():
    text = "Send documents to 742 Evergreen Terrace, Springfield by mail."
    redacted, matches = redact_pii(text)
    assert "[ADDRESS_REDACTED]" in redacted
    assert "742 Evergreen Terrace" not in redacted
    assert len(matches) == 1
    assert matches[0]["type"] == "ADDRESS"


def test_clean_text_unchanged():
    text = "The policy specifies a 30-day settlement period after receipt of documentation."
    redacted, matches = redact_pii(text)
    assert redacted == text
    assert len(matches) == 0
    assert has_pii(text) is False


def test_apply_pii_policy_block():
    text = "Claimant SSN is 123-45-6789."
    filtered, is_blocked, matches = apply_pii_policy(text, policy="block")
    assert is_blocked is True
    assert filtered == PII_BLOCKED_MESSAGE
    assert len(matches) == 1


def test_apply_pii_policy_redact():
    text = "Claimant SSN is 123-45-6789 and email is user@domain.com."
    filtered, is_blocked, matches = apply_pii_policy(text, policy="redact")
    assert is_blocked is False
    assert "[SSN_REDACTED]" in filtered
    assert "[EMAIL_REDACTED]" in filtered
    assert "123-45-6789" not in filtered
    assert len(matches) == 2


# ── Full End-to-End Pipeline Test with GenerationService ──────────────────────

@pytest.mark.asyncio
async def test_generation_service_end_to_end_pii_redaction():
    """Verify that GenerationService redacts PII before returning the final AnswerResponse."""
    svc = GenerationService()
    chunk_id = uuid.uuid4()
    context = [
        RetrievalResult(
            chunk_id=chunk_id,
            content="Quote requires SSN 987-65-4321 and VIN 1HGCR2F83HA987654.",
            score=5.0,
            provenance=Provenance(
                document_id=uuid.uuid4(),
                filename="quote_rules.pdf",
                page=1,
                section="§3",
                jurisdiction="GLOBAL",
                chunk_index=0,
            ),
        )
    ]

    mock_llm_response = (
        "Under the quote policy, the insurer requires SSN 987-65-4321, email agent@quote.com, "
        "and vehicle VIN 1HGCR2F83HA987654 [1]."
    )

    with patch("app.generation.service.get_llm_provider") as mock_provider_fn:
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = mock_llm_response
        mock_provider_fn.return_value = mock_provider

        res = await svc.answer(
            query="What is required for a quote?",
            context_chunks=context,
        )

    # Verify PII is redacted from the final answer
    assert "987-65-4321" not in res.answer
    assert "agent@quote.com" not in res.answer
    assert "1HGCR2F83HA987654" not in res.answer
    assert "[SSN_REDACTED]" in res.answer
    assert "[EMAIL_REDACTED]" in res.answer
    assert "[VIN_REDACTED]" in res.answer

    # Verify citations also have PII redacted in excerpts
    assert len(res.citations) == 1
    assert "987-65-4321" not in res.citations[0].excerpt
    assert "[SSN_REDACTED]" in res.citations[0].excerpt
