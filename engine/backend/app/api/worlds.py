"""Organic4D Engine — REST 엔드포인트: worlds (Phase 3.2, 3.3).

POST /worlds — 세계 생성
GET /worlds/{id} — 월드 메타정보 조회
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.store import world_store
from pydantic import BaseModel


router = APIRouter(prefix="/worlds", tags=["worlds"])


class CreateWorldRequest(BaseModel):
    """POST /worlds 요청."""
    initial_cell_count: int = 5
    t_max: float = 100.0


class CreateWorldResponse(BaseModel):
    """POST /worlds 응답."""
    world_id: str


class WorldResponse(BaseModel):
    """GET /worlds/{id} 응답."""
    world_id: str
    t_max: float
    status: str


@router.post("", response_model=CreateWorldResponse)
def create_world(req: CreateWorldRequest):
    """월드 생성."""
    world_id = world_store.create(
        t_max=req.t_max,
        initial_cell_count=req.initial_cell_count,
    )
    return CreateWorldResponse(world_id=world_id)


@router.get("/{world_id}", response_model=WorldResponse)
def get_world(world_id: str):
    """월드 메타정보 조회."""
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    world = entry["world"]
    return WorldResponse(
        world_id=world.world_id,
        t_max=world.t_max,
        status=entry["status"],
    )
