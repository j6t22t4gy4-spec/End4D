"""Session thread API tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "0")


def test_create_session_and_list():
    created = client.post("/sessions", json={"title": "Korea policy thread"})
    assert created.status_code == 200
    session = created.json()
    assert session["session_id"]
    assert session["title"] == "Korea policy thread"
    assert session["world_count"] == 0

    listed = client.get("/sessions")
    assert listed.status_code == 200
    sessions = listed.json()
    assert any(item["session_id"] == session["session_id"] for item in sessions)


def test_world_creation_attaches_to_session():
    created = client.post("/sessions", json={"title": "Housing strategy"})
    session_id = created.json()["session_id"]

    world_res = client.post(
        "/worlds",
        json={
            "prompt": "금리와 주택 보조금의 장기 신념 변화를 본다",
            "session_id": session_id,
        },
    )
    assert world_res.status_code == 200
    world = world_res.json()
    assert world["session_id"] == session_id

    session_res = client.get(f"/sessions/{session_id}")
    assert session_res.status_code == 200
    session = session_res.json()
    assert session["world_count"] >= 1
    assert session["latest_world_id"] == world["world_id"]
    assert any(item["world_id"] == world["world_id"] for item in session["worlds"])


def test_rename_and_delete_session():
    created = client.post("/sessions", json={"title": "Initial session"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    renamed = client.patch(f"/sessions/{session_id}", json={"title": "Renamed session"})
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Renamed session"

    deleted = client.delete(f"/sessions/{session_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    missing = client.get(f"/sessions/{session_id}")
    assert missing.status_code == 404


def test_session_review_returns_multi_world_summary():
    created = client.post("/sessions", json={"title": "Long horizon thread"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    for prompt in [
        "청년 고용 정책의 장기 집단 분열을 본다",
        "지역 불평등과 사회적 고도 변화를 본다",
    ]:
        world_res = client.post("/worlds", json={"prompt": prompt, "session_id": session_id})
        assert world_res.status_code == 200
        world_id = world_res.json()["world_id"]
        assert client.post(f"/worlds/{world_id}/run", json={"stream": False}).status_code == 200

    review = client.get(f"/sessions/{session_id}/review")
    assert review.status_code == 200
    payload = review.json()
    assert payload["session_id"] == session_id
    assert payload["summary"]
    assert int(payload["metrics"]["world_count"]) >= 2
    assert isinstance(payload["strongest_worlds"], list)
    assert isinstance(payload["ranked_worlds"], list)
    assert isinstance(payload["recommended_pairs"], list)
    assert "group_tables" in payload
    assert "lineage_summary" in payload
    assert "policy_lineage_bridge" in payload
    assert "citations" in payload
    assert "key_findings.0" in payload["citations"]
    assert "decision_implications.0" in payload["citations"]
    assert all(item.get("anchor_id") for item in payload["citations"]["key_findings.0"])
    assert "repair_used" in payload["review_meta"]["summary"]


def test_session_review_query_returns_answer_and_grounding():
    created = client.post("/sessions", json={"title": "Session analyst thread"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    for prompt in [
        "정책 실험 A로 집단 분열과 지역 격차를 본다",
        "정책 실험 B로 사회적 고도와 응집도 변화를 본다",
    ]:
        world_res = client.post("/worlds", json={"prompt": prompt, "session_id": session_id})
        assert world_res.status_code == 200
        world_id = world_res.json()["world_id"]
        assert client.post(f"/worlds/{world_id}/run", json={"stream": False}).status_code == 200

    response = client.post(
        f"/sessions/{session_id}/review/query",
        json={"question": "이 세션에서 가장 불안정했던 정책 실험은 무엇이고 왜 그런가?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert payload["answer"]
    assert isinstance(payload["evidence"], list)
    assert "grounding" in payload
    assert isinstance(payload["citations"], list)


def test_session_review_accepts_objective_query():
    created = client.post("/sessions", json={"title": "Objective ranking thread"})
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    for prompt in [
        "응집도가 높은 정책 실험을 본다",
        "분열과 지역 fracture가 큰 정책 실험을 본다",
    ]:
        world_res = client.post("/worlds", json={"prompt": prompt, "session_id": session_id})
        assert world_res.status_code == 200
        world_id = world_res.json()["world_id"]
        assert client.post(f"/worlds/{world_id}/run", json={"stream": False}).status_code == 200

    review = client.get(f"/sessions/{session_id}/review", params={"objective": "cohesion"})
    assert review.status_code == 200
    payload = review.json()
    assert payload["metrics"]["objective"] == "cohesion"
    assert isinstance(payload["ranked_worlds"], list)
    assert payload["objective_explanation"]
