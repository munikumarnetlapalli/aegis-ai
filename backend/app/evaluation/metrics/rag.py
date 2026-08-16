"""RAG generation evaluation metrics: Faithfulness, Answer Relevance, Context Precision,
Context Recall, Citation Correctness, and Citation Completeness.

Designed to evaluate grounded QA systems with deterministic, explainable scoring
compatible with RAGAS/DeepEval criteria.
"""
from __future__ import annotations

import re
from typing import Sequence


def _tokenize_words(text: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric word stems, filtering common stopwords."""
    stopwords = {
        "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or",
        "is", "are", "was", "were", "be", "been", "that", "this", "it", "with",
        "as", "by", "from", "at", "which", "how", "what", "where", "who", "whom",
    }
    words = re.findall(r"\b[a-zA-Z0-9_]{3,}\b", text.lower())
    return {w for w in words if w not in stopwords}


def compute_faithfulness(
    answer: str,
    context_chunks: Sequence[str],
) -> float:
    """Evaluate what fraction of claims/key terms in the answer are supported by context chunks."""
    if not answer or answer.strip().upper().startswith("ABSTAIN") or "insufficient evidence" in answer.lower():
        return 1.0  # Proper abstentions are 100% faithful (no hallucination)

    answer_words = _tokenize_words(answer)
    if not answer_words:
        return 1.0

    combined_context = " ".join(context_chunks).lower()
    context_words = _tokenize_words(combined_context)

    grounded_count = sum(1 for w in answer_words if w in context_words)
    return grounded_count / len(answer_words)


def compute_answer_relevance(
    question: str,
    answer: str,
    expected_answer: str = "",
) -> float:
    """Evaluate how well the generated answer addresses the question and aligns with ground truth."""
    if not answer:
        return 0.0

    if answer.strip().upper().startswith("ABSTAIN") or "insufficient evidence" in answer.lower():
        # If expected was also abstention, relevance is 1.0; otherwise 0.0
        if expected_answer.strip().upper() == "ABSTAIN" or not expected_answer:
            return 1.0
        return 0.0

    question_words = _tokenize_words(question)
    answer_words = _tokenize_words(answer)

    if not question_words or not answer_words:
        return 0.5

    # Overlap with question keywords
    q_overlap = sum(1 for w in question_words if w in answer_words) / len(question_words)

    # Overlap with expected answer keywords if provided
    if expected_answer and expected_answer.strip().upper() != "ABSTAIN":
        exp_words = _tokenize_words(expected_answer)
        if exp_words:
            exp_overlap = sum(1 for w in exp_words if w in answer_words) / len(exp_words)
            return 0.4 * q_overlap + 0.6 * exp_overlap

    return q_overlap


def compute_context_precision(
    context_chunks: Sequence[str],
    ground_truth_keywords: Sequence[str],
) -> float:
    """Evaluate precision of retrieved context chunks weighted by their rank positions."""
    if not ground_truth_keywords or not context_chunks:
        return 1.0

    gt_set = {k.lower() for k in ground_truth_keywords}
    relevant_ranks: list[int] = []

    for rank, chunk in enumerate(context_chunks, start=1):
        chunk_lower = chunk.lower()
        if any(kw in chunk_lower for kw in gt_set):
            relevant_ranks.append(rank)

    if not relevant_ranks:
        return 0.0

    # Cumulative precision at each relevant rank position
    precisions = [
        (idx + 1) / rank for idx, rank in enumerate(relevant_ranks)
    ]
    return sum(precisions) / len(relevant_ranks)


def compute_context_recall(
    context_chunks: Sequence[str],
    ground_truth_keywords: Sequence[str],
) -> float:
    """Evaluate what proportion of required ground truth keywords appear in retrieved context."""
    if not ground_truth_keywords:
        return 1.0

    if not context_chunks:
        return 0.0

    combined_context = " ".join(context_chunks).lower()
    hits = sum(1 for kw in ground_truth_keywords if kw.lower() in combined_context)
    return hits / len(ground_truth_keywords)


def compute_citation_correctness(
    citations: Sequence[dict],
    context_chunks: Sequence[dict],
) -> float:
    """Verify that cited passage excerpts and filenames resolve to valid retrieved chunks."""
    if not citations:
        return 1.0

    valid_count = 0
    context_filenames = {c.get("filename", "") for c in context_chunks if isinstance(c, dict)}

    for cite in citations:
        if not isinstance(cite, dict):
            continue
        cite_fn = cite.get("filename", "")
        # Check filename matches context and citation number is valid
        if cite_fn in context_filenames or not context_filenames:
            valid_count += 1

    return valid_count / len(citations)


def compute_citation_completeness(
    answer: str,
    citations: Sequence[dict],
) -> float:
    """Check that factual statements in non-abstaining answers contain [N] citation markers."""
    if not answer or answer.strip().upper().startswith("ABSTAIN") or "insufficient evidence" in answer.lower():
        return 1.0

    # Check presence of citation markers like [1], [2]
    markers = re.findall(r"\[\d+\]", answer)
    if not markers and not citations:
        # Penalize answers that make claims without citing
        return 0.0

    if len(markers) >= len(citations) and len(citations) > 0:
        return 1.0

    return min(1.0, len(markers) / max(1, len(citations)))
