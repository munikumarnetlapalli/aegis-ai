"""Health check endpoint.

GET /health

Returns 200 {"status": "healthy", "database": "connected", "version": "..."}
Returns 503 {"status": "unhealthy", "database": "unreachable", "version": "..."}
if the database cannot be reached.

This endpoint is used by:
- Docker Compose health checks (backend service)
- React frontend on mount to verify the stack is running
- Load balancer / orchestration liveness probes
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Health check",
    response_description="Service health status including database connectivity",
)
async def health_check() -> JSONResponse:
    """Check service health and database connectivity.

    Runs a lightweight `SELECT 1` against PostgreSQL to confirm the database
    is reachable. Returns 503 if the database is unreachable so that Docker
    Compose and load balancers can detect the failure automatically.
    """
    settings = get_settings()
    version = settings.app_version

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except SQLAlchemyError as exc:
        logger.error("Health check: database unreachable — %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "unreachable",
                "version": version,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy",
            "database": db_status,
            "version": version,
        },
    )
