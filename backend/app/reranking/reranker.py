"""Cross-encoder reranker interface and implementation.

Architecture rule: all rerankers must implement the Reranker ABC.
This ensures the reranker can be swapped (e.g. Cohere reranker, Azure ML)
without touching any calling code.

Local dev: cross-encoder/ms-marco-MiniLM-L-6-v2 (no GPU required).
Production: configure via RERANKER_MODEL env var.

The model is lazy-loaded on first call and cached for the process lifetime
(same pattern as LocalSentenceTransformerProvider).
"""
from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod

from app.retrieval.service import RetrievalResult

logger = logging.getLogger(__name__)


# ── Abstract interface ─────────────────────────────────────────────────────────

class Reranker(ABC):
    """Interface all reranker implementations must satisfy."""

    @abstractmethod
    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        """Re-score and sort results by relevance to query.

        Parameters
        ----------
        query : str
            The original user query.
        results : list[RetrievalResult]
            Candidate chunks from the hybrid retrieval stage.
        top_k : int | None
            If provided, return only the top-k results after reranking.

        Returns
        -------
        list[RetrievalResult]
            Results sorted by cross-encoder score descending.
            The `score` field is replaced with the cross-encoder score.
        """
        ...


# ── CrossEncoder implementation ────────────────────────────────────────────────

class CrossEncoderReranker(Reranker):
    """Reranker backed by sentence-transformers CrossEncoder.

    Lazy-loads the model on first call; thread-safe via a lock.
    Uses the same dependency (sentence-transformers) as the embedding provider.
    """

    _lock = threading.Lock()
    _model: dict[str, object] = {}  # model_name → CrossEncoder instance

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    def _get_model(self):
        if self._model_name not in CrossEncoderReranker._model:
            with CrossEncoderReranker._lock:
                if self._model_name not in CrossEncoderReranker._model:
                    logger.info(
                        "Loading cross-encoder reranker %r (first call — may take a moment)",
                        self._model_name,
                    )
                    from sentence_transformers import CrossEncoder  # noqa: PLC0415

                    CrossEncoderReranker._model[self._model_name] = CrossEncoder(
                        self._model_name
                    )
                    logger.info("Reranker model loaded.")
        return CrossEncoderReranker._model[self._model_name]

    def rerank(
        self,
        query: str,
        results: list[RetrievalResult],
        top_k: int | None = None,
    ) -> list[RetrievalResult]:
        if not results:
            return []

        model = self._get_model()
        pairs = [[query, r.content] for r in results]
        scores = model.predict(pairs)

        # Sort results by cross-encoder score descending
        ranked = sorted(
            zip(scores, results),
            key=lambda x: float(x[0]),
            reverse=True,
        )

        if top_k is not None:
            ranked = ranked[:top_k]

        reranked: list[RetrievalResult] = []
        for score, result in ranked:
            reranked.append(
                RetrievalResult(
                    chunk_id=result.chunk_id,
                    content=result.content,
                    score=float(score),
                    provenance=result.provenance,
                )
            )

        logger.info(
            "Reranker: %d candidates → %d results (top score=%.4f)",
            len(results),
            len(reranked),
            reranked[0].score if reranked else 0.0,
        )
        return reranked


# ── Factory ────────────────────────────────────────────────────────────────────

_reranker_instance: Reranker | None = None
_reranker_lock = threading.Lock()


def get_reranker() -> Reranker:
    """Return the configured reranker singleton."""
    global _reranker_instance  # noqa: PLW0603
    if _reranker_instance is None:
        with _reranker_lock:
            if _reranker_instance is None:
                from app.core.config import get_settings  # noqa: PLC0415

                settings = get_settings()
                _reranker_instance = CrossEncoderReranker(
                    model_name=settings.reranker_model
                )
                logger.info("Reranker: %s", settings.reranker_model)
    return _reranker_instance
