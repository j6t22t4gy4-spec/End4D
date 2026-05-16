"""Build compact intra-t scene events for live playback and snapshot replay.

The simulation still advances in discrete t steps. These events describe the
meaningful beats inside that step so the UI can replay a t as a short scene
sequence instead of a single hard jump.
"""
from __future__ import annotations

from typing import Any

from app.core.scene_selector import MAX_SCENES_PER_T, select_scene_candidates
from app.models.cell import Cell


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
    return select_scene_candidates(
        cells,
        current_t=current_t,
        next_t=next_t,
        internal_interactions=internal_interactions,
        group_state=group_state,
        limit=limit,
    )


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
    narrative_specificity_values: list[float] = []
    scenario_linked_events = 0
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
        if event.get("scene_type") in {"interaction", "consultation"}:
            relationship_events += 1
        interaction_type = str(event.get("interaction_type") or "")
        if interaction_type == "hostile":
            hostile_events += 1
        if interaction_type == "positive":
            positive_events += 1
        pressure_sum += abs(float(event.get("pressure_delta") or 0.0))
        summary = str(event.get("summary") or "")
        reason = str(event.get("narrative_reason") or "")
        scenario = str(event.get("scenario_relevance") or "")
        specificity = min(1.0, (len(summary) + len(reason)) / 220.0)
        if event.get("source_label") and event.get("target_label"):
            specificity += 0.12
        if scenario:
            scenario_linked_events += 1
            specificity += 0.12
        narrative_specificity_values.append(min(1.0, specificity))
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
    specificity_score = _mean(narrative_specificity_values)
    scenario_link_rate = scenario_linked_events / max(1, scenes_per_t)
    quality_score = max(
        0.0,
        min(
            1.0,
            continuity * 0.42
            + specificity_score * 0.28
            + scenario_link_rate * 0.16
            + min(1.0, relationship_events / 6.0) * 0.14,
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
        "narrative_specificity_score": round(specificity_score, 4),
        "scenario_link_rate": round(scenario_link_rate, 4),
        "scene_quality_score": round(quality_score, 4),
        "scene_quality_grade": _quality_grade(quality_score),
        "quality_warnings": _quality_warnings(
            scenes_per_t=scenes_per_t,
            participation=participation,
            relationship_events=relationship_events,
            specificity_score=specificity_score,
            scenario_link_rate=scenario_link_rate,
        ),
        "pressure_delta_abs_sum": round(pressure_sum, 4),
    }


def _quality_grade(score: float) -> str:
    if score >= 0.78:
        return "strong"
    if score >= 0.58:
        return "usable"
    if score >= 0.36:
        return "thin"
    return "weak"


def _quality_warnings(
    *,
    scenes_per_t: int,
    participation: float,
    relationship_events: int,
    specificity_score: float,
    scenario_link_rate: float,
) -> list[str]:
    warnings: list[str] = []
    if scenes_per_t < 4:
        warnings.append("too_few_scenes")
    if participation < 0.12:
        warnings.append("low_agent_participation")
    if relationship_events < 2:
        warnings.append("weak_relationship_stream")
    if specificity_score < 0.42:
        warnings.append("generic_scene_text")
    if scenario_link_rate < 0.25:
        warnings.append("weak_scenario_link")
    return warnings[:4]


def _mean(values: list[float]) -> float:
    return float(sum(values) / len(values)) if values else 0.0
