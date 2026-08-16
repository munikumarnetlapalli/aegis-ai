"""Query API route.

POST /query — retrieve evidence chunks for a natural-language query.

M2 retrieval smoke-test endpoint updated for M4 server-side authentication support:
If authenticated, uses the trusted user role & jurisdiction.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.retrieval.service import RetrievalService
from app.schemas.documents import (
    ChunkResult,
    ProvenanceSchema,
    QueryRequest,
    QueryResponse,
)
from app.security.dependencies import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])

_retrieval_service = RetrievalService()


@router.post(
    "",
    response_model=QueryResponse,
    summary="Retrieve evidence chunks for a query",
)
async def query_documents(
    body: QueryRequest,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> QueryResponse:
    """Embed the query and return the top-k most similar document chunks.

    Jurisdiction and role filters are applied inside the SQL query.
    """
    settings = get_settings()
    top_k = min(body.top_k, settings.retrieval_top_k)

    if current_user is not None:
        effective_jurisdiction = current_user.jurisdiction
        effective_roles = None if current_user.role == "admin" else [current_user.role]
    else:
        effective_jurisdiction = body.jurisdiction
        effective_roles = body.allowed_roles

    try:
        results = await _retrieval_service.retrieve(
            query=body.query,
            jurisdiction=effective_jurisdiction,
            allowed_roles=effective_roles,
            top_k=top_k,
            db=db,
        )
    except Exception as exc:
        logger.exception("Query failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "RETRIEVAL_FAILED", "message": "Retrieval failed."},
        ) from exc

    chunk_results = [
        ChunkResult(
            chunk_id=r.chunk_id,
            content=r.content,
            score=r.score,
            provenance=ProvenanceSchema(
                document_id=r.provenance.document_id,
                filename=r.provenance.filename,
                page=r.provenance.page,
                section=r.provenance.section,
                jurisdiction=r.provenance.jurisdiction,
                chunk_index=r.provenance.chunk_index,
            ),
        )
        for r in results
    ]

    message = (
        f"Found {len(chunk_results)} evidence chunk(s)."
        if chunk_results
        else "No matching chunks found.  Try a different query or upload relevant documents."
    )

    return QueryResponse(
        query=body.query,
        results=chunk_results,
        result_count=len(chunk_results),
        message=message,
    )
