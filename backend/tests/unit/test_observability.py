"""Unit tests for M7 Observability: hashing, privacy, spans, tracer, cost, and drift."""
from __future__ import annotations

import json
import time
import pytest

from app.observability.cost import calculate_token_cost, estimate_tokens_from_text
from app.observability.drift import DriftEngine
from app.observability.privacy import compute_query_hash, sanitize_trace_metadata
from app.observability.schema import PipelineSpan, RequestTrace
from app.observability.tracer import AegisTracer


class TestPrivacyAndHashing:
    """Test SHA-256 deterministic query hashing and privacy metadata sanitization."""

    def test_query_hash_deterministic_and_sha256(self):
        q1 = "What is the policy deductible for Collision?"
        q2 = "  what is the   policy deductible for collision?  "
        h1 = compute_query_hash(q1)
        h2 = compute_query_hash(q2)

        assert len(h1) == 64
        assert h1 == h2
        assert h1 == h1.lower()
        # Verify hex format
        int(h1, 16)

    def test_empty_query_hash(self):
        h = compute_query_hash("")
        assert len(h) == 64

    def test_sanitize_trace_metadata_removes_forbidden_keys(self):
        raw_meta = {
            "top_k": 5,
            "query": "secret query text",
            "raw_query": "secret query text 2",
            "prompt": "system prompt instructions",
            "content": "confidential document text",
            "password": "supersecretpassword",
            "token": "secret_token_123",
            "nested": {
                "safe_score": 0.85,
                "system_prompt": "do not leak",
                "jwt": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDcSemACt8x4iTMCda8Yhe3iZaWbvV5XKSTbuAn0M",
            },
        }

        sanitized = sanitize_trace_metadata(raw_meta)
        serialized = json.dumps(sanitized)

        assert "top_k" in sanitized
        assert sanitized["top_k"] == 5
        assert "safe_score" in sanitized["nested"]
        assert sanitized["nested"]["safe_score"] == 0.85

        # Negative assertions — forbidden values must NOT exist
        assert "secret query text" not in serialized
        assert "system prompt instructions" not in serialized
        assert "confidential document text" not in serialized
        assert "supersecretpassword" not in serialized
        assert "do not leak" not in serialized
        assert "eyJhbGciOi" not in serialized


class TestCostAndTokenAccounting:
    """Test rate card pricing and token calculations."""

    def test_estimate_tokens_from_text(self):
        text = "Hello, world! This is a test sentence with about 60 characters."
        est = estimate_tokens_from_text(text)
        assert est > 0
        assert est == pytest.approx(len(text) / 4.0, abs=2)

    def test_rate_cards_known_models(self):
        # Ollama local is $0
        c_ollama = calculate_token_cost(
            provider="ollama", model="llama3.2", input_tokens=1000, output_tokens=500
        )
        assert c_ollama.total_tokens == 1500
        assert c_ollama.estimated_cost_usd == 0.0

        # Azure gpt-4o-mini ($0.15 / 1M in, $0.60 / 1M out)
        c_mini = calculate_token_cost(
            provider="azure_openai", model="gpt-4o-mini", input_tokens=100_000, output_tokens=10_000
        )
        # in: 100k/1M * 0.15 = $0.015, out: 10k/1M * 0.60 = $0.006 => total $0.021
        assert c_mini.estimated_cost_usd == pytest.approx(0.021, abs=1e-5)

    def test_unknown_model_safe_fallback(self):
        c_unknown = calculate_token_cost(
            provider="custom_provider", model="unlisted_future_model_v9", input_tokens=500, output_tokens=250
        )
        assert c_unknown.total_tokens == 750
        assert c_unknown.estimated_cost_usd == 0.0


class TestAegisTracer:
    """Test tracer lifecycle, monotonic span timing, and error safety."""

    def test_tracer_start_and_span_timing(self):
        tracer = AegisTracer(enabled=True)
        trace = tracer.start_trace(
            query="Test query for timing",
            user_role="admin",
            jurisdiction="GLOBAL",
        )
        assert trace.request_id is not None
        assert len(trace.query_hash) == 64

        with tracer.span("test.operation", metadata={"key": "val"}) as span:
            time.sleep(0.01)  # 10ms
            if span:
                span.metadata["extra"] = 123

        finished = tracer.finish_trace(
            retrieved_chunk_ids=["chunk-1"],
            top_reranker_score=0.95,
            citation_count=1,
            citation_status="PASS",
        )

        assert finished is not None
        assert finished.total_latency_ms >= 8.0  # At least sleep duration
        assert len(finished.spans) == 1
        assert finished.spans[0].name == "test.operation"
        assert finished.spans[0].latency_ms >= 8.0
        assert finished.spans[0].metadata.get("extra") == 123
        assert finished.citation_status == "PASS"

    def test_tracer_exception_in_span_marked_error(self):
        tracer = AegisTracer(enabled=True)
        tracer.start_trace(query="Exception test")

        with pytest.raises(ValueError, match="Span failure test"):
            with tracer.span("failing.span"):
                raise ValueError("Span failure test")

        trace = tracer.get_current_trace()
        assert trace is not None
        assert len(trace.spans) == 1
        assert trace.spans[0].status == "ERROR"
        assert trace.spans[0].metadata.get("error_type") == "ValueError"


class TestDriftEngine:
    """Test statistical drift calculations against the M6 baseline."""

    def test_drift_insufficient_samples(self):
        engine = DriftEngine(min_samples_required=10)
        report = engine.evaluate_drift(
            current_metrics={"recall_at_5": 0.50, "faithfulness": 0.50},
            sample_count=5,
        )
        assert report.overall_drift_status == "INSUFFICIENT_DATA"
        assert all(m.status == "INSUFFICIENT_DATA" for m in report.metrics)

    def test_drift_stable_metrics(self):
        engine = DriftEngine(min_samples_required=10, default_threshold_pct=5.0)
        # Near baseline metrics
        current = {
            "recall_at_5": 1.3646,
            "mrr": 1.0000,
            "faithfulness": 0.9185,
            "answer_relevance": 0.8064,
            "abstention_accuracy": 0.8500,
            "false_answer_rate": 0.0833,
            "mean_top_reranker_score": -0.230,
        }
        report = engine.evaluate_drift(current_metrics=current, sample_count=50)
        assert report.overall_drift_status == "HEALTHY"
        assert all(not m.drift_detected for m in report.metrics)

    def test_drift_detected_on_degradation(self):
        engine = DriftEngine(min_samples_required=10, default_threshold_pct=5.0)
        # Faithfulness degraded from 0.9185 to 0.7000 (> 20% drop)
        current = {
            "recall_at_5": 1.3646,
            "mrr": 1.0000,
            "faithfulness": 0.7000,
            "answer_relevance": 0.8064,
            "abstention_accuracy": 0.8500,
        }
        report = engine.evaluate_drift(current_metrics=current, sample_count=50)
        assert report.overall_drift_status == "DRIFT_DETECTED"
        faith_item = next(m for m in report.metrics if m.metric_name == "faithfulness")
        assert faith_item.drift_detected is True
        assert faith_item.status == "DRIFT_ALERT"
