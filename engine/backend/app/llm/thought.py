"""Thought 벡터 갱신 (Phase 6.4).

10~50 t마다 텍스트 요약 후 임베딩 → 256차원. 융합 조건 70%는 rules에서 cosine으로 판정.

LLM runtime이 켜져 있으면 로컬/Ollama 또는 클라우드 API를 통해
중간 reasoning text를 생성한 뒤, 이를 임베딩해 thought_vec를 갱신한다.
"""
from __future__ import annotations

import re
from typing import List

import numpy as np

from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.settings import get_llm_agent_sample_size, get_thought_refresh_interval, get_ui_language
from app.llm.embeddings import embed_texts
from app.llm.facade import llm_facade
from app.models.cell import Cell

def update_thoughts_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    interval = get_thought_refresh_interval()
    if t_int <= 0:
        return cells
    # Write an early first thought so short runs still expose cognition traces.
    if t_int != 1 and t_int % interval != 0:
        return cells

    selected = _selected_indices(cells, t_int, get_llm_agent_sample_size())
    selected_cells = [cells[idx] for idx in selected]
    texts = llm_facade.think(selected_cells)
    vecs = embed_texts(texts, 256)
    out: List[Cell] = [c.copy() for c in cells]
    for k, idx in enumerate(selected):
        thought_text = _summarize_thought_text(texts[k], selected_cells[k])
        previous_thought = str(out[idx].action_state.get("last_thought_summary", "")).strip()
        continuity_score = _thought_continuity_score(previous_thought, thought_text)
        entry = memory_entry(
            t=float(current_t),
            kind="thought_update",
            summary=thought_text,
            importance=0.58,
            source="llm.thought",
            payload={"raw_text": str(texts[k] or "")[:400]},
            tags=["llm", "thought"],
        )
        behavior = behavior_event(
            t=float(current_t),
            event_type="thought_update",
            source="llm.thought",
            summary=thought_text,
            quality_score=0.6,
            payload={"raw_text": str(texts[k] or "")[:240]},
        )
        current_action_state = dict(out[idx].action_state)
        if previous_thought:
            current_action_state["previous_thought_summary"] = previous_thought
            current_action_state["previous_thought_t"] = current_action_state.get("last_thought_t")
        current_action_state["thought_continuity_score"] = continuity_score
        current_action_state["thought_continuity_state"] = _continuity_state_label(continuity_score)
        current_action_state["last_thought_summary"] = thought_text
        current_action_state["last_thought_t"] = float(current_t)
        updated = append_memory(
            out[idx].copy(
                thought_vec=vecs[k].copy(),
                action_state=current_action_state,
            ),
            entry,
            behavior=behavior,
            promote=False,
        )
        out[idx] = updated
    return out


def _selected_indices(cells: List[Cell], t_int: int, limit: int) -> List[int]:
    if len(cells) <= limit:
        return list(range(len(cells)))
    ranked = sorted(
        range(len(cells)),
        key=lambda idx: (
            -(0 if np.linalg.norm(cells[idx].thought_vec) > 0 else 1),
            -len(cells[idx].short_memory) - len(cells[idx].long_memory),
            -float(cells[idx].energy),
            f"{t_int}:{cells[idx].cell_id}",
        ),
    )
    return ranked[:limit]


def _summarize_thought_text(text: str, cell: Cell) -> str:
    raw = " ".join(str(text or "").strip().split())
    if raw:
        return raw[:220]
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    if get_ui_language() == "ko":
        return f"{role}는 당장의 제약과 다음 선택지를 다시 계산하고 있다."
    return f"{role} is reassessing immediate goals and constraints."


def _thought_continuity_score(previous: str, current: str) -> float:
    prev_tokens = _normalize_tokens(previous)
    current_tokens = _normalize_tokens(current)
    if not prev_tokens or not current_tokens:
        return 0.0
    overlap = len(prev_tokens & current_tokens)
    union = len(prev_tokens | current_tokens)
    if union <= 0:
        return 0.0
    return round(overlap / union, 3)


def _continuity_state_label(score: float) -> str:
    if score >= 0.55:
        return "stable"
    if score >= 0.22:
        return "evolving"
    return "volatile"


def _normalize_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"\s+", " ", str(text or "").strip().lower())
    if not cleaned:
        return set()
    return {
        token
        for token in re.split(r"[^0-9a-zA-Z가-힣_]+", cleaned)
        if len(token) >= 2
    }
