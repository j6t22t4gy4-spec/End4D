"""POST /worlds 프롬프트 계약."""
from fastapi.testclient import TestClient

from app.main import app
from app.core.store import world_store

client = TestClient(app)


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
