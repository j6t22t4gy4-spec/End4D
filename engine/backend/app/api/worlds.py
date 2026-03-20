"""Organic4D Engine — REST 엔드포인트: worlds (Phase 3.2, 3.3).

POST /worlds — 프롬프트 기반 세계 생성 (CONCEPT §5.2)
GET /worlds/{id} — 월드 메타정보 조회
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.store import world_store
from app.core.world_genesis import propose_world_from_prompt

router = APIRouter(prefix="/worlds", tags=["worlds"])


class CreateWorldRequest(BaseModel):
    """POST /worlds — 사용자는 질의(프롬프트)만 제출. 수치는 AI(또는 스텁)가 제안."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=16_000,
        description="예측·탐색하고 싶은 세계/시나리오를 자연어로 기술",
    )


class CreateWorldResponse(BaseModel):
    """POST /worlds 응답 — 제안된 파라미터를 투명하게 반환 (사용자가 고르지 않음)."""

    world_id: str
    t_max: float
    initial_cell_count: int
    rationale: str
    role_catalog: List[str]
    t_step_semantic: str
    t_step_unit: str
    nutrient_per_step: float


class WorldResponse(BaseModel):
    """GET /worlds/{id} 응답."""
    world_id: str
    t_max: float
    status: str
    genesis_prompt: Optional[str] = None
    genesis_rationale: Optional[str] = None
    role_catalog: List[str] = Field(default_factory=list)
    t_step_semantic: str = ""
    t_step_unit: str = "day"
    nutrient_per_step: float = 1.0


@router.post("", response_model=CreateWorldResponse)
def create_world(req: CreateWorldRequest):
    """프롬프트 → 세계 제안 → 저장. (후속: 외부 LLM API로 propose_world_from_prompt 대체)"""
    plan = propose_world_from_prompt(req.prompt)
    world_id = world_store.create(
        t_max=plan.t_max,
        initial_cell_count=plan.initial_cell_count,
        genesis_prompt=req.prompt,
        genesis_rationale=plan.rationale,
        role_catalog=plan.role_catalog,
        t_step_semantic=plan.t_step_semantic,
        t_step_unit=plan.t_step_unit,
        nutrient_per_step=plan.nutrient_per_step,
    )
    return CreateWorldResponse(
        world_id=world_id,
        t_max=plan.t_max,
        initial_cell_count=plan.initial_cell_count,
        rationale=plan.rationale,
        role_catalog=plan.role_catalog,
        t_step_semantic=plan.t_step_semantic,
        t_step_unit=plan.t_step_unit,
        nutrient_per_step=plan.nutrient_per_step,
    )


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
        genesis_prompt=entry.get("genesis_prompt"),
        genesis_rationale=entry.get("genesis_rationale"),
        role_catalog=list(entry.get("role_catalog") or []),
        t_step_semantic=world.t_step_semantic,
        t_step_unit=world.t_step_unit,
        nutrient_per_step=world.nutrient_per_step,
    )
