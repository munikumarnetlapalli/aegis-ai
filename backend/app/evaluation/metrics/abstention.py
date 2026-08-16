"""Abstention calibration and hallucination prevention metrics.

Evaluates how accurately the system answers supported queries while refusing
unsupported / out-of-domain / hallucination-trap queries.

Metrics:
- Abstention Accuracy: (True Answers + True Abstentions) / Total
- False Answer Rate: Hallucinating on unanswerable/unsupported queries
- False Abstention Rate: Refusing on legitimate answerable queries
"""
from __future__ import annotations

from typing import Sequence


def evaluate_abstention_decision(
    is_answerable: bool,
    did_abstain: bool,
) -> str:
    """Classify the abstention outcome."""
    if is_answerable and not did_abstain:
        return "CORRECT_ANSWER"
    elif not is_answerable and did_abstain:
        return "CORRECT_ABSTAIN"
    elif not is_answerable and not did_abstain:
        return "FALSE_ANSWER"  # Hallucinated answer on unsupported query
    else:
        return "FALSE_ABSTAIN"  # Over-abstention on valid query


def compute_abstention_metrics(
    eval_results: Sequence[dict],
) -> dict[str, float]:
    """Compute aggregate abstention performance across an evaluation dataset.

    Each item in eval_results must have:
    - 'is_answerable': bool (or category != 'unanswerable')
    - 'abstained': bool
    """
    if not eval_results:
        return {
            "abstention_accuracy": 1.0,
            "false_answer_rate": 0.0,
            "false_abstention_rate": 0.0,
            "total_evaluated": 0,
            "correct_answers": 0,
            "correct_abstentions": 0,
            "false_answers": 0,
            "false_abstentions": 0,
        }

    correct_answers = 0
    correct_abstains = 0
    false_answers = 0
    false_abstains = 0

    total_answerable = 0
    total_unanswerable = 0

    for item in eval_results:
        is_ans = item.get("is_answerable", True)
        abstained = item.get("abstained", False)

        if is_ans:
            total_answerable += 1
            if not abstained:
                correct_answers += 1
            else:
                false_abstains += 1
        else:
            total_unanswerable += 1
            if abstained:
                correct_abstains += 1
            else:
                false_answers += 1

    total = len(eval_results)
    accuracy = (correct_answers + correct_abstains) / total if total > 0 else 1.0
    fa_rate = false_answers / total_unanswerable if total_unanswerable > 0 else 0.0
    fab_rate = false_abstains / total_answerable if total_answerable > 0 else 0.0

    return {
        "abstention_accuracy": accuracy,
        "false_answer_rate": fa_rate,
        "false_abstention_rate": fab_rate,
        "total_evaluated": total,
        "total_answerable": total_answerable,
        "total_unanswerable": total_unanswerable,
        "correct_answers": correct_answers,
        "correct_abstentions": correct_abstains,
        "false_answers": false_answers,
        "false_abstentions": false_abstains,
    }
