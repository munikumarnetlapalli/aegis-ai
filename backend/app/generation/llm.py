"""LLM provider interface and Ollama implementation.

Architecture rule: all LLM calls must go through the LLMProvider interface.
Provider selection is driven entirely by configuration (llm_provider env var).

Local dev:  OllamaProvider → llama3.2 (or any model pulled in the ollama container)
Production: AzureOpenAIProvider (M8+) — same interface, different implementation.

The Ollama provider uses httpx async calls so it integrates cleanly into the
FastAPI async request context without blocking.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

logger = logging.getLogger(__name__)

# Timeout for Ollama LLM calls. Suitable for local CPU inference.
_LLM_TIMEOUT_SECONDS = 180.0


# ── Abstract interface ─────────────────────────────────────────────────────────

class LLMProvider(ABC):
    """Interface all LLM implementations must satisfy."""

    @abstractmethod
    async def generate(self, messages: list[dict], **kwargs) -> str:
        """Generate a response from a list of chat messages.

        Parameters
        ----------
        messages : list[dict]
            OpenAI-style message list: [{"role": "system"|"user"|"assistant", "content": str}]

        Returns
        -------
        str
            The generated assistant response text.
        """
        ...


# ── Ollama implementation ──────────────────────────────────────────────────────

class OllamaProvider(LLMProvider):
    """LLM provider backed by a local Ollama server.

    Calls the Ollama /api/chat endpoint over HTTP using httpx async.
    Gracefully degrades if Ollama is unreachable (returns abstention fallback).
    """

    def __init__(self, base_url: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model

    async def generate(self, messages: list[dict], **kwargs) -> str:
        timeout = kwargs.pop("timeout", _LLM_TIMEOUT_SECONDS)
        options = {"num_predict": 160, "temperature": 0.0, **kwargs.pop("options", {})}
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": options,
            **kwargs,
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{self._base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content: str = data["message"]["content"]
                logger.info(
                    "Ollama [%s]: generated %d chars", self._model, len(content)
                )
                return content
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning(
                "Ollama unreachable or timed out (%s) at %s — returning abstention fallback",
                type(exc).__name__,
                self._base_url,
            )
            return (
                "I'm unable to generate an answer right now because the language model "
                "service is unavailable or timed out. Please try again later."
            )
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama HTTP error %s: %s", exc.response.status_code, exc)
            raise
        except Exception as exc:
            logger.exception("Unexpected error calling Ollama: %s", exc)
            raise


# ── Factory ────────────────────────────────────────────────────────────────────

_llm_instance: LLMProvider | None = None


def get_llm_provider() -> LLMProvider:
    """Return the configured LLM provider singleton."""
    global _llm_instance  # noqa: PLW0603
    if _llm_instance is None:
        from app.core.config import get_settings  # noqa: PLC0415

        settings = get_settings()
        if settings.llm_provider == "ollama":
            _llm_instance = OllamaProvider(
                base_url=settings.ollama_base_url,
                model=settings.llm_model,
            )
            logger.info(
                "LLM provider: ollama / %s @ %s",
                settings.llm_model,
                settings.ollama_base_url,
            )
        else:
            raise NotImplementedError(
                f"LLM provider {settings.llm_provider!r} is not implemented yet."
            )
    return _llm_instance
