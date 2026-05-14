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
    """Turn any user input into a simulation-ready scenario packet.

    The raw prompt is preserved, but short/underspecified prompts get a stable
    scaffold so persona seeding, thought prompts, and swarm relevance all see a
    comparable level of scenario detail.
    """
    raw = " ".join(str(prompt or "").strip().split())
    if not raw:
        raw = "일반 사회 변화 시나리오"
    tokens = _tokens(raw)
    domain = _infer_domain(raw)
    country = infer_country_from_prompt(raw) or "KR"
    actors = _infer_actor_set(raw, domain=domain)
    conflict_axes = _infer_conflict_axes(raw, domain=domain)
    policy_shocks = _infer_policy_shocks(raw, domain=domain)
    observables = _infer_observables(raw, domain=domain)
    time_unit, time_semantic, _ = _infer_time_step_and_nutrient(raw)
    specificity = _specificity_score(raw, tokens)
    normalized = (
        f"원문 시나리오: {raw}\n"
        f"시뮬레이션 배경: {country} 맥락의 {domain} 변화가 여러 이해관계자에게 비대칭적으로 작용한다.\n"
        f"핵심 행위자: {', '.join(actors)}.\n"
        f"갈등/협력 축: {', '.join(conflict_axes)}.\n"
        f"초기 충격 후보: {', '.join(policy_shocks)}.\n"
        f"관측 목표: {', '.join(observables)}.\n"
        f"시간 해석: {time_semantic}.\n"
        "시뮬레이션 지침: 각 에이전트는 자신의 persona, role, zone을 기준으로 압력, 협상, 이동, 자원 선택을 구체적으로 갱신한다. "
        "짧은 입력이라도 집단 분화, 정책 민감도, 지역/역할별 비대칭 반응, 관계선 상호작용이 드러나도록 실행한다."
    )
    return {
        "raw_prompt": raw,
        "scenario_prompt": normalized,
        "scenario_quality": {
            "specificity_score": round(specificity, 3),
            "domain": domain,
            "country": country,
            "actors": actors,
            "conflict_axes": conflict_axes,
            "policy_shocks": policy_shocks,
            "observables": observables,
            "t_step_unit": time_unit,
            "was_expanded": specificity < 0.72,
        },
    }


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


def _infer_domain(text: str) -> str:
    checks = [
        (r"주택|부동산|임대|월세|housing|rent|real estate", "주거/부동산"),
        (r"고용|노동|임금|일자리|employment|labor|wage|job", "노동/고용"),
        (r"기후|환경|탄소|에너지|climate|carbon|energy", "기후/에너지"),
        (r"금리|금융|투자|시장|물가|inflation|finance|market|rate", "시장/금융"),
        (r"교육|학교|대학|education|school|university", "교육/역량"),
        (r"의료|건강|돌봄|health|care|hospital", "보건/돌봄"),
        (r"AI|기술|데이터|플랫폼|technology|platform|data", "기술/플랫폼"),
        (r"교통|물류|이동|transport|logistics|mobility", "교통/물류"),
    ]
    for pattern, label in checks:
        if re.search(pattern, text, re.I):
            return label
    return "사회 정책/시장"


