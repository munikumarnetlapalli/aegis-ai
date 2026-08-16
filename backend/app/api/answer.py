"""Answer API route — POST /answer.

Full RAG endpoint with M4 layered security + M7 Observability:
- Server-side authentication and trusted role/jurisdiction derivation
- Adversarial prompt-injection pre-screening
- Rate limiting protection
- Hybrid retrieval (dense + BM25 + RRF + reranker) inside SQL auth constraints
- Grounded generation with citation validation
- Presidio-class PII redaction on responses
- Structured compliance audit logging
- M7 end-to-end tracing and privacy-safe telemetry
"""
from __future__ import annotations

import logging
import time

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.generation.service import GenerationService
from app.models.user import User
from app.observability.dispatcher import dispatch_trace
from app.observability.tracer import get_tracer
from app.retrieval.service import HybridRetrievalService
from app.schemas.documents import AnswerRequest, AnswerResponse, AnswerTelemetry, Citation
from app.security.audit import audit_log
from app.security.dependencies import get_optional_user
from app.security.guardrails import scan_prompt_injection
from app.security.pii import apply_pii_policy
from app.security.rate_limit import check_rate_limit_or_raise

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/answer", tags=["answer"])

_hybrid_retrieval = HybridRetrievalService()
_generation_service = GenerationService()


