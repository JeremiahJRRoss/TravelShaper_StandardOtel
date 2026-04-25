# TravelShaper

**AI travel planning assistant** — fill in a form, get an opinionated briefing with flights, hotels, cultural prep, and activity picks.

Every recommendation includes a hyperlink and an explanation of *why* it was chosen. The agent runs two distinct voices depending on budget mode, and the entire request flow is instrumented with Arize Phoenix for observability.

---

## Before You Begin

TravelShaper needs two things from the outside world: an OpenAI key to think with, and a SerpAPI key to search with. Everything else — the agent, the tools, the UI, the tracing stack — lives inside the project. Getting these keys configured correctly is the single most important step in setup, and the one most likely to cause confusion later if skipped.

### 1. Create your environment file

```bash
cd src
cp .env.example .env
```

Open `.env` in any editor and fill in your keys:

```
OPENAI_API_KEY=sk-...
SERPAPI_API_KEY=...
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

**Where to get keys:**

- **OpenAI** (required) — [platform.openai.com/api-keys](https://platform.openai.com/api-keys). The agent cannot function without this. The validation classifiers in `api.py` also use OpenAI models via LangChain's `ChatOpenAI`.
- **SerpAPI** (required for flights, hotels, and cultural guide) — [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). The free tier provides 250 searches per month, which supports roughly 60–125 full trip briefings. Without this key, the agent falls back to DuckDuckGo for everything — functional, but limited.
- **Phoenix endpoint** — leave the default. It points to the Phoenix container that Docker Compose starts automatically. Only change this if you are running Phoenix on a different host.

The `.env` file is listed in `.gitignore` and will never be committed. If you see an auth error later, this is the first place to check.

### 2. Trace destination (optional)

Traces are sent to Arize Phoenix by default. To change the destination,
edit `OTEL_DESTINATION` in `src/tracing.yaml`:

**Phoenix (local dev — default, no changes needed):**
```yaml
OTEL_DESTINATION: phoenix
```

**Arize AX (cloud):**
```yaml
OTEL_DESTINATION: arize
```
Then set `ARIZE_SPACE_ID` and `ARIZE_API_KEY` in your `.env` file.
Get credentials from [app.arize.com/account/api-keys](https://app.arize.com/account/api-keys).

**Custom OTLP (Cribl, Honeycomb, Grafana, Datadog, etc.):**
```yaml
OTEL_DESTINATION: custom
```
Then set `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_AUTH_TOKEN` in `.env`.

After changing `tracing.yaml`, rebuild: `docker compose build && docker compose up -d`

---

## Choose How to Run

There are two ways to run TravelShaper. Pick the one that fits your situation — they produce identical results.

### Option A: Docker Compose (recommended)

This is the fastest path. Docker handles Python versions, dependencies, and Phoenix in one command. You do not need a virtual environment.

```bash
cd src
chmod +x setup.sh
./setup.sh
```

The setup script checks prerequisites (it detects both `docker compose` v2 and legacy `docker-compose`), prompts for API keys if `.env` does not exist yet, builds the containers, and starts both services. When it finishes:

| Service | URL |
|---------|-----|
| TravelShaper (app + API) | [http://localhost:8000](http://localhost:8000) |
| Phoenix (tracing UI) | [http://localhost:6006](http://localhost:6006) |

To stop everything:

```bash
docker compose down
# or, if using legacy Docker Compose:
docker-compose down
```

To rebuild after code changes (Docker caches aggressively — this ensures fresh containers):

```bash
docker compose build --no-cache
docker compose up -d
```

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

**Phoenix tracing** (optional in venv mode): the tracing client packages
(`arize-phoenix-otel`, `openinference-instrumentation-langchain`) are included
in `pyproject.toml` and installed by `poetry install`. To run the Phoenix
server and evaluations locally, also install:

```bash
pip install arize-phoenix arize-phoenix-evals
```

You will also need to run the Phoenix server separately. The simplest way is Docker:

```bash
docker run -p 6006:6006 arizephoenix/phoenix:latest
```

---

## Running Tests

Here is the thing about the tests that matters most: they are entirely self-contained. All 14 tests use mocked external calls. They do not need API keys, a running server, or Docker. They need only the right Python packages available to import.

The principle is simple: every command that runs Python code should execute inside either a container or an activated virtual environment. Never bare system Python.

### If you are using a local virtual environment

Run tests in the same venv where you installed dependencies:

```bash
cd src
source .venv/bin/activate
pytest tests/ -v
```

### If you are using Docker

The `docker-compose.yml` does not include a dedicated test service, so you run pytest inside the existing `travelshaper` container:

```bash
cd src
docker compose exec travelshaper pytest tests/ -v
```

If the container is not already running, start it first with `docker compose up -d`, then run the command above.

Expected output: **14 tests passing**.

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
locally and best-effort synced to Phoenix.

```bash
curl -s -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"run_id": "your-run-id-here", "score": 1, "comment": "Great trip plan!"}'
```

**`GET /health`** — Returns `{"status": "ok"}`. Used by Docker's health check and useful for verifying the server is alive.

---

## Running Traces and Evaluations

Traces are generated by running real queries against the live API. Do this after starting the full Docker Compose stack (or after starting both the app and Phoenix in venv mode).

### Generate traces

The trace script must be run from within the `src/` directory, since it calls Python modules with relative imports:

```bash
cd src
chmod +x run_traces.sh
./run_traces.sh
```

This fires 11 queries covering every tool combination, both budget voices, auto-correction, vague inputs, past-date error handling, and edge cases. All dates in the queries are computed dynamically relative to today, so the script never goes stale. Each query generates a trace visible in Phoenix at [http://localhost:6006](http://localhost:6006).

You can optionally pass a custom base URL:

```bash
./run_traces.sh http://localhost:8000
```

### Run evaluations

```bash
cd src
python -m evaluations.run_evals
```

This runs three LLM-as-judge metrics against the collected traces:

- **User Frustration** — uses Phoenix's built-in `USER_FRUSTRATION_PROMPT_TEMPLATE` (the `frustration.py` file in `evaluations/metrics/` contains a custom reference prompt but it is not used in production)
- **Tool Usage Correctness** — custom LLM-as-judge prompt
- **Answer Completeness** — custom LLM-as-judge prompt with scope awareness

Results are logged back to Phoenix and visible in the Evaluations tab. A `frustrated_interactions` dataset is automatically created from any traces flagged as frustrated.

See [docs/trace-queries.md](src/docs/trace-queries.md) for the full query list and [docs/evaluation-prompts.md](src/docs/evaluation-prompts.md) for evaluation methodology.

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
├── evaluations/
│   ├── run_evals.py                # Phoenix evaluation runner (3 metrics)
│   └── metrics/
│       ├── frustration.py          # Reference frustration prompt (production uses Phoenix built-in)
│       ├── answer_completeness.py  # ANSWER_COMPLETENESS_PROMPT
│       └── tool_correctness.py     # TOOL_CORRECTNESS_PROMPT
├── scripts/
│   ├── export_spans.py             # Export Phoenix spans to CSV
│   └── sync_feedback.py            # Batch-sync feedback.jsonl → Phoenix annotations
├── tests/
│   ├── test_tools.py               # 4 tool tests
│   ├── test_agent.py               # 2 agent graph tests
│   └── test_api.py                 # 18 endpoint, validation, and feedback tests
├── docs/
│   ├── ARCHITECTURE.md
│   ├── PRD.md
│   ├── system-prompt-spec.md
│   ├── test-specification.md
│   ├── docker-spec.md
│   ├── evaluation-prompts.md
│   ├── trace-queries.md
│   ├── implementation-plan.md
│   └── presentation-outline.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── run_traces.sh                   # 11 trace queries + span export
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
- **All tracing through LangChain instrumentation** — only `agent.py._init_tracing()` imports OTEL packages. `api.py` uses `RunnableConfig` metadata to tag request-level attributes (destination, departure, budget mode) which the LangChain instrumentor propagates to all child spans. Swapping trace backends (e.g., LangSmith, Datadog) means changing one function.
- **Validation classifiers use LangChain `ChatOpenAI`** — the place and preference validators in `api.py` call `gpt-4o` through `langchain-openai` rather than the raw OpenAI SDK. This makes validation LLM calls visible in Phoenix traces alongside agent spans.

---

## Known Limitations

- Planning assistant only — recommends options but does not book.
- Flight and hotel prices reflect time of search, not guaranteed availability.
- Cultural guidance is practical advice based on common norms, not absolute rules.
- Designed for English-speaking American travellers; guidance assumes U.S. norms as baseline.
- Single-turn: no conversation memory between requests.
- SerpAPI free tier supports ~60–125 full briefings per month.
- Voice routing uses keyword matching — the budget voice triggers on `save money`, `budget`, `cheapest`, or `spend as little` appearing in the message. Synonyms like "frugal" or "inexpensive" will not trigger it and will default to the full-experience voice.

---

## Troubleshooting

**Server won't start** — confirm your `.env` exists with valid keys. If running locally, confirm the venv is activated and you have run `poetry install -E dev`. If running Docker, try `docker compose build --no-cache`.

**Auth error from OpenAI or SerpAPI** — check your `.env` file. Verify the SerpAPI key at [serpapi.com/manage-api-key](https://serpapi.com/manage-api-key). Verify the OpenAI key at [platform.openai.com/api-keys](https://platform.openai.com/api-keys).

**Tests fail with ModuleNotFoundError** — you are running pytest outside of an isolated environment. Either activate your venv (`source .venv/bin/activate`) or run tests inside the Docker container (`docker compose exec travelshaper pytest tests/ -v`). Confirm that `pyproject.toml` contains `[tool.pytest.ini_options]` with `pythonpath = ["."]`.

**Poor or incomplete results** — include origin, destination, dates, and budget in your request. Check SerpAPI usage (free tier: 250 searches/month). Try well-known destinations first.

**Finding traces in Phoenix** — Set `TRAVELSHAPER_DEBUG=true` in your `.env` file. The `/chat` response will include a `debug.trace_url` that links directly to the trace in Phoenix. For SSE streaming, the `done` event includes a `run_id` you can search for in the Phoenix UI.

**Missing traces in Phoenix** — confirm Phoenix is running. If using Docker Compose, both services start together. If using a venv, you need to start Phoenix separately. Run at least one `/chat` query, then refresh the Phoenix UI at [http://localhost:6006](http://localhost:6006).

**`ModuleNotFoundError: No module named 'phoenix'`** — the tracing client packages are installed by `poetry install`. If you need the full Phoenix server locally, install it with: `pip install arize-phoenix arize-phoenix-evals`. In Docker mode, Phoenix runs in its own container.

**`run_traces.sh` fails with import errors** — make sure you are running the script from inside the `src/` directory. The script calls `python3 -m scripts.export_spans` and `python3 -m evaluations.run_evals`, which require `src/` as the working directory for Python's module resolution to work.

---

MIT License — see [LICENSE](LICENSE).
