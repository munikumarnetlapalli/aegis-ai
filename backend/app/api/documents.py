"""Documents API routes with M4 security, rate limiting, and audit logging.

POST /documents    — upload and ingest a document
GET  /documents    — list all indexed documents
GET  /documents/{id} — document detail
"""
from __future__ import annotations

import logging
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.ingestion.normalizer import normalize_unicode_text
from app.ingestion.service import IngestionService
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.user import User
from app.schemas.documents import (
    DocumentChunkItem,
    DocumentChunksResponse,
    DocumentDeleteResponse,
    DocumentListItem,
    DocumentListResponse,
    DocumentUploadResponse,
)
from app.security.audit import audit_log
from app.security.dependencies import get_optional_user
from app.security.rate_limit import check_rate_limit_or_raise

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])

# Singleton service — parser/chunker/model are expensive to construct
_ingestion_service = IngestionService()


# ── POST /documents ────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a document",
)
async def upload_document(
    request: Request,
    file: UploadFile = File(..., description="Document file (PDF, DOCX, HTML, TXT)"),
    jurisdiction: str = Form(
        default="GLOBAL",
        description="Jurisdiction code, e.g. 'EU', 'US', 'HIPAA', 'GLOBAL'",
    ),
    allowed_roles: str = Form(
        default="",
        description="Comma-separated list of roles that may access this document",
    ),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """Upload a document and run it through the full ingestion pipeline."""
    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    user_id_str = str(current_user.id) if current_user else None

    # Rate limiting check
    await check_rate_limit_or_raise(
        request=request,
        scope="doc_upload",
        max_requests=settings.rate_limit_upload_per_minute,
        user_id=user_id_str,
    )

    roles = [r.strip().lower() for r in allowed_roles.split(",") if r.strip()]
    file_bytes = await file.read()
    content_type = file.content_type or "application/octet-stream"
    clean_filename = file.filename or "upload"

    try:
        result = await _ingestion_service.ingest(
            file_bytes=file_bytes,
            filename=clean_filename,
            content_type=content_type,
            jurisdiction=jurisdiction.upper(),
            allowed_roles=roles,
            db=db,
        )
    except ValueError as exc:
        audit_log(
            "DOCUMENT_UPLOAD_FAILED",
            user_id=user_id_str,
            email=current_user.email if current_user else None,
            ip_address=client_ip,
            status="FAILURE",
            details={"filename": clean_filename, "error": str(exc)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_DOCUMENT", "message": str(exc)},
        ) from exc
    except Exception as exc:
        logger.exception("Document ingestion failed: %s", exc)
        audit_log(
            "DOCUMENT_UPLOAD_FAILED",
            user_id=user_id_str,
            email=current_user.email if current_user else None,
            ip_address=client_ip,
            status="FAILURE",
            details={"filename": clean_filename, "error": "Internal error"},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "INGESTION_FAILED", "message": "Document ingestion failed."},
        ) from exc

    audit_log(
        "DOCUMENT_UPLOAD_SUCCESS",
        user_id=user_id_str,
        email=current_user.email if current_user else None,
        role=current_user.role if current_user else None,
        jurisdiction=jurisdiction.upper(),
        ip_address=client_ip,
        status="SUCCESS",
        details={
            "document_id": str(result.document_id),
            "filename": result.filename,
            "chunk_count": result.chunk_count,
            "page_count": result.page_count,
            "allowed_roles": roles,
        },
    )

    return DocumentUploadResponse(
        document_id=result.document_id,
        filename=result.filename,
        status=result.status,
        chunk_count=result.chunk_count,
        page_count=result.page_count,
    )


# ── GET /documents ─────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List indexed documents",
)
async def list_documents(
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """Return all documents ordered by creation date (newest first)."""
    # If user is authenticated and not admin/auditor, optionally filter by jurisdiction
    stmt = select(Document).order_by(Document.created_at.desc())
    if current_user is not None and current_user.role not in ("admin", "auditor"):
        if current_user.jurisdiction != "GLOBAL":
            stmt = stmt.where(
                (Document.jurisdiction == current_user.jurisdiction)
                | (Document.jurisdiction == "GLOBAL")
            )

    rows = (await db.execute(stmt)).scalars().all()

    items = [
        DocumentListItem(
            document_id=doc.id,
            filename=doc.filename,
            content_type=doc.content_type,
            jurisdiction=doc.jurisdiction,
            allowed_roles=doc.allowed_roles,
            status=doc.status,
            chunk_count=doc.chunk_count,
            page_count=doc.page_count,
            created_at=doc.created_at,
        )
        for doc in rows
    ]
    return DocumentListResponse(documents=items, total=len(items))


# ── GET /documents/{id} ────────────────────────────────────────────────────────

@router.get(
    "/{document_id}",
    response_model=DocumentListItem,
    summary="Get document detail",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentListItem:
    """Return a single document by ID with server-side authorization check."""
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document {document_id} not found."},
        )

    # Server-side jurisdiction check for authenticated users
    if current_user is not None and current_user.role not in ("admin", "auditor"):
        if (
            current_user.jurisdiction != "GLOBAL"
            and doc.jurisdiction != "GLOBAL"
            and doc.jurisdiction != current_user.jurisdiction
        ):
            audit_log(
                "DOCUMENT_ACCESS_DENIED",
                user_id=str(current_user.id),
                email=current_user.email,
                role=current_user.role,
                jurisdiction=current_user.jurisdiction,
                status="DENIED",
                details={"document_id": str(document_id), "doc_jurisdiction": doc.jurisdiction},
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "JURISDICTION_MISMATCH", "message": "Access to this document is restricted by jurisdiction."},
            )

    return DocumentListItem(
        document_id=doc.id,
        filename=doc.filename,
        content_type=doc.content_type,
        jurisdiction=doc.jurisdiction,
        allowed_roles=doc.allowed_roles,
        status=doc.status,
        chunk_count=doc.chunk_count,
        page_count=doc.page_count,
        created_at=doc.created_at,
    )


