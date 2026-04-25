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
poetry install -E dev
```

#### Phoenix tracing packages (optional — for running the Phoenix server locally)

The tracing client packages (`arize-phoenix-otel`,
`openinference-instrumentation-langchain`) are installed by `poetry install`.
To run the Phoenix server and evaluations locally, also install:

```bash
pip install arize-phoenix arize-phoenix-evals
```

### 1e. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your keys.

---

## 2. Running the API Server

### Option A — Local (venv)

```bash
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

### Option B — Docker Compose (recommended for full stack)

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| TravelShaper API | http://localhost:8000 |
| Phoenix Tracing UI | http://localhost:6006 |

### Option C — One-command setup

```bash
chmod +x setup.sh
./setup.sh
```

---

## 3. Running the Tests

### All 14 tests (recommended)

```bash
pytest tests/ -v
```

Expected output: **14 passed** (2 agent structure tests, 8 API/validation tests, 4 tool tests).

> **No API keys are required to run tests.** All external calls are mocked.

---

## 4. Generating Phoenix Traces

### Run all 11 trace queries automatically

```bash
chmod +x run_traces.sh
./run_traces.sh
```

The script runs 11 queries covering every tool combination, both budget voices, place auto-correction, past-date error handling, and edge cases. All dates are computed dynamically relative to today.

View traces in the Phoenix UI at **http://localhost:6006** after running queries.

---

## 5. Running Evaluations

```bash
python -m evaluations.run_evals
```

Three metrics: User Frustration (Phoenix built-in), Tool Usage Correctness (custom), Answer Completeness (custom).

Results are logged back to Phoenix and visible in the **Evaluations** tab.

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
│   ├── test_tools.py               # 4 tool unit tests (mocked)
│   ├── test_agent.py               # 2 agent structure tests
│   └── test_api.py                 # 8 API endpoint + validation tests
├── evaluations/
│   ├── run_evals.py                # Phoenix evaluation runner (3 metrics)
│   └── metrics/
│       ├── frustration.py          # Reference frustration prompt
│       ├── answer_completeness.py  # ANSWER_COMPLETENESS_PROMPT
│       └── tool_correctness.py     # TOOL_CORRECTNESS_PROMPT
├── scripts/
│   └── export_spans.py             # Export Phoenix spans to CSV
├── run_traces.sh                   # 11 trace queries for Phoenix tracing
├── setup.sh                        # One-command setup (Docker path)
├── Dockerfile                      # Container build
├── docker-compose.yml              # TravelShaper + Phoenix stack
├── pyproject.toml                  # Dependencies
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

**Phoenix UI shows no traces**
Run `./run_traces.sh` after starting the full `docker compose up` stack.

**`ModuleNotFoundError: No module named 'phoenix'`**
The tracing client packages are installed by `poetry install`. If you need
the Phoenix server or eval runner locally, install them with pip:
`pip install arize-phoenix arize-phoenix-evals`
