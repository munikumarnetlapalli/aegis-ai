"""Evidence threshold and abstention logic.

Design principle:
    Abstain rather than hallucinate.  This module decides whether the retrieved
    evidence is strong enough to attempt generation.  If not, a canned
    abstention message is returned instead of an LLM call.

Thresholds are configurable from Settings so they can be tuned against the
M6 golden evaluation set.  The defaults are deliberately permissive (never
abstain on score alone) until we have evaluation data to justify tighter values.

Abstention criteria (all configurable):
1. Top chunk reranker score < evidence_threshold
2. Number of valid evidence chunks < min_evidence_chunks
"""
from __future__ import annotations

from app.retrieval.service import RetrievalResult

# The message returned to the client when evidence is insufficient.
ABSTENTION_MESSAGE = (
    "I don't have confident citations to answer this question. "
    "The available documents do not provide sufficient evidence."
)

# Confidence labels returned with the answer.
CONFIDENCE_HIGH = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW = "low"


def should_abstain(
    results: list[RetrievalResult],
    threshold: float = -7.0,
    min_chunks: int = 1,
) -> bool:
    """Return True if evidence is insufficient to attempt generation.

    Parameters
    ----------
    results : list[RetrievalResult]
        Reranked results (best first). Scores are cross-encoder logits.
    threshold : float
        Minimum acceptable score for the top chunk.
        - < -7.0: hard abstention (irrelevant/trap queries)
        - >= -7.0: soft/strong evidence (proceed to grounded generation)
    min_chunks : int
        Minimum number of chunks required.

    Returns
    -------
    bool
        True → hard abstain. False → proceed with generation.
    """
    if not results or len(results) < min_chunks:
        return True
    if results[0].score < threshold:
        return True
    return False


def confidence_label(results: list[RetrievalResult]) -> str:
    """Return a human-readable confidence label based on top-chunk score.

    Score ranges (cross-encoder ms-marco-MiniLM logits):
        > 5.0     → high     (very strong relevance signal)
        1.0–5.0   → medium   (standard relevance)
        < 1.0     → low      (soft/moderate evidence)
    """
    if not results:
        return CONFIDENCE_LOW
    top_score = results[0].score
    if top_score > 5.0:
        return CONFIDENCE_HIGH
    if top_score >= 1.0:
        return CONFIDENCE_MEDIUM
    return CONFIDENCE_LOW


