from app.core.settings import (
    get_action_refresh_interval,
    get_dialogue_interval,
    get_group_deliberation_interval,
    get_llm_agent_sample_size,
    get_llm_cycle_prompt_budget,
    get_llm_task_live_floor,
    get_thought_refresh_interval,
    get_worldview_memory_threshold,
    get_worldview_refresh_interval,
    get_worldview_t_threshold,
)


def test_llm_first_profile_uses_denser_cadence(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_RUNTIME_PROFILE", "llm-first")
    monkeypatch.delenv("ORGANIC4D_THOUGHT_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_ACTION_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_WORLDVIEW_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_DIALOGUE_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_GROUP_DELIBERATION_INTERVAL", raising=False)
    monkeypatch.setenv("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE", "2048")
    monkeypatch.setenv("ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET", "1200")

    assert get_thought_refresh_interval() <= 6
    assert get_action_refresh_interval() <= 2
    assert get_worldview_refresh_interval() <= 12
    assert get_worldview_memory_threshold() <= 48
    assert get_worldview_t_threshold() <= 80.0
    assert get_dialogue_interval() <= 6
    assert get_group_deliberation_interval() <= 12
    assert get_llm_agent_sample_size() >= 1024
    assert get_llm_cycle_prompt_budget() >= 1200
    assert get_llm_task_live_floor("action") >= 1
    assert get_llm_task_live_floor("thought") >= 1


def test_rules_first_profile_uses_more_conservative_cadence(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_RUNTIME_PROFILE", "rules-first")
    monkeypatch.delenv("ORGANIC4D_THOUGHT_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_ACTION_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_WORLDVIEW_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_DIALOGUE_INTERVAL", raising=False)
    monkeypatch.delenv("ORGANIC4D_GROUP_DELIBERATION_INTERVAL", raising=False)

    assert get_thought_refresh_interval() >= 24
    assert get_action_refresh_interval() >= 12
    assert get_worldview_refresh_interval() >= 48
    assert get_dialogue_interval() >= 30
    assert get_group_deliberation_interval() >= 60
    assert get_llm_task_live_floor("action") == 0
