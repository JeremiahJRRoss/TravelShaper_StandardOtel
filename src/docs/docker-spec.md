# Docker Specification — TravelShaper Travel Assistant

**Version:** 3.0 (v0.3.0)

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

# Ensure runtime directories exist
# - /app/static serves the browser chat UI
# - /app/logs holds the structured JSON log file tailed by the Observe Agent
RUN mkdir -p /app/static /app/logs

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
      - TRACELOOP_BASE_URL=${TRACELOOP_BASE_URL:-http://localhost:4318}
      - TRACELOOP_TRACE_CONTENT=${TRACELOOP_TRACE_CONTENT:-true}
      - OTEL_RESOURCE_ATTRIBUTES=${OTEL_RESOURCE_ATTRIBUTES:-service.name=travelshaper,service.version=0.3.0}
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped
```

The compose file defines a single `travelshaper` service. The Observe Agent is
**not** a compose service — it runs on the host and is managed by the operator.
Spans are exported via OTLP HTTP to `TRACELOOP_BASE_URL` (default
`http://localhost:4318`) where the Observe Agent receives them and forwards to
Observe. Structured JSON logs are written to `/app/logs/travelshaper.log` inside
the container; the bind mount `./logs:/app/logs` exposes that file on the host
so the Observe Agent's filelog receiver can tail it.

---

## Notes

**Why `poetry.lock` is committed and copied into the container:**
The lockfile pins exact versions of every dependency and their transitive deps,
ensuring reproducible builds across environments.

**Tracing dependency (`traceloop-sdk`):**
Traceloop SDK (OpenLLMetry) is a regular Poetry dependency in `pyproject.toml`.
It auto-instruments LangChain/LangGraph and the OpenAI SDK and exports OTLP
HTTP spans to the Observe Agent. No Phoenix or Arize packages are installed.

**Observe Agent runs outside docker-compose:**
The Observe Agent is operator-managed on the host. It listens on the OTLP HTTP
port for Traceloop spans and tails `./logs/travelshaper.log` via its filelog
receiver. Keeping it out of compose lets a single agent serve multiple
applications and matches Observe's recommended deployment model.

**Why `openai` is an explicit dependency:**
The `openai` SDK is a transitive dependency of `langchain-openai`. It is
listed explicitly in `pyproject.toml` to pin a compatible version. `api.py`
does not import the `openai` SDK directly — all LLM calls go through
LangChain's `ChatOpenAI`.

**The `temperature` model_kwargs pattern:**
`gpt-5.3-chat-latest` only accepts `temperature=1`. LangChain's `ChatOpenAI` Pydantic
field rejects `None` on older versions, so the workaround is
`model_kwargs={"temperature": 1}`.
