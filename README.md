# AegisAI

> **Production-grade regulated-document RAG assistant** — answers questions over
> compliance and insurance documents with grounded citations, role-based access
> control, and jurisdiction isolation.

---

## What it does

AegisAI allows authorized users to ask questions about regulated documents and
receive answers that are:

- **Grounded** — every factual claim is backed by a retrieved evidence chunk
- **Cited** — sources include document, section, and page number
- **Restricted by role** — RBAC enforced inside the retrieval query
- **Restricted by jurisdiction** — EU users never see US-only content
- **Honest** — abstains when evidence is insufficient rather than hallucinating

```
User:    What is the claim settlement period under Policy 2026?

AegisAI: The policy specifies a 30-day settlement period after
         receipt of all required documentation.

         Sources:
         [1] Policy-2026.pdf — §8.2, page 12

         Confidence: High
```

---

## Architecture

```
React + TypeScript (Vite)
        │
     FastAPI
        │
  LangGraph agent
   ┌────┴─────┐
   │          │
 Auth/RBAC  Query Router
   │          │
   └────┬─────┘
        │
  Retrieval Pipeline
  ┌─────┴──────┐
  │            │
Dense        BM25
(pgvector)  (sparse)
  │            │
  └─────┬──────┘
        │
     RRF merge
        │
     Reranker
        │
     Top-K
        │
       LLM
  ┌────┼────┐
  │    │    │
Cite  PII  Guard
valid      rails
        │
   Final Response
```

---

## Build milestones

| Milestone | Scope | Status |
|---|---|---|
| **M1** | Foundation — React, FastAPI, PostgreSQL, pgvector, Docker, health checks | 🟢 Complete |
| **M2** | Document ingestion — upload, Docling, chunking, embed, index | 🟢 Complete |
| **M3** | Production RAG — BM25, RRF, reranking, citations, abstention | 🟢 Complete |
| **M4** | Security — auth, RBAC, jurisdiction isolation, PII, prompt injection | 🟢 Complete |
| **M5** | Product UI — polished chat, documents, citation viewer, provenance | 🟢 Complete |
| **M6** | Evaluation — 200-question golden set, RAG metrics, red team, CI gating | 🟢 Complete |
| **M7** | Observability — Langfuse, Phoenix, tracing, drift | ⬜ |
| **M8** | Azure — containers, database, storage, model, monitoring | ⬜ |

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, TanStack Query |
| Backend | Python 3.12, FastAPI, Pydantic, SQLAlchemy |
| Database | PostgreSQL 16 + pgvector |
| AI orchestration | LangGraph (M5+) |
| Ingestion | Docling (M2+) |
| Evaluation | RAGAS, DeepEval, 200-question golden set (M6+) |
| Observability | Langfuse, Arize Phoenix (M7+) |
| Deployment | Docker locally → Azure (M8) |

---

## Quick start (M1)

```bash
# 1. Clone
git clone https://github.com/munikumarnetlapalli/aegis-ai.git
cd aegis-ai

# 2. Configure
cp .env.example .env
# Edit .env if you want custom passwords (defaults work for local dev)

# 3. Start everything
docker compose up

# 4. Verify
curl http://localhost:8000/health
# → {"status":"healthy","database":"connected","version":"0.1.0"}

# 5. Open the UI
# → http://localhost:5173
```

All three services start automatically. The React app shows a live health badge
confirming the full chain: Browser → React → FastAPI → PostgreSQL → "healthy".

---

## Repository structure

```
aegis-ai/
├── apps/web/               # React + TypeScript frontend (Vite)
├── backend/
│   ├── app/
│   │   ├── api/            # Thin FastAPI routes
│   │   ├── core/           # Config, database, shared utilities
│   │   ├── services/       # Business logic (routes call into here)
│   │   ├── ingestion/      # M2: Docling pipeline
│   │   ├── retrieval/      # M3: dense, BM25, RRF
│   │   ├── reranking/      # M3: reranker interface
│   │   ├── generation/     # M4: LLM provider, prompts
│   │   ├── agent/          # M5: LangGraph graph
│   │   ├── security/       # M4+: RBAC, PII, guardrails
│   │   ├── evaluation/     # M6: golden set, RAGAS
│   │   └── observability/  # M7: Langfuse, Phoenix
│   └── tests/
├── data/
│   ├── raw/                # Source documents (gitignored)
│   ├── processed/          # Processed chunks (gitignored)
│   ├── golden-set/         # 200-question evaluation set
│   └── red-team/           # 50+ adversarial test cases
├── infrastructure/
│   ├── docker/             # Production Dockerfiles
│   └── azure/              # Azure deployment configs (M8)
├── docs/
│   ├── architecture/       # Architecture diagrams
│   ├── decisions/          # ADRs (ADR-001 onwards)
│   ├── api/                # API documentation
│   └── evaluation/         # Evaluation methodology
├── skills/                 # Agent reference files
├── .env.example            # Environment variable template
├── docker-compose.yml      # Local development stack
└── README.md
```

---

## Security model

Security is layered — not a single gate:

```
Input → authentication → authorization → retrieval controls
      → generation → output validation → PII → citation validation
      → response
```

Key principles:
- **Authorization inside the query** — unauthorized content never reaches the LLM
- **Jurisdiction isolation** — EU users cannot surface US-only content (tested)
- **Prompt-injection defense** — retrieved content is treated as data, not instructions
- **Citation validation** — every citation resolves to a real chunk server-side
- **PII detection** — Presidio-class detection before any response is returned

---

## Engineering principles

1. **Correctness over speed** — abstain rather than hallucinate
2. **Authorization at the source** — filter at query time, not after retrieval
3. **Provenance everywhere** — every chunk traceable to document, page, section
4. **Measurable, not claimed** — evaluation scores from real runs, not assertions
5. **Local-first** — full stack runs without any cloud dependency until M8

---

## Skills (agent reference files)

| File | When to load |
|---|---|
| `skills/aegisai-core.md` | Always — orientation, rules, tech stack |
| `skills/rag-engineering.md` | Ingestion, chunking, retrieval, citations |
| `skills/security.md` | RBAC, jurisdiction, PII, prompt injection |
| `skills/frontend.md` | React, chat UI, streaming, citation viewer |
| `skills/evaluation.md` | Golden set, RAGAS, red-team |
| `skills/observability.md` | Langfuse, Phoenix, tracing |
| `skills/deployment.md` | Docker, Azure, health checks |

---

## License

MIT
