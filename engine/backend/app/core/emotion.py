"""Organic4D Engine — 규칙 기반 Emotion 벡터 (Phase 6.1).

8차원: joy, anger, fear, calm, surprise, trust, anticipation, disgust
ARCHITECTURE_CHECKLIST 4.1: LLM 호출 0. CONCEPT §6.1
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.models.cell import Cell

# 순서는 API/프론트와 동기화 (docs/CODE_REFERENCE.md)
EMOTION_LABELS = (
    "joy",
    "anger",
    "fear",
    "calm",
    "surprise",
    "trust",
    "anticipation",
    "disgust",
)

EMOTION_DIM = 8

# 이웃 밀집도 판정 (3D 거리, t 제외한 공간 거리에 가깝게)
NEIGHBOR_RADIUS = 3.0
CROWD_REFERENCE = 12.0

# 이전 감정과의 블렌딩 (급격한 깜빡임 완화)
BLEND_ALPHA = 0.38


def _spatial_distance_sq(c1: Cell, c2: Cell) -> float:
    dx = c1.x - c2.x
    dy = c1.y - c2.y
    dz = c1.z - c2.z
    return dx * dx + dy * dy + dz * dz


def count_neighbors(cells: List[Cell], cell: Cell, radius: float = NEIGHBOR_RADIUS) -> int:
    """같은 스텝의 다른 세포 중 공간 거리 < radius 인 개수."""
    r2 = radius * radius
    n = 0
    for other in cells:
        if other.cell_id == cell.cell_id:
            continue
        if _spatial_distance_sq(cell, other) < r2:
            n += 1
    return n


def compute_emotion_proposal(cell: Cell, neighbor_count: int) -> np.ndarray:
    """에너지·밀집도로 8D 감정 후보를 계산 (규칙 기반)."""
    e = np.zeros(EMOTION_DIM, dtype=np.float32)
    e_norm = float(np.clip(cell.energy / 100.0, 0.0, 1.0))

    # 에너지: 낮을수록 불안·혐오, 높을수록 기쁨·안정·신뢰
    e[2] += 0.65 * (1.0 - e_norm)  # fear
    e[7] += 0.22 * (1.0 - e_norm)  # disgust
    e[0] += 0.72 * e_norm  # joy
    e[3] += 0.55 * e_norm  # calm
    e[5] += 0.35 * e_norm  # trust

    crowd = min(1.0, neighbor_count / CROWD_REFERENCE)
    e[2] += 0.42 * crowd
    e[1] += 0.35 * crowd  # anger
    e[3] -= 0.28 * crowd
    e[6] += 0.25 * crowd  # anticipation (경쟁·압박)

    # 중간 에너지대: 변동·불확실
    mid_stress = 1.0 - abs(e_norm - 0.45) * 2.0
    mid_stress = float(np.clip(mid_stress, 0.0, 1.0))
    e[4] += 0.22 * mid_stress  # surprise

    return np.clip(e, -1.0, 1.0).astype(np.float32)


def update_emotions(cells: List[Cell], current_t: float) -> List[Cell]:
    """매 t 끝에서 호출: 모든 세포의 emotion_vec 갱신."""
    if not cells:
        return cells

    out: List[Cell] = []
    for cell in cells:
        nc = count_neighbors(cells, cell)
        proposal = compute_emotion_proposal(cell, nc)
        blended = (1.0 - BLEND_ALPHA) * cell.emotion_vec.astype(
            np.float32
        ) + BLEND_ALPHA * proposal
        blended = np.clip(blended, -1.0, 1.0).astype(np.float32)
        out.append(cell.copy(emotion_vec=blended))
    return out
