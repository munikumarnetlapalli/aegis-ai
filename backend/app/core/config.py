"""Application configuration.

All settings are read from environment variables or a .env file.
Never hard-code secrets here — this file is committed to source control.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_version: str = "0.1.0"
    secret_key: str = "change-me-in-production"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+asyncpg://aegis:aegis_dev_password@postgres:5432/aegisdb"
    )

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── Embedding (M2+) ───────────────────────────────────────────────────────
    # Provider: "local" uses sentence-transformers; future: "azure", "openai"
    embedding_provider: str = "local"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # MUST match the Vector(dim) in chunk.py and migration 0001.
    # Changing this requires a new migration.
    embedding_dim: int = 384

    # ── Chunking (M2+) ────────────────────────────────────────────────────────
    # Target chunk size in tokens.  Measure retrieval quality before tuning.
    chunk_size: int = 512
    # Overlap as a fraction of chunk_size.  10% ≈ 51 tokens.
    chunk_overlap: int = 51

    # ── Upload limits (M2+) ───────────────────────────────────────────────────
    upload_max_mb: int = 50
    allowed_extensions: list[str] = [".pdf", ".docx", ".html", ".txt"]

    # ── Retrieval (M2+) ───────────────────────────────────────────────────────────
    # M6 tuning: increased from 20→30 to give reranker more candidates.
    # Dense@30 ensures low-ranked but relevant chunks survive into RRF.
    retrieval_top_k: int = 30

    # ── M3: BM25 + RRF ────────────────────────────────────────────────────────
    # M6 tuning: increased from 20→30 to match dense candidate pool.
    bm25_top_k: int = 30
    # RRF constant k: lower k gives a steeper relative bonus to chunks appearing
    # in BOTH dense and BM25 lists.  Tuned from 60→40 based on M6 diagnostics.
    rrf_k: int = 40
    # Final context size fed to the LLM after reranking.
    reranker_top_k: int = 5

    # ── M3: Reranker ──────────────────────────────────────────────────────────
    # CrossEncoder from sentence-transformers. No GPU required for this model.
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # ── M3: Evidence threshold & abstention ───────────────────────────────────
    # Min reranker score for the top chunk before we hard-abstain.
    # Cross-encoder ms-marco logits:
    #   > 1.0: high confidence
    #   -3.0 to 1.0: medium confidence
    #   -7.0 to -3.0: soft evidence (proceed to LLM grounded generation)
    #   < -7.0: hard abstention (irrelevant noise/trap query)
    evidence_threshold: float = -7.0
    # Min number of retrieved chunks above threshold before we answer.
    min_evidence_chunks: int = 1


    # ── M3: LLM provider ──────────────────────────────────────────────────────
    # Provider: "ollama" (local) | "azure" (M8+)
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    ollama_base_url: str = "http://ollama:11434"

    # ── M4: Security & Authentication ─────────────────────────────────────────
    jwt_secret_key: str = "change-me-in-production-jwt-secret"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # ── M4: Rate limiting & Guardrails ─────────────────────────────────────────
    rate_limit_enabled: bool = True
    rate_limit_auth_per_minute: int = 10
    rate_limit_query_per_minute: int = 60
    rate_limit_upload_per_minute: int = 20

    pii_redaction_enabled: bool = True
    pii_policy: Literal["redact", "block"] = "redact"
    prompt_injection_detection_enabled: bool = True
    dev_seed_users: bool = True

    # ── M7: Observability, Tracing & Drift ────────────────────────────────────
    observability_enabled: bool = True
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "http://localhost:3010"
    phoenix_host: str | None = None
    drift_threshold_pct: float = 5.0


    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def upload_max_bytes(self) -> int:
        return self.upload_max_mb * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton."""
    return Settings()
