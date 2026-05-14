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
            "scene_agent_limit": 64,
            "pressure_grid_size": 12,
            "min_interactions_per_step": 2,
            "max_interactions_per_step": 8,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["config"]["agent_count"] == 160
    assert data["final"]["t"] == 5
    assert data["final"]["metrics"]["simulation_mode"] == "swarm"
    assert data["final"]["metrics"]["llm_mode"] == "packet"
    assert data["final"]["metrics"]["llm_packet_count"] > 0
    assert data["final"]["metrics"]["internal_interactions"] >= 10
    assert data["final"]["metrics"]["last_interactions_per_step"] >= 2
    assert data["final"]["agent_sample"] == []
    assert data["final"]["full_agents"] == []
    assert data["final"]["scene"]["agent_count"] == 160
    assert len(data["final"]["scene"]["agents"]) <= 64
    assert data["final"]["metrics"]["pressure_grid_cells"] == 144
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


def test_swarm_run_endpoint_accepts_persona_catalog_without_echoing_it():
    response = client.post(
        "/swarm/run",
        json={
            "agent_count": 90,
            "meso_group_count": 9,
            "steps": 2,
            "scenario_prompt": "서울 자영업 규제와 물류 이동 제한",
            "persona_catalog": [
                {
                    "persona_id": "p1",
                    "persona_text": "서울의 자영업 상인",
                    "role_key": "자영업 상인",
                    "role_label": "자영업 상인",
                    "attrs": {"occupation": "자영업", "district": "서울"},
                },
                {
                    "persona_id": "p2",
                    "persona_text": "대구의 물류 기사",
                    "role_key": "물류 기사",
                    "role_label": "물류 기사",
                    "attrs": {"occupation": "물류", "district": "대구"},
                },
            ],
            "scene_agent_limit": 12,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["config"]["persona_count"] == 2
    assert "persona_catalog" not in data["config"]
    assert data["final"]["metrics"]["avg_persona_grounding"] > 0.5
    assert any(agent["role"] == "자영업 상인" for agent in data["final"]["scene"]["agents"])


def test_swarm_run_endpoint_only_returns_full_agents_when_requested():
    response = client.post(
        "/swarm/run",
        json={
            "agent_count": 32,
            "meso_group_count": 4,
            "steps": 2,
            "include_full_agents": True,
            "scene_agent_limit": 8,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["final"]["full_agents"]) == 32
    assert len(data["final"]["scene"]["agents"]) <= 8
    assert data["final"]["metrics"]["full_agents_included"] is True
