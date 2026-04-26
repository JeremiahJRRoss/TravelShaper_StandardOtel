# Changelog

## [0.3.0] — 2026-04-25

### Migrate tracing from Arize Phoenix to Observe Inc

#### Changed
- Migrated tracing from Arize Phoenix / Arize AX / custom OTLP backends
  to Observe Inc via the Traceloop SDK (OpenLLMetry).
- Traces are now exported via OTLP HTTP to `TRACELOOP_BASE_URL`
  (default `http://localhost:4318`), where the Observe Agent forwards
  them to the Observe cloud.
- Added structured JSON logging to `/app/logs/travelshaper.log` for the
  Observe Agent's filelog receiver. A human-readable copy still goes to
  stderr for local development.
- Added `Traceloop.set_association_properties()` calls in `/chat` and
  `/chat/stream` so session_id, run_id, destination, budget_mode, and
  prompt_version filter cleanly in the Observe LLM Explorer.
- `OTEL_RESOURCE_ATTRIBUTES` is now split between layers: the app sets
  `service.name` / `service.version`; the Observe Agent's resource
  processor owns `deployment.environment` and other infra attributes.
- Simplified the Dockerfile (no conditional Poetry extras) and
  docker-compose.yml (no Phoenix container, no Arize/Phoenix env vars).
- Bumped package and FastAPI app version to `0.3.0`.

#### Removed
- `tracing.yaml` and the YAML-driven backend selection in `agent.py`
  (`_load_tracing_config`, `_init_phoenix`, `_init_arize`, `_init_custom`).
- Optional Poetry extras `phoenix`, `arize`, and `custom` from
  `pyproject.toml`. The corresponding packages — `arize-phoenix-otel`,
  `arize-otel`, `openinference-instrumentation-langchain`,
  `opentelemetry-exporter-otlp-proto-http`, and `pyyaml` — are gone too.
- The Phoenix container (`arizephoenix/phoenix:latest`) and its
  `depends_on` link from docker-compose.yml.
- `evaluations/` directory (the Phoenix `llm_classify` eval pipeline:
  frustration, tool_correctness, answer_completeness, tool_output_quality).
- `scripts/export_spans.py` (Phoenix span export to CSV) and
  `scripts/sync_feedback.py` (Phoenix feedback annotation sync).
- `_sync_feedback_to_phoenix()` in `api.py`. The `/feedback` endpoint
  still stores submissions to `feedback.jsonl` but always returns
  `synced_to_phoenix: false`.

#### Preserved
- All 4 tools, agent graph topology, dual-voice system prompts, and SSE
  streaming behavior.
- `RunnableConfig` metadata propagation, token / cost tracking,
  SLA timing budgets, and local feedback storage.
- All 11 trace queries in `run_traces.sh`.
- Eval prompts documented in `docs/evaluation-prompts.md` so the
  pipeline can be reimplemented against Observe later.

## [0.2.5] — 2026-04-09

### Trace URL fix + dead env var cleanup

**`api.py`**
- `_trace_url()` now handles the `custom` OTEL backend. Previously it
  fell through to a Phoenix URL when `TRACE_DESTINATION == "custom"`.
  Now returns `trace:{run_id}` (no standard viewer URL exists for
  arbitrary OTLP endpoints).

**`docker-compose.yml`**
- Removed `TRAVELSHAPER_TRACE_BACKEND` env var passthrough. This variable
  was used in v0.2.3 (env-var-based routing) but has been dead since v0.2.4
  switched to `tracing.yaml`. No code reads it.

**`docs/docker-spec.md`**
- Removed `TRAVELSHAPER_TRACE_BACKEND` from the docker-compose example.

**`Dockerfile`**
- Fixed `OTEL_DESTINATION` parsing during build. The previous command
  used `python3 -c "import yaml; ..."` to read `tracing.yaml`, but
  `pyyaml` was not yet installed at that build stage. The `import yaml`
  failure was silenced by `2>/dev/null`, causing `DEST` to always fall
  back to `"phoenix"` — so `arize` and `custom` extras were never
  installed. Replaced with `grep`/`awk` which need no Python packages.
- Added `custom` branch to install `poetry install -E custom` when
  `OTEL_DESTINATION=custom`. Previously the `else` branch ran bare
  `poetry install` with no extras, so the OTLP exporter packages were
  never installed.

**`pyproject.toml`**
- Added `opentelemetry-exporter-otlp-proto-http` as optional dependency
  under new `custom` extra. `_init_custom()` imports from this package
  but it was never a direct dependency — it only came in transitively
  through the phoenix/arize extras.

**`tests/test_api.py`** — 3 new tests:
- `test_trace_url_phoenix`
- `test_trace_url_arize`
- `test_trace_url_custom`

## [0.2.4] — 2026-04-09

### Configurable OTEL trace routing via `tracing.yaml`

Traces can now be sent to Phoenix, Arize AX, or any OTLP-compatible endpoint
by editing a single line in `tracing.yaml`. No Python code changes needed to
switch backends.

#### Usage

Edit `OTEL_DESTINATION` in `src/tracing.yaml`:

```yaml
# Local development
OTEL_DESTINATION: phoenix

# Arize AX cloud (set ARIZE_SPACE_ID and ARIZE_API_KEY in .env)
OTEL_DESTINATION: arize

# Cribl, Honeycomb, Grafana, Datadog, etc.
OTEL_DESTINATION: custom
```

Then rebuild: `docker compose build && docker compose up -d`

#### How it works

- **Build time:** Dockerfile reads `OTEL_DESTINATION` from `tracing.yaml` and
  installs only the Poetry extras needed for that backend (`-E phoenix`,
  `-E arize`, or nothing for custom).
- **Runtime:** `agent.py` loads `tracing.yaml`, resolves `${ENV_VAR}` references
  from the environment, and initializes the matching OTEL TracerProvider.
- **Downstream:** The `LangChainInstrumentor` receives the TracerProvider and
  produces identical OpenInference spans regardless of destination. RunnableConfig
  metadata, span attributes, evaluations, and feedback are all unaffected.

#### Custom destination

The `custom` backend uses the raw OTEL SDK — no vendor packages needed.
It works with any OTLP-compatible receiver. Three protocol options:

