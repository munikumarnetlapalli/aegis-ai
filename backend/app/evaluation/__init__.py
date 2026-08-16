"""Evaluation package for AegisAI — Milestone 6 (M6)."""
from app.evaluation.metrics.abstention import compute_abstention_metrics
from app.evaluation.metrics.rag import (
    compute_answer_relevance,
    compute_citation_completeness,
    compute_citation_correctness,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
)
from app.evaluation.metrics.red_team import compute_red_team_metrics, evaluate_red_team_case
from app.evaluation.metrics.retrieval import (
    evaluate_retrieval_batch,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.runner import EvaluationRunner

__all__ = [
    "EvaluationRunner",
    "recall_at_k",
    "precision_at_k",
    "reciprocal_rank",
    "ndcg_at_k",
    "evaluate_retrieval_batch",
    "compute_faithfulness",
    "compute_answer_relevance",
    "compute_context_precision",
    "compute_context_recall",
    "compute_citation_correctness",
    "compute_citation_completeness",
    "compute_abstention_metrics",
    "evaluate_red_team_case",
    "compute_red_team_metrics",
]
