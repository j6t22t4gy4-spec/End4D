"""Organic4D Engine — 2D social field 좌표·거리 함수 (Phase 1.2)."""
from __future__ import annotations

from typing import Tuple, Union

import numpy as np

from app.models.cell import Cell


def distance_4d(
    p1: Union[Cell, Tuple[float, float, float, float]],
    p2: Union[Cell, Tuple[float, float, float, float]],
    *,
    space_weight: float = 1.0,
    time_weight: float = 0.1,
) -> float:
    """하위 호환성용 거리 함수.

    이름은 유지하지만 실제 의미는 2D distance + zone penalty + time 이다.
    """
    def to_tuple(p: Union[Cell, Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
        if isinstance(p, Cell):
            return p.position_4d()
        return p

    x1, y1, z1, t1 = to_tuple(p1)
    x2, y2, z2, t2 = to_tuple(p2)

    space_sq = (x1 - x2) ** 2 + (y1 - y2) ** 2
    if isinstance(p1, Cell) and isinstance(p2, Cell):
        penalty = zone_penalty(p1, p2)
        space_sq += penalty * penalty
    time_sq = (t1 - t2) ** 2

    return float(np.sqrt(space_weight * space_sq + time_weight * time_sq))


def zone_penalty(a: Cell, b: Cell) -> float:
    """Return an additive zone friction penalty for cross-zone interaction."""
    zone_a = (a.zone_id or "").strip()
    zone_b = (b.zone_id or "").strip()
    if not zone_a or not zone_b or zone_a == zone_b:
        return 0.0
    return max(0.35, 1.0 + (float(a.zone_friction) + float(b.zone_friction)) / 2.0)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """코사인 유사도 (융합 조건 등에 사용)."""
    anorm = np.linalg.norm(a)
    bnorm = np.linalg.norm(b)
    if anorm == 0 or bnorm == 0:
        return 0.0
    return float(np.dot(a, b) / (anorm * bnorm))
