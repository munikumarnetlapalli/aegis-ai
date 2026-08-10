# Deployment Skill

Load this file when working on: Docker Compose, Dockerfiles, Azure deployment,
health checks, secrets management, or `infrastructure/`.

## Local-first principle

Debug retrieval, security, and evaluation issues locally before moving anything
to Azure. Azure Student credits are finite — don't burn them on infrastructure
iteration that can be done locally.

## M1 Docker Compose (initial services)

```
frontend   — React/Vite dev server     (port 5173)
backend    — FastAPI + uvicorn         (port 8000)
postgres   — pgvector/pgvector:pg16   (port 5432, internal volume)
```

Add langfuse and phoenix **after** the core pipeline is stable and evaluated.
Don't add observability infrastructure before there's something to observe.

## Health checks (required for all services)

```yaml
# postgres
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
  interval: 10s
  timeout: 5s
  retries: 5

# backend — depends on postgres being healthy
healthcheck:
  test: ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
  interval: 15s
  timeout: 5s
  retries: 3
  start_period: 30s
```

Backend must use `depends_on: postgres: condition: service_healthy`.

## GET /health contract

```json
{
  "status": "healthy",
  "database": "connected",
  "version": "0.1.0"
}
```

Returns `503` if the database is unreachable. React app polls this on mount.

## Secrets (Docker)

- **Never bake secrets into images.**
- Secrets come from `.env` (gitignored) via `env_file: .env` in Compose.
- `.env.example` is committed; `.env` is never committed.
- In production (Azure), use Azure Key Vault or environment variables injected
  at deployment time — not secrets baked into container images.

## Dockerfile best practices

- Multi-stage builds where it saves significant image size.
- Pin base image versions (`python:3.12-slim`, `node:20-alpine`).
- Don't run as root in production images.
- No secrets in ENV instructions; read them at runtime.
- Backend: `CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`
- Frontend dev: `CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]`

## Azure deployment strategy (M10)

```
React frontend → Azure Static Web Apps or CDN
FastAPI container → Azure Container Apps or App Service
PostgreSQL → Azure Database for PostgreSQL (Flexible Server + pgvector extension)
Document storage → Azure Blob Storage
LLM/embedding → Azure OpenAI Service
Secrets → Azure Key Vault
```

Migration order: get local system fully working and evaluated first, then migrate
the database, then the backend container, then the frontend. Don't migrate all
layers simultaneously — it makes debugging impossible.

## Docker Compose volume naming

Use named volumes for database persistence:
```yaml
volumes:
  postgres_data:
    driver: local
```

Use `docker compose down -v` only when you intentionally want to wipe data.
Default `docker compose down` preserves the volume.
