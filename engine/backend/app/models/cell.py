"""Organic4D Engine — 세포(에이전트) 모델 (Phase 1.1).

CONCEPT §5: 세포 = (x,y,z,t), energy, gene_vec, memory, emotion_vec, thought_vec, worldview_vec
ARCHITECTURE_CHECKLIST 2.1: 세포 위치는 반드시 (x, y, z, t) 4차원
ARCHITECTURE_CHECKLIST 2.2: emotion_vec, thought_vec, worldview_vec 포함 (3계층)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List
import uuid

import numpy as np


@dataclass
class Cell:
    """4D 시공간의 유기체 세포."""

    # 4D 좌표 (CONCEPT §5)
    x: float
    y: float
    z: float
    t: float

    # 에너지
    energy: float

    # 유전자 벡터 (분열·융합 시 전달·변이)
    gene_vec: np.ndarray

    # 메모리 (장기 이벤트)
    memory: List[str] = field(default_factory=list)

    # 3계층 감정·생각·세계관 (Phase 1: 고정/임의 값)
    emotion_vec: np.ndarray = field(default_factory=lambda: np.zeros(8))
    thought_vec: np.ndarray = field(default_factory=lambda: np.zeros(256))
    worldview_vec: np.ndarray = field(default_factory=lambda: np.zeros(384))

    # 고유 ID (분열·융합 시 추적)
    cell_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def position_4d(self) -> tuple[float, float, float, float]:
        """4D 좌표 반환."""
        return (self.x, self.y, self.z, self.t)

    def position_3d(self) -> tuple[float, float, float]:
        """3D 공간 좌표 (시각화용)."""
        return (self.x, self.y, self.z)

    def copy(self, **overrides) -> Cell:
        """복사본 생성 (분열 등에 사용)."""
        d = {
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "t": self.t,
            "energy": self.energy,
            "gene_vec": self.gene_vec.copy(),
            "memory": list(self.memory),
            "emotion_vec": self.emotion_vec.copy(),
            "thought_vec": self.thought_vec.copy(),
            "worldview_vec": self.worldview_vec.copy(),
        }
        d.update(overrides)
        return Cell(**d)
