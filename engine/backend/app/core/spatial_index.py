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
        self.cells = list(cells)
        self._buckets: DefaultDict[GridKey, List[Cell]] = defaultdict(list)
        for cell in self.cells:
            self._buckets[self._key(cell)].append(cell)
        if self.cells:
            self._min_x = min(c.x for c in self.cells)
            self._max_x = max(c.x for c in self.cells)
            self._min_y = min(c.y for c in self.cells)
            self._max_y = max(c.y for c in self.cells)
            self._min_z = min(c.z for c in self.cells)
            self._max_z = max(c.z for c in self.cells)
        else:
            self._min_x = self._max_x = 0.0
            self._min_y = self._max_y = 0.0
            self._min_z = self._max_z = 0.0

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

    def search_radius_covering_bounds(self, cell: Cell) -> float:
        """Radius large enough to cover all indexed cells from a query cell."""
        dx = max(abs(cell.x - self._min_x), abs(cell.x - self._max_x))
        dy = max(abs(cell.y - self._min_y), abs(cell.y - self._max_y))
        dz = max(abs(cell.z - self._min_z), abs(cell.z - self._max_z))
        return (dx * dx + dy * dy + dz * dz) ** 0.5 + self.cell_size

    def nearest_candidates(
        self,
        cell: Cell,
        *,
        k: int,
        initial_radius: float,
    ) -> List[Cell]:
        """Return enough 3D candidates to contain the k nearest cells."""
        if not self.cells or k <= 0:
            return []

        radius = max(float(initial_radius), self.cell_size)
        max_radius = max(radius, self.search_radius_covering_bounds(cell))
        while True:
            r2 = radius * radius
            out: List[Cell] = []
            seen: set[str] = set()
            for other in self.candidate_cells(cell, radius):
                if other.cell_id in seen:
                    continue
                seen.add(other.cell_id)
                if spatial_distance_sq(cell, other) <= r2:
                    out.append(other)
            if len(out) >= k or radius >= max_radius:
                return out or list(self.cells)
            radius *= 2.0


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
