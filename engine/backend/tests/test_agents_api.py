"""Agent group observability API tests."""
import numpy as np
from fastapi.testclient import TestClient

from app.core.store import world_store
from app.main import app
from app.models.cell import Cell

client = TestClient(app)


def test_agent_summary_groups_latest_snapshot_by_role():
    wid = world_store.create(
        t_max=11,
        initial_cell_count=4,
        role_catalog=["citizen", "regulator"],
        persona_country="KR",
        persona_source="local:test",
        persona_catalog=[
            {
                "persona_id": "p1",
                "persona_text": "서울의 정책 관심 시민",
                "role_key": "citizen",
                "role_label": "citizen",
                "country": "KR",
            },
            {
                "persona_id": "p2",
                "persona_text": "부산의 시장 규제 담당자",
                "role_key": "regulator",
                "role_label": "regulator",
                "country": "KR",
            },
        ],
    )
    store = world_store.get_snapshot_store(wid)
    assert store is not None
    cells = [
        Cell(
            cell_id=f"cell-{i}",
            x=float(i),
            y=0.0,
            z=0.0,
            t=11.0,
            energy=50.0 + i,
            gene_vec=np.zeros(32),
            emotion_vec=np.ones(8) * 0.1,
            thought_vec=np.zeros(256),
            worldview_vec=np.zeros(384),
            role_key="citizen" if i < 2 else "regulator",
            role_label="citizen" if i < 2 else "regulator",
            persona_country="KR",
            memory=["seed", "t=10 social_observation neighbors=1"],
        )
        for i in range(4)
    ]
    store.save(11.0, cells)

    response = client.get(f"/worlds/{wid}/agents/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["world_id"] == wid
    assert data["t"] == 11.0
    assert data["group_count"] >= 2
    assert data["cell_count"] >= 4
    assert any(group["role_key"] == "citizen" for group in data["groups"])
    assert all("dominant_emotion" in group for group in data["groups"])
    assert all("avg_interaction_quality" in group for group in data["groups"])

    stance_response = client.get(f"/worlds/{wid}/agents/stance-summary")
    assert stance_response.status_code == 200
    stance_data = stance_response.json()
    assert stance_data["world_id"] == wid
    assert stance_data["groups"]
    assert all("stance" in group for group in stance_data["groups"])


def test_agent_belief_trajectory_tracks_role_and_zone_changes():
    wid = world_store.create(
        t_max=2,
        initial_cell_count=4,
        role_catalog=["citizen", "regulator"],
        persona_country="KR",
        persona_source="local:test",
    )
    store = world_store.get_snapshot_store(wid)
    assert store is not None

    def cells_at(t: float, pressure: float, tension: float) -> list[Cell]:
        cells: list[Cell] = []
        for idx in range(4):
            is_citizen = idx < 2
            role = "citizen" if is_citizen else "regulator"
            zone = "north" if idx % 2 == 0 else "south"
            role_pressure = pressure if is_citizen else pressure * 0.5
            role_tension = tension if is_citizen else tension * 0.4
            action_state = {
                "role_group_cohesion": 0.72 - role_tension * 0.2,
                "role_group_tension": role_tension,
                "role_group_fracture_risk": role_pressure,
                "role_group_drift_velocity": 0.08 + pressure * 0.1,
                "zone_group_cohesion": 0.64,
                "zone_group_tension": tension * (0.8 if zone == "south" else 0.45),
                "zone_group_fracture_risk": pressure * (0.7 if zone == "south" else 0.35),
                "zone_group_drift_velocity": 0.05 + tension * 0.12,
                "collective_pressure": role_pressure,
                "cooperation_bias": 0.52,
                "policy_sensitivity": 0.56 + pressure * 0.1,
                "resource_bias": 0.48,
                "mobility_bias": 0.44,
            }
            cells.append(
                Cell(
                    cell_id=f"cell-{idx}",
                    x=float(idx),
                    y=float(idx % 2),
                    z=float(idx) * 0.1 + pressure,
                    t=t,
                    energy=50.0,
                    gene_vec=np.zeros(32),
                    emotion_vec=np.ones(8) * 0.1,
                    thought_vec=np.zeros(256),
                    worldview_vec=np.zeros(384),
                    role_key=role,
                    role_label=role,
                    zone_id=zone,
                    zone_label=zone,
                    action_state=action_state,
                )
            )
        return cells

    store.save(0.0, cells_at(0.0, pressure=0.12, tension=0.1))
    store.save(1.0, cells_at(1.0, pressure=0.34, tension=0.25))
    store.save(2.0, cells_at(2.0, pressure=0.58, tension=0.5))

    role_response = client.get(f"/worlds/{wid}/agents/belief-trajectory")
    assert role_response.status_code == 200
    role_data = role_response.json()
    assert role_data["group_kind"] == "role"
    assert role_data["point_count"] == 3
    citizen = next(group for group in role_data["groups"] if group["group_id"] == "citizen")
    assert citizen["latest_stance"] == "contested"
    assert citizen["deltas"]["pressure_delta"] > 0.3
    assert citizen["points"][-1]["pressure_bucket"] == "elevated"
    assert "policy" in citizen["points"][-1]["stance_signature"]

    zone_response = client.get(f"/worlds/{wid}/agents/belief-trajectory", params={"group_kind": "zone"})
    assert zone_response.status_code == 200
    zone_data = zone_response.json()
    assert zone_data["group_kind"] == "zone"
    assert zone_data["groups"]
    assert all(group["points"] for group in zone_data["groups"])
