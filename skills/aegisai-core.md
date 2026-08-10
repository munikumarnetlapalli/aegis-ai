---
name: aegis-ai-engineering
description: >
  Build and evolve AegisAI, a production-grade compliance/regulated-document RAG assistant
  (React + FastAPI + LangGraph + pgvector + Docling + Azure). Use this skill whenever the
  user is working in the aegis-ai repository, or asks to add/modify anything related to
  document ingestion, hybrid retrieval (dense/BM25/RRF), reranking, RBAC/jurisdiction
  filtering, citation-grounded generation, prompt-injection defense, PII redaction,
  RAGAS/red-team evaluation, Langfuse/Phoenix observability, or Azure deployment for
  this project.
---

# AegisAI Core Skill

AegisAI is a **regulated-document intelligence platform**, not a chatbot demo.
Every feature must move the system closer to answering, provably, three questions
for every response it gives a user:

```
CAN the user access this information?
IS there sufficient evidence?
CAN we prove where the answer came from?
```

If any answer is no, the system must **abstain** rather than produce a confident,
unsupported answer.

## The 3-Question Test

Apply this to every PR / feature / change before marking it done:

| Question | Where enforced |
|---|---|
| Can the user access this? | Server-side RBAC + jurisdiction filter **inside** the retrieval query |
| Is there sufficient evidence? | Evidence threshold check before LLM generation |
| Can we prove where it came from? | Citation → chunk → document → page/section validation |

## Non-negotiable engineering rules

- **Authorization inside the query.** Never retrieve broadly and filter afterward.
  Unauthorized content must never reach the LLM.
- **Every chunk has provenance.** `document_id`, version, page, section,
  jurisdiction, `allowed_roles` — missing any of these means the chunk cannot
  be cited and must not be indexed.
- **Retrieved content is untrusted data.** User input, documents, chunks, and
  conversation history are all adversarial. Only the system prompt is an
  instruction source.
- **Abstain rather than guess.** When evidence is insufficient, return an explicit
  "insufficient evidence" response.
- **No hard-coded secrets, ever.** `.env` / `.env.example` only. If a secret
  leaks into git history, stop everything and expunge it before continuing.
- **Never invent test results, delete failing tests, or disable security checks.**

## Technology stack

| Layer | Choice |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind, React Router, TanStack Query |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, PostgreSQL + pgvector |
| AI orchestration | LangGraph, pluggable embedding / reranker / LLM interfaces |
| Ingestion | Docling (structured parsing) |
| Security | RBAC, jurisdiction filtering, PII detection (Presidio), prompt-injection defense |
| Evaluation | RAGAS, DeepEval, 200-question golden set, 50+ red-team cases |
| Observability | Langfuse (LLM traces/cost), Phoenix (retrieval/embedding/drift) |
| Deployment | Docker locally → Azure in production |

## Build order (37 steps, M1–M10)

```
M1  Foundation       — React, FastAPI, PostgreSQL, pgvector, Docker, health checks
M2  First RAG        — upload, parse, chunk, embed, index, retrieve, answer
M3  Production RAG   — BM25, RRF, reranking, metadata filters, citations, abstention
M4  Security         — authentication, RBAC, jurisdiction isolation, PII, prompt-injection
M5  Product UI       — polished React UI: chat, documents, citation viewer, history
M6  Evaluation       — 200-question golden set, RAGAS, red team, regression evaluation
M7  Observability    — Langfuse, Phoenix, tracing, latency, tokens, cost, drift
M8  Azure            — container deployment, database, storage, model integration
```

## Agent orientation checklist

Before writing code:
1. `git log --oneline -20` — understand where the project is.
2. Identify the milestone (above). Don't assume it matches what the user said.
3. Load the relevant skill file for the area you're working in.
4. Inspect existing interfaces before creating new ones.
5. Implement the **smallest correct change** — no speculative layers.

After writing code:
1. Run tests and report **actual** results.
2. Run lint/type checks where configured.
3. Inspect the diff — nothing unrelated should have changed.
4. Fix regressions before marking done.

## Definition of Done

A feature is NOT complete just because it works:
```
implementation exists        tests exist
errors are handled           security is considered
configuration documented     observability exists where relevant
documentation updated        existing tests still pass
```

## Reference files (load before working in that area)

- `skills/rag-engineering.md` — ingestion, chunking, provenance, dense/BM25/RRF, reranking, evidence threshold, citations
- `skills/security.md` — RBAC, jurisdiction isolation, prompt-injection, PII, citation-viewer auth, rate limiting
- `skills/frontend.md` — React structure, chat/document/citation UI, streaming, error handling
- `skills/evaluation.md` — golden set schema, RAGAS metrics, red-team categories
- `skills/observability.md` — Langfuse, Phoenix, what to trace and what NOT to log
- `skills/deployment.md` — Docker local setup, Azure strategy, health checks, secrets
