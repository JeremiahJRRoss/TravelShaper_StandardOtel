# Software Architecture Document — TravelShaper Travel Assistant

**Version:** 2.1 (v0.1.5)
**Date:** April 2026
**Status:** Implementation phase

---

## 1. Overview

TravelShaper is a LangGraph-based travel planning agent exposed via a FastAPI HTTP API. It accepts a natural-language travel request, dispatches specialized tools to gather flight, hotel, and cultural intelligence, and returns a synthesized travel briefing. All LLM and tool activity is traced via Arize Phoenix.

This document describes the software architecture: component design, data flow, external dependencies, deployment topology, and the decisions behind each choice.

---

## 2. Architecture Goals

TravelShaper's architecture is optimized for five goals:

1. **Deliver useful trip briefings in one request.** The system accepts a single natural-language prompt and returns a synthesized travel briefing with flights, hotels, cultural prep, and interest-based suggestions. No multi-step wizard, no session required.

2. **Keep the agent workflow simple and explainable.** The design preserves the starter app's ReAct-style graph and adds tools without introducing unnecessary orchestration complexity. The graph topology adds one entry node (`route_and_inject`) for voice selection — the tool loop itself does not change.

3. **Make tool use observable and evaluable.** Phoenix must capture LLM calls, tool calls, and full request traces. Evaluation metrics (user frustration, tool correctness, answer completeness) must be runnable against collected traces.

4. **Support local demo and production discussion.** The architecture must run locally with Docker and also support a credible production deployment story with scaling, latency, and cost considerations for the presentation.

5. **Stay within deliberate product boundaries.** TravelShaper is a planning assistant, not a booking system. It is single-turn, API-only, English-only, and does not include persistent user accounts or saved trips. These are non-goals, not gaps.

---

## 3. System Context

```
┌──────────┐       HTTP POST /chat        ┌──────────────────┐
│  Client   │ ──────────────────────────▶  │  TravelShaper API     │
│  (curl,   │                              │  (FastAPI)       │
│  browser, │  ◀──────────────────────────  │                  │
│  frontend)│       JSON response          └────────┬─────────┘
└──────────┘                                        │
                                                    │ invokes
                                                    ▼
                                           ┌──────────────────┐
                                           │  LangGraph Agent │
                                           │  (ReAct loop)    │
                                           └────────┬─────────┘
                                                    │
                              ┌──────────┬──────────┼──────────┬──────────┐
                              │          │          │          │          │
                              ▼          ▼          ▼          ▼          ▼
                         ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
                         │ OpenAI │ │SerpAPI │ │SerpAPI │ │SerpAPI │ │ DDG    │
                         │ GPT   │ │Flights │ │Hotels  │ │Google  │ │ Search │
                         └────────┘ └────────┘ └────────┘ └────────┘ └────────┘

                              ▲
                              │ traces (OTLP)
                              ▼
                         ┌────────────┐
                         │   Phoenix  │
                         │   (local)  │
                         └────────────┘
```

**External dependencies:**

| Service | Purpose | Auth | Failure mode |
|---------|---------|------|-------------|
| OpenAI API | LLM reasoning and synthesis | API key | Fatal — agent cannot function |
| SerpAPI | Flights, hotels, scoped web search | API key | Degraded — falls back to DuckDuckGo |
| DuckDuckGo | General web search | None | Degraded — agent relies on LLM knowledge |
| Phoenix | Trace collection and evaluation | None (local) | Silent — app functions, traces lost |

---

## 4. Component Architecture

### 4.1 Component overview

```
src/
├── api.py                     # HTTP layer — REST + SSE endpoints + validation
├── agent.py                   # Agent graph + dual system prompts + voice routing
├── static/
│   └── index.html             # Browser chat UI (Bebas Neue / Cormorant Garamond / DM Sans)
├── tools/
│   ├── __init__.py            # SerpAPI helper (serpapi_request)
│   ├── flights.py             # search_flights
│   ├── hotels.py              # search_hotels
│   └── cultural_guide.py      # get_cultural_guide
├── evaluations/
│   ├── run_evals.py           # Evaluation runner (3 metrics)
│   └── metrics/
│       ├── frustration.py     # Reference frustration prompt (production uses Phoenix built-in)
│       ├── answer_completeness.py # ANSWER_COMPLETENESS_PROMPT
│       └── tool_correctness.py# TOOL_CORRECTNESS_PROMPT
├── scripts/
│   └── export_spans.py        # Export Phoenix spans to CSV
├── tests/
│   ├── test_tools.py          # 4 tool tests
│   ├── test_agent.py          # 2 agent graph tests
│   └── test_api.py            # 8 API + validation tests
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .env
```

### 4.2 Component responsibilities

**api.py — HTTP layer**

Owns the FastAPI application, request/response models, endpoint routing, and input validation.
Delegates intelligence to the agent. Stateless — no session management.