- `http/protobuf` — recommended, works through firewalls
- `grpc` — fastest, but may be blocked by proxies
- `http/json` — zero binary deps, useful when protobuf causes conflicts

#### Changes

**`tracing.yaml`** *(new file)*
- Config file with `OTEL_DESTINATION`, per-backend settings, and `${ENV_VAR}` support

**`pyproject.toml`**
- Added `pyyaml = "^6.0"` (config parsing)
- `arize-phoenix-otel` and `arize-otel` moved to optional extras
- New extras: `phoenix`, `arize`
- Version bumped to 0.2.4

**`agent.py`**
- `_load_tracing_config()` — loads and resolves `tracing.yaml`
- `_init_tracing()` — dispatches to backend-specific init based on config
- `_init_phoenix(cfg)` — reads endpoint/project from config dict
- `_init_arize(cfg)` — reads credentials from config dict
- `_init_custom(cfg)` — raw OTEL SDK setup, supports http/protobuf, grpc, http/json
- `TRACE_DESTINATION` — exported for `api.py` trace URL helper

**`api.py`**
- Imports `TRACE_DESTINATION` from `agent` (replaces env var read)

**`Dockerfile`**
- Reads `OTEL_DESTINATION` from `tracing.yaml` at build time
- Installs matching Poetry extra (`-E phoenix`, `-E arize`, or none)

**`docker-compose.yml`**
- Passes custom OTLP env vars to container

**`.env.example`**
- Added `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_AUTH_TOKEN`

**`tests/test_agent.py`** — 3 new tests (2 updated, 1 added):
- `test_load_tracing_config_resolves_env_vars`
- `test_init_tracing_defaults_to_phoenix` (updated for config-driven approach)
- `test_init_tracing_selects_arize_when_configured` (updated)
- `test_init_tracing_selects_custom` (new)

---

## [0.2.3] — 2026-04-08

### Switchable trace backend: Phoenix or Arize AX

TravelShaper now supports sending traces to either Arize Phoenix (local/self-
hosted, default) or Arize AX (cloud platform) via the
`TRAVELSHAPER_TRACE_BACKEND` environment variable.

Both backends produce identical OpenInference traces — the same LangChain
instrumentor, the same span attributes, the same metadata. The only difference
is where the OTLP exporter sends the data.

#### Usage

**Phoenix (default — no changes needed):**
```
TRAVELSHAPER_TRACE_BACKEND=phoenix
PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces
```

**Arize AX:**
```
TRAVELSHAPER_TRACE_BACKEND=arize
ARIZE_SPACE_ID=your-space-id
ARIZE_API_KEY=your-api-key
ARIZE_PROJECT_NAME=travelshaper   # optional, defaults to "travelshaper"
```

#### Changes

**`pyproject.toml`**
- Added `arize-otel = "^0.12"` dependency

**`agent.py`**
- `_init_tracing()` now reads `TRAVELSHAPER_TRACE_BACKEND` env var
- Split into `_init_phoenix()` and `_init_arize()` backend-specific setup
- Arize mode validates `ARIZE_SPACE_ID` and `ARIZE_API_KEY` are set

**`api.py`**
- `_phoenix_trace_url()` renamed to `_trace_url()` — returns Arize AX URL
  when backend is `arize`, Phoenix URL otherwise

**`.env.example`**
- Added `TRAVELSHAPER_TRACE_BACKEND`, `ARIZE_SPACE_ID`, `ARIZE_API_KEY`,
  `ARIZE_PROJECT_NAME`

**`docker-compose.yml`**
- Arize env vars passed through to container

**`tests/test_agent.py`** — 2 new tests:
- `test_init_tracing_defaults_to_phoenix`
- `test_init_tracing_selects_arize_when_configured`

Total tests: **32 passing**

---

## [0.2.2] — 2026-04-08

### Dependency consolidation — Poetry as sole package manager

The three packages previously pip-installed in the Dockerfile
(`arize-phoenix-otel`, `openinference-instrumentation-langchain`, `openai`)
are now regular Poetry dependencies in `pyproject.toml`. The pip workaround
is removed.

#### Background

In v0.0.1 (March 2026), `arize-phoenix-otel` declared narrow Python version
constraints (e.g., `>=3.13,<3.14`) that conflicted with the project's
`python = "^3.11"`. Poetry's resolver could not find compatible versions,
so these packages were installed via pip in the Dockerfile as a workaround.

The upstream constraint is now `>=3.10,<3.15`. Poetry can resolve this with
a `python = ">=3.11,<3.15"` marker on the dependency, making the pip
workaround unnecessary.

#### Changes

**`pyproject.toml`**
- Added `openai = "^1.58"`, `arize-phoenix-otel = {version = "^0.15", python = ">=3.11,<3.15"}`,
  and `openinference-instrumentation-langchain = {version = "^0.1", python = ">=3.11,<3.15"}`
  as regular dependencies
- Removed stale comment about Poetry resolver conflicts
- Version bumped `0.2.1` → `0.2.2`

**`poetry.lock`**
- Regenerated with all dependencies pinned

**`Dockerfile`**
- Upgraded Poetry from 1.8.2 to 2.3.3 (required to read lock-version 2.1)
- Removed `RUN pip install` block — Poetry installs everything
- `COPY` now includes `poetry.lock` alongside `pyproject.toml`
- Removed stale comments about pip workaround

**Documentation** — removed pip-workaround explanations from:
- `RUNNING.md` — venv setup simplified; no separate pip step for tracing
- `README.md` — same simplification
- `docs/docker-spec.md` — notes rewritten; version bumped to 2.2

#### What this achieves

| Before | After |
|--------|-------|
| Two install steps in Dockerfile (Poetry + pip) | One install step (Poetry) |
| Poetry 1.8.2 in container, 2.3.x locally | Poetry 2.3.3 everywhere |
| pip deps resolved fresh each build | `poetry.lock` committed — reproducible builds |
| pip deps invisible to `poetry show` | All deps visible and version-locked |
| Six files explaining the workaround | Clean docs, no stale caveats |

Total tests: **14 passing** (unchanged)

## [0.2.1] — 2026-04-08

### Tool output quality eval + dataset curation

Fourth evaluation metric and automatic dataset curation from eval results.

