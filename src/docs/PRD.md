# Product Requirements Document — TravelShaper Travel Assistant

**Version:** 1.3 (v0.3.0 — Observe migration)
**Date:** April 2026
**Status:** Implementation phase
**Author:** [Your Name]

---

## 1. Purpose

This document defines the product requirements for TravelShaper, an AI-powered travel planning assistant built as a technical assessment. TravelShaper extends a LangGraph starter application into a functional travel agent that searches real flight and hotel data, provides cultural preparation guidance, and delivers synthesized trip recommendations — all instrumented with the Traceloop SDK (OpenLLMetry) and a host-side Observe Agent that forwards traces and structured logs to Observe cloud.

> **In one sentence:** TravelShaper is a single-turn, LLM-powered travel planning assistant that combines structured flight and hotel search with interest-based destination intelligence and cultural prep to deliver an explainable, personalized travel briefing for English-speaking American travelers.

---

## 2. Problem Statement

Planning international travel as an American requires navigating multiple disconnected tools: one site for flights, another for hotels, a travel blog for restaurant tips, a government site for visa info, and scattered forum posts for etiquette advice. The traveler does all the synthesis themselves — comparing options, cross-referencing reviews, and figuring out what to pack.

TravelShaper solves this by acting as a single conversational interface that searches across multiple sources, ranks results by the traveler's stated priorities, and delivers one cohesive recommendation that includes logistics, cultural preparation, and interest-based activity suggestions.

---

## 3. Target User

**Primary persona:** English-speaking American adult planning international or domestic leisure travel.

**Assumptions about the user:**
- Knows where they want to go (or has it narrowed to a region)
- Has rough dates or a travel window in mind
- Has a sense of budget preference (save money vs. full experience)
- Has specific interests they want the trip to cater to
- Does not have deep familiarity with the destination's language or customs
- Wants practical, actionable recommendations — not an overwhelming list of options

---

## 4. Jobs to Be Done

When a traveler comes to TravelShaper, they are trying to accomplish one or more of these jobs:

- **"Help me figure out the best way to get there."** — Compare flight options, understand tradeoffs between price, duration, and layovers.
- **"Help me choose where to stay based on my priorities."** — Match hotels to budget, location preferences, and trip style.
- **"Tell me what's worth doing for my interests."** — Surface destination-specific activities tailored to what the traveler actually cares about.
- **"Prepare me so I don't feel unprepared or awkward."** — Provide language basics, etiquette norms, dress expectations, and common mistakes to avoid.
- **"Summarize tradeoffs so I can make a decision faster."** — Explain *why* one option is better for this traveler, not just list options.

---

## 5. Non-goals

TravelShaper is explicitly **not** intended to:

- Complete bookings or process payments
- Manage airline loyalty accounts or hotel reward programs
- Guarantee real-time inventory accuracy or fare holds
- Provide persistent conversation memory across separate `/chat` requests
- Act as a comprehensive rail or ferry booking engine
- Replace dedicated travel agent services for complex multi-city itineraries

---

## 6. Future Goals

- Highly stylized language support beyond English
- Expanded UX functionality
- Deeper safety and security considerations

---

## 7. Scope

### 7.1 In scope (this implementation)

| Capability | Description |
|------------|-------------|
| Browser chat interface | Self-contained HTML/CSS/JS UI served at `http://localhost:8000` by FastAPI; calls the `/chat/stream` endpoint; coexists with the REST API |
| Flight search | Query Google Flights via SerpAPI; return structured results with prices, airlines, duration, layovers |
| Hotel search | Query Google Hotels via SerpAPI; return structured results with nightly rates, ratings, amenities |
| Cultural guide | Web-search-based research on language basics, etiquette, tipping, dress code, and common mistakes for American travelers |
| Interest discovery | Web search scoped to the traveler's stated interests (food, arts, events, fitness, nature, photography) |
| Synthesized briefing | LLM combines all tool results into a single opinionated travel recommendation |
| Budget-aware ranking | Recommendations are shaped by the traveler's budget preference |
| Place validation | gpt-4o validates departure/destination names, auto-corrects misspellings, rejects fictional places |
| Preference validation | gpt-4o safety-classifies free-form preference text before it reaches the agent |
| Traceloop SDK instrumentation | In-process auto-instrumentation of LangChain / LangGraph / OpenAI; OTLP/HTTP export to `TRACELOOP_BASE_URL` |
| Observe Agent (host) | Receives OTLP traces from the app and tails the JSON log file; forwards both to Observe cloud |
| Observe LLM Explorer integration | Per-request association properties (`user_id`, `chat_id`, `destination`, `budget_mode`, `prompt_version`) for filtering and grouping |
| Structured JSON logging | `logging_config.setup_logging()` writes one JSON record per line to `/app/logs/travelshaper.log` with `trace_id` / `span_id` fields for log/trace correlation |
| Tests | 14 unit tests covering tool schemas, agent graph, and API endpoints + validation |
| Docker | Dockerfile for the application; docker-compose.yml runs only the app and bind-mounts `./logs:/app/logs` for the host-side agent |
| API | FastAPI server with `/chat`, `/chat/stream`, `/health`, and `/feedback` endpoints |

