"""Unit tests for the TravelShaper LangGraph agent structure.

Verifies that build_agent() produces a compiled graph with the expected
nodes and that all four tools are registered — without making any live
LLM or API calls.
"""

import sys
from unittest.mock import MagicMock, patch

from agent import (
    FULL_EXPERIENCE_PROMPT_VERSION,
    SAVE_MONEY_PROMPT_VERSION,
    build_agent,
    get_prompt_version,
    tools,
)


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
# Test 7 (overall): tracing initializes via Traceloop SDK
# ---------------------------------------------------------------------------

def test_init_tracing_calls_traceloop() -> None:
    """_init_tracing should call Traceloop.init with app_name=travelshaper."""
    from agent import _init_tracing

    fake_module = MagicMock()
    fake_traceloop_cls = MagicMock()
    fake_module.Traceloop = fake_traceloop_cls

    with patch.dict(sys.modules, {"traceloop.sdk": fake_module}):
        _init_tracing()

    fake_traceloop_cls.init.assert_called_once()
    call_kwargs = fake_traceloop_cls.init.call_args.kwargs
    assert call_kwargs.get("app_name") == "travelshaper"
