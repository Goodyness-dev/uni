# Multi-stage production Dockerfile for ScholarPilot
FROM python:3.12-slim-bookworm AS builder

WORKDIR /build

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install python wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt


# Final runtime stage
FROM python:3.12-slim-bookworm AS runner

WORKDIR /app

# Install runtime dependencies for PostgreSQL and Playwright Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    ca-certificates \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed wheels from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install Playwright browser binaries
RUN python -m playwright install --with-deps chromium || true

# Copy application code
COPY app/ /app/app/
COPY scripts/ /app/scripts/
COPY backend/data/listings.json /app/backend/data/listings.json
COPY alembic.ini /app/alembic.ini

# Create non-root user and runtime directories
RUN useradd -m -u 1000 scholarpilot && \
    mkdir -p /app/storage/screenshots && \
    chown -R scholarpilot:scholarpilot /app

USER scholarpilot

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start FastAPI application server
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