#### Tool Output Quality eval

New `evaluations/metrics/tool_output_quality.py` judges whether tool outputs
contain relevant, plausible, and correctly-targeted data. This is independent
of the existing Tool Usage Correctness eval (which checks tool *selection*).

Three-tier labels: `good` (all outputs relevant and plausible), `degraded`
(minor issues but data is usable), `poor` (wrong destinations, implausible
prices, or mostly empty results).

This is the hardest eval prompt to calibrate. Check the `explanation` field
in Phoenix after running evals — if the judge is miscalibrating (e.g.,
flagging realistic prices as implausible), adjust the range guidance in the
prompt.

#### Per-outcome datasets

`run_evals.py` now creates per-outcome datasets automatically:
- `frustrated_interactions` (existing — kept)
- `tool_incorrect_interactions` — traces where tool selection was wrong
- `incomplete_interactions` — traces with unintentionally missing sections
- `poor_tool_output_interactions` — traces where tool data was bad

#### Golden set

A `golden_set` dataset is created from traces where ALL four evals scored
positive. This is the regression test suite: before deploying a prompt change,
re-run these queries and compare eval scores. If a previously-good trace now
fails, the change regressed something.

#### Changes

**`evaluations/metrics/tool_output_quality.py`** *(new file)*
- `TOOL_OUTPUT_QUALITY_PROMPT` — LLM-as-judge prompt with criteria for
  relevance, plausibility, targeting, and completeness

**`evaluations/run_evals.py`**
- Added fourth eval: Tool Output Quality (`good`/`degraded`/`poor`)
- `_upload_outcome_dataset()` helper for DRY dataset creation
- Per-outcome datasets for all four evals
- Golden set creation from intersection of all positive results

**`tests/test_evals.py`** *(new file)*
- `test_tool_output_quality_prompt_importable`
- `test_all_eval_prompts_have_required_template_vars`

Total tests: **30 passing**

## [0.2.0] — 2026-04-08

### Token/cost tracking and latency budgets

Every request now reports token usage, estimated cost, and latency breakdown.

#### Token tracking

A `TokenUsageTracker` callback handler is created per request and attached to
`config["callbacks"]`. It accumulates token counts across all LLM calls —
validation classifiers and agent — with per-model breakdowns for cost estimation.

The agent model now sets `stream_usage=True`, which makes OpenAI report token
counts in the final streaming chunk. Without this, the SSE streaming endpoint
would record zero tokens.

#### Cost estimation

Approximate cost computed from per-model rates defined in `_COST_PER_1M_TOKENS`.
Rates are module-level constants — update them when OpenAI changes pricing.
Unknown models get zero cost, not an error.

#### Latency budgets

Two phases timed separately with `time.monotonic()`:
- Validation phase (all `validate_place` + `validate_preferences` calls)
- Agent phase (`agent.invoke` / `agent.astream`)

The `timing.sla_exceeded` flag is `true` when total request time exceeds
`_SLA_TOTAL_S` (default 35 seconds). The budget is also recorded as
`travelshaper.sla.budget_ms` span metadata for Phoenix dashboards.

#### Response schema changes

`/chat` response and SSE `done` event now include:
```json
{
  "response": "...",
  "run_id": "...",
  "usage": {
    "prompt_tokens": 600,
    "completion_tokens": 820,
    "total_tokens": 1420,
    "estimated_cost_usd": 0.01485,
    "llm_calls": 4,
    "by_model": { "gpt-4o": {"...": "..."}, "gpt-5.3-chat-latest": {"...": "..."} }
  },
  "timing": {
    "validation_ms": 1200.5,
    "agent_ms": 18500.3,
    "total_ms": 19700.8,
    "sla_exceeded": false,
    "sla_budget_ms": 35000
  }
}
```

#### Changes

**`agent.py`**
- Added `stream_usage=True` to agent model constructor
- `llm_call` node now accepts `config: RunnableConfig` and propagates it to
  `model_with_tools.invoke()`, fixing callback propagation for token tracking

**`api.py`**
- `_COST_PER_1M_TOKENS` rate table (gpt-4o, gpt-4o-mini, gpt-5.3-chat-latest)
- `_SLA_VALIDATION_S`, `_SLA_AGENT_S`, `_SLA_TOTAL_S` budget constants
- `TokenUsageTracker` callback class with per-model accumulation
- `_build_timing()` helper for latency breakdown and SLA detection
- Both endpoints: create tracker, time phases, include `usage` + `timing`
- `_stream_agent` accepts timing params, enriches `done` event
- Span metadata: `travelshaper.total_tokens`, `travelshaper.estimated_cost_usd`,
  `travelshaper.sla.budget_ms`, `travelshaper.sla.exceeded`

**`tests/test_api.py`** — 3 new tests

Total tests: **28 passing**

---

## [0.1.9] — 2026-04-06

### User feedback capture

Users can rate travel briefings with thumbs up / thumbs down via the browser
UI. Feedback is stored locally in `feedback.jsonl` and can be synced to
Phoenix as "User Feedback" annotations on traces.

#### Design: storage-first, sync later

The `/feedback` endpoint writes to `feedback.jsonl` and returns immediately
(~1ms). Phoenix annotation happens either best-effort at request time or via
`python -m scripts.sync_feedback` as a batch operation. Feedback is never
lost due to Phoenix downtime.

A simple in-memory rate limiter prevents abuse: max 20 submissions per session
per 5-minute window.

#### Changes

**`api.py`**
- `FeedbackRequest` / `FeedbackResponse` Pydantic models
- `POST /feedback` endpoint with score validation and rate limiting
- `_store_feedback()` — appends to `feedback.jsonl`
- `_sync_feedback_to_phoenix()` — best-effort span annotation
- `_check_feedback_rate()` — in-memory per-session rate limiter

**`scripts/sync_feedback.py`** *(new file)*
- Batch sync: reads unsynced entries, matches to Phoenix spans, logs
  annotations, marks as synced. Safe to run repeatedly.

**`static/index.html`**
- Thumbs up / thumbs down widget on result screen
- `sendFeedback(score)` posts to `/feedback` with `run_id` + `session_id`
- Buttons disable after submission; widget resets on new briefing

**`tests/test_api.py`** — 3 new tests + autouse cleanup fixture

