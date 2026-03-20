"""Organic4D Engine — 세포 메모리 누적 (Phase 6.7 POC).

Redis 대신 in-memory 리스트로 경험 문자열을 쌓아 Worldview 갱신 조건을 만족시킨다.
"""
from __future__ import annotations

from typing import List

from app.models.cell import Cell

MEMORY_APPEND_INTERVAL = 25
MEMORY_MAX_ENTRIES = 120


def append_step_memory(cells: List[Cell], current_t: float) -> List[Cell]:
    """주기적으로 짧은 경험 로그를 메모리에 추가 (융합 등은 rules에서 이미 병합)."""
    t_int = int(current_t)
    if t_int <= 0 or t_int % MEMORY_APPEND_INTERVAL != 0:
        return cells

    out: List[Cell] = []
    for c in cells:
        line = f"t={t_int} energy={c.energy:.1f}"
        mem = list(c.memory) + [line]
        if len(mem) > MEMORY_MAX_ENTRIES:
            mem = mem[-MEMORY_MAX_ENTRIES:]
        out.append(c.copy(memory=mem))
    return out
