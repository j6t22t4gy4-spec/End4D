"""Organic4D Engine — t 스텝 루프 노드 (Phase 2.2).

한 t에서 성장→분열→사멸→융합→돌연변이 후 메모리·Emotion·Thought·Worldview 갱신.
ARCHITECTURE_CHECKLIST 5.2~5.3
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from typing import TYPE_CHECKING, Any, Callable, Optional

from app.core.agent_interactions import apply_agent_interactions
from app.core.collective_dynamics import apply_collective_dynamics, compute_group_state
from app.core.emotion import update_emotions
from app.core.memory_step import append_step_memory
from app.core.policy_events import apply_active_policies
from app.core.scene_events import build_intra_t_scene_events, compute_scene_quality_metrics
from app.core.social_elevation import refresh_social_elevation
from app.core.spatial_dynamics import update_spatial_positions
from app.core.settings import get_snapshot_interval
from app.core.rules import (
    apply_growth,
    apply_division,
    apply_death,
    apply_fusion,
    apply_mutation,
)
from app.llm.actions import update_action_states_if_due
from app.llm.dialogue import apply_agent_dialogues_if_due
from app.llm.group_deliberation import apply_group_deliberation_if_due
from app.llm.facade import llm_facade
from app.llm.thought import update_thoughts_if_due
from app.llm.worldview import update_worldviews_if_due

if TYPE_CHECKING:
    from app.graph.time_flow import SimulationState


@contextmanager
def _temporary_swarm_llm_env(engine_params: dict | None):
    params = dict(engine_params or {})
    if str(params.get("simulation_mode") or "precision").strip().lower() != "swarm":
        yield
        return

    meso = dict((params.get("swarm_tier_model") or {}).get("meso") or {})
    mode = str(params.get("swarm_llm_mode") or meso.get("llm_mode") or "packet").strip().lower()
    group_count = max(1, int(meso.get("group_count") or params.get("zone_count") or 24))
    if mode == "agent":
        overrides = {
            "ORGANIC4D_ACTION_INTERVAL": "2",
            "ORGANIC4D_LLM_AGENT_SAMPLE_SIZE": str(max(512, group_count * 64)),
            "ORGANIC4D_DIALOGUE_INTERVAL": "12",
            "ORGANIC4D_DIALOGUE_MAX_PAIRS": str(max(48, group_count * 3)),
            "ORGANIC4D_GROUP_DELIBERATION_INTERVAL": "24",
            "ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS": str(min(256, group_count)),
            "ORGANIC4D_LLM_BUDGET_ACTION": str(max(128, group_count * 24)),
            "ORGANIC4D_LLM_BUDGET_GROUP_DELIBERATION": str(min(256, group_count)),
            "ORGANIC4D_LLM_PRIORITY_ACTION": "0",
            "ORGANIC4D_LLM_PRIORITY_GROUP_DELIBERATION": "2",
        }
    else:
        overrides = {
            "ORGANIC4D_ACTION_INTERVAL": "16",
            "ORGANIC4D_LLM_AGENT_SAMPLE_SIZE": str(max(64, group_count * 4)),
            "ORGANIC4D_DIALOGUE_INTERVAL": "48",
            "ORGANIC4D_DIALOGUE_MAX_PAIRS": str(max(12, group_count)),
            "ORGANIC4D_GROUP_DELIBERATION_INTERVAL": "6",
            "ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS": str(min(256, group_count)),
            "ORGANIC4D_LLM_BUDGET_ACTION": str(max(24, group_count * 2)),
            "ORGANIC4D_LLM_BUDGET_GROUP_DELIBERATION": str(min(512, max(24, group_count * 2))),
            "ORGANIC4D_LLM_PRIORITY_ACTION": "3",
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
    with _temporary_swarm_llm_env(state.get("engine_params")):
        return _step_loop_node(state)


def _step_loop_node(state: "SimulationState") -> dict:
    cells = state["cells"]
    current_t = state["current_t"]
    nutrient_per_step = state.get("nutrient_per_step", 1.0)
    world_events = state.get("world_events") or []
    next_t = current_t + 1
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

    cells = apply_active_policies(cells, current_t=current_t, events=world_events)
    cells = apply_growth(cells, nutrient_per_step=nutrient_per_step)
    cells = apply_division(cells, current_t=current_t)
    cells = apply_death(cells)
    cells = apply_fusion(cells, current_t=current_t)
    cells = apply_mutation(cells)

    cells = append_step_memory(cells, next_t)
    cells, internal_group_state, internal_interactions, live_scene_events = _apply_precision_internal_interactions(
        cells,
        current_t=current_t,
        next_t=next_t,
        engine_params=state.get("engine_params"),
        previous_group_state=state.get("group_state"),
        scene_event_sink=state.get("scene_event_sink") if callable(state.get("scene_event_sink")) else None,
    )
    cells = update_thoughts_if_due(cells, next_t)
    cells = update_worldviews_if_due(cells, next_t)
    cells, pre_action_group_state = apply_collective_dynamics(
        cells,
        current_t=next_t,
        previous_group_state=internal_group_state or state.get("group_state"),
    )
    cells = update_action_states_if_due(cells, next_t)
    cells = apply_agent_dialogues_if_due(cells, next_t)
    cells, coalition_state, coalition_history = apply_group_deliberation_if_due(
        cells,
        next_t,
        coalition_state=state.get("coalition_state"),
        coalition_history=state.get("coalition_history"),
    )
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
    cells = [_stamp_precision_internal_metrics(c, next_t, internal_interactions) for c in cells]
    final_scene_events = build_intra_t_scene_events(
        cells,
        current_t=current_t,
        next_t=next_t,
        internal_interactions=internal_interactions,
        group_state=group_state,
        limit=4,
    )
    scene_events = _merge_scene_events(live_scene_events, final_scene_events, internal_interactions=internal_interactions)
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
    return out


def _apply_precision_internal_interactions(
    cells: list,
    *,
    current_t: float,
    next_t: float,
    engine_params: dict | None,
    previous_group_state: dict | None,
    scene_event_sink: Optional[Callable[[dict[str, Any]], None]] = None,
) -> tuple[list, dict, int, list[dict[str, Any]]]:
    params = dict(engine_params or {})
    interactions = _precision_internal_interaction_count(
        cells,
        engine_params=params,
        previous_group_state=previous_group_state,
    )
    group_state = dict(previous_group_state or {})
    scene_events: list[dict[str, Any]] = []
    emitted_keys: set[tuple[str, str, str]] = set()
    if interactions <= 1:
        cells = apply_agent_interactions(cells, next_t)
        cells = update_spatial_positions(cells, current_t=next_t, engine_params=params)
        cells = update_emotions(cells, next_t)
        cells, group_state = apply_collective_dynamics(
            cells,
            current_t=next_t,
            previous_group_state=group_state,
        )
        _collect_live_scene_events(
            cells,
            current_t=current_t,
            next_t=next_t,
            scene_t=next_t,
            interactions=1,
            group_state=group_state,
            scene_events=scene_events,
            emitted_keys=emitted_keys,
            scene_event_sink=scene_event_sink,
        )
        return cells, group_state, 1, scene_events

    for idx in range(interactions):
        progress = (idx + 1) / interactions
        internal_t = float(current_t) + (float(next_t) - float(current_t)) * progress
        cells = apply_agent_interactions(
            cells,
            internal_t,
            interval=1,
            radius=float(params.get("internal_interaction_radius", params.get("interaction_radius", 4.0))),
            max_neighbors=int(params.get("internal_max_neighbors", 3)),
            force=True,
        )
        cells = update_spatial_positions(cells, current_t=internal_t, engine_params=params)
        cells = update_emotions(cells, internal_t)
        cells, group_state = apply_collective_dynamics(
            cells,
            current_t=internal_t,
            previous_group_state=group_state,
        )
        _collect_live_scene_events(
            cells,
            current_t=current_t,
            next_t=next_t,
            scene_t=internal_t,
            interactions=interactions,
            group_state=group_state,
            scene_events=scene_events,
            emitted_keys=emitted_keys,
            scene_event_sink=scene_event_sink,
        )
    return cells, group_state, interactions, scene_events


def _collect_live_scene_events(
    cells: list,
    *,
    current_t: float,
    next_t: float,
    scene_t: float,
    interactions: int,
    group_state: dict,
    scene_events: list[dict[str, Any]],
    emitted_keys: set[tuple[str, str, str]],
    scene_event_sink: Optional[Callable[[dict[str, Any]], None]],
) -> None:
    batch = build_intra_t_scene_events(
        cells,
        current_t=current_t,
        next_t=next_t,
        internal_interactions=interactions,
        group_state=group_state,
        limit=3,
    )
    for event in batch:
        key = (
            str(event.get("source_id") or ""),
            ",".join(str(item) for item in event.get("target_ids") or []),
            str(event.get("interaction_type") or event.get("scene_type") or ""),
        )
        if key in emitted_keys:
            continue
        emitted_keys.add(key)
        event = dict(event)
        event["scene_t"] = float(scene_t)
        event["scene_progress"] = _scene_progress(current_t=current_t, next_t=next_t, scene_t=scene_t)
        event["scene_index"] = len(scene_events) + 1
        event["scene_count"] = max(1, min(12, interactions * 3))
        event["live_computed"] = True
        event["scene_id"] = f"live-scene-{_safe_t(next_t)}-{event['scene_index']}"
        scene_events.append(event)
        if scene_event_sink is not None:
            scene_event_sink(dict(event))
        if len(scene_events) >= 12:
            return


def _merge_scene_events(
    live_events: list[dict[str, Any]],
    final_events: list[dict[str, Any]],
    *,
    internal_interactions: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for event in [*live_events, *final_events]:
        key = (
            str(event.get("source_id") or ""),
            ",".join(str(item) for item in event.get("target_ids") or []),
            str(event.get("interaction_type") or event.get("scene_type") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(event))
        if len(merged) >= 12:
            break
    merged.sort(key=lambda item: float(item.get("scene_progress", 0.0) or 0.0))
    scene_count = len(merged)
    for idx, event in enumerate(merged, start=1):
        event["scene_index"] = idx
        event["scene_count"] = scene_count
        event["internal_interactions"] = int(max(1, internal_interactions))
    return merged


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


def _scene_progress(*, current_t: float, next_t: float, scene_t: float) -> float:
    span = max(1e-6, float(next_t) - float(current_t))
    return max(0.04, min(0.96, round((float(scene_t) - float(current_t)) / span, 4)))


def _safe_t(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "-")


def _precision_internal_interaction_count(
    cells: list,
    *,
    engine_params: dict,
    previous_group_state: dict | None,
) -> int:
    mode = str(engine_params.get("simulation_mode") or "precision").strip().lower()
    if mode == "swarm":
        return 1
    min_steps = max(1, int(engine_params.get("min_interactions_per_step", 2)))
    max_steps = max(min_steps, int(engine_params.get("max_interactions_per_step", 6)))
    sensitivity = max(0.1, float(engine_params.get("interaction_sensitivity", 1.0)))
    pressure = 0.0
    fracture = 0.0
    if previous_group_state:
        groups = list((previous_group_state.get("groups") or {}).values()) if isinstance(previous_group_state, dict) else []
        if groups:
            pressure = max(float(group.get("avg_collective_pressure", group.get("pressure", 0.0)) or 0.0) for group in groups)
            fracture = max(float(group.get("fracture_risk", 0.0) or 0.0) for group in groups)
    local_density = _avg_action_value(cells, "local_density", 0.0)
    policy = _avg_action_value(cells, "policy_sensitivity", 0.5)
    scenario_need = min(1.0, (pressure * 0.32 + fracture * 0.28 + local_density * 0.16 + policy * 0.12) * sensitivity)
    return max(min_steps, min(max_steps, min_steps + round((max_steps - min_steps) * scenario_need)))


def _avg_action_value(cells: list, key: str, fallback: float) -> float:
    if not cells:
        return 0.0
    values = []
    for cell in cells:
        try:
            values.append(float(dict(cell.action_state).get(key, fallback) or fallback))
        except (TypeError, ValueError):
            values.append(float(fallback))
    return sum(values) / max(1, len(values))


def _stamp_precision_internal_metrics(cell, next_t: float, interactions: int):
    action_state = dict(cell.action_state)
    action_state["internal_interactions"] = int(interactions)
    action_state["last_internal_interaction_t"] = float(next_t)
    return cell.copy(t=next_t, action_state=action_state)
