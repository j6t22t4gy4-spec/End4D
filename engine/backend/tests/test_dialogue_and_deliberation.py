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

    def fake_run_dialogues(pairs, *, current_t):
        assert current_t == 25.0
        assert len(pairs) == 1
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
        ]

    monkeypatch.setattr("app.llm.dialogue.llm_facade.run_dialogues", fake_run_dialogues)
    cells = [_cell("a", 0.0, "citizen"), _cell("b", 1.0, "regulator")]
    out = apply_agent_dialogues_if_due(cells, current_t=25.0)

    assert out[0].behavior_log[-1]["event_type"] == "agent_dialogue"
    assert out[1].behavior_log[-1]["event_type"] == "agent_dialogue"
    assert out[0].action_state["cooperation_bias"] > 0.5
    assert out[0].long_memory[-1]["kind"] == "agent_dialogue"
    assert out[0].relationship_state["b"]["dialogue_count"] == 1
    assert out[0].relationship_state["b"]["trust"] > 0.0


def test_agent_dialogue_reuses_relationship_history(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_DIALOGUE_INTERVAL", "25")
    monkeypatch.setenv("ORGANIC4D_DIALOGUE_MAX_PAIRS", "1")

    def fake_run_dialogues(pairs, *, current_t):
        return [
            json.dumps(
                {
                    "summary_a": "citizen reopens trust with regulator",
                    "summary_b": "regulator accepts repeat channel",
                    "alignment_delta": 0.09,
                    "tension_delta": 0.01,
                    "cooperation_delta": 0.05,
                    "importance": 0.78,
                }
            )
        ]

    monkeypatch.setattr("app.llm.dialogue.llm_facade.run_dialogues", fake_run_dialogues)
    anchor = _cell("a", 0.0, "citizen").copy(
        relationship_state={
            "b": {
                "peer_id": "b",
                "trust": 0.62,
                "tension": 0.08,
                "alignment": 0.12,
                "dialogue_count": 2,
                "last_t": 20.0,
                "last_summary": "previous compromise",
            }
        }
    )
    close_new = _cell("c", 0.8, "citizen")
    known_peer = _cell("b", 1.2, "regulator")

    out = apply_agent_dialogues_if_due([anchor, close_new, known_peer], current_t=25.0)

    rel = out[0].relationship_state["b"]
    assert rel["dialogue_count"] == 3
    assert rel["trust"] > 0.62
    assert out[0].action_state["last_dialogue_peer_id"] == "b"


def test_group_deliberation_updates_role_pressure(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_GROUP_DELIBERATION_INTERVAL", "50")
    monkeypatch.setenv("ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS", "2")
    monkeypatch.setenv("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE", "4")

    def fake_deliberate_groups(groups, *, current_t):
        assert current_t == 50.0
        assert groups
        return [
            json.dumps(
                {
                    "stance_summary": "role group forms a pro-stability coalition",
                    "cohesion_delta": 0.1,
                    "tension_delta": 0.02,
                    "coalition_signal": "moderate",
                    "cohesion_score": 0.74,
                    "relationship_tension": 0.18,
                    "importance": 0.82,
                }
            )
            for _ in groups
        ]

    monkeypatch.setattr(
        "app.llm.group_deliberation.llm_facade.deliberate_groups",
        fake_deliberate_groups,
    )
    cells = [
        _cell("a", 0.0, "citizen").copy(
            relationship_state={
                "b": {
                    "peer_id": "b",
                    "trust": 0.64,
                    "tension": 0.12,
                    "alignment": 0.22,
                    "dialogue_count": 2,
                    "last_t": 45.0,
                    "last_summary": "shared stability concern",
                }
            }
        ),
        _cell("b", 1.0, "citizen").copy(
            relationship_state={
                "a": {
                    "peer_id": "a",
                    "trust": 0.58,
                    "tension": 0.1,
                    "alignment": 0.18,
                    "dialogue_count": 2,
                    "last_t": 45.0,
                    "last_summary": "shared stability concern",
                }
            }
        ),
        _cell("c", 2.0, "regulator"),
    ]
    out = apply_group_deliberation_if_due(cells, current_t=50.0)

    assert all(c.action_state["group_coalition_signal"] == "moderate" for c in out)
    assert out[0].action_state["group_cohesion_score"] == 0.74
    assert out[0].behavior_log[-1]["event_type"] == "group_deliberation"
    assert out[0].long_memory[-1]["kind"] == "group_deliberation"
    assert out[0].long_memory[-1]["payload"]["avg_trust"] > 0.0
