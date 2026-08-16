# Milestone 7 (M7) Implementation Notes & Repository Discovery

## 1. Existing Architecture Discovered
- **FastAPI Backend (`backend/app/`)**:
  - `main.py`: Factory `create_app()` registering routers (`health`, `auth`, `documents`, `query`, `answer`).
  - `api/answer.py`: Central RAG endpoint with 8 sequential steps (Rate limiting, Prompt injection scan, Server-side RBAC derivation, Hybrid retrieval, Generation + citation validation, PII policy, Citation mapping with PII redaction, Structured audit log).
  - `retrieval/service.py`: `HybridRetrievalService.retrieve()` calling `DenseRetriever` (pgvector cosine), `BM25Retriever` (SQL keyword), `reciprocal_rank_fusion()`, and `CrossEncoderReranker.rerank()`.
  - `generation/service.py`: `GenerationService.answer()` managing hard abstention threshold check, prompt construction, LLM generation, citation extraction and validation, zero-citation ungrounded safeguard, and PII policy enforcement.
  - `generation/llm.py`: `OllamaProvider` calling `http://ollama:11434/api/chat`.
  - `security/dependencies.py`: `get_current_user()` and `require_roles(allowed_roles)` for RBAC.

- **Database State**:
  - PostgreSQL 16 + pgvector.
  - Alembic migrations:
    - `0001_create_documents_chunks.py` (documents and chunks with pgvector)
    - `0002_create_users.py` (users with roles and hashed passwords)
  - Next migration: `0003_create_pipeline_traces.py` for `pipeline_traces` table.

- **Frontend Architecture (`apps/web/`)**:
  - React 18 + TypeScript + Vite.
  - Navigation tabs in `App.tsx`: `chat`, `documents`, `query`.
  - Adding `observability` tab with `ObservabilityPanel.tsx`.
  - Adding micro-badge in `ChatPanel.tsx` for latency/token display.

## 2. Exact Insertion Points for Spans
1. `security.guardrail`: [backend/app/api/answer.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/api/answer.py#L70-L95) around `scan_prompt_injection()`.
2. `retrieval.dense`: [backend/app/retrieval/service.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/retrieval/service.py#L250) around `self._dense.retrieve()`.
3. `retrieval.bm25`: [backend/app/retrieval/service.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/retrieval/service.py#L261) around `bm25_retriever.retrieve()`.
4. `retrieval.rrf`: [backend/app/retrieval/service.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/retrieval/service.py#L271) around `reciprocal_rank_fusion()`.
5. `reranking.cross_encoder`: [backend/app/retrieval/service.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/retrieval/service.py#L285) around `reranker.rerank()`.
6. `generation.abstention_check`: [backend/app/generation/service.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/generation/service.py#L138) around `should_abstain()`.
7. `generation.llm`: [backend/app/generation/service.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/generation/service.py#L163) around `llm.generate()`.
8. `generation.citations`: [backend/app/generation/service.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/generation/service.py#L183) around `validate_citations()`.
9. `security.pii`: [backend/app/api/answer.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/api/answer.py#L147) around `apply_pii_policy()`.
10. `rag.answer`: [backend/app/api/answer.py](file:///c:/Users/sudhe/OneDrive/Desktop/aegis-ai/backend/app/api/answer.py#L45) around full `answer_query()`.

## 3. Telemetry Privacy Guarantees
- Raw queries are hashed using `compute_query_hash()` (SHA-256 hex string).
- No raw chunks or system prompts are stored in `PipelineSpan.metadata`.
- All serialized traces must pass negative assertions for query/chunk/secret/PII leakage.

## 4. RBAC Mapping
- `admin` and `auditor`: Allowed access to `/observability/*` API endpoints.
- `analyst` and `viewer`: Denied access (`403 Forbidden`).
