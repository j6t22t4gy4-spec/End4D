"""Organic4D Engine — 4D 좌표·거리 함수 (Phase 1.2).

CONCEPT §10.1: 4D 거리 함수 — (x,y,z)와 t에 가중치 적용 가능
ARCHITECTURE_CHECKLIST 2.3: (x,y,z)와 t에 가중치 적용 가능해야 함
"""
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
    """4D 거리 계산.

    d = sqrt( space_weight * ((x1-x2)² + (y1-y2)² + (z1-z2)²) + time_weight * (t1-t2)² )

    Args:
        p1, p2: Cell 또는 (x, y, z, t) 튜플
        space_weight: 공간 (x,y,z) 가중치
        time_weight: 시간 t 가중치 (기본 0.1 — t 차이 영향 완화)

    Returns:
        가중 유클리드 거리
    """
    def to_tuple(p: Union[Cell, Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
        if isinstance(p, Cell):
            return p.position_4d()
        return p

    x1, y1, z1, t1 = to_tuple(p1)
    x2, y2, z2, t2 = to_tuple(p2)

    space_sq = (x1 - x2) ** 2 + (y1 - y2) ** 2 + (z1 - z2) ** 2
    time_sq = (t1 - t2) ** 2

    return float(np.sqrt(space_weight * space_sq + time_weight * time_sq))


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """코사인 유사도 (융합 조건 등에 사용)."""
    anorm = np.linalg.norm(a)
    bnorm = np.linalg.norm(b)
    if anorm == 0 or bnorm == 0:
        return 0.0
    return float(np.dot(a, b) / (anorm * bnorm))
