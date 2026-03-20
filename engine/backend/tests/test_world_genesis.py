"""프롬프트 기반 세계 제안 (world_genesis 스텁)."""
from app.core.world_genesis import propose_world_from_prompt


def test_genesis_returns_plan():
    p = propose_world_from_prompt("단기 시나리오 몇 주 안에 시장 반응")
    assert p.t_max <= 100
    assert 6 <= p.initial_cell_count <= 48
    assert len(p.role_catalog) >= 3
    assert p.rationale
    assert p.t_step_unit
    assert p.t_step_semantic
    assert p.nutrient_per_step > 0


def test_genesis_long_horizon_keyword():
    p = propose_world_from_prompt("향후 10년 장기 예측 정책 시나리오를 시뮬하고 싶다")
    assert p.t_max >= 200
    assert "규제자" in p.role_catalog or "시장참여자" in p.role_catalog or len(p.role_catalog) >= 3
    assert p.nutrient_per_step >= 50
    assert "년" in p.t_step_semantic or "장기" in p.t_step_semantic


def test_genesis_hourly_smaller_nutrient():
    p = propose_world_from_prompt("실시간으로 시간당 호가 변동을 보고 싶다")
    assert p.t_step_unit == "hour"
    assert p.nutrient_per_step < 1.0
