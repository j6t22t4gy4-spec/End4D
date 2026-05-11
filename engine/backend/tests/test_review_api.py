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


def test_review_diff_returns_comparison():
    base = client.post(
        "/worlds",
        json={"prompt": "기본 정책 시나리오로 청년 고용과 지역 불평등을 본다"},
    )
    assert base.status_code == 200
    base_world_id = base.json()["world_id"]
    assert client.post(f"/worlds/{base_world_id}/run", json={"stream": False}).status_code == 200

    target = client.post(
        "/worlds",
        json={"prompt": "강한 청년 고용 보조금 정책을 주입한 시나리오를 본다"},
    )
    assert target.status_code == 200
    target_world_id = target.json()["world_id"]
    assert client.post(f"/worlds/{target_world_id}/run", json={"stream": False}).status_code == 200

    diff = client.get(f"/worlds/{target_world_id}/review/diff", params={"base_world_id": base_world_id})
    assert diff.status_code == 200
    payload = diff.json()
    assert payload["base_world_id"] == base_world_id
    assert payload["target_world_id"] == target_world_id
    assert payload["summary"]
    assert isinstance(payload["key_deltas"], list)
    assert "compared_metrics" in payload
