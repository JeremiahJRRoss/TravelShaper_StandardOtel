# Presentation Outline — TravelShaper Travel Assistant

**Total time: 20–25 minutes**
**Format: Screen share with live demo**

---

## Slide 1: Title (30 sec)
- "TravelShaper — AI Travel Planning Assistant"
- Your name, date
- One-liner: "A single-turn LLM agent that combines flight search, hotel search, and cultural intelligence into a personalized travel briefing."

---

## Slide 2: The Problem (1 min)
- Planning a trip means bouncing across 5+ sites
- Flights on Google Flights, hotels on Booking.com, etiquette on random blogs, "what to wear" on forums
- Three pain points: fragmentation, decision fatigue, missing cultural context
- "What if one agent did all of this and explained its reasoning?"

---

## Slide 3: Product Overview (1 min)
- 5 structured form inputs: departure city, destination, departure date, duration, budget mode
- Interests: 6 checkboxes (Food, Arts, Photography, Nature, Fitness, Nightlife)
- Optional free-form preferences field (500 chars, LLM-validated before use)
- 4 tools: flights, hotels, cultural guide, web search
- 1 output: a synthesised travel briefing with hyperlinks for every named recommendation
- Browser UI at `http://localhost:8000` — no curl required for the demo
- Target user: English-speaking American leisure traveller

---

## Slide 4: Agent Architecture (3 min)
- Show the LangGraph graph diagram
- START → route_and_inject → llm_call → should_continue → tool_node → llm_call → END
- "`route_and_inject` selects the voice at graph entry. The ReAct loop itself is unchanged from the starter app — I only added tools."
- Walk through the 4 tools: what each does, what API backs it
- Explain why SerpAPI: one key, three engines, structured JSON, free tier

**Key point:** The LLM decides which tools to call. No hardcoded routing.

---

## Slide 5: Tool Deep Dive (2 min)
- Show tool interface pattern: `@tool` decorator, typed args, docstring, error handling
- "The docstring is the prompt — GPT-5.3 reads it to decide when to invoke the tool"
- Show the adapter principle: tools return Pydantic-modelled formatted strings, not raw JSON
- Show error handling: tools never raise into the agent loop

---

## Slide 6: System Prompt Design (1.5 min)
- **Two prompts, not one** — budget mode selects the voice at runtime via `route_and_inject()`
- **Save money:** Bourdain's honesty + Billy Dee Williams' cool + Gladwell's narrative intelligence. Budget is philosophy, not compromise.
- **Full experience:** Robin Leach's spectacle + Pharrell's joy + Salman Rushdie's prose depth. Cities as mythology.
- Both prompts share: mandatory hyperlinks for every named recommendation, cinematic opener, memorable closing line
- Key insight: two separate prompts rather than one with conditional instructions — the model commits fully to one voice instead of blending

---

## Slide 7: Observability — OpenTelemetry & Traceloop (3 min)

**Explain the concepts:**
- **OpenTelemetry** — the industry standard for distributed tracing
- **Traceloop SDK (OpenLLMetry)** — auto-instruments LangChain/LangGraph and OpenAI calls and emits OTel spans with GenAI-specific attributes
- **Traces vs. Spans:**
  - A **trace** is the full lifecycle of one user request
  - A **span** is a single step (one LLM call, one tool execution)
- **Observe** consumes these traces (via the Observe Agent on the host) and provides the UI for exploring them, alongside the structured JSON logs the app writes to `/app/logs/travelshaper.log`

**Show in Observe:**
- A real trace from the demo queries
- Point out the root span, LLM spans, tool spans
- Show token counts, latency per span, tool inputs/outputs

---

## Slide 8: Traces in Action (2 min)
- Show 2-3 different trace patterns:
  1. Full trip query (4 tool calls, 2 LLM calls)
  2. Cultural guide only (1 tool call)
  3. Vague query (web search fallback)
- "You can see exactly what the agent decided to do and why"
- Show how latency breaks down: most time is in external API calls

---

## Slide 9: Evaluation (3 min)
- Three metrics: User Frustration, Tool Usage Correctness, Answer Completeness
- All use LLM-as-judge pattern: send trace data to GPT-4o with an evaluation prompt
- **User Frustration:** detects incomplete answers, ignored requests, fabricated details
- **Tool Correctness:** checks if the right tools were called with valid parameters (custom prompt)
- **Answer Completeness:** three-tier classification with scope awareness (custom prompt)
- The automated eval pipeline was removed during the Observe migration — the prompts (see `evaluation-prompts.md`) are preserved for reimplementation against Observe's query/dataset features or an external eval runner
- "This is how you'd build a feedback loop — identify failure cases, create a dataset, fine-tune or adjust prompts"

---

## Slide 10: Deployment Architecture Design (3 min)
- Show the production architecture diagram:
  - Load balancer → N stateless TravelShaper instances → external APIs
  - Redis for caching + future session memory
  - Observe Agent (host-side) receives Traceloop OTLP spans and tails JSON logs, forwarding both to Observe
- **Scaling strategy:** horizontal scaling is easy because the app is stateless
- **Cost considerations:** OpenAI is the dominant cost (~$0.02-$0.08/query), SerpAPI free tier supports ~60-125 briefings/month

---

## Slide 11: Live Demo (5 min)
1. Show the app running (curl to /health)
2. Send a full trip planning query
3. Walk through the response — point out flights, hotels, cultural prep, interest suggestions
4. Switch to Observe — show the trace landed via the Observe Agent
5. Show spans: LLM calls, tool calls, latency breakdown
6. Show the corresponding structured JSON log lines from `/app/logs/travelshaper.log` correlated by trace id
7. Optionally: send a second query to show different tool dispatch

**Demo options:**

Option A — Browser UI (recommended):
```
Open http://localhost:8000
Fill in: San Francisco → Tokyo, 2 weeks, save money, food + photography
Click "Plan my trip →" and watch the live SSE status feed
```

Option B — curl:
```bash
curl -s http://localhost:8000/health | python3 -m json.tool

curl -s -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Flying from San Francisco to Tokyo, mid-October, 10 days, save money, love food and photography.",
    "departure": "San Francisco, CA",
    "destination": "Tokyo, Japan"
  }' | python3 -m json.tool
```

---

## Slide 12: What I'd Do Next (1 min)
- Multi-turn conversation memory (Redis-backed session state)
- Weather API for data-driven packing advice
- Dedicated train/ferry search (Trainline, Omio)
- Response caching to reduce SerpAPI cost and latency
- Google Places Autocomplete as a client-side layer on top of LLM place validation

---

## Slide 13: Q&A
- "Happy to dig into any part of the architecture, evaluation approach, or tool design"

---

## Timing summary

| Section | Minutes |
|---------|---------|
| Title + Problem + Overview | 2.5 |
| Agent Architecture + Tools | 5 |
| System Prompt | 1.5 |
| Observability (OTEL/Traceloop/Observe) | 5 |
| Evaluation | 3 |
| Deployment Architecture | 3 |
| Live Demo | 5 |
| What's Next + Q&A | 1.5 |
| **Total** | **~26 min** |

---

## Preparation checklist

- [ ] TravelShaper running: `docker compose up -d` from `src/`
- [ ] Browser open at `http://localhost:8000` — confirm UI loads
- [ ] Observe Agent running on the host and receiving OTLP HTTP on port 4318
- [ ] Observe workspace open with traces from the 11 demo queries already ingested
- [ ] Terminal with curl commands ready as backup
- [ ] Architecture diagram ready
- [ ] No API keys visible on screen
- [ ] Run `./run_traces.sh` beforehand if traces are empty
