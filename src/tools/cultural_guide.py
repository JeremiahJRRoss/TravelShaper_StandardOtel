"""Cultural guide tool — searches for etiquette, language, and dress guidance."""

from typing import List

from langchain_core.tools import tool
from pydantic import BaseModel

from tools import serpapi_request


# ---------------------------------------------------------------------------
# Pydantic structured output models
# ---------------------------------------------------------------------------


class CulturalSnippet(BaseModel):
    """Structured representation of a single cultural guidance snippet."""

    title: str
    snippet: str
    source: str


class CulturalGuideResult(BaseModel):
    """Structured representation of a full cultural guide response."""

    destination: str
    snippets: List[CulturalSnippet] = []
    errors: List[str] = []

    def to_agent_string(self) -> str:
        """Produce the same output as the original get_cultural_guide() string logic."""
        all_lines = []
        for s in self.snippets:
            all_lines.append(f"- {s.title} ({s.source}): {s.snippet}")
        all_lines.extend(self.errors)

        if not all_lines:
            return (
                f"Could not find cultural guidance for {self.destination}. "
                f"I'll provide general advice based on my knowledge."
            )

        lines = [
            f"Cultural and travel prep research for {self.destination}:",
            "",
        ] + all_lines

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_snippets(data: dict, max_results: int = 5) -> list[str]:
    """Extract readable snippets from Google search results."""
    results = data.get("organic_results", [])
    snippets = []
    for r in results[:max_results]:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        source = r.get("displayed_link", "")
        if snippet:
            snippets.append(f"- {title} ({source}): {snippet}")
    return snippets


def _extract_snippet_models(data: dict, max_results: int = 5) -> List[CulturalSnippet]:
    """Extract CulturalSnippet models from Google search results."""
    results = data.get("organic_results", [])
    snippets = []
    for r in results[:max_results]:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        source = r.get("displayed_link", "")
        if snippet:
            snippets.append(CulturalSnippet(title=title, snippet=snippet, source=source))
    return snippets


# ---------------------------------------------------------------------------
# Tool
# ---------------------------------------------------------------------------


@tool
def get_cultural_guide(destination: str) -> str:
    """Get cultural and travel preparation guidance for a destination.

    Use this tool when the user is traveling to an international destination
    and needs help with local customs, language, etiquette, dress code, or
    tipping norms. Also use this for domestic destinations where cultural
    context would be helpful.

    destination should be a city or country name like 'Tokyo, Japan' or 'Barcelona, Spain'.

    Returns a compilation of web-sourced guidance on:
    - Essential local phrases and pronunciation
    - Greeting and etiquette customs
    - Tipping expectations
    - Dress code and packing advice
    - Common mistakes American travelers make
    """
    queries = [
        f"{destination} etiquette tips for American tourists",
        f"{destination} essential local phrases for travelers",
        f"{destination} what to wear dress code tourists",
    ]

    all_snippets: List[CulturalSnippet] = []
    errors: List[str] = []

    for query in queries:
        try:
            data = serpapi_request(
                {
                    "engine": "google",
                    "q": query,
                    "gl": "us",
                    "hl": "en",
                    "num": "5",
                }
            )
            all_snippets.extend(_extract_snippet_models(data, max_results=3))
        except Exception as e:
            from tools import _mark_span_error
            _mark_span_error(str(e))
            errors.append(f"- Search for '{query}' failed: {e}")

    result = CulturalGuideResult(
        destination=destination,
        snippets=all_snippets,
        errors=errors,
    )

    return result.to_agent_string()
