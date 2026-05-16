"""Live micro-beat scene events for intra-t consultation playback.

These events are intentionally cheaper and denser than review-grade scene
selection. They are the visible "conversation strokes" inside one t: short,
ordered source -> target beats that make the social field feel alive while the
deeper 3-layer commit waits for the t boundary.
"""
from __future__ import annotations

from typing import Any

from app.core.scene_narrator import render_consultation_scene
from app.models.cell import Cell


def build_microbeat_consultation_events(
    cells: list[Cell],
    *,
    current_t: float,
    next_t: float,
    scene_t: float,
    beat_index: int,
    beat_count: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return ordered, low-cost source -> target consultation beats."""
    if not cells or limit <= 0:
        return []
    cell_index = {cell.cell_id: cell for cell in cells}
    candidates: list[tuple[float, str, dict[str, Any]]] = []
    for cell in cells:
        event = _latest_consultation_event(cell, scene_t=scene_t)
        if not event:
            continue
        payload = dict(event.get("payload") or {})
        target_ids = [str(value) for value in list(payload.get("neighbor_ids") or [])[:4] if str(value)]
        if not target_ids:
            primary = str(payload.get("primary_target_id") or "")
            target_ids = [primary] if primary else []
        if not target_ids:
            continue
        quality = float(event.get("quality_score") or payload.get("quality_score") or 0.0)
        action = dict(cell.action_state or {})
        pressure = float(action.get("collective_pressure", 0.0) or 0.0)
        decision = float(action.get("decision_pressure_delta", 0.0) or 0.0)
        score = quality + pressure * 0.24 + decision * 0.18
        candidates.append((score, cell.cell_id, {"cell": cell, "payload": payload, "target_ids": target_ids, "quality": quality}))

    candidates.sort(key=lambda item: (-item[0], item[1]))
    events: list[dict[str, Any]] = []
    for _, _, item in candidates[: max(limit * 2, limit)]:
        source: Cell = item["cell"]
        payload = dict(item["payload"])
        quality = float(item["quality"])
        event_type = _interaction_type(payload)
        for target_offset, target_id in enumerate(item["target_ids"][:4]):
            target = cell_index.get(target_id)
            progress = _beat_progress(
                beat_index=beat_index,
                beat_count=beat_count,
                target_offset=target_offset,
            )
            narrative = render_consultation_scene(
                source=source,
                target=target,
                event_type=event_type,
                payload=payload,
            )
            events.append(
                {
                    "scene_id": f"microbeat-{_safe_t(next_t)}-{beat_index + 1}-{len(events) + 1}",
                    "stream_episode_id": f"t{_safe_t(next_t)}-mirofish-stream",
                    "stream_session_id": f"t{_safe_t(next_t)}-mirofish-stream",
                    "stream_round_index": int(beat_index) + 1,
                    "stream_round_count": int(max(1, beat_count)),
                    "stream_event_index": int(len(events)) + 1,
                    "session_index": int(beat_index) + 1,
                    "session_count": int(max(1, beat_count)),
                    "session_event_index": int(len(events)) + 1,
                    "t_composition_role": "mirofish_style_stream_episode",
                    "t": float(next_t),
                    "start_t": float(current_t),
                    "scene_t": float(scene_t),
                    "scene_progress": progress,
                    "scene_type": "consultation",
                    "interaction_type": event_type,
                    "source_id": source.cell_id,
                    "target_ids": [target_id],
                    "group_ids": _groups_for(source, target),
                    "pressure_delta": _pressure_delta(payload, event_type, quality),
                    "relationship_delta": _relationship_delta(event_type, quality),
                    "visual_hint": {
                        "kind": "microbeat_arc",
                        "color_role": event_type,
                        "pulse": True,
                        "intensity": round(max(0.28, min(1.0, quality)), 4),
                    },
                    "salience": round(quality + (0.18 if event_type in {"hostile", "negative"} else 0.06), 4),
                    "live_computed": True,
                    "stream_phase": "micro_consultation",
                    "beat_index": int(beat_index),
                    "beat_count": int(max(1, beat_count)),
                    **narrative,
                }
            )
            if len(events) >= limit:
                return events
    return events


def _latest_consultation_event(cell: Cell, *, scene_t: float) -> dict[str, Any] | None:
    for item in reversed(list(cell.behavior_log or [])[-6:]):
        if str(item.get("event_type") or "") != "social_observation":
            continue
        try:
            if abs(float(item.get("t") or 0.0) - float(scene_t)) > 1e-4:
                continue
        except (TypeError, ValueError):
            continue
        return dict(item)
    return None


def _beat_progress(*, beat_index: int, beat_count: int, target_offset: int) -> float:
    count = max(1, int(beat_count))
    base = (int(beat_index) + 1) / count
    offset = min(0.018, max(0, int(target_offset)) * 0.012)
    return max(0.035, min(0.965, round(base + offset, 4)))


def _interaction_type(payload: dict[str, Any]) -> str:
    alignment = str(payload.get("alignment") or "neutral")
    thought = float(payload.get("thought_similarity") or 0.0)
    worldview = float(payload.get("worldview_similarity") or 0.0)
    if alignment == "ally":
        return "positive"
    if alignment == "tension":
        return "hostile"
    if alignment == "mixed":
        return "negative"
    if min(thought, worldview) < -0.08:
        return "hostile"
    if min(thought, worldview) < -0.02:
        return "negative"
    return "dialogue"


def _pressure_delta(payload: dict[str, Any], event_type: str, quality: float) -> float:
    sign = -1.0 if event_type == "positive" else 1.0 if event_type in {"negative", "hostile"} else 0.25
    shift = abs(float(payload.get("belief_shift") or 0.0))
    return round(sign * min(0.22, quality * 0.07 + shift * 0.34), 4)


def _relationship_delta(event_type: str, quality: float) -> float:
    sign = 1.0 if event_type == "positive" else -1.0 if event_type in {"negative", "hostile"} else 0.12
    return round(sign * min(0.22, max(0.018, quality * 0.10)), 4)


def _groups_for(source: Cell, target: Cell | None) -> list[str]:
    groups = [str(source.role_key or source.zone_id or "agent")]
    if target is not None:
        groups.append(str(target.role_key or target.zone_id or "agent"))
    return sorted({group for group in groups if group})


def _safe_t(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "-")
