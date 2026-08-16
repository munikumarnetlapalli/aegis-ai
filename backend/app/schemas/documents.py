"""Pydantic schemas for M2 document ingestion and retrieval responses."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Documents ──────────────────────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    status: str
    chunk_count: int
    page_count: int
    message: str = "Document ingested successfully."


class DocumentListItem(BaseModel):
    document_id: uuid.UUID
    filename: str
    content_type: str
    jurisdiction: str
    allowed_roles: list[str]
    status: str
    chunk_count: int | None
    page_count: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]
    total: int


# ── Query ──────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    jurisdiction: str | None = Field(
        default=None,
        description="Filter by jurisdiction (e.g. 'EU', 'US'). None = no filter.",
    )
    allowed_roles: list[str] | None = Field(
        default=None,
        description="Filter by roles. None = no role filter.",
    )
    top_k: int = Field(default=10, ge=1, le=50)


class ProvenanceSchema(BaseModel):
    document_id: uuid.UUID
    filename: str
    page: int
    section: str
    jurisdiction: str
    chunk_index: int


class ChunkResult(BaseModel):
    chunk_id: uuid.UUID
    content: str
    score: float
    provenance: ProvenanceSchema


class QueryResponse(BaseModel):
    query: str
    results: list[ChunkResult]
    result_count: int
    message: str = ""


# ── Answer (M3) ────────────────────────────────────────────────────────────────

class AnswerRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    jurisdiction: str | None = Field(
        default=None,
        description="Filter by jurisdiction (e.g. 'EU', 'US'). None = no filter.",
    )
    allowed_roles: list[str] | None = Field(
        default=None,
        description="Filter by roles. None = no role filter.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of evidence chunks to retrieve after reranking.",
    )


class Citation(BaseModel):
    """A validated citation that resolves to a real retrieved chunk."""

    citation_number: int
    chunk_id: uuid.UUID
    filename: str
    section: str
    page: int
    excerpt: str = Field(description="First 200 chars of the source chunk.")


class AnswerTelemetry(BaseModel):
    """M7 telemetry metadata attached to AnswerResponse."""

    request_id: str
    total_latency_ms: float = 0.0
    retrieval_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    latency_breakdown_ms: dict[str, float] = Field(default_factory=dict)
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: float = 0.0


class AnswerResponse(BaseModel):
    """Full RAG response with grounded answer, citations, and confidence."""

    query: str
    answer: str
    citations: list[Citation]
    confidence: str = Field(
        description="Evidence quality: 'high', 'medium', or 'low'."
    )
    abstained: bool = Field(
        description="True if the model abstained due to insufficient evidence."
    )
    evidence_count: int = Field(
        description="Number of evidence chunks used for generation."
    )
    telemetry: AnswerTelemetry | None = Field(
        default=None, description="Optional M7 execution telemetry and performance metadata."
    )



# ── M5: Document Chunk Inspection & Deletion ──────────────────────────────────

class DocumentChunkItem(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    page: int
    section: str
    jurisdiction: str
    allowed_roles: list[str]
    content: str
    char_count: int

    model_config = {"from_attributes": True}


class DocumentChunksResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    total_chunks: int
    chunks: list[DocumentChunkItem]


class DocumentDeleteResponse(BaseModel):
    document_id: uuid.UUID
    filename: str
    deleted: bool
    message: str = "Document deleted successfully."


