"""Phase 6: 스텝 루프에 Emotion·Thought·메모리 연동."""
import os

import numpy as np
import pytest

from app.api.run import _build_live_observer_cells
from app.core.snapshot import SnapshotStore
from app.graph.nodes import step_loop_node
from app.graph.time_flow import _create_initial_cells, create_time_flow_graph
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
        assert "collective_pressure" in c.action_state
        assert "group_influence_applied" in c.action_state


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


def test_precision_step_runs_internal_interactions_inside_t():
    cells = [
        Cell(
            cell_id=f"precision-agent-{i}",
            x=float(i * 0.8),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=55.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.04 * (i + 1)),
            worldview_vec=np.full(384, 0.03 * (i + 1)),
            role_key="citizen",
            role_label="citizen",
            action_state={"policy_sensitivity": 0.95, "mobility_bias": 0.65},
        )
        for i in range(4)
    ]

    out = step_loop_node(
        {
            "cells": cells,
            "current_t": 0.0,
            "t_max": 1.0,
            "world_events": [],
            "engine_params": {
                "simulation_mode": "precision",
                "min_interactions_per_step": 3,
                "max_interactions_per_step": 3,
            },
        }
    )

    assert out["current_t"] == 1.0
    assert all(int(cell.action_state.get("internal_interactions", 0)) == 3 for cell in out["cells"])
    assert any("t=0." in line and "social_observation" in line for cell in out["cells"] for line in cell.memory)


def test_swarm_packet_mode_overrides_llm_cadence_during_step(monkeypatch):
    captured: dict[str, str | None] = {}

    def capture_action_env(cells, current_t):
        captured["action_interval"] = os.environ.get("ORGANIC4D_ACTION_INTERVAL")
        captured["sample_size"] = os.environ.get("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE")
        captured["deliberation_interval"] = os.environ.get("ORGANIC4D_GROUP_DELIBERATION_INTERVAL")
        captured["deliberation_groups"] = os.environ.get("ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS")
        captured["action_priority"] = os.environ.get("ORGANIC4D_LLM_PRIORITY_ACTION")
        captured["group_priority"] = os.environ.get("ORGANIC4D_LLM_PRIORITY_GROUP_DELIBERATION")
        return cells

    monkeypatch.setattr("app.graph.nodes.update_thoughts_if_due", lambda cells, current_t: cells)
    monkeypatch.setattr("app.graph.nodes.update_worldviews_if_due", lambda cells, current_t: cells)
    monkeypatch.setattr("app.graph.nodes.update_action_states_if_due", capture_action_env)
    monkeypatch.setattr("app.graph.nodes.apply_agent_dialogues_if_due", lambda cells, current_t: cells)
    monkeypatch.setattr(
        "app.graph.nodes.apply_group_deliberation_if_due",
        lambda cells, current_t, coalition_state=None, coalition_history=None: (
            cells,
            dict(coalition_state or {}),
            list(coalition_history or []),
        ),
    )
    cells = _create_initial_cells(
        count=8,
        role_catalog=["citizen", "worker"],
        engine_params={"simulation_mode": "swarm", "zone_count": 4, "zone_layout": "swarm"},
    )

    out = step_loop_node(
        {
            "cells": cells,
            "current_t": 0.0,
            "t_max": 1.0,
            "engine_params": {
                "simulation_mode": "swarm",
                "swarm_llm_mode": "packet",
                "swarm_tier_model": {"meso": {"group_count": 24, "llm_mode": "packet"}},
            },
            "world_events": [],
        }
    )

    assert out["current_t"] == 1.0
    assert captured["action_interval"] == "16"
    assert captured["deliberation_interval"] == "6"
    assert captured["deliberation_groups"] == "24"
    assert captured["action_priority"] == "3"
    assert captured["group_priority"] == "0"
    assert os.environ.get("ORGANIC4D_ACTION_INTERVAL") is None


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


def test_persona_attrs_seed_action_priors():
    persona_catalog = [
        {
            "persona_id": "persona-1",
            "persona_text": "A civic-minded delivery worker in Seoul who volunteers on weekends.",
            "role_key": "citizen",
            "role_label": "citizen",
            "country": "KR",
            "attrs": {
                "occupation": "delivery driver",
                "hobbies_and_interests": "community volunteer, local activism",
                "region": "Seoul metro",
                "transportation": "motorbike and subway",
                "education_level": "master",
            },
        }
    ]
    cells = _create_initial_cells(
        count=1,
        t=0.0,
        role_catalog=["citizen"],
        persona_catalog=persona_catalog,
        engine_params={"zone_count": 1},
    )
    action_state = cells[0].action_state
    assert float(action_state["mobility_bias"]) > 0.55
    assert float(action_state["cooperation_bias"]) > 0.6
    assert float(action_state["policy_sensitivity"]) > 0.55
    assert "persona_prior_summary" in action_state
    assert action_state["persona_prior_factors"]


def test_persona_distribution_bias_seeds_initial_cells():
    persona_catalog = [
        {
            "persona_id": "persona-1",
            "persona_text": "A Seoul public nurse with strong civic engagement.",
            "role_key": "nurse",
            "role_label": "public nurse",
            "country": "KR",
            "attrs": {"occupation": "public nurse", "province": "Seoul", "age": 45},
        }
    ]
    cells = _create_initial_cells(
        count=1,
        t=0.0,
        role_catalog=["nurse"],
        persona_catalog=persona_catalog,
        engine_params={
            "zone_count": 1,
            "persona_initial_bias": {
                "energy_offset": 3.0,
                "cooperation_delta": 0.08,
                "policy_sensitivity_delta": 0.07,
            },
        },
    )
    action_state = cells[0].action_state
    assert cells[0].energy >= 53.0
    assert float(action_state["cooperation_bias"]) >= 0.56
    assert float(action_state["policy_sensitivity"]) >= 0.57
    assert action_state["persona_distribution_bias"]["energy_offset"] == 3.0


def test_graph_emits_collective_group_state_and_feedback():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    initial_cells = [
        Cell(
            cell_id=f"group-{idx}",
            x=float(idx),
            y=float(idx % 2),
            z=0.1 * idx,
            t=0.0,
            energy=45.0 + idx * 3,
            gene_vec=np.zeros(32),
            emotion_vec=np.full(8, 0.05 * (idx + 1)),
            thought_vec=np.full(256, 0.02 * (idx + 1)),
            worldview_vec=np.full(384, 0.03 * (idx + 1)),
            role_key="citizen" if idx < 3 else "merchant",
            role_label="citizen" if idx < 3 else "merchant",
            zone_id="zone-a" if idx % 2 == 0 else "zone-b",
            zone_label="zone-a" if idx % 2 == 0 else "zone-b",
            action_state={"mobility_bias": 0.35 + idx * 0.05},
        )
        for idx in range(6)
    ]
    out = graph.invoke(
        {
            "initial_cells": initial_cells,
            "t_max": 2,
            "snapshot_store": store,
        }
    )
    group_state = dict(out.get("group_state") or {})
    assert group_state["collective_signal"] in {"stable", "realigning", "fracturing"}
    assert "citizen" in group_state["role_groups"]
    assert "zone-a" in group_state["zone_groups"]
    sample = out["cells"][0].action_state
    assert "role_group_cohesion" in sample
    assert "zone_group_tension" in sample
    assert "collective_pressure" in sample
    assert "decision_pressure_delta" in sample
    assert "group_pressure_reason" in sample
