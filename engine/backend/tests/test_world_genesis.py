"""프롬프트 기반 세계 제안 (world_genesis 스텁)."""
import json

import pytest

from app.core.persona_dataset import PersonaSeed
from app.core.world_genesis import apply_persona_distribution_to_plan, normalize_scenario_prompt, propose_world_from_prompt, refine_scenario_for_runtime


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "0")
    monkeypatch.setenv("ORGANIC4D_LLM_PROVIDER", "stub")


def test_genesis_returns_plan():
    p = propose_world_from_prompt("단기 시나리오 몇 주 안에 시장 반응")
    assert p.t_max <= 100
    assert 6 <= p.initial_cell_count <= 48
    assert len(p.role_catalog) >= 3
    assert p.rationale
    assert p.t_step_unit
    assert p.t_step_semantic
    assert p.nutrient_per_step > 0
    assert p.persona_country
    assert p.persona_source


def test_normalize_scenario_prompt_expands_short_input():
    scenario = normalize_scenario_prompt("금리")

    assert scenario["raw_prompt"] == "금리"
    assert "원문 시나리오: 금리" in scenario["scenario_prompt"]
    assert "핵심 행위자" in scenario["scenario_prompt"]
    assert "갈등/협력 축" in scenario["scenario_prompt"]
    assert scenario["scenario_quality"]["was_expanded"] is True
    assert scenario["scenario_quality"]["domain"] == "시장/금융"


def test_refine_scenario_for_runtime_uses_llm_director(monkeypatch):
    monkeypatch.setattr("app.core.world_genesis.get_llm_chat_enabled", lambda: True)

    def fake_direct_scenario(payload):
        return (
            """
            {
              "scenario_prompt": "청년 세입자와 임대인, 금리 충격을 둘러싼 실행용 시나리오",
              "actor_roles": ["청년 세입자", "소형 임대인", "정책 중재자", "금융기관"],
              "initial_zones": ["임차인 밀집지", "자산 보유 bloc", "정책 중재권"],
              "placement_logic": "세입자와 임대인은 가까운 경계에, 정책 중재자는 사이에 배치",
              "conflict_axes": ["주거비 부담", "자산 기대", "정책 신뢰"],
              "initial_scene_beats": ["세입자가 조건 조정을 요구", "임대인이 금리 비용을 전가"],
              "role_assignment_policy": "occupation과 scenario role 토큰을 매칭",
              "pressure_seeds": {"sensitive_roles": ["청년 세입자"]},
              "rationale": "director test"
            }
            """,
            {"provider": "stub-test", "model": "director", "prompt_count_sent": 1},
        )

    monkeypatch.setattr("app.core.world_genesis.llm_facade.direct_scenario", fake_direct_scenario)
    refined = refine_scenario_for_runtime(
        engine_params={"raw_prompt": "금리와 월세", "scenario_prompt": "원문 시나리오: 금리와 월세"},
        role_catalog=["생산자", "소비자"],
        persona_catalog=[],
        simulation_mode="precision",
    )

    assert refined["scenario_director_mode"] == "llm"
    assert refined["scenario_actor_roles"][0] == "청년 세입자"
    assert refined["zone_layout"] == "scenario_social_field"
    assert refined["scenario_quality"]["runtime_director_mode"] == "llm"


def test_genesis_long_horizon_keyword():
    p = propose_world_from_prompt("향후 10년 장기 예측 정책 시나리오를 시뮬하고 싶다")
    assert p.t_max >= 200
    assert "규제자" in p.role_catalog or "시장참여자" in p.role_catalog or len(p.role_catalog) >= 3
    assert p.nutrient_per_step >= 50
    assert "년" in p.t_step_semantic or "장기" in p.t_step_semantic
    assert p.persona_country == "KR"


def test_genesis_hourly_smaller_nutrient():
    p = propose_world_from_prompt("실시간으로 시간당 호가 변동을 보고 싶다")
    assert p.t_step_unit == "hour"
    assert p.nutrient_per_step < 1.0


def test_genesis_can_use_llm_json_plan(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "1")

    def fake_plan_genesis(prompt_text, heuristic_payload):
        assert "향후 30년 한국 사회 구조 변화" in prompt_text
        assert "initial_cell_count" in heuristic_payload
        return (
            json.dumps(
                {
                    "t_max": 320,
                    "initial_cell_count": 18,
                    "role_catalog": ["정부", "기업", "가계", "청년"],
                    "rationale": "LLM plan",
                    "t_step_semantic": "1 스텝 ≈ 1년",
                    "t_step_unit": "year",
                    "nutrient_per_step": 40,
                    "persona_country": "KR",
                    "persona_source": "llm:openai",
                },
                ensure_ascii=False,
            )
        )

    monkeypatch.setattr(
        "app.core.world_genesis.llm_facade.plan_genesis",
        fake_plan_genesis,
    )
    p = propose_world_from_prompt("향후 30년 한국 사회 구조 변화")
    assert p.t_max == 320
    assert p.initial_cell_count == 18
    assert p.role_catalog[:3] == ["정부", "기업", "가계"]
    assert p.persona_source == "llm:openai"


def test_genesis_can_absorb_persona_distribution():
    plan = propose_world_from_prompt("한국 산업 정책 시뮬레이션")
    personas = [
        PersonaSeed(
            persona_id="a",
            persona_text="서울의 데이터 분석가",
            role_key="분석가",
            role_label="분석가",
            country="KR",
            attrs={"province": "서울", "age": 33},
        ),
        PersonaSeed(
            persona_id="b",
            persona_text="부산의 자영업자",
            role_key="자영업자",
            role_label="자영업자",
            country="KR",
            attrs={"province": "부산", "age": 52},
        ),
    ]
    adjusted, bias = apply_persona_distribution_to_plan(plan, personas)
    assert adjusted.persona_distribution_summary["persona_count"] == 2
    assert adjusted.role_catalog[0] in {"분석가", "자영업자"}
    assert bias["zone_count"] >= 2
    assert adjusted.nutrient_per_step >= plan.nutrient_per_step
    assert "initial_bias" in bias
    assert "energy_offset" in bias["initial_bias"]
    assert bias["z_scale_multiplier"] >= 1.0