**`.gitignore`** — added `feedback.jsonl`

Total tests: **25 passing**

---

## [0.1.8] — 2026-04-06

### Session identity, prompt versioning, and guardrail span tagging

Three trace-quality improvements shipped together because they touch the same
RunnableConfig metadata construction in `api.py`.

**Session identity:** The browser generates a stable session ID
(`crypto.randomUUID()`) on page load and sends it with every request. Phoenix
Sessions tab now groups all requests from the same browser session.

**Prompt versioning:** Named version constants (`save_money_v1`,
`full_experience_v1`) and a single `get_prompt_version()` function in
`agent.py` replace the duplicated keyword matching in `api.py`. Every trace
carries `travelshaper.prompt_version` for filtering in Phoenix. Bump the
version suffix when editing prompt text to compare eval scores across
revisions.

**Guardrail span tagging:** Validation classifier LLM spans now carry
`travelshaper.span_type: "guardrail"`, `travelshaper.guardrail.name`, and
`travelshaper.guardrail.field`. Root spans carry `travelshaper.guardrails.count`
and `travelshaper.guardrails.blocked` for dashboard-level guardrail monitoring.
Validation outcome attributes (`travelshaper.validation.departure`, etc.)
record whether each field was valid, corrected, failed, or skipped.

#### Changes

**`agent.py`**
- Added `SAVE_MONEY_PROMPT_VERSION`, `FULL_EXPERIENCE_PROMPT_VERSION` constants
- Added `_PROMPT_REGISTRY` dict and `_BUDGET_KEYWORDS` tuple
- Added `get_prompt_version(message)` — single source of truth for voice routing
- `get_system_prompt()` now delegates to `get_prompt_version()`
- `route_and_inject()` uses `get_prompt_version()` internally

**`api.py`**
- `ChatRequest` accepts optional `session_id` field
- Imported `get_prompt_version` from `agent`
- Added `_guardrail_metadata()` helper
- `/chat` and `/chat/stream` config uses client `session_id` (falls back to `run_id`)
- `budget_mode` derived from `prompt_version` (no more duplicated keyword check)
- Validation calls pass guardrail metadata through config
- Root span metadata includes guardrail summary and validation outcomes
- `_llm_json` preserves caller's `run_name` and metadata

**`static/index.html`**
- Generates `SESSION_ID` via `crypto.randomUUID()` on page load
- Sends `session_id` with every `/chat/stream` request

**`tests/test_api.py`** — 5 new tests:
- `test_chat_uses_client_session_id`
- `test_chat_falls_back_to_run_id_without_session`
- `test_chat_sets_budget_prompt_version`
- `test_chat_sets_full_experience_prompt_version`
- `test_chat_records_guardrail_metadata`

**`tests/test_agent.py`** — 1 new test:
- `test_prompt_version_routing`

Total tests: **22 passing**

## [0.1.7] — 2026-04-06

### Debug trace URL

When `TRAVELSHAPER_DEBUG=true` is set, the `/chat` response includes a `debug`
object with `run_id` and a clickable Phoenix `trace_url`. The SSE `done` event
now always includes `run_id` regardless of debug mode (needed for feedback
capture in a future PR).

#### Changes

**`api.py`**
- Added `_DEBUG` and `_PHOENIX_UI_URL` config from environment variables
- Added `_phoenix_trace_url()` helper
- `/chat` response now includes `run_id` always and `debug` object when debug enabled
- `/chat` endpoint returns plain dict instead of `ChatResponse` model (enables conditional fields)
- `_stream_agent` accepts `run_id` parameter, includes it in `done` SSE event

**`static/index.html`**
- Stores `window._lastRunId` from SSE `done` event for future feedback use

**`.env.example`**
- Added `TRAVELSHAPER_DEBUG=false` and `PHOENIX_UI_URL=http://localhost:6006`

**`tests/test_api.py`**
- `test_chat_includes_debug_when_enabled` — debug object present when flag on
- `test_chat_excludes_debug_when_disabled` — debug object absent when flag off

Total tests: **16 passing**

## [0.1.6] — 2026-04-06

### Validation spans nested under request trace

Validation classifier LLM calls (`validate_place`, `validate_preferences`)
now inherit the parent `RunnableConfig` from the request endpoint so their
spans appear nested under the `travelshaper_chat` / `travelshaper_stream`
chain in Phoenix, rather than as orphaned root-level spans.

#### Changes

**`api.py`**
- `_llm_json()` accepts an optional `config: RunnableConfig` parameter and
  merges it with `run_name: "validation_classifier"` before invoking the LLM
- `validate_place()` accepts an optional `config` parameter and forwards it
  to `_llm_json()`
- `validate_preferences()` accepts an optional `config` parameter and
  forwards it to `_llm_json()`
- `/chat` endpoint passes `config` to both `validate_place()` and
  `validate_preferences()`
- `/chat/stream` endpoint passes `stream_config` to both validation functions

**`tests/test_api.py`**
- Updated `assert_called_once_with` to accept the new `config` kwarg
- Updated `side_effect` function signature to accept optional `config`

#### Trace structure (before → after)

| Before | After |
|--------|-------|
| 4 root spans: 1 chain + 3 orphaned LLM | 1 root chain span with 3 LLM children |
| Validation spans not linked to request | Validation spans nested under request trace |
| Phoenix shows 4 separate traces per request | Phoenix shows 1 trace per request |

Total tests: **14 passing** (unchanged)

## [0.1.5] — 2026-04-06

### Tracing & observability consolidation

All tracing now flows through LangChain's callback/instrumentor system. Only
`agent.py._init_tracing()` imports OTEL packages — `api.py` no longer touches
`opentelemetry` directly. Swapping trace backends (LangSmith, Datadog, etc.)
requires changing one function.

#### Changes

**`agent.py`**
- Wrapped the top-level Phoenix/OTEL tracing block in a named
  `_init_tracing()` function with a docstring marking it as the single OTEL
  integration point. Called immediately after definition — behaviour unchanged
- Added `config={"run_name": "travelshaper_llm_call"}` to
  `model_with_tools.invoke()` so the LLM span gets a descriptive name in traces

