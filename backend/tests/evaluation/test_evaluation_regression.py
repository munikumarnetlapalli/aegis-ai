"""Automated test suite for M6 Evaluation Metrics, Red-Team Defenses, and CI Regression Gates."""
import pytest
from app.evaluation.metrics.abstention import (
    compute_abstention_metrics,
    evaluate_abstention_decision,
)
from app.evaluation.metrics.rag import (
    compute_answer_relevance,
    compute_citation_completeness,
    compute_citation_correctness,
    compute_context_precision,
    compute_context_recall,
    compute_faithfulness,
)
from app.evaluation.metrics.red_team import (
    compute_red_team_metrics,
    evaluate_red_team_case,
)
from app.evaluation.metrics.retrieval import (
    evaluate_retrieval_batch,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)
from app.evaluation.runner import DEFAULT_THRESHOLDS, EvaluationRunner


class TestRetrievalMetrics:
    """Verify standard Information Retrieval metrics calculations."""

    def test_recall_at_k(self):
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc2", "doc5", "doc8"}
        # Top 5 contains doc2 and doc5 (2 out of 3 relevant)
        assert recall_at_k(retrieved, relevant, k=5) == pytest.approx(2 / 3)
        assert recall_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 3)

    def test_precision_at_k(self):
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc2", "doc5"}
        # Top 5 has 2 relevant items
        assert precision_at_k(retrieved, relevant, k=5) == pytest.approx(2 / 5)
        # Top 2 has 1 relevant item
        assert precision_at_k(retrieved, relevant, k=2) == pytest.approx(1 / 2)

    def test_reciprocal_rank(self):
        retrieved = ["docA", "docB", "docC"]
        assert reciprocal_rank(retrieved, {"docA"}) == 1.0
        assert reciprocal_rank(retrieved, {"docB"}) == 0.5
        assert reciprocal_rank(retrieved, {"docC"}) == pytest.approx(1 / 3)
        assert reciprocal_rank(retrieved, {"docZ"}) == 0.0

    def test_ndcg_at_k(self):
        # Perfect ranking: relevant items first
        perfect = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc2"}
        assert ndcg_at_k(perfect, relevant, k=3) == pytest.approx(1.0)

        # Inverted ranking
        inverted = ["doc3", "doc2", "doc1"]
        score = ndcg_at_k(inverted, relevant, k=3)
        assert 0.0 < score < 1.0

    def test_evaluate_retrieval_batch(self):
        retrieved_batch = [["d1", "d2"], ["d3", "d4"]]
        relevant_batch = [{"d1"}, {"d4"}]
        metrics = evaluate_retrieval_batch(retrieved_batch, relevant_batch, k=2)
        assert "recall_at_2" in metrics
        assert "mrr" in metrics
        assert metrics["recall_at_2"] == 1.0


class TestRAGQualityMetrics:
    """Verify RAG generation quality metrics."""

    def test_faithfulness_supported(self):
        context = ["Bodily injury liability covers injuries caused to others in accidents."]
        answer = "Bodily injury liability covers injuries to other people."
        score = compute_faithfulness(answer, context)
        assert score > 0.6

    def test_faithfulness_abstention(self):
        # Abstaining is 100% faithful (no ungrounded claims)
        assert compute_faithfulness("ABSTAIN", ["some context"]) == 1.0

    def test_answer_relevance(self):
        question = "What does collision insurance cover?"
        answer = "Collision insurance covers damage to your vehicle when you hit another car."
        expected = "Collision covers vehicle damage from accidents."
        score = compute_answer_relevance(question, answer, expected)
        assert score > 0.6

    def test_context_precision_and_recall(self):
        context = ["The deductible is $500.", "The grace period is 30 days.", "Unrelated noise."]
        keywords = ["deductible", "grace period"]
        prec = compute_context_precision(context, keywords)
        rec = compute_context_recall(context, keywords)
        assert prec > 0.7
        assert rec == 1.0

    def test_citation_correctness_and_completeness(self):
        citations = [{"filename": "policy.pdf", "page": 1}]
        context = [{"filename": "policy.pdf"}]
        assert compute_citation_correctness(citations, context) == 1.0

        answer_with_cites = "Collision is covered [1] under the standard policy terms [2]."
        assert compute_citation_completeness(answer_with_cites, [{}, {}]) == 1.0


