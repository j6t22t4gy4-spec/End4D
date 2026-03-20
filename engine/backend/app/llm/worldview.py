"""Worldview 벡터 갱신 (Phase 6.5).

t≥200 또는 메모리 100+ 인 세포만, 주기적으로 경험 텍스트를 384차원에 임베딩.
ARCHITECTURE_CHECKLIST 4.5, 4.6
"""
from __future__ import annotations

from typing import List

from app.llm.embeddings import embed_texts
from app.models.cell import Cell

WORLDVIEW_MEMORY_THRESHOLD = 100
WORLDVIEW_T_THRESHOLD = 200.0
# 조건 충족 후에도 매 스텝 호출하지 않도록 간격
WORLDVIEW_REFRESH_INTERVAL = 40


def _worldview_text(cell: Cell) -> str:
    if cell.memory:
        tail = "; ".join(cell.memory[-40:])
        return f"accumulated experience: {tail}"
    return "nascent worldview; no structured memory yet"


def update_worldviews_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    if t_int <= 0 or t_int % WORLDVIEW_REFRESH_INTERVAL != 0:
        return cells

    texts: List[str] = []
    indices: List[int] = []
    for i, c in enumerate(cells):
        qualifies = float(current_t) >= WORLDVIEW_T_THRESHOLD or len(c.memory) >= WORLDVIEW_MEMORY_THRESHOLD
        if qualifies:
            texts.append(_worldview_text(c))
            indices.append(i)

    if not texts:
        return cells

    vecs = embed_texts(texts, 384)
    out = list(cells)
    for k, idx in enumerate(indices):
        out[idx] = out[idx].copy(worldview_vec=vecs[k].copy())
    return out
