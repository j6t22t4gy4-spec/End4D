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


class TimelineSummaryResponse(BaseModel):
    world_id: str
    points_count: int
    first_t: float
    last_t: float
    initial_cell_count: int
    final_cell_count: int
    min_cell_count: int
    max_cell_count: int
    initial_total_energy: float
    final_total_energy: float
    peak_total_energy: float
    cell_delta: int
    energy_delta: float
    outcome: str


def _timeline_points(store) -> List[TimelinePoint]:
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
    return points


def _classify_outcome(points: List[TimelinePoint]) -> str:
    if not points:
        return "not_started"
    first = points[0]
    last = points[-1]
    if last.cell_count == 0:
        return "extinct"
    if last.cell_count >= max(first.cell_count * 1.5, first.cell_count + 3):
        return "expanding"
    if last.cell_count <= first.cell_count * 0.6:
        return "contracting"
    if last.total_energy > first.total_energy * 1.25:
        return "energy_accumulating"
    if last.total_energy < first.total_energy * 0.75:
        return "energy_depleted"
    return "stable"


@router.get("/{world_id}/timeline", response_model=TimelineResponse)
def get_timeline(world_id: str):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")

    return TimelineResponse(world_id=world_id, points=_timeline_points(store))


@router.get("/{world_id}/timeline/summary", response_model=TimelineSummaryResponse)
def get_timeline_summary(world_id: str):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")

    points = _timeline_points(store)
    if not points:
        raise HTTPException(status_code=404, detail="No timeline points available")

    first = points[0]
    last = points[-1]
    cell_counts = [p.cell_count for p in points]
    energies = [p.total_energy for p in points]
    return TimelineSummaryResponse(
        world_id=world_id,
        points_count=len(points),
        first_t=first.t,
        last_t=last.t,
        initial_cell_count=first.cell_count,
        final_cell_count=last.cell_count,
        min_cell_count=min(cell_counts),
        max_cell_count=max(cell_counts),
        initial_total_energy=first.total_energy,
        final_total_energy=last.total_energy,
        peak_total_energy=max(energies),
        cell_delta=last.cell_count - first.cell_count,
        energy_delta=last.total_energy - first.total_energy,
        outcome=_classify_outcome(points),
    )
