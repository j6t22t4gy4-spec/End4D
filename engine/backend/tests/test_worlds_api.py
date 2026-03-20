"""POST /worlds 프롬프트 계약."""
from fastapi.testclient import TestClient

from app.main import app

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
