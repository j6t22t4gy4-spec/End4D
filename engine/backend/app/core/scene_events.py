"""Build compact intra-t scene events for live playback and snapshot replay.

The simulation still advances in discrete t steps. These events describe the
meaningful beats inside that step so the UI can replay a t as a short scene
sequence instead of a single hard jump.
"""
from __future__ import annotations

from typing import Any

from app.models.cell import Cell


MAX_SCENES_PER_T = 12


def build_intra_t_scene_events(
    cells: list[Cell],
    *,
    current_t: float,
    next_t: float,
    internal_interactions: int,
    group_state: dict[str, Any] | None = None,
    limit: int = MAX_SCENES_PER_T,
) -> list[dict[str, Any]]:
    """Return top-K narrative/visual beats for one t interval."""
    if not cells or limit <= 0:
        return []

    events: list[dict[str, Any]] = []
    events.extend(_interaction_scenes(cells, current_t=current_t, next_t=next_t, limit=max(4, limit - 2)))
    events.extend(_pressure_scenes(group_state or {}, current_t=current_t, next_t=next_t, start_index=len(events)))

    events = sorted(
        events,
        key=lambda item: (
            -float(item.get("salience", 0.0) or 0.0),
            float(item.get("scene_index", 0) or 0),
            str(item.get("scene_id") or ""),
        ),
    )[:limit]
    events = sorted(events, key=lambda item: float(item.get("scene_progress", 0.0) or 0.0))
    scene_count = len(events)
    for idx, event in enumerate(events, start=1):
        event["scene_index"] = idx
        event["scene_count"] = scene_count
        event["internal_interactions"] = int(max(1, internal_interactions))
    return events


def compute_scene_quality_metrics(
    scene_events: list[dict[str, Any]],
    cells: list[Cell],
    *,
    current_t: float,
    next_t: float,
) -> dict[str, Any]:
    """Summarize whether a t interval had enough visible social development."""
    agent_ids = {cell.cell_id for cell in cells}
    participants: set[str] = set()
    relationship_events = 0
    hostile_events = 0
    positive_events = 0
    pressure_sum = 0.0
    sorted_events = sorted(scene_events, key=lambda item: float(item.get("scene_progress", 0.0) or 0.0))
    previous_progress: float | None = None
    gaps: list[float] = []
    for event in sorted_events:
        source_id = str(event.get("source_id") or "")
        if source_id in agent_ids:
            participants.add(source_id)
        for target_id in event.get("target_ids") or []:
            target_id = str(target_id)
            if target_id in agent_ids:
                participants.add(target_id)
        if event.get("scene_type") == "interaction":
            relationship_events += 1
        interaction_type = str(event.get("interaction_type") or "")
        if interaction_type == "hostile":
            hostile_events += 1
        if interaction_type == "positive":
            positive_events += 1
        pressure_sum += abs(float(event.get("pressure_delta") or 0.0))
        progress = float(event.get("scene_progress", 0.0) or 0.0)
        if previous_progress is not None:
            gaps.append(max(0.0, progress - previous_progress))
        previous_progress = progress

    scenes_per_t = len(scene_events)
    participation = len(participants) / max(1, len(agent_ids))
    dead_timestep = 1.0 if scenes_per_t == 0 or relationship_events == 0 else 0.0
    max_gap = max(gaps) if gaps else (1.0 if scenes_per_t <= 1 else 0.0)
    continuity = max(
        0.0,
        min(
            1.0,
            0.34 * min(1.0, scenes_per_t / 8.0)
            + 0.28 * min(1.0, participation / 0.35)
            + 0.22 * min(1.0, relationship_events / 6.0)
            + 0.16 * (1.0 - min(1.0, max_gap)),
        ),
    )
    return {
        "t": float(next_t),
        "start_t": float(current_t),
        "scenes_per_t": scenes_per_t,
        "agent_participation_rate": round(participation, 4),
        "relationship_event_count": relationship_events,
        "hostile_event_count": hostile_events,
        "positive_event_count": positive_events,
        "dead_timestep_rate": dead_timestep,
        "narrative_continuity_score": round(continuity, 4),
        "pressure_delta_abs_sum": round(pressure_sum, 4),
    }


