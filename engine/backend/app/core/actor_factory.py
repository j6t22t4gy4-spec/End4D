"""Actor/persona factory for End4D.

Persona datasets are raw material. The engine needs actor sheets: a stable name,
a social role, a local identity, a zone, motives, fears, and initial behavioral
biases that the 4D field can simulate.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ActorSheet:
    actor_id: str
    name: str
    role_key: str
    role_label: str
    occupation: str
    country: str
    zone_id: str
    zone_label: str
    identity_summary: str
    goal: str
    fear: str
    speech_style: str
    relationship_bias: str
    attrs: dict[str, Any] = field(default_factory=dict)


KOREAN_FAMILY_NAMES = ["김", "이", "박", "최", "정", "강", "조", "윤", "장", "임", "한", "오", "서", "신", "권", "황"]
KOREAN_GIVEN_NAMES = [
    "민준",
    "서연",
    "지훈",
    "하린",
    "도윤",
    "수빈",
    "현우",
    "예진",
    "준호",
    "나영",
    "태민",
    "가은",
    "성민",
    "유진",
    "재호",
    "소윤",
    "민재",
    "다은",
    "지호",
    "은서",
]


def build_actor_sheet(
    *,
    persona: dict[str, Any],
    role_catalog: list[str],
    scenario_roles: list[str],
    scenario_zones: list[str],
    zone_count: int,
    region_zone_map: dict[str, int],
    i: int,
) -> ActorSheet:
    attrs = dict(persona.get("attrs") or {})
    persona_text = str(persona.get("persona_text") or "")
    role_key = choose_scenario_role(persona, role_catalog, i=i, scenario_roles=scenario_roles)
    role_label = str(role_key if scenario_roles else persona.get("role_label") or role_key)
    name = actor_name(persona, attrs=attrs, i=i)
    occupation = str(attrs.get("occupation") or persona.get("role_label") or role_label).strip() or role_label
    region_label = str(
        attrs.get("district")
        or attrs.get("province")
        or attrs.get("region")
        or persona.get("zone_label")
        or ""
    ).strip()
    zone_index = choose_scenario_zone_index(
        persona=persona,
        role_key=role_key,
        region_label=region_label,
        zone_count=zone_count,
        region_zone_map=region_zone_map,
        scenario_zones=scenario_zones,
        i=i,
    )
    zone_id = str(persona.get("zone_id") or f"zone-{zone_index}")
    zone_label = str(
        persona.get("zone_label")
        or (scenario_zones[zone_index] if scenario_zones and zone_index < len(scenario_zones) else "")
        or region_label
        or f"Zone {zone_index}"
    )
    identity = identity_summary(
        name=name,
        role=role_label,
        persona_text=persona_text,
        attrs=attrs,
        zone_label=zone_label,
    )
    goal, fear = motive_pair(role=role_label, occupation=occupation, persona_text=persona_text)
    style = speech_style(attrs, role=role_label)
    relationship = relationship_bias(attrs, role=role_label)
    actor_attrs = dict(attrs)
    actor_attrs.update(
        {
            "agent_name": name,
            "display_name": f"{name}({role_label})",
            "occupation": occupation,
            "identity_summary": identity,
            "actor_goal": goal,
            "actor_fear": fear,
            "speech_style": style,
            "relationship_bias": relationship,
        }
    )
    return ActorSheet(
        actor_id=str(persona.get("persona_id") or f"actor-{i}"),
        name=name,
        role_key=role_key,
        role_label=role_label,
        occupation=occupation,
        country=str(persona.get("country") or attrs.get("country") or ""),
        zone_id=zone_id,
        zone_label=zone_label,
        identity_summary=identity,
        goal=goal,
        fear=fear,
        speech_style=style,
        relationship_bias=relationship,
        attrs=actor_attrs,
    )


def choose_scenario_role(persona: dict[str, Any], roles: list[str], *, i: int, scenario_roles: list[str]) -> str:
    if not roles:
        return "agent"
    if not scenario_roles:
        return str(persona.get("role_key") or roles[i % len(roles)])
    attrs = dict(persona.get("attrs") or {})
    haystack = " ".join(
        str(value)
        for value in (
            persona.get("role_key"),
            persona.get("role_label"),
            persona.get("persona_text"),
            attrs.get("occupation"),
            attrs.get("hobbies_and_interests"),
            attrs.get("district"),
            attrs.get("province"),
            attrs.get("region"),
            attrs.get("values"),
            attrs.get("career_goals_and_ambitions"),
        )
        if value
    ).lower()
    scored = []
    for idx, role in enumerate(scenario_roles):
        role_tokens = role_tokens_from(role)
        overlap = sum(1 for token in role_tokens if token and token in haystack)
        stable = stable_unit(f"{persona.get('persona_id') or i}:{role}")
        scored.append((overlap, stable, -idx, role))
    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return str(scored[0][3])
    return str(scenario_roles[i % len(scenario_roles)])


def choose_scenario_zone_index(
    *,
    persona: dict[str, Any],
    role_key: str,
    region_label: str,
    zone_count: int,
    region_zone_map: dict[str, int],
    scenario_zones: list[str],
    i: int,
) -> int:
    if zone_count <= 0:
        return 0
    if region_label in region_zone_map:
        return int(region_zone_map[region_label]) % zone_count
    if not scenario_zones:
        return i % zone_count
    attrs = dict(persona.get("attrs") or {})
    haystack = " ".join(
        str(value)
        for value in (
            role_key,
            persona.get("persona_text"),
            attrs.get("occupation"),
            attrs.get("district"),
            attrs.get("province"),
            attrs.get("region"),
            attrs.get("values"),
            attrs.get("career_goals_and_ambitions"),
        )
        if value
    ).lower()
    scored = []
    for idx, zone in enumerate(scenario_zones[:zone_count]):
        tokens = role_tokens_from(zone)
        overlap = sum(1 for token in tokens if token and token in haystack)
        scored.append((overlap, stable_unit(f"{role_key}:{zone}:{i}"), -idx, idx))
    scored.sort(reverse=True)
    if scored and scored[0][0] > 0:
        return int(scored[0][3]) % zone_count
    return int((stable_unit(f"{role_key}:{persona.get('persona_id') or i}") * zone_count)) % zone_count


def actor_name(persona: dict[str, Any], *, attrs: dict[str, Any], i: int) -> str:
    for key in ("name", "full_name", "person_name", "agent_name", "display_name"):
        value = str(attrs.get(key) or persona.get(key) or "").strip()
        if value:
            return value.split("(")[0].strip()[:24]
    seed = str(persona.get("persona_id") or persona.get("persona_text") or attrs.get("occupation") or f"agent-{i}")
    family = KOREAN_FAMILY_NAMES[int(stable_unit(seed) * len(KOREAN_FAMILY_NAMES)) % len(KOREAN_FAMILY_NAMES)]
    given = KOREAN_GIVEN_NAMES[int(stable_unit(f"{seed}:given:{i}") * len(KOREAN_GIVEN_NAMES)) % len(KOREAN_GIVEN_NAMES)]
    return f"{family}{given}"


def identity_summary(
    *,
    name: str,
    role: str,
    persona_text: str,
    attrs: dict[str, Any],
    zone_label: str,
) -> str:
    district = str(attrs.get("district") or attrs.get("province") or attrs.get("region") or zone_label or "").strip()
    occupation = str(attrs.get("occupation") or role or "").strip()
    values = str(attrs.get("values") or "").strip()
    pieces = [f"{name}({role})"]
    if occupation and occupation != role:
        pieces.append(occupation)
    if district:
        pieces.append(district)
    if values:
        pieces.append(values[:40])
    if persona_text:
        pieces.append(" ".join(persona_text.split())[:90])
    return " · ".join(piece for piece in pieces if piece)


def motive_pair(*, role: str, occupation: str, persona_text: str) -> tuple[str, str]:
    haystack = f"{role} {occupation} {persona_text}".lower()
    if any(token in haystack for token in ("임차", "세입", "저소득", "소비자")):
        return "생활비와 선택권을 지키며 주변 사람들의 반응을 확인한다.", "비용 부담이 혼자에게 전가되고 목소리가 묻히는 상황을 두려워한다."
    if any(token in haystack for token in ("기업", "임대", "사업", "자영업", "상점")):
        return "수익성과 평판을 동시에 지키며 정책 변화에 적응한다.", "규제나 여론 압력으로 생존 전략이 막히는 상황을 두려워한다."
    if any(token in haystack for token in ("정부", "정책", "규제", "행정")):
        return "갈등을 관리하며 정책 신뢰와 실행 가능성을 확보한다.", "현장 반발이 커져 정책 정당성이 흔들리는 상황을 두려워한다."
    if any(token in haystack for token in ("노동", "고용", "구직")):
        return "일자리 안정과 협상력을 확보하기 위해 동료 신호를 모은다.", "변화 비용이 노동자에게 집중되는 상황을 두려워한다."
    return "자신의 위치에서 유리한 신호를 찾고 가까운 관계망과 판단을 조율한다.", "사회장의 압력이 커질 때 고립되거나 잘못된 선택을 하는 것을 두려워한다."


def speech_style(attrs: dict[str, Any], *, role: str) -> str:
    text = f"{role} {attrs.get('occupation', '')} {attrs.get('education_level', '')}".lower()
    if any(token in text for token in ("정부", "정책", "행정", "분석", "박사", "석사")):
        return "근거와 조건을 따져 말하는 분석적 말투"
    if any(token in text for token in ("상점", "자영업", "소비자", "시민", "노동")):
        return "생활 경험과 주변 반응을 섞어 말하는 구체적 말투"
    return "조심스럽지만 이해관계가 걸리면 분명해지는 말투"


def relationship_bias(attrs: dict[str, Any], *, role: str) -> str:
    text = f"{role} {attrs.get('hobbies_and_interests', '')} {attrs.get('values', '')}".lower()
    if any(token in text for token in ("community", "봉사", "협력", "volunteer")):
        return "cooperative"
    if any(token in text for token in ("기업", "투자", "규제", "정부")):
        return "strategic"
    return "local-trust"


def role_tokens_from(value: Any) -> list[str]:
    return [token.lower() for token in re.findall(r"[A-Za-z가-힣0-9]{2,}", str(value or ""))]


def stable_unit(value: Any) -> float:
    raw = str(value or "")
    if not raw:
        return 0.5
    total = sum((idx + 1) * ord(ch) for idx, ch in enumerate(raw))
    return (total % 10007) / 10007.0
