"""Snapshot export and restore API for what-if workflows."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.serialization import cell_to_dict
from app.core.store import world_store
from app.graph.time_flow import create_resume_time_flow_graph

router = APIRouter(prefix="/worlds", tags=["state"])

T_MATCH_EPS = 1e-5


def _snapshot_at_t(store, t: float):
    snap = store.get(t)
    if snap is not None:
        return snap
    for k in store.list_t():
        if abs(float(k) - float(t)) < T_MATCH_EPS:
            return store.get(k)
    return None


class StateSnapshotResponse(BaseModel):
    world_id: str
    t: float
    t_max: float
    status: str
    role_catalog: List[str] = Field(default_factory=list)
    persona_country: str = ""
    persona_source: str = ""
    cell_count: int
    cells: List[Dict[str, Any]]


class RestoreRequest(BaseModel):
    t: float = Field(..., description="복원할 스냅샷 시점")
    target: Literal["current", "fork"] = "current"
    resume: bool = True


class RestoreResponse(BaseModel):
    source_world_id: str
    world_id: str
    restored_t: float
    resumed: bool
    final_t: float
    cell_count: int
    snapshots_cleared: int = 0


@router.get("/{world_id}/state", response_model=StateSnapshotResponse)
def export_state(
    world_id: str,
    t: Optional[float] = Query(None, description="미지정 시 최신 스냅샷"),
):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")

    if t is None:
        available_t = store.list_t()
        if not available_t:
            raise HTTPException(status_code=404, detail="No snapshot available")
        snap = store.get(available_t[-1])
    else:
        snap = _snapshot_at_t(store, t)
    if snap is None:
        raise HTTPException(status_code=404, detail="No snapshot available")

    return StateSnapshotResponse(
        world_id=world_id,
        t=float(snap.t),
        t_max=float(entry["world"].t_max),
        status=str(entry["status"]),
        role_catalog=list(entry.get("role_catalog") or []),
        persona_country=str(entry.get("persona_country") or ""),
        persona_source=str(entry.get("persona_source") or ""),
        cell_count=len(snap.cells),
        cells=[cell_to_dict(cell) for cell in snap.cells],
    )


@router.post("/{world_id}/restore", response_model=RestoreResponse)
def restore_state(world_id: str, body: RestoreRequest):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    if entry["status"] == "running":
        raise HTTPException(status_code=409, detail="Simulation already running")

    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")

    snap = _snapshot_at_t(store, body.t)
    if snap is None:
        raise HTTPException(status_code=404, detail="No snapshot available")
    restored_t = float(snap.t)
    restored_cells = [cell.copy() for cell in snap.cells]

    if body.target == "fork":
        new_world_id = world_store.clone_from_snapshot(world_id, snapshot_t=restored_t)
        if new_world_id is None:
            raise HTTPException(status_code=500, detail="Fork failed")
        fork_entry = world_store.get(new_world_id)
        assert fork_entry is not None
        target_store = fork_entry["snapshot_store"]
        target_world = fork_entry["world"]
        if body.resume and restored_t < float(target_world.t_max):
            world_store.set_status(new_world_id, "running")
            try:
                result = create_resume_time_flow_graph().invoke(
                    {
                        "cells": restored_cells,
                        "current_t": restored_t,
                        "t_max": float(target_world.t_max),
                        "snapshot_store": target_store,
                        "nutrient_per_step": world_store.get_nutrient_per_step(new_world_id),
                    },
                    config={"recursion_limit": int(max(target_world.t_max - restored_t, 0)) + 80},
                )
                final_t = float(result["current_t"])
                cell_count = len(result["cells"])
            finally:
                world_store.set_status(new_world_id, "done")
        else:
            final_t = restored_t
            cell_count = len(restored_cells)
        return RestoreResponse(
            source_world_id=world_id,
            world_id=new_world_id,
            restored_t=restored_t,
            resumed=body.resume,
            final_t=final_t,
            cell_count=cell_count,
            snapshots_cleared=0,
        )

    cleared = store.clear_after(restored_t)
    store.save(restored_t, restored_cells)
    final_t = restored_t
    cell_count = len(restored_cells)
    if body.resume and restored_t < float(entry["world"].t_max):
        world_store.set_status(world_id, "running")
        try:
            result = create_resume_time_flow_graph().invoke(
                {
                    "cells": restored_cells,
                    "current_t": restored_t,
                    "t_max": float(entry["world"].t_max),
                    "snapshot_store": store,
                    "nutrient_per_step": world_store.get_nutrient_per_step(world_id),
                },
                config={"recursion_limit": int(max(entry["world"].t_max - restored_t, 0)) + 80},
            )
            final_t = float(result["current_t"])
            cell_count = len(result["cells"])
        finally:
            world_store.set_status(world_id, "done")

    return RestoreResponse(
        source_world_id=world_id,
        world_id=world_id,
        restored_t=restored_t,
        resumed=body.resume,
        final_t=final_t,
        cell_count=cell_count,
        snapshots_cleared=cleared,
    )
