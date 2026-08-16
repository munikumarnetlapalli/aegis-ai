"""Reciprocal Rank Fusion (RRF) — hybrid retrieval merge.

Merges dense (pgvector cosine) and sparse (BM25) result lists into a single
ranked list using the RRF formula from Cormack et al. (2009):

    score(d) = Σ_r  1 / (k + rank_r(d))

where k is a constant that controls how steeply scores drop off.
The standard value k=60 works well in practice; expose it as a parameter
so it can be tuned against the golden evaluation set in M6.

Design:
- Pure Python, no external dependencies.
- Chunk deduplication: if a chunk appears in both lists, its RRF scores
  are *summed* (i.e. it is rewarded for appearing in both rankings).
- The Provenance object from the first-seen occurrence of a chunk is kept;
  they should always be identical for the same chunk_id.
"""
from __future__ import annotations

import uuid

from app.retrieval.service import RetrievalResult


def reciprocal_rank_fusion(
    *ranked_lists: list[RetrievalResult],
    k: int = 60,
    top_n: int | None = None,
) -> list[RetrievalResult]:
    """Merge one or more ranked result lists using Reciprocal Rank Fusion.

    Parameters
    ----------
    *ranked_lists : list[RetrievalResult]
        Any number of ranked result lists (typically 2: dense + BM25).
        Each list should be ordered best → worst.
    k : int
        RRF constant.  Higher values reduce the penalty for lower-ranked items.
        Default 60 is the value from the original paper.
    top_n : int | None
        If provided, trim the output to the top-n results.

    Returns
    -------
    list[RetrievalResult]
        Merged results, sorted by RRF score descending.
        The `score` field on each result holds the cumulative RRF score.
    """
    # Map chunk_id → cumulative RRF score
    rrf_scores: dict[uuid.UUID, float] = {}
    # Keep the first-seen RetrievalResult so we preserve provenance.
    first_seen: dict[uuid.UUID, RetrievalResult] = {}

    for ranked_list in ranked_lists:
        for rank, result in enumerate(ranked_list, start=1):
            cid = result.chunk_id
            rrf_score = 1.0 / (k + rank)
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + rrf_score
            if cid not in first_seen:
                first_seen[cid] = result

    # Sort by cumulative RRF score, highest first
    sorted_ids = sorted(rrf_scores, key=lambda cid: rrf_scores[cid], reverse=True)

    if top_n is not None:
        sorted_ids = sorted_ids[:top_n]

    merged: list[RetrievalResult] = []
    for cid in sorted_ids:
        original = first_seen[cid]
        # Replace the retriever-specific score with the RRF score
        merged.append(
            RetrievalResult(
                chunk_id=original.chunk_id,
                content=original.content,
                score=rrf_scores[cid],
                provenance=original.provenance,
            )
        )

    return merged
