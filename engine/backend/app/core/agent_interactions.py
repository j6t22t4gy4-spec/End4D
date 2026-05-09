"""Agent-to-agent interaction memory for the engine data flywheel.

This layer does not add chatbot/user interaction. It lets cells periodically
observe nearby agents and write compact social experience into memory, which
then feeds Thought/Worldview embedding updates.
"""
from __future__ import annotations

from typing import List

from app.core.coordinates import distance_4d
from app.core.memory_step import trim_memory
from app.core.spatial_index import SpatialHashGrid
from app.models.cell import Cell

SOCIAL_INTERACTION_INTERVAL = 10
SOCIAL_RADIUS = 4.0
MAX_NEIGHBORS_PER_CELL = 3


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
        for n in neighbors:
            role = n.role_label or n.role_key or "agent"
            role_counts[role] = role_counts.get(role, 0) + 1
            energy_sum += float(n.energy)

        roles = ", ".join(f"{role}:{count}" for role, count in sorted(role_counts.items()))
        avg_energy = energy_sum / len(neighbors)
        line = (
            f"t={t_int} social_observation neighbors={len(neighbors)} "
            f"roles=[{roles}] avg_neighbor_energy={avg_energy:.1f}"
        )
        out.append(cell.copy(memory=trim_memory(list(cell.memory) + [line])))
    return out
