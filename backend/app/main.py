"""AegisAI FastAPI application factory.

Architecture: thin routes → services → database
Route handlers must not contain business logic, DB queries, or authorization rules.
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.answer import router as answer_router
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.health import router as health_router
from app.api.observability import router as observability_router
from app.api.query import router as query_router
from app.core.config import get_settings


# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    settings = get_settings()
    logger.info(
        "AegisAI backend starting — env=%s version=%s",
        settings.app_env,
        settings.app_version,
    )

    # Run Alembic migrations on startup so the schema is always current.
    # In production this should be a separate init container / job, but
    # for local dev it is convenient and safe (Alembic is idempotent).
    try:
        import asyncio  # noqa: PLC0415
        from alembic.config import Config  # noqa: PLC0415
        from alembic import command  # noqa: PLC0415
        import os  # noqa: PLC0415

        alembic_cfg = Config(
            os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        )
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        # Run in a thread to avoid blocking the event loop
        await asyncio.get_event_loop().run_in_executor(
            None, lambda: command.upgrade(alembic_cfg, "head")
        )
        logger.info("Database migrations applied.")
    except Exception as exc:
        logger.warning("Migration run failed (continuing): %s", exc)

    yield
    logger.info("AegisAI backend shutting down.")


# ── Application factory ───────────────────────────────────────────────────────
def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="AegisAI",
        description=(
            "Production-grade regulated-document RAG assistant. "
            "Answers are grounded in retrieved evidence with verifiable citations."
        ),
        version=settings.app_version,
        lifespan=lifespan,
        # Hide docs in production (re-enable behind auth if needed)
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes ──────────────────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(query_router)
    app.include_router(answer_router)
    app.include_router(observability_router)


    # ── Global exception handler ───────────────────────────────────────────────
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Return structured error — never expose stack traces to clients."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred.",
                }
            },
        )

    return app


app = create_app()
