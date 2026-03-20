"""God View 주입·재실행 (Phase 7)."""
from fastapi.testclient import TestClient

from app.main import app
from app.core.store import world_store
from app.graph.time_flow import create_time_flow_graph


client = TestClient(app)


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