def _interaction_scenes(
    cells: list[Cell],
    *,
    current_t: float,
    next_t: float,
    limit: int,
) -> list[dict[str, Any]]:
    cell_index = {cell.cell_id: cell for cell in cells}
    raw: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for cell in cells:
        for item in reversed(cell.behavior_log[-8:]):
            if str(item.get("event_type") or "") != "social_observation":
                continue
            payload = dict(item.get("payload") or {})
            target_ids = [str(value) for value in list(payload.get("neighbor_ids") or [])[:3] if str(value)]
            if not target_ids:
                continue
            target_id = target_ids[0]
            event_type = _interaction_type(payload)
            key = (str(cell.cell_id), target_id, event_type)
            if key in seen:
                continue
            seen.add(key)
            source = cell_index.get(cell.cell_id, cell)
            target = cell_index.get(target_id)
            quality = float(item.get("quality_score") or payload.get("quality_score") or 0.0)
            scene_t = _clamp(float(item.get("t") or next_t), float(current_t), float(next_t))
            progress = _progress(current_t=current_t, next_t=next_t, scene_t=scene_t)
            raw.append(
                {
                    "scene_id": f"scene-{_safe_t(next_t)}-{len(raw) + 1}",
                    "t": float(next_t),
                    "start_t": float(current_t),
                    "scene_t": scene_t,
                    "scene_progress": progress,
                    "scene_type": "interaction",
                    "interaction_type": event_type,
                    "source_id": source.cell_id,
                    "source_label": _agent_label(source),
                    "target_ids": target_ids,
                    "target_label": _agent_label(target) if target is not None else target_id,
                    "group_ids": _groups_for(source, target),
                    "summary": _interaction_summary(source, target, event_type, payload),
                    "narrative_reason": _interaction_reason(source, target, event_type, payload),
                    "scenario_relevance": _scenario_relevance(source, target),
                    "agent_context": {
                        "source": _agent_context(source),
                        "target": _agent_context(target),
                    },
                    "sentiment": _sentiment(event_type),
                    "pressure_delta": _pressure_delta(payload, event_type, quality),
                    "relationship_delta": _relationship_delta(event_type, quality),
                    "visual_hint": {
                        "kind": "arc",
                        "color_role": event_type,
                        "pulse": quality >= 0.62,
                    },
                    "salience": round(quality + (0.2 if event_type in {"hostile", "negative"} else 0.0), 4),
                }
            )
            if len(raw) >= limit * 2:
                break
        if len(raw) >= limit * 2:
            break
    return sorted(raw, key=lambda item: float(item.get("salience", 0.0) or 0.0), reverse=True)[:limit]


def _pressure_scenes(
    group_state: dict[str, Any],
    *,
    current_t: float,
    next_t: float,
    start_index: int,
) -> list[dict[str, Any]]:
    groups = list((group_state.get("groups") or {}).values()) if isinstance(group_state, dict) else []
    if not groups:
        return []
    top = sorted(
        groups,
        key=lambda group: (
            float(group.get("fracture_risk", 0.0) or 0.0)
            + float(group.get("tension", 0.0) or 0.0)
            + float(group.get("avg_collective_pressure", group.get("pressure", 0.0)) or 0.0)
        ),
        reverse=True,
    )[:2]
    events: list[dict[str, Any]] = []
    for idx, group in enumerate(top, start=1):
        pressure = float(group.get("avg_collective_pressure", group.get("pressure", 0.0)) or 0.0)
        tension = float(group.get("tension", 0.0) or 0.0)
        fracture = float(group.get("fracture_risk", 0.0) or 0.0)
        progress = min(0.94, 0.72 + idx * 0.1)
        events.append(
            {
                "scene_id": f"scene-{_safe_t(next_t)}-pressure-{start_index + idx}",
                "t": float(next_t),
                "start_t": float(current_t),
                "scene_t": float(current_t) + (float(next_t) - float(current_t)) * progress,
                "scene_progress": progress,
                "scene_type": "pressure_shift",
                "interaction_type": _pressure_type(pressure=pressure, tension=tension, fracture=fracture),
                "source_id": str(group.get("group_id") or group.get("id") or ""),
                "source_label": str(group.get("group_label") or group.get("label") or "Group"),
                "target_ids": [],
                "target_label": "",
                "group_ids": [str(group.get("group_id") or group.get("id") or "")],
                "summary": _pressure_summary(group, pressure=pressure, tension=tension, fracture=fracture),
                "sentiment": "risk" if fracture >= 0.45 or tension >= 0.45 else "neutral",
                "pressure_delta": round(max(pressure, tension, fracture) * 0.16, 4),
                "relationship_delta": 0.0,
                "visual_hint": {
                    "kind": "field",
                    "color_role": "pressure",
                    "intensity": round(max(pressure, tension, fracture), 4),
                },
                "salience": round(max(pressure, tension, fracture), 4),
            }
        )
    return events


