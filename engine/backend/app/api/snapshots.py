"""Organic4D Engine — REST 엔드포인트: snapshots (Phase 3.2).

GET /worlds/{id}/snapshots?t= — t 시점 스냅샷 조회
IMPLEMENTATION §0: GET /worlds/{id}/snapshots?t=
"""
from __future__ import annotations

from typing import List, Optional, Union

from fastapi import APIRouter, HTTPException, Query

from app.core.store import world_store
from app.models.cell import Cell
from pydantic import BaseModel


router = APIRouter(prefix="/worlds", tags=["snapshots"])


def _cell_to_dict(c: Cell) -> dict:
    """Cell → JSON 직렬화 가능 dict."""
    return {
        "cell_id": c.cell_id,
        "x": float(c.x),
        "y": float(c.y),
        "z": float(c.z),
        "t": float(c.t),
        "energy": float(c.energy),
        "gene_vec": c.gene_vec.tolist(),
        "emotion_vec": c.emotion_vec.tolist(),
        "thought_vec": c.thought_vec.tolist(),
        "worldview_vec": c.worldview_vec.tolist(),
        "role_key": c.role_key,
        "role_label": c.role_label,
    }


class CellResponse(BaseModel):
    """스냅샷 내 세포 응답."""
    cell_id: str
    x: float
    y: float
    z: float
    t: float
    energy: float
    gene_vec: List[float]
    emotion_vec: List[float]
    thought_vec: List[float]
    worldview_vec: List[float]
    role_key: str = "agent"
    role_label: str = ""


class SnapshotResponse(BaseModel):
    """GET /worlds/{id}/snapshots 응답."""
    world_id: str
    t: float
    cells: List[CellResponse]


class SnapshotsListResponse(BaseModel):
    """t 목록 응답 (t 미지정 시)."""
    world_id: str
    available_t: List[float]


@router.get("/{world_id}/snapshots", response_model=Union[SnapshotResponse, SnapshotsListResponse])
def get_snapshots(
    world_id: str,
    t: Optional[float] = Query(None, description="시점 t (미지정 시 저장된 t 목록 반환)"),
):
    """t 시점 스냅샷 조회. t 미지정 시 저장된 t 목록 반환."""
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")

    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")

    if t is not None:
        snap = store.get(t) or store.get_nearest(t)
        if snap is None:
            raise HTTPException(status_code=404, detail="No snapshot available")
        cells = [CellResponse(**_cell_to_dict(c)) for c in snap.cells]
        return SnapshotResponse(world_id=world_id, t=snap.t, cells=cells)

    available_t = store.list_t()
    return SnapshotsListResponse(world_id=world_id, available_t=available_t)
