"""Unit tests for the TravelShaper LangGraph agent structure.

Verifies that build_agent() produces a compiled graph with the expected
nodes and that all four tools are registered — without making any live
LLM or API calls.
"""

import os
from unittest.mock import patch, MagicMock

import pytest

from agent import build_agent, tools, get_prompt_version, SAVE_MONEY_PROMPT_VERSION, FULL_EXPERIENCE_PROMPT_VERSION


# ---------------------------------------------------------------------------
# Test 4 (overall): agent graph has the expected nodes
# ---------------------------------------------------------------------------

def test_agent_graph_has_expected_nodes() -> None:
    """build_agent() must return a compiled graph with the expected nodes."""
    agent = build_agent()
    nodes = list(agent.get_graph().nodes.keys())

    assert "route_and_inject" in nodes, f"Expected 'route_and_inject' in graph nodes, got: {nodes}"
    assert "llm_call" in nodes, f"Expected 'llm_call' in graph nodes, got: {nodes}"
    assert "tool_node" in nodes, f"Expected 'tool_node' in graph nodes, got: {nodes}"


# ---------------------------------------------------------------------------
# Test 5 (overall): all four tools are registered
# ---------------------------------------------------------------------------

def test_agent_tools_registered() -> None:
    """The tools list must contain exactly 4 tools with the correct names."""
    tool_names = [t.name for t in tools]

    assert len(tools) == 4, f"Expected 4 tools, got {len(tools)}: {tool_names}"
    assert "search_flights" in tool_names, f"Missing 'search_flights' in {tool_names}"
    assert "search_hotels" in tool_names, f"Missing 'search_hotels' in {tool_names}"
    assert "get_cultural_guide" in tool_names, f"Missing 'get_cultural_guide' in {tool_names}"
    assert "duckduckgo_search" in tool_names, f"Missing 'duckduckgo_search' in {tool_names}"


# ---------------------------------------------------------------------------
# Test 6 (overall): prompt version routing
# ---------------------------------------------------------------------------

def test_prompt_version_routing() -> None:
    """get_prompt_version routes budget keywords to save_money, default to full_experience."""
    assert get_prompt_version("I want to save money on this trip") == SAVE_MONEY_PROMPT_VERSION
    assert get_prompt_version("cheapest option please") == SAVE_MONEY_PROMPT_VERSION
    assert get_prompt_version("budget trip to Rome") == SAVE_MONEY_PROMPT_VERSION
    assert get_prompt_version("spend as little as possible") == SAVE_MONEY_PROMPT_VERSION
    assert get_prompt_version("Plan a luxury trip to Paris") == FULL_EXPERIENCE_PROMPT_VERSION
    assert get_prompt_version("full experience in Tokyo") == FULL_EXPERIENCE_PROMPT_VERSION
    assert get_prompt_version("surprise me") == FULL_EXPERIENCE_PROMPT_VERSION


# ---------------------------------------------------------------------------
# Test 7 (overall): tracing config resolves env vars
# ---------------------------------------------------------------------------

def test_load_tracing_config_resolves_env_vars() -> None:
    """_load_tracing_config resolves ${VAR} and ${VAR:-default} from env."""
    import tempfile
    from pathlib import Path as RealPath
    from agent import _load_tracing_config

    config_content = (
        "OTEL_DESTINATION: arize\n"
        "arize:\n"
        "  space_id: ${TEST_SPACE_ID}\n"
        "  api_key: ${TEST_API_KEY:-fallback_key}\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(config_content)
        f.flush()
        tmp_path = RealPath(f.name)

    try:
        with patch("agent.Path") as mock_path_cls:
            mock_parent = MagicMock()
            mock_parent.__truediv__ = lambda self, name: tmp_path
            mock_path_inst = MagicMock()
            mock_path_inst.parent = mock_parent
            mock_path_cls.return_value = mock_path_inst

            with patch.dict(os.environ, {"TEST_SPACE_ID": "space-123"}, clear=False):
                # TEST_API_KEY not set — should use fallback
                os.environ.pop("TEST_API_KEY", None)
                config = _load_tracing_config()

        assert config["OTEL_DESTINATION"] == "arize"
        assert config["arize"]["space_id"] == "space-123"
        assert config["arize"]["api_key"] == "fallback_key"
    finally:
        tmp_path.unlink()


# ---------------------------------------------------------------------------
# Test 8 (overall): trace backend defaults to Phoenix
# ---------------------------------------------------------------------------

def test_init_tracing_defaults_to_phoenix() -> None:
    """When OTEL_DESTINATION is phoenix, _init_tracing calls _init_phoenix."""
    from agent import _init_tracing

    with patch("agent._load_tracing_config", return_value={
             "OTEL_DESTINATION": "phoenix",
             "phoenix": {"endpoint": "http://localhost:6006/v1/traces"},
         }), \
         patch("agent._init_phoenix", return_value=MagicMock()) as mock_phoenix, \
         patch("agent._init_arize") as mock_arize, \
         patch("agent._init_custom") as mock_custom, \
         patch("openinference.instrumentation.langchain.LangChainInstrumentor"):
        _init_tracing()

    mock_phoenix.assert_called_once()
    mock_arize.assert_not_called()
    mock_custom.assert_not_called()


# ---------------------------------------------------------------------------
# Test 9 (overall): trace backend selects Arize when configured
# ---------------------------------------------------------------------------

def test_init_tracing_selects_arize_when_configured() -> None:
    """When OTEL_DESTINATION is arize, _init_tracing calls _init_arize."""
    from agent import _init_tracing

    with patch("agent._load_tracing_config", return_value={
             "OTEL_DESTINATION": "arize",
             "arize": {"space_id": "s", "api_key": "k"},
         }), \
         patch("agent._init_arize", return_value=MagicMock()) as mock_arize, \
         patch("agent._init_phoenix") as mock_phoenix, \
         patch("agent._init_custom") as mock_custom, \
         patch("openinference.instrumentation.langchain.LangChainInstrumentor"):
        _init_tracing()

    mock_arize.assert_called_once()
    mock_phoenix.assert_not_called()
    mock_custom.assert_not_called()


# ---------------------------------------------------------------------------
# Test 10 (overall): trace backend selects custom when configured
# ---------------------------------------------------------------------------

def test_init_tracing_selects_custom() -> None:
    """When OTEL_DESTINATION is custom, _init_tracing calls _init_custom."""
    from agent import _init_tracing

    with patch("agent._load_tracing_config", return_value={
             "OTEL_DESTINATION": "custom",
             "custom": {
                 "endpoint": "https://cribl:4318/v1/traces",
                 "protocol": "http/protobuf",
             },
         }), \
         patch("agent._init_custom", return_value=MagicMock()) as mock_custom, \
         patch("agent._init_phoenix") as mock_phoenix, \
         patch("agent._init_arize") as mock_arize, \
         patch("openinference.instrumentation.langchain.LangChainInstrumentor"):
        _init_tracing()

    mock_custom.assert_called_once()
    mock_phoenix.assert_not_called()
    mock_arize.assert_not_called()
