# Evaluation Prompts — TravelShaper Travel Assistant

**These are the exact prompts that drove the evaluation pipeline.**

> **Note (Observe migration):** The automated evaluation pipeline (`evaluations/`
> and `scripts/`) was removed when TravelShaper migrated from Phoenix to Observe
> via Traceloop + the Observe Agent. The prompts and rationale in this document
> are preserved verbatim so they can be reimplemented against Observe's
> query/dataset features or an external eval runner. The Phoenix-specific
> snippets below (`phoenix.evals`, `OpenAIModel`, `SpanEvaluations`,
> `client.log_evaluations`, the `localhost:6006` UI) are illustrative of the
> previous wiring and are not expected to run as-is against Observe.

---

## Why These Metrics

The three evaluation metrics weren't chosen from a generic checklist — they target specific failure modes observed during development and trace analysis. Each metric exists because the system failed in a particular way that needed a dedicated detector.

### User Frustration — chosen because of silent tool failures

When a SerpAPI call returns empty results (thin coverage for a niche destination, rate limit hit, or timeout), the agent doesn't crash — it receives a "No flights found" string from the tool. The LLM then has to decide what to do with that gap. In some cases, the agent produces a response that simply omits the missing section without acknowledging it. The user asked for flights and hotels but only got hotels — and the response doesn't say why.

A second failure mode: the agent occasionally ignores the user's budget preference. The system prompt instructs it to set `sort_by=3` for budget travelers, but on some runs the LLM passes `sort_by=13` anyway (or doesn't pass it at all, defaulting to highest rating). The user asked to save money and got luxury hotel recommendations. The response is coherent but wrong for the user's stated needs.

The user frustration evaluator catches both patterns — responses that omit requested information and responses that contradict the user's stated preferences. Using Phoenix's built-in `USER_FRUSTRATION_PROMPT_TEMPLATE` rather than a custom prompt was a deliberate choice: it's validated against real conversational patterns and checks for the exact signals these failures produce (incomplete answers, ignored requests).

### Tool Usage Correctness — chosen because of IATA code and parameter errors

The most common tool-level failure is incorrect airport codes. The system prompt includes guidance to convert city names to IATA codes, but the LLM sometimes passes "San Francisco" instead of "SFO", or invents plausible-but-wrong codes for smaller airports. SerpAPI returns empty results, and the agent moves on without flights — a silent failure that cascades into an incomplete briefing.

A second failure mode: the agent occasionally skips `get_cultural_guide` for international destinations, particularly when the user's message is heavily focused on flights or hotels. The system prompt says "always use for international destinations" but the LLM deprioritizes it when the message is logistics-heavy.

A third failure mode: unnecessary tool calls. On vague queries like "I need a break, surprise me" (Query 9 in the trace set), the agent sometimes calls `search_flights` without having a destination — passing empty or hallucinated airport codes. This wastes a SerpAPI call and returns garbage data.

The tool correctness evaluator checks all three dimensions — were the right tools called, were necessary tools missed, and were parameters valid. The prompt explicitly names the four available tools and asks the judge to evaluate selection, completeness, and parameter validity against the user's actual request.

### Answer Completeness — chosen because of partial briefings on scoped requests

TravelShaper's 10 trace queries deliberately include scoped requests — "flights only" (Query 6), "hotels only" (Query 7), "I'm already here, no transport needed" (Query 5). Early in development, the frustration evaluator flagged these as frustrated because they were "missing" sections. But they're not incomplete — the user explicitly asked for a subset. The frustration metric couldn't distinguish "missing because the agent failed" from "missing because the user didn't ask for it."

This created a need for a separate completeness metric with scope awareness. The answer completeness evaluator uses a three-tier classification (complete / partial / incomplete) and its prompt explicitly handles scoped requests: "Do NOT penalise for missing sections the user explicitly excluded or did not request." This means Query 6 (flights only) can score "complete" even though it has no hotel section, while a full trip request that's missing hotels scores "incomplete."

Together with frustration, completeness gives two complementary views — frustration measures the user's likely emotional response, completeness measures whether the response structurally matched the request. A response can be complete but frustrating (all sections present but budget preference ignored) or incomplete but not frustrating (missing one section but the response acknowledges the gap gracefully).

---

## Evaluation 1: User Frustration

### Purpose
Detect traces where the agent's response would likely frustrate the user: incomplete answers, ignored requests, hallucinated details, or unhelpful responses.

### LLM-as-judge prompt

```python
USER_FRUSTRATION_PROMPT = """\
You are evaluating an AI travel assistant's response for signs of user frustration.

Given the user's message and the assistant's response, determine whether the user \
would likely be frustrated with the response.

A response IS frustrating if any of the following are true:
- The user asked about flights but the response contains no flight information
- The user asked about hotels but the response contains no hotel information
- The user asked about a specific destination but the response is generic and not destination-specific
- The response says "I cannot help with that" or refuses to act when the request is reasonable
- The response contains obviously fabricated specifics (fake hotel names, made-up prices) not from tool results
- The response ignores a key part of the user's request (e.g., user asked for budget options but got luxury only)
- The response is extremely short or vague when the user asked a detailed question

A response is NOT frustrating if:
- It provides useful partial information and acknowledges what it couldn't find
- It addresses the main request even if some details are missing
- It asks a reasonable clarifying question when the input is truly ambiguous

User message: {input}

Assistant response: {output}

Tool calls made: {tool_calls}

Respond with ONLY a JSON object:
{{
  "label": "frustrated" or "not_frustrated",
  "score": 0 or 1,
  "explanation": "One sentence explaining your judgment."
}}
"""
```

### Implementation

```python
from phoenix.evals import llm_classify, OpenAIModel

# Define the evaluation model
eval_model = OpenAIModel(model="gpt-4o", temperature=0)

# Run evaluation on spans dataframe
frustration_results = llm_classify(
    dataframe=spans_df,
    template=USER_FRUSTRATION_PROMPT,
    model=eval_model,
    rails=["frustrated", "not_frustrated"],
    provide_explanation=True,
)
```

### Expected distribution
With well-crafted queries (see trace-queries.md):
- Queries 1-3, 6-8, 10: should be "not_frustrated" (clear requests with tool results)
- Query 4: could be either (no flights/hotels, but cultural info is provided)
- Query 5: should be "not_frustrated" (interest-based, web search handles it)
- Query 9: most likely "not_frustrated" if agent gives destination suggestions, "frustrated" if it refuses

---

## Evaluation 2: Tool Usage Correctness

### Purpose
Assess whether the agent selected appropriate tools for the user's request and passed valid parameters.

### LLM-as-judge prompt

```python
TOOL_CORRECTNESS_PROMPT = """\
You are evaluating whether an AI travel assistant used its tools correctly.

The assistant has access to these tools:
- search_flights: Search for flights. Requires departure airport code, arrival airport code, and dates.
- search_hotels: Search for hotels. Requires a destination query and dates.
- get_cultural_guide: Get etiquette, language, and dress guidance for a destination.
- duckduckgo_search: General web search for interests, events, activities, and fallback queries.

Given the user's message and the tools that were called, evaluate:

1. Were the RIGHT tools called? (Did the agent search flights when the user asked about flights?)
2. Were any NECESSARY tools missed? (Did the agent skip cultural guide for an international trip?)
3. Were tool PARAMETERS valid? (Did the agent pass proper airport codes, not city names? Were dates in YYYY-MM-DD format?)
4. Were any UNNECESSARY tools called? (Did the agent search flights when the user only asked about food?)

User message: {input}

Tools called and their inputs:
{tool_calls}

Respond with ONLY a JSON object:
{{
  "label": "correct" or "incorrect",
  "score": 0 or 1,
  "explanation": "One sentence explaining your judgment. Mention specific tools that were correctly used, missed, or misused."
}}
"""
```

### Implementation

```python
tool_correctness_results = llm_classify(
    dataframe=spans_df,
    template=TOOL_CORRECTNESS_PROMPT,
    model=eval_model,
    rails=["correct", "incorrect"],
    provide_explanation=True,
)
```

### Expected distribution
- Most queries should be "correct" if the system prompt is well-crafted
- Common failure modes to look for:
  - Agent passes "San Francisco" instead of "SFO" to search_flights
  - Agent skips get_cultural_guide for international destinations
  - Agent calls search_flights when user only asked about cultural info
  - Agent passes malformed dates

---

## Evaluation 3: Answer Completeness

### Purpose
Measures whether the response covers all sections the user reasonably expected, given the specific nature of their query. Three-tier classification with scope-awareness.

### LLM-as-judge prompt
See `evaluations/metrics/answer_completeness.py` for the full prompt.

### Expected distribution
- Full trip requests (Queries 1-3, 8, 10): should be "complete" if all sections present
- Scoped requests (Queries 5-7): should be "complete" even with missing sections (user didn't ask)
- Query 9 (vague): could be any label depending on response substantiveness

---

## Evaluation 4: Tool Output Quality

### Purpose
Assess whether tool outputs contain relevant, plausible, and correctly-targeted data — independent of whether the right tools were called.

### Why this exists alongside Tool Usage Correctness
Tool correctness asks: "did the agent call the right tools?" Tool output quality asks: "was the data that came back actually good?" You can call the right tool with the right parameters and still get garbage (rate limit, wrong IATA code that maps to the wrong airport, etc.).

### LLM-as-judge prompt
See `evaluations/metrics/tool_output_quality.py` for the full prompt.

### Expected distribution
- Most traces with live SerpAPI data should score `good`
- Niche routes or rate-limited queries may score `degraded`
- Wrong IATA codes or completely empty results score `poor`

### Calibration notes
This is the hardest eval to calibrate because "plausible" is route-dependent. After running evals, check the `explanation` field in Phoenix. Common miscalibration: the judge flags realistic prices as implausible because the prompt's range guidance is too narrow. Widen the ranges if needed.

---

## Integration: evaluations/run_evals.py

The run_evals.py script imports prompts from the metrics modules. This matches the project structure in the README.

**evaluations/metrics/frustration.py:**
```python
"""User frustration evaluation metric."""

USER_FRUSTRATION_PROMPT = """\
You are evaluating an AI travel assistant's response for signs of user frustration.

Given the user's message and the assistant's response, determine whether the user \
would likely be frustrated with the response.

A response IS frustrating if any of the following are true:
- The user asked about flights but the response contains no flight information
- The user asked about hotels but the response contains no hotel information
- The user asked about a specific destination but the response is generic and not destination-specific
- The response says "I cannot help with that" or refuses to act when the request is reasonable
- The response contains obviously fabricated specifics (fake hotel names, made-up prices) not from tool results
- The response ignores a key part of the user's request (e.g., user asked for budget options but got luxury only)
- The response is extremely short or vague when the user asked a detailed question

A response is NOT frustrating if:
- It provides useful partial information and acknowledges what it couldn't find
- It addresses the main request even if some details are missing
- It asks a reasonable clarifying question when the input is truly ambiguous

User message: {input}

Assistant response: {output}

Tool calls made: {tool_calls}

Respond with ONLY a JSON object:
{{"label": "frustrated" or "not_frustrated", "score": 0 or 1, "explanation": "One sentence explaining your judgment."}}
"""
```

**evaluations/metrics/tool_correctness.py:**
```python
"""Tool usage correctness evaluation metric."""

TOOL_CORRECTNESS_PROMPT = """\
You are evaluating whether an AI travel assistant used its tools correctly.

The assistant has access to these tools:
- search_flights: Search for flights. Requires departure airport code, arrival airport code, and dates.
- search_hotels: Search for hotels. Requires a destination query and dates.
- get_cultural_guide: Get etiquette, language, and dress guidance for a destination.
- duckduckgo_search: General web search for interests, events, activities, and fallback queries.

Given the user's message and the tools that were called, evaluate:

1. Were the RIGHT tools called? (Did the agent search flights when the user asked about flights?)
2. Were any NECESSARY tools missed? (Did the agent skip cultural guide for an international trip?)
3. Were tool PARAMETERS valid? (Did the agent pass proper airport codes, not city names? Were dates in YYYY-MM-DD format?)
4. Were any UNNECESSARY tools called? (Did the agent search flights when the user only asked about food?)

User message: {input}

Tools called and their inputs:
{tool_calls}

Respond with ONLY a JSON object:
{{"label": "correct" or "incorrect", "score": 0 or 1, "explanation": "One sentence explaining your judgment. Mention specific tools that were correctly used, missed, or misused."}}
"""
```

**evaluations/run_evals.py:**
```python
"""Run Phoenix evaluations on captured TravelShaper traces."""

import phoenix as px
from phoenix.evals import llm_classify, OpenAIModel
from phoenix.trace import SpanEvaluations

from evaluations.metrics.frustration import USER_FRUSTRATION_PROMPT
from evaluations.metrics.tool_correctness import TOOL_CORRECTNESS_PROMPT

# Connect to Phoenix
client = px.Client()

# Get spans
spans_df = client.get_spans_dataframe()

# Filter to root spans (one per user request)
root_spans = spans_df[spans_df["parent_id"].isna()].copy()

if root_spans.empty:
    print("No traces found. Run some queries first.")
    exit(1)

print(f"Found {len(root_spans)} traces. Running evaluations...")

# Evaluation model
eval_model = OpenAIModel(model="gpt-4o", temperature=0)

# --- User Frustration ---
# NOTE: Template variables {input}, {output}, {tool_calls} must map to span DataFrame columns.
# Phoenix span columns are typically: "attributes.input.value", "attributes.output.value".
# You may need to rename columns or use provide a `template_variables` mapping.
# Check Phoenix docs: https://arize.com/docs/phoenix/evaluation/python-quickstart

frustration_results = llm_classify(
    dataframe=root_spans,
    template=USER_FRUSTRATION_PROMPT,
    model=eval_model,
    rails=["frustrated", "not_frustrated"],
    provide_explanation=True,
)

client.log_evaluations(
    SpanEvaluations(
        eval_name="User Frustration",
        dataframe=frustration_results,
    )
)

frustrated_count = (frustration_results["label"] == "frustrated").sum()
total = len(frustration_results)
print(f"User Frustration: {frustrated_count}/{total} frustrated ({frustrated_count/total*100:.0f}%)")

# --- Tool Correctness ---
tool_correctness_results = llm_classify(
    dataframe=root_spans,
    template=TOOL_CORRECTNESS_PROMPT,
    model=eval_model,
    rails=["correct", "incorrect"],
    provide_explanation=True,
)

client.log_evaluations(
    SpanEvaluations(
        eval_name="Tool Usage Correctness",
        dataframe=tool_correctness_results,
    )
)

correct_count = (tool_correctness_results["label"] == "correct").sum()
total = len(tool_correctness_results)
print(f"Tool Correctness: {correct_count}/{total} correct ({correct_count/total*100:.0f}%)")

# --- Create frustrated dataset ---
frustrated_df = root_spans[frustration_results["label"] == "frustrated"]
if not frustrated_df.empty:
    dataset = client.upload_dataset(
        dataframe=frustrated_df,
        dataset_name="frustrated_interactions",
        input_keys=["attributes.input.value"],
        output_keys=["attributes.output.value"],
    )
    print(f"Created 'frustrated_interactions' dataset with {len(frustrated_df)} examples.")
else:
    print("No frustrated interactions found — no dataset created.")

print("Evaluations complete. View results in Phoenix UI at http://localhost:6006")
```

---

## Notes

- The `{input}`, `{output}`, and `{tool_calls}` placeholders are filled by Phoenix from span attributes. Check Phoenix docs for the exact column names — they may be `attributes.input.value`, `attributes.output.value`, etc.
- The evaluation model uses GPT-4o at temperature=0 for deterministic judgments.
- The frustrated interactions dataset (Step 6 requirement) is created automatically from evaluation results.
- Run evaluations AFTER the 10 trace queries have been executed, not before.
