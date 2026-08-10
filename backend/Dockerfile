# ── AegisAI Backend — Dockerfile ──────────────────────────────────────────────
# Multi-stage build: builder installs dependencies, runtime is a lean image.
# NEVER bake secrets into this file or any image layer.

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System build tools needed to compile psycopg2 and other C extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker layer cache skips reinstall if unchanged
COPY requirements.txt ./

# Install all runtime dependencies into /install prefix
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps (libpq for asyncpg/psycopg2, curl for health-check probe)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Copy application source (this is the only layer that changes on code edits)
COPY app/ ./app/

# Run as non-root user — never run production containers as root
RUN adduser --disabled-password --gecos "" aegis
USER aegis

EXPOSE 8000

# Secrets are injected at runtime via environment variables — NEVER here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
