"""Retrieval evaluation metrics: Recall@K, Precision@K, MRR, and nDCG@K.

Standard information retrieval formulas:
- Recall@K = |Retrieved_K ∩ Relevant| / |Relevant|
- Precision@K = |Retrieved_K ∩ Relevant| / K
- Reciprocal Rank (RR) = 1 / rank_first_relevant (or 0 if none found)
- nDCG@K = DCG@K / IDCG@K where DCG@K = sum_{i=1}^K (rel_i / log2(i + 1))
"""
from __future__ import annotations

import math
from typing import Sequence


def recall_at_k(
    retrieved_items: Sequence[str],
    relevant_items: set[str],
    k: int = 5,
) -> float:
    """Compute Recall at rank K."""
    if not relevant_items:
        return 1.0  # Empty relevance set is vacuously satisfied

    top_k = retrieved_items[:k]
    hits = sum(1 for item in top_k if item in relevant_items)
    return hits / len(relevant_items)


def precision_at_k(
    retrieved_items: Sequence[str],
    relevant_items: set[str],
    k: int = 5,
) -> float:
    """Compute Precision at rank K."""
    if k <= 0:
        return 0.0

    top_k = retrieved_items[:k]
    if not top_k:
        return 0.0

    hits = sum(1 for item in top_k if item in relevant_items)
    return hits / len(top_k)


def reciprocal_rank(
    retrieved_items: Sequence[str],
    relevant_items: set[str],
) -> float:
    """Compute Reciprocal Rank (1/rank of first hit, 1-indexed)."""
    if not relevant_items:
        return 1.0

    for rank, item in enumerate(retrieved_items, start=1):
        if item in relevant_items:
            return 1.0 / rank

    return 0.0


def ndcg_at_k(
    retrieved_items: Sequence[str],
    relevant_items: set[str],
    k: int = 5,
) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank K."""
    if not relevant_items:
        return 1.0

    top_k = retrieved_items[:k]
    if not top_k:
        return 0.0

    # Calculate DCG@K
    dcg = 0.0
    for i, item in enumerate(top_k):
        rel = 1.0 if item in relevant_items else 0.0
        if rel > 0:
            dcg += rel / math.log2(i + 2)  # i=0 -> rank 1 -> log2(2) = 1

    # Calculate Ideal DCG@K (IDCG)
    ideal_hits = min(len(relevant_items), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))

    if idcg <= 0.0:
        return 0.0

    return dcg / idcg


def evaluate_retrieval_batch(
    retrieved_batch: list[list[str]],
    relevant_batch: list[set[str]],
    k: int = 5,
) -> dict[str, float]:
    """Compute average retrieval metrics over a batch of queries."""
    if not retrieved_batch:
        return {"recall_at_k": 0.0, "precision_at_k": 0.0, "mrr": 0.0, "ndcg_at_k": 0.0}

    n = len(retrieved_batch)
    recalls = [recall_at_k(r, rel, k=k) for r, rel in zip(retrieved_batch, relevant_batch)]
    precisions = [precision_at_k(r, rel, k=k) for r, rel in zip(retrieved_batch, relevant_batch)]
    mrrs = [reciprocal_rank(r, rel) for r, rel in zip(retrieved_batch, relevant_batch)]
    ndcgs = [ndcg_at_k(r, rel, k=k) for r, rel in zip(retrieved_batch, relevant_batch)]

    return {
        f"recall_at_{k}": sum(recalls) / n,
        f"precision_at_{k}": sum(precisions) / n,
        "mrr": sum(mrrs) / n,
        f"ndcg_at_{k}": sum(ndcgs) / n,
    }
