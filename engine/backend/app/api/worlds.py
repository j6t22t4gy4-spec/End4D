"""Organic4D Engine — REST 엔드포인트: worlds (Phase 3.2, 3.3).

POST /worlds — 프롬프트 기반 세계 생성 (CONCEPT §5.2)
GET /worlds/{id} — 월드 메타정보 조회
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, conint

from app.core.persona_dataset import (
    infer_role_catalog_from_personas,
    load_persona_seeds,
    persona_source_info,
    persona_source_info_from_label,
    persona_source_label,
    personas_to_dicts,
)
from app.core.store import world_store
from app.core.world_genesis import (
    apply_genesis_overrides,
    apply_persona_distribution_to_plan,
    propose_world_from_prompt,
)

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
    god_mode: Optional[Dict[str, Any]] = Field(
        default=None,
        description="고급 수동 제어. 미지정 시 자동 계획 사용",
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
    simulation_config: Dict[str, Any] = Field(default_factory=dict)
    persona_distribution_summary: Dict[str, Any] = Field(default_factory=dict)


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
    persona_distribution_summary: Dict[str, Any] = Field(default_factory=dict)
    config_version: str = ""
    simulation_config: Dict[str, Any] = Field(default_factory=dict)
    comparison_meta: Dict[str, Any] = Field(default_factory=dict)
    coalition_state: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    group_state: Dict[str, Any] = Field(default_factory=dict)
    cached_review_summary: Optional[Dict[str, Any]] = None
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


class DeleteWorldResponse(BaseModel):
    world_id: str
    deleted: bool


@router.post("", response_model=CreateWorldResponse)
def create_world(req: CreateWorldRequest):
    """프롬프트 → 세계 제안 → 저장. (후속: 외부 LLM API로 propose_world_from_prompt 대체)"""
    plan = propose_world_from_prompt(req.prompt)
    god_mode = dict(req.god_mode or {})
    god_enabled = bool(god_mode.get("enabled"))
    god_overrides = dict(god_mode.get("overrides") or {})
    engine_params = dict(god_mode.get("engine_params") or {})
    auto_roles_from_personas = bool(god_mode.get("auto_roles_from_personas", True))
    if god_enabled:
        plan = apply_genesis_overrides(plan, god_overrides)
    personas = load_persona_seeds(
        country=plan.persona_country,
        count=plan.initial_cell_count,
        seed_text=req.prompt,
    )
    plan, persona_bias = apply_persona_distribution_to_plan(plan, personas)
    persona_catalog = personas_to_dicts(personas)
    role_catalog = plan.role_catalog
    if personas and auto_roles_from_personas:
        role_catalog = infer_role_catalog_from_personas(personas, limit=8) or role_catalog
    if god_enabled and god_overrides.get("role_catalog"):
        role_catalog = [str(role).strip() for role in god_overrides.get("role_catalog") or [] if str(role).strip()] or role_catalog
    persona_source = persona_source_label(plan.persona_country) if persona_catalog else f"not_configured:{plan.persona_country}"
    persona_distribution_summary = dict(plan.persona_distribution_summary or {})
    inferred_engine_params = {
        "zone_count": int(persona_bias.get("zone_count", engine_params.get("zone_count", 1) or 1)),
        "zone_layout": str(persona_bias.get("zone_layout", engine_params.get("zone_layout", "grid"))),
        "regional_labels": list(persona_bias.get("regional_labels") or []),
        "persona_role_catalog": list(persona_bias.get("role_catalog") or []),
        "persona_distribution_summary": persona_distribution_summary,
    }
    simulation_config = {
        "schema_version": "simulation-config/v3",
        "t_max": float(plan.t_max),
        "initial_cell_count": int(plan.initial_cell_count),
        "role_catalog": list(role_catalog),
        "t_step_semantic": plan.t_step_semantic,
        "t_step_unit": plan.t_step_unit,
        "nutrient_per_step": float(plan.nutrient_per_step),
        "persona_country": plan.persona_country,
        "persona_source": persona_source,
        "persona_distribution_summary": persona_distribution_summary,
        "engine_params": {
            **inferred_engine_params,
            **engine_params,
            "control_mode": "god" if god_enabled else "auto",
            "auto_roles_from_personas": auto_roles_from_personas,
            "genesis_mode": "persona-aware" if persona_catalog else "heuristic",
            "z_mode": str(engine_params.get("z_mode", "hybrid")),
            "z_weight": float(engine_params.get("z_weight", 0.08)),
            "z_scale": float(engine_params.get("z_scale", 12.0)),
        },
        "comparison_meta": {},
    }

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
        engine_params=simulation_config["engine_params"],
        simulation_config=simulation_config,
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
        simulation_config=dict((entry or {}).get("simulation_config") or {}),
        persona_distribution_summary=persona_distribution_summary,
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
        persona_distribution_summary=dict((entry.get("simulation_config") or {}).get("persona_distribution_summary") or {}),
        config_version=str(entry.get("config_version") or ""),
        simulation_config=dict(entry.get("simulation_config") or {}),
        comparison_meta=dict(entry.get("comparison_meta") or {}),
        coalition_state={
            str(role): dict(payload)
            for role, payload in dict(entry.get("coalition_state") or {}).items()
        },
        group_state=dict(entry.get("group_state") or {}),
        cached_review_summary=dict((entry.get("review_cache") or {}).get("summary_response") or {}) or None,
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


@router.delete("/{world_id}", response_model=DeleteWorldResponse)
def delete_world(world_id: str):
    deleted = world_store.delete(world_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="World not found")
    return DeleteWorldResponse(world_id=world_id, deleted=True)