def _interaction_type(payload: dict[str, Any]) -> str:
    alignment = str(payload.get("alignment") or "neutral")
    cluster_signal = str(payload.get("cluster_signal") or "")
    thought_similarity = float(payload.get("thought_similarity") or 0.0)
    worldview_similarity = float(payload.get("worldview_similarity") or 0.0)
    if alignment == "ally":
        return "positive"
    if alignment == "tension":
        return "hostile"
    if alignment == "mixed":
        return "negative"
    if cluster_signal == "ideological_tension" or min(thought_similarity, worldview_similarity) < -0.08:
        return "hostile"
    if min(thought_similarity, worldview_similarity) < -0.02:
        return "negative"
    return "dialogue"


def _interaction_summary(source: Cell, target: Cell | None, event_type: str, payload: dict[str, Any]) -> str:
    source_label = _agent_label(source)
    target_label = _agent_label(target) if target is not None else "주변 행위자"
    source_stance = _agent_stance(source)
    target_stance = _agent_stance(target)
    scenario = _scenario_relevance(source, target)
    pressure = _pressure_phrase(source, target)
    if event_type == "positive":
        verb = "협력 가능성을 확인"
    elif event_type == "negative":
        verb = "이해관계 차이를 드러냄"
    elif event_type == "hostile":
        verb = "높은 긴장 속에서 충돌 신호를 남김"
    else:
        verb = "상황 정보를 교환하며 다음 선택을 탐색"
    cluster = str(payload.get("cluster_signal") or "")
    fragments = [f"{source_label}와 {target_label}이 {verb}"]
    if source_stance:
        fragments.append(f"{source_label} 쪽 맥락: {source_stance}")
    if target_stance and target_stance != source_stance:
        fragments.append(f"{target_label} 쪽 맥락: {target_stance}")
    if scenario:
        fragments.append(f"시나리오 연결: {scenario}")
    if pressure:
        fragments.append(f"압력 배경: {pressure}")
    if cluster:
        fragments.append(f"신호: {cluster}")
    return " · ".join(_compact_fragment(fragment, 120) for fragment in fragments if fragment)


def _interaction_reason(source: Cell, target: Cell | None, event_type: str, payload: dict[str, Any]) -> str:
    source_reason = _recent_action_or_thought(source)
    target_reason = _recent_action_or_thought(target)
    belief_shift = abs(float(payload.get("belief_shift") or 0.0))
    if event_type == "positive":
        outcome = "공통 이해관계가 커져 협력 쪽으로 기울었습니다"
    elif event_type == "hostile":
        outcome = "신념 차이와 압력 신호가 겹치며 갈등이 증폭됐습니다"
    elif event_type == "negative":
        outcome = "서로의 우선순위가 어긋나며 조정 비용이 커졌습니다"
    else:
        outcome = "불확실성을 줄이기 위해 정보를 교환했습니다"
    details = [outcome]
    if source_reason:
        details.append(f"source: {source_reason}")
    if target_reason and target_reason != source_reason:
        details.append(f"target: {target_reason}")
    if belief_shift >= 0.08:
        details.append(f"belief shift {belief_shift:.2f}")
    return " · ".join(_compact_fragment(detail, 120) for detail in details)


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


def _agent_label(cell: Cell | None) -> str:
    if cell is None:
        return "agent"
    return str(cell.role_label or cell.role_key or cell.persona_id or cell.cell_id or "agent")


