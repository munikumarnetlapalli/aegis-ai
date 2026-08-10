# ── AegisAI Backend — Dockerfile ──────────────────────────────────────────────
# Multi-stage build: builder installs dependencies, runtime is a lean image.
# NEVER bake secrets into this file or any image layer.

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest first (layer-cache friendly)
COPY pyproject.toml ./

# Install all dependencies into a local prefix
RUN pip install --no-cache-dir --prefix=/install ".[dev]" 2>/dev/null || \
    pip install --no-cache-dir --prefix=/install .

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps (libpq for psycopg2, curl for health check probe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/

# Run as non-root user
RUN adduser --disabled-password --gecos "" aegis
USER aegis

EXPOSE 8000

# Secrets are injected at runtime via environment variables — never here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
