"""Append-only social action records for live 4D simulation playback.

The social field should feel like activity is happening while t is running,
not like a finished snapshot is being animated afterward. Scene events remain
the narrative layer; action records are the compact source-of-truth activity
log that UI panels and replay can tail.

This is intentionally not a Twitter/Reddit clone. End4D's ledger records
changes in a 4D social field: contact, alignment, contestation, pressure,
drift, and deep cognition commits across x/y/z/t.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

END4D_ACTION_TYPES = {
    "FIELD_CONTACT": "agent senses another actor inside the same local social field",
    "FIELD_ALIGN": "agents move toward cooperation or shared stance",
    "FIELD_CONTEST": "agents push against each other due to incompatible pressure or worldview",
    "FIELD_NEGOTIATE": "agents expose disagreement but keep coordination possible",
    "FIELD_PRESSURE_SHIFT": "a role/zone/bloc pressure field changes",
    "FIELD_DRIFT": "a live frame shows spatial/social drift without a completed decision",
    "DEEP_COMMIT": "heavy t-boundary cognition commits the period into thought/action/worldview state",
}


def action_record_from_scene_event(scene_event: dict[str, Any]) -> dict[str, Any]:
    """Convert an intra-t scene event into a compact action-ledger record."""
    event = dict(scene_event or {})
    scene_type = str(event.get("scene_type") or "scene")
    interaction_type = str(event.get("interaction_type") or event.get("sentiment") or "dialogue")
    source_id = str(event.get("source_id") or "")
    source_label = str(event.get("source_label") or source_id or "field")
    target_ids = [str(item) for item in event.get("target_ids") or [] if str(item)]
    target_label = str(event.get("target_label") or ", ".join(target_ids) or "")
    scene_t = float(event.get("scene_t") or event.get("t") or 0.0)
    t_value = float(event.get("t") or scene_t)
    action_type = _action_type(scene_type=scene_type, interaction_type=interaction_type)
    field_axis = _field_axis(event)
    action_label = _action_label(action_type)
    record = {
        "record_id": str(event.get("scene_id") or f"action-{t_value:.2f}-{scene_t:.2f}"),
        "round_num": int(max(0, round(t_value))),
        "t": t_value,
        "scene_t": scene_t,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "platform": "social_field",
        "domain": "end4d_social_field",
        "field_axis": field_axis,
        "agent_id": source_id,
        "agent_name": source_label,
        "target_ids": target_ids,
        "target_label": target_label,
        "action_type": action_type,
        "action_label": action_label,
        "action_description": END4D_ACTION_TYPES.get(action_type, ""),
        "interaction_type": interaction_type,
        "action_args": {
            "scene_type": scene_type,
            "scene_index": event.get("scene_index"),
            "scene_count": event.get("scene_count"),
            "stream_phase": event.get("stream_phase"),
            "pressure_delta": event.get("pressure_delta"),
            "relationship_delta": event.get("relationship_delta"),
            "group_ids": list(event.get("group_ids") or []),
            "visual_hint": dict(event.get("visual_hint") or {}),
        },
        "result": str(event.get("summary") or ""),
        "reason": str(event.get("narrative_reason") or ""),
        "scenario_relevance": str(event.get("scenario_relevance") or ""),
        "interpretation": _interpretation(
            action_type=action_type,
            source_label=source_label,
            target_label=target_label,
            event=event,
        ),
        "success": True,
    }
    return {key: value for key, value in record.items() if value not in (None, "", [])}


def attach_action_record(scene_event: dict[str, Any]) -> dict[str, Any]:
    event = dict(scene_event or {})
    if "action_record" not in event:
        event["action_record"] = action_record_from_scene_event(event)
    return event


def _action_type(*, scene_type: str, interaction_type: str) -> str:
    if scene_type == "pressure_shift":
        return "FIELD_PRESSURE_SHIFT"
    if scene_type == "stream_frame":
        return "FIELD_DRIFT"
    if scene_type == "stream_phase":
        return "DEEP_COMMIT"
    if interaction_type == "positive":
        return "FIELD_ALIGN"
    if interaction_type == "hostile":
        return "FIELD_CONTEST"
    if interaction_type == "negative":
        return "FIELD_NEGOTIATE"
    return "FIELD_CONTACT"


def _action_label(action_type: str) -> str:
    labels = {
        "FIELD_CONTACT": "사회장 접촉",
        "FIELD_ALIGN": "정렬/협력",
        "FIELD_CONTEST": "대립/압력 충돌",
        "FIELD_NEGOTIATE": "협상/이견 조정",
        "FIELD_PRESSURE_SHIFT": "압력장 변화",
        "FIELD_DRIFT": "장 내부 이동",
        "DEEP_COMMIT": "t 경계 심층 커밋",
    }
    return labels.get(action_type, action_type.replace("_", " ").title())


def _field_axis(event: dict[str, Any]) -> str:
    scene_type = str(event.get("scene_type") or "")
    groups = [str(item) for item in event.get("group_ids") or [] if str(item)]
    if scene_type == "pressure_shift":
        return "macro"
    if any(item.startswith("zone:") for item in groups):
        return "zone"
    if any(item.startswith("role:") for item in groups):
        return "role"
    if event.get("target_ids"):
        return "agent"
    return "field"


def _interpretation(*, action_type: str, source_label: str, target_label: str, event: dict[str, Any]) -> str:
    pressure = float(event.get("pressure_delta") or 0.0)
    relation = float(event.get("relationship_delta") or 0.0)
    target = target_label or "주변 장"
    if action_type == "FIELD_ALIGN":
        return f"{source_label}와 {target}의 관계가 협력 방향으로 기울며 다음 장면의 압력 완충 가능성이 커집니다."
    if action_type == "FIELD_CONTEST":
        return f"{source_label}와 {target} 사이에서 대립 압력이 발생해 국소 사회장의 긴장이 상승합니다."
    if action_type == "FIELD_NEGOTIATE":
        return f"{source_label}와 {target}이 이견을 드러냈지만 관계 단절보다는 조정 국면에 머뭅니다."
    if action_type == "FIELD_PRESSURE_SHIFT":
        return f"집단 압력장이 재배치됩니다. pressure_delta={pressure:.3f}, relationship_delta={relation:.3f}."
    if action_type == "DEEP_COMMIT":
        return "t 내부 장면들이 누적되어 Thought/Action/Worldview 경계 상태로 커밋됩니다."
    if action_type == "FIELD_DRIFT":
        return "아직 결론이 나기 전, 위치·압력·접촉 가능성이 장 내부에서 계속 조정됩니다."
    return f"{source_label}가 {target}을 감지하며 다음 협의 가능성을 엽니다."
