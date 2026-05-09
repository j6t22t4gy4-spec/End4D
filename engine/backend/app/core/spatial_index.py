"""Uniform grid spatial index for local neighbor searches.

The engine uses this for same-timestep 3D neighborhood queries before applying
the exact 4D distance or emotion radius checks.
"""
from __future__ import annotations

from collections import defaultdict
from itertools import product
from math import ceil, floor
from typing import DefaultDict, Iterable, List, Tuple

from app.models.cell import Cell

GridKey = Tuple[int, int, int]


class SpatialHashGrid:
    """Small dependency-free 3D grid index for cells in one simulation step."""

    def __init__(self, cells: List[Cell], cell_size: float):
        self.cell_size = max(float(cell_size), 1e-6)
        self._buckets: DefaultDict[GridKey, List[Cell]] = defaultdict(list)
        for cell in cells:
            self._buckets[self._key(cell)].append(cell)

    def _key(self, cell: Cell) -> GridKey:
        return (
            floor(cell.x / self.cell_size),
            floor(cell.y / self.cell_size),
            floor(cell.z / self.cell_size),
        )

    def candidate_cells(self, cell: Cell, radius: float) -> Iterable[Cell]:
        """Yield cells from buckets that can contain neighbors within radius."""
        cx, cy, cz = self._key(cell)
        bucket_radius = max(1, ceil(float(radius) / self.cell_size))
        offsets = range(-bucket_radius, bucket_radius + 1)
        for dx, dy, dz in product(offsets, offsets, offsets):
            yield from self._buckets.get((cx + dx, cy + dy, cz + dz), ())


def spatial_distance_sq(c1: Cell, c2: Cell) -> float:
    dx = c1.x - c2.x
    dy = c1.y - c2.y
    dz = c1.z - c2.z
    return dx * dx + dy * dy + dz * dz


def count_neighbors_by_cell(
    cells: List[Cell],
    radius: float,
) -> dict[str, int]:
    """Count same-step 3D neighbors with grid pruning."""
    if not cells:
        return {}

    grid = SpatialHashGrid(cells, cell_size=radius)
    r2 = radius * radius
    counts: dict[str, int] = {}
    for cell in cells:
        n = 0
        for other in grid.candidate_cells(cell, radius):
            if other.cell_id == cell.cell_id:
                continue
            if spatial_distance_sq(cell, other) < r2:
                n += 1
        counts[cell.cell_id] = n
    return counts
