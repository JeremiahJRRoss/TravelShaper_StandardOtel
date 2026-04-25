# Implementation Plan — TravelShaper Travel Assistant

**Execution instructions for the AI builder:**
- Execute ONE step at a time
- After each step, state what you created and confirm the acceptance criteria
- Then STOP and wait for the user to say "continue" before proceeding
- Do NOT combine steps or work ahead

---

## Step 1: Project scaffolding + dependency update

Do all of these together:

**1a. Create directories and __init__.py files:**
```
se-interview/
├── tools/
│   └── __init__.py          (already exists — verify)
├── tests/
│   └── __init__.py          (already exists — verify)
├── evaluations/
│   ├── __init__.py          (already exists — verify)
│   └── metrics/
│       └── __init__.py      (already exists — verify)
└── docs/                    (already exists)
```

**1b. Update pyproject.toml** — add to `[tool.poetry.dependencies]`:
```toml
requests = "^2.31"
arize-phoenix = {version = "*", optional = true}
arize-phoenix-evals = {version = "*", optional = true}
arize-phoenix-otel = {version = "*", optional = true}
openinference-instrumentation-langchain = {version = "*", optional = true}
pytest = {version = "^8", optional = true}
httpx = {version = "^0.27", optional = true}
```
Add:
```toml
[tool.poetry.extras]
phoenix = ["arize-phoenix", "arize-phoenix-evals", "arize-phoenix-otel", "openinference-instrumentation-langchain"]
dev = ["pytest", "httpx"]
```

**1c. Update .env.example:**
```
OPENAI_API_KEY=your_openai_api_key_here
SERPAPI_API_KEY=your_serpapi_api_key_here
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

**1d. Verify existing tool modules** — Read and confirm these files exist and are correct:
- `tools/__init__.py` — has `serpapi_request()` function
- `tools/flights.py` — has `search_flights` tool with `@tool` decorator
- `tools/hotels.py` — has `search_hotels` tool with `@tool` decorator
- `tools/cultural_guide.py` — has `get_cultural_guide` tool with `@tool` decorator

**Done when:** All directories exist, pyproject.toml is updated, .env.example has 3 keys, all 4 tool files are confirmed correct.

**STOP and wait for "continue".**

---

## Step 2: Rewrite agent.py

Replace agent.py entirely. This is the most important file in the project.

**Before writing code, read `docs/system-prompt-spec.md`.** It contains the exact SYSTEM_PROMPT and the exact Phoenix instrumentation block. Copy both verbatim.

The new agent.py must:
1. Import `load_dotenv` and call it first
2. Import all 4 tools: `search_flights`, `search_hotels`, `get_cultural_guide`, `DuckDuckGoSearchRun`
3. Include the Phoenix instrumentation block (wrapped in try/except ImportError):
```python
try:
    import os as _os
    from phoenix.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor
    endpoint = _os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://localhost:6006/v1/traces")
    tracer_provider = register(project_name="travelshaper", endpoint=endpoint)
    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)
except ImportError:
    pass