Endpoints:
- `POST /chat` — synchronous; accepts `{"message": str, "preferences": str|null, "departure": str|null, "destination": str|null}`; returns `{"response": str, "run_id": str}`. When `TRAVELSHAPER_DEBUG=true`, the response also includes a `debug` object with `trace_url` pointing to the Phoenix UI trace view. Used by curl and tests.
- `POST /chat/stream` — SSE streaming; same request body; emits real-time `status`, `place_corrected`, `place_error`, `validation_error`, `done`, and `error` events. The SSE `done` event always includes `run_id`. Used by the browser UI.
- `GET /health` — returns `{"status": "ok"}`
- `POST /feedback` — accepts `{ run_id, session_id, score, comment }`;
  stores feedback to local JSONL, best-effort syncs to Phoenix as a
  "User Feedback" annotation. Score must be `1` or `-1`. Rate-limited
  to 20 submissions per session per 5-minute window.
- `GET /` — serves the browser chat UI (`static/index.html`)

Validation pipeline (runs before agent invocation):
1. **Place validation** — `validate_place()` calls `gpt-4o` to verify departure and destination are real, recognisable places. Corrects misspellings; rejects ambiguous or fictional names.
2. **Preference validation** — `validate_preferences()` calls `gpt-4o` to safety-classify free-form user text. Rejects illegal requests, prompt injection, and off-topic content.

Does not contain business logic beyond validation.

**agent.py — Agent orchestration**

Owns the LangGraph state graph, two voice-matched system prompts, and the tool registry.

Two system prompts selected at runtime by `get_system_prompt(message)`:
- `SYSTEM_PROMPT_SAVE_MONEY` — Bourdain / Billy Dee Williams / Gladwell voice; activated when message contains "save money", "budget", "cheapest", or "spend as little"
- `SYSTEM_PROMPT_FULL_EXPERIENCE` — Robin Leach / Pharrell Williams / Salman Rushdie voice; the default

Graph nodes:
- `route_and_inject` — runs once at graph entry; inspects the last human message for budget keywords, selects the appropriate system prompt, and injects it into message state as a `SystemMessage`
- `llm_call` — invokes gpt-5.3-chat-latest with the message history (which already contains the system prompt injected by `route_and_inject`) and bound tools
- `tool_node` — executes tool calls, returns `ToolMessage` results
- `should_continue` — routes to `tool_node` if tool calls present, otherwise to `END`

The graph topology:

```
START → route_and_inject → llm_call → should_continue?
                                        ├── tool calls present → tool_node → llm_call
                                        └── no tool calls     → END
```

The extension adds three new tools to the registry and one entry node for voice routing. The ReAct loop (llm_call ↔ tool_node) is unchanged from the starter app.

**tools/ — Tool modules**

Each tool is a self-contained module that:
1. Defines a function decorated with `@tool` (LangChain tool interface)
2. Has a clear docstring that the LLM reads to decide when to invoke it
3. Accepts typed parameters
4. Returns a string (tool output that becomes a `ToolMessage`)
5. Handles its own errors and returns a descriptive message on failure

Tools do not call each other. Tools do not access agent state. Tools are independently testable.

**evaluations/ — Phoenix evaluation scripts**

Standalone scripts that run after traces are collected. Not part of the request path. Read spans from Phoenix, apply evaluation logic, and write results back to Phoenix as annotations.

**tests/ — Test suite**

Unit tests that validate tool schemas, agent graph construction, and API endpoint behavior. Tests mock external API calls — they never require live SerpAPI or OpenAI keys.

---

## 5. Data Flow

### 5.1 Request lifecycle

```
1. Client sends POST /chat {"message": "..."}
      │
2. api.py validates places and preferences, wraps message as HumanMessage, invokes agent
      │
3. agent.build_agent() returns compiled graph
      │
4. Graph executes: START → route_and_inject
      │
5. route_and_inject inspects message for budget keywords, injects SystemMessage into state
      │
6. Graph continues: route_and_inject → llm_call
      │
7. GPT-5.3 reads system prompt (from state) + user message + tool descriptions
      │
8. GPT-5.3 decides: call tools or respond directly
      │
      ├── [Tools needed] → returns AIMessage with tool_calls
      │     │
      │  9. should_continue routes to tool_node
      │     │
      │  10. tool_node executes each tool call:
      │     ├── search_flights(departure, arrival, date, ...)
      │     │     └── HTTP GET to SerpAPI → structured JSON → string
      │     ├── search_hotels(destination, check_in, check_out, ...)
      │     │     └── HTTP GET to SerpAPI → structured JSON → string
      │     ├── get_cultural_guide(destination)
      │     │     └── HTTP GET to SerpAPI → web results → string
      │     └── web_search(query)
      │           └── DuckDuckGo → string
      │     │
      │  11. tool_node returns list of ToolMessages
      │     │
      │  12. Graph loops back to llm_call
      │     │
      │  13. GPT-5.3 reads tool results, synthesizes briefing
      │     │
      │  14. should_continue → END (no more tool calls)
      │
      └── [No tools needed] → returns AIMessage with content
            │
15. api.py extracts final message content
      │
16. Client receives {"response": "..."}
```

