FROM python:3.11-slim

# Set working directory (also where setup.sh's ./logs bind-mount lands)
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create the runtime user. Fixed UID/GID 1000 so host-side bind-mount
# permissions are predictable: chown ./logs to 1000:1000 on the host and
# the container can write its JSON log file straight to it.
RUN groupadd --system --gid 1000 travelshaper \
    && useradd  --system --uid 1000 --gid travelshaper \
                --home-dir /app --shell /sbin/nologin travelshaper

# Install Poetry (still as root — Poetry installs system-wide)
RUN pip install --no-cache-dir poetry==2.3.3

# Copy dependency files first (layer caching)
COPY pyproject.toml poetry.lock ./

# Install dependencies. Tracing is provided by the traceloop-sdk regular
# dependency — no conditional extras needed.
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy application code, then make sure the runtime user owns everything
# under WORKDIR (including the static and logs directories created below).
COPY . .
RUN mkdir -p /app/static /app/logs && \
    chown -R travelshaper:travelshaper /app

# Drop privileges for the rest of the container's lifetime.
USER travelshaper

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the API server
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
