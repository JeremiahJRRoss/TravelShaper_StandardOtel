"""Unit tests for TravelShaper evaluation prompt modules.

These verify the eval prompts are importable and contain the expected
template variables. They do NOT run the actual LLM-as-judge pipeline
(that requires a live Phoenix instance with traces).
"""

import pytest


def test_tool_output_quality_prompt_importable() -> None:
    """The tool_output_quality module imports and the prompt is a non-empty string."""
    from evaluations.metrics.tool_output_quality import TOOL_OUTPUT_QUALITY_PROMPT

    assert isinstance(TOOL_OUTPUT_QUALITY_PROMPT, str)
    assert len(TOOL_OUTPUT_QUALITY_PROMPT) > 100
    # Must contain the template variables that llm_classify expects
    assert "{input}" in TOOL_OUTPUT_QUALITY_PROMPT
    assert "{tool_calls}" in TOOL_OUTPUT_QUALITY_PROMPT


def test_all_eval_prompts_have_required_template_vars() -> None:
    """All custom eval prompts contain {input} and at least one of {output}/{tool_calls}."""
    from evaluations.metrics.tool_correctness import TOOL_CORRECTNESS_PROMPT
    from evaluations.metrics.answer_completeness import ANSWER_COMPLETENESS_PROMPT
    from evaluations.metrics.tool_output_quality import TOOL_OUTPUT_QUALITY_PROMPT

    for name, prompt in [
        ("tool_correctness", TOOL_CORRECTNESS_PROMPT),
        ("answer_completeness", ANSWER_COMPLETENESS_PROMPT),
        ("tool_output_quality", TOOL_OUTPUT_QUALITY_PROMPT),
    ]:
        assert "{input}" in prompt, f"{name} missing {{input}} template var"
        has_output = "{output}" in prompt
        has_tools = "{tool_calls}" in prompt
        assert has_output or has_tools, (
            f"{name} must contain at least one of {{output}} or {{tool_calls}}"
        )
