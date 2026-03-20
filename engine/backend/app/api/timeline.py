"""시나리오 타임라인 집계 (Phase 7.4).

GET /worlds/{id}/timeline — 각 저장 t별 세포 수·에너지 합 (Recharts 등용)
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.store import world_store

router = APIRouter(prefix="/worlds", tags=["timeline"])


class TimelinePoint(BaseModel):
    t: float
    cell_count: int
    total_energy: float


class TimelineResponse(BaseModel):
    world_id: str
    points: List[TimelinePoint]


@router.get("/{world_id}/timeline", response_model=TimelineResponse)
def get_timeline(world_id: str):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")

    points: List[TimelinePoint] = []
    for t in store.list_t():
        snap = store.get(t)
        if snap is None:
            continue
        cells = snap.cells
        te = sum(float(c.energy) for c in cells)
        points.append(
            TimelinePoint(t=float(t), cell_count=len(cells), total_energy=te)
        )

    return TimelineResponse(world_id=world_id, points=points)