# ── GET /documents/{id}/chunks (M5 Chunk Inspector) ──────────────────────────

@router.get(
    "/{document_id}/chunks",
    response_model=DocumentChunksResponse,
    summary="Get document chunks with provenance (no raw vectors)",
)
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentChunksResponse:
    """Return chunks of a document for provenance and content inspection."""
    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document {document_id} not found."},
        )

    # Server-side jurisdiction check
    if current_user is not None and current_user.role not in ("admin", "auditor"):
        if (
            current_user.jurisdiction != "GLOBAL"
            and doc.jurisdiction != "GLOBAL"
            and doc.jurisdiction != current_user.jurisdiction
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "JURISDICTION_MISMATCH", "message": "Access to this document is restricted by jurisdiction."},
            )

    stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index.asc())
    rows = (await db.execute(stmt)).scalars().all()

    chunk_items = [
        DocumentChunkItem(
            chunk_id=c.id,
            document_id=c.document_id,
            filename=c.filename,
            chunk_index=c.chunk_index,
            page=c.page,
            section=normalize_unicode_text(c.section or ""),
            jurisdiction=c.jurisdiction,
            allowed_roles=c.allowed_roles or [],
            content=normalize_unicode_text(c.content),
            char_count=len(normalize_unicode_text(c.content)),
        )
        for c in rows
    ]

    return DocumentChunksResponse(
        document_id=doc.id,
        filename=doc.filename,
        total_chunks=len(chunk_items),
        chunks=chunk_items,
    )


# ── DELETE /documents/{id} ───────────────────────────────────────────────────

@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    summary="Delete a document and its chunks",
)
async def delete_document(
    document_id: uuid.UUID,
    request: Request,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentDeleteResponse:
    """Delete a document and all cascaded chunks with authorization check."""
    client_ip = request.client.host if request.client else "unknown"
    user_id_str = str(current_user.id) if current_user else None

    # Deletion requires admin or compliance_officer if authenticated
    if current_user is not None and current_user.role not in ("admin", "compliance_officer"):
        audit_log(
            "DOCUMENT_DELETE_FORBIDDEN",
            user_id=user_id_str,
            email=current_user.email,
            role=current_user.role,
            jurisdiction=current_user.jurisdiction,
            ip_address=client_ip,
            status="DENIED",
            details={"document_id": str(document_id)},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "INSUFFICIENT_PERMISSIONS", "message": "Only administrators or compliance officers can delete documents."},
        )

    doc = await db.get(Document, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": f"Document {document_id} not found."},
        )

    filename = doc.filename
    await db.delete(doc)
    await db.commit()

    audit_log(
        "DOCUMENT_DELETED",
        user_id=user_id_str,
        email=current_user.email if current_user else None,
        role=current_user.role if current_user else None,
        jurisdiction=doc.jurisdiction,
        ip_address=client_ip,
        status="SUCCESS",
        details={"document_id": str(document_id), "filename": filename},
    )

    return DocumentDeleteResponse(
        document_id=document_id,
        filename=filename,
        deleted=True,
        message=f"Document '{filename}' and all associated chunks were successfully deleted.",
    )

