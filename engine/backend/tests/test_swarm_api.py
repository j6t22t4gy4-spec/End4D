from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_swarm_run_endpoint_returns_lightweight_runtime_payload():
    response = client.post(
        "/swarm/run",
        json={
            "agent_count": 160,
            "meso_group_count": 8,
            "steps": 5,
            "llm_mode": "packet",
            "packet_interval": 2,
            "policy_intensity": 0.6,
            "include_agent_sample": False,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["config"]["agent_count"] == 160
    assert data["final"]["t"] == 5
    assert data["final"]["metrics"]["simulation_mode"] == "swarm"
    assert data["final"]["metrics"]["llm_mode"] == "packet"
    assert data["final"]["metrics"]["llm_packet_count"] > 0
    assert data["final"]["agent_sample"] == []
    assert len(data["trajectory"]) == 6


def test_swarm_run_endpoint_agent_mode_counts_sample_prompts():
    response = client.post(
        "/swarm/run",
        json={
            "agent_count": 160,
            "meso_group_count": 8,
            "steps": 5,
            "llm_mode": "agent",
            "packet_interval": 2,
            "agent_llm_sample_size": 16,
            "agent_sample_size": 4,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["final"]["metrics"]["llm_mode"] == "agent"
    assert data["final"]["metrics"]["llm_prompt_count"] > data["final"]["metrics"]["llm_packet_count"]
    assert len(data["final"]["agent_sample"]) == 4
