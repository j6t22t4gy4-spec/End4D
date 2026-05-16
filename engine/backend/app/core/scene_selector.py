"""Select compact intra-t scene candidates for playback.

This module intentionally stays free of review scoring. It only chooses the
beats that should be visible in a t interval and delegates wording to the
narrator.
"""
from __future__ import annotations

from typing import Any

from app.core.scene_narrator import render_consultation_scene, render_pressure_scene
from app.models.cell import Cell


MAX_SCENES_PER_T = 24


def select_scene_candidates(
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
    events.extend(_interaction_scenes(cells, current_t=current_t, next_t=next_t, limit=max(6, limit - 3)))
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
    max_candidates = max(limit * 3, limit)
    for cell in cells:
        for item in reversed(cell.behavior_log[-8:]):
            if str(item.get("event_type") or "") != "social_observation":
                continue
            payload = dict(item.get("payload") or {})
            target_ids = [str(value) for value in list(payload.get("neighbor_ids") or [])[:3] if str(value)]
            if not target_ids:
                continue
            event_type = _interaction_type(payload)
            quality = float(item.get("quality_score") or payload.get("quality_score") or 0.0)
            scene_t = _clamp(float(item.get("t") or next_t), float(current_t), float(next_t))
            source = cell_index.get(cell.cell_id, cell)
            for target_offset, target_id in enumerate(target_ids[:2]):
                key = (str(cell.cell_id), target_id, event_type)
                if key in seen:
                    continue
                seen.add(key)
                target = cell_index.get(target_id)
                target_quality = max(0.0, quality - target_offset * 0.06)
                progress = min(
                    0.96,
                    _progress(current_t=current_t, next_t=next_t, scene_t=scene_t) + target_offset * 0.014,
                )
                narrative = render_consultation_scene(
                    source=source,
                    target=target,
                    event_type=event_type,
                    payload=payload,
                )
                raw.append(
                    {
                        "scene_id": f"scene-{_safe_t(next_t)}-{len(raw) + 1}",
                        "t": float(next_t),
                        "start_t": float(current_t),
                        "scene_t": scene_t,
                        "scene_progress": progress,
                        "scene_type": "consultation",
                        "interaction_type": event_type,
                        "source_id": source.cell_id,
                        "target_ids": [target_id],
                        "group_ids": _groups_for(source, target),
                        "pressure_delta": _pressure_delta(payload, event_type, target_quality),
                        "relationship_delta": _relationship_delta(event_type, target_quality),
                        "visual_hint": {
                            "kind": "arc",
                            "color_role": event_type,
                            "pulse": target_quality >= 0.56,
                        },
                        "salience": round(
                            target_quality
                            + (0.2 if event_type in {"hostile", "negative"} else 0.0)
                            + (0.03 if target_offset == 0 else 0.0),
                            4,
                        ),
                        **narrative,
                    }
                )
                if len(raw) >= max_candidates:
                    break
            if len(raw) >= max_candidates:
                break
        if len(raw) >= max_candidates:
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
    )[:3]
    events: list[dict[str, Any]] = []
    for idx, group in enumerate(top, start=1):
        pressure = float(group.get("avg_collective_pressure", group.get("pressure", 0.0)) or 0.0)
        tension = float(group.get("tension", 0.0) or 0.0)
        fracture = float(group.get("fracture_risk", 0.0) or 0.0)
        progress = min(0.95, 0.66 + idx * 0.085)
        narrative = render_pressure_scene(group, pressure=pressure, tension=tension, fracture=fracture)
        group_id = str(group.get("group_id") or group.get("id") or "")
        events.append(
            {
                "scene_id": f"scene-{_safe_t(next_t)}-pressure-{start_index + idx}",
                "t": float(next_t),
                "start_t": float(current_t),
                "scene_t": float(current_t) + (float(next_t) - float(current_t)) * progress,
                "scene_progress": progress,
                "scene_type": "pressure_shift",
                "interaction_type": _pressure_type(pressure=pressure, tension=tension, fracture=fracture),
                "source_id": group_id,
                "target_ids": [],
                "group_ids": [group_id],
                "pressure_delta": round(max(pressure, tension, fracture) * 0.16, 4),
                "relationship_delta": 0.0,
                "visual_hint": {
                    "kind": "field",
                    "color_role": "pressure",
                    "intensity": round(max(pressure, tension, fracture), 4),
                },
                "salience": round(max(pressure, tension, fracture), 4),
                **narrative,
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


def _groups_for(source: Cell, target: Cell | None) -> list[str]:
    groups = [str(source.role_key or source.zone_id or "agent")]
    if target is not None:
        groups.append(str(target.role_key or target.zone_id or "agent"))
    return sorted({group for group in groups if group})


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_t(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "-")
