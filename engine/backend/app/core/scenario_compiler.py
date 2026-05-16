"""End4D scenario compiler.

This module turns raw user text into a simulation contract. It deliberately
does not imitate MiroFish's social-platform domain; it borrows the useful
pipeline shape: normalize seed material first, then let runtime/profile/field
layers consume a stable contract.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

from app.core.persona_dataset import infer_country_from_prompt
from app.core.settings import get_llm_chat_enabled
from app.llm.facade import llm_facade


@dataclass(frozen=True)
class ScenarioContract:
    raw_prompt: str
    scenario_prompt: str
    domain: str
    country: str
    actors: list[str]
    zones: list[str]
    conflict_axes: list[str]
    pressure_sources: list[str]
    observables: list[str]
    time_unit: str
    time_semantic: str
    specificity_score: float
    was_expanded: bool

    def to_legacy_packet(self) -> dict[str, Any]:
        quality = {
            "specificity_score": round(float(self.specificity_score), 3),
            "domain": self.domain,
            "country": self.country,
            "actors": list(self.actors),
            "zones": list(self.zones),
            "conflict_axes": list(self.conflict_axes),
            "policy_shocks": list(self.pressure_sources),
            "pressure_sources": list(self.pressure_sources),
            "observables": list(self.observables),
            "t_step_unit": self.time_unit,
            "was_expanded": bool(self.was_expanded),
        }
        return {
            "raw_prompt": self.raw_prompt,
            "scenario_prompt": self.scenario_prompt,
            "scenario_quality": quality,
            "scenario_contract": asdict(self),
        }


def compile_scenario_prompt(prompt: str) -> ScenarioContract:
    raw = " ".join(str(prompt or "").strip().split())
    if not raw:
        raw = "일반 사회 변화 시나리오"
    tokens = _tokens(raw)
    domain = infer_domain(raw)
    country = infer_country_from_prompt(raw) or "KR"
    actors = infer_actor_set(raw, domain=domain)
    zones = runtime_zones_for_domain(domain)
    conflict_axes = infer_conflict_axes(raw, domain=domain)
    pressure_sources = infer_policy_shocks(raw, domain=domain)
    observables = infer_observables(raw, domain=domain)
    time_unit, time_semantic, _ = infer_time_step_and_nutrient(raw)
    specificity = _specificity_score(raw, tokens)
    scenario_prompt = (
        f"원문 시나리오: {raw}\n"
        f"시뮬레이션 배경: {country} 맥락의 {domain} 변화가 여러 이해관계자에게 비대칭적으로 작용한다.\n"
        f"핵심 행위자: {', '.join(actors)}.\n"
        f"초기 zone/사회장: {', '.join(zones)}.\n"
        f"갈등/협력 축: {', '.join(conflict_axes)}.\n"
        f"초기 충격 후보: {', '.join(pressure_sources)}.\n"
        f"관측 목표: {', '.join(observables)}.\n"
        f"시간 해석: {time_semantic}.\n"
        "시뮬레이션 지침: 각 에이전트는 자신의 이름, 역할, 직업, zone, 관계 기억을 기준으로 압력, 협상, 이동, 자원 선택을 구체적으로 갱신한다. "
        "짧은 입력이라도 집단 분화, 정책 민감도, 지역/역할별 비대칭 반응, 관계선 상호작용이 드러나도록 실행한다."
    )
    return ScenarioContract(
        raw_prompt=raw,
        scenario_prompt=scenario_prompt,
        domain=domain,
        country=country,
        actors=actors,
        zones=zones,
        conflict_axes=conflict_axes,
        pressure_sources=pressure_sources,
        observables=observables,
        time_unit=time_unit,
        time_semantic=time_semantic,
        specificity_score=specificity,
        was_expanded=specificity < 0.72,
    )


def normalize_scenario_prompt(prompt: str) -> dict[str, Any]:
    return compile_scenario_prompt(prompt).to_legacy_packet()


def prepare_swarm_v2_scenario(prompt: str) -> dict[str, Any]:
    """Compile user input into a V2 runtime brief.

    Swarm V2 should not consume raw user text directly. A short prompt like
    "기본소득" needs concrete actors, conflict axes, zones, and early beats before
    the fast stream starts; otherwise every agent sounds like it is reacting to a
    vague keyword. This helper keeps the raw prompt for provenance while giving
    the runtime a stable executable scenario.
    """
    contract = compile_scenario_prompt(prompt)
    legacy_packet = contract.to_legacy_packet()
    refined = refine_scenario_for_runtime(
        engine_params=legacy_packet,
        role_catalog=contract.actors,
        persona_catalog=[],
        simulation_mode="swarm",
    )
    director = dict(refined.get("scenario_director") or {})
    scenario_prompt = _compose_swarm_v2_runtime_prompt(
        raw_prompt=contract.raw_prompt,
        scenario_prompt=str(refined.get("scenario_prompt") or contract.scenario_prompt),
        actor_roles=list(refined.get("scenario_actor_roles") or contract.actors),
        initial_zones=list(refined.get("scenario_initial_zones") or contract.zones),
        conflict_axes=list(refined.get("scenario_conflict_axes") or contract.conflict_axes),
        initial_scene_beats=list(refined.get("scenario_initial_scene_beats") or []),
        placement_logic=str(refined.get("scenario_placement_logic") or ""),
    )
    return {
        "raw_prompt": contract.raw_prompt,
        "scenario_prompt": scenario_prompt,
        "scenario_contract": legacy_packet.get("scenario_contract") or asdict(contract),
        "scenario_quality": dict(refined.get("scenario_quality") or legacy_packet.get("scenario_quality") or {}),
        "scenario_director_mode": str(refined.get("scenario_director_mode") or "heuristic"),
        "scenario_director_fallback_reason": str(
            (refined.get("scenario_quality") or {}).get("runtime_director_fallback_reason") or ""
        ),
        "scenario_director": director,
        "scenario_actor_roles": list(refined.get("scenario_actor_roles") or contract.actors),
        "scenario_initial_zones": list(refined.get("scenario_initial_zones") or contract.zones),
        "scenario_conflict_axes": list(refined.get("scenario_conflict_axes") or contract.conflict_axes),
        "scenario_initial_scene_beats": list(refined.get("scenario_initial_scene_beats") or []),
        "scenario_placement_logic": str(refined.get("scenario_placement_logic") or ""),
    }


def _compose_swarm_v2_runtime_prompt(
    *,
    raw_prompt: str,
    scenario_prompt: str,
    actor_roles: list[str],
    initial_zones: list[str],
    conflict_axes: list[str],
    initial_scene_beats: list[str],
    placement_logic: str,
) -> str:
    beats = initial_scene_beats or [
        "각 행위자가 자기 이해관계를 기준으로 첫 반응을 낸다",
        "비용 부담자와 수혜자가 서로의 말을 받아치며 관계선을 만든다",
        "중재자/기관 역할이 압력 완화 또는 증폭의 계기가 된다",
    ]
    return (
        f"원문 시나리오: {raw_prompt}\n"
        f"실행용 시나리오: {scenario_prompt}\n"
        f"핵심 행위자/역할: {', '.join(actor_roles[:10])}.\n"
        f"초기 사회장/zone: {', '.join(initial_zones[:12])}.\n"
        f"갈등/협력 축: {', '.join(conflict_axes[:8])}.\n"
        f"초기 배치 논리: {placement_logic or '이해관계가 가까운 집단은 밀집시키고 갈등 집단은 경계면에 배치한다.'}\n"
        f"초기 stream beats: {' / '.join(beats[:8])}.\n"
        "Swarm V2 실행 지침: 한 세션은 많은 빠른 상호작용으로 구성된다. "
        "각 에이전트는 자신의 이름, 역할, zone, 최근 기억을 기준으로 다른 에이전트의 발언에 즉시 반응한다."
    )


def refine_scenario_for_runtime(
    *,
    engine_params: dict[str, Any],
    role_catalog: list[str],
    persona_catalog: list[dict],
    simulation_mode: str = "precision",
) -> dict[str, Any]:
    params = dict(engine_params or {})
    if params.get("scenario_director_applied"):
        return params

    raw_prompt = str(params.get("raw_prompt") or params.get("scenario_prompt") or "").strip()
    scenario_prompt = str(params.get("scenario_prompt") or raw_prompt or "일반 사회 변화 시나리오")
    fallback = heuristic_runtime_director(
        raw_prompt=raw_prompt,
        scenario_prompt=scenario_prompt,
        role_catalog=role_catalog,
        persona_catalog=persona_catalog,
        simulation_mode=simulation_mode,
    )

    if not get_llm_chat_enabled():
        return merge_runtime_director(params, fallback, mode="heuristic", fallback_reason="llm_disabled")

    payload = {
        "raw_prompt": raw_prompt,
        "current_scenario_prompt": scenario_prompt,
        "current_role_catalog": list(role_catalog or []),
        "persona_preview": persona_preview(persona_catalog),
        "simulation_mode": simulation_mode,
        "current_scenario_quality": dict(params.get("scenario_quality") or {}),
        "end4d_identity": {
            "domain": "4d_social_field",
            "axes": ["x", "y", "z", "t"],
            "do_not_emit_social_media_actions": True,
            "desired_outputs": ["actors", "zones", "pressure_sources", "relationship_conflicts"],
        },
    }
    try:
        text, meta = llm_facade.direct_scenario(payload)
    except Exception as exc:
        return merge_runtime_director(params, fallback, mode="heuristic", fallback_reason=f"provider_error:{type(exc).__name__}")

    parsed = extract_json_object(text)
    if not parsed:
        return merge_runtime_director(params, fallback, mode="heuristic", fallback_reason="invalid_director_json")

    director = normalize_runtime_director_payload(parsed, fallback=fallback)
    director["llm_meta"] = {
        "provider": str(meta.get("provider") or ""),
        "model": str(meta.get("model") or ""),
        "fallback_reason": str(meta.get("fallback_reason") or ""),
        "prompt_count_sent": int(meta.get("prompt_count_sent", 0) or 0),
    }
    return merge_runtime_director(params, director, mode="llm", fallback_reason=str(meta.get("fallback_reason") or ""))


def heuristic_runtime_director(
    *,
    raw_prompt: str,
    scenario_prompt: str,
    role_catalog: list[str],
    persona_catalog: list[dict],
    simulation_mode: str,
) -> dict[str, Any]:
    text = scenario_prompt or raw_prompt
    domain = infer_domain(text)
    actors = infer_actor_set(text, domain=domain)
    zones = runtime_zones_for_domain(domain)
    return {
        "scenario_prompt": scenario_prompt,
        "actor_roles": actors[:8] or list(role_catalog or ["시민/가계", "정책 담당자", "시장 참여자"]),
        "initial_zones": zones,
        "placement_logic": (
            "이해관계가 가까운 행위자는 같은 zone/bloc에 배치하고, 비용 부담자와 정책 집행자는 인접하지만 분리된 위치에서 시작한다."
            if simulation_mode != "swarm"
            else "역할별 bloc 중심을 만들되, 갈등 축이 있는 bloc은 서로 가까운 경계에 배치해 초반 상호작용 밀도를 높인다."
        ),
        "conflict_axes": infer_conflict_axes(text, domain=domain),
        "initial_scene_beats": [
            f"{actors[0]}가 초기 충격을 해석하고 주변 집단과 정보를 교환",
            f"{actors[min(1, len(actors)-1)]}가 비용/혜택 배분을 두고 긴장 신호를 형성",
            "정책 담당자와 현장 집단 사이의 신뢰/불신이 관계선으로 드러남",
            "지역/zone별 압력 차이가 이동성과 협력 선택을 흔듦",
        ],
        "role_assignment_policy": "persona의 occupation/region/value와 scenario actor role의 토큰을 매칭해 가장 가까운 역할을 부여한다.",
        "pressure_seeds": {
            "sensitive_roles": actors[:4],
            "separation_axes": infer_conflict_axes(text, domain=domain)[:3],
        },
        "rationale": "runtime heuristic director fallback",
    }


def merge_runtime_director(
    params: dict[str, Any],
    director: dict[str, Any],
    *,
    mode: str,
    fallback_reason: str,
) -> dict[str, Any]:
    scenario_quality = dict(params.get("scenario_quality") or {})
    scenario_quality.update(
        {
            "runtime_director_mode": mode,
            "runtime_director_fallback_reason": fallback_reason,
            "runtime_actor_roles": list(director.get("actor_roles") or []),
            "runtime_initial_zones": list(director.get("initial_zones") or []),
        }
    )
    merged = dict(params)
    merged.update(
        {
            "scenario_prompt": str(director.get("scenario_prompt") or params.get("scenario_prompt") or ""),
            "scenario_quality": scenario_quality,
            "scenario_director_applied": True,
            "scenario_director_mode": mode,
            "scenario_director": dict(director),
            "scenario_actor_roles": list(director.get("actor_roles") or []),
            "scenario_initial_zones": list(director.get("initial_zones") or []),
            "scenario_placement_logic": str(director.get("placement_logic") or ""),
            "scenario_conflict_axes": list(director.get("conflict_axes") or []),
            "scenario_initial_scene_beats": list(director.get("initial_scene_beats") or []),
            "zone_layout": "scenario_social_field",
            "zone_count": max(3, min(24, len(list(director.get("initial_zones") or [])) or int(params.get("zone_count", 4) or 4))),
            "regional_labels": list(director.get("initial_zones") or params.get("regional_labels") or []),
        }
    )
    return merged


def infer_domain(text: str) -> str:
    checks = [
        (r"주택|부동산|임대|월세|housing|rent|real estate", "주거/부동산"),
        (r"고용|노동|임금|일자리|employment|labor|wage|job", "노동/고용"),
        (r"기본소득|복지|빈곤|소득\s*보장|생활\s*지원|welfare|basic income|ubi|poverty", "복지/소득"),
        (r"기후|환경|탄소|에너지|climate|carbon|energy", "기후/에너지"),
        (r"금리|금융|투자|시장|물가|가격|담합|inflation|finance|market|rate|price", "시장/금융"),
        (r"교육|학교|대학|education|school|university", "교육/역량"),
        (r"의료|건강|돌봄|health|care|hospital", "보건/돌봄"),
        (r"AI|기술|데이터|플랫폼|technology|platform|data", "기술/플랫폼"),
        (r"교통|물류|이동|transport|logistics|mobility", "교통/물류"),
    ]
    for pattern, label in checks:
        if re.search(pattern, text, re.I):
            return label
    return "사회 정책/시장"


def infer_actor_set(text: str, *, domain: str) -> list[str]:
    actors = (
        ["저소득 시민", "청년 구직자", "납세자", "지방행정 담당자", "소규모 상점 경영자"]
        if domain == "복지/소득"
        else ["시민/가계", "정책 담당자", "시장 참여자"]
    )
    domain_actors = {
        "주거/부동산": ["임차인", "임대인", "건설/금융 이해관계자"],
        "노동/고용": ["노동자", "고용주", "취약 구직자"],
        "복지/소득": ["저소득 시민", "청년 구직자", "납세자", "지방행정 담당자", "소규모 상점 경영자"],
        "기후/에너지": ["에너지 소비자", "산업체", "환경 단체"],
        "시장/금융": ["소비자", "가격 결정 기업", "규제기관"],
        "교육/역량": ["학생/학부모", "교육기관", "고용시장"],
        "보건/돌봄": ["환자/가계", "의료기관", "돌봄 노동자"],
        "기술/플랫폼": ["플랫폼 기업", "노동자/사용자", "규제기관"],
        "교통/물류": ["통근자", "물류 노동자", "지역 상권"],
    }
    for actor in domain_actors.get(domain, []):
        if actor not in actors:
            actors.append(actor)
    if re.search(r"청년|youth|young", text, re.I):
        actors.append("청년층")
    if re.search(r"노년|고령|elder|senior", text, re.I):
        actors.append("고령층")
    if re.search(r"자영업|상인|small business", text, re.I):
        actors.append("자영업자")
    return list(dict.fromkeys(actors))[:8]


def infer_conflict_axes(text: str, *, domain: str) -> list[str]:
    axes = ["정책 수혜자와 비용 부담자의 비대칭", "지역/zone별 압력 차이", "협력과 이탈의 선택 갈등"]
    if domain in {"주거/부동산", "시장/금융"}:
        axes.append("자산/가격 결정권을 가진 집단과 비용을 부담하는 집단의 기대 차이")
    if domain == "복지/소득":
        axes.append("현금 지원 수혜 기대와 재정 부담 우려의 충돌")
        axes.append("소비 진작 기대와 근로/세금 부담 논쟁")
    if domain in {"노동/고용", "기술/플랫폼"}:
        axes.append("생산성 향상과 고용 안정성의 긴장")
    if domain in {"기후/에너지", "교통/물류"}:
        axes.append("전환 비용과 장기 편익의 시차")
    if re.search(r"불평등|격차|inequality|gap", text, re.I):
        axes.append("소득/지역 격차 확대 가능성")
    return axes[:6]


def infer_policy_shocks(text: str, *, domain: str) -> list[str]:
    if re.search(r"보조금|지원|subsidy|support", text, re.I):
        return ["선별 보조금 도입", "지원 대상 재분류", "재정 지속성 논쟁"]
    if re.search(r"기본소득|복지|빈곤|소득\s*보장|basic income|ubi|welfare", text, re.I):
        return ["기본소득 지급 충격", "재원 조달/세금 논쟁", "소비 회복 기대와 근로 유인 논쟁"]
    if re.search(r"규제|제한|restriction|regulation|담합", text, re.I):
        return ["규제 강화", "대상 집단의 회피/적응", "비대상 집단으로 압력 전파"]
    defaults = {
        "주거/부동산": ["임대료/대출 규칙 변화", "주거비 충격", "지역별 공급 제약"],
        "노동/고용": ["고용 보조/규제 변화", "임금 충격", "직무 이동성 변화"],
        "기후/에너지": ["탄소/에너지 비용 충격", "전환 보조금", "산업별 부담 재배분"],
        "복지/소득": ["소득 보장 정책 충격", "재정 부담 재분배", "지역 소비 변화"],
        "시장/금융": ["금리/가격 충격", "소비심리 변화", "자산가격 기대 조정"],
        "기술/플랫폼": ["자동화/플랫폼 규칙 변화", "데이터 접근성 변화", "노동 대체 압력"],
    }
    return defaults.get(domain, ["정책 방향 전환", "자원 배분 변화", "집단별 해석 차이"])


def infer_observables(text: str, *, domain: str) -> list[str]:
    observables = ["collective pressure", "fracture risk", "cohesion/tension", "agent interaction lines"]
    if domain in {"주거/부동산", "시장/금융", "복지/소득"}:
        observables.append("자원/가격 민감도")
    if domain in {"노동/고용", "교통/물류"}:
        observables.append("mobility/drift")
    if re.search(r"신념|여론|trust|belief|opinion", text, re.I):
        observables.append("belief trajectory")
    return observables[:7]


def runtime_zones_for_domain(domain: str) -> list[str]:
    mapping = {
        "주거/부동산": ["임차인 밀집지", "자산 보유 bloc", "정책 집행 구역", "금융/대출 압력권"],
        "노동/고용": ["노동자 네트워크", "고용주 bloc", "취약 구직자 구역", "정책 중재 구역"],
        "복지/소득": ["저소득 시민권", "납세자 우려권", "지방행정 집행권", "지역 상권 반응권"],
        "시장/금융": ["소비자 압력권", "가격 결정 기업권", "규제기관 주변", "시장 기대 전파권"],
        "기후/에너지": ["전환 비용권", "산업체 bloc", "환경 여론권", "정책 보조권"],
        "기술/플랫폼": ["플랫폼 중심부", "사용자/노동자 경계", "규제 감시권", "데이터 접근권"],
        "교통/물류": ["물류 노동 경계", "통근자 밀집권", "지역 상권권", "정책 통제권"],
    }
    return mapping.get(domain, ["수혜 집단권", "비용 부담권", "정책 중재권", "시장 반응권"])


def infer_time_step_and_nutrient(text: str) -> tuple[str, str, float]:
    if re.search(r"10\s*년|십\s*년|수십\s*년|decade|세\s*기|장기\s*예측", text, re.I):
        return "decade_scale", "1 스텝 ≈ 다년·장기 정책 주기 (스텁: 연 단위 흐름에 맞춘 합산)", 120.0
    if re.search(r"연간|년\s*단위|1\s*년|한\s*해|per\s*year|annual|yoy|매\s*년", text, re.I):
        return "year", "1 스텝 ≈ 1년", 52.0
    if re.search(r"월|분기|month|quarterly", text, re.I):
        return "month", "1 스텝 ≈ 1개월", 4.5
    if re.search(r"시간|시간당|실시간|intraday|hourly|매\s*시", text, re.I):
        return "hour", "1 스텝 ≈ 1시간", 0.06
    if re.search(r"일일|매\s*일|하루|daily|per\s*day", text, re.I):
        return "day", "1 스텝 ≈ 1일", 1.0
    return "day", "1 스텝 ≈ 1일 (질의에서 단위 힌트 없음, 기본)", 1.0


def persona_preview(persona_catalog: list[dict], limit: int = 12) -> list[dict[str, Any]]:
    preview = []
    for item in list(persona_catalog or [])[:limit]:
        attrs = dict(item.get("attrs") or {})
        preview.append(
            {
                "persona_id": str(item.get("persona_id") or ""),
                "role_key": str(item.get("role_key") or ""),
                "role_label": str(item.get("role_label") or ""),
                "persona_text": str(item.get("persona_text") or "")[:220],
                "attrs": {
                    key: attrs[key]
                    for key in ("occupation", "district", "province", "region", "age", "gender", "values")
                    if key in attrs
                },
            }
        )
    return preview


def normalize_runtime_director_payload(payload: dict[str, Any], *, fallback: dict[str, Any]) -> dict[str, Any]:
    scenario_prompt = str(payload.get("scenario_prompt") or fallback.get("scenario_prompt") or "").strip()
    actor_roles = string_list(payload.get("actor_roles"), fallback=fallback.get("actor_roles") or [])
    initial_zones = string_list(payload.get("initial_zones"), fallback=fallback.get("initial_zones") or [])
    conflict_axes = string_list(payload.get("conflict_axes"), fallback=fallback.get("conflict_axes") or [])
    initial_scene_beats = string_list(payload.get("initial_scene_beats"), fallback=fallback.get("initial_scene_beats") or [])
    pressure_seeds = mapping_dict(payload.get("pressure_seeds"), fallback=fallback.get("pressure_seeds") or {})
    return {
        "scenario_prompt": scenario_prompt or str(fallback.get("scenario_prompt") or ""),
        "actor_roles": actor_roles[:10],
        "initial_zones": initial_zones[:12],
        "placement_logic": str(payload.get("placement_logic") or fallback.get("placement_logic") or ""),
        "conflict_axes": conflict_axes[:8],
        "initial_scene_beats": initial_scene_beats[:10],
        "role_assignment_policy": str(payload.get("role_assignment_policy") or fallback.get("role_assignment_policy") or ""),
        "pressure_seeds": pressure_seeds,
        "rationale": str(payload.get("rationale") or fallback.get("rationale") or ""),
    }


def string_list(value: Any, *, fallback: Any) -> list[str]:
    if isinstance(value, str):
        raw = re.split(r"[,;\n]+", value)
    else:
        raw = value if isinstance(value, list) else fallback
    out = []
    for item in list(raw or []):
        if isinstance(item, dict):
            item = (
                item.get("name")
                or item.get("label")
                or item.get("role")
                or item.get("zone")
                or item.get("axis")
                or item.get("beat")
                or item.get("title")
                or item.get("description")
                or ""
            )
        text = str(item).strip()
        if text:
            out.append(text)
    return out


def mapping_dict(value: Any, *, fallback: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(fallback, dict):
        return dict(fallback)
    return {}


def extract_json_object(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
    return None


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z가-힣0-9]{2,}", str(text or ""))}


def _specificity_score(text: str, tokens: set[str]) -> float:
    score = min(0.45, len(tokens) / 28.0)
    if re.search(r"정책|규제|보조금|세금|금리|policy|regulation|subsidy|tax|rate", text, re.I):
        score += 0.18
    if re.search(r"청년|노동|기업|자영업|시민|정부|지역|agent|actor|worker|business|citizen", text, re.I):
        score += 0.16
    if re.search(r"갈등|분열|협력|불평등|가격|고용|이동|trust|conflict|inequality|employment", text, re.I):
        score += 0.14
    if re.search(r"년|월|분기|시간|장기|단기|year|month|quarter|long|short", text, re.I):
        score += 0.10
    return max(0.0, min(1.0, score))
