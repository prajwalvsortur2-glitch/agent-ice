# Agent ICE backend image.
#
# Notes:
#   * Ollama is NOT included in this image. Run it as a sidecar (see
#     docker-compose.yml) or on the host.
#   * The image binds to 127.0.0.1 inside the container by default; the
#     compose file publishes it to the host.
#   * No secrets are baked into the image. RECEIPT_SECRET must be supplied
#     at runtime via environment variables.

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Minimal runtime dependencies.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for better layer caching.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application code.
COPY app ./app
COPY policies ./policies
COPY data ./data
COPY scripts ./scripts

# Ensure runtime dirs exist.
RUN mkdir -p /app/logs /app/data/results

# Non-root user.
RUN useradd --create-home --shell /bin/bash agentice \
    && chown -R agentice:agentice /app
USER agentice

EXPOSE 8000

# Healthcheck hits the local /health endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

# Default command runs the API.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]