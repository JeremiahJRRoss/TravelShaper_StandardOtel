"""Tool output quality evaluation metric.

Judges whether tool outputs contain relevant, plausible, and correctly-targeted
data — not just whether the right tools were called (which tool_correctness
already covers). This catches cases where SerpAPI returns garbage data that the
LLM then faithfully synthesises into a confident-sounding but wrong briefing.

Used by evaluations/run_evals.py to classify TravelShaper traces as
'good', 'degraded', or 'poor' via Phoenix llm_classify.
"""

TOOL_OUTPUT_QUALITY_PROMPT = """\
You are evaluating the quality of tool outputs in an AI travel planning assistant.

The assistant has access to these tools:
- search_flights: Searches Google Flights via SerpAPI. Returns airline, price, \
duration, stops, departure/arrival times.
- search_hotels: Searches Google Hotels via SerpAPI. Returns hotel name, nightly \
rate, rating, amenities.
- get_cultural_guide: Searches Google for cultural/etiquette information for a \
destination.
- duckduckgo_search: General web search for interests, activities, and fallback \
queries.

Examine each tool call's INPUT ARGUMENTS and OUTPUT CONTENT. Judge whether the \
tool outputs contain relevant, plausible, and correctly-targeted data.

## Evaluation criteria

### Relevance
- Do flight results match the requested origin AND destination cities?
- Do hotel results match the requested city/region?
- Does cultural guide content relate to the actual destination country?
- Are web search results topically relevant to the user's stated interests?

### Plausibility
- Are flight prices in a realistic range? ($50-400 domestic US, $200-2500 \
international economy)
- Are hotel nightly rates realistic? ($20-1000+ depending on class and location)
- Are ratings on expected scales? (hotels: 1.0-5.0 stars)
- Are flight durations plausible for the distance? (domestic US: 1-6h, \
transatlantic: 6-12h, transpacific: 10-16h)

### Targeting
- Do IATA codes in flight search inputs match the cities the user mentioned? \
(e.g., "San Francisco" should produce SFO, not SFI)
- Are hotel search queries scoped to the right city?
- Are cultural guide queries about the right country?

### Completeness
- Did tools return substantive data, or mostly errors and empty results?
- If a tool returned an error, was it a reasonable failure (e.g., no flights \
for a niche route) or caused by bad input (wrong IATA code, malformed date)?

## Important: distinguish tool quality from tool selection

Do NOT penalise for tools that were not called — that is the job of the \
Tool Usage Correctness evaluator. Only evaluate the quality of tools that \
WERE called.

If no tools were called at all, label as "good" (there is nothing to evaluate).

User message: {input}

Tool calls and their outputs:
{tool_calls}

Respond with ONLY a JSON object:
{{"label": "good" or "degraded" or "poor", \
"score": 1.0 or 0.5 or 0.0, \
"explanation": "One sentence. Cite specific tool outputs that were relevant/problematic."}}
"""
