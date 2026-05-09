"""Session thread API tests."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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
