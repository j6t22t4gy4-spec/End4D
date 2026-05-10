from app.llm.prompt_registry import (
    PROMPT_SCHEMA_VERSION,
    build_prompt_contract,
    get_prompt_meta,
    get_prompt_spec,
    get_prompt_system_instruction,
)


def test_prompt_registry_exposes_structured_meta():
    spec = get_prompt_spec("action")
    assert spec.task == "action"
    assert spec.output_mode == "json"
    assert "strategy_summary" in spec.expected_keys

    meta = get_prompt_meta("action")
    assert meta["schema_version"] == PROMPT_SCHEMA_VERSION
    assert meta["prompt_version"] == spec.version
    assert "strategy_summary" in meta["expected_keys"]


def test_prompt_contract_renders_labeled_sections():
    prompt = build_prompt_contract(
        "thought",
        [
            ("agent_state", "role=citizen; energy=50"),
            ("reflection", "scarcity rising"),
        ],
    )
    assert "[PROMPT_CONTRACT]" in prompt
    assert "prompt_version=thought-v2" in prompt
    assert "[AGENT_STATE]" in prompt
    assert "[REFLECTION]" in prompt


def test_prompt_system_instruction_includes_schema_and_task():
    instruction = get_prompt_system_instruction("policy")
    assert f"prompt_schema_version={PROMPT_SCHEMA_VERSION}" in instruction
    assert "task=policy" in instruction
    assert "expected_keys=memory_summary" in instruction
