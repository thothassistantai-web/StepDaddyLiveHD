# StepDaddyLiveHD v2.0 — Modernized Dockerfile
# Python 3.12 + Reflex 0.9.4

FROM python:3.12-slim

# Install system dependencies (including unzip for Bun, curl for healthcheck)
RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
        unzip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies first (for better layer caching)
COPY requirements.txt .
RUN python -m venv /app/.venv && \
    /app/.venv/bin/pip install --no-cache-dir -r requirements.txt

ENV PATH="/app/.venv/bin:$PATH"

# Copy application source
COPY . .

# Initialize Reflex and build frontend
ARG API_URL=http://localhost:3000
ENV REFLEX_API_URL=${API_URL}
RUN reflex init && reflex export --frontend-only

# Create logo cache directory
RUN mkdir -p /app/logo-cache

# Environment variables
ARG PORT=3000
ARG PROXY_CONTENT=TRUE
ARG SOCKS5=""
ARG DLHD_BASE_URL=https://dlhd.pk

ENV PORT=${PORT} \
    API_URL=${API_URL} \
    REFLEX_API_URL=${API_URL} \
    PROXY_CONTENT=${PROXY_CONTENT} \
    SOCKS5=${SOCKS5} \
    DLHD_BASE_URL=${DLHD_BASE_URL} \
    PYTHONUNBUFFERED=1

EXPOSE ${PORT}

# Health check
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Run Reflex (serves both frontend and backend)
CMD exec reflex run --env prod --backend-port ${PORT} --single-port
