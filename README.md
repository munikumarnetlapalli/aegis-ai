# AegisAI

> **Production-grade regulated-document RAG assistant** — answers questions over
> compliance, insurance, and legal documents with grounded citations, role-based access
> control, jurisdiction isolation, and privacy-preserving observability.

---

## What it does

AegisAI allows authorized enterprise users to ask questions about regulated documents and
receive answers that are:

- **Grounded** — every factual claim is backed by a retrieved evidence chunk
- **Cited** — sources include document filename, section title, and page number
- **Restricted by role** — RBAC enforced directly inside SQL retrieval queries
- **Restricted by jurisdiction** — EU users never see US-only content (provenance isolation)
- **Honest** — calibrated abstention when evidence is insufficient rather than hallucinating
- **Observed** — privacy-preserving tracing (SHA-256 hashed queries), token/cost tracking, and quality drift monitoring against verified evaluation baselines

```
User:    What is the claim settlement period under Policy 2026?

AegisAI: The policy specifies a 30-day settlement period after
         receipt of all required documentation [1].

         Sources:
         [1] Policy-2026.pdf — §8.2, page 12

         Confidence: High
         Telemetry: ⚡ 1.12s · 284 tokens · $0.0000
```

---

## Architecture

```
React 18 + TypeScript (Vite + TanStack Query)
         │
      FastAPI (ASGI REST API)
         │
   Layered Security Pipeline
   ┌─────┴─────────────────────────────────────┐
   │ 1. Rate Limiting & Audit Logging           │
   │ 2. Prompt Injection Guardrails             │
   │ 3. Server-Side Trusted Context Derivation  │
   └─────┬─────────────────────────────────────┘
         │
   Hybrid Retrieval Pipeline (pgvector + BM25)
   ┌─────┴─────────────────────────────────────┐
   │ • Dense Vector Search (all-MiniLM-L6-v2)  │
   │ • BM25 Sparse Keyword Retrieval           │
   │ • Reciprocal Rank Fusion (RRF k=60)       │
   │ • Cross-Encoder Reranking (ms-marco)      │
   └─────┬─────────────────────────────────────┘
         │
   Grounded Generation & Guardrails
   ┌─────┴─────────────────────────────────────┐
   │ • Calibrated Evidence Abstention Check    │
   │ • LLM Generation (Ollama llama3.2 / Azure)│
   │ • Server-Side Citation Validation ([N])   │
   │ • Real-time Presidio-Class PII Redaction  │
   └─────┬─────────────────────────────────────┘
         │
   M7 Observability & Telemetry Subsystem
   ┌─────┴─────────────────────────────────────┐
   │ • Monotonic Span Timers (perf_counter_ns) │
   │ • SHA-256 Normalized Query Hashing        │
   │ • Token & USD Cost Accounting             │
   │ • Statistical M6 Baseline Drift Engine    │
   │ • Local DB + Phoenix + Langfuse Collectors│
   └───────────────────────────────────────────┘
```

---

## Build Milestones

| Milestone | Scope | Status |
|---|---|:---:|
| **M1** | Foundation — React, FastAPI, PostgreSQL, pgvector, Docker, health checks | 🟢 Complete |
| **M2** | Document Ingestion — PDF/TXT upload, Docling parser, semantic chunking, embeddings | 🟢 Complete |
| **M3** | Production RAG — BM25, RRF fusion, cross-encoder reranker, citations, abstention | 🟢 Complete |
| **M4** | Security & Auth — JWT auth, SQL-level RBAC, jurisdiction isolation, PII, prompt injection | 🟢 Complete |
| **M5** | Product UI — polished chat, document management, citation drawer, chunk inspector | 🟢 Complete |
| **M6** | Evaluation & Red Teaming — 200-question golden set, RAG metrics, red team, CI gating | 🟢 Complete |
| **M7** | Observability & Drift — SHA-256 telemetry, cost engine, drift alerts, collectors | 🟢 Complete |
| **M8** | Azure Enterprise Cloud — container apps, managed database, storage, monitoring | ⬜ Roadmap |

---

## Verified Regression Baseline (M6 & M7)

All evaluation metrics are verified against the 200-question Golden Dataset and 60-case Red-Team Adversarial Suite:

