"""Agent-to-agent interaction memory for the engine data flywheel.

This layer does not add chatbot/user interaction. It lets cells periodically
observe nearby agents and write compact social experience into memory, which
then feeds Thought/Worldview embedding updates.
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.core.coordinates import cosine_similarity, distance_4d
from app.core.memory_step import trim_memory
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
            f"roles=[{roles}] avg_neighbor_energy={avg_energy:.1f} alignment={alignment}"
        )
        memory = list(cell.memory) + [line]
        source_neighbor = aligned[0] if aligned else neighbors[0]
        memory.append(f"t={t_int} borrowed_signal={_salient_memory(source_neighbor)[:180]}")

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

        out.append(
            cell.copy(
                memory=trim_memory(memory),
                thought_vec=thought_vec,
                worldview_vec=worldview_vec,
            )
        )
    return out
