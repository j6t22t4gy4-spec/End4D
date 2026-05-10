"""LLM-backed action and policy integration tests."""
import numpy as np

from app.core.inject_handlers import apply_inject_to_cells
from app.llm.actions import update_action_states_if_due
from app.models.cell import Cell


def _cell(role: str = "citizen") -> Cell:
    return Cell(
        cell_id=f"{role}-1",
        x=0.0,
        y=0.0,
        z=0.0,
        t=0.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key=role,
        role_label=role,
        persona_text=f"{role} persona",
    )


def test_action_update_populates_action_state(monkeypatch):
    def fake_decide_actions(cells):
        assert len(cells) == 1
        return [
            '{"strategy_summary":"build coalition","resource_bias":0.7,"risk_tolerance":0.4,"cooperation_bias":0.8,"policy_sensitivity":0.6,"mobility_bias":0.3}'
        ]

    monkeypatch.setattr("app.llm.actions.llm_facade.decide_actions", fake_decide_actions)
    updated = update_action_states_if_due([_cell()], current_t=10.0)
    assert updated[0].action_state["cooperation_bias"] == 0.8
    assert updated[0].behavior_log[-1]["event_type"] == "action_plan"


def test_policy_shift_uses_llm_interpretation(monkeypatch):
    def fake_interpret_policy(cells, *, event_type, payload):
        assert event_type == "policy_shift"
        assert payload["name"] == "housing subsidy reform"
        return [
            '{"memory_summary":"supports targeted subsidy reform","emotion_index":5,"emotion_delta":0.25,"cooperation_shift":0.1,"policy_sensitivity_shift":0.2,"importance":0.8}'
        ]

    monkeypatch.setattr("app.llm.policy.llm_facade.interpret_policy", fake_interpret_policy)
    updated = apply_inject_to_cells(
        [_cell("시민")],
        "policy_shift",
        {
            "name": "housing subsidy reform",
            "summary": "정부가 주거 보조금 구조를 개편한다",
            "intensity": 0.7,
            "target_roles": ["시민"],
        },
    )
    cell = updated[0]
    assert cell.behavior_log[-1]["event_type"] == "policy_interpretation"
    assert cell.action_state["policy_sensitivity"] > 0.5
    assert cell.emotion_vec[5] > 0