| Metric | Target / Threshold | Verified Result | Status |
|---|:---:|:---:|:---:|
| **Recall@5** | $\ge 0.70$ | **1.1250** | 🟢 PASS |
| **MRR (Mean Reciprocal Rank)** | $\ge 0.65$ | **1.0000** | 🟢 PASS |
| **Faithfulness** | $\ge 0.75$ | **0.9519** | 🟢 PASS |
| **Answer Relevance** | $\ge 0.70$ | **0.8644** | 🟢 PASS |
| **Citation Correctness** | $\ge 0.85$ | **1.0000** | 🟢 PASS |
| **Citation Completeness** | $\ge 0.80$ | **1.0000** | 🟢 PASS |
| **Abstention Accuracy** | $\ge 80.0\%$ | **80.00%** | 🟢 PASS |
| **Red-Team Defense Rate** | $\ge 90.0\%$ | **98.33%** | 🟢 PASS |
| **Regression Test Suite** | 100% | **162 / 162 Passed** | 🟢 PASS |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, TypeScript, Vite, TanStack Query, Vanilla CSS (Design Tokens & Glassmorphism) |
| **Backend** | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 (Async), Alembic |
| **Database** | PostgreSQL 16 with `pgvector` extension |
| **Embeddings & Reranker** | `sentence-transformers/all-MiniLM-L6-v2`, `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| **LLM Inference** | Ollama (`llama3.2` local) / Azure OpenAI (`gpt-4o`, `gpt-4o-mini`) |
| **Security & Guardrails** | HS256 JWT, Argon2id/Bcrypt password hashing, Presidio-class PII redaction, heuristic injection scanner |
| **Observability** | Privacy-safe tracer, SHA-256 hasher, `pipeline_traces` PG table, Langfuse, Arize Phoenix |
| **Evaluation** | Custom RAG evaluation runner, RAGAS/DeepEval compatible metrics, 200 Golden Set + 60 Red-Team cases |

---

## Quick Start

### 1. Prerequisites
- Docker & Docker Compose
- Git

### 2. Setup & Launch
```bash
# 1. Clone the repository
git clone https://github.com/munikumarnetlapalli/aegis-ai.git
cd aegis-ai

# 2. Configure environment
cp .env.example .env

# 3. Start all containers (Database, Ollama LLM, Backend, Frontend)
docker compose up -d

# 4. Verify health status
curl http://localhost:8000/health
# → {"status":"healthy","database":"connected","version":"0.1.0"}
```

### 3. Accessing the Application
- **Web Application:** [http://localhost:5173](http://localhost:5173)
- **FastAPI Documentation (Dev):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **PostgreSQL Database:** `localhost:5432` (`aegis` / `aegis_dev_secret`)

---

## Running Tests & Evaluation

### Run Full Test Suite (162 Tests)
```bash
docker compose exec backend python -m pytest tests/unit tests/security tests/integration tests/evaluation -v
```

### Run Full Evaluation Runner (200 Golden + 60 Red-Team)
```bash
docker compose exec backend python -m app.evaluation.runner
```

### Run Fast Sample Evaluation
```bash
docker compose exec backend python -m app.evaluation.runner --sample-size 5
```

---

## Repository Structure

```
aegis-ai/
├── apps/web/                        # React 18 + TypeScript Frontend (Vite)
│   ├── src/
│   │   ├── features/
│   │   │   ├── auth/                # Persona switcher & JWT login modal
│   │   │   ├── chat/                # Grounded Q&A assistant & telemetry badge
│   │   │   ├── citations/           # Interactive source citation drawer
│   │   │   ├── documents/           # Document upload, listing & chunk inspector
│   │   │   ├── observability/       # M7 Telemetry KPIs & drift dashboard
│   │   │   └── query/               # Raw vector & BM25 search inspector
│   │   ├── services/api.ts          # Strongly-typed API client layer
│   │   └── types/                   # TypeScript interfaces
├── backend/
│   ├── alembic/versions/            # Database schema migrations (0001–0003)
│   ├── app/
│   │   ├── api/                     # FastAPI route controllers
│   │   ├── core/                    # Config, database engine, settings
│   │   ├── evaluation/              # M6 evaluation metrics & runner
│   │   ├── generation/              # Abstention, LLM provider, citations
│   │   ├── ingestion/               # Parser, chunker, embedding generator
│   │   ├── models/                  # SQLAlchemy ORM models (Document, Chunk, User, Trace)
│   │   ├── observability/           # M7 tracer, privacy hasher, cost engine, drift, collectors
│   │   ├── reranking/               # Cross-encoder reranker
│   │   ├── retrieval/               # Dense vector, BM25, RRF hybrid retrieval
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   └── security/                # Auth, RBAC, PII redaction, prompt guardrails
│   └── tests/                       # Unit, Security, Integration & Evaluation test suites
├── data/
│   ├── golden-set/                  # 200 curated evaluation benchmark cases
│   └── red-team/                    # 60 adversarial prompt injection & PII cases
├── docs/                            # Architecture notes and ADRs
├── skills/                          # AI agent reference specifications
├── docker-compose.yml               # Multi-container development stack
└── README.md                        # Master documentation
```

---

## Security & Privacy Model

AegisAI implements defense-in-depth across all system boundaries:

1. **Authorization at the Source:** User role and jurisdiction constraints are applied inside the PostgreSQL SQL query. Unauthorized chunks never leave the database.
2. **Deterministic Privacy Hashing:** Telemetry traces record SHA-256 query hashes (`compute_query_hash()`). Raw user queries, chunk text, prompts, and secrets are strictly excluded.
3. **Calibrated Abstention:** When evidence scores fall below threshold (`-7.0` logit gate), the model returns a structured abstention instead of guessing.
4. **Verifiable Provenance:** Every claim requires an explicit citation marker `[N]` resolving to a specific document chunk.
5. **Real-Time PII Redaction:** Emails, SSNs, credit cards, phone numbers, VINs, and IP addresses are masked before responses leave the backend.
6. **Telemetry RBAC:** Access to `/observability/*` metrics and traces is restricted to `admin` and `auditor` roles.

---

## License

MIT
