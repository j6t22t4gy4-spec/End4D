"""Organic4D Engine — 세계·스냅샷 모델 (Phase 1.3).

ARCHITECTURE §2.2: World → Snapshot → Cell 계층 구조
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .cell import Cell


@dataclass
class NutrientEvent:
    """영양분 이벤트 (God View 주입 등)."""
    t: float
    event_type: str
    payload: dict


@dataclass
class Snapshot:
    """특정 t 시점의 세계 스냅샷."""
    world_id: str
    t: float
    cells: List[Cell] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


@dataclass
class World:
    """4D 세계."""
    world_id: str
    t_max: float
    initial_cells: List[Cell] = field(default_factory=list)
    nutrients: List[NutrientEvent] = field(default_factory=list)
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