def _agent_context(cell: Cell | None) -> dict[str, Any]:
    if cell is None:
        return {}
    action = dict(cell.action_state or {})
    attrs = dict(cell.persona_attrs or {})
    return {
        "role": _agent_label(cell),
        "zone": str(cell.zone_label or cell.zone_id or ""),
        "persona": _persona_phrase(cell),
        "thought": _compact_fragment(str(action.get("last_thought_summary") or ""), 180),
        "action": _compact_fragment(str(action.get("last_action_summary") or action.get("strategy_summary") or ""), 180),
        "policy_sensitivity": round(float(action.get("policy_sensitivity", 0.0) or 0.0), 3),
        "collective_pressure": round(float(action.get("collective_pressure", 0.0) or 0.0), 3),
        "district": str(attrs.get("district") or attrs.get("region") or attrs.get("province") or ""),
    }


def _agent_stance(cell: Cell | None) -> str:
    if cell is None:
        return ""
    action = dict(cell.action_state or {})
    thought = str(action.get("last_thought_summary") or "").strip()
    action_summary = str(action.get("last_action_summary") or action.get("strategy_summary") or "").strip()
    persona = _persona_phrase(cell)
    if thought and action_summary:
        return _compact_fragment(f"{persona}; 생각={thought}; 행동={action_summary}", 190)
    if action_summary:
        return _compact_fragment(f"{persona}; 행동={action_summary}", 170)
    if thought:
        return _compact_fragment(f"{persona}; 생각={thought}", 170)
    return _compact_fragment(persona, 140)


def _persona_phrase(cell: Cell | None) -> str:
    if cell is None:
        return ""
    attrs = dict(cell.persona_attrs or {})
    parts = [
        str(attrs.get("occupation") or cell.role_label or cell.role_key or "").strip(),
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


def _scenario_relevance(source: Cell | None, target: Cell | None) -> str:
    for cell in (source, target):
        if cell is None:
            continue
        attrs = dict(cell.persona_attrs or {})
        scenario = str(attrs.get("scenario_prompt") or attrs.get("raw_prompt") or "").strip()
        if scenario:
            return _compact_fragment(scenario, 150)
    return ""


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
            phrases.append(f"{_agent_label(cell)} pressure {pressure:.2f}/tension {tension:.2f}/fracture {fracture:.2f}")
    return _compact_fragment("; ".join(phrases), 160)


def _recent_action_or_thought(cell: Cell | None) -> str:
    if cell is None:
        return ""
    action = dict(cell.action_state or {})
    for key in ("last_action_summary", "strategy_summary", "last_thought_summary", "action_reason", "persona_prior_summary"):
        value = str(action.get(key) or "").strip()
        if value:
            return _compact_fragment(value, 140)
    for item in reversed(list(cell.short_memory or [])[-4:]):
        value = str(item.get("summary") or "").strip()
        if value:
            return _compact_fragment(value, 140)
    return ""


def _compact_fragment(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _groups_for(source: Cell, target: Cell | None) -> list[str]:
    groups = [str(source.role_key or source.zone_id or "agent")]
    if target is not None:
        groups.append(str(target.role_key or target.zone_id or "agent"))
    return sorted({group for group in groups if group})


def _sentiment(event_type: str) -> str:
    if event_type == "positive":
        return "positive"
    if event_type == "hostile":
        return "hostile"
    if event_type == "negative":
        return "negative"
    return "neutral"


def _pressure_delta(payload: dict[str, Any], event_type: str, quality: float) -> float:
    sign = -1.0 if event_type == "positive" else 1.0 if event_type in {"negative", "hostile"} else 0.35
    shift = abs(float(payload.get("belief_shift") or 0.0))
    return round(sign * min(0.25, quality * 0.08 + shift * 0.4), 4)


def _relationship_delta(event_type: str, quality: float) -> float:
    sign = 1.0 if event_type == "positive" else -1.0 if event_type in {"negative", "hostile"} else 0.15
    return round(sign * min(0.25, max(0.02, quality * 0.12)), 4)


def _pressure_type(*, pressure: float, tension: float, fracture: float) -> str:
    if fracture >= 0.55 or tension >= 0.55:
        return "hostile"
    if fracture >= 0.35 or tension >= 0.35 or pressure >= 0.45:
        return "negative"
    return "dialogue"


def _progress(*, current_t: float, next_t: float, scene_t: float) -> float:
    span = max(1e-6, float(next_t) - float(current_t))
    return round(_clamp((float(scene_t) - float(current_t)) / span, 0.04, 0.96), 4)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_t(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "-")
