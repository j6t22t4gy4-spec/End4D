"""Organic4D Engine — 세포(에이전트) 모델 (Phase 1.1).

CONCEPT §5·§5.1: 세포 = 역할 + (x,y,z,t), energy, gene_vec, memory, 3계층 벡터
ARCHITECTURE_CHECKLIST 2.1: 세포 위치는 반드시 (x, y, z, t) 4차원
ARCHITECTURE_CHECKLIST 2.2: emotion_vec, thought_vec, worldview_vec 포함 (3계층)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List
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

    # 레거시 메모리 문자열 뷰 (호환성 유지)
    memory: List[str] = field(default_factory=list)
    short_memory: List[Dict[str, Any]] = field(default_factory=list)
    long_memory: List[Dict[str, Any]] = field(default_factory=list)
    behavior_log: List[Dict[str, Any]] = field(default_factory=list)

    # 3계층 감정·생각·세계관 (Phase 1: 고정/임의 값)
    emotion_vec: np.ndarray = field(default_factory=lambda: np.zeros(8))
    thought_vec: np.ndarray = field(default_factory=lambda: np.zeros(256))
    worldview_vec: np.ndarray = field(default_factory=lambda: np.zeros(384))

    # 역할 (CONCEPT §5.1) — 3계층은 이 역할 맥락에서 해석·갱신
    role_key: str = "agent"
    role_label: str = ""

    # 선택: 외부 페르소나 데이터셋 기반 초기 조건
    persona_id: str = ""
    persona_text: str = ""
    persona_country: str = ""
    persona_attrs: Dict[str, Any] = field(default_factory=dict)

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
            "short_memory": [dict(item) for item in self.short_memory],
            "long_memory": [dict(item) for item in self.long_memory],
            "behavior_log": [dict(item) for item in self.behavior_log],
            "emotion_vec": self.emotion_vec.copy(),
            "thought_vec": self.thought_vec.copy(),
            "worldview_vec": self.worldview_vec.copy(),
            "role_key": self.role_key,
            "role_label": self.role_label,
            "persona_id": self.persona_id,
            "persona_text": self.persona_text,
            "persona_country": self.persona_country,
            "persona_attrs": dict(self.persona_attrs),
            "cell_id": self.cell_id,
        }
        d.update(overrides)
        return Cell(**d)