**`api.py`**
- Replaced `from openai import OpenAI` and the `_openai` client with
  `langchain_openai.ChatOpenAI`. Validation classifiers now appear as traced
  LangChain LLM spans with `run_name: "validation_classifier"`
- Removed `from opentelemetry import trace as otel_trace` and the
  `if otel_trace is not None` branching in the `/chat` endpoint
- Added `RunnableConfig` with request-level metadata (`travelshaper.destination`,
  `travelshaper.departure`, `travelshaper.budget_mode`,
  `travelshaper.has_preferences`) and `run_name` to both `/chat` and
  `/chat/stream` endpoints. The LangChain instrumentor propagates this metadata
  to all child spans automatically
- Updated `_stream_agent` signature to accept an optional `RunnableConfig` and
  forward it to `agent.stream()`

**`evaluations/run_evals.py`**
- Added `_find_col(df, candidates)` helper for defensive column discovery
- Replaced all five hardcoded references to `attributes.input.value` /
  `attributes.output.value` with candidate-list lookups that fall back gracefully
  across Phoenix instrumentor versions
- Added a diagnostic warning when expected columns are not found, printing
  available input/output column names to aid debugging

**`Dockerfile`**
- Updated pip install comment to note `openai` is kept as an explicit transitive
  dependency for `langchain-openai` version stability

**Documentation**
- `README.md` — updated design decisions, troubleshooting, and venv setup to
  reflect that `api.py` no longer imports the `openai` SDK directly
- `docs/ARCHITECTURE.md` — rewrote section 7.1 (Instrumentation) and 7.3
  (Trace structure) to describe `_init_tracing()`, `RunnableConfig` metadata,
  `run_name` labels, and validation classifier span visibility
- `docs/docker-spec.md` — updated pip install comment and `openai` rationale
- `RUNNING.md` — updated test count from 8 to 14

#### What this achieves

| Before | After |
|--------|-------|
| `api.py` imports `opentelemetry` directly | Only `agent.py._init_tracing()` knows about OTEL |
| Validation LLM calls invisible to tracing | Traced as LangChain LLM spans via `ChatOpenAI` |
| `/chat/stream` has no request-level trace metadata | Gets `RunnableConfig` with metadata and `run_name` |
| Eval script hardcodes column names | Defensive discovery with fallback and warnings |
| Swapping OTEL provider requires touching 2+ files | Change one function: `_init_tracing()` |

Total tests: **14 passing** (unchanged)

---

## [0.1.2] — 2026-03-23

### Two changes: place validation + Tribeca art-house UI

#### 1. Place name validation

**`api.py`** — new `validate_place(name, field) → PlaceValidationResult`
using `gpt-4o` with a geographic classifier prompt. Handles four cases:

- **Valid** — recognisable real place; returns `canonical` (standardised
  English name, e.g. "SF" → "San Francisco, California, USA")
- **Corrected** — misspelling of an identifiable place; returns both
  `corrected` and `canonical`; agent proceeds with the corrected name
- **Ambiguous** — multiple real places match (e.g. "Springfield",
  "Georgia"); returns `valid=False` with a disambiguation prompt
- **Invalid/fake** — unrecognisable or fictional; returns `valid=False`
  with a user-friendly message
- **Prompt injection** — malicious content in place field; rejected safely

Both `departure` and `destination` fields on `ChatRequest` are validated
before the agent is invoked, in both the sync `/chat` and SSE
`/chat/stream` endpoints.

**`/chat/stream` SSE events added:**
- `place_error` — `{field, message}` — invalid place; UI highlights the
  field and shows the message on the form screen
- `place_corrected` — `{field, original, canonical}` — auto-correction
  happened; UI shows a teal banner after the result loads

**`static/index.html`** — correction banner + field highlighting:
- Teal `correction-banner` div appears on the result screen when a name
  was auto-corrected: "Departure interpreted as: San Francisco, California"
- The offending input field gets a red border on `place_error` with focus

**`tests/test_api.py`** expanded to 8 API tests (was 5):
- `test_chat_accepts_valid_places` — valid place passes through
- `test_chat_rejects_invalid_place` — fake place → 400, agent not called;
  uses `side_effect` mock so departure passes and destination fails
- `test_chat_auto_corrects_misspelled_place` — "Tokio" → "Tokyo, Japan",
  agent is still called with corrected name

#### 2. Tribeca art-house UI redesign

Complete visual rebuild of `static/index.html`.

**Aesthetic:** Black-and-white editorial with a single hot accent (sunset
orange). Raw, architectural, poster-like. Think: a gallery on Franklin
Street, a cast-iron loft, an art magazine at the MoMA bookshop.

**Fonts:**
- **Bebas Neue** — ultra-condensed display, all-caps, pure poster energy.
  Used for form headline, loading title, section numbers, result hero,
  nav logo. Sizes from 26px up to `clamp(56px, 10vw, 120px)`.
- **Cormorant Garamond** — italic serif for elegance and contrast.
  Used for the "The world is waiting." sub-headline and section subtitles.
- **DM Sans** — clean, minimal body. All form labels, body copy, metadata.

**Layout principles:**
- No card boxes or rounded corners — everything is ruled lines and raw white
- Three-weight border system: 3px black (section openers), 1px rule, 1.5px
  form borders
- Form inputs have a brutalist `box-shadow: 3px 3px 0 var(--black)` on focus
- CTA button is flat orange with a `4px 4px 0 black` drop shadow that
  animates on hover (lift + larger shadow)
- Report sections numbered 01–04 with giant muted numerals as section markers
- Bullet dots replaced with an em dash `—`
- Hyperlinks: black text, orange underline, 2px thick
- Loading screen: animated sliding orange bar instead of a spinner
- Responsive: single-column below 780px, sidebar moves below with a 3px
  black top border; all type scales with `clamp()`

**`pyproject.toml`** — version bumped `0.1.1` → `0.1.2`

Total tests: **14 passing**

---

## [0.1.1] — 2026-03-23

### Four changes: real-time status, model updates, typography, writing style

#### 1. Real-time SSE status during agent execution

**`api.py`** — new `POST /chat/stream` endpoint using `StreamingResponse`
with `media_type="text/event-stream"`. Uses LangGraph's `.stream()` with
`stream_mode="updates"` to emit one event per node execution:

