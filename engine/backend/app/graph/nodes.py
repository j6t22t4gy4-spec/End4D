"""Organic4D Engine — t 스텝 루프 노드 (Phase 2.2).

한 t에서 성장→분열→사멸→융합→돌연변이 순서로 규칙 적용.
ARCHITECTURE_CHECKLIST 5.2: 매 t: 성장/분열/사멸/융합/돌연변이 + Emotion
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from app.core.rules import (
    apply_growth,
    apply_division,
    apply_death,
    apply_fusion,
    apply_mutation,
)

if TYPE_CHECKING:
    from app.graph.time_flow import SimulationState


def step_loop_node(state: "SimulationState") -> dict:
    """한 t 스텝: 5대 규칙 순차 적용 후 t 증가."""
    cells = state["cells"]
    current_t = state["current_t"]
    nutrient_per_step = state.get("nutrient_per_step", 1.0)

    cells = apply_growth(cells, nutrient_per_step=nutrient_per_step)
    cells = apply_division(cells, current_t=current_t)
    cells = apply_death(cells)
    cells = apply_fusion(cells, current_t=current_t)
    cells = apply_mutation(cells)

    next_t = current_t + 1
    cells = [c.copy(t=next_t) for c in cells]

    store = state.get("snapshot_store")
    if store is not None:
        store.save(next_t, cells)

    out: dict = {
        "cells": cells,
        "current_t": next_t,
    }
    if "t_max" in state:
        out["t_max"] = state["t_max"]
    if "snapshot_store" in state:
        out["snapshot_store"] = state["snapshot_store"]
    return out
