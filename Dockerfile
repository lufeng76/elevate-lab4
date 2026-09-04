# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Install security updates and curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv

# Copy project definition and lockfile
COPY pyproject.toml uv.lock* ./

# Install dependencies into system environment using uv
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy application source code and knowledge bundle
COPY agent/ ./agent/
COPY knowledge/ ./knowledge/
COPY evals/ ./evals/
COPY HR_Agentic_Solution_SDD.md ./
COPY .env.example ./

# Security: Create and switch to non-privileged application user
RUN useradd -u 10001 -m -s /bin/bash appuser && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/healthz || exit 1

CMD ["python", "-m", "agent.server"]
