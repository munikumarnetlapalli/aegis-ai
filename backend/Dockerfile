# ── AegisAI Backend — Dockerfile ──────────────────────────────────────────────
# Multi-stage build: builder installs dependencies, runtime is a lean image.
# NEVER bake secrets into this file or any image layer.

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# System build tools needed to compile psycopg2 and other C extensions.
# M2 additions: poppler-utils (PDF parsing), libgl1 + libglib2.0-0 (OpenCV/Docling)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libpq-dev \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker layer cache skips reinstall if unchanged
COPY requirements.txt ./

# Install all runtime dependencies into /install prefix
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Runtime system deps:
#   libpq5       — asyncpg / psycopg2
#   curl         — health-check probe
#   poppler-utils — Docling PDF rendering
#   libgl1        — OpenCV (used internally by Docling)
#   libglib2.0-0  — GLib (OpenCV dependency)
#   gcc / g++     — PyTorch TorchInductor needs a C++ compiler at runtime;
#                   without it, any torch.compile() call will crash with
#                   "InvalidCxxCompiler: No working C++ compiler found"
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder stage
COPY --from=builder /install /usr/local

# Disable PyTorch TorchDynamo / Inductor JIT compilation.
# Docling's layout models trigger torch.compile() which tries to JIT-compile
# C++ kernels. We disable all neural pipeline stages in parser.py, but these
# env vars act as a container-level safety net in case any transitive import
# tries to trigger compilation.
ENV TORCHDYNAMO_DISABLE=1
ENV TORCH_COMPILE_DISABLE=1

# Copy application source (this is the only layer that changes on code edits)
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Run as non-root user — never run production containers as root
RUN adduser --disabled-password --gecos "" aegis
USER aegis

EXPOSE 8000

# Secrets are injected at runtime via environment variables — NEVER here.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