### 7.2 Out of scope (this implementation)

| Capability | Rationale |
|------------|-----------|
| Booking or payment | TravelShaper recommends; it does not transact |
| Multi-turn conversation memory | Current implementation is single-turn; session management is a production enhancement |
| Dedicated train/ferry APIs | Guidance available via general web search but not through structured APIs |
| User accounts or saved trips | No persistence layer beyond Observe traces / logs and local `feedback.jsonl` |
| Automated trace evaluation | Removed during the Observe migration; pending reimplementation against Observe's trace store (prompts preserved in `docs/evaluation-prompts.md`) |
| Phoenix-backed feedback sync | `/feedback` writes to local JSONL only; the response field `synced_to_phoenix` is preserved for the UI but always `false` |
| Full frontend application | The browser UI is a single HTML file for demo use |
| Real-time price alerts | No background jobs or push notifications |
| Multi-language support | English for MVP |

### 7.3 Future roadmap (documented, not built)

**Phase 2 — Conversational depth:** Session-based memory, weather API, richer hotel filtering, caching.

**Phase 3 — Expanded coverage:** Rail APIs, structured event search, destination comparison, rate limiting.

**Phase 4 — Product maturity:** Saved trips, collaborative planning, horizontal scaling, multi-language support.

---

## 8. Functional Requirements

### 8.1 User input

The system accepts a single chat message containing some or all of the following:

| Field | Required | Example |
|-------|----------|---------|
| Origin city | Yes | "Flying from San Francisco" |
| Destination | Yes | "Want to go to Tokyo" |
| Travel dates | Recommended | "Mid-October, about 10 days" |
| Budget preference | Recommended | "Trying to save money" or "Full experience" |
| Interests | Recommended | "Food, photography, and art" |
| Free-form preferences | No | "Vegetarian, travelling with kids" (max 500 chars) |

If required fields are missing, the agent should still attempt a useful response using reasonable defaults rather than refusing to act.

### 8.2 Tool behavior

**search_flights**

| Property | Specification |
|----------|---------------|
| Input | Departure airport code, arrival airport code, outbound date, return date |
| Source | SerpAPI `google_flights` engine |
| Output | List of flight options with: airline, price, duration, number of stops, departure/arrival times, carbon emissions |
| Budget behavior | "Save money" → sort by price ascending; "Full experience" → sort by top flights |
| Error handling | Return a message indicating flights could not be found if SerpAPI returns empty or errors |

**search_hotels**

| Property | Specification |
|----------|---------------|
| Input | Destination query, check-in date, check-out date, number of adults, sort_by |
| Source | SerpAPI `google_hotels` engine |
| Output | List of properties with: name, nightly rate, overall rating, review count, amenities |
| Budget behavior | "Save money" → sort_by=3 (price); "Full experience" → sort_by=13 (rating) |
| Error handling | Return a message indicating hotels could not be found if SerpAPI returns empty or errors |

**get_cultural_guide**

| Property | Specification |
|----------|---------------|
| Input | Destination country/city |
| Source | SerpAPI `google` engine with scoped queries |
| Output | Compiled snippets covering etiquette, phrases, dress code, tipping |
| Error handling | Fall back to LLM's training knowledge if web search returns thin results |

**duckduckgo_search (existing)**

| Property | Specification |
|----------|---------------|
| Input | Free-text search query |
| Source | DuckDuckGo |
| Output | Search result snippets |
| Usage | General fallback for interest-based discovery and questions not covered by specialized tools |

### 8.3 Response synthesis

After all tools return, the LLM produces a single response that:

1. Leads with the most decision-relevant information (flights and hotels)
2. Provides 2–4 options per category, not exhaustive lists
3. Explains *why* each recommendation fits the traveler's stated preferences
4. Includes cultural preparation when a cultural guide was retrieved
5. Includes interest-based suggestions when relevant
6. Notes tradeoffs honestly
7. Acknowledges limitations when data is thin
8. Includes markdown hyperlinks for every named place, hotel, restaurant, and attraction

### 8.4 API contract

