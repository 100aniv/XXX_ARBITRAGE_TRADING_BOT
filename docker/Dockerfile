# ============================================================================
# Arbitrage Trading Engine - Production Dockerfile
# Multi-stage build for optimized image size
# ============================================================================

# ============================================================================
# Stage 1: Builder
# ============================================================================
FROM python:3.10-slim as builder

LABEL maintainer="arbitrage-dev"
LABEL description="Arbitrage Trading Engine - Builder Stage"

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY requirements.txt .
COPY poetry.lock* pyproject.toml* ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ============================================================================
# Stage 2: Runtime
# ============================================================================
FROM python:3.10-slim

LABEL maintainer="arbitrage-dev"
LABEL description="Arbitrage Trading Engine - Production Runtime"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ENV=production

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r arbitrage && \
    useradd -r -g arbitrage -u 1000 -s /bin/bash arbitrage

# Set working directory
WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY --chown=arbitrage:arbitrage . /app

# Create necessary directories
RUN mkdir -p /app/logs /app/tmp && \
    chown -R arbitrage:arbitrage /app

# Switch to non-root user
USER arbitrage

# Expose ports (if needed for future HTTP/metrics endpoints)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python healthcheck.py || exit 1

# Entrypoint
ENTRYPOINT ["/app/docker/entrypoint.sh"]

# Default command
CMD ["python", "-m", "arbitrage.live_runner"]
