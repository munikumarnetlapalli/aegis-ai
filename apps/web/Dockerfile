# ── AegisAI Frontend — Dockerfile ─────────────────────────────────────────────
# Runs the Vite dev server inside Docker for local development.
# NEVER bake secrets into this image — use environment variables at runtime.

FROM node:20-alpine

WORKDIR /app

# CHOKIDAR_USEPOLLING: required for Vite file watching to work inside Docker
# on Windows (Docker Desktop uses a virtual filesystem that doesn't fire
# native inotify events — polling is the reliable fallback).
ENV CHOKIDAR_USEPOLLING=true

# Copy dependency manifests first (layer-cache friendly — reinstall only when
# package.json changes, not on every source code change)
COPY package.json ./

# Install dependencies
RUN npm install

# Copy source after npm install to keep the cache layer valid
COPY . .

EXPOSE 5173

# --host 0.0.0.0 is required — without it Vite binds only to localhost
# inside the container and is unreachable from the host machine.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
