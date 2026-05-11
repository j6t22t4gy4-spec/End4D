"""Review summary API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_review_summary_returns_summary_and_annotations():
    created = client.post(
        "/worlds",
        json={"prompt": "청년 고용 정책이 장기 신념과 지역 격차에 미치는 영향을 본다"},
    )
    assert created.status_code == 200
    world_id = created.json()["world_id"]

    ran = client.post(f"/worlds/{world_id}/run", json={"stream": False})
    assert ran.status_code == 200

    review = client.get(f"/worlds/{world_id}/review/summary")
    assert review.status_code == 200
    payload = review.json()

    assert payload["world_id"] == world_id
    assert payload["summary"]
    assert payload["summary_mode"] in {"heuristic", "llm"}
    assert isinstance(payload["timeline_annotations"], list)
    assert "metrics" in payload
    assert "review_meta" in payload