def _infer_actor_set(text: str, *, domain: str) -> list[str]:
    actors = ["시민/가계", "정책 담당자", "시장 참여자"]
    domain_actors = {
        "주거/부동산": ["임차인", "임대인", "건설/금융 이해관계자"],
        "노동/고용": ["노동자", "고용주", "취약 구직자"],
        "기후/에너지": ["에너지 소비자", "산업체", "환경 단체"],
        "시장/금융": ["투자자", "소비자", "규제기관"],
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
    return actors[:8]


def _infer_conflict_axes(text: str, *, domain: str) -> list[str]:
    axes = ["정책 수혜자와 비용 부담자의 비대칭", "지역/zone별 압력 차이", "협력과 이탈의 선택 갈등"]
    if domain in {"주거/부동산", "시장/금융"}:
        axes.append("자산 보유자와 비보유자의 기대 차이")
    if domain in {"노동/고용", "기술/플랫폼"}:
        axes.append("생산성 향상과 고용 안정성의 긴장")
    if domain in {"기후/에너지", "교통/물류"}:
        axes.append("전환 비용과 장기 편익의 시차")
    if re.search(r"불평등|격차|inequality|gap", text, re.I):
        axes.append("소득/지역 격차 확대 가능성")
    return axes[:6]


def _infer_policy_shocks(text: str, *, domain: str) -> list[str]:
    if re.search(r"보조금|지원|subsidy|support", text, re.I):
        return ["선별 보조금 도입", "지원 대상 재분류", "재정 지속성 논쟁"]
    if re.search(r"규제|제한|restriction|regulation", text, re.I):
        return ["규제 강화", "대상 집단의 회피/적응", "비대상 집단으로 압력 전파"]
    defaults = {
        "주거/부동산": ["임대료/대출 규칙 변화", "주거비 충격", "지역별 공급 제약"],
        "노동/고용": ["고용 보조/규제 변화", "임금 충격", "직무 이동성 변화"],
        "기후/에너지": ["탄소/에너지 비용 충격", "전환 보조금", "산업별 부담 재배분"],
        "시장/금융": ["금리/유동성 충격", "소비심리 변화", "자산가격 기대 조정"],
        "기술/플랫폼": ["자동화/플랫폼 규칙 변화", "데이터 접근성 변화", "노동 대체 압력"],
    }
    return defaults.get(domain, ["정책 방향 전환", "자원 배분 변화", "집단별 해석 차이"])


def _infer_observables(text: str, *, domain: str) -> list[str]:
    observables = ["collective pressure", "fracture risk", "cohesion/tension", "agent interaction lines"]
    if domain in {"주거/부동산", "시장/금융"}:
        observables.append("자원/가격 민감도")
    if domain in {"노동/고용", "교통/물류"}:
        observables.append("mobility/drift")
    if re.search(r"신념|여론|trust|belief|opinion", text, re.I):
        observables.append("belief trajectory")
    return observables[:7]


def _stable_extra_cells(prompt: str) -> int:
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return int(h[:4], 16) % 12


def _infer_time_step_and_nutrient(text: str) -> tuple[str, str, float]:
    """질의에서 스텝의 시간 단위 추정 → 영양(에너지 유입) 스케일.

    후속: LLM이 동일 필드를 JSON으로 채움. 큰 스텝(년)일수록 한 번에 유입되는
    «기간 합산» 자원을 크게 두는 단순 모델(튜닝 가능).
    """
    if re.search(
        r"10\s*년|십\s*년|수십\s*년|decade|세\s*기|장기\s*예측",
        text,
        re.I,
    ):
        return (
            "decade_scale",
            "1 스텝 ≈ 다년·장기 정책 주기 (스텁: 연 단위 흐름에 맞춘 합산)",
            120.0,
        )
    if re.search(
        r"연간|년\s*단위|1\s*년|한\s*해|per\s*year|annual|yoy|매\s*년",
        text,
        re.I,
    ):
        return "year", "1 스텝 ≈ 1년", 52.0
    if re.search(r"월|분기|month|quarterly", text, re.I):
        return "month", "1 스텝 ≈ 1개월", 4.5
    if re.search(
        r"시간|시간당|실시간|intraday|hourly|매\s*시",
        text,
        re.I,
    ):
        return "hour", "1 스텝 ≈ 1시간", 0.06
    if re.search(r"일일|매\s*일|하루|daily|per\s*day", text, re.I):
        return "day", "1 스텝 ≈ 1일", 1.0
    return "day", "1 스텝 ≈ 1일 (질의에서 단위 힌트 없음, 기본)", 1.0


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

    t_unit, t_semantic, nutrient = _infer_time_step_and_nutrient(text)
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
    payload = _extract_json_object(out)
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


def _extract_json_object(text: str) -> dict | None:
    raw = text.strip()
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
