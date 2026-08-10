# Observability Skill

Load this file when working on: Langfuse integration, Phoenix integration,
tracing, latency/cost tracking, drift detection, or `backend/app/observability/`.

## What to trace (per request)

```python
{
  "request_id":          str,   # UUID, correlates all spans
  "session_id":          str,   # anonymized user session
  "query_hash":          str,   # SHA-256 of query (not raw text — PII risk)
  "retrieval_latency_ms": int,
  "embedding_latency_ms": int,
  "bm25_latency_ms":     int,
  "reranker_latency_ms": int,
  "llm_latency_ms":      int,
  "total_latency_ms":    int,
  "chunk_ids_retrieved": list[str],
  "reranker_scores":     list[float],
  "model_name":          str,
  "input_tokens":        int,
  "output_tokens":       int,
  "total_tokens":        int,
  "estimated_cost_usd":  float,
  "citation_validation": "pass" | "fail",
  "guardrail_result":    "pass" | "blocked",
  "abstained":           bool,
  "prompt_version":      str,
}
```

## What NOT to log

- Raw user queries (PII risk — log only the hash)
- Retrieved chunk content (may contain sensitive document data)
- System prompt (security risk)
- API keys or tokens (ever)
- Raw PII from LLM outputs

## Langfuse (LLM observability)

Track: traces, generations, token counts, latency, model, retrieval steps,
prompt versions, evaluation scores, cost estimates.

```python
# Langfuse must be optional — app runs without it
try:
    from langfuse import Langfuse
    langfuse = Langfuse()
except Exception:
    langfuse = None  # observability failure must not break the request
```

The application must remain **fully functional** if Langfuse is unreachable.
Observability is not a hard runtime dependency.

## Phoenix (retrieval & drift)

Monitor: retrieval quality distributions, similarity score distributions,
latency trends, evaluation score trends, embedding drift.

Goal: detect degradation after source documents, models, prompts, or retrieval
parameters change — before users notice it.

## Drift detection

Alert when any metric degrades by more than a configurable threshold (default: 5%):
- Mean reranker score
- Context precision (from RAGAS)
- Citation correctness
- Faithfulness
- Answer relevance
- Document score distributions

Threshold must be **configurable**, not hard-coded into business logic.

## Cost tracking

Track per-request and aggregate:
```
input_tokens × input_rate
output_tokens × output_rate
embedding_calls × embedding_rate
reranker_calls × reranker_rate
```

Provide: cost/query, cost/day, cost/model, cache hit rate, cache miss rate.

During local development (Ollama/local models), cost may be zero — still collect
token counts and latency for baseline comparison with cloud models.

## Prompt caching

If the production LLM supports prompt caching, structure prompts with stable prefixes:

```
[SYSTEM POLICY — stable]
[STATIC SAFETY RULES — stable]
[STATIC DOMAIN INSTRUCTIONS — stable]
─────────────────────────────────
[USER QUESTION — dynamic]
[RETRIEVED EVIDENCE — dynamic]
```

Measure actual cache hit rate from real traffic before claiming any benefit.
