"""Shared SerpAPI request helper used by all SerpAPI-backed tools."""

import os
import requests

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
SERPAPI_URL = "https://serpapi.com/search"


def serpapi_request(params: dict, timeout: int = 15) -> dict:
    """Execute a SerpAPI request and return the parsed JSON response.

    Args:
        params: Query parameters including the 'engine' key.
        timeout: Request timeout in seconds.

    Returns:
        Parsed JSON response dict.

    Raises:
        requests.Timeout: If the request exceeds the timeout.
        requests.HTTPError: If the API returns a non-2xx status.
        ValueError: If the SERPAPI_API_KEY is not set.
    """
    if not SERPAPI_KEY:
        raise ValueError(
            "SERPAPI_API_KEY environment variable is not set. "
            "Get a free key at https://serpapi.com"
        )
    params["api_key"] = SERPAPI_KEY
    response = requests.get(SERPAPI_URL, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _mark_span_error(error_message: str) -> None:
    """Best-effort: mark the current OTEL span as errored.

    No-op if opentelemetry is not installed or no span is active.
    """
    try:
        from opentelemetry import trace as otel_trace
        span = otel_trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(error_message))
    except Exception:
        pass
