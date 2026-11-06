# SentinelForge Zero-Cost Production Dockerfile
# Optimized for Hugging Face Spaces (Docker Space) & Render Free Tier
FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_MODE=production \
    PORT=7860 \
    HOST=0.0.0.0

# Install minimal OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for caching
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY pyproject.toml .env.example README.md AI_USAGE.md ./
COPY sentinelforge/ ./sentinelforge/
COPY sample_repo/ ./sample_repo/
COPY eval/ ./eval/
COPY tests/ ./tests/

# Create non-root user (UID 1000 required for Hugging Face Spaces)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/.sentinelforge /app/data && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 7860
EXPOSE 8000

# Health check using FastAPI /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-7860}/health || exit 1

# Start FastAPI ASGI server with dynamic port support (works on HF Spaces & Render)
CMD ["sh", "-c", "uvicorn sentinelforge.api.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
