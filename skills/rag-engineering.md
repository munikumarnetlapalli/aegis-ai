# RAG Engineering Skill

Load this file when working on: ingestion pipeline, chunking, embeddings, vector
indexing, dense retrieval, BM25, RRF, reranking, evidence threshold, or citations.

## Ingestion pipeline

```
Upload → Validate → Parse → Normalize → Structure extraction
       → Chunk → Metadata enrichment → Embed → Index
```

Supported formats (M2): PDF, DOCX, HTML, TXT. Primary parser: **Docling**.
Reserve multimodal processing (ColPali) for documents where visual information
materially affects meaning — don't route everything through expensive multimodal.

## Provenance (non-negotiable)

Every chunk must carry:

```python
{
  "chunk_id":          str,   # unique, stable
  "document_id":       str,
  "document_version":  str,
  "filename":          str,
  "page":              int,
  "section":           str,
  "jurisdiction":      str,   # e.g. "EU", "US", "HIPAA"
  "allowed_roles":     list[str],
  "chunk_index":       int,
  "created_at":        datetime
}
```

Never create a chunk without all of the above. Never generate a citation that
can't map back to a stored chunk.

## Chunking strategy

Prefer **structure-aware** over blind character splitting:
- Preserve headings, paragraphs, tables, lists, and page boundaries.
- Chunk size and overlap must be **configurable** (not hard-coded).
- Measure retrieval quality before tuning chunking parameters.
- Starting point (not a claimed optimal): ~512 tokens, 10% overlap.

## Provider interfaces

All providers behind interfaces so they can be swapped without rewriting the agent:

```python
class EmbeddingProvider:
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, query: str) -> list[float]: ...

class LLMProvider:
    def generate(self, messages: list[dict], **kwargs) -> str: ...

class Reranker:
    def rerank(self, query: str, documents: list[RetrievalResult]) -> list[RetrievalResult]: ...
```

Local dev: sentence-transformers + Ollama. Production: Azure-hosted models.
Provider selection belongs in **configuration**, not application logic.

## Retrieval pipeline

### Dense (pgvector)

Input: query embedding. Output: ranked chunks.
Authorization + jurisdiction filters apply **during** the query — not after.

### Sparse (BM25)

Critical for exact terminology, policy numbers, section references, legal phrases,
and uncommon identifiers that dense embeddings blur.

### Hybrid (RRF)

```
Query → Dense Retrieval ──┐
      → BM25 ─────────────┼→ RRF → Top-N → Reranker → Top-5
```

Use Reciprocal Rank Fusion with configurable `k` parameter.
Starting point (measure before claiming optimal): dense top-20, BM25 top-20, merged top-20.

### Reranking

```
Hybrid top-20 → Cross-encoder reranker → top-5 (with scores)
```

Record reranker scores — don't discard ranking signal you might need for debugging.
Reranker must be behind the `Reranker` interface above.

## Evidence threshold and abstention

Before generation, decide whether evidence is sufficient using:
- Reranker score of the top chunk
- Number of supporting chunks above a confidence floor
- Source agreement (chunks from multiple documents vs. single source)
- Citation availability

If evidence is below the **configurable** threshold → **abstain**:

```
"I don't have confident citations to answer this question.
The available documents do not provide sufficient evidence."
```

Don't claim the threshold is optimal until evaluated against the golden set.

## Citation architecture

The model must **never invent a citation identifier**.
Citations reference retrieved chunk IDs only.

```
[1] Policy-2026.pdf §8.2 p.12
```

Backend validates `citation_id → chunk → document → page/section` and rejects
anything that doesn't resolve. Every factual claim should have evidence behind it.

## Database schema (PostgreSQL + pgvector)

Core entities: `users`, `roles`, `documents`, `document_versions`, `chunks`,
`conversations`, `messages`, `citations`, `evaluation_runs`.

Chunk fields:
```sql
chunk_id        UUID PRIMARY KEY,
document_id     UUID REFERENCES documents(id),
version         VARCHAR,
content         TEXT,
embedding       VECTOR(1536),   -- dimension matches embedding model
page            INTEGER,
section         VARCHAR,
source          VARCHAR,
jurisdiction    VARCHAR,
allowed_roles   TEXT[],
created_at      TIMESTAMPTZ DEFAULT now()
```

Use migrations for every schema change. Index on `embedding` (ivfflat/hnsw),
`jurisdiction`, `allowed_roles`, and `document_id` based on actual query patterns.
