"""LLM-backed action and policy integration tests."""
import numpy as np

from app.core.inject_handlers import apply_inject_to_cells
from app.llm.actions import _heuristic_action_state, _parse_action_state, update_action_states_if_due
from app.llm.thought import _summarize_thought_text
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
        persona_text=f"{role} persona focused on neighborhood survival and policy tradeoffs",
        persona_attrs={"district": "서울", "occupation": role, "scenario": "임대료 급등과 지역 규제 충격"},
        zone_id="zone-seoul",
        zone_label="서울 상권",
    )


def test_action_update_populates_action_state(monkeypatch):
    def fake_decide_actions(cells):
        assert len(cells) == 1
        return [
            '{"strategy_summary":"build coalition","resource_bias":0.7,"risk_tolerance":0.4,"cooperation_bias":0.8,"policy_sensitivity":0.6,"mobility_bias":0.3}'
        ]

    monkeypatch.setattr("app.llm.actions.llm_facade.decide_actions", fake_decide_actions)
    cell = _cell().copy(
        action_state={
            "collective_signal": "fracturing",
            "collective_pressure": 0.66,
            "role_group_cohesion": 0.41,
            "role_group_fracture_risk": 0.72,
            "zone_group_tension": 0.63,
            "zone_group_drift_velocity": 0.44,
            "group_influence_applied": True,
        }
    )
    updated = update_action_states_if_due([cell], current_t=10.0)
    assert updated[0].action_state["cooperation_bias"] < 0.8
    assert updated[0].action_state["policy_sensitivity"] > 0.6
    assert updated[0].behavior_log[-1]["event_type"] == "action_plan"
    assert updated[0].action_state["collective_signal"] == "fracturing"
    assert updated[0].action_state["group_influence_applied"] is True
    assert updated[0].action_state["collective_influence_applied"] is True
    assert updated[0].action_state["collective_action_decision_delta"] > 0.0
    assert "fracture" in updated[0].action_state["group_pressure_reason"]


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


def test_policy_shift_records_collective_policy_effect(monkeypatch):
    def fake_interpret_policy(cells, *, event_type, payload):
        return [
            '{"memory_summary":"reacts under social pressure","emotion_index":3,"emotion_delta":0.1,"cooperation_shift":0.05,"policy_sensitivity_shift":0.12,"importance":0.72}'
        ]

    monkeypatch.setattr("app.llm.policy.llm_facade.interpret_policy", fake_interpret_policy)
    cell = _cell("worker").copy(
        action_state={
            "collective_pressure": 0.7,
            "zone_group_tension": 0.68,
            "role_group_fracture_risk": 0.74,
            "collective_signal": "fracturing",
        }
    )
    updated = apply_inject_to_cells(
        [cell],
        "policy_shift",
        {
            "name": "labor protections",
            "summary": "보호 정책 강화",
            "intensity": 0.6,
            "target_roles": ["worker"],
        },
    )
    action_state = updated[0].action_state
    assert action_state["collective_policy_effect"] > 0.0
    assert action_state["collective_policy_decision_delta"] > 0.0
    assert action_state["collective_influence_applied"] is True
    assert "fracture" in action_state["group_pressure_reason"]
    assert action_state["fracture_signal_received"] is True


def test_action_summary_is_grounded_and_localized(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_UI_LANGUAGE", "ko")
    cell = _cell("자영업 상인").copy(
        action_state={
            "collective_pressure": 0.62,
            "collective_pressure_bucket": "watch",
            "collective_signal": "fracturing",
        },
        behavior_log=[
            {
                "event_type": "social_observation",
                "summary": "근처 노동자 그룹과 임대료 정책을 두고 긴장이 높아짐",
            }
        ],
    )

    fallback = _heuristic_action_state(cell)
    assert "행동:" in str(fallback["last_action_summary"])
    assert "이유:" in str(fallback["last_action_summary"])
    assert "대상:" in str(fallback["last_action_summary"])
    assert "heuristic adaptive stance" not in str(fallback["last_action_summary"])

    parsed = _parse_action_state(
        '{"strategy_summary":"adaptive planning","resource_bias":0.6,"risk_tolerance":0.5,'
        '"cooperation_bias":0.5,"policy_sensitivity":0.5,"mobility_bias":0.4}',
        cell,
    )
    assert "서울 상권" in str(parsed["last_action_summary"])
    assert "자영업 상인" in str(parsed["last_action_summary"])


def test_thought_summary_regrounds_generic_english_in_korean(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_UI_LANGUAGE", "ko")
    cell = _cell("정책 담당자").copy(
        action_state={"collective_pressure": 0.7, "collective_pressure_bucket": "elevated"},
        behavior_log=[{"event_type": "agent_dialogue", "summary": "주민 대표가 규제 완화를 요구함"}],
    )

    summary = _summarize_thought_text("reassessing immediate goals and constraints", cell)

    assert "정책 담당자" in summary
    assert "서울 상권" in summary
    assert "reassessing" not in summary.lower()
