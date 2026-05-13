"""Organic4D Engine — t 스텝 루프 노드 (Phase 2.2).

한 t에서 성장→분열→사멸→융합→돌연변이 후 메모리·Emotion·Thought·Worldview 갱신.
ARCHITECTURE_CHECKLIST 5.2~5.3
"""
from __future__ import annotations

from contextlib import contextmanager
import os
from typing import TYPE_CHECKING, Optional

from app.core.agent_interactions import apply_agent_interactions
from app.core.collective_dynamics import apply_collective_dynamics, compute_group_state
from app.core.emotion import update_emotions
from app.core.memory_step import append_step_memory
from app.core.policy_events import apply_active_policies
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
    cells = apply_agent_interactions(cells, next_t)
    cells = update_spatial_positions(
        cells,
        current_t=next_t,
        engine_params=state.get("engine_params"),
    )
    cells = update_emotions(cells, next_t)
    cells = update_thoughts_if_due(cells, next_t)
    cells = update_worldviews_if_due(cells, next_t)
    cells, pre_action_group_state = apply_collective_dynamics(
        cells,
        current_t=next_t,
        previous_group_state=state.get("group_state"),
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
    cells = [c.copy(t=next_t) for c in cells]

    store = state.get("snapshot_store")
    snapshot_interval = get_snapshot_interval()
    should_save_snapshot = int(next_t) == int(float(state.get("t_max", next_t))) or int(next_t) % snapshot_interval == 0
    if store is not None and should_save_snapshot:
        store.save(next_t, cells)

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
    return out