- When `llm_call` produces tool_calls → emits `status` event with the
  specific tool label (✈️ Searching flights, 🏨 Finding hotels, etc.)
- When `llm_call` produces a final message (no tool_calls) → emits
  "✍️ Writing your personalised briefing"
- When `tool_node` executes → emits "📊 Processing search results"
- On completion → emits `done` event with the full response text
- On error → emits `error` event

Event format: standard SSE `event: <type>\ndata: <json>\n\n`

The original `POST /chat` endpoint (synchronous, returns full JSON) is
unchanged — curl, pytest, and all non-browser clients continue to work.

**`static/index.html`** — loading screen redesigned:
- Replaces hardcoded animated steps with a live `status-feed` div
- `addStatus(message, state)` appends a new `.status-item` element per
  SSE event, marks the previous item as `.done`
- Active item has a pulsing dot; done items turn teal
- 600ms pause after the "ready" status so users can see it before the
  result transitions in
- Validation errors from SSE (`validation_error` event) route back to
  the form screen with the rejection message

#### 2. Model updates

- **Agent:** `gpt-4.1` → `gpt-5.3-chat-latest`
- **Validator:** `gpt-4.1-mini` → `gpt-4o` (more reliable classification)

#### 3. Typography and spacing

- **Fonts:** Cormorant Garamond replaced with **Cormorant Garamond** for
  display; body switched to **Poppins** (geometric, designer-grade, highly
  legible at large sizes)
- **Body size:** 15px → **18px** with line-height 1.85
- **Paragraph gap:** 16px between paragraphs in report sections
- **Card title:** 32px → **52px** italic Cormorant Garamond
- **Result hero title:** 42px → **58px** italic bold
- **Section titles:** 20px → **26px** italic bold
- **Loading title:** 26px → **36px** italic
- Card padding: 40px → **48px**; rep-body padding: 22px → **28px 32px**;
  hero padding: 36px → **48px 52px**

#### 4. Writing style — Robin Leach + Pharrell Williams

`SYSTEM_PROMPT` completely rewritten with a new voice section:
- **Robin Leach:** theatrical, aspirational, vivid sensory prose —
  "sanctuaries of refined indulgence", cinematic openers per section
- **Pharrell:** infectious joy, warmth, celebratory energy, inclusive
  enthusiasm — "trust us, you are going to LOVE this"
- Combined opening hook required before every briefing
- Section headers reframed as editorial titles:
  "✈️ Getting There — Your Chariot Awaits"
  "🏨 Where to Stay — Your Home Away From Home"
  "🗺️ Before You Go — The Insider Brief"
  "📍 What to Do — The Real Itinerary"
- Required memorable closing line at end of every briefing
- SECTIONS matcher updated to catch new header vocabulary
  (chariot, sanctuary, insider brief, real itinerary)

**`pyproject.toml`** — version bumped `0.1.0` → `0.1.1`

---

## [0.1.0] — 2026-03-23

### Three changes: UI redesign, model upgrade, hyperlinks in reports

#### 1. UI redesign — new brand palette and typography

Complete visual overhaul of `static/index.html`.

**Palette (exact values from spec):**
- Primary Ocean Blue `#0F4C81` — header, form labels, section titles, sidebar hover
- Secondary Deep Teal `#006D77` — hyperlinks, checked interest chips
- Accent / CTA Sunset Orange `#FF7A00` — submit button, bullet dots, form logo mark, eyebrow text
- Text / UI Dark Slate `#1F2937` — body copy
- Background Cloud `#F8FAFC` — page background, input backgrounds
- Base White `#FFFFFF` — cards, sections

**Typography:**
- **Fraunces** (display / optical size variable font) — card titles, result title, section titles, loading title. Larger sizes: card title 32px, result hero 42px, section titles 20px.
- **Sora** (geometric sans) — all body text, labels, form fields, buttons

**Visual changes:**
- Header: sticky, primary blue with orange logo mark and version badge
- Form card: rounded-xl corners, larger title hierarchy, orange CTA button with shadow and hover lift
- Budget toggle: primary blue when selected (was green)
- Interest chips: teal when selected
- Result hero: gradient banner (primary → teal) with decorative circles
- Report sections: icon box with orange-light background, teal hyperlinks, hover shadow
- Sidebar: primary blue route text, slide-right hover animation
- Bullet dots changed from gold to sunset orange

#### 2. Model upgrade

- **Agent:** `gpt-4o` → `gpt-4.1` (better instruction following, stronger at agentic tasks)
- **Validator:** `gpt-4o-mini` → `gpt-4.1-mini` (faster, cheaper, stronger than 4o-mini)

#### 3. Hyperlinks in every report recommendation

**`agent.py` — SYSTEM_PROMPT updated:**
Added a "Hyperlinks — REQUIRED" section instructing the model to include a
markdown `[Name](URL)` link for every named place, restaurant, hotel,
attraction, neighborhood, airline, and activity. Provides examples and
fallback URL patterns (Google Maps, Google Search) for cases where an
official website is not known.

**`static/index.html` — `renderInline()` updated:**
Added regex to convert `[text](url)` → `<a href="url" target="_blank"
rel="noopener noreferrer">text</a>`. Links are styled in Deep Teal with
underline, hover transition to Primary Blue. Works in both sectioned report
cards and the raw fallback renderer. The order of replacement matters:
links are rendered before bold/italic to avoid conflicts.

#### Other changes
- `pyproject.toml` version bumped `0.0.9` → `0.1.0`
- `api.py` version string updated to `0.1.0`
- Loading screen last step updated: "Compiling your briefing with links"

---

## [0.0.9] — 2026-03-22

### Feature: Free-form preferences field with LLM safety validation

#### Free-form preferences (Change 1)

A new optional `preferences` field (max 500 characters) is added to both
the API and the UI. It accepts free-form text describing additional
considerations the user wants applied to web search queries — things like
dietary restrictions, mobility needs, travel companions, or style
preferences that don't fit the structured form fields.

The field is passed to the agent framed explicitly as DuckDuckGo search
context: *"Additional context for web search queries (use when calling
duckduckgo_search to refine results): …"*. This ensures the agent knows
to apply the text to general web queries rather than the structured SerpAPI
tools.