### 5.2 Data shapes

**Agent state:**

```python
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
```

The state is a flat list of messages. Each graph node appends to it. LangGraph's `operator.add` reducer handles concatenation.

**Tool inputs (Pydantic or typed args):**

```python
# search_flights
{
    "departure_id": "SFO",        # IATA airport code
    "arrival_id": "NRT",          # IATA airport code
    "outbound_date": "2026-10-15", # YYYY-MM-DD
    "return_date": "2026-10-25",   # YYYY-MM-DD
}

# search_hotels
{
    "query": "Tokyo hotels",
    "check_in_date": "2026-10-15",
    "check_out_date": "2026-10-25",
    "adults": 2,
    "sort_by": 3                   # 3=lowest price, 13=highest rating
}

# get_cultural_guide
{
    "destination": "Tokyo, Japan"
}
```

**Tool outputs:**

All tools return strings. For structured sources (SerpAPI flights/hotels), the tool formats the JSON response into a readable summary. For web search tools, the raw search snippets are returned. The LLM handles final synthesis.

### 5.3 Partial-input behavior

Users will not always provide all five expected inputs (origin, destination, dates, budget, interests). The architecture handles this gracefully:

- **Missing dates:** The agent searches without date constraints or uses a reasonable near-future window. Flight and hotel tools degrade to less specific results, not errors.
- **Missing budget preference:** The agent defaults to the full-experience voice (no budget keyword detected by `route_and_inject`), showing a range of options without strong ranking bias.
- **Missing interests:** The agent skips interest-based web search and focuses on flights, hotels, and cultural prep.
- **Missing origin:** The agent cannot search flights but can still search hotels, cultural info, and interests for the destination.

The guiding principle: provide the best possible partial briefing rather than refuse to act or depend on follow-up state that doesn't exist in a single-turn system.

---

## 6. Technology Decisions

### 6.1 LangGraph over plain LangChain

The starter app uses LangGraph's `StateGraph` rather than LangChain's `AgentExecutor`. This gives explicit control over the agent loop: we can see exactly which nodes fire, in what order, and with what state. Phoenix traces map cleanly to graph nodes, making observability richer.

The ReAct loop (llm → tool → llm → ... → end) is the simplest useful agent pattern and matches the assessment's scope.

### 6.2 GPT-5.3 as the reasoning model

gpt-5.3-chat-latest is used for the agent because:
- Strong agentic reasoning and synthesis capability
- Strong tool-calling support (parallel tool calls, reliable structured arguments)
- Good at synthesis tasks (combining multiple tool results into a coherent briefing)
- Temperature is passed via `model_kwargs={"temperature": 1}` — the only value gpt-5.3-chat-latest accepts

### 6.3 SerpAPI as the data layer

SerpAPI was chosen because:
- One API key powers three tool types (flights, hotels, general search)
- Google Flights and Google Hotels engines return structured JSON — not raw HTML scraping
- Free tier (250 searches/month) is sufficient for development and demo
- Python `requests` library is the only dependency — no SDK required

The alternative was direct web scraping or dedicated APIs (Amadeus, Booking.com). Scraping is brittle. Dedicated APIs require separate accounts and approval processes that conflict with the time constraint.

### 6.4 DuckDuckGo as fallback

Already present in the starter code. No API key needed. Provides general web search coverage for interest discovery, cultural questions, and edge cases that SerpAPI doesn't cover.

### 6.5 FastAPI for the HTTP layer

Already present in the starter code. Async-capable, automatic OpenAPI docs at `/docs`, Pydantic validation on request/response models. No reason to change it.

### 6.6 Phoenix for observability

Phoenix was chosen because:
- Required by the assessment
- OpenTelemetry-native — traces capture LLM calls, tool usage, and latency automatically
- Local-first — runs as a local server, no cloud account needed
- Built-in evaluation framework for user frustration and custom metrics
- LangGraph integration via `openinference-instrumentation-langchain`

---

## 7. Observability Architecture

### 7.1 Instrumentation

Tracing is initialized at application startup via `_init_tracing()` in `agent.py`. This is the **only** file that imports OTEL packages — all other tracing flows through LangChain's callback/instrumentor system.

#### Trace routing

Trace destination is configured in `tracing.yaml` via `OTEL_DESTINATION`:

| Destination | Package | Endpoint | Auth |
|-------------|---------|----------|------|
| `phoenix` (default) | `arize-phoenix-otel` | `PHOENIX_COLLECTOR_ENDPOINT` | Optional `PHOENIX_API_KEY` |
| `arize` | `arize-otel` | `otlp.arize.com:443` (gRPC) | `ARIZE_SPACE_ID` + `ARIZE_API_KEY` |
| `custom` | *(none — OTEL SDK only)* | `OTEL_EXPORTER_OTLP_ENDPOINT` | `OTEL_AUTH_TOKEN` via headers |

All three produce identical OpenInference spans via the same `LangChainInstrumentor`.
The choice affects only where OTLP data is exported.