@router.post(
    "",
    response_model=AnswerResponse,
    summary="Ask a question and receive a grounded, cited answer",
)
async def answer_query(
    body: AnswerRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> AnswerResponse:
    """Full RAG pipeline with M4 security controls and M7 Observability.

    Authorization:
        Role and jurisdiction filters are derived server-side from the authenticated
        user's token and applied inside the SQL retrieval query.
    """
    settings = get_settings()
    tracer = get_tracer()
    client_ip = request.client.host if request.client else "unknown"
    start_time = time.time()

    # Determine user identity and role
    user_id_str = str(current_user.id) if current_user else None
    if current_user is not None:
        effective_jurisdiction = current_user.jurisdiction
        effective_roles = None if current_user.role == "admin" else [current_user.role]
        effective_email = current_user.email
        effective_role = current_user.role
    else:
        effective_jurisdiction = body.jurisdiction
        effective_roles = body.allowed_roles
        effective_email = None
        effective_role = None

    # ── M7: Start Trace ───────────────────────────────────────────────────────
    req_id = request.headers.get("X-Request-ID")
    trace = tracer.start_trace(
        query=body.query,
        request_id=req_id,
        session_id=user_id_str,
        user_role=effective_role,
        jurisdiction=effective_jurisdiction,
    )

    # ── 1. Rate limiting ───────────────────────────────────────────────────────
    await check_rate_limit_or_raise(
        request=request,
        scope="query_answer",
        max_requests=settings.rate_limit_query_per_minute,
        user_id=user_id_str,
    )

    # ── 2. Prompt injection pre-screening ──────────────────────────────────────
    if settings.prompt_injection_detection_enabled:
        with tracer.span("security.guardrail") as guardrail_span:
            is_injection, reason = scan_prompt_injection(body.query)
            if guardrail_span:
                guardrail_span.metadata["is_injection"] = is_injection
                if is_injection:
                    guardrail_span.metadata["reason"] = reason

        if is_injection:
            audit_log(
                "PROMPT_INJECTION_DETECTED",
                user_id=user_id_str,
                email=effective_email,
                role=effective_role,
                jurisdiction=effective_jurisdiction,
                ip_address=client_ip,
                status="BLOCKED",
                details={"reason": reason, "query": body.query[:200]},
            )
            tracer.finish_trace(guardrail_blocked=True, abstained=True)
            background_tasks.add_task(dispatch_trace, trace)

            telemetry = _build_telemetry(trace)
            return AnswerResponse(
                query=body.query,
                answer=(
                    "I cannot process this request because it violates system security policies. "
                    "Please ask a valid question regarding regulated policy documents."
                ),
                citations=[],
                confidence="low",
                abstained=True,
                evidence_count=0,
                telemetry=telemetry,
            )

    top_k = min(body.top_k, settings.reranker_top_k)

    # ── 3. Hybrid retrieval (SQL-level RBAC & jurisdiction) ────────────────────
    try:
        context_chunks = await _hybrid_retrieval.retrieve(
            query=body.query,
            jurisdiction=effective_jurisdiction,
            allowed_roles=effective_roles,
            top_k=top_k,
            db=db,
        )
    except Exception as exc:
        logger.exception("Hybrid retrieval failed: %s", exc)
        tracer.finish_trace(error=str(exc))
        background_tasks.add_task(dispatch_trace, trace)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "RETRIEVAL_FAILED", "message": "Retrieval failed."},
        ) from exc

    # ── 4. Generation + citation validation ────────────────────────────────────
    try:
        result = await _generation_service.answer(
            query=body.query,
            context_chunks=context_chunks,
            evidence_threshold=settings.evidence_threshold,
            min_evidence_chunks=settings.min_evidence_chunks,
        )
    except Exception as exc:
        logger.exception("Generation failed: %s", exc)
        tracer.finish_trace(error=str(exc))
        background_tasks.add_task(dispatch_trace, trace)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "GENERATION_FAILED", "message": "Answer generation failed."},
        ) from exc

    # ── 5. PII redaction / blocking ────────────────────────────────────────────
    final_answer = result.answer
    if settings.pii_redaction_enabled:
        with tracer.span("security.pii", metadata={"policy": settings.pii_policy}) as pii_span:
            final_answer, is_blocked, pii_matches = apply_pii_policy(
                final_answer, policy=settings.pii_policy
            )
            if pii_span:
                pii_span.metadata["entity_count"] = len(pii_matches)
                pii_span.metadata["is_blocked"] = is_blocked

        if pii_matches:
            audit_log(
                "PII_DETECTED",
                user_id=user_id_str,
                email=effective_email,
                ip_address=client_ip,
                status="BLOCKED" if is_blocked else "REDACTED",
                details={"entity_count": len(pii_matches), "policy": settings.pii_policy},
            )
        if is_blocked:
            tracer.finish_trace(
                retrieved_chunk_ids=[c.chunk_id for c in context_chunks],
                top_reranker_score=context_chunks[0].score if context_chunks else None,
                citation_count=0,
                citation_status="NONE",
                abstained=True,
                guardrail_blocked=False,
            )
            background_tasks.add_task(dispatch_trace, trace)
            telemetry = _build_telemetry(trace)
            return AnswerResponse(
                query=result.query,
                answer=final_answer,
                citations=[],
                confidence="low",
                abstained=True,
                evidence_count=result.evidence_count,
                telemetry=telemetry,
            )

    # ── 6. Map citations with PII redaction ────────────────────────────────────
    citations = []
    for c in result.citations:
        excerpt = c.excerpt
        if settings.pii_redaction_enabled:
            excerpt, _, _ = apply_pii_policy(excerpt, policy="redact")
        citations.append(
            Citation(
                citation_number=c.citation_number,
                chunk_id=c.chunk_id,
                filename=c.filename,
                section=c.section,
                page=c.page,
                excerpt=excerpt,
            )
        )

    # ── 7. Structured audit log ───────────────────────────────────────────────
    elapsed_ms = int((time.time() - start_time) * 1000)
    audit_log(
        "QUERY_EXECUTED",
        user_id=user_id_str,
        email=effective_email,
        role=effective_role,
        jurisdiction=effective_jurisdiction,
        ip_address=client_ip,
        status="SUCCESS",
        details={
            "query": body.query[:120],
            "evidence_count": result.evidence_count,
            "abstained": result.abstained,
            "confidence": result.confidence,
            "elapsed_ms": elapsed_ms,
        },
    )

    # ── 8. M7: Finalize Trace and Build Telemetry ──────────────────────────────
    tracer.finish_trace(
        retrieved_chunk_ids=[c.chunk_id for c in context_chunks],
        top_reranker_score=context_chunks[0].score if context_chunks else None,
        citation_count=len(citations),
        citation_status="PASS" if len(citations) > 0 else "NONE",
        abstained=result.abstained,
        guardrail_blocked=False,
    )
    background_tasks.add_task(dispatch_trace, trace)
    telemetry = _build_telemetry(trace)

    return AnswerResponse(
        query=result.query,
        answer=final_answer,
        citations=citations,
        confidence=result.confidence,
        abstained=result.abstained,
        evidence_count=result.evidence_count,
        telemetry=telemetry,
    )


def _build_telemetry(trace) -> AnswerTelemetry | None:
    """Safely build AnswerTelemetry metadata object from RequestTrace."""
    if trace is None:
        return None
    return AnswerTelemetry(
        request_id=trace.request_id,
        total_latency_ms=trace.total_latency_ms,
        retrieval_latency_ms=round(
            trace.latency_breakdown_ms.get("retrieval.dense", 0.0)
            + trace.latency_breakdown_ms.get("retrieval.bm25", 0.0),
            3,
        ),
        llm_latency_ms=round(trace.latency_breakdown_ms.get("generation.llm", 0.0), 3),
        latency_breakdown_ms=trace.latency_breakdown_ms,
        token_usage={
            "input_tokens": trace.tokens_and_cost.input_tokens,
            "output_tokens": trace.tokens_and_cost.output_tokens,
            "total_tokens": trace.tokens_and_cost.total_tokens,
        },
        estimated_cost_usd=trace.tokens_and_cost.estimated_cost_usd,
    )
