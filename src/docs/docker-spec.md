# Docker Specification — TravelShaper Travel Assistant

**Version:** 2.3 (v0.2.3)

---

## Dockerfile

```dockerfile
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
COPY pyproject.toml poetry.lock ./

# Install Python dependencies (no virtualenv inside container)
# poetry.lock ensures reproducible builds with exact pinned versions.
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

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
```

### Build and run

```bash
# Force clean rebuild (recommended after code changes)
docker compose down
docker compose build --no-cache
docker compose up -d
```

> **Important:** Always use `--no-cache` after modifying Python files.

---

## docker-compose.yml

```yaml
services:
  travelshaper:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      - PHOENIX_COLLECTOR_ENDPOINT=http://phoenix:6006/v1/traces
      - ARIZE_SPACE_ID=${ARIZE_SPACE_ID:-}
      - ARIZE_API_KEY=${ARIZE_API_KEY:-}
      - ARIZE_PROJECT_NAME=${ARIZE_PROJECT_NAME:-travelshaper}
      - ARIZE_ENDPOINT=${ARIZE_ENDPOINT:-}
    depends_on:
      phoenix:
        condition: service_started
    restart: unless-stopped

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
    restart: unless-stopped
```

---

## Notes

**Why `poetry.lock` is committed and copied into the container:**
The lockfile pins exact versions of every dependency and their transitive deps,
ensuring reproducible builds across environments.

**Phoenix tracing packages (`arize-phoenix-otel`, `openinference-instrumentation-langchain`):**
These are regular Poetry dependencies in `pyproject.toml` (with a `python = ">=3.11,<3.15"`
marker to satisfy the upstream Python version constraint).

**Why `arize-phoenix` (the full server) is NOT installed in this container:**
The full Phoenix server package would conflict with TravelShaper's FastAPI version.
Phoenix runs in its own container (`arizephoenix/phoenix:latest`).

**Why `openai` is an explicit dependency:**
The `openai` SDK is a transitive dependency of `langchain-openai`. It is
listed explicitly in `pyproject.toml` to pin a compatible version. `api.py`
does not import the `openai` SDK directly — all LLM calls go through
LangChain's `ChatOpenAI`.

**The `temperature` model_kwargs pattern:**
`gpt-5.3-chat-latest` only accepts `temperature=1`. LangChain's `ChatOpenAI` Pydantic
field rejects `None` on older versions, so the workaround is
`model_kwargs={"temperature": 1}`.