```
4. Define `SYSTEM_PROMPT` as a constant (copy from system-prompt-spec.md)
5. Define `tools` list with all 4 tools
6. Define `tools_by_name` dict
7. Define `model` and `model_with_tools`
8. Define `MessagesState(TypedDict)` with `messages: Annotated[list[AnyMessage], operator.add]`
9. Define `llm_call(state)` — invoke model_with_tools with `[SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]`
10. Define `tool_node(state)` — execute tool calls from last message
11. Define `should_continue(state)` — route to "tool_node" or END
12. Define `build_agent()` — build StateGraph with nodes and edges, compile and return

**Done when:** The file can be imported without error. `build_agent()` returns a compiled graph with nodes "llm_call" and "tool_node".

**STOP and wait for "continue".**

---

## Step 3: Update api.py

Minimal changes to api.py:
1. Ensure `load_dotenv()` is called before `from agent import build_agent`
2. The rest stays the same — `POST /chat` and `GET /health`

**Done when:** `api.py` imports cleanly and both endpoints work.

**STOP and wait for "continue".**

---

## Step 4: Write tests/test_tools.py

Write exactly 4 tests. See `docs/test-specification.md` for exact mock data and assertions.

**Critical mock path rule:** Each tool imports `serpapi_request` via `from tools import serpapi_request`. Mock where it's USED:
- `@patch("tools.flights.serpapi_request")`
- `@patch("tools.hotels.serpapi_request")`
- `@patch("tools.cultural_guide.serpapi_request")`

Tests:
1. `test_search_flights_formats_results` — mock returns flight data → assert "ANA", "687", "SFO", "NRT" in result
2. `test_search_flights_handles_empty_results` — mock returns empty → assert "No flights found" in result
3. `test_search_hotels_formats_results` — mock returns hotel data → assert "Hotel Gracery Shinjuku", "$89" in result
4. `test_cultural_guide_returns_guidance` — mock returns organic results → assert "Bowing", "Japan Etiquette Guide" in result

**Done when:** `pytest tests/test_tools.py -v` shows 4 passing.

**STOP and wait for "continue".**

---

## Step 5: Write tests/test_agent.py

Write exactly 2 tests:

1. `test_agent_graph_has_expected_nodes` — call `build_agent()`, check the compiled graph has nodes named "llm_call" and "tool_node"
2. `test_agent_tools_registered` — import `tools` from agent module, verify `len(tools) == 4` and names include "search_flights", "search_hotels", "get_cultural_guide", "duckduckgo_search"

**Done when:** `pytest tests/test_agent.py -v` shows 2 passing.

**STOP and wait for "continue".**

---

## Step 6: Write tests/test_api.py

Write exactly 2 tests using FastAPI's TestClient (from `starlette.testclient`):

1. `test_health_endpoint` — GET `/health` returns 200 with `{"status": "ok"}`
2. `test_chat_endpoint_accepts_message` — mock `api.agent.invoke` to return `{"messages": [AIMessage(content="test briefing")]}`, POST `/chat` with `{"message": "Plan a trip"}`, assert 200 and non-empty "response" field

**Done when:** `pytest tests/test_api.py -v` shows 2 passing. Then run `pytest tests/ -v` to confirm all 8 pass.

**STOP and wait for "continue".**

---

## Step 7: Create Docker files

Copy these exactly from `docs/docker-spec.md`:

1. `Dockerfile` — the full Dockerfile with HEALTHCHECK, curl, poetry==1.8.2
2. `docker-compose.yml` — travelshaper service + phoenix service
3. `.dockerignore` — exclude .env, .git, __pycache__, docs

Also update `.gitignore` to include: `.env`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `spans_export.csv`

**Done when:** All 3 files created. Dockerfile syntax is valid.

**STOP and wait for "continue".**

---

## Step 8: Write evaluations/metrics/frustration.py

Create the user frustration evaluator module. See `docs/evaluation-prompts.md` for the exact prompt.

The file should contain:
1. A module docstring
2. The `USER_FRUSTRATION_PROMPT` string constant (copy from evaluation-prompts.md)

That's it — just the prompt constant. The run_evals.py script imports it.

**Done when:** File exists and can be imported.

**STOP and wait for "continue".**

---

## Step 9: Write evaluations/metrics/tool_correctness.py

Create the tool correctness evaluator module. See `docs/evaluation-prompts.md` for the exact prompt.

The file should contain:
1. A module docstring
2. The `TOOL_CORRECTNESS_PROMPT` string constant (copy from evaluation-prompts.md)

**Done when:** File exists and can be imported.

**STOP and wait for "continue".**

---

## Step 10: Write evaluations/run_evals.py

Create the evaluation runner script. See `docs/evaluation-prompts.md` for the complete script.

The file should:
1. Import prompts from `evaluations.metrics.frustration` and `evaluations.metrics.tool_correctness`
2. Connect to Phoenix via `px.Client()`
3. Fetch spans with `client.get_spans_dataframe()`
4. Filter to root spans
5. Run `llm_classify` with both prompts
6. Log evaluations back to Phoenix with `SpanEvaluations`
7. Create a "frustrated_interactions" dataset from frustrated results
8. Print summary stats

Include a NOTE comment about checking Phoenix docs for exact column name mapping.

**Done when:** File exists, imports work, and the script would run correctly against a populated Phoenix instance.

**STOP and wait for "continue".**

---

## Step 11: Create run_traces.sh

Create a shell script with all 10 trace queries from `docs/trace-queries.md`:

```bash
#!/bin/bash
# Run 10 trace queries against TravelShaper for Phoenix tracing
set -e
BASE_URL="${1:-http://localhost:8000}"
```

Include all 10 curl commands with `echo "=== Query N ==="` headers and `sleep 2` between each.

**Done when:** File exists and is executable.

**STOP and wait for "continue".**

---

## Step 12: Final verification

Run these checks:
1. `pytest tests/ -v` — all 8 tests pass
2. Review every file in the project for consistency
3. Confirm no API keys are hardcoded anywhere
4. Confirm `.gitignore` includes `.env`
5. List every file created or modified in a summary table

**Done when:** You provide a complete file inventory with status (created/modified/unchanged) for every file in the project.