The config file is read at two stages:
- **Build time** by the Dockerfile to install only the needed Poetry extras
- **Runtime** by `agent.py` to initialize the correct TracerProvider

Secrets use `${ENV_VAR}` syntax in `tracing.yaml` and are resolved from the
container environment (`.env` file) at runtime.

Typical pattern: Phoenix for local development and CI, Arize AX for staging
and production, custom for enterprise observability platforms (Cribl, Honeycomb,
Grafana Tempo, Datadog, etc.).

The initialization is split into five functions:

- `_load_tracing_config()` — loads `tracing.yaml`, resolves `${ENV_VAR}` refs.
- `_init_tracing()` — entry point; imports the instrumentor, dispatches to the
  appropriate backend based on config, then instruments.
- `_init_phoenix(cfg)` — configures Phoenix via `phoenix.otel.register()`.
- `_init_arize(cfg)` — configures Arize AX via `arize.otel.register()`.
- `_init_custom(cfg)` — configures any OTLP endpoint via raw OTEL SDK.
  Supports `http/protobuf` (default), `grpc`, and `http/json` protocols.

**Key design principle:** `api.py` does not import `opentelemetry` directly. Instead, it attaches request-level metadata (destination, departure, budget mode) via LangChain's `RunnableConfig`, which the instrumentor propagates to all child spans automatically. This means swapping the OTEL backend requires editing one line in `tracing.yaml` — no code changes needed.

The validation classifiers (`validate_place`, `validate_preferences`) use LangChain's `ChatOpenAI` instead of the raw OpenAI SDK, so their LLM calls appear as traced spans alongside the agent's own LLM and tool spans. Each key invocation is tagged with a `run_name` for easy identification in Phoenix:

| Invocation | `run_name` |
|------------|------------|
| Agent LLM call | `travelshaper_llm_call` |
| Validation classifier | `validation_classifier` |
| `/chat` request | `travelshaper_chat` |
| `/chat/stream` request | `travelshaper_stream` |

#### Request-level metadata attributes

Every request trace carries these attributes in `RunnableConfig.metadata`,
propagated to all child spans by the LangChain instrumentor:

| Attribute | Source | Example |
|-----------|--------|---------|
| `session.id` | Browser `crypto.randomUUID()` or per-request fallback | `"a1b2c3d4-..."` |
| `travelshaper.prompt_version` | `get_prompt_version()` from `agent.py` | `"save_money_v1"` |
| `travelshaper.budget_mode` | Derived from prompt version | `"save_money"` |
| `travelshaper.destination` | Request field | `"Tokyo, Japan"` |
| `travelshaper.departure` | Request field | `"San Francisco, CA"` |
| `travelshaper.validation.departure` | Post-validation | `"valid"` / `"corrected"` / `"failed"` |
| `travelshaper.validation.destination` | Post-validation | Same |
| `travelshaper.validation.preferences` | Post-validation | `"valid"` / `"failed"` / `"skipped"` |
| `travelshaper.guardrails.count` | Count of validation calls | `2` |
| `travelshaper.guardrails.blocked` | Count of rejections | `0` |
| `travelshaper.total_tokens` | Post-request | `1420` |
| `travelshaper.estimated_cost_usd` | Post-request | `0.01485` |
| `travelshaper.sla.budget_ms` | Constant | `35000` |
| `travelshaper.sla.exceeded` | Post-request | `false` |

Validation classifier spans additionally carry:

| Attribute | Value |
|-----------|-------|
| `travelshaper.span_type` | `"guardrail"` |
| `travelshaper.guardrail.name` | `"place_validation"` or `"preference_validation"` |
| `travelshaper.guardrail.field` | `"departure"`, `"destination"`, or `"preferences"` |

### 7.2 What gets traced

| Span type | Captured data |
|-----------|---------------|
| LLM span | Model name, input messages, output message, token counts (prompt + completion), latency, tool call decisions |
| Tool span | Tool name, input arguments, output content, execution duration |
| Chain span | End-to-end trace from `/chat` request to response, linking all child spans |

### 7.3 Trace structure

A typical travel briefing query produces this trace:

```
[Chain] travelshaper_chat (RunnableConfig metadata: destination, departure, budget_mode)
  ├── [LLM] validation_classifier (place validation — departure)
  ├── [LLM] validation_classifier (place validation — destination)
  └── [Chain] agent.invoke
        ├── [Chain] route_and_inject (selects voice, injects system prompt)
        ├── [LLM] travelshaper_llm_call (initial — decides to call tools)
        ├── [Tool] search_flights
        ├── [Tool] search_hotels
        ├── [Tool] get_cultural_guide
        └── [LLM] travelshaper_llm_call (synthesis — produces final briefing)
```

Total spans per query: typically 8–13 depending on how many tools are dispatched, whether place validation triggers, and whether the LLM loops more than once. Validation classifier spans are nested under the request chain because `validate_place()` and `validate_preferences()` receive the endpoint's `RunnableConfig` (which carries the `run_id` / trace context). The LangChain instrumentor uses this to parent the LLM spans correctly.