#### LLM safety validation (Change 2)

All non-empty `preferences` values are validated by `gpt-4o-mini` before
the main agent is invoked. The classifier uses a strict system prompt that:

- **Allows** legitimate travel preferences: dietary restrictions, health
  and mobility needs, travel style, interest refinements, budget details,
  companion context
- **Rejects** illegal requests, adult content, hate speech, prompt
  injection attempts, credential extraction, and off-topic attack vectors

If validation fails, the API returns **HTTP 400** with a user-facing
explanation. The main agent is **never invoked** with unvalidated content.
Empty or whitespace-only preferences bypass validation entirely.

The UI handles a 400 response by returning to the form screen and
displaying the rejection reason — the user never sees the loading screen
for a rejected request.

#### Changes

**`api.py`**
- Added `VALIDATION_SYSTEM_PROMPT` constant — the classifier prompt
- Added `ValidationResult` Pydantic model
- Added `validate_preferences(text) → ValidationResult` — calls
  `gpt-4o-mini` at temperature 0; returns `valid=False` on any error
- Added `build_agent_message(base, preferences)` — appends validated
  preferences framed as DuckDuckGo context
- Updated `ChatRequest` — added `preferences: str | None` field
  (max_length=500)
- Updated `chat()` endpoint — validates preferences before agent invocation;
  raises HTTP 400 if invalid
- Added `openai` import and `_openai` client instance
- Version string updated to `0.0.9`

**`static/index.html`**
- Added `<textarea id="preferences">` with `maxlength="500"` below the
  interest chips
- Live character counter (`updateCharCount()`) turns amber at 450, red at
  500
- Field note: *"Used to refine web search queries. Content is
  safety-checked before use."*
- `onSubmit` reads the preferences value and includes it in the fetch
  body only when non-empty
- 400 responses are handled gracefully: returns to the form screen and
  shows the rejection message rather than displaying an error on the
  loading screen

**`tests/test_api.py`**
- Expanded from 2 tests to 5:
  - `test_health_endpoint` (unchanged)
  - `test_chat_endpoint_accepts_message` (unchanged)
  - `test_chat_accepts_valid_preferences` — mocks validate to pass, asserts
    agent is called and validate was called with the correct text
  - `test_chat_rejects_invalid_preferences` — mocks validate to fail,
    asserts 400 returned and agent.invoke never called
  - `test_chat_skips_validation_for_empty_preferences` — whitespace
    preferences, asserts validate not called

**`pyproject.toml`**
- Version bumped `0.0.8` → `0.0.9`
- Added `openai` as a direct dependency note (installed via pip in Docker)

Total tests: **11 passing**

---

## [0.0.8] — 2026-03-22

### Feature: Structured form UI, history, and directory versioning

#### Web interface redesign
Complete redesign of `static/index.html`. The free-text chat box is
replaced with a structured one-shot trip planning form.

**Form fields:**
- Departure city / region (free text — agent resolves nearest airport)
- Destination (free text)
- Departure date (date picker, min = today)
- Trip duration (1–4 weeks, select)
- Budget preference (Save money / Full experience toggle)
- Interests (6 checkboxes: Food, Arts, Photography, Nature, Fitness, Nightlife)

**One-shot flow:**
The user fills the form, submits once, and receives a single complete
travel briefing. There is no back-and-forth. A "Plan another trip" button
resets the form. This matches the single-turn architecture of the agent.

**Structured message construction:**
The form fields are assembled into a precise natural-language prompt
including departure city, IATA lookup instruction, destination, exact
dates (departure + calculated return), budget, and interests. This
produces more reliable agent responses than open-ended chat.

**Formatted report rendering:**
The agent's markdown response is parsed into named sections
(Getting There, Where to Stay, Before You Go, What to Do) and rendered
as styled cards with section icons, bullet lists, and inline bold
formatting. Falls back to a styled raw view if sections cannot be parsed.

**Trip history:**
The last 10 completed trips are saved to `localStorage` and displayed in
a sidebar on the main page. Each entry shows the route and dates. Clicking
any entry re-renders that trip's briefing. History can be cleared.

**Print / Save as PDF:**
A "Save as PDF" button triggers `window.print()`. Print CSS hides the
header, sidebar, and action buttons so only the report renders cleanly.

#### App structure
- **Versioned directory:** project now lives in `travelshaper-v0.0.8/src/`
  instead of the opaque `se-interview-main/` name. The top-level folder
  carries the version; the source subdirectory uses the standard `src/`
  convention.

#### Other changes
- `pyproject.toml` version bumped `0.0.7` → `0.0.8`
- `api.py` version string updated to `0.0.8`

---

## [0.0.7] — 2026-03-22

### Feature: Browser chat interface

Added a self-contained browser UI served directly by FastAPI. Users can
now interact with TravelShaper at `http://localhost:8000` without using
curl. The REST API (`/chat`, `/health`) is completely unchanged and
coexists with the UI — curl, pytest, and all scripts continue to work
identically.

### Changes

**`static/index.html`** *(new file)*
- Single self-contained HTML/CSS/JS chat interface
- Dark, travel-themed design using DM Serif Display + DM Sans fonts
- Auto-growing textarea; Enter to send, Shift+Enter for newline
- Animated thinking indicator while the agent is working
- Lightweight markdown rendering: `**bold**`, headers, bullet points
- Error state shown inline if the server returns a non-200 response
- No npm, no build step, no external dependencies beyond Google Fonts

**`api.py`**
- Added `from fastapi.staticfiles import StaticFiles`
- Added `app.mount("/", StaticFiles(directory="static", html=True), name="static")` after all API routes — API routes take priority, static mount handles everything else
- Updated app title and version string

**`Dockerfile`**
- Added `RUN mkdir -p /app/static` after `COPY . .` to guarantee the directory exists in the container even on a clean build

**`README.md`** *(updated in documentation pass)*
- Added "Using the Web Interface" section
- Added `GET /` to API endpoint docs
- Added `static/index.html` to project structure

**`docs/PRD.md`** *(updated in documentation pass)*
- Version bumped to 1.1
- Browser UI added to in-scope capabilities table
- `GET /` added to API contract
- Success criteria updated

**`pyproject.toml`**
- Version bumped `0.0.6` → `0.0.7`

