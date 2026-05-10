"""Persistent peer-relationship helpers for dialogue-driven social dynamics."""
from __future__ import annotations

from typing import Any, Dict, List

from app.models.cell import Cell

RELATIONSHIP_LIMIT = 24


def summarize_relationship(cell: Cell, peer_id: str) -> str:
    state = dict(cell.relationship_state.get(peer_id) or {})
    if not state:
        return "no prior relationship"
    trust = float(state.get("trust", 0.0))
    tension = float(state.get("tension", 0.0))
    dialogue_count = int(state.get("dialogue_count", 0))
    alignment = float(state.get("alignment", 0.0))
    summary = str(state.get("last_summary") or "prior dialogue")
    return (
        f"dialogues={dialogue_count}, trust={trust:.2f}, tension={tension:.2f}, "
        f"alignment={alignment:.2f}, last={summary[:160]}"
    )


def relationship_score(cell: Cell, peer_id: str) -> float:
    state = dict(cell.relationship_state.get(peer_id) or {})
    if not state:
        return 0.0
    trust = float(state.get("trust", 0.0))
    tension = float(state.get("tension", 0.0))
    dialogue_count = min(1.0, int(state.get("dialogue_count", 0)) / 4.0)
    alignment = abs(float(state.get("alignment", 0.0)))
    recency_bonus = 0.06 if float(state.get("last_t", -1.0)) >= 0.0 else 0.0
    return trust * 0.55 + tension * 0.35 + dialogue_count * 0.15 + alignment * 0.1 + recency_bonus


def update_relationship(
    cell: Cell,
    peer_id: str,
    *,
    current_t: float,
    trust_delta: float,
    tension_delta: float,
    alignment_delta: float,
    summary: str,
) -> Cell:
    relationships = {
        str(existing_peer_id): dict(existing_state)
        for existing_peer_id, existing_state in cell.relationship_state.items()
    }
    state = dict(relationships.get(peer_id) or {})
    state["peer_id"] = peer_id
    state["trust"] = _clip01(float(state.get("trust", 0.0)) + trust_delta)
    state["tension"] = _clip01(float(state.get("tension", 0.0)) + tension_delta)
    state["alignment"] = _signed(float(state.get("alignment", 0.0)) + alignment_delta)
    state["dialogue_count"] = int(state.get("dialogue_count", 0)) + 1
    state["last_t"] = float(current_t)
    state["last_summary"] = summary[:240]
    relationships[peer_id] = state
    relationships = _trim_relationships(relationships)
    return cell.copy(relationship_state=relationships)


def average_relationship_metrics(cells: List[Cell]) -> Dict[str, float]:
    trust_values: List[float] = []
    tension_values: List[float] = []
    repeat_peer_values: List[float] = []
    for cell in cells:
        relationships = list((cell.relationship_state or {}).values())
        if not relationships:
            continue
        trust_values.extend(float(item.get("trust", 0.0)) for item in relationships)
        tension_values.extend(float(item.get("tension", 0.0)) for item in relationships)
        repeat_peer_values.append(sum(1 for item in relationships if int(item.get("dialogue_count", 0)) >= 2))
    return {
        "avg_trust": _mean(trust_values),
        "avg_tension": _mean(tension_values),
        "repeat_peer_density": _mean(repeat_peer_values),
    }


def _trim_relationships(relationships: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    ranked = sorted(
        relationships.items(),
        key=lambda item: (
            -(
                float(item[1].get("trust", 0.0))
                + float(item[1].get("tension", 0.0))
                + min(1.0, int(item[1].get("dialogue_count", 0)) / 4.0)
            ),
            -float(item[1].get("last_t", -1.0)),
            item[0],
        ),
    )
    return {peer_id: dict(state) for peer_id, state in ranked[:RELATIONSHIP_LIMIT]}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _signed(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def _mean(values: List[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))
