"""Embedding provider interface and implementations.

All embedding calls must go through this interface so that the provider
(local sentence-transformers, Azure OpenAI, etc.) can be swapped without
touching any other code.

Local dev: sentence-transformers/all-MiniLM-L6-v2  (384-dim, no GPU required)
Production: configured via EMBEDDING_PROVIDER / EMBEDDING_MODEL env vars
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ── Abstract interface ─────────────────────────────────────────────────────────

class EmbeddingProvider(ABC):
    """Interface that all embedding implementations must satisfy."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of document texts.  Returns a list of float vectors."""
        ...

    @abstractmethod
    def embed_query(self, query: str) -> list[float]:
        """Embed a single query string.  Returns a float vector."""
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        """The output vector dimension for this provider."""
        ...


# ── Local sentence-transformers implementation ─────────────────────────────────

class LocalSentenceTransformerProvider(EmbeddingProvider):
    """Embedding provider backed by sentence-transformers (CPU-only, local).

    The underlying model is lazy-loaded on first use and cached for the process
    lifetime.  Thread-safe via a lock — only one thread loads the model.
    """

    _lock = threading.Lock()
    _model = None  # class-level cache

    def __init__(self, model_name: str, dim: int) -> None:
        self._model_name = model_name
        self._dim = dim

    def _get_model(self):
        """Lazy-load the model on first call (thread-safe)."""
        if LocalSentenceTransformerProvider._model is None:
            with LocalSentenceTransformerProvider._lock:
                if LocalSentenceTransformerProvider._model is None:
                    logger.info(
                        "Loading embedding model %r (first call — may take a moment)",
                        self._model_name,
                    )
                    from sentence_transformers import SentenceTransformer  # noqa: PLC0415

                    LocalSentenceTransformerProvider._model = SentenceTransformer(
                        self._model_name
                    )
                    logger.info("Embedding model loaded.")
        return LocalSentenceTransformerProvider._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        vectors = model.encode(texts, batch_size=32, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_query(self, query: str) -> list[float]:
        model = self._get_model()
        vector = model.encode([query], show_progress_bar=False)[0]
        return vector.tolist()

    @property
    def dimension(self) -> int:
        return self._dim


# ── Factory ────────────────────────────────────────────────────────────────────

_provider_instance: EmbeddingProvider | None = None
_provider_lock = threading.Lock()


def get_embedding_provider() -> EmbeddingProvider:
    """Return the configured embedding provider singleton.

    Provider selection is driven entirely by Settings — never by application code.
    """
    global _provider_instance  # noqa: PLW0603
    if _provider_instance is None:
        with _provider_lock:
            if _provider_instance is None:
                from app.core.config import get_settings  # noqa: PLC0415

                settings = get_settings()
                if settings.embedding_provider == "local":
                    _provider_instance = LocalSentenceTransformerProvider(
                        model_name=settings.embedding_model,
                        dim=settings.embedding_dim,
                    )
                else:
                    raise NotImplementedError(
                        f"Embedding provider {settings.embedding_provider!r} "
                        "is not implemented yet."
                    )
                logger.info(
                    "Embedding provider: %s / %s (dim=%d)",
                    settings.embedding_provider,
                    settings.embedding_model,
                    settings.embedding_dim,
                )
    return _provider_instance
