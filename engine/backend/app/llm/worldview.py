"""Worldview 벡터 갱신 (Phase 6.5).

t≥200 또는 메모리 100+ 인 세포만, 주기적으로 경험 텍스트를 384차원에 임베딩.
ARCHITECTURE_CHECKLIST 4.5, 4.6
"""
from __future__ import annotations

from typing import List

from app.core.settings import (
    get_llm_agent_sample_size,
    get_worldview_memory_threshold,
    get_worldview_refresh_interval,
    get_worldview_t_threshold,
)
from app.llm.embeddings import embed_texts
from app.llm.facade import llm_facade
from app.models.cell import Cell

def update_worldviews_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    interval = get_worldview_refresh_interval()
    if t_int <= 0 or t_int % interval != 0:
        return cells

    selected_cells: List[Cell] = []
    indices: List[int] = []
    limit = get_llm_agent_sample_size()
    ranked_indices = sorted(
        range(len(cells)),
        key=lambda idx: (
            -len(cells[idx].long_memory),
            -len(cells[idx].memory),
            -float(cells[idx].energy),
            cells[idx].cell_id,
        ),
    )
    selected_indices = set(ranked_indices[:limit])
    for i, c in enumerate(cells):
        if i not in selected_indices:
            continue
        qualifies = (
            float(current_t) >= get_worldview_t_threshold()
            or len(c.long_memory) >= 8
            or len(c.memory) >= get_worldview_memory_threshold()
        )
        if qualifies:
            indices.append(i)
            selected_cells.append(c)

    if not selected_cells:
        return cells

    generated = llm_facade.update_worldviews(selected_cells)
    vecs = embed_texts(generated, 384)
    out = list(cells)
    for k, idx in enumerate(indices):
        out[idx] = out[idx].copy(worldview_vec=vecs[k].copy())
    return out
