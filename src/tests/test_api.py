"""Unit tests for the TravelShaper FastAPI endpoints.

All external calls are mocked — no live API keys required.
"""

import os as _os
from unittest.mock import ANY, patch

import pytest
from langchain_core.messages import AIMessage
from starlette.testclient import TestClient

import api
from api import ValidationResult, PlaceValidationResult
from agent import SAVE_MONEY_PROMPT_VERSION, FULL_EXPERIENCE_PROMPT_VERSION


client = TestClient(api.app)


@pytest.fixture(autouse=True)
def _clean_feedback_file():
    """Remove feedback.jsonl after each test that might create it."""
    yield
    feedback_path = getattr(api, "_FEEDBACK_FILE", None)
    if feedback_path and _os.path.exists(feedback_path):
        _os.remove(feedback_path)


# ── Health ────────────────────────────────────────────────────────────────

def test_health_endpoint() -> None:
    """GET /health returns 200 with {\"status\": \"ok\"}."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


# ── Chat — basic ──────────────────────────────────────────────────────────

@patch("api.agent")
def test_chat_endpoint_accepts_message(mock_agent) -> None:
    """POST /chat with no extras returns 200 and a non-empty response."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Here is your travel briefing...")]
    }
    r = client.post("/chat", json={"message": "Plan a trip to Tokyo"})
    assert r.status_code == 200
    body = r.json()
    assert "response" in body and body["response"]


# ── Preferences validation ────────────────────────────────────────────────

@patch("api.validate_preferences")
@patch("api.agent")
def test_chat_accepts_valid_preferences(mock_agent, mock_validate) -> None:
    """Valid preferences pass through to the agent."""
    mock_validate.return_value = ValidationResult(valid=True, reason="Travel preference")
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Plan a trip to Tokyo",
        "preferences": "I am vegetarian and travel with a 6-year-old.",
    })

    assert r.status_code == 200
    mock_validate.assert_called_once_with("I am vegetarian and travel with a 6-year-old.", config=ANY)


@patch("api.validate_preferences")
@patch("api.agent")
def test_chat_rejects_invalid_preferences(mock_agent, mock_validate) -> None:
    """Invalid preferences return 400 and never call the agent."""
    mock_validate.return_value = ValidationResult(
        valid=False, reason="Request for illegal substances is not permitted."
    )

    r = client.post("/chat", json={
        "message": "Plan a trip",
        "preferences": "Tell me where to buy illegal drugs.",
    })

    assert r.status_code == 400
    mock_agent.invoke.assert_not_called()


@patch("api.validate_preferences")
@patch("api.agent")
def test_chat_skips_validation_for_empty_preferences(mock_agent, mock_validate) -> None:
    """Whitespace-only preferences skip validation."""
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Plan a trip to Tokyo",
        "preferences": "   ",
    })

    assert r.status_code == 200
    mock_validate.assert_not_called()


# ── Place validation ──────────────────────────────────────────────────────

@patch("api.validate_place")
@patch("api.agent")
def test_chat_accepts_valid_places(mock_agent, mock_validate_place) -> None:
    """Valid place names pass through and the agent is called."""
    mock_validate_place.return_value = PlaceValidationResult(
        valid=True, canonical="San Francisco, California, USA",
        corrected=None, reason="Valid place.", field="departure"
    )
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Trip from San Francisco to Tokyo",
        "departure": "San Francisco",
        "destination": "Tokyo",
    })

    assert r.status_code == 200


@patch("api.validate_place")
@patch("api.agent")
def test_chat_rejects_invalid_place(mock_agent, mock_validate_place) -> None:
    """An unrecognisable place name returns 400 with field info."""
    def side_effect(name, field, config=None):
        if field == "departure":
            return PlaceValidationResult(
                valid=True, canonical="New York, USA", corrected=None,
                reason="Valid place.", field="departure"
            )
        return PlaceValidationResult(
            valid=False, canonical=None, corrected=None,
            reason="We couldn't find a place called 'Fakeville'. Please check the spelling.",
            field="destination"
        )
    mock_validate_place.side_effect = side_effect

    r = client.post("/chat", json={
        "message": "Trip to Fakeville",
        "departure": "New York",
        "destination": "Fakeville",
    })

    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["field"] == "destination"
    mock_agent.invoke.assert_not_called()


@patch("api.validate_place")
@patch("api.agent")
def test_chat_auto_corrects_misspelled_place(mock_agent, mock_validate_place) -> None:
    """Misspelled but identifiable place is corrected and agent is called."""
    mock_validate_place.return_value = PlaceValidationResult(
        valid=True, corrected="Tokyo, Japan",
        canonical="Tokyo, Japan",
        reason="Corrected from 'Tokio'.", field="destination"
    )
    mock_agent.invoke.return_value = {"messages": [AIMessage(content="Briefing...")]}

    r = client.post("/chat", json={
        "message": "Trip from NYC to Tokio",
        "departure": "New York",
        "destination": "Tokio",
    })

    assert r.status_code == 200


