"""God View 주입·재실행 (Phase 7)."""
import numpy as np
from fastapi.testclient import TestClient

from app.main import app
from app.core.store import world_store
from app.graph.time_flow import create_time_flow_graph
from app.models.cell import Cell


client = TestClient(app)


def _cell(*, cell_id: str, role: str, zone_id: str, x: float = 0.0) -> Cell:
    return Cell(
        cell_id=cell_id,
        x=x,
        y=0.0,
        z=0.0,
        t=0.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key=role,
        role_label=role,
        zone_id=zone_id,
        zone_label=zone_id,
    )


def test_inject_requires_snapshot():
    wid = world_store.create(t_max=3, initial_cell_count=1)
    r = client.post(
        f"/worlds/{wid}/inject",
        json={"t": 0, "event_type": "noop", "payload": {}},
    )
    assert r.status_code == 404


def test_inject_nutrient_and_forward_recomputes():
    wid = world_store.create(t_max=4, initial_cell_count=2)
    entry = world_store.get(wid)
    store = entry["snapshot_store"]
    graph = create_time_flow_graph()
    graph.invoke(
        {
            "t_max": 4.0,
            "initial_cell_count": 2,
            "snapshot_store": store,
        },
        config={"recursion_limit": 20},
    )

    energy_before = sum(c.energy for c in store.get(2.0).cells)

    r = client.post(
        f"/worlds/{wid}/inject",
        json={
            "t": 2.0,
            "event_type": "nutrient_burst",
            "payload": {"amount": 50.0},
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["forwarded"] is True
    assert data["final_t"] == 4.0

    energy_after = sum(c.energy for c in store.get(2.0).cells)
    assert energy_after > energy_before


def test_policy_shift_persists_across_duration_for_target_role():
    wid = world_store.create(t_max=6, initial_cell_count=2)
    entry = world_store.get(wid)
    store = entry["snapshot_store"]
    graph = create_time_flow_graph()
    graph.invoke(
        {
            "t_max": 6.0,
            "initial_cells": [
                _cell(cell_id="firm-1", role="기업", zone_id="zone-1"),
                _cell(cell_id="citizen-1", role="시민", zone_id="zone-2", x=1.0),
            ],
            "snapshot_store": store,
        },
        config={"recursion_limit": 20},
    )

    r = client.post(
        f"/worlds/{wid}/inject",
        json={
            "t": 2.0,
            "event_type": "policy_shift",
            "payload": {
                "name": "industrial tax credit",
                "summary": "특정 산업 구역에 세액공제를 제공한다",
                "intensity": 0.8,
                "duration_steps": 3,
                "target_roles": ["기업"],
                "target_zones": ["zone-1"],
                "effect_profile": "stimulus",
            },
        },
    )
    assert r.status_code == 200
    snap4 = store.get(4.0)
    assert snap4 is not None
    by_id = {cell.cell_id: cell for cell in snap4.cells}
    assert by_id["firm-1"].action_state["active_policy_names"] == ["industrial tax credit"]
    assert by_id["firm-1"].energy > by_id["citizen-1"].energy


def test_timeline_lists_points():
    wid = world_store.create(t_max=2, initial_cell_count=1)
    entry = world_store.get(wid)
    graph = create_time_flow_graph()
    graph.invoke(
        {"t_max": 2.0, "initial_cell_count": 1, "snapshot_store": entry["snapshot_store"]},
        config={"recursion_limit": 10},
    )
    r = client.get(f"/worlds/{wid}/timeline")
    assert r.status_code == 200
    pts = r.json()["points"]
    assert len(pts) >= 2
    assert all("cell_count" in p and "total_energy" in p for p in pts)


def test_timeline_summary_classifies_result():
    wid = world_store.create(t_max=3, initial_cell_count=2)
    entry = world_store.get(wid)
    graph = create_time_flow_graph()
    graph.invoke(
        {"t_max": 3.0, "initial_cell_count": 2, "snapshot_store": entry["snapshot_store"]},
        config={"recursion_limit": 12},
    )

    r = client.get(f"/worlds/{wid}/timeline/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["points_count"] >= 2
    assert data["first_t"] == 0.0
    assert data["last_t"] == 3.0
    assert data["final_cell_count"] >= 0
    assert data["outcome"] in {
        "extinct",
        "expanding",
        "contracting",
        "energy_accumulating",
        "energy_depleted",
        "stable",
    }


def test_state_export_and_restore_fork():
    wid = world_store.create(t_max=4, initial_cell_count=2)
    entry = world_store.get(wid)
    graph = create_time_flow_graph()
    graph.invoke(
        {"t_max": 4.0, "initial_cell_count": 2, "snapshot_store": entry["snapshot_store"]},
        config={"recursion_limit": 20},
    )

    export_res = client.get(f"/worlds/{wid}/state?t=2")
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert export_data["t"] == 2.0
    assert export_data["cell_count"] >= 1
    assert export_data["config_version"]
    assert "simulation_config" in export_data
    assert "behavior_log" in export_data["cells"][0]

    fork_res = client.post(
        f"/worlds/{wid}/restore",
        json={"t": 2.0, "target": "fork", "resume": True},
    )
    assert fork_res.status_code == 200
    fork_data = fork_res.json()
    assert fork_data["source_world_id"] == wid
    assert fork_data["world_id"] != wid
    assert fork_data["final_t"] == 4.0
    assert fork_data["config_version"]
    assert fork_data["comparison_meta"]["parent_world_id"] == wid

    fork_entry = world_store.get(fork_data["world_id"])
    assert fork_entry is not None
    assert fork_entry["snapshot_store"].get(2.0) is not None
    assert fork_entry["snapshot_store"].get(4.0) is not None
    world_res = client.get(f"/worlds/{fork_data['world_id']}")
    assert world_res.status_code == 200
    assert world_res.json()["comparison_meta"]["parent_world_id"] == wid
