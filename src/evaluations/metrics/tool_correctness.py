"""Tool usage correctness evaluation metric.

Used by evaluations/run_evals.py to classify TravelShaper traces as
'correct' or 'incorrect' via Phoenix llm_classify.
"""

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