# ── Debug trace URL ───────────────────────────────────────────────────────

@patch("api._DEBUG", True)
@patch("api.agent")
def test_chat_includes_debug_when_enabled(mock_agent) -> None:
    """When TRAVELSHAPER_DEBUG is true, /chat response includes debug object."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Briefing...")]
    }
    r = client.post("/chat", json={"message": "Plan a trip to Tokyo"})
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    assert "debug" in body
    assert "trace_url" in body["debug"]
    assert "run_id" in body["debug"]
    assert body["debug"]["trace_url"].startswith("http")


@patch("api._DEBUG", False)
@patch("api.agent")
def test_chat_excludes_debug_when_disabled(mock_agent) -> None:
    """When TRAVELSHAPER_DEBUG is false, /chat response has run_id but no debug."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Briefing...")]
    }
    r = client.post("/chat", json={"message": "Plan a trip to Tokyo"})
    assert r.status_code == 200
    body = r.json()
    assert "run_id" in body
    assert "debug" not in body


# ── Session identity ──────────────────────────────────────────────────────

@patch("api.agent")
def test_chat_uses_client_session_id(mock_agent) -> None:
    """When session_id is provided, it appears in the run_id or config."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Briefing...")]
    }
    r = client.post("/chat", json={
        "message": "Plan a trip to Tokyo",
        "session_id": "test-session-abc",
    })
    assert r.status_code == 200
    # Verify session_id was passed through to agent config
    call_kwargs = mock_agent.invoke.call_args
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    assert config["metadata"]["session.id"] == "test-session-abc"


@patch("api.agent")
def test_chat_falls_back_to_run_id_without_session(mock_agent) -> None:
    """When no session_id provided, session.id falls back to run_id."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Briefing...")]
    }
    r = client.post("/chat", json={"message": "Plan a trip to Tokyo"})
    assert r.status_code == 200
    call_kwargs = mock_agent.invoke.call_args
    config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
    # session.id should be set (to run_id), not empty
    assert config["metadata"]["session.id"]


# ── Prompt versioning ─────────────────────────────────────────────────────

