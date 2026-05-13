"""Organic4D Engine — t 스텝 루프 노드 (Phase 2.2).

한 t에서 성장→분열→사멸→융합→돌연변이 후 메모리·Emotion·Thought·Worldview 갱신.
ARCHITECTURE_CHECKLIST 5.2~5.3
"""
from __future__ import annotations

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


def step_loop_node(state: "SimulationState") -> dict:
    """한 t 스텝: 5대 규칙 순차 적용 후 t 증가."""
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
