"""Phase 6: 스텝 루프에 Emotion·Thought·메모리 연동."""
import numpy as np
import pytest

from app.core.snapshot import SnapshotStore
from app.graph.time_flow import create_time_flow_graph
from app.models.cell import Cell


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "0")
    monkeypatch.setenv("ORGANIC4D_LLM_PROVIDER", "stub")


def test_graph_run_preserves_vector_shapes_and_advances_t():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    out = graph.invoke(
        {
            "initial_cell_count": 3,
            "t_max": 22,
            "snapshot_store": store,
        }
    )
    assert out["current_t"] == 22
    for c in out["cells"]:
        assert c.emotion_vec.shape == (8,)
        assert c.thought_vec.shape == (256,)
        assert c.worldview_vec.shape == (384,)
        assert isinstance(c.memory, list)
        assert isinstance(c.short_memory, list)
        assert isinstance(c.long_memory, list)
        assert isinstance(c.behavior_log, list)
        assert isinstance(c.action_state, dict)


def test_graph_uses_engine_zone_layout_params():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    out = graph.invoke(
        {
            "initial_cell_count": 6,
            "t_max": 1,
            "snapshot_store": store,
            "engine_params": {
                "zone_count": 3,
                "zone_layout": "bands",
                "zone_spacing": 3.0,
            },
        }
    )
    zone_ids = {c.zone_id for c in out["cells"]}
    ys = {round(float(c.y), 1) for c in out["cells"]}
    assert len(zone_ids) == 3
    assert len(ys) >= 2


def test_graph_assigns_social_elevation_from_engine_params():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    out = graph.invoke(
        {
            "initial_cell_count": 4,
            "t_max": 1,
            "snapshot_store": store,
            "engine_params": {
                "z_mode": "wealth",
                "z_weight": 0.16,
                "z_scale": 10.0,
            },
        }
    )
    assert any(float(c.z) > 0.0 for c in out["cells"])
    assert all(c.action_state["z_mode"] == "wealth" for c in out["cells"])
    assert all(float(c.action_state["z_weight"]) == 0.16 for c in out["cells"])


def test_thought_refresh_at_interval_changes_vector():
    """Thought는 첫 스텝과 cadence마다 갱신되어야 한다."""
    store = SnapshotStore()
    graph = create_time_flow_graph()
    graph.invoke(
        {
            "initial_cell_count": 1,
            "t_max": 21,
            "snapshot_store": store,
        }
    )
    snap0 = store.get(0.0)
    snap21 = store.get(21.0)
    assert snap0 is not None and snap21 is not None
    assert not np.allclose(snap0.cells[0].thought_vec, snap21.cells[0].thought_vec)
    assert str(snap21.cells[0].action_state.get("last_thought_summary", "")).strip()


def test_graph_writes_agent_social_memory_before_thought_refresh():
    """Internal agent observations become memory before the next Thought cycle."""
    store = SnapshotStore()
    graph = create_time_flow_graph()
    initial_cells = [
        Cell(
            cell_id=f"agent-{i}",
            x=float(i),
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
        )
        for i, role in enumerate(["citizen", "regulator", "producer"])
    ]
    graph.invoke(
        {
            "initial_cells": initial_cells,
            "t_max": 21,
            "snapshot_store": store,
        }
    )
    snap15 = store.get(15.0)
    snap21 = store.get(21.0)
    assert snap15 is not None and snap21 is not None
    assert any(
        "social_observation" in line
        for cell in snap15.cells
        for line in cell.memory
    )
    assert any(
        "borrowed_signal=" in line
        for cell in snap15.cells
        for line in cell.memory
    )
    assert any(
        str(cell.action_state.get("last_thought_summary", "")).strip()
        for cell in snap21.cells
    )


def test_graph_updates_xy_positions_from_social_field_dynamics():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    initial_cells = [
        Cell(
            cell_id=f"mover-{i}",
            x=float(i * 1.2),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=50.0 + i,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.1 * (i + 1)),
            worldview_vec=np.full(384, 0.05 * (i + 1)),
            role_key="citizen",
            role_label="citizen",
            action_state={"mobility_bias": 0.8},
        )
        for i in range(4)
    ]
    out = graph.invoke(
        {
            "initial_cells": initial_cells,
            "t_max": 5,
            "snapshot_store": store,
        }
    )
    moved = [
        abs(cell.x - initial_cells[idx].x) + abs(cell.y - initial_cells[idx].y)
        for idx, cell in enumerate(out["cells"])
    ]
    assert any(delta > 0.05 for delta in moved)
    assert any(float(cell.action_state.get("last_spatial_shift", 0.0)) > 0.0 for cell in out["cells"])