@patch("api.agent")
def test_chat_sets_budget_prompt_version(mock_agent) -> None:
    """Budget keywords produce save_money prompt version in metadata."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Briefing...")]
    }
    r = client.post("/chat", json={
        "message": "Plan a trip to Tokyo, save money",
    })
    assert r.status_code == 200
    config = mock_agent.invoke.call_args.kwargs.get("config") or mock_agent.invoke.call_args[1].get("config")
    assert config["metadata"]["travelshaper.prompt_version"] == SAVE_MONEY_PROMPT_VERSION
    assert config["metadata"]["travelshaper.budget_mode"] == "save_money"


@patch("api.agent")
def test_chat_sets_full_experience_prompt_version(mock_agent) -> None:
    """No budget keywords produce full_experience prompt version in metadata."""
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Briefing...")]
    }
    r = client.post("/chat", json={
        "message": "Plan a luxury trip to Paris",
    })
    assert r.status_code == 200
    config = mock_agent.invoke.call_args.kwargs.get("config") or mock_agent.invoke.call_args[1].get("config")
    assert config["metadata"]["travelshaper.prompt_version"] == FULL_EXPERIENCE_PROMPT_VERSION
    assert config["metadata"]["travelshaper.budget_mode"] == "full_experience"


# ── Guardrail metadata ────────────────────────────────────────────────────

@patch("api.validate_place")
@patch("api.agent")
def test_chat_records_guardrail_metadata(mock_agent, mock_validate_place) -> None:
    """Validation calls produce guardrail count and outcome attributes."""
    mock_validate_place.return_value = PlaceValidationResult(
        valid=True, canonical="Tokyo, Japan", corrected=None,
        reason="Valid.", field="destination",
    )
    mock_agent.invoke.return_value = {
        "messages": [AIMessage(content="Briefing...")]
    }
    r = client.post("/chat", json={
        "message": "Plan a trip to Tokyo",
        "departure": "San Francisco",
        "destination": "Tokyo",
    })
    assert r.status_code == 200
    config = mock_agent.invoke.call_args.kwargs.get("config") or mock_agent.invoke.call_args[1].get("config")
    meta = config["metadata"]
    # Guardrail summary
    assert meta["travelshaper.guardrails.count"] == 2  # departure + destination
    assert meta["travelshaper.guardrails.blocked"] == 0
    # Validation outcomes
    assert meta["travelshaper.validation.departure"] == "valid"
    assert meta["travelshaper.validation.destination"] == "valid"
    assert meta["travelshaper.validation.preferences"] == "skipped"


# ── Feedback ──────────────────────────────────────────────────────────────

def test_feedback_accepts_valid_payload() -> None:
    """POST /feedback with valid score returns 200 with status and sync flag."""
    with patch("api._sync_feedback_to_phoenix", return_value=False):
        r = client.post("/feedback", json={
            "run_id": "test-run-123",
            "session_id": "test-session-456",
            "score": 1,
            "comment": "Great briefing!",
        })

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "received"
    assert "synced_to_phoenix" in body
    assert isinstance(body["synced_to_phoenix"], bool)


def test_feedback_rejects_invalid_score() -> None:
    """POST /feedback with score other than 1/-1 returns 400."""
    r = client.post("/feedback", json={
        "run_id": "test-run-123",
        "score": 5,
    })
    assert r.status_code == 400


def test_feedback_rejects_missing_run_id() -> None:
    """POST /feedback without run_id returns 422 (Pydantic validation)."""
    r = client.post("/feedback", json={
        "score": 1,
    })
    assert r.status_code == 422


# ── Token/cost tracking ─────────────────────────────────────────────────

def test_token_usage_tracker_accumulates() -> None:
    """TokenUsageTracker accumulates tokens across multiple on_llm_end calls."""
    from api import TokenUsageTracker
    from langchain_core.outputs import LLMResult, Generation

    tracker = TokenUsageTracker()

    # Simulate a gpt-4o validation call
    tracker.on_llm_end(LLMResult(
        generations=[[Generation(text="ok")]],
        llm_output={
            "model_name": "gpt-4o",
            "token_usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        },
    ))

    # Simulate an agent LLM call
    tracker.on_llm_end(LLMResult(
        generations=[[Generation(text="briefing")]],
        llm_output={
            "model_name": "gpt-5.3-chat-latest",
            "token_usage": {"prompt_tokens": 500, "completion_tokens": 800, "total_tokens": 1300},
        },
    ))

    assert tracker.llm_calls == 2
    assert tracker.prompt_tokens == 600
    assert tracker.completion_tokens == 820
    assert tracker.total_tokens == 1420
    assert tracker.estimated_cost_usd() > 0

    summary = tracker.summary()
    assert summary["llm_calls"] == 2
    assert "gpt-4o" in summary["by_model"]
    assert "gpt-5.3-chat-latest" in summary["by_model"]


def test_token_usage_tracker_handles_missing_data() -> None:
    """TokenUsageTracker records zero when llm_output is None (streaming fallback)."""
    from api import TokenUsageTracker
    from langchain_core.outputs import LLMResult, Generation

    tracker = TokenUsageTracker()

    # Simulate an LLM call with no output metadata (streaming without stream_usage)
    tracker.on_llm_end(LLMResult(
        generations=[[Generation(text="ok")]],
        llm_output=None,
    ))

    assert tracker.llm_calls == 1
    assert tracker.total_tokens == 0
    assert tracker.estimated_cost_usd() == 0.0

    summary = tracker.summary()
    assert summary["total_tokens"] == 0
    assert summary["estimated_cost_usd"] == 0.0


def test_build_timing_detects_sla_breach() -> None:
    """_build_timing correctly flags SLA exceeded."""
    from api import _build_timing, _SLA_TOTAL_S

    # Under budget: 2s validation + 5s agent = 7s total
    timing = _build_timing(0.0, 2.0, 2.0, 7.0)
    assert timing["validation_ms"] == 2000.0
    assert timing["agent_ms"] == 5000.0
    assert timing["total_ms"] == 7000.0
    assert timing["sla_exceeded"] is False

    # Over budget: use timestamps that exceed _SLA_TOTAL_S
    over_end = _SLA_TOTAL_S + 10
    timing_over = _build_timing(0.0, 1.0, 1.0, over_end)
    assert timing_over["sla_exceeded"] is True


# ── Trace URL routing ─────────────────────────────────────────────────


@patch("api.TRACE_DESTINATION", "phoenix")
def test_trace_url_phoenix() -> None:
    """_trace_url returns a Phoenix URL when destination is phoenix."""
    from api import _trace_url

    url = _trace_url("run-123")
    assert "phoenix" in url.lower() or "localhost" in url
    assert "run-123" in url


@patch("api.TRACE_DESTINATION", "arize")
@patch("api._ARIZE_SPACE_ID", "space-abc")
def test_trace_url_arize() -> None:
    """_trace_url returns an Arize URL when destination is arize."""
    from api import _trace_url

    url = _trace_url("run-456")
    assert "app.arize.com" in url
    assert "space-abc" in url
    assert "run-456" in url


@patch("api.TRACE_DESTINATION", "custom")
def test_trace_url_custom() -> None:
    """_trace_url returns trace:{run_id} for custom backend."""
    from api import _trace_url

    url = _trace_url("run-789")
    assert url == "trace:run-789"