### 7.4 Evaluation pipeline

Evaluations run as a separate batch process after traces are collected:

```
Phoenix (stored traces)
    │
    ▼
run_evals.py
    ├── Fetch spans from Phoenix
    ├── [1/4] User Frustration (Phoenix built-in template)
    ├── [2/4] Tool Usage Correctness (custom prompt)
    ├── [3/4] Answer Completeness (custom prompt)
    ├── [4/4] Tool Output Quality (custom prompt)
    ├── Write annotations back to Phoenix
    ├── Create per-outcome datasets
    └── Create golden_set from all-positive traces
```

Evaluators are LLM-as-judge functions: they send the trace data to GPT-4o with an evaluation prompt and receive a label plus an explanation.

Four metrics chosen based on observed failure modes:

| Metric | What it catches | Labels |
|--------|----------------|--------|
| User Frustration | Silent omissions, ignored preferences | frustrated / not_frustrated |
| Tool Usage Correctness | Wrong tools, bad parameters, missed tools | correct / incorrect |
| Answer Completeness | Missing sections (scope-aware) | complete / partial / incomplete |
| Tool Output Quality | Garbage data, wrong destinations, implausible prices | good / degraded / poor |

* **User Frustration** catches the most common end-user-visible failure: the agent silently omitting requested information when a tool returns empty results, or contradicting the user's stated budget preference. Uses Phoenix's built-in template for validated detection.
* **Tool Usage Correctness** catches the most common agent-level failure: incorrect IATA codes passed to `search_flights`, skipped `get_cultural_guide` calls for international trips, and unnecessary tool calls on vague queries. These are invisible to the user but directly cause the incomplete briefings that frustration detects.
* **Answer Completeness** fills a gap the other two metrics can't cover: distinguishing intentionally scoped responses (user asked for flights only) from unintentionally incomplete ones (agent failed to search hotels). Its three-tier classification (complete/partial/incomplete) with scope-awareness prevents false positives on scoped queries in the trace set.
* **Tool Output Quality** catches a failure mode invisible to the other three: the right tool was called with valid parameters, but the data that came back was wrong (SerpAPI rate limit, IATA code that maps to the wrong airport, implausible prices). The LLM confidently synthesises this garbage into a wrong briefing that *looks* complete and correct.

**Per-outcome datasets** are created automatically from traces matching negative
eval labels. These make it trivial to investigate specific failure modes in
Phoenix.

**Golden set:** Traces where all four evals scored positive. Use as a regression
test suite before deploying prompt changes.

**User feedback annotations.** The `POST /feedback` endpoint and
`scripts/sync_feedback.py` write "User Feedback" annotations to Phoenix
spans. These appear in the Evaluations tab alongside automated eval results,
providing ground truth for validating the automated metrics. Feedback is
stored locally in `feedback.jsonl` as the durable source of truth; Phoenix
annotations are derived from it.

### 7.5 Token/cost tracking and latency budgets

A `TokenUsageTracker` (LangChain `BaseCallbackHandler`) is created per request
and attached to `config["callbacks"]`. It accumulates token counts across all
LLM calls in the request — both validation classifiers and agent — with
per-model breakdowns.

Cost estimation uses approximate per-model rates defined in
`_COST_PER_1M_TOKENS`. The rate table must be updated manually when provider
pricing changes.

Two request phases are timed separately:
- **Validation phase:** all `validate_place` + `validate_preferences` calls
- **Agent phase:** `agent.invoke()` or `agent.astream()` execution

The `sla_exceeded` flag triggers when total time exceeds `_SLA_TOTAL_S`
(default 35s). The budget and flag are recorded as span metadata for Phoenix
dashboards.

**Streaming token counts:** The agent model sets `stream_usage=True`, which
makes OpenAI include usage data in the final streaming chunk. Without this,
`on_llm_end` receives no token data during streaming and the tracker records
zeros.

---

## 8. Tool Design Patterns

### 8.1 Tool interface contract

Every tool follows the same pattern:

```python
from langchain_core.tools import tool

@tool
def search_flights(
    departure_id: str,
    arrival_id: str,
    outbound_date: str,
    return_date: str,
) -> str:
    """Search for flights between two airports.
    
    Use this tool when the user wants to find flights.
    departure_id and arrival_id should be IATA airport codes (e.g., SFO, NRT, CDG).
    Dates should be YYYY-MM-DD format.
    """
    # 1. Build SerpAPI request
    # 2. Execute HTTP call
    # 3. Parse response
    # 4. Format as readable string
    # 5. Return string (or error message)
```

**The docstring is critical.** GPT-5.3 reads it to decide when to invoke the tool and what arguments to pass. A vague docstring means unreliable tool selection.

### 8.2 Error handling strategy

Tools never raise exceptions into the agent loop. On failure, they return a descriptive error string that the LLM can work with:

```python
try:
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.Timeout:
    return "Flight search timed out. Please try again."
except requests.HTTPError as e:
    return f"Flight search failed: {e}"
```

