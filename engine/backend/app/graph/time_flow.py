"""Organic4D Engine — LangGraph 시간 흐름 그래프 (Phase 2.1).

노드: init → step_loop → (성장→분열→사멸→융합→돌연변이)
ARCHITECTURE_CHECKLIST 5.1: 입력 → 4D세계 → 에이전트 풀 → 시간 흐름 엔진
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

from langgraph.graph import StateGraph, START, END

from app.core.collective_dynamics import apply_collective_dynamics
from app.models.cell import Cell
from app.core.memory_store import seed_memory_from_text
from app.core.social_elevation import refresh_social_elevation
from app.core.snapshot import SnapshotStore
from app.graph.nodes import step_loop_node


def _create_initial_cells(
    count: int = 5,
    t: float = 0.0,
    role_catalog: Optional[List[str]] = None,
    persona_catalog: Optional[List[dict]] = None,
    engine_params: Optional[Dict[str, Any]] = None,
) -> List[Cell]:
    """초기 세포 생성. 페르소나가 있으면 역할·메모리 seed로 사용."""
    import numpy as np
    import math

    params = dict(engine_params or {})
    roles = role_catalog if role_catalog else ["agent"]
    if not roles:
        roles = ["agent"]
    personas = persona_catalog or []
    simulation_mode = str(params.get("simulation_mode") or "precision").strip().lower()
    max_zones = 64 if simulation_mode == "swarm" else 12
    zone_count = max(1, min(max_zones, int(params.get("zone_count", max(1, min(4, count))))))
    zone_layout = str(params.get("zone_layout", "grid")).strip() or "grid"
    spacing = max(0.6, float(params.get("zone_spacing", 2.0)))
    zone_influence_step = max(0.0, float(params.get("zone_influence_step", 0.08)))
    zone_friction_step = max(0.0, float(params.get("zone_friction_step", 0.1)))
    regional_labels = [str(label).strip() for label in params.get("regional_labels") or [] if str(label).strip()]
    region_zone_map = {label: idx for idx, label in enumerate(regional_labels[:zone_count])}
    initial_bias = dict(params.get("persona_initial_bias") or {})

    cells = []
    grid_width = max(1, math.ceil(count ** 0.5))
    for i in range(count):
        persona = personas[i % len(personas)] if personas else {}
        rk = str(persona.get("role_key") or roles[i % len(roles)])
        label = str(persona.get("role_label") or rk)
        persona_text = str(persona.get("persona_text") or "")
        attrs = dict(persona.get("attrs") or {})
        region_label = str(
            attrs.get("district")
            or attrs.get("province")
            or attrs.get("region")
            or persona.get("zone_label")
            or ""
        ).strip()
        zone_index = region_zone_map.get(region_label, i % zone_count)
        zone_id = str(persona.get("zone_id") or f"zone-{zone_index}")
        zone_label = str(persona.get("zone_label") or region_label or f"Zone {zone_index}")
        zone_influence = float(persona.get("zone_influence", 1.0 + zone_influence_step * zone_index))
        zone_friction = float(persona.get("zone_friction", zone_friction_step * zone_index))
        row = i // grid_width
        col = i % grid_width
        if zone_layout == "bands":
            x = float(col * spacing)
            y = float(zone_index * spacing * 2.2 + (row // max(1, zone_count)) * spacing)
        elif zone_layout == "ring":
            theta = (2.0 * math.pi * i) / max(1, count)
            radius = spacing * (2.4 + zone_index * 0.55)
            x = float(math.cos(theta) * radius)
            y = float(math.sin(theta) * radius)
        elif zone_layout == "swarm":
            theta = (2.0 * math.pi * (i % max(8, zone_count * 3))) / max(8, zone_count * 3)
            ring = 1.0 + (i // max(1, zone_count)) ** 0.5 * 0.18
            radius = spacing * (1.8 + zone_index * 0.42) * ring
            x = float(math.cos(theta + zone_index * 0.37) * radius + (i % 7) * 0.035)
            y = float(math.sin(theta + zone_index * 0.37) * radius + (i % 11) * 0.025)
        else:
            x = float(col * spacing)
            y = float(row * spacing)
        age = _safe_age(attrs.get("age"))
        initial_energy = (
            50.0
            + float(initial_bias.get("energy_offset", 0.0) or 0.0)
            + _energy_bias_from_persona(label=label, attrs=attrs, age=age)
        )
        action_state = _seed_action_state_from_persona(
            label=label,
            attrs=attrs,
            zone_index=zone_index,
            initial_bias=initial_bias,
        )
        cell = Cell(
                x=x,
                y=y,
                z=0.0,
                t=t,
                energy=initial_energy,
                gene_vec=np.random.randn(32).astype(np.float32) * 0.1,
                emotion_vec=np.random.randn(8).astype(np.float32) * 0.1,
                thought_vec=np.random.randn(256).astype(np.float32) * 0.1,
                worldview_vec=np.random.randn(384).astype(np.float32) * 0.1,
                action_state=action_state,
                role_key=rk,
                role_label=label,
                persona_id=str(persona.get("persona_id") or ""),
                persona_text=persona_text,
                persona_country=str(persona.get("country") or ""),
                persona_attrs=attrs,
                zone_id=zone_id,
                zone_label=zone_label,
                zone_influence=zone_influence,
                zone_friction=zone_friction,
            )
        if persona_text:
            cell = seed_memory_from_text(cell, persona_text)
        cells.append(cell)
    return refresh_social_elevation(cells, current_t=t, engine_params=params)


def _safe_age(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _energy_bias_from_persona(*, label: str, attrs: Dict[str, Any], age: int | None) -> float:
    bias = 0.0
    role_text = label.lower()
    if any(token in role_text for token in ("규제", "정부", "분석", "기술", "기업", "시장")):
        bias += 4.0
    if any(token in role_text for token in ("시민", "소비", "자영업")):
        bias += 1.5
    if age is not None:
        if age < 30:
            bias -= 2.0
        elif age >= 55:
            bias += 2.0
    education = str(attrs.get("education_level", "") or "").lower()
    if education:
        if "doctor" in education or "phd" in education or "박사" in education:
            bias += 2.0
        elif "master" in education or "석사" in education:
            bias += 1.0
    return bias


def _seed_action_state_from_persona(
    *,
    label: str,
    attrs: Dict[str, Any],
    zone_index: int,
    initial_bias: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    global_bias = dict(initial_bias or {})
    role_text = label.lower()
    cooperation = 0.54 if any(token in role_text for token in ("시민", "가계", "관측")) else 0.48
    policy = 0.58 if any(token in role_text for token in ("규제", "정부", "공공")) else 0.44
    resource = 0.6 if any(token in role_text for token in ("기업", "시장", "투자", "자영업")) else 0.46
    mobility = 0.42 + min(0.18, zone_index * 0.03)
    interests = str(attrs.get("hobbies_and_interests", "") or "").lower()
    if interests and any(token in interests for token in ("community", "봉사", "volunteer")):
        cooperation += 0.08
    priors = _persona_priors(attrs)
    cooperation += priors["cooperation_delta"]
    policy += priors["policy_delta"]
    resource += priors["resource_delta"]
    mobility += priors["mobility_delta"]
    cooperation += float(global_bias.get("cooperation_delta", 0.0) or 0.0)
    policy += float(global_bias.get("policy_sensitivity_delta", 0.0) or 0.0)
    resource += float(global_bias.get("resource_delta", 0.0) or 0.0)
    mobility += float(global_bias.get("mobility_delta", 0.0) or 0.0)
    return {
        "cooperation_bias": round(max(0.0, min(1.0, cooperation)), 4),
        "policy_sensitivity": round(max(0.0, min(1.0, policy)), 4),
        "resource_bias": round(max(0.0, min(1.0, resource)), 4),
        "mobility_bias": round(max(0.0, min(1.0, mobility)), 4),
        "strategy_summary": "persona_seeded_initial_state",
        "persona_prior_summary": priors["summary"],
        "persona_prior_factors": priors["factors"],
        "persona_distribution_bias": {
            key: round(float(value), 4)
            for key, value in global_bias.items()
            if isinstance(value, (int, float))
        },
    }


def _persona_priors(attrs: Dict[str, Any]) -> Dict[str, Any]:
    occupation = _normalize_attr_text(attrs.get("occupation"))
    region = _normalize_attr_text(
        attrs.get("district") or attrs.get("province") or attrs.get("region")
    )
    education = _normalize_attr_text(attrs.get("education_level"))
    interests = _normalize_attr_text(attrs.get("hobbies_and_interests"))
    commute = _normalize_attr_text(
        attrs.get("commute") or attrs.get("transportation") or attrs.get("mobility_pattern")
    )
    household = _normalize_attr_text(
        attrs.get("household_type") or attrs.get("family_status") or attrs.get("marital_status")
    )

    cooperation_delta = 0.0
    policy_delta = 0.0
    resource_delta = 0.0
    mobility_delta = 0.0
    factors: list[str] = []

    def apply(delta_key: str, amount: float, reason: str) -> None:
        nonlocal cooperation_delta, policy_delta, resource_delta, mobility_delta
        if delta_key == "cooperation":
            cooperation_delta += amount
        elif delta_key == "policy":
            policy_delta += amount
        elif delta_key == "resource":
            resource_delta += amount
        elif delta_key == "mobility":
            mobility_delta += amount
        factors.append(reason)

    if _contains_any(occupation, ["teacher", "nurse", "social worker", "care", "교사", "간호", "복지", "공무", "public"]):
        apply("cooperation", 0.08, "public-facing occupation lifts cooperation")
        apply("policy", 0.06, "public-facing occupation raises policy sensitivity")
    if _contains_any(occupation, ["entrepreneur", "founder", "business", "trader", "investor", "자영업", "사업", "투자", "상인"]):
        apply("resource", 0.1, "market-facing occupation raises resource focus")
        apply("mobility", 0.05, "market-facing occupation adds movement pressure")
    if _contains_any(occupation, ["driver", "delivery", "field", "sales", "logistics", "운전", "배송", "영업", "물류"]):
        apply("mobility", 0.14, "mobile occupation raises mobility bias")
    if _contains_any(education, ["phd", "doctor", "석사", "박사", "master"]):
        apply("policy", 0.05, "higher education lifts policy sensitivity")
        apply("resource", 0.03, "higher education slightly raises strategic resource focus")
    if _contains_any(interests, ["volunteer", "community", "activism", "civic", "봉사", "공동체", "시민", "활동"]):
        apply("cooperation", 0.08, "community-oriented interest raises cooperation")
        apply("policy", 0.04, "community-oriented interest raises policy attention")
    if _contains_any(interests, ["investing", "finance", "market", "trading", "재테크", "금융", "주식", "시장"]):
        apply("resource", 0.08, "finance-oriented interest raises resource focus")
    if _contains_any(commute, ["car", "bus", "subway", "train", "taxi", "bike", "도보", "자차", "버스", "지하철", "기차", "오토바이"]):
        apply("mobility", 0.08, "commute footprint raises mobility bias")
    if _contains_any(commute, ["remote", "home", "재택", "원격", "home office"]):
        apply("mobility", -0.06, "remote pattern lowers mobility bias")
        apply("cooperation", 0.03, "remote pattern slightly increases local coordination")
    if _contains_any(household, ["single parent", "caregiver", "대가족", "부양", "돌봄", "single-parent"]):
        apply("cooperation", 0.05, "care burden raises cooperation need")
        apply("mobility", -0.04, "care burden slightly reduces mobility")
    if _contains_any(region, ["capital", "seoul", "metro", "urban", "서울", "수도권", "도심"]):
        apply("mobility", 0.04, "urban region slightly raises mobility")
        apply("policy", 0.03, "urban region slightly raises policy sensitivity")

    summary = "; ".join(factors[:6]) if factors else "default persona priors"
    return {
        "cooperation_delta": cooperation_delta,
        "policy_delta": policy_delta,
        "resource_delta": resource_delta,
        "mobility_delta": mobility_delta,
        "factors": factors[:8],
        "summary": summary,
    }


def _normalize_attr_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _contains_any(text: str, needles: List[str]) -> bool:
    if not text:
        return False
    return any(needle in text for needle in needles)


# State: TypedDict 대신 dict 사용 (Cell 직렬화 이슈 회피)
SimulationState = Dict[str, Any]


def _init_node(state: SimulationState) -> SimulationState:
    """초기화: initial_cells가 있으면 사용, 없으면 기본 생성."""
    cells = state.get("initial_cells")
    if cells is None:
        cells = _create_initial_cells(
            count=state.get("initial_cell_count", 5),
            t=0.0,
            role_catalog=state.get("role_catalog"),
            persona_catalog=state.get("persona_catalog"),
            engine_params=state.get("engine_params"),
        )
    else:
        cells = refresh_social_elevation(
            [cell.copy() for cell in cells],
            current_t=0.0,
            engine_params=state.get("engine_params"),
        )
    cells, group_state = apply_collective_dynamics(
        cells,
        current_t=0.0,
        previous_group_state=state.get("group_state"),
    )
    out: SimulationState = {
        "cells": cells,
        "current_t": 0.0,
        "coalition_state": dict(state.get("coalition_state") or {}),
        "coalition_history": [dict(item) for item in state.get("coalition_history") or []],
        "group_state": dict(group_state),
    }
    if "t_max" in state:
        out["t_max"] = state["t_max"]
    if "nutrient_per_step" in state:
        out["nutrient_per_step"] = state["nutrient_per_step"]
    if "snapshot_store" in state:
        out["snapshot_store"] = state["snapshot_store"]
    if "world_events" in state:
        out["world_events"] = list(state["world_events"])
    if "engine_params" in state:
        out["engine_params"] = dict(state["engine_params"])
    store = state.get("snapshot_store")
    if store is not None:
        store.save(0.0, cells)
    return out


def _should_continue(state: SimulationState) -> str:
    """t < t_max이면 step_loop, 아니면 종료."""
    if state["current_t"] < state["t_max"]:
        return "step"
    return "done"


def create_time_flow_graph():
    """시간 흐름 LangGraph 생성 및 컴파일."""
    graph = StateGraph(SimulationState)

    graph.add_node("init", _init_node)
    graph.add_node("step_loop", step_loop_node)

    graph.add_edge(START, "init")
    graph.add_conditional_edges(
        "init",
        lambda s: "step" if s["current_t"] < s["t_max"] else "done",
        {"step": "step_loop", "done": END},
    )
    graph.add_conditional_edges(
        "step_loop",
        _should_continue,
        {"step": "step_loop", "done": END},
    )

    return graph.compile()


def create_resume_time_flow_graph():
    """주입 후 t_inject→t_max만 재계산 (init 생략, START→step_loop).

    state 필수 키: cells, current_t, t_max, snapshot_store
    선택: nutrient_per_step
    """
    graph = StateGraph(SimulationState)
    graph.add_node("step_loop", step_loop_node)
    graph.add_edge(START, "step_loop")
    graph.add_conditional_edges(
        "step_loop",
        _should_continue,
        {"step": "step_loop", "done": END},
    )
    return graph.compile()
