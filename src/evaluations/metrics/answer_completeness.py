"""Answer completeness evaluation metric.
Measures whether TravelShaper's response covers all sections the user
reasonably expected, given the specific nature of their query.
Used by evaluations/run_evals.py to classify TravelShaper traces as
'complete', 'partial', or 'incomplete' via Phoenix llm_classify.
"""

ANSWER_COMPLETENESS_PROMPT = """\
You are evaluating whether an AI travel assistant gave a complete response \
to a user's travel planning query.

Determine what sections the user reasonably expected based on their message:

For a FULL trip planning request (origin city, destination, and dates all provided):
- Expected sections: flights, hotels, cultural guidance (for international trips), \
and at least one interest-specific recommendation.
- All expected sections must contain substantive content (specific names, prices, \
or actionable details), not just vague mentions.

For a PARTIAL or SCOPED request where the user explicitly limited what they want:
- "flights only" or "just flights" → only flight information is expected
- "hotels only" or "just hotels" → only hotel information is expected
- "I don't need flights" or "already booked" → flights are NOT expected
- "no cultural guide" → cultural guidance is NOT expected
- Cultural-only questions → only cultural guidance is expected
- Interest-only questions ("best food in X") → only interest recommendations expected

Do NOT penalise for missing sections the user explicitly excluded or did not request.

For a VAGUE or OPEN-ENDED request (no origin, no dates, general question):
- Evaluate based on whether the response is substantive and helpful for what was asked.
- A thoughtful, detailed response to a vague question is "complete."

Classification:
- "complete"   — all expected sections are present with substantive, specific content
- "partial"    — one expected section is thin (lacks specifics) or one section is missing
- "incomplete" — two or more expected sections are missing or the response is unhelpfully vague

User message: {input}

Assistant response: {output}

Tools called and their results:
{tool_calls}

Use the tool call information to distinguish between:
- "the agent did not search for this" (relevant tool was never called)
- "the agent searched but found nothing" (tool was called, returned empty or error)
Only penalise for missing sections when the relevant tool was not called AND the \
user's request implied that section should be present.

Respond with ONLY a JSON object:
{{"label": "complete" or "partial" or "incomplete", \
"score": 1.0 or 0.5 or 0.0, \
"explanation": "One sentence. Name any missing or thin sections."}}
"""
