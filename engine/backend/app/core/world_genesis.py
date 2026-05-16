"""프롬프트 기반 세계 제안 (World Genesis).

사용자 질의만으로 t_max·초기 개체 수·역할 목록 등을 제안.
후속: 외부 LLM API로 대체. 현재는 휴리스틱 스텁 (코드·프롬프트는 자체 작성).
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List

from app.core.persona_dataset import infer_country_from_prompt, persona_genesis_bias
from app.core.scenario_compiler import (
    extract_json_object,
    infer_time_step_and_nutrient,
    normalize_scenario_prompt as _compile_scenario_prompt_legacy,
    refine_scenario_for_runtime as _refine_scenario_for_runtime,
)
from app.core.settings import get_llm_chat_enabled
from app.llm.facade import llm_facade


# 기본 역할 풀 — 시나리오가 구체적이지 않을 때
_DEFAULT_ROLES = [
    "생산자",
    "분배자",
    "규제자",
    "소비자",
    "관측자",
]

_KEYWORD_ROLES = [
    (r"정책|규제|법|정부", "규제자"),
    (r"시장|거래|금융|투자", "시장참여자"),
    (r"기업|회사|스타트업", "기업"),
    (r"시민|소비|여론", "시민"),
    (r"기후|환경|에너지", "환경행위자"),
    (r"기술|AI|데이터", "기술주체"),
]


@dataclass
class GenesisPlan:
    """AI(또는 스텁)가 제안하는 단일 세계 초기 조건."""

    t_max: float
    initial_cell_count: int
    role_catalog: List[str]
    rationale: str
    # 한 스텝 t가 달력에서 의미하는 바 (시/일/년 …) — 사용자가 고르지 않음
    t_step_semantic: str
    t_step_unit: str
    # apply_growth에 쓰는 영양 유입 강도 (시간 스케일에 비례해 스텁에서 가중)
    nutrient_per_step: float
    # 초기 에이전트 페르소나 데이터셋 선택 힌트
    persona_country: str
    persona_source: str
    persona_distribution_summary: Dict[str, Any] | None = None


def normalize_scenario_prompt(prompt: str) -> Dict[str, Any]:
    """Compatibility wrapper for the dedicated scenario compiler."""
    return _compile_scenario_prompt_legacy(prompt)


def refine_scenario_for_runtime(
    *,
    engine_params: Dict[str, Any],
    role_catalog: list[str],
    persona_catalog: list[dict],
    simulation_mode: str = "precision",
) -> Dict[str, Any]:
    """Compatibility wrapper for the dedicated scenario compiler."""
    return _refine_scenario_for_runtime(
        engine_params=engine_params,
        role_catalog=role_catalog,
        persona_catalog=persona_catalog,
        simulation_mode=simulation_mode,
    )


def _stable_extra_cells(prompt: str) -> int:
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return int(h[:4], 16) % 12


def propose_world_from_prompt(prompt: str) -> GenesisPlan:
    """
    프롬프트에서 예측·탐색 목적에 맞는 초기 세계를 제안.
    (후속: 동일 계약으로 LLM JSON 출력 연동)
    """
    text = prompt.strip()
    if not text:
        text = "일반 복잡계 시나리오"

    heuristic = _heuristic_plan(text)
    if not get_llm_chat_enabled():
        return heuristic

    llm_plan = _llm_plan(text, heuristic)
    return llm_plan or heuristic


def apply_genesis_overrides(
    plan: GenesisPlan,
    overrides: Dict[str, Any] | None = None,
) -> GenesisPlan:
    data = dict(overrides or {})
    simulation_mode = str(data.get("simulation_mode") or "").strip().lower()
    max_initial_cells = 5000 if simulation_mode == "swarm" else 256
    role_catalog = [
        str(item).strip()
        for item in data.get("role_catalog") or plan.role_catalog
        if str(item).strip()
    ]
    if not role_catalog:
        role_catalog = list(plan.role_catalog)
    return GenesisPlan(
        t_max=max(1.0, float(data.get("t_max", plan.t_max))),
        initial_cell_count=max(
            6, min(max_initial_cells, int(data.get("initial_cell_count", plan.initial_cell_count)))
        ),
        role_catalog=role_catalog[:16],
        rationale=str(data.get("rationale") or plan.rationale),
        t_step_semantic=str(data.get("t_step_semantic") or plan.t_step_semantic),
        t_step_unit=str(data.get("t_step_unit") or plan.t_step_unit),
        nutrient_per_step=max(
            0.01, float(data.get("nutrient_per_step", plan.nutrient_per_step))
        ),
        persona_country=str(data.get("persona_country") or plan.persona_country),
        persona_source=str(data.get("persona_source") or plan.persona_source),
        persona_distribution_summary=dict(data.get("persona_distribution_summary") or plan.persona_distribution_summary or {}),
    )


def _heuristic_plan(text: str) -> GenesisPlan:

    # 시간 범위: 질문 길이·키워드로 거칠게 스케일
    t_max = 80.0
    if len(text) > 200:
        t_max = 160.0
    if re.search(r"장기|10년|수십\s*년|예측", text, re.I):
        t_max = 280.0
    if re.search(r"단기|즉시|몇\s*주", text, re.I):
        t_max = 48.0

    base_cells = 8
    n_extra = _stable_extra_cells(text)
    initial_cell_count = min(48, max(6, base_cells + n_extra))

    roles: List[str] = []
    for pattern, label in _KEYWORD_ROLES:
        if re.search(pattern, text) and label not in roles:
            roles.append(label)
    if len(roles) < 3:
        for r in _DEFAULT_ROLES:
            if r not in roles:
                roles.append(r)
            if len(roles) >= 5:
                break

    t_unit, t_semantic, nutrient = infer_time_step_and_nutrient(text)
    persona_country = infer_country_from_prompt(text) or "KR"
    persona_source = f"configured_dataset:{persona_country}"

    rationale = (
        f"질의 길이·키워드 기반 스텁 제안입니다. "
        f"시간 의미: {t_semantic} (unit={t_unit}), "
        f"스텝당 영양 유입 nutrient_per_step≈{nutrient:.3f}. "
        f"t_max≈{int(t_max)}, 초기 에이전트≈{initial_cell_count}, "
        f"역할 풀: {', '.join(roles[:6])}. "
        f"페르소나 국가 힌트: {persona_country}. "
        f"LLM 연동 시 동일 필드로 최적화된 세계를 채웁니다."
    )

    return GenesisPlan(
        t_max=t_max,
        initial_cell_count=initial_cell_count,
        role_catalog=roles[:8],
        rationale=rationale,
        t_step_semantic=t_semantic,
        t_step_unit=t_unit,
        nutrient_per_step=nutrient,
        persona_country=persona_country,
        persona_source=persona_source,
        persona_distribution_summary={},
    )


def apply_persona_distribution_to_plan(
    plan: GenesisPlan,
    personas: list,
) -> tuple[GenesisPlan, Dict[str, Any]]:
    if not personas:
        return plan, {}
    bias = persona_genesis_bias(personas)
    role_catalog = [str(role).strip() for role in bias.get("role_catalog") or plan.role_catalog if str(role).strip()]
    nutrient = max(0.01, float(plan.nutrient_per_step) * float(bias.get("nutrient_multiplier", 1.0)))
    rationale = (
        f"{plan.rationale} "
        f"Persona-aware bias applied: roles={', '.join(role_catalog[:5])}; "
        f"top_regions={', '.join(str(item['label']) for item in bias.get('summary', {}).get('top_regions', [])[:3]) or 'none'}; "
        f"zone_count≈{int(bias.get('zone_count', 1))}; nutrient_multiplier≈{float(bias.get('nutrient_multiplier', 1.0)):.2f}."
    )
    return (
        GenesisPlan(
            t_max=plan.t_max,
            initial_cell_count=plan.initial_cell_count,
            role_catalog=role_catalog[:8] or list(plan.role_catalog),
            rationale=rationale,
            t_step_semantic=plan.t_step_semantic,
            t_step_unit=plan.t_step_unit,
            nutrient_per_step=nutrient,
            persona_country=plan.persona_country,
            persona_source=plan.persona_source,
            persona_distribution_summary=dict(bias.get("summary") or {}),
        ),
        bias,
    )


def _llm_plan(text: str, fallback: GenesisPlan) -> GenesisPlan | None:
    out = llm_facade.plan_genesis(
        text,
        json.dumps(_plan_to_dict(fallback), ensure_ascii=False),
    )
    payload = extract_json_object(out)
    if payload is None:
        return None
    try:
        role_catalog = [str(x).strip() for x in payload.get("role_catalog") or [] if str(x).strip()]
        if len(role_catalog) < 3:
            role_catalog = list(fallback.role_catalog)
        return GenesisPlan(
            t_max=float(payload.get("t_max", fallback.t_max)),
            initial_cell_count=max(6, min(64, int(payload.get("initial_cell_count", fallback.initial_cell_count)))),
            role_catalog=role_catalog[:8],
            rationale=str(payload.get("rationale") or fallback.rationale),
            t_step_semantic=str(payload.get("t_step_semantic") or fallback.t_step_semantic),
            t_step_unit=str(payload.get("t_step_unit") or fallback.t_step_unit),
            nutrient_per_step=max(0.01, float(payload.get("nutrient_per_step", fallback.nutrient_per_step))),
            persona_country=str(payload.get("persona_country") or fallback.persona_country),
            persona_source=str(payload.get("persona_source") or fallback.persona_source),
            persona_distribution_summary=dict(fallback.persona_distribution_summary or {}),
        )
    except Exception:
        return None


def _plan_to_dict(plan: GenesisPlan) -> dict:
    return {
        "t_max": plan.t_max,
        "initial_cell_count": plan.initial_cell_count,
        "role_catalog": list(plan.role_catalog),
        "rationale": plan.rationale,
        "t_step_semantic": plan.t_step_semantic,
        "t_step_unit": plan.t_step_unit,
        "nutrient_per_step": plan.nutrient_per_step,
        "persona_country": plan.persona_country,
        "persona_source": plan.persona_source,
        "persona_distribution_summary": dict(plan.persona_distribution_summary or {}),
    }
