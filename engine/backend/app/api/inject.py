"""God View 주입 API (Phase 7.1, 7.3).

POST /worlds/{id}/inject — { t, event_type, payload }
t 시점 스냅샷을 수정한 뒤 t 초과 스냅샷을 지우고 t→t_max 재실행.
"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.inject_handlers import apply_inject_to_cells
from app.core.store import world_store
from app.graph.time_flow import create_resume_time_flow_graph
from app.models.world import NutrientEvent, World

router = APIRouter(prefix="/worlds", tags=["inject"])

T_MATCH_EPS = 1e-5


def _snapshot_at_t(store, t: float):
    snap = store.get(t)
    if snap is not None:
        return snap
    for k in store.list_t():
        if abs(float(k) - float(t)) < T_MATCH_EPS:
            return store.get(k)
    return None


class InjectRequest(BaseModel):
    t: float = Field(..., description="주입 적용 시점 (저장된 스냅샷 t와 일치)")
    event_type: str = Field(..., description="nutrient_burst | append_memory | emotion_spike | noop")
    payload: Dict[str, Any] = Field(default_factory=dict)


class InjectResponse(BaseModel):
    world_id: str
    t_inject: float
    event_type: str
    status: str
    final_t: float = 0.0
    cell_count: int = 0
    snapshots_cleared: int = 0
    forwarded: bool = False


def _append_nutrient_event(world: World, t: float, event_type: str, payload: Dict) -> None:
    world.nutrients.append(
        NutrientEvent(t=float(t), event_type=event_type, payload=dict(payload))
    )


@router.post("/{world_id}/inject", response_model=InjectResponse)
def inject_event(world_id: str, body: InjectRequest):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    if entry["status"] == "running":
        raise HTTPException(status_code=409, detail="Simulation already running")

    world: World = entry["world"]
    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")

    snap = _snapshot_at_t(store, body.t)
    if snap is None:
        raise HTTPException(
            status_code=404,
            detail=f"No snapshot at t={body.t}. Run simulation first or pick an available t.",
        )

    t_inject = float(snap.t)
    cells_in = [c.copy() for c in snap.cells]
    cells_after = apply_inject_to_cells(cells_in, body.event_type, body.payload)

    cleared = store.clear_after(t_inject)
    store.save(t_inject, cells_after)
    _append_nutrient_event(world, t_inject, body.event_type, body.payload)

    t_max = float(world.t_max)
    if t_inject >= t_max:
        world_store.set_status(world_id, "done")
        return InjectResponse(
            world_id=world_id,
            t_inject=t_inject,
            event_type=body.event_type,
            status="done",
            final_t=t_inject,
            cell_count=len(cells_after),
            snapshots_cleared=cleared,
            forwarded=False,
        )

    world_store.set_status(world_id, "running")
    try:
        graph = create_resume_time_flow_graph()
        result = graph.invoke(
            {
                "cells": cells_after,
                "current_t": t_inject,
                "t_max": t_max,
                "snapshot_store": store,
                "nutrient_per_step": 1.0,
            },
            config={"recursion_limit": int(max(t_max - t_inject, 0)) + 80},
        )
        final_t = float(result["current_t"])
        cell_count = len(result["cells"])
    finally:
        world_store.set_status(world_id, "done")

    return InjectResponse(
        world_id=world_id,
        t_inject=t_inject,
        event_type=body.event_type,
        status="done",
        final_t=final_t,
        cell_count=cell_count,
        snapshots_cleared=cleared,
        forwarded=True,
    )
