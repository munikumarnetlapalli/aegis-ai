"""Statistical drift detection engine comparing live metrics to the M6 baseline."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from app.observability.schema import DriftReport, MetricDriftItem

logger = logging.getLogger(__name__)

_DEFAULT_BASELINE_PATH = Path(__file__).parent / "baselines" / "m6_baseline.json"

# Metric direction mapping
_METRIC_DIRECTIONS: dict[str, Literal["higher_is_better", "lower_is_better", "range_bound"]] = {
    "recall_at_5": "higher_is_better",
    "precision_at_5": "higher_is_better",
    "mrr": "higher_is_better",
    "ndcg_at_5": "higher_is_better",
    "faithfulness": "higher_is_better",
    "answer_relevance": "higher_is_better",
    "context_precision": "higher_is_better",
    "context_recall": "higher_is_better",
    "citation_correctness": "higher_is_better",
    "citation_completeness": "higher_is_better",
    "abstention_accuracy": "higher_is_better",
    "false_answer_rate": "lower_is_better",
    "red_team_defense_rate": "higher_is_better",
    "mean_top_reranker_score": "higher_is_better",
}


class DriftEngine:
    """Computes statistical drift between live telemetry/evaluations and the M6 baseline."""

    def __init__(
        self,
        baseline_path: Path | str | None = None,
        default_threshold_pct: float = 5.0,
        min_samples_required: int = 10,
    ) -> None:
        self.baseline_path = Path(baseline_path) if baseline_path else _DEFAULT_BASELINE_PATH
        self.default_threshold_pct = default_threshold_pct
        self.min_samples_required = min_samples_required
        self._baseline_data: dict = self._load_baseline()

    def _load_baseline(self) -> dict:
        """Load baseline metrics from JSON artifact."""
        if not self.baseline_path.exists():
            logger.warning("Baseline file %s not found. Using fallback defaults.", self.baseline_path)
            return {
                "baseline_version": "v1.0-m6-fallback",
                "metrics": {
                    "recall_at_5": 1.3646,
                    "mrr": 1.0000,
                    "faithfulness": 0.9185,
                    "answer_relevance": 0.8064,
                    "abstention_accuracy": 0.8500,
                    "false_answer_rate": 0.0833,
                    "red_team_defense_rate": 0.9833,
                    "mean_top_reranker_score": -0.230,
                },
            }
        try:
            with open(self.baseline_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.exception("Failed to parse baseline file %s: %s", self.baseline_path, exc)
            return {"baseline_version": "error", "metrics": {}}

    def evaluate_drift(
        self,
        current_metrics: dict[str, float],
        sample_count: int,
        threshold_pct: float | None = None,
    ) -> DriftReport:
        """Compare current live metric averages against baseline metrics.

        Directionality is explicitly handled:
        - For 'higher_is_better', negative delta_pct beyond threshold constitutes degradation.
        - For 'lower_is_better', positive delta_pct beyond threshold constitutes degradation.
        - For negative baseline metrics (e.g. mean reranker logit -0.230), delta is evaluated signed.
        """
        thresh = threshold_pct if threshold_pct is not None else self.default_threshold_pct
        baseline_metrics = self._baseline_data.get("metrics", {})
        baseline_ver = self._baseline_data.get("baseline_version", "v1.0-m6")

        items: list[MetricDriftItem] = []
        drift_detected_any = False

        is_insufficient = sample_count < self.min_samples_required

        for metric_name, base_val in baseline_metrics.items():
            if metric_name not in current_metrics:
                continue

            curr_val = float(current_metrics[metric_name])
            direction = _METRIC_DIRECTIONS.get(metric_name, "higher_is_better")
            delta = curr_val - base_val

            if abs(base_val) > 1e-9:
                delta_pct = (delta / abs(base_val)) * 100.0
            else:
                delta_pct = 0.0

            if is_insufficient:
                status = "INSUFFICIENT_DATA"
                has_drift = False
            else:
                # Evaluate drift based on metric directionality
                if direction == "higher_is_better":
                    has_drift = delta_pct < -thresh
                elif direction == "lower_is_better":
                    has_drift = delta_pct > thresh
                else:
                    has_drift = abs(delta_pct) > thresh

                status = "DRIFT_ALERT" if has_drift else "STABLE"

            if has_drift:
                drift_detected_any = True

            items.append(
                MetricDriftItem(
                    metric_name=metric_name,
                    baseline_value=round(base_val, 4),
                    current_value=round(curr_val, 4),
                    delta=round(delta, 4),
                    delta_pct=round(delta_pct, 2),
                    threshold_pct=thresh,
                    drift_detected=has_drift,
                    status=status,
                    direction=direction,
                )
            )

        if is_insufficient:
            overall_status = "INSUFFICIENT_DATA"
        elif drift_detected_any:
            overall_status = "DRIFT_DETECTED"
        else:
            overall_status = "HEALTHY"

        return DriftReport(
            baseline_version=baseline_ver,
            sample_count=sample_count,
            min_samples_required=self.min_samples_required,
            metrics=items,
            overall_drift_status=overall_status,
        )
