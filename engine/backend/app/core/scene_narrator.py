"""Narrative rendering helpers for intra-t social field scenes.

Selector code decides *which* beats matter. This module decides how those
beats should be described for playback, review, and chat grounding.
"""
from __future__ import annotations

from typing import Any

from app.models.cell import Cell


def render_consultation_scene(
    *,
    source: Cell,
    target: Cell | None,
    event_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Return stable narrative fields for a source -> target consultation."""
    return {
        "source_label": agent_label(source),
        "target_label": agent_label(target) if target is not None else "주변 행위자",
        "summary": _consultation_summary(source, target, event_type, payload),
        "narrative_reason": _consultation_reason(source, target, event_type, payload),
        "scenario_relevance": scenario_relevance(source, target),
        "agent_context": {
            "source": agent_context(source),
            "target": agent_context(target),
        },
        "sentiment": sentiment(event_type),
    }


def render_pressure_scene(
    group: dict[str, Any],
    *,
    pressure: float,
    tension: float,
    fracture: float,
) -> dict[str, Any]:
    """Return stable narrative fields for a group pressure transition."""
    label = str(group.get("group_label") or group.get("label") or "Group")
    return {
        "source_label": label,
        "target_label": "",
        "summary": _pressure_summary(group, pressure=pressure, tension=tension, fracture=fracture),
        "sentiment": "risk" if fracture >= 0.45 or tension >= 0.45 else "neutral",
    }


def agent_label(cell: Cell | None) -> str:
    if cell is None:
        return "agent"
    attrs = dict(cell.persona_attrs or {})
    name = str(attrs.get("agent_name") or attrs.get("display_name") or "").strip()
    role = str(cell.role_label or cell.role_key or "agent").strip() or "agent"
    if name:
        return name if "(" in name else f"{name}({role})"
    return str(role or cell.persona_id or cell.cell_id or "agent")


def agent_context(cell: Cell | None) -> dict[str, Any]:
    if cell is None:
        return {}
    action = dict(cell.action_state or {})
    attrs = dict(cell.persona_attrs or {})
    return {
        "role": str(cell.role_label or cell.role_key or ""),
        "identity": agent_label(cell),
        "zone": str(cell.zone_label or cell.zone_id or ""),
        "persona": _persona_phrase(cell),
        "thought": _compact_fragment(str(action.get("last_thought_summary") or ""), 180),
        "action": _compact_fragment(str(action.get("last_action_summary") or action.get("strategy_summary") or ""), 180),
        "policy_sensitivity": round(float(action.get("policy_sensitivity", 0.0) or 0.0), 3),
        "collective_pressure": round(float(action.get("collective_pressure", 0.0) or 0.0), 3),
        "district": str(attrs.get("district") or attrs.get("region") or attrs.get("province") or ""),
    }


def scenario_relevance(source: Cell | None, target: Cell | None) -> str:
    for cell in (source, target):
        if cell is None:
            continue
        attrs = dict(cell.persona_attrs or {})
        scenario = str(attrs.get("scenario_prompt") or attrs.get("raw_prompt") or "").strip()
        if scenario:
            return _compact_fragment(scenario, 150)
    return ""


def sentiment(event_type: str) -> str:
    if event_type == "positive":
        return "positive"
    if event_type == "hostile":
        return "hostile"
    if event_type == "negative":
        return "negative"
    return "neutral"


def _consultation_summary(source: Cell, target: Cell | None, event_type: str, payload: dict[str, Any]) -> str:
    micro_utterance = str(payload.get("micro_utterance") or "").strip()
    if micro_utterance:
        return _compact_fragment(micro_utterance, 170)
    source_label = agent_label(source)
    target_label = agent_label(target) if target is not None else "주변 행위자"
    topic = _consultation_topic(source, target, payload)
    if event_type == "positive":
        return f"{source_label} → {target_label}: {topic}에 협력 신호를 보냄"
    if event_type == "hostile":
        return f"{source_label} → {target_label}: {topic}을 두고 강하게 충돌"
    if event_type == "negative":
        return f"{source_label} → {target_label}: {topic}에 이견을 전달"
    return f"{source_label} → {target_label}: {topic}을 짧게 확인"


def _consultation_reason(source: Cell, target: Cell | None, event_type: str, payload: dict[str, Any]) -> str:
    pressure = _pressure_phrase(source, target)
    cluster = str(payload.get("cluster_signal") or "").strip()
    belief_shift = abs(float(payload.get("belief_shift") or 0.0))
    if event_type == "positive":
        base = "공통 이해관계가 확인되어 다음 접촉 가능성이 올라갑니다."
    elif event_type == "hostile":
        base = "역할/신념 차이가 커져 관계 압력이 즉시 상승합니다."
    elif event_type == "negative":
        base = "목표는 비슷하지만 비용과 우선순위가 어긋납니다."
    else:
        base = "불확실성을 줄이기 위한 경량 협의입니다."
    details = [base]
    if pressure:
        details.append(pressure)
    if cluster:
        details.append(f"signal={cluster}")
    if belief_shift >= 0.08:
        details.append(f"shift={belief_shift:.2f}")
    return " · ".join(_compact_fragment(detail, 96) for detail in details)


def _consultation_topic(source: Cell, target: Cell | None, payload: dict[str, Any]) -> str:
    for cell in (source, target):
        if cell is None:
            continue
        action = dict(cell.action_state or {})
        for key in ("last_action_summary", "strategy_summary", "last_thought_summary"):
            value = str(action.get(key) or "").strip()
            if value and not _is_placeholder_summary(value):
                return _compact_fragment(value, 34)
        attrs = dict(cell.persona_attrs or {})
        for key in ("occupation", "identity_summary", "persona_summary"):
            value = str(attrs.get(key) or "").strip()
            if value:
                return _compact_fragment(value, 34)
    scenario = scenario_relevance(source, target)
    if scenario:
        return _compact_fragment(scenario, 34)
    return "현재 국면"


def _is_placeholder_summary(value: str) -> bool:
    raw = str(value or "").strip().lower()
    return raw in {"persona_seeded_initial_state", "adaptive planning", "current_state_reflection"}


def _pressure_summary(group: dict[str, Any], *, pressure: float, tension: float, fracture: float) -> str:
    label = str(group.get("group_label") or group.get("label") or "집단")
    drift = float(group.get("drift_velocity", 0.0) or 0.0)
    cohesion = float(group.get("cohesion", 0.0) or 0.0)
    if fracture >= 0.55:
        return f"{label} 내부의 분열 위험이 높아졌습니다. cohesion {cohesion:.2f}, tension {tension:.2f}, drift {drift:.2f}."
    if tension >= 0.45:
        return f"{label}의 긴장이 장면 후반부에 뚜렷해졌습니다. pressure {pressure:.2f}, fracture {fracture:.2f}."
    if pressure >= 0.45:
        return f"{label}에 집단 압력이 누적되고 있습니다. drift {drift:.2f}가 다음 선택을 흔듭니다."
    return f"{label}의 압력장이 완만하게 재정렬됩니다. cohesion {cohesion:.2f}, pressure {pressure:.2f}."


def _persona_phrase(cell: Cell | None) -> str:
    if cell is None:
        return ""
    attrs = dict(cell.persona_attrs or {})
    parts = [
        str(attrs.get("identity_summary") or attrs.get("occupation") or cell.role_label or cell.role_key or "").strip(),
        str(attrs.get("district") or attrs.get("province") or attrs.get("region") or cell.zone_label or "").strip(),
    ]
    age = attrs.get("age")
    if age not in (None, ""):
        parts.append(f"{age}세")
    values = attrs.get("values")
    if values:
        parts.append(str(values))
    text = ", ".join(part for part in parts if part)
    if text:
        return text
    return str(cell.persona_text or cell.persona_id or cell.cell_id or "")[:120]


def _pressure_phrase(source: Cell | None, target: Cell | None) -> str:
    phrases = []
    for cell in (source, target):
        if cell is None:
            continue
        action = dict(cell.action_state or {})
        pressure = float(action.get("collective_pressure", 0.0) or 0.0)
        tension = float(action.get("role_group_tension", action.get("zone_group_tension", 0.0)) or 0.0)
        fracture = float(action.get("role_group_fracture_risk", action.get("zone_group_fracture_risk", 0.0)) or 0.0)
        if max(pressure, tension, fracture) >= 0.18:
            phrases.append(f"{agent_label(cell)} pressure {pressure:.2f}/tension {tension:.2f}/fracture {fracture:.2f}")
    return _compact_fragment("; ".join(phrases), 160)


def _compact_fragment(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"
