"""Agent-to-agent interaction memory for the engine data flywheel.

This layer does not add chatbot/user interaction. It lets cells periodically
observe nearby agents and write compact social experience into memory, which
then feeds Thought/Worldview embedding updates.
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.core.belief_dynamics import apply_belief_update
from app.core.coordinates import cosine_similarity, distance_4d
from app.core.interaction_quality import evaluate_interaction_quality
from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.spatial_index import SpatialHashGrid
from app.models.cell import Cell

SOCIAL_INTERACTION_INTERVAL = 10
SOCIAL_RADIUS = 4.0
MAX_NEIGHBORS_PER_CELL = 3
THOUGHT_ALIGNMENT_THRESHOLD = 0.35
WORLDVIEW_ALIGNMENT_THRESHOLD = 0.20


def _blend_unit(base: np.ndarray, target: np.ndarray, weight: float) -> np.ndarray:
    if base.size == 0:
        return base
    out = (1.0 - weight) * base + weight * target
    norm = float(np.linalg.norm(out))
    if norm <= 1e-8:
        return out
    return out / norm


def _salient_memory(neighbor: Cell) -> str:
    for line in reversed(neighbor.memory[-5:]):
        if line.strip():
            return line.strip()
    return neighbor.persona_text[:160].strip() or "no_signal"


def apply_agent_interactions(
    cells: List[Cell],
    current_t: float,
    *,
    interval: int = SOCIAL_INTERACTION_INTERVAL,
    radius: float = SOCIAL_RADIUS,
    max_neighbors: int = MAX_NEIGHBORS_PER_CELL,
) -> List[Cell]:
    """Append nearby-agent observations to cell memory at a fixed interval."""
    t_int = int(current_t)
    if not cells or t_int <= 0 or t_int % interval != 0:
        return cells

    grid = SpatialHashGrid(cells, cell_size=radius)
    out: List[Cell] = []
    for cell in cells:
        candidates = [
            other
            for other in grid.candidate_cells(cell, radius)
            if other.cell_id != cell.cell_id and distance_4d(cell, other) <= radius
        ]
        candidates.sort(key=lambda other: distance_4d(cell, other))
        neighbors = candidates[:max_neighbors]
        if not neighbors:
            out.append(cell)
            continue

        role_counts: dict[str, int] = {}
        energy_sum = 0.0
        aligned: List[Cell] = []
        conflicted: List[Cell] = []
        for n in neighbors:
            role = n.role_label or n.role_key or "agent"
            role_counts[role] = role_counts.get(role, 0) + 1
            energy_sum += float(n.energy)
            thought_sim = cosine_similarity(cell.thought_vec, n.thought_vec)
            worldview_sim = cosine_similarity(cell.worldview_vec, n.worldview_vec)
            if (
                thought_sim >= THOUGHT_ALIGNMENT_THRESHOLD
                or worldview_sim >= WORLDVIEW_ALIGNMENT_THRESHOLD
            ):
                aligned.append(n)
            elif thought_sim < 0.0 or worldview_sim < -0.05:
                conflicted.append(n)

        roles = ", ".join(f"{role}:{count}" for role, count in sorted(role_counts.items()))
        avg_energy = energy_sum / len(neighbors)
        quality = evaluate_interaction_quality(cell, neighbors)
        if aligned and conflicted:
            alignment = "mixed"
        elif aligned:
            alignment = "ally"
        elif conflicted:
            alignment = "tension"
        else:
            alignment = "neutral"
        line = (
            f"t={t_int} social_observation neighbors={len(neighbors)} "
            f"roles=[{roles}] avg_neighbor_energy={avg_energy:.1f} alignment={alignment} "
            f"cluster_signal={quality['cluster_signal']} quality={quality['quality_score']:.2f}"
        )
        source_neighbor = aligned[0] if aligned else neighbors[0]

        thought_vec = cell.thought_vec
        worldview_vec = cell.worldview_vec
        if aligned:
            thought_target = np.mean([n.thought_vec for n in aligned], axis=0)
            worldview_target = np.mean([n.worldview_vec for n in aligned], axis=0)
            thought_vec = _blend_unit(cell.thought_vec, thought_target, 0.18)
            worldview_vec = _blend_unit(cell.worldview_vec, worldview_target, 0.08)
        elif conflicted:
            conflict_target = np.mean([n.thought_vec for n in conflicted], axis=0)
            thought_vec = _blend_unit(cell.thought_vec, -conflict_target, 0.10)

        belief = apply_belief_update(
            cell.copy(thought_vec=thought_vec, worldview_vec=worldview_vec),
            neighbors=neighbors,
            quality=quality,
            alignment=alignment,
        )
        thought_vec = belief["thought_vec"]
        worldview_vec = belief["worldview_vec"]

        updated = cell.copy(
            thought_vec=thought_vec,
            worldview_vec=worldview_vec,
        )
        observation_entry = memory_entry(
            t=float(t_int),
            kind="social_observation",
            summary=line,
            importance=float(quality["quality_score"]),
            source="engine.agent_interactions",
            payload={
                "alignment": alignment,
                "roles": roles,
                "avg_neighbor_energy": avg_energy,
                "cluster_signal": quality["cluster_signal"],
                "quality_score": quality["quality_score"],
                "belief_shift": belief["belief_shift"],
                "belief_polarity": belief["belief_polarity"],
            },
            tags=["interaction", "social"],
        )
        behavior = behavior_event(
            t=float(t_int),
            event_type="social_observation",
            source="engine.agent_interactions",
            summary=line,
            quality_score=float(quality["quality_score"]),
            payload={
                "neighbor_ids": [n.cell_id for n in neighbors],
                "alignment": alignment,
                "cluster_signal": quality["cluster_signal"],
                "thought_similarity": quality["thought_similarity"],
                "worldview_similarity": quality["worldview_similarity"],
                "belief_shift": belief["belief_shift"],
                "belief_polarity": belief["belief_polarity"],
            },
        )
        updated = append_memory(
            updated,
            observation_entry,
            behavior=behavior,
            promote=float(quality["quality_score"]) >= 0.72,
        )
        borrowed_summary = f"t={t_int} borrowed_signal={_salient_memory(source_neighbor)[:180]}"
        borrowed_entry = memory_entry(
            t=float(t_int),
            kind="borrowed_signal",
            summary=borrowed_summary,
            importance=max(0.35, float(quality["quality_score"]) * 0.85),
            source="engine.agent_interactions",
            payload={"from_cell_id": source_neighbor.cell_id},
            tags=["interaction", "signal"],
        )
        updated = append_memory(updated, borrowed_entry, promote=False)
        belief_entry = memory_entry(
            t=float(t_int),
            kind="belief_update",
            summary=f"t={t_int} {belief['belief_summary']}",
            importance=max(0.42, min(0.95, float(quality["quality_score"]) * 0.9)),
            source="engine.belief_dynamics",
            payload={
                "belief_shift": belief["belief_shift"],
                "belief_polarity": belief["belief_polarity"],
                "cluster_signal": quality["cluster_signal"],
            },
            tags=["belief", "worldview"],
        )
        updated = append_memory(
            updated,
            belief_entry,
            promote=float(belief["belief_shift"]) >= 0.18 or float(quality["quality_score"]) >= 0.76,
        )
        out.append(updated)
    return out
