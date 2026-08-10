# ADR-001 — Vector Storage: PostgreSQL + pgvector

**Status:** Accepted
**Date:** 2026-08-10
**Milestone:** M1 Foundation

---

## Context

AegisAI needs a vector store to index document chunk embeddings for dense
semantic retrieval. The system also needs to store chunk metadata (jurisdiction,
roles, provenance), enforce RBAC at the query level, and run BM25 alongside
dense retrieval.

Key constraints:
- Authorization and jurisdiction filtering must happen **inside** the retrieval
  query — not as a post-retrieval filter.
- Every chunk must be co-located with its metadata so that a single query can
  enforce RBAC, jurisdiction, and embedding similarity simultaneously.
- Local-first development (no managed cloud service required for M1–M7).
- Must support parameterized queries to prevent SQL injection.

## Decision

Use **PostgreSQL + pgvector** as the sole vector store.

The `pgvector` extension adds a `VECTOR` column type and supports both
`ivfflat` and `hnsw` indices for approximate nearest-neighbour search.
All chunk metadata lives in the same PostgreSQL table, enabling RBAC and
jurisdiction filtering in a single parameterized SQL query.

## Alternatives considered

| Option | Reason not chosen |
|---|---|
| Pinecone | Managed SaaS — no local dev, metadata filtering less composable with SQL RBAC, adds cost and external dependency from day 1 |
| Weaviate | Separate service to deploy and maintain; RBAC model is different from SQL; harder to co-locate with existing PostgreSQL data |
| Qdrant | Good option but adds a second stateful service; metadata filtering syntax is non-SQL; harder to enforce RBAC in one query |
| Chroma | Good for prototyping; not production-grade for multi-tenant RBAC + jurisdiction isolation |
| Redis Vector | Redis is not a primary relational store; awkward to join chunk metadata with user permissions |

## Trade-offs

**Benefits:**
- Single database for all structured data and vectors — no data sync between stores.
- RBAC + jurisdiction filter composable with standard SQL `WHERE` clauses.
- `pgvector` is production-battle-tested (Supabase, Neon, etc.).
- Azure Database for PostgreSQL supports pgvector — no migration needed for M10.
- Parameterized ORM queries prevent SQL injection naturally.

**Costs:**
- pgvector is not as fast as dedicated ANN databases at very large scale
  (hundreds of millions of vectors). This is acceptable for the regulated-document
  use case which typically has thousands to tens of thousands of chunks.
- Requires pgvector extension to be installed (handled by `pgvector/pgvector:pg16`
  Docker image — no manual setup needed).

## Consequences

- All chunks stored in PostgreSQL with `embedding VECTOR(1536)` column.
- Index type (`ivfflat` vs `hnsw`) determined by retrieval quality experiments in M3.
- Provider abstraction means the embedding dimension can change when the embedding
  model changes (requires migration and re-indexing).
- If scale eventually requires a dedicated ANN store, the `EmbeddingProvider` /
  `RetrievalResult` interface allows swapping without changing the agent layer.
