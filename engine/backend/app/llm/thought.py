"""Thought 벡터 갱신 (Phase 6.4).

10~50 t마다 텍스트 요약 후 임베딩 → 256차원. 융합 조건 70%는 rules에서 cosine으로 판정.

LLM runtime이 켜져 있으면 로컬/Ollama 또는 클라우드 API를 통해
중간 reasoning text를 생성한 뒤, 이를 임베딩해 thought_vec를 갱신한다.
"""
from __future__ import annotations

from typing import List

from app.llm.embeddings import embed_texts
from app.llm.chat_runtime import generate_reasoning_texts
from app.llm.prompt_engineering import build_thought_prompt
from app.models.cell import Cell

# ARCHITECTURE_CHECKLIST 4.3: 10~50 t
THOUGHT_UPDATE_INTERVAL = 20
def update_thoughts_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    if t_int <= 0 or t_int % THOUGHT_UPDATE_INTERVAL != 0:
        return cells

    prompts = [build_thought_prompt(c) for c in cells]
    texts = generate_reasoning_texts(prompts, task="thought")
    vecs = embed_texts(texts, 256)
    out: List[Cell] = []
    for i, c in enumerate(cells):
        out.append(c.copy(thought_vec=vecs[i].copy()))
    return out
