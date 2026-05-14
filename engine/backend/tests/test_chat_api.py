"""World chat API tests."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.store import world_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "0")


def test_world_chat_returns_grounded_answer_and_session():
    created = client.post("/worlds", json={"prompt": "기본소득 정책과 지역 상권 반응을 대화로 묻는다"})
    assert created.status_code == 200
    world_id = created.json()["world_id"]
    ran = client.post(f"/worlds/{world_id}/run", json={"stream": False})
    assert ran.status_code == 200

    times = client.get(f"/worlds/{world_id}/snapshots").json()["available_t"]
    latest_t = times[-1]
    response = client.post(
        f"/worlds/{world_id}/chat",
        json={
            "question": "지금 정책에 가장 민감한 집단은 누구야?",
            "context": {"t": latest_t, "target_type": "world"},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["world_id"] == world_id
    assert payload["session_id"]
    assert payload["answer"]
    assert payload["metadata"]["snapshot"]["t"] == latest_t
    assert payload["grounding"]["snapshot"]
    assert "persona" in payload["metadata"]

    entry = world_store.get(world_id)
    assert entry is not None
    sessions = dict(entry.get("chat_sessions") or {})
    assert payload["session_id"] in sessions
    assert len(sessions[payload["session_id"]]["messages"]) == 2


def test_world_chat_accepts_agent_context():
    created = client.post("/worlds", json={"prompt": "상인과 소비자의 갈등을 묻는다"})
    assert created.status_code == 200
    world_id = created.json()["world_id"]
    assert client.post(f"/worlds/{world_id}/run", json={"stream": False}).status_code == 200
    times = client.get(f"/worlds/{world_id}/snapshots").json()["available_t"]
    snap = client.get(f"/worlds/{world_id}/snapshots", params={"t": times[-1]}).json()
    cell_id = snap["cells"][0]["cell_id"]

    response = client.post(
        f"/worlds/{world_id}/chat",
        json={
            "question": "이 에이전트는 방금 무슨 걱정을 하고 있어?",
            "context": {"t": snap["t"], "target_type": "agent", "cell_id": cell_id},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["context"]["target_type"] == "agent"
    assert payload["metadata"]["persona"][0]["cell_id"] == cell_id
    assert any(item["cell_id"] == cell_id for item in payload["grounding"]["personas"])