**GET /**

Serves the browser chat interface (`static/index.html`). Returns HTTP 200 with the HTML page.

**POST /chat**

Request:
```json
{
  "message": "string (required)",
  "departure": "string or null (optional — triggers place validation)",
  "destination": "string or null (optional — triggers place validation)",
  "preferences": "string or null (optional — max 500 chars, safety-validated)"
}
```

Response (200):
```json
{
  "response": "string"
}
```

Error (400 — validation failure):
```json
{
  "detail": "string or {field, message}"
}
```

**POST /chat/stream**

Same request body as `/chat`. SSE event stream with event types: `status`, `place_corrected`, `place_error`, `validation_error`, `done`, `error`.

**GET /health**

Response:
```json
{
  "status": "ok"
}
```

---

## 9. Agent Architecture

### 9.1 Graph structure

```
START → route_and_inject → llm_call → should_continue?
                                        ├── tool calls present → tool_node → llm_call (loop)
                                        └── no tool calls     → END
```

The `route_and_inject` node selects the appropriate voice-matched system prompt based on budget keywords and injects it into message state. The ReAct loop (llm_call ↔ tool_node) is unchanged from the starter code. The extension adds three new tools to the tool registry and the `route_and_inject` entry node.

### 9.2 System prompt

Two system prompts are defined in `agent.py`, selected at runtime by `route_and_inject`:
- `SYSTEM_PROMPT_SAVE_MONEY` — activated by "save money", "budget", "cheapest", or "spend as little"
- `SYSTEM_PROMPT_FULL_EXPERIENCE` — the default

### 9.3 Tool dispatch logic

The LLM decides which tools to call based on the user's message. Expected behavior:

| User message contains | Tools the agent should call |
|----------------------|----------------------------|
| Origin + destination + dates | `search_flights`, `search_hotels`, `get_cultural_guide` |
| Destination + interests only | `get_cultural_guide`, `duckduckgo_search` |
| General travel question | `duckduckgo_search` |
| "Find me flights from X to Y" | `search_flights` |
| "What should I know before visiting Japan?" | `get_cultural_guide` |

---

## 10. Evaluation Requirements

> **Status:** the automated evaluation pipeline was removed during the
> Observe migration and is pending reimplementation against Observe's
> trace store. The prompt text for each metric is preserved in
> `docs/evaluation-prompts.md` for that future implementation.

### 10.1 User frustration evaluation (deferred)

Detect interactions where the agent's response would likely frustrate the user. LLM-as-judge prompt preserved in `docs/evaluation-prompts.md`.

### 10.2 Tool usage correctness evaluation (deferred)

Assess whether the agent selected appropriate tools and passed valid parameters. Custom LLM-as-judge prompt preserved in `docs/evaluation-prompts.md`.

### 10.3 Answer completeness evaluation (deferred)

Distinguish intentionally scoped responses from unintentionally incomplete ones. Three-tier classification (complete/partial/incomplete) with scope awareness.

### 10.4 Trace volume

A minimum of 11 diverse queries must be traced in Observe, covering full trip planning, partial requests, interest-heavy requests, cultural questions, edge cases, and past-date error handling.

---

## 11. Testing Requirements

### 11.1 Unit tests (14 total)

| Category | Count | What it validates |
|----------|-------|-------------------|
| Tool tests | 4 | Tool formatting, empty results, cultural guide compilation |
| Agent graph tests | 2 | Graph nodes, tool registration |
| API tests | 8 | Health endpoint, chat endpoint, preference validation (valid/invalid/empty), place validation (valid/invalid/auto-correct) |

### 11.2 Test execution

```bash
cd src
pytest tests/ -v
```

All tests pass without requiring external API keys.

---

## 12. Deployment Requirements

### 12.1 Docker Compose (recommended)

```bash
cd src
./setup.sh
```

Exposes TravelShaper on port 8000. The Observe Agent runs on the host (not
in compose); the application reaches it at `TRACELOOP_BASE_URL` (default
`http://localhost:4318`) and writes JSON logs to `./logs/travelshaper.log`,
which the agent's filelog receiver tails.

---

## 13. Success Criteria

This implementation is successful if:

1. The agent responds to travel planning queries with flight, hotel, and cultural recommendations sourced from real APIs
2. Three new tools (`search_flights`, `search_hotels`, `get_cultural_guide`) are integrated into the LangGraph agent
3. The Traceloop SDK exports traces for all LLM calls and tool invocations to the Observe Agent, which forwards them to Observe cloud
4. Structured JSON logs written to `/app/logs/travelshaper.log` carry `trace_id` and are tailed by the Observe Agent, so logs and traces correlate in Observe
5. Per-request association properties (`user_id`, `chat_id`, `destination`, `budget_mode`, `prompt_version`) appear on traces in Observe's LLM Explorer
6. At least 11 diverse queries are visible in Observe
7. The unit test suite passes (no live network calls)
8. A Dockerfile builds successfully
9. A browser chat interface is served at `http://localhost:8000` with SSE streaming
10. Place validation and preference validation protect the agent from bad input
11. The README documents setup, usage, architecture, and design decisions

---

## 14. Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| SerpAPI free tier exhausted | No flight/hotel results | Use mock responses for dev; reserve live queries for demo |
| Empty results for niche destinations | Incomplete briefing | Agent gracefully notes missing data; DuckDuckGo fills gaps |
| OpenAI API latency spikes | Slow responses | Set reasonable timeouts |
| Low-quality cultural guide results | Inaccurate etiquette advice | Agent falls back to training knowledge |

---

MIT License — see [LICENSE](LICENSE).
