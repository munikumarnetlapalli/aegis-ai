# ── AegisAI Frontend — Dockerfile ─────────────────────────────────────────────
# Runs the Vite dev server inside Docker for local development.
# NEVER bake secrets into this image — use environment variables at runtime.

FROM node:20-alpine

WORKDIR /app

# Copy dependency manifests first (layer-cache friendly)
COPY package.json ./

# Install dependencies
RUN npm install

# Copy source
COPY . .

EXPOSE 5173

# Vite must bind to 0.0.0.0 to be reachable from outside the container.
# VITE_API_BASE_URL is injected at runtime via docker-compose env_file.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
