# TravelShaper — Running & Testing Guide

> **Note:** The main README.md is the primary reference. This guide provides extended detail for specific workflows.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.11+ | Required |
| pip | Any recent | Comes with Python |
| Docker + Docker Compose | Any recent | For containerised run |
| OpenAI API key | — | Required for the agent |
| SerpAPI key | — | Required for flights/hotels/cultural guide |

---

## 1. Local Setup

### 1a. Clone / unzip the project

```bash
cd travelshaper/src
```

### 1b. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
# .venv\Scripts\activate         # Windows
```

### 1c. Install Poetry inside the venv

```bash
pip install --upgrade pip
pip install poetry==1.8.2
```

### 1d. Install project dependencies

```bash
# Runtime only
poetry install

# Or, with the test runner
poetry install -E dev
```

The Traceloop SDK (OpenLLMetry) and its LangChain auto-instrumentation are
declared in `pyproject.toml` and installed automatically. The previous
optional extras (`phoenix`, `arize`, `custom`) are gone.

### 1e. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys. Tracing is configured via
`TRACELOOP_BASE_URL` (default `http://localhost:4318`), which points at
the host-side **Observe Agent** OTLP/HTTP receiver.

---

## 2. Running the API Server

### Option A — Local (venv)

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### Option B — Docker or Podman Compose

`docker-compose.yml` defines a single `travelshaper` service and is
OCI-compliant, so it runs unchanged under either Docker or Podman. The
Observe Agent runs on the **host** (not in compose) and is user-managed.
The container bind-mounts `./logs:/app/logs` so the host-side Observe Agent
can tail `/app/logs/travelshaper.log` (structured JSON).

```bash
docker compose up --build
# or, on Podman:
podman compose up --build
```

| Service | URL |
|---------|-----|
| TravelShaper API | http://localhost:8000 |

Traces are exported via OTLP/HTTP to `TRACELOOP_BASE_URL` and surface in
**Observe** — there is no local tracing UI.

### Option C — One-command setup

`setup.sh` auto-detects whichever runtime is installed (`docker` first,
then `podman`) and the matching compose CLI (v2 plugin first, standalone
fallback). No flags needed.

```bash
chmod +x setup.sh
./setup.sh
```

#### Installing Podman

If you do not already have Docker, Podman is a daemonless drop-in. See the
top-level [`README.md`](../../README.md#installing-podman-as-an-alternative-to-docker)
for the full notes (including the Linux `host.docker.internal` workaround).
Quick reference:

- **macOS:** `brew install podman && podman machine init && podman machine start`
- **Debian / Ubuntu:** `sudo apt install -y podman podman-compose`
- **Fedora / RHEL:** `sudo dnf install -y podman podman-compose`
- **Windows:** [Podman Desktop](https://podman.io/) or `winget install RedHat.Podman`, then `podman machine init && podman machine start`

---

## 3. Running the Tests

### Run the unit suite (recommended)

```bash
pytest tests/ -v
```

The unit suite (~22-24 tests) covers agent structure, API/validation,
tool behaviour, and Traceloop SDK initialisation.

> **No API keys are required to run tests.** All external calls are mocked.

---

## 4. Generating Traces

### Run all 11 trace queries automatically

```bash
chmod +x run_traces.sh
./run_traces.sh
```

The script runs 11 queries covering every tool combination, both budget voices, place auto-correction, past-date error handling, and edge cases. All dates are computed dynamically relative to today.

The Traceloop SDK exports OTLP/HTTP spans to `TRACELOOP_BASE_URL` (the
host's Observe Agent on `:4318` by default), which forwards them — along
with tailed structured logs — to **Observe cloud**. View results in your
Observe workspace.

---

## 5. Evaluations

The previous in-repo eval pipeline (`evaluations/`) and the Phoenix-only
helper scripts (`scripts/export_spans.py`, `scripts/sync_feedback.py`)
were removed during the Observe migration. The judge prompts that powered
those metrics are preserved as reference material in
[`docs/evaluation-prompts.md`](evaluation-prompts.md), to be re-used
inside Observe (Monitors / LLM-as-judge) or any external eval harness.

---

## 6. Interactive API Docs

| Page | URL |
|------|-----|
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |

---

## 7. Project Structure Reference

```
src/
├── agent.py                        # LangGraph agent — dual system prompts, voice routing
├── api.py                          # FastAPI server (POST /chat, /chat/stream, GET /health)
├── static/
│   └── index.html                  # Browser chat UI
├── tools/
│   ├── __init__.py                 # SerpAPI helper (serpapi_request)
│   ├── flights.py                  # search_flights tool
│   ├── hotels.py                   # search_hotels tool
│   └── cultural_guide.py          # get_cultural_guide tool
├── tests/
│   ├── test_tools.py               # tool unit tests (mocked)
│   ├── test_agent.py               # agent structure tests
│   ├── test_api.py                 # API endpoint + validation tests
│   └── test_traceloop.py           # Traceloop SDK initialisation test
├── docs/
│   └── evaluation-prompts.md       # Reference judge prompts (post-migration)
├── logs/                           # Bind-mounted into Docker as /app/logs
│   └── travelshaper.log            # Structured JSON; tailed by Observe Agent
├── run_traces.sh                   # 11 trace queries to drive trace generation
├── setup.sh                        # One-command setup (Docker path)
├── Dockerfile                      # Container build
├── docker-compose.yml              # Single-service compose (Observe Agent runs on host)
├── pyproject.toml                  # Dependencies (Traceloop SDK, no extras)
└── .env.example                    # Environment variable template
```

---

## 8. Troubleshooting

**`SERPAPI_API_KEY is not set` error**
Copy `.env.example` to `.env` and add your SerpAPI key, then restart.

**`OPENAI_API_KEY` auth error**
Check your `.env` file.

**Tests fail to collect**
Make sure you are running from `src/` with the venv active. Then run `pytest tests/ -v`.

**No traces in Observe**
Traces are only generated when real queries hit the live API. Confirm the
**Observe Agent** is running on the host and listening on OTLP/HTTP
`:4318`, that `TRACELOOP_BASE_URL` matches, and then run `./run_traces.sh`
against the live server.

**No logs reaching Observe**
Check that `./logs/travelshaper.log` is being written (the app logs
structured JSON there) and that the Observe Agent is configured to tail
that file. In Docker, the host directory `./logs` is bind-mounted to
`/app/logs` inside the container.