This lets the agent gracefully degrade: "I couldn't find flight data, but here's what I know about Tokyo from web search..."

### 8.3 SerpAPI call pattern

All SerpAPI tools share a common helper:

```python
import os
import requests

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_URL = "https://serpapi.com/search"

def serpapi_request(params: dict, timeout: int = 15) -> dict:
    params["api_key"] = SERPAPI_KEY
    response = requests.get(SERPAPI_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()
```

Each tool sets the `engine` parameter to the appropriate SerpAPI engine:
- `search_flights` → `engine=google_flights`
- `search_hotels` → `engine=google_hotels`
- `get_cultural_guide` → `engine=google` (with scoped queries)

### 8.4 Response formatting

SerpAPI returns large JSON payloads. Tools extract and format the relevant fields using Pydantic models (`FlightSearchResult`, `HotelSearchResult`, `CulturalGuideResult`) rather than passing raw JSON to the LLM (which would waste tokens and reduce synthesis quality). Each model has a `to_agent_string()` method that produces the formatted output.

### 8.5 Adapter design principle

Tools return TravelShaper-owned output formats, not raw vendor JSON. This protects the agent from upstream response drift — if SerpAPI changes a field name or nesting structure, only the tool adapter changes, not the system prompt or synthesis logic. It also makes evaluation easier, since tool outputs have a consistent shape regardless of which provider backs them.

---

## 9. System Prompt Design

TravelShaper uses two system prompts selected at runtime. This section explains what they contain, why they are written the way they are, and how the selection decision is made.

### 9.1 Why two prompts instead of one

The naive approach is a single prompt with an instruction like "if the user wants to save money, write like Bourdain; if they want the full experience, write like Robin Leach." This does not work reliably. The model reads the entire prompt before generating and blends registers rather than committing to one. A traveller asking for a budget trip gets prose that is 60% Bourdain and 40% Robin Leach — hedged, inconsistent, and not particularly good at being either.

Two separate prompts solve this by giving the model complete, unambiguous instructions with no competing voice. Each prompt is internally consistent from the opening identity statement through every section instruction. The model never has to decide between two modes — it only knows one mode at a time.

### 9.2 Voice routing

```python
def get_system_prompt(message: str) -> str:
    lower = message.lower()
    if "save money" in lower or "budget" in lower \
       or "cheapest" in lower or "spend as little" in lower:
        return SYSTEM_PROMPT_SAVE_MONEY
    return SYSTEM_PROMPT_FULL_EXPERIENCE
```

This runs inside `route_and_inject()`, which executes once at graph entry. The `route_and_inject` node reads the last human message from state, calls `get_system_prompt()`, and appends the selected `SystemMessage` to the message list. All subsequent `llm_call` invocations see the system prompt already in the message history — no re-injection or re-selection occurs.

The routing is intentionally simple — keyword matching on the assembled message string, not a separate classification call. The reasoning:

