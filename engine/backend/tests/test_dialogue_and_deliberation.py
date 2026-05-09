"""LLM dialogue and role-level deliberation tests."""
import json

import numpy as np

from app.llm.dialogue import apply_agent_dialogues_if_due
from app.llm.group_deliberation import apply_group_deliberation_if_due
from app.models.cell import Cell


def _cell(cell_id: str, x: float, role: str) -> Cell:
    return Cell(
        cell_id=cell_id,
        x=x,
        y=0.0,
        z=0.0,
        t=25.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key=role,
        role_label=role,
        action_state={"cooperation_bias": 0.5, "policy_sensitivity": 0.6},
    )


def test_agent_dialogue_writes_behavior_log(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_DIALOGUE_INTERVAL", "25")
    monkeypatch.setenv("ORGANIC4D_DIALOGUE_MAX_PAIRS", "2")

    def fake_generate(prompts, *, task):
        assert task == "dialogue"
        return [
            json.dumps(
                {
                    "summary_a": "citizen accepts a cautious compromise",
                    "summary_b": "regulator hears implementation concern",
                    "alignment_delta": 0.12,
                    "tension_delta": -0.03,
                    "cooperation_delta": 0.08,
                    "importance": 0.8,
                }
            )
            for _ in prompts
        ]

    monkeypatch.setattr("app.llm.dialogue.generate_reasoning_texts", fake_generate)
    cells = [_cell("a", 0.0, "citizen"), _cell("b", 1.0, "regulator")]
    out = apply_agent_dialogues_if_due(cells, current_t=25.0)

    assert out[0].behavior_log[-1]["event_type"] == "agent_dialogue"
    assert out[1].behavior_log[-1]["event_type"] == "agent_dialogue"
    assert out[0].action_state["cooperation_bias"] > 0.5
    assert out[0].long_memory[-1]["kind"] == "agent_dialogue"


def test_group_deliberation_updates_role_pressure(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_GROUP_DELIBERATION_INTERVAL", "50")
    monkeypatch.setenv("ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS", "2")
    monkeypatch.setenv("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE", "4")

    def fake_generate(prompts, *, task):
        assert task == "group_deliberation"
        return [
            json.dumps(
                {
                    "stance_summary": "role group forms a pro-stability coalition",
                    "cohesion_delta": 0.1,
                    "tension_delta": 0.02,
                    "coalition_signal": "moderate",
                    "importance": 0.82,
                }
            )
            for _ in prompts
        ]

    monkeypatch.setattr("app.llm.group_deliberation.generate_reasoning_texts", fake_generate)
    cells = [
        _cell("a", 0.0, "citizen"),
        _cell("b", 1.0, "citizen"),
        _cell("c", 2.0, "regulator"),
    ]
    out = apply_group_deliberation_if_due(cells, current_t=50.0)

    assert all(c.action_state["group_coalition_signal"] == "moderate" for c in out)
    assert out[0].behavior_log[-1]["event_type"] == "group_deliberation"
    assert out[0].long_memory[-1]["kind"] == "group_deliberation"
