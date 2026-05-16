"""Compact interaction event DTOs shared by live stream and snapshot APIs."""
from __future__ import annotations

from app.models.cell import Cell


def compact_interaction_events(cell: Cell, *, limit: int = 3) -> list[dict]:
    events: list[dict] = []
    for item in reversed(cell.behavior_log[-10:]):
        if str(item.get("event_type") or "") != "social_observation":
            continue
        payload = dict(item.get("payload") or {})
        neighbor_ids = [str(value) for value in list(payload.get("neighbor_ids") or [])[:3] if str(value)]
        if not neighbor_ids:
            continue
        alignment = str(payload.get("alignment") or "neutral")
        event_type = interaction_event_type(alignment=alignment, payload=payload)
        events.append(
            {
                "type": event_type,
                "source_id": cell.cell_id,
                "target_ids": neighbor_ids,
                "t": float(item.get("t") or cell.t),
                "alignment": alignment,
                "cluster_signal": str(payload.get("cluster_signal") or ""),
                "quality": round(float(item.get("quality_score") or payload.get("quality_score") or 0.0), 4),
                "summary": str(payload.get("micro_utterance") or item.get("summary") or "")[:220],
                "target_label": str(payload.get("primary_target_label") or ""),
                "intensity": round(float(payload.get("consultation_intensity") or item.get("quality_score") or 0.0), 4),
            }
        )
        if len(events) >= limit:
            break
    return list(reversed(events))


def interaction_event_type(*, alignment: str, payload: dict) -> str:
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
