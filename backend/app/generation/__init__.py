"""Generation package — prompt building, LLM client, citation validation, abstention."""
from __future__ import annotations

from app.generation.abstention import (
    ABSTENTION_MESSAGE,
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    confidence_label,
    should_abstain,
)
from app.generation.citations import Citation, validate_citations
from app.generation.llm import LLMProvider, OllamaProvider, get_llm_provider
from app.generation.service import AnswerResponse, GenerationService

__all__ = [
    "ABSTENTION_MESSAGE",
    "CONFIDENCE_HIGH",
    "CONFIDENCE_LOW",
    "CONFIDENCE_MEDIUM",
    "AnswerResponse",
    "Citation",
    "GenerationService",
    "LLMProvider",
    "OllamaProvider",
    "confidence_label",
    "get_llm_provider",
    "should_abstain",
    "validate_citations",
]
