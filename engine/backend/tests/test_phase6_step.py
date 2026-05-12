"""Phase 6: 스텝 루프에 Emotion·Thought·메모리 연동."""
import numpy as np
import pytest

from app.api.run import _build_live_observer_cells
from app.core.snapshot import SnapshotStore
from app.graph.time_flow import create_time_flow_graph
from app.llm import thought as thought_module
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
    assert "thought_continuity_score" in snap21.cells[0].action_state
    assert "thought_continuity_state" in snap21.cells[0].action_state


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
    assert any(str(cell.action_state.get("mobility_state", "")) for cell in out["cells"])


def test_live_observer_sampling_balances_focus_and_zone_coverage():
    cells = []
    for idx in range(8):
        zone_id = f"zone-{idx % 3}"
        cell = Cell(
            cell_id=f"observer-{idx}",
            x=float(idx),
            y=float(idx % 2),
            z=float(idx),
            t=5.0,
            energy=40.0 + idx * 5,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.05 * (idx + 1)),
            worldview_vec=np.zeros(384),
            role_key=f"role-{idx % 4}",
            role_label=f"role-{idx % 4}",
            zone_id=zone_id,
            zone_label=zone_id,
            action_state={
                "last_thought_summary": "reassess constraints" if idx in {0, 1, 2, 6} else "",
                "last_thought_t": float(4 + idx % 3),
                "thought_continuity_score": 0.75 if idx in {0, 1} else 0.2,
                "last_spatial_shift": 0.6 if idx in {3, 4, 7} else 0.05,
                "mobility_bias": 0.9 if idx in {3, 4} else 0.2,
            },
            short_memory=[{"summary": "recent signal"}] * (idx % 3),
            behavior_log=[{"summary": "behavior", "event_type": "thought_update"}] * (1 + idx % 2),
        )
        cells.append(cell)

    observer_cells, sampled = _build_live_observer_cells(cells, limit=6)
    assert sampled is True
    focuses = {str(cell["action_state"].get("observer_focus")) for cell in observer_cells}
    zones = {str(cell.get("zone_id")) for cell in observer_cells}
    assert "thought" in focuses
    assert "mover" in focuses
    assert "zone" in focuses or len(zones) >= 3
    assert len(zones) >= 2
    assert all("observer_score" in cell["action_state"] for cell in observer_cells)


def test_thought_continuity_prefers_semantic_similarity(monkeypatch):
    def fake_embed_texts(texts, dim):
        vectors = []
        for text in texts:
            if "food crisis" in text:
                vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
            elif "supply collapse" in text:
                vec = np.array([0.92, 0.08, 0.0], dtype=np.float32)
            else:
                vec = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            padded = np.zeros(dim, dtype=np.float32)
            padded[: len(vec)] = vec
            padded /= np.linalg.norm(padded) + 1e-8
            vectors.append(padded)
        return np.stack(vectors, axis=0)

    monkeypatch.setattr(thought_module, "embed_texts", fake_embed_texts)
    thought_module._CONTINUITY_EMBED_CACHE.clear()

    score = thought_module._thought_continuity_score(
        "The food crisis is escalating, so rationing may be necessary.",
        "A supply collapse is spreading, so rationing still looks necessary.",
    )
    assert score >= 0.8
    assert thought_module._continuity_state_label(score) == "stable"


def test_thought_continuity_falls_back_to_token_overlap(monkeypatch):
    def broken_embed_texts(texts, dim):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(thought_module, "embed_texts", broken_embed_texts)
    thought_module._CONTINUITY_EMBED_CACHE.clear()

    score = thought_module._thought_continuity_score(
        "Local transport pressure keeps rising around the zone boundary.",
        "Local transport pressure keeps rising around the zone boundary tonight.",
    )
    assert score > 0.7
