"""Organic4D Engine — t 스텝 루프 노드 (Phase 2.2).

한 t에서 성장→분열→사멸→융합→돌연변이 후 메모리·Emotion·Thought·Worldview 갱신.
ARCHITECTURE_CHECKLIST 5.2~5.3
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from typing import TYPE_CHECKING, Any

from app.core.action_ledger import attach_action_record
from app.core.collective_dynamics import apply_collective_dynamics, compute_group_state
from app.core.consultation_kernel import stamp_precision_internal_metrics
from app.core.deep_commit_runtime import run_deep_commit
from app.core.memory_step import append_step_memory
from app.core.miro_swarm_runtime import run_miro_swarm_step
from app.core.policy_events import apply_active_policies
from app.core.runtime_timing import RuntimeTimer
from app.core.scene_events import build_intra_t_scene_events, compute_scene_quality_metrics
from app.core.social_elevation import refresh_social_elevation
from app.core.settings import get_snapshot_interval
from app.core.stream_episode_runtime import emit_stream_phase, merge_stream_episode_events, run_stream_episode
from app.core.rules import (
    apply_growth,
    apply_division,
    apply_death,
    apply_fusion,
    apply_mutation,
)
from app.llm.facade import llm_facade
from app.llm.thought import update_thoughts_if_due
from app.llm.worldview import update_worldviews_if_due

if TYPE_CHECKING:
    from app.graph.time_flow import SimulationState


@contextmanager
def _temporary_swarm_llm_env(engine_params: dict | None, *, cell_count: int | None = None):
    params = dict(engine_params or {})
    simulation_mode = str(params.get("simulation_mode") or "precision").strip().lower()
    agent_feel = str(params.get("stream_llm_agent_feel", "")).strip().lower() not in {"", "0", "false", "off", "no"}
    if simulation_mode != "swarm" and not agent_feel:
        yield
        return

    meso = dict((params.get("swarm_tier_model") or {}).get("meso") or {})
    mode = str(params.get("swarm_llm_mode") or meso.get("llm_mode") or "packet").strip().lower()
    group_count = max(1, int(meso.get("group_count") or params.get("zone_count") or 24))
    requested_sample = _positive_int(params.get("llm_agent_sample_size"))
    stream_max_agents = _positive_int(params.get("stream_max_active_agents"))
    sample_ceiling = max(48, requested_sample or stream_max_agents or group_count * 6)
    if cell_count is not None and cell_count > 0:
        sample_ceiling = min(int(cell_count), sample_ceiling)
    agent_sample = max(1, sample_ceiling)
    if mode == "agent":
        overrides = {
            "ORGANIC4D_ACTION_INTERVAL": "1",
            "ORGANIC4D_LLM_AGENT_SAMPLE_SIZE": str(agent_sample),
            "ORGANIC4D_DIALOGUE_INTERVAL": "1",
            "ORGANIC4D_DIALOGUE_MAX_PAIRS": str(max(16, group_count)),
            "ORGANIC4D_GROUP_DELIBERATION_INTERVAL": "1",
            "ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS": str(min(256, group_count)),
            "ORGANIC4D_LLM_BUDGET_ACTION": str(max(48, group_count * 3)),
            "ORGANIC4D_LLM_BUDGET_DIALOGUE": str(max(16, group_count)),
            "ORGANIC4D_LLM_BUDGET_GROUP_DELIBERATION": str(min(256, group_count)),
            "ORGANIC4D_LLM_PRIORITY_ACTION": "0",
            "ORGANIC4D_LLM_PRIORITY_DIALOGUE": "1",
            "ORGANIC4D_LLM_PRIORITY_GROUP_DELIBERATION": "2",
        }
    else:
        packet_sample = max(48, group_count * 2)
        overrides = {
            "ORGANIC4D_ACTION_INTERVAL": "1",
            "ORGANIC4D_LLM_AGENT_SAMPLE_SIZE": str(packet_sample),
            "ORGANIC4D_DIALOGUE_INTERVAL": "1",
            "ORGANIC4D_DIALOGUE_MAX_PAIRS": str(max(8, group_count // 2)),
            "ORGANIC4D_GROUP_DELIBERATION_INTERVAL": "1",
            "ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS": str(min(256, group_count)),
            "ORGANIC4D_LLM_BUDGET_ACTION": str(max(24, group_count * 2)),
            "ORGANIC4D_LLM_BUDGET_DIALOGUE": str(max(8, group_count // 2)),
            "ORGANIC4D_LLM_BUDGET_GROUP_DELIBERATION": str(min(512, max(16, group_count))),
            "ORGANIC4D_LLM_PRIORITY_ACTION": "3",
            "ORGANIC4D_LLM_PRIORITY_DIALOGUE": "2",
            "ORGANIC4D_LLM_PRIORITY_GROUP_DELIBERATION": "0",
        }
    previous = {key: os.environ.get(key) for key in overrides}
    try:
        os.environ.update(overrides)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def step_loop_node(state: "SimulationState") -> dict:
    """한 t 스텝: 5대 규칙 순차 적용 후 t 증가."""
    if str((state.get("engine_params") or {}).get("simulation_mode") or "precision").strip().lower() == "swarm":
        return run_miro_swarm_step(state)
    with _temporary_swarm_llm_env(state.get("engine_params"), cell_count=len(state.get("cells") or [])):
        return _step_loop_node(state)


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _step_loop_node(state: "SimulationState") -> dict:
    runtime_timer = RuntimeTimer()
    cells = state["cells"]
    current_t = state["current_t"]
    nutrient_per_step = state.get("nutrient_per_step", 1.0)
    world_events = state.get("world_events") or []
    next_t = current_t + 1
    scene_event_sink = state.get("scene_event_sink") if callable(state.get("scene_event_sink")) else None
    with runtime_timer.phase("llm_cycle_begin"):
        llm_facade.begin_cycle(
            f"world-step:{int(next_t)}",
            context={
                "current_t": float(current_t),
                "next_t": float(next_t),
                "cell_count": len(cells),
                "simulation_mode": str((state.get("engine_params") or {}).get("simulation_mode") or "precision"),
                "swarm_llm_mode": str((state.get("engine_params") or {}).get("swarm_llm_mode") or ""),
            },
        )
    emit_stream_phase(
        cells,
        current_t=current_t,
        next_t=next_t,
        progress=0.025,
        phase="stream_bootstrap",
        round_count=1,
        scene_event_sink=scene_event_sink,
    )

    with runtime_timer.phase("rules_and_memory"):
        cells = apply_active_policies(cells, current_t=current_t, events=world_events)
        cells = apply_growth(cells, nutrient_per_step=nutrient_per_step)
        cells = apply_division(cells, current_t=current_t)
        cells = apply_death(cells)
        cells = apply_fusion(cells, current_t=current_t)
        cells = apply_mutation(cells)
        cells = append_step_memory(cells, next_t)

    with runtime_timer.phase("stream_episode"):
        stream_episode = run_stream_episode(
            cells,
            current_t=current_t,
            next_t=next_t,
            engine_params=state.get("engine_params"),
            previous_group_state=state.get("group_state"),
            scene_event_sink=scene_event_sink,
        )
        cells = stream_episode.cells
        internal_group_state = stream_episode.group_state
        internal_interactions = stream_episode.round_count
        live_scene_events = stream_episode.live_scene_events
    with runtime_timer.phase("thought_worldview"):
        cells = update_thoughts_if_due(cells, next_t)
        cells = update_worldviews_if_due(cells, next_t)
    with runtime_timer.phase("collective_pre_action"):
        cells, pre_action_group_state = apply_collective_dynamics(
            cells,
            current_t=next_t,
            previous_group_state=internal_group_state or state.get("group_state"),
        )
    emit_stream_phase(
        cells,
        current_t=current_t,
        next_t=next_t,
        progress=0.72,
        phase="deep_commit",
        round_count=internal_interactions,
        scene_event_sink=scene_event_sink,
    )
    with runtime_timer.phase("deep_commit"):
        cells, coalition_state, coalition_history = run_deep_commit(
            cells,
            next_t=next_t,
            coalition_state=state.get("coalition_state"),
            coalition_history=state.get("coalition_history"),
        )
    with runtime_timer.phase("field_commit"):
        cells = refresh_social_elevation(
            cells,
            current_t=next_t,
            engine_params=state.get("engine_params"),
        )
        group_state = compute_group_state(
            cells,
            current_t=next_t,
            previous_group_state=state.get("group_state") or pre_action_group_state,
        )
        cells = [stamp_precision_internal_metrics(c, next_t, internal_interactions) for c in cells]
    with runtime_timer.phase("scene_select"):
        final_scene_events = build_intra_t_scene_events(
            cells,
            current_t=current_t,
            next_t=next_t,
            internal_interactions=internal_interactions,
            group_state=group_state,
            limit=6,
        )
        scene_events = merge_stream_episode_events(live_scene_events, final_scene_events, round_count=internal_interactions)
        scene_events = [attach_action_record(event) for event in scene_events]
    with runtime_timer.phase("scene_accumulate_quality"):
        cells = _apply_scene_accumulation(cells, scene_events, next_t=next_t)
        scene_metrics = compute_scene_quality_metrics(
            scene_events,
            cells,
            current_t=current_t,
            next_t=next_t,
        )

    store = state.get("snapshot_store")
    snapshot_interval = get_snapshot_interval()
    should_save_snapshot = int(next_t) == int(float(state.get("t_max", next_t))) or int(next_t) % snapshot_interval == 0
    if store is not None and should_save_snapshot:
        store.save(next_t, cells, scene_events=scene_events, scene_metrics=scene_metrics)

    out: dict = {
        "cells": cells,
        "current_t": next_t,
    }
    if "t_max" in state:
        out["t_max"] = state["t_max"]
    if "snapshot_store" in state:
        out["snapshot_store"] = state["snapshot_store"]
    if "world_events" in state:
        out["world_events"] = list(state["world_events"])
    if "engine_params" in state:
        out["engine_params"] = dict(state["engine_params"])
    out["coalition_state"] = dict(coalition_state)
    out["coalition_history"] = [dict(item) for item in coalition_history]
    out["group_state"] = dict(group_state)
    out["scene_events"] = [dict(item) for item in scene_events]
    out["scene_metrics"] = dict(scene_metrics)
    out["scene_events_live_emitted"] = bool(live_scene_events)
    out["runtime_timing"] = runtime_timer.snapshot()
    return out


def _apply_scene_accumulation(cells: list, scene_events: list[dict[str, Any]], *, next_t: float) -> list:
    if not cells or not scene_events:
        return cells
    deltas: dict[str, dict[str, float]] = {}
    counts: dict[str, int] = {}
    for event in scene_events:
        involved = [str(event.get("source_id") or "")]
        involved.extend(str(item) for item in event.get("target_ids") or [])
        pressure_delta = float(event.get("pressure_delta") or 0.0)
        relationship_delta = float(event.get("relationship_delta") or 0.0)
        for cell_id in {item for item in involved if item}:
            bucket = deltas.setdefault(cell_id, {"pressure": 0.0, "relationship": 0.0})
            bucket["pressure"] += pressure_delta
            bucket["relationship"] += relationship_delta
            counts[cell_id] = counts.get(cell_id, 0) + 1

    out = []
    for cell in cells:
        delta = deltas.get(cell.cell_id)
        if not delta:
            out.append(cell)
            continue
        action_state = dict(cell.action_state)
        previous_pressure = float(action_state.get("collective_pressure", 0.0) or 0.0)
        scene_pressure = float(delta["pressure"])
        scene_relationship = float(delta["relationship"])
        action_state["scene_pressure_delta"] = round(scene_pressure, 4)
        action_state["scene_relationship_delta"] = round(scene_relationship, 4)
        action_state["scene_participation_count"] = int(counts.get(cell.cell_id, 0))
        action_state["last_scene_t"] = float(next_t)
        action_state["collective_pressure"] = max(0.0, min(1.0, previous_pressure + scene_pressure * 0.12))
        out.append(cell.copy(action_state=action_state))
    return out
