"""POST /worlds 프롬프트 계약."""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.store import world_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "0")


def test_create_world_requires_prompt():
    r = client.post("/worlds", json={})
    assert r.status_code == 422


def test_create_world_from_prompt():
    r = client.post(
        "/worlds",
        json={"prompt": "기후 정책과 시장 참여자의 장기 역학을 보고 싶다"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "world_id" in data
    assert data["t_max"] > 0
    assert data["initial_cell_count"] >= 6
    assert isinstance(data["role_catalog"], list)
    assert data["rationale"]
    assert "t_step_semantic" in data
    assert "t_step_unit" in data
    assert data["nutrient_per_step"] > 0
    assert data["persona_country"]
    assert "persona_source" in data
    assert "persona_count" in data
    assert "persona_distribution_summary" in data
    assert data["config_version"]
    assert "simulation_config" in data


def test_create_world_with_god_mode_overrides():
    r = client.post(
        "/worlds",
        json={
            "prompt": "한국 도시 정책 시뮬레이션",
            "god_mode": {
                "enabled": True,
                "auto_roles_from_personas": False,
                "overrides": {
                    "t_max": 42,
                    "initial_cell_count": 12,
                    "role_catalog": ["시민", "규제자", "기업"],
                    "persona_country": "JP",
                    "nutrient_per_step": 2.5,
                    "t_step_unit": "month",
                },
                "engine_params": {
                    "zone_count": 6,
                    "zone_layout": "bands",
                    "zone_spacing": 3.5,
                    "z_mode": "influence",
                    "z_weight": 0.18,
                    "z_scale": 14.0,
                },
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["t_max"] == 42
    assert data["initial_cell_count"] == 12
    assert data["role_catalog"] == ["시민", "규제자", "기업"]
    assert data["persona_country"] == "JP"
    assert data["nutrient_per_step"] == 2.5
    assert data["simulation_config"]["engine_params"]["control_mode"] == "god"
    assert data["simulation_config"]["engine_params"]["zone_layout"] == "bands"
    assert data["simulation_config"]["engine_params"]["z_mode"] == "influence"
    assert data["simulation_config"]["engine_params"]["z_weight"] == 0.18
    assert data["simulation_config"]["engine_params"]["z_scale"] == 14.0


def test_create_world_normalizes_short_prompt_for_simulation():
    r = client.post("/worlds", json={"prompt": "금리"})
    assert r.status_code == 200
    data = r.json()
    config = data["simulation_config"]
    params = config["engine_params"]

    assert params["raw_prompt"] == "금리"
    assert "원문 시나리오: 금리" in params["scenario_prompt"]
    assert "핵심 행위자" in params["scenario_prompt"]
    assert params["scenario_quality"]["was_expanded"] is True
    assert params["scenario_quality"]["domain"] == "시장/금융"
    assert config["scenario_prompt"] == params["scenario_prompt"]


def test_create_world_with_swarm_mode_allows_large_agent_pool():
    r = client.post(
        "/worlds",
        json={
            "prompt": "대량 시민 에이전트가 정책 충격에 반응하는 swarm 시나리오",
            "god_mode": {
                "enabled": True,
                "overrides": {
                    "simulation_mode": "swarm",
                    "t_max": 24,
                    "initial_cell_count": 1000,
                },
                "engine_params": {
                    "simulation_mode": "swarm",
                    "swarm_llm_mode": "packet",
                    "swarm_tier_model": {
                        "micro": {"rule_based": True},
                        "meso": {"group_count": 24, "llm_mode": "packet"},
                        "macro": {"fields": ["pressure", "shock", "drift"]},
                    },
                    "zone_count": 24,
                    "zone_layout": "swarm",
                },
            },
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["initial_cell_count"] == 1000
    params = data["simulation_config"]["engine_params"]
    assert params["simulation_mode"] == "swarm"
    assert params["swarm_llm_mode"] == "packet"
    assert params["swarm_tier_model"]["meso"]["group_count"] == 24
    assert params["zone_layout"] == "swarm"


def test_world_persona_preview():
    wid = world_store.create(
        t_max=1,
        initial_cell_count=1,
        persona_country="KR",
        persona_source="local:test",
        persona_catalog=[
            {
                "persona_id": "p1",
                "persona_text": "서울의 제조업 기술자",
                "role_key": "기술자",
                "role_label": "기술자",
                "country": "KR",
                "attrs": {"age": 34},
            }
        ],
    )
    r = client.get(f"/worlds/{wid}/personas?limit=1")
    assert r.status_code == 200
    data = r.json()
    assert data["persona_count"] == 1
    assert data["items"][0]["persona_id"] == "p1"
    assert data["source"]["country"] == "KR"
    assert data["source"]["source"] == "local:test"
    assert data["source"]["configured"] is True


def test_world_persona_preview_uses_local_pack_source(tmp_path, monkeypatch):
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    persona_file = packs_dir / "kr_persona.jsonl"
    persona_file.write_text(
        json.dumps(
            {
                "uuid": "p1",
                "professional_persona": "서울의 제조업 기술자",
                "occupation": "기술자",
                "country": "KR",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "data-packs/v1",
        "packs": [
            {
                "pack_id": "nemotron-kr-core",
                "kind": "persona",
                "country": "KR",
                "version": "2026.05",
                "relative_path": "kr_persona.jsonl",
                "license": "CC BY 4.0",
            }
        ],
    }
    manifest_path = packs_dir / "packs.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(manifest_path))

    r = client.post("/worlds", json={"prompt": "한국 산업 정책 시뮬레이션"})
    assert r.status_code == 200
    world_id = r.json()["world_id"]
    preview = client.get(f"/worlds/{world_id}/personas?limit=1")
    assert preview.status_code == 200
    data = preview.json()
    assert data["source"]["source"] == "local-pack:nemotron-kr-core@2026.05"


def test_create_world_includes_persona_distribution_summary_from_pack(tmp_path, monkeypatch):
    packs_dir = tmp_path / "packs"
    packs_dir.mkdir()
    persona_file = packs_dir / "kr_persona.jsonl"
    persona_file.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "uuid": "p1",
                        "professional_persona": "서울의 데이터 분석가",
                        "occupation": "분석가",
                        "province": "서울",
                        "age": 31,
                        "country": "KR",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "uuid": "p2",
                        "professional_persona": "부산의 자영업자",
                        "occupation": "자영업자",
                        "province": "부산",
                        "age": 52,
                        "country": "KR",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema_version": "data-packs/v1",
        "packs": [
            {
                "pack_id": "nemotron-kr-core",
                "kind": "persona",
                "country": "KR",
                "version": "2026.05",
                "relative_path": "kr_persona.jsonl",
                "license": "CC BY 4.0",
            }
        ],
    }
    manifest_path = packs_dir / "packs.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("ORGANIC4D_DATA_CACHE_DIR", str(packs_dir))
    monkeypatch.setenv("ORGANIC4D_DATA_PACK_MANIFEST", str(manifest_path))

    r = client.post("/worlds", json={"prompt": "한국 도시 경제 정책 시뮬레이션"})
    assert r.status_code == 200
    data = r.json()
    summary = data["persona_distribution_summary"]
    assert summary["persona_count"] >= 1
    assert data["simulation_config"]["engine_params"]["genesis_mode"] == "persona-aware"
    assert data["simulation_config"]["engine_params"]["zone_count"] >= 1
    assert "persona_initial_bias" in data["simulation_config"]["engine_params"]
    assert data["simulation_config"]["engine_params"]["z_scale"] >= 12.0


def test_delete_world_removes_it_from_store():
    created = client.post(
        "/worlds",
        json={"prompt": "삭제 가능한 world인지 확인하는 시나리오"},
    )
    assert created.status_code == 200
    world_id = created.json()["world_id"]

    deleted = client.delete(f"/worlds/{world_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/worlds/{world_id}")
    assert missing.status_code == 404


def test_get_world_includes_group_state():
    created = client.post(
        "/worlds",
        json={"prompt": "집단 상태가 world 응답에 보이는지 확인"},
    )
    assert created.status_code == 200
    world_id = created.json()["world_id"]
    entry = world_store.get(world_id)
    assert entry is not None
    entry["group_state"] = {
        "collective_signal": "realigning",
        "summary": {"role": {"avg_cohesion": 0.61}, "zone": {"avg_fracture_risk": 0.41}},
    }

    response = client.get(f"/worlds/{world_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["group_state"]["collective_signal"] == "realigning"
