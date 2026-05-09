"""Thought 벡터 갱신 (Phase 6.4).

10~50 t마다 텍스트 요약 후 임베딩 → 256차원. 융합 조건 70%는 rules에서 cosine으로 판정.

후속: `ORGANIC4D_LLM_CHAT_ENABLED=1` + `app.core.settings.get_llm_chat_enabled()`로
Ollama 등 대화형 LLM 경로를 붙일 수 있음 (현재는 임베딩만).
"""
from __future__ import annotations

from typing import List

from app.llm.embeddings import embed_texts
from app.llm.prompt_engineering import build_thought_prompt
from app.models.cell import Cell

# ARCHITECTURE_CHECKLIST 4.3: 10~50 t
THOUGHT_UPDATE_INTERVAL = 20
def update_thoughts_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    if t_int <= 0 or t_int % THOUGHT_UPDATE_INTERVAL != 0:
        return cells

    texts = [build_thought_prompt(c) for c in cells]
    vecs = embed_texts(texts, 256)
    out: List[Cell] = []
    for i, c in enumerate(cells):
        out.append(c.copy(thought_vec=vecs[i].copy()))
    return out
