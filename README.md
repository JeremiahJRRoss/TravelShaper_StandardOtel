# TravelShaper

**AI travel planning assistant** — fill in a form, get an opinionated briefing with flights, hotels, cultural prep, and activity picks.

Every recommendation includes a hyperlink and an explanation of *why* it was chosen. The agent runs two distinct voices depending on budget mode, and the entire request flow is instrumented via the Traceloop SDK (OpenLLMetry) and forwarded to Observe through the Observe Agent.

---

## Before You Begin

TravelShaper needs two things from the outside world: an OpenAI key to think with, and a SerpAPI key to search with. Everything else — the agent, the tools, the UI — lives inside the project. Tracing is optional: if no collector is configured, spans are silently dropped and the app continues to serve requests.

### 1. Create your environment file

```bash
cd src
cp .env.example .env
```

Open `.env` in any editor and fill in your keys:

```
OPENAI_API_KEY=sk-...
SERPAPI_API_KEY=...
TRACELOOP_BASE_URL=http://localhost:4318
```

**Where to get keys:**

- **OpenAI** (required) — [platform.openai.com/api-keys](https://platform.openai.com/api-keys). The agent cannot function without this. The validation classifiers in `api.py` also use OpenAI models via LangChain's `ChatOpenAI`.
- **SerpAPI** (required for flights, hotels, and cultural guide) — [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). The free tier provides 250 searches per month, which supports roughly 60–125 full trip briefings. Without this key, the agent falls back to DuckDuckGo for everything — functional, but limited.
- **`TRACELOOP_BASE_URL`** — points at the OTLP HTTP endpoint of an Observe Agent (default `localhost:4318`). Leave the default if you are running an Observe Agent on the host. Inside Docker the compose file rewrites this to `host.docker.internal:4318`.

The `.env` file is listed in `.gitignore` and will never be committed. If you see an auth error later, this is the first place to check.

### 2. Observe Agent (optional)

TravelShaper exports two telemetry signals to the [Observe
Agent](https://docs.observeinc.com/) running on your host:

- **OTLP traces** on `localhost:4318` (HTTP) — emitted by the Traceloop SDK
- **Structured JSON logs** in `./logs/travelshaper.log` — written by the
  Python `logging` module and tailed by the Observe Agent's filelog receiver

Configure infrastructure-level resource attributes (`deployment.environment`,
`host.name`, cluster IDs, etc.) in the agent's resource processor — the app
only sets `service.name` and `service.version`. This means the same image
runs in dev, staging, and prod without rebuilding.

If you do not run an Observe Agent, traces are dropped harmlessly and the
log file simply accumulates on disk.

---

## Choose How to Run

There are two main ways to run TravelShaper. Pick the one that fits your situation — they produce identical results.

### Option A: Docker or Podman Compose (recommended)

This is the fastest path. The container runtime handles Python versions and dependencies in one command — you do not need a virtual environment. TravelShaper's `Dockerfile` and `docker-compose.yml` are OCI-compliant, so they work unchanged with either Docker or Podman; `setup.sh` auto-detects whichever runtime is installed.

```bash
cd src
chmod +x setup.sh
./setup.sh
```

The setup script picks Docker first, falls back to Podman, then probes for the matching compose CLI (`docker compose` v2 → `docker-compose` → `podman compose` → `podman-compose`). It prompts for API keys if `.env` does not exist yet, builds the container, and starts the service. When it finishes:

| Service | URL |
|---------|-----|
| TravelShaper (app + API) | [http://localhost:8000](http://localhost:8000) |

The Observe Agent runs on the host (or as a separate sidecar) and is **not** managed by compose. The compose file bind-mounts `./logs:/app/logs` so the agent's filelog receiver can tail `travelshaper.log` from outside the container.

To stop everything:

```bash
docker compose down
# or, on Podman:
podman compose down
# or, with the legacy standalone tools:
docker-compose down
podman-compose down
```

To rebuild after code changes (container layers cache aggressively — this ensures fresh containers):

```bash
docker compose build --no-cache && docker compose up -d
# or, on Podman:
podman compose build --no-cache && podman compose up -d
```

#### Installing Podman as an alternative to Docker

Podman is a daemonless, drop-in alternative to Docker. Install it once for your platform, then `setup.sh` will detect and use it automatically.

- **macOS (Homebrew):**
  ```bash
  brew install podman
  podman machine init
  podman machine start
  ```
- **Linux (Debian / Ubuntu):**
  ```bash
  sudo apt update
  sudo apt install -y podman podman-compose
  ```
- **Linux (Fedora / RHEL / Rocky):**
  ```bash
  sudo dnf install -y podman podman-compose
  ```
- **Windows:** install [Podman Desktop](https://podman.io/) or run `winget install RedHat.Podman`, then:
  ```powershell
  podman machine init
  podman machine start
  ```

If you prefer to skip `setup.sh`, the equivalent manual sequence is:

```bash
cd src
cp .env.example .env   # then fill in your API keys
podman compose build
podman compose up -d
```

> **Linux Podman gotcha:** the compose file points `TRACELOOP_BASE_URL` at `host.docker.internal:4318`, which Mac/Windows resolve automatically but Linux does not. Either override the URL in `.env` to your host's IP, or start the stack with an explicit alias: `podman compose --add-host host.docker.internal:host-gateway up -d`.

### Option B: Local virtual environment

Use this if you prefer working outside Docker, want hot-reload during development, or need to debug with local tools. A virtual environment is required — do not install into your system Python.

```bash
cd src
python3 -m venv .venv
source .venv/bin/activate       # macOS / Linux
# .venv\Scripts\activate        # Windows
pip install --upgrade pip
pip install poetry==1.8.2
poetry install -E dev
```

Start the server:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The app is now running at [http://localhost:8000](http://localhost:8000).

**Tracing** (optional in venv mode): the Traceloop SDK is a regular
dependency installed by `poetry install`. With `TRACELOOP_BASE_URL`
pointing at a running Observe Agent on `localhost:4318`, spans are
exported automatically. With nothing listening on that port, the SDK
buffers and drops spans without affecting the request path.

---

## Running Tests

Here is the thing about the tests that matters most: they are entirely self-contained. Every test uses mocked external calls — no API keys, running server, or Docker required. They need only the right Python packages available to import.

The principle is simple: every command that runs Python code should execute inside either a container or an activated virtual environment. Never bare system Python.

### If you are using a local virtual environment

Run tests in the same venv where you installed dependencies:

```bash
cd src
source .venv/bin/activate
pytest tests/ -v
```

### If you are using Docker or Podman

The compose file does not include a dedicated test service, so you run pytest inside the existing `travelshaper` container:

```bash
cd src
docker compose exec travelshaper pytest tests/ -v
# or, on Podman:
podman compose exec travelshaper pytest tests/ -v
```

If the container is not already running, start it first with `docker compose up -d` (or `podman compose up -d`), then run the command above.

Expected output: a passing run of the unit suite (no live network calls).

---

## What It Does

TravelShaper takes a departure city, destination, dates, budget preference, and interests, then dispatches four tools to gather live data:

- **search_flights** — Google Flights via SerpAPI (prices, airlines, layovers)
- **search_hotels** — Google Hotels via SerpAPI (rates, ratings, amenities)
- **get_cultural_guide** — scoped Google search for etiquette, language, dress code
- **duckduckgo_search** — open web search for interests and gaps (no key needed)

It synthesises the results into a single briefing covering getting there, where to stay, cultural prep, and what to do — tailored to your budget mode and selected interests.

The agent runs two distinct voices depending on budget mode. "Save money" activates a Bourdain / Billy Dee Williams / Gladwell voice — muscular prose, insider knowledge, budget as philosophy. "Full experience" activates a Robin Leach / Pharrell / Rushdie voice — theatrical, joyful, literary. Both are instructed to include a markdown hyperlink for every named place, hotel, restaurant, and attraction.

Voice routing works by keyword matching on the assembled message string. The browser UI always includes the exact phrase "save money" or "full experience" in the message it constructs, so routing is reliable from the form. When using curl or the API directly, include one of these keywords in your message: `save money`, `budget`, `cheapest`, or `spend as little` to trigger the budget voice. Any message without these keywords defaults to the full-experience voice.

---

## API Endpoints

**`GET /`** — Browser UI. Open [http://localhost:8000](http://localhost:8000) in any browser. No curl required.

**`POST /chat`** — Synchronous chat. Returns the full JSON response when the agent finishes. Useful for curl, scripts, and tests. The response includes `usage` (token counts, estimated cost, per-model breakdown) and `timing` (validation/agent/total latency in ms, SLA status).

The request body accepts four fields: `message` (required), plus optional `departure`, `destination`, and `preferences`. When `departure` and `destination` are provided, gpt-4o validates them as real places before the agent runs — correcting misspellings and rejecting fictional names. When they are omitted, place validation is skipped and the agent receives the message as-is.

```bash
# Full request with place validation:
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Plan a trip from NYC to Rome, September, save money, food and history.",
    "departure": "NYC",
    "destination": "Rome"
  }' | python3 -m json.tool

# Minimal request (no place validation):
curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Plan a trip from NYC to Rome, September, save money, food and history."}' \
  | python3 -m json.tool
```

**`POST /chat/stream`** — SSE streaming. Same request body as `/chat`. The browser UI uses this to show real-time status updates as each tool executes. Emits `status`, `place_corrected`, `place_error`, `validation_error`, `done`, and `error` event types. The `done` event payload includes `usage` and `timing` fields matching the `/chat` response.

**`POST /feedback`** — Submit user feedback on a briefing. Requires `run_id`
(from the `/chat` response or SSE `done` event) and `score` (1 or -1).
Optional `session_id` and `comment` (max 1000 chars). Feedback is stored
locally as JSONL. The legacy `synced_to_phoenix` field in the response is
preserved for the UI but is always `false` — Observe-side annotation will
need to be reimplemented post-migration.

```bash
curl -s -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"run_id": "your-run-id-here", "score": 1, "comment": "Great trip plan!"}'
```

**`GET /health`** — Returns `{"status": "ok"}`. Used by Docker's health check and useful for verifying the server is alive.

---

## Running Traces

Traces are generated by running real queries against the live API. Do this after starting the Docker Compose stack (or the app in venv mode) with an Observe Agent listening on `localhost:4318`.

### Generate traces

```bash
cd src
chmod +x run_traces.sh
./run_traces.sh
```

This fires 11 queries covering every tool combination, both budget voices, auto-correction, vague inputs, past-date error handling, and edge cases. All dates in the queries are computed dynamically relative to today, so the script never goes stale. Each query produces a trace that the Observe Agent forwards to your Observe workspace.

You can optionally pass a custom base URL:

```bash
./run_traces.sh http://localhost:8000
```

### Evaluations

The Phoenix-based eval pipeline (`User Frustration`, `Tool Usage Correctness`,
`Answer Completeness`) was removed during the Observe migration because it
depended on `phoenix.evals.llm_classify`. The prompts are preserved in
[docs/evaluation-prompts.md](src/docs/evaluation-prompts.md) and can be
reimplemented against Observe's query/dataset features or an external
eval runner.

See [docs/trace-queries.md](src/docs/trace-queries.md) for the full query list.

---

## Project Structure

```
src/
├── api.py                          # FastAPI server — /chat, /chat/stream, /health, static UI
├── agent.py                        # LangGraph agent — dual system prompts, voice routing
├── static/index.html               # Browser UI — Bebas Neue / Cormorant Garamond / DM Sans
├── tools/
│   ├── __init__.py                 # serpapi_request() helper
│   ├── flights.py                  # search_flights (SerpAPI Google Flights)
│   ├── hotels.py                   # search_hotels (SerpAPI Google Hotels)
│   └── cultural_guide.py          # get_cultural_guide (scoped Google search)
├── logging_config.py               # JSON logging + stderr handlers
├── tests/
│   ├── test_tools.py               # tool tests
│   ├── test_agent.py               # agent graph + Traceloop init tests
│   └── test_api.py                 # endpoint, validation, and feedback tests
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PRD.md
│   ├── system-prompt-spec.md
│   ├── test-specification.md
│   ├── docker-spec.md
│   ├── evaluation-prompts.md
│   ├── trace-queries.md
│   └── presentation-outline.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── run_traces.sh                   # 11 trace queries
├── setup.sh                        # One-command setup (Docker path)
├── RUNNING.md                      # Extended setup guide (some sections outdated — prefer this README)
└── CHANGELOG.md
```

---

## Architecture

The agent uses a LangGraph ReAct loop with a voice-routing entry node. The graph topology extends the starter app by adding a `route_and_inject` node at graph entry and registering three new tools.

```
Browser / curl
  │
  ├── POST /chat/stream  (SSE — browser UI)
  └── POST /chat         (sync — curl / tests)
           │
           ▼
     Place + Preference Validation (gpt-4o via ChatOpenAI)
           │
           ▼
     LangGraph Agent
           │
     route_and_inject(message)
           ├── "save money" → Bourdain / Billy Dee / Gladwell system prompt
           └── default     → Leach / Pharrell / Rushdie system prompt
           │
           ▼
     llm_call (gpt-5.3-chat-latest)
           │
           ├── search_flights       (SerpAPI → Google Flights)
           ├── search_hotels        (SerpAPI → Google Hotels)
           ├── get_cultural_guide   (SerpAPI → Google Search)
           └── duckduckgo_search    (DuckDuckGo, no key needed)
           │
     tool_node → llm_call (synthesis)
           │
     SSE stream / JSON response → browser / client
```

Graph topology:

```
START → route_and_inject → llm_call → should_continue?
                                        ├── tool calls present → tool_node → llm_call
                                        └── no tool calls     → END
```

For the full architecture narrative — component design, data flow, LLM decision making, prompt design rationale, deployment topology, and security considerations — see [docs/ARCHITECTURE.md](src/docs/ARCHITECTURE.md).

---

## Design Decisions

There is a pattern in how TravelShaper makes its choices, and the pattern is worth naming: every decision optimises for the shortest path to a working demo that is still architecturally honest.

- **Single HTML file UI** — no npm, no build step; served directly by FastAPI alongside the REST API. The constraint produced a better result: one file that loads instantly and has zero deployment friction.
- **SerpAPI as single data provider** — one key powers flights, hotels, and scoped web searches with structured JSON. The alternative was three separate APIs with three approval processes.
- **Cultural guide as a first-class tool** — etiquette and language prep is what separates a useful travel briefing from a price comparison. Most travel tools skip this entirely.
- **DuckDuckGo as fallback** — covers general queries without requiring an additional API key. Already present in the starter code.
- **Two system prompts, not one** — a single prompt with conditional voice instructions produces blended, inconsistent output. Two separate prompts let the model commit fully to one register.
- **Voice routing as a dedicated graph node** — `route_and_inject` runs once at graph entry to select and inject the system prompt into message state. All subsequent `llm_call` invocations see the prompt already in history — no re-injection needed.
- **Place validation before agent** — gpt-4o catches misspellings and rejects fictional places before the expensive agent runs. A 1-second validation call saves 30 seconds of wasted agent time. Validation only runs when `departure` and `destination` fields are explicitly provided in the request body.
- **Single-turn design** — each request is independent. This is a deliberate product boundary, not a gap.
- **All tracing through the Traceloop SDK (OpenLLMetry)** — `agent.py._init_tracing()` calls `Traceloop.init()`, which auto-instruments LangChain and OpenAI and exports OTLP spans to `TRACELOOP_BASE_URL`. `api.py` calls `Traceloop.set_association_properties()` so session_id, run_id, destination, budget_mode, and prompt_version flow through every span (and power filtering in Observe's LLM Explorer).
- **Validation classifiers use LangChain `ChatOpenAI`** — the place and preference validators in `api.py` call `gpt-4o` through `langchain-openai` rather than the raw OpenAI SDK. Their spans appear alongside the agent's in Observe's trace explorer.
- **Logs and traces correlate via shared trace_id** — Python's `logging` module writes structured JSON records to `/app/logs/travelshaper.log`. The Observe Agent tails the file with its filelog receiver and uses the trace_id key to correlate log entries with their parent traces.

---

## Known Limitations

- Planning assistant only — recommends options but does not book.
- Flight and hotel prices reflect time of search, not guaranteed availability.
- Cultural guidance is practical advice based on common norms, not absolute rules.
- Designed for English-speaking American travellers; guidance assumes U.S. norms as baseline.
- Single-turn: no conversation memory between requests.
- SerpAPI free tier supports ~60–125 full briefings per month.
- Voice routing uses keyword matching — the budget voice triggers on `save money`, `budget`, `cheapest`, or `spend as little` appearing in the message. Synonyms like "frugal" or "inexpensive" will not trigger it and will default to the full-experience voice.
- The automated evaluation pipeline (`evaluations/`) was removed during the Observe migration because it depended on Phoenix's `llm_classify`. Eval prompts are preserved in [docs/evaluation-prompts.md](src/docs/evaluation-prompts.md) and need to be reimplemented against Observe or an external eval runner.
- `/feedback` no longer annotates the originating trace. The endpoint still records to `feedback.jsonl` but `synced_to_phoenix` in the response is always `false`.

---

## Troubleshooting

**Server won't start** — confirm your `.env` exists with valid keys. If running locally, confirm the venv is activated and you have run `poetry install -E dev`. If running Docker, try `docker compose build --no-cache`.

**Auth error from OpenAI or SerpAPI** — check your `.env` file. Verify the SerpAPI key at [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). Verify the OpenAI key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

**Tests fail with ModuleNotFoundError** — you are running pytest outside of an isolated environment. Either activate your venv (`source .venv/bin/activate`) or run tests inside the Docker container (`docker compose exec travelshaper pytest tests/ -v`). Confirm that `pyproject.toml` contains `[tool.pytest.ini_options]` with `pythonpath = ["."]`.

**Poor or incomplete results** — include origin, destination, dates, and budget in your request. Check SerpAPI usage (free tier: 250 searches/month). Try well-known destinations first.

**Finding traces in Observe** — set `TRAVELSHAPER_DEBUG=true` in your `.env`. The `/chat` response includes a `debug.run_id` and a `debug.trace_url` of the form `trace:<run_id>`. Search for that run_id in the Observe Trace Explorer.

**Missing traces in Observe** — confirm an Observe Agent is running on the host with an OTLP receiver on port 4318. Inside Docker, `TRACELOOP_BASE_URL` defaults to `http://host.docker.internal:4318` so traffic crosses the container boundary correctly on Mac/Windows; on Linux you may need to add `--add-host` or run the agent in the same Docker network. Check the agent's logs for ingest activity, then look in the Observe Trace Explorer.

**Missing logs in Observe** — confirm the Observe Agent's filelog receiver is configured to tail `./logs/travelshaper.log` (mounted at `/app/logs/travelshaper.log` inside the container). The file is created lazily on first log write — make at least one request, then check that `./logs/travelshaper.log` exists on the host.

**Podman on Linux: traces never reach the Observe Agent** — root cause is the missing `host.docker.internal` mapping. Two fixes: either (a) override `TRACELOOP_BASE_URL` in `.env` to the host's actual IP (e.g. `http://10.0.2.2:4318` for Podman's default network), or (b) start the stack with the explicit alias: `podman compose --add-host host.docker.internal:host-gateway up -d`.

**`setup.sh` says "no container runtime found"** — install Docker (https://docs.docker.com/get-docker/) or Podman (https://podman.io/docs/installation) and rerun. On macOS Podman also requires `podman machine init && podman machine start` before the script will work.

---

MIT License — see [LICENSE](LICENSE).
