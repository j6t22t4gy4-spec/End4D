"""Organic4D Engine — REST 엔드포인트: worlds (Phase 3.2, 3.3).

POST /worlds — 프롬프트 기반 세계 생성 (CONCEPT §5.2)
GET /worlds/{id} — 월드 메타정보 조회
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, conint

from app.core.persona_dataset import (
    load_persona_seeds,
    persona_source_info,
    persona_source_info_from_label,
    persona_source_label,
    personas_to_dicts,
)
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
    session_id: Optional[str] = Field(
        default=None,
        description="결과를 연결할 실행 세션 ID. 미지정 시 자동 생성",
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
    persona_country: str
    persona_source: str
    persona_count: int
    config_version: str
    session_id: str


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
    persona_country: str = ""
    persona_source: str = ""
    persona_count: int = 0
    config_version: str = ""
    simulation_config: Dict[str, Any] = Field(default_factory=dict)
    comparison_meta: Dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""


class PersonaPreviewItem(BaseModel):
    persona_id: str
    persona_text: str
    role_key: str = "agent"
    role_label: str = "agent"
    country: str = ""
    attrs: Dict[str, Any] = Field(default_factory=dict)


class PersonaSourceResponse(BaseModel):
    country: str
    source: str
    dataset_id: str = ""
    path: str = ""
    license: str = ""
    url: str = ""
    attribution_required: bool = False
    citation: str = ""
    configured: bool = False


class PersonaPreviewResponse(BaseModel):
    world_id: str
    persona_count: int
    source: PersonaSourceResponse
    items: List[PersonaPreviewItem]


@router.post("", response_model=CreateWorldResponse)
def create_world(req: CreateWorldRequest):
    """프롬프트 → 세계 제안 → 저장. (후속: 외부 LLM API로 propose_world_from_prompt 대체)"""
    plan = propose_world_from_prompt(req.prompt)
    personas = load_persona_seeds(
        country=plan.persona_country,
        count=plan.initial_cell_count,
        seed_text=req.prompt,
    )
    persona_catalog = personas_to_dicts(personas)
    role_catalog = plan.role_catalog
    if personas:
        persona_roles = []
        for p in personas:
            if p.role_label and p.role_label not in persona_roles:
                persona_roles.append(p.role_label)
        role_catalog = persona_roles[:8] or role_catalog
    persona_source = persona_source_label(plan.persona_country) if persona_catalog else f"not_configured:{plan.persona_country}"

    world_id = world_store.create(
        t_max=plan.t_max,
        initial_cell_count=plan.initial_cell_count,
        genesis_prompt=req.prompt,
        genesis_rationale=plan.rationale,
        role_catalog=role_catalog,
        t_step_semantic=plan.t_step_semantic,
        t_step_unit=plan.t_step_unit,
        nutrient_per_step=plan.nutrient_per_step,
        persona_country=plan.persona_country,
        persona_source=persona_source,
        persona_catalog=persona_catalog,
        session_id=req.session_id,
    )
    entry = world_store.get(world_id)
    return CreateWorldResponse(
        world_id=world_id,
        t_max=plan.t_max,
        initial_cell_count=plan.initial_cell_count,
        rationale=plan.rationale,
        role_catalog=role_catalog,
        t_step_semantic=plan.t_step_semantic,
        t_step_unit=plan.t_step_unit,
        nutrient_per_step=plan.nutrient_per_step,
        persona_country=plan.persona_country,
        persona_source=persona_source,
        persona_count=len(persona_catalog),
        config_version=str((entry or {}).get("config_version") or ""),
        session_id=str((entry or {}).get("session_id") or ""),
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
        persona_country=str(entry.get("persona_country") or ""),
        persona_source=str(entry.get("persona_source") or ""),
        persona_count=len(entry.get("persona_catalog") or []),
        config_version=str(entry.get("config_version") or ""),
        simulation_config=dict(entry.get("simulation_config") or {}),
        comparison_meta=dict(entry.get("comparison_meta") or {}),
        session_id=str(entry.get("session_id") or ""),
    )


@router.get("/{world_id}/personas", response_model=PersonaPreviewResponse)
def get_world_personas(
    world_id: str,
    limit: conint(ge=1, le=100) = 20,
):
    """Preview the persona seeds attached to a world."""
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")

    catalog = list(entry.get("persona_catalog") or [])
    country = str(entry.get("persona_country") or "")
    source = str(entry.get("persona_source") or "")
    items = [PersonaPreviewItem(**p) for p in catalog[: int(limit)]]
    return PersonaPreviewResponse(
        world_id=world_id,
        persona_count=len(catalog),
        source=PersonaSourceResponse(
            **persona_source_info_from_label(country, source, configured=bool(catalog))
        ),
        items=items,
    )
