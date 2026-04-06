# ─── Stage 1: Build React frontend ──────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend/ .
RUN npm run build

# ─── Stage 2: Runtime (Python + nginx + supervisord) ─────────────────────────
FROM python:3.12-slim

# System packages: nginx for static serving + API proxy, supervisor to manage processes
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    supervisor \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv (provides both `uv` and `uvx` binaries)
RUN pip install --no-cache-dir uv

WORKDIR /app

# Step 1: install all *dependencies* (no local package yet) — this layer is
# cached as long as pyproject.toml / uv.lock don't change, even if src/ does.
# README.md is required by hatchling (listed as readme in pyproject.toml).
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Step 2: copy source, then install the local package into the same venv
COPY src/ src/
RUN uv sync --frozen --no-dev

# Pre-fetch brandvoice-mcp so `uvx brandvoice-mcp` works offline at runtime
RUN uv tool install brandvoice-mcp

# ── Static frontend ──────────────────────────────────────────────────────────
COPY --from=frontend-builder /app/frontend/dist /usr/share/nginx/html

# ── nginx config ─────────────────────────────────────────────────────────────
COPY nginx.conf /etc/nginx/sites-available/default
RUN rm -f /etc/nginx/sites-enabled/default \
 && ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default

# ── supervisord config ───────────────────────────────────────────────────────
COPY supervisord.conf /etc/supervisor/conf.d/app.conf

# Persistent data directory for SQLite (mount a volume here in production)
RUN mkdir -p /data && chmod 755 /data

EXPOSE 80

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
