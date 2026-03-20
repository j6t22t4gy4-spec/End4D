"""God View 주입 이벤트 → 세포 상태 변환 (Phase 7.1).

event_type별 payload 규약은 API 문서·프론트 기본값과 맞출 것.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from app.models.cell import Cell


def apply_inject_to_cells(
    cells: List[Cell],
    event_type: str,
    payload: Dict,
) -> List[Cell]:
    """스냅샷 시점의 세포 목록에 주입 효과 적용."""
    if event_type == "nutrient_burst":
        amt = float(payload.get("amount", 10.0))
        return [c.copy(energy=c.energy + amt) for c in cells]

    if event_type == "append_memory":
        text = str(payload.get("text", "injected event"))
        return [c.copy(memory=list(c.memory) + [text]) for c in cells]

    if event_type == "emotion_spike":
        idx = int(payload.get("index", 2))
        delta = float(payload.get("delta", 0.35))
        out: List[Cell] = []
        for c in cells:
            ev = c.emotion_vec.copy().astype(np.float32)
            if 0 <= idx < ev.shape[0]:
                ev[idx] = np.clip(float(ev[idx]) + delta, -1.0, 1.0)
            out.append(c.copy(emotion_vec=ev))
        return out

    if event_type == "noop":
        return [c.copy() for c in cells]

    # 알 수 없는 타입: 보수적으로 복사만
    return [c.copy() for c in cells]
