"""프롬프트 기반 세계 제안 (world_genesis 스텁)."""
import json

import pytest

from app.core.persona_dataset import PersonaSeed
from app.core.world_genesis import apply_persona_distribution_to_plan, propose_world_from_prompt


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