- The browser form passes a budget toggle whose value is literally `"save money"` or `"full experience"`, so the keywords are guaranteed to appear in the message.
- A separate classification LLM call would add latency and cost for a decision the form has already made explicitly.
- False negatives (a budget user whose message doesn't trigger the keywords) default to the full-experience voice, which is acceptable — the content is still accurate, just more theatrical.

`SYSTEM_PROMPT_FULL_EXPERIENCE` is the default because it produces richer, more ambitious prose for ambiguous or vague queries where no budget signal exists.

### 9.3 SYSTEM_PROMPT_SAVE_MONEY — Bourdain / Billy Dee Williams / Gladwell

**The identity statement** opens with the three voices named explicitly. This is not metaphorical decoration — it is an instruction. Models respond strongly to named author voices because they carry dense implicit style information from training data. Naming Bourdain activates: short declarative sentences, first-person authority, anti-tourist-trap orientation, reverence for the unglamorous. Naming Billy Dee Williams adds cool and poise — the prose doesn't shout, it leans in. Naming Gladwell adds the non-obvious connection, the tipping-point insight that reframes a recommendation.

**Key structural choices:**

- *"Budget is a philosophy, not a limitation"* — reframes the entire mode. The agent is not apologising for cheap options; it is treating the budget traveller as someone who is travelling smarter.
- *"Never say 'hidden gem'"* — explicit prohibition on the single most overused phrase in travel writing.
- The DuckDuckGo search query examples are written like a journalist on assignment: `"best late night ramen Tokyo locals"`, `"free museums Barcelona Tuesday"`. This influences how the tool is actually called.
- *"End with one line. Make it land."* — the closing instruction is intentionally brief.

**Hotel sort:** `sort_by=3` (lowest price). **Tradeoff framing:** stated plainly.

### 9.4 SYSTEM_PROMPT_FULL_EXPERIENCE — Leach / Pharrell / Rushdie

**The identity statement** again names all three voices explicitly. Robin Leach's theatrical grandeur activates the aspirational register. Pharrell's energy prevents this from becoming stiff. Rushdie's prose intelligence pushes it toward literary depth.

**Key structural choices:**

- *"Cities are mythology"* — the single most important instruction. It tells the agent to approach destinations as layered, historically accumulated places.
- *"Every sentence must earn its place"* — anti-bloat instruction.
- Section headers are reframed as editorial titles: "Getting There — Your Chariot Awaits", "Where to Stay — A Sanctuary Awaits".

**Hotel sort:** `sort_by=13` (highest rating).

### 9.5 Shared prompt instructions (both prompts)

Both prompts share a set of hard requirements that cannot vary by voice:

- **Hyperlinks** — mandatory for every named entity. Both prompts include a dedicated section with worked examples.
- **Parallel tool dispatch** — "Call multiple tools in one turn whenever possible."
- **No fabricated facts** — explicit prohibition on fabricating prices, flight times, and hotel names.
- **Section structure** — four named sections with consistent titles that the JavaScript parser in `static/index.html` can reliably segment into cards.

### 9.6 Prompt versioning

Each system prompt has a named version constant (`save_money_v1`,
`full_experience_v1`). The `get_prompt_version(message)` function in `agent.py`
is the single source of truth for voice routing — both `route_and_inject()` and
`api.py`'s config construction import it. When editing prompt text, bump the
version suffix (e.g., `save_money_v2`). This makes the change visible in
Phoenix traces: filter by `travelshaper.prompt_version` to compare eval scores
before and after the edit.

---

## 10. LLM Decision Making

This section explains how the LLM decides what to do at each step of the agent loop, and what happens when those decisions go wrong.

### 10.1 The decision surface

The LLM makes three types of decisions on each `llm_call` invocation:

1. **Which tools to call, and with what arguments.** The model reads the system prompt's tool guidance section, the user's message, and any previous tool results in the conversation history, then decides which tools are relevant for this turn.

2. **Whether to call tools at all, or respond directly.** If the model determines it has enough information to produce a useful response without additional tool calls, it returns a plain `AIMessage` with no `tool_calls`. The `should_continue` edge detects this and routes to `END`.

3. **How to synthesise tool results into prose.** After tool results are returned as `ToolMessage` objects and appended to the state, the model performs a synthesis call. This is where the voice prompts do most of their work.

### 10.2 Tool selection logic

The system prompt's tool guidance section is the primary mechanism for shaping tool selection. Each tool has three signal sources the model uses:

**The `@tool` docstring** — this is what the model actually reads when deciding whether to invoke a tool.

**The system prompt's tool guidance section** — complements the docstring with routing logic.

**Conversation history** — if a previous turn already has hotel results in the `ToolMessage` history, the model typically does not call `search_hotels` again.

### 10.3 Parallel tool dispatch

When the model determines multiple tools are needed, it returns a single `AIMessage` with multiple entries in `tool_calls`. LangGraph's `tool_node` executes these sequentially within a single node invocation. The system prompt instruction "Call multiple tools in a single turn whenever possible" drives this behaviour.

### 10.4 Hotel sort_by routing

Both prompts instruct the model to set `sort_by` differently based on budget mode:

- Save money: `sort_by=3` (lowest price)
- Full experience: `sort_by=13` (highest rating)

This is not hardcoded in the tool — the model reads the instruction and passes the correct parameter.

### 10.5 When the model gets it wrong

**Wrong IATA code.** The most common tool failure. The flight tool returns an error string that the model incorporates gracefully.

**Fabricated hotel names.** Without the "never fabricate" instruction, the model occasionally invents plausible-sounding hotel names when search results are thin.

**Section header repetition.** The JavaScript parser handles this with a `seenTitles` set that merges duplicate section matches.

**Ignored tool results.** Occasionally the model synthesises from general knowledge rather than the tool results it was given. The tool correctness evaluator catches this.

---

## 11. Input Validation Architecture

TravelShaper validates two types of user input before the agent runs: place names and free-form preference text. Both use `gpt-4o` as a classifier via LangChain's `ChatOpenAI`.

### 11.1 Place name validation

**Purpose:** Prevent the agent from spending 20–30 seconds searching for a fictional or misspelled city.

**The classifier prompt instructs `gpt-4o` to return one of four outcomes:**

| Outcome | Condition | Agent behaviour |
|---------|-----------|-----------------|
| `valid=true, corrected=null` | Recognisable real place, correctly spelled | Agent proceeds with input as-is |
| `valid=true, corrected="Tokyo, Japan"` | Misspelling of an identifiable place | Agent proceeds with corrected name; UI shows teal correction banner |
| `valid=false` (ambiguous) | Multiple places match | Request rejected with disambiguation prompt |
| `valid=false` (invalid) | Unrecognisable, fictional, or injected | Request rejected with user-friendly message |

**Fail-open on transient errors.** If the `gpt-4o` call itself fails, `validate_place()` returns `valid=True` with the original input.

### 11.2 Preference text validation

**Purpose:** The `preferences` field is free-form text up to 500 characters that gets appended to the agent's message. Without validation, this is a prompt injection surface.

**Fail-safe on errors.** Unlike place validation, preference validation fails closed: if the `gpt-4o` call fails, `validate_preferences()` returns `valid=False`.

### 11.3 Validation in the SSE stream

The `/chat/stream` endpoint runs validation before opening the SSE connection. If validation fails, it emits a single typed event and closes. The user never sees the loading screen for a request that will be rejected.

### 11.4 Validation cost and latency

Each validation call to `gpt-4o` costs approximately 0.5–1 second. A full request with both place fields and a preferences field makes up to three sequential validation calls before the agent starts.

---

## 12. Deployment Architecture

### 12.1 Local development

```
┌─────────────────────────────────────────────┐
│  Developer machine                          │
│                                             │
│  ┌──────────┐     ┌──────────┐              │
│  │ TravelShaper  │     │ Phoenix  │              │
│  │ :8000    │────▶│ :6006    │              │
│  └────┬─────┘     └──────────┘              │
│       │                                     │
└───────┼─────────────────────────────────────┘
        │
        ▼ (outbound HTTPS)
   ┌─────────┐  ┌─────────┐  ┌─────────┐
   │ OpenAI  │  │ SerpAPI │  │  DDG    │
   └─────────┘  └─────────┘  └─────────┘
```

### 12.2 Docker Compose

```yaml
services:
  travelshaper:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - phoenix

  phoenix:
    image: arizephoenix/phoenix:latest
    ports:
      - "6006:6006"
```

### 12.3 Production architecture (proposed, not implemented)

Horizontal scaling behind a load balancer, Redis for caching + future session memory, separate OTEL collector for async trace export.

---

## 13. Security Considerations

### 13.1 Current implementation

| Concern | Status |
|---------|--------|
| API key storage | `.env` file, excluded from git via `.gitignore` |
| API authentication | None — open endpoint. Acceptable for local demo. |
| Input validation | Pydantic model validates request shape; LLM classifiers validate content |
| Prompt injection | System prompt is hardcoded; user message is treated as untrusted; preferences field is LLM-classified |
| Data persistence | No user data stored beyond Phoenix traces |
| HTTPS | Not configured — local HTTP only |

### 13.2 Production additions

- API key or JWT authentication on `/chat`
- Rate limiting per client
- HTTPS via load balancer TLS termination
- Input sanitization before tool dispatch
- Audit logging for all tool calls
- Phoenix traces redacted of PII before long-term storage

---

## 14. Testing Strategy

### 14.1 Test categories

| Category | Count | What it validates | External calls |
|----------|-------|-------------------|----------------|
| Tool schema tests | 4 | Input types, output format, docstring presence | Mocked |
| Agent graph tests | 2 | Correct nodes, edges, and compilation | None |
| API endpoint tests | 8 | HTTP status codes, response shapes, validation | Mocked |
| **Total** | **14** | | |

### 14.2 Mocking approach

Tests use `unittest.mock.patch` to replace external API calls. No test requires a live API key.

---

## 15. Evolution Path

The architecture is designed to evolve without rewrites. Each phase extends the existing structure.

**Near-term:** Structured preference extraction, bounded result ranking, timeout and fallback policies.

**Medium-term:** Redis-backed session memory, response caching, LangGraph subgraphs if tool set grows.

**Long-term:** Authenticated users, destination comparison mode, itinerary generation, multi-agent specialization.

---

## 16. Key Architectural Decisions Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Agent framework | LangGraph StateGraph | Explicit graph control, better trace visibility, matches starter code |
| Voice routing | Dedicated `route_and_inject` node | Clean separation; system prompt injected once, not on every LLM call |
| LLM provider | OpenAI GPT-5.3 (agent) / GPT-4o (validation) | Strong tool-calling support; well-documented |
| Travel data source | SerpAPI | Single API key for flights + hotels + search; structured JSON |
| General search | DuckDuckGo | No API key needed; already in starter code |
| Observability | Arize Phoenix | Required by assessment; local-first; built-in evaluation framework |
| HTTP framework | FastAPI | Already in starter code; async-capable |
| Deployment | Docker + Docker Compose | Docker is assessment requirement; Compose simplifies Phoenix co-deployment |

---

## 17. Glossary

| Term | Definition |
|------|-----------|
| Agent | A LangGraph state machine that loops between LLM reasoning and tool execution |
| ReAct | Reasoning + Acting — the pattern where an LLM reasons, acts (calls a tool), observes the result, and repeats |
| Tool | A Python function registered with LangChain's `@tool` decorator, callable by the LLM |
| Span | A single unit of work in a trace (one LLM call, one tool execution) |
| Trace | An end-to-end record of a user request, composed of multiple spans |
| Phoenix | Arize's open-source observability platform for LLM applications |
| OpenInference | The semantic convention for LLM observability spans, built on OpenTelemetry |
| SerpAPI | A web API that returns structured Google search results |
| OTEL / OTLP | OpenTelemetry / OpenTelemetry Protocol |
