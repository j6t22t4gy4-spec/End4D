"""Thought 벡터 갱신 (Phase 6.4).

10~50 t마다 텍스트 요약 후 임베딩 → 256차원. 융합 조건 70%는 rules에서 cosine으로 판정.

LLM runtime이 켜져 있으면 로컬/Ollama 또는 클라우드 API를 통해
중간 reasoning text를 생성한 뒤, 이를 임베딩해 thought_vec를 갱신한다.
"""
from __future__ import annotations

from typing import List

from app.core.settings import get_llm_agent_sample_size
from app.llm.embeddings import embed_texts
from app.llm.facade import llm_facade
from app.models.cell import Cell

# ARCHITECTURE_CHECKLIST 4.3: 10~50 t
THOUGHT_UPDATE_INTERVAL = 20
def update_thoughts_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    if t_int <= 0 or t_int % THOUGHT_UPDATE_INTERVAL != 0:
        return cells

    selected = _selected_indices(cells, t_int, get_llm_agent_sample_size())
    selected_cells = [cells[idx] for idx in selected]
    texts = llm_facade.think(selected_cells)
    vecs = embed_texts(texts, 256)
    out: List[Cell] = [c.copy() for c in cells]
    for k, idx in enumerate(selected):
        out[idx] = out[idx].copy(thought_vec=vecs[k].copy())
    return out


def _selected_indices(cells: List[Cell], t_int: int, limit: int) -> List[int]:
    if len(cells) <= limit:
        return list(range(len(cells)))
    ranked = sorted(
        range(len(cells)),
        key=lambda idx: (
            -len(cells[idx].short_memory) - len(cells[idx].long_memory),
            -float(cells[idx].energy),
            f"{t_int}:{cells[idx].cell_id}",
        ),
    )
    return ranked[:limit]
