FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install --no-cache-dir poetry==2.3.3

# Copy dependency files first (layer caching)
COPY pyproject.toml poetry.lock tracing.yaml ./

# Read OTEL_DESTINATION from tracing.yaml and install matching Poetry extras.
# Each backend has its own optional extra with the vendor/exporter packages.
RUN poetry config virtualenvs.create false && \
    DEST=$(grep -m1 '^OTEL_DESTINATION:' tracing.yaml | awk '{print $2}' | tr -d '[:space:]') && \
    DEST=${DEST:-phoenix} && \
    echo "[TravelShaper] Build: OTEL_DESTINATION=$DEST" && \
    if [ "$DEST" = "phoenix" ]; then \
        poetry install --no-interaction --no-ansi --no-root -E phoenix; \
    elif [ "$DEST" = "arize" ]; then \
        poetry install --no-interaction --no-ansi --no-root -E arize; \
    elif [ "$DEST" = "custom" ]; then \
        poetry install --no-interaction --no-ansi --no-root -E custom; \
    else \
        poetry install --no-interaction --no-ansi --no-root; \
    fi

# Copy application code
COPY . .

# Ensure static directory exists (serves the browser chat UI)
RUN mkdir -p /app/static

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