---

## [0.0.6] — 2026-03-22

### Problem
Docker build failed at step 6/8 with:
```
The option "--no-lock" does not exist
```
The `--no-lock` flag was introduced in a later version of Poetry.
Poetry 1.8.2 (pinned in our Dockerfile) does not support it.

### Fix
Remove the `--no-lock` flag. Poetry 1.8.2 automatically generates a
lockfile during `install` if one is not present — no flag needed.

### Changes

**`Dockerfile`**
- Removed `--no-lock` from `poetry install` command
- Updated comment to note that Poetry auto-generates the lockfile

**`pyproject.toml`**
- Bumped version `0.0.5` → `0.0.6`

---

## [0.0.5] — 2026-03-22

### Problem
Docker build failed at step 5/8 with:
```
"/poetry.lock": not found
```
The Dockerfile tried to `COPY pyproject.toml poetry.lock ./` but no
`poetry.lock` file exists in the project — it was never generated.

### Root cause
`poetry.lock` is generated by running `poetry lock` locally and should be
committed to the repo. Since it was never generated, the Docker build had
nothing to copy. Rather than requiring users to run `poetry lock` before
building, we drop the lock file requirement from the Docker build entirely.

### Changes

**`Dockerfile`**
- Removed `poetry.lock` from the `COPY` line (now only copies `pyproject.toml`)
- Added `--no-lock` flag to `poetry install` so Poetry resolves dependencies
  fresh from `pyproject.toml` without requiring a lockfile

**`pyproject.toml`**
- Bumped version `0.0.4` → `0.0.5`

---

## [0.0.4] — 2026-03-22

### Problem
TravelShaper container kept restarting with:
```
AssertionError: Status code 204 must not have a response body
```
Installing the full `arize-phoenix` package inside the TravelShaper
container caused a conflict: `arize-phoenix` internally registers FastAPI
routes using `status_code=204` with a response body, which newer versions
of FastAPI correctly reject. The container crashed on startup before
uvicorn could serve a single request.

### Root cause
`arize-phoenix` is the full Phoenix **server** — the UI and ingestion
backend that runs at `http://localhost:6006`. It should never be installed
in the TravelShaper container because we already run it as a separate
service (`arizephoenix/phoenix:latest`) via docker-compose. Installing it
in both containers introduced the FastAPI version conflict.

Our app only needs two lightweight packages to **send** traces:
- `arize-phoenix-otel` — configures the OpenTelemetry exporter
- `openinference-instrumentation-langchain` — auto-instruments LangChain/LangGraph calls

### Changes

**`Dockerfile`**
- Removed `arize-phoenix` and `arize-phoenix-evals` from the `pip install` step
- Kept only `arize-phoenix-otel` and `openinference-instrumentation-langchain`
- Updated comment to explain the separation of concerns

**`pyproject.toml`**
- Bumped version `0.0.3` → `0.0.4`

---

## [0.0.3] — 2026-03-22

### Problem
Phoenix traces were not appearing in the Phoenix UI despite the agent
responding correctly. The Phoenix packages (`arize-phoenix-otel`,
`openinference-instrumentation-langchain`) were missing from the Docker
container because they were removed from `pyproject.toml` in v0.0.1 to
fix Poetry's version resolver conflict. The local venv `pip install` step
was never replicated inside the container, so the instrumentation block
in `agent.py` silently fell through the `except ImportError: pass` and
no traces were sent.

### Changes

**`Dockerfile`**
- Added a `RUN pip install --no-cache-dir` step after `poetry install`
  to install the four Phoenix packages directly:
  `arize-phoenix`, `arize-phoenix-evals`, `arize-phoenix-otel`,
  `openinference-instrumentation-langchain`
- Added a comment explaining why these are installed via pip rather than
  Poetry

**`pyproject.toml`**
- Bumped version `0.0.2` → `0.0.3`

---

## [0.0.2] — 2026-03-22

### Problem
`docker-compose up --build` emitted a warning:
```
the attribute `version` is obsolete, it will be ignored, please remove it to avoid potential confusion
```
Docker Compose v2+ no longer uses the top-level `version` field. It is
silently ignored but produces noise in the build output and could confuse
readers of the file.

### Changes

**`docker-compose.yml`**
- Removed the obsolete top-level `version: "3.8"` line

**`pyproject.toml`**
- Bumped version `0.0.1` → `0.0.2`

---

## [0.0.1] — 2026-03-22

### Problem
`poetry install -E phoenix` failed with a dependency resolution error because
`arize-phoenix-otel` declares narrow Python version constraints (e.g.
`>=3.13,<3.14`) that conflict with the project's `python = "^3.11"` constraint.
Poetry's resolver cannot find a single version of `arize-phoenix-otel` that
satisfies both the project's allowed Python range (3.11–3.13) and the
package's own bounds simultaneously.

### Changes

**`pyproject.toml`**
- Bumped version `0.1.0` → `0.0.1`
- Removed `arize-phoenix`, `arize-phoenix-evals`, `arize-phoenix-otel`, and
  `openinference-instrumentation-langchain` as optional dependencies
- Removed the `[tool.poetry.extras] phoenix` extra
- Added a comment explaining why these packages are excluded and directing
  users to `RUNNING.md`

**`RUNNING.md`**
- Step 1d: replaced `poetry install` / `poetry install -E phoenix` with
  `poetry install -E dev` for core deps, followed by a separate
  `pip install` block for the Phoenix packages
- Added explanation of why `pip` is used instead of a Poetry extra
- Troubleshooting: replaced `poetry install -E phoenix` fix with the correct
  `pip install` command for Phoenix packages
- Removed the "Poetry creates a nested virtualenv" troubleshooting entry
  (no longer relevant now that Phoenix is pip-installed)

**`README.md`**
- Setup section: expanded from a single `poetry install` step to the full
  venv → Poetry → `poetry install -E dev` → optional `pip install` for
  Phoenix flow; added note explaining the Phoenix constraint issue
- `poetry run phoenix serve` → `phoenix serve` (two occurrences)
- Troubleshooting: updated "server does not start" entry to reference venv
  activation and `poetry install -E dev`

---

## [0.0] — 2026-03-22

Initial implementation. See `README.md` for full feature description.