class TestAbstentionMetrics:
    """Verify abstention classification and accuracy."""

    def test_abstention_classification(self):
        assert evaluate_abstention_decision(is_answerable=True, did_abstain=False) == "CORRECT_ANSWER"
        assert evaluate_abstention_decision(is_answerable=False, did_abstain=True) == "CORRECT_ABSTAIN"
        assert evaluate_abstention_decision(is_answerable=False, did_abstain=False) == "FALSE_ANSWER"
        assert evaluate_abstention_decision(is_answerable=True, did_abstain=True) == "FALSE_ABSTAIN"

    def test_compute_abstention_metrics(self):
        results = [
            {"is_answerable": True, "abstained": False},
            {"is_answerable": True, "abstained": False},
            {"is_answerable": False, "abstained": True},
            {"is_answerable": False, "abstained": False},  # 1 false answer
        ]
        metrics = compute_abstention_metrics(results)
        assert metrics["abstention_accuracy"] == 0.75
        assert metrics["false_answer_rate"] == 0.5
        assert metrics["false_abstention_rate"] == 0.0


class TestRedTeamMetrics:
    """Verify red-team adversarial evaluation."""

    def test_prompt_injection_blocked(self):
        case = {
            "id": "rt-001",
            "category": "prompt_injection",
            "expected_behavior": "BLOCK",
            "severity": "critical",
        }
        res = evaluate_red_team_case(
            case=case,
            actual_response="I cannot process this request because it violates system security policies.",
            was_blocked=True,
            did_abstain=False,
        )
        assert res["passed"] is True

    def test_pii_leakage_detected(self):
        case = {
            "id": "rt-011",
            "category": "pii_extraction",
            "expected_behavior": "SAFE_RESPONSE",
            "severity": "critical",
        }
        res = evaluate_red_team_case(
            case=case,
            actual_response="User SSN is 123-45-6789.",
            was_blocked=False,
            did_abstain=False,
            extracted_pii=["123-45-6789"],
        )
        assert res["passed"] is False

    def test_aggregate_red_team_metrics(self):
        cases = [
            {"passed": True, "category": "prompt_injection", "severity": "critical"},
            {"passed": True, "category": "prompt_injection", "severity": "critical"},
            {"passed": False, "category": "pii_extraction", "severity": "high"},
        ]
        metrics = compute_red_team_metrics(cases)
        assert metrics["overall_pass_rate"] == pytest.approx(2 / 3)
        assert metrics["by_category"]["prompt_injection"]["pass_rate"] == 1.0


class TestRegressionGates:
    """Verify regression checking logic properly enforces threshold gates."""

    def test_passing_gates(self):
        runner = EvaluationRunner(thresholds=DEFAULT_THRESHOLDS)
        golden_results = {
            "retrieval_metrics": {"recall_at_5": 0.85, "precision_at_5": 0.65, "mrr": 0.80, "ndcg_at_5": 0.80},
            "rag_metrics": {"faithfulness": 0.88, "answer_relevance": 0.82},
            "abstention_metrics": {"abstention_accuracy": 0.90, "false_answer_rate": 0.05},
        }
        red_team_results = {
            "metrics": {"overall_pass_rate": 0.95}
        }
        passed, failures = runner.check_regression_gates(golden_results, red_team_results)
        assert passed is True
        assert len(failures) == 0

    def test_failing_gates_on_degradation(self):
        runner = EvaluationRunner(thresholds=DEFAULT_THRESHOLDS)
        golden_results = {
            "retrieval_metrics": {"recall_at_5": 0.50, "mrr": 0.40},  # Below 0.70 / 0.65
            "rag_metrics": {"faithfulness": 0.60, "answer_relevance": 0.50},  # Below
            "abstention_metrics": {"abstention_accuracy": 0.60, "false_answer_rate": 0.30},  # Above 0.15
        }
        red_team_results = {
            "metrics": {"overall_pass_rate": 0.60}  # Below 0.85
        }
        passed, failures = runner.check_regression_gates(golden_results, red_team_results)
        assert passed is False
        assert len(failures) > 0
