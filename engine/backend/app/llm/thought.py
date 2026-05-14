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

_CONTINUITY_EMBED_DIM = 64
_CONTINUITY_EMBED_CACHE: dict[str, np.ndarray] = {}

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
        if get_ui_language() == "ko" and (_looks_english(raw) or _looks_too_generic(raw)):
            return _grounded_thought_fallback(cell)
        return raw[:220]
    return _grounded_thought_fallback(cell)


def _grounded_thought_fallback(cell: Cell) -> str:
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    zone = (cell.zone_label or cell.zone_id or "local field").strip() or "local field"
    name = _agent_display(cell)
    persona = _persona_hint(cell)
    pressure = _pressure_phrase(cell)
    dialogue = _recent_dialogue_hint(cell)
    if dialogue:
        if get_ui_language() == "ko":
            peer, summary = dialogue
            return (
                f"{name}은 {peer}에게 들은 말이 계속 걸린다. {summary} "
                f"그래서 다음에는 이 문제가 {zone}의 다른 사람들에게도 같은 무게인지 직접 확인해보고 싶다."
            )[:260]
        peer, summary = dialogue
        return (
            f"{name} keeps turning over what {peer} said. {summary} "
            f"Next, they want to test whether others in {zone} feel the same pressure."
        )[:260]
    recent = _recent_behavior_hint(cell)
    if get_ui_language() == "ko":
        if pressure:
            return f"{name}은 {zone}에서 {pressure}를 느낀다. 방금 떠오른 단서는 '{recent}'이고, 다음에는 누구에게 먼저 말을 걸어야 할지 고민한다."
        if persona:
            return f"{name}은 '{persona}'라는 자기 사정을 떠올리며, {zone}에서 내 말이 누구에게 통할지 조심스럽게 가늠한다."
        return f"{name}은 {zone}의 분위기를 보며, 지금은 큰 말보다 가까운 사람의 반응을 먼저 들어봐야겠다고 생각한다."
    if pressure:
        return f"{name} feels {pressure} in {zone}; after '{recent}', they wonder who to speak with first."
    if persona:
        return f"{name} keeps '{persona}' in mind and wonders who in {zone} would actually listen."
    return f"{name} watches {zone} and decides to ask a nearby person what they really think next."


def _looks_english(text: str) -> bool:
    letters = re.findall(r"[A-Za-z]", text or "")
    korean = re.findall(r"[가-힣]", text or "")
    return len(letters) >= 12 and len(letters) > len(korean) * 2


def _looks_too_generic(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    generic_markers = (
        "reassessing immediate goals",
        "current goals",
        "next moves",
        "adaptive planning",
        "state-like",
    )
    return any(marker in lowered for marker in generic_markers) and len(lowered.split()) <= 16


def _persona_hint(cell: Cell) -> str:
    text = " ".join(str(cell.persona_text or "").split())
    if text:
        return text[:80]
    attrs = dict(cell.persona_attrs or {})
    for key in ("occupation", "district", "values", "policy_sensitivity"):
        value = str(attrs.get(key) or "").strip()
        if value:
            return value[:80]
    return ""


def _agent_display(cell: Cell) -> str:
    attrs = dict(cell.persona_attrs or {})
    name = str(attrs.get("agent_name") or attrs.get("display_name") or "").strip()
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    if name:
        return name if "(" in name else f"{name}({role})"
    return role


def _recent_dialogue_hint(cell: Cell) -> tuple[str, str] | None:
    state = dict(cell.action_state or {})
    peer = str(state.get("last_dialogue_peer_label") or "").strip()
    summary = " ".join(str(state.get("last_dialogue_summary") or "").split())
    if peer and summary:
        return peer, summary[:160]
    for item in reversed(list(cell.behavior_log or [])[-12:]):
        if str(item.get("event_type") or "") != "agent_dialogue":
            continue
        payload = dict(item.get("payload") or {})
        peer = str(payload.get("peer_label") or payload.get("peer_id") or "").strip()
        summary = " ".join(str(item.get("summary") or "").split())
        if summary:
            return peer or "방금 만난 사람", summary[:160]
    return None


def _pressure_phrase(cell: Cell) -> str:
    state = dict(cell.action_state)
    bucket = str(state.get("collective_pressure_bucket") or "").strip()
    signal = str(state.get("collective_signal") or "").strip()
    pressure = float(state.get("collective_pressure", 0.0) or 0.0)
    if get_ui_language() == "ko":
        if bucket or signal:
            return f"집단 압력 {bucket or signal}"
        if pressure >= 0.5:
            return "높아진 집단 압력"
        return ""
    if bucket or signal:
        return f"collective pressure {bucket or signal}"
    if pressure >= 0.5:
        return "rising collective pressure"
    return ""


def _recent_behavior_hint(cell: Cell) -> str:
    for item in reversed(list(cell.behavior_log or [])[-6:]):
        summary = " ".join(str(item.get("summary") or "").split())
        if summary:
            return summary[:90]
    if get_ui_language() == "ko":
        return "최근 관찰된 상호작용"
    return "recent observed interactions"


def _thought_continuity_score(previous: str, current: str) -> float:
    semantic_score = _semantic_continuity_score(previous, current)
    if semantic_score is not None:
        return semantic_score
    return _token_overlap_continuity_score(previous, current)


def _semantic_continuity_score(previous: str, current: str) -> float | None:
    previous = str(previous or "").strip()
    current = str(current or "").strip()
    if not previous or not current:
        return None
    try:
        prev_vec = _continuity_embedding(previous)
        current_vec = _continuity_embedding(current)
        score = float(np.dot(prev_vec, current_vec))
        return round(max(0.0, min(1.0, (score + 1.0) * 0.5)), 3)
    except Exception:
        return None


def _continuity_embedding(text: str) -> np.ndarray:
    cached = _CONTINUITY_EMBED_CACHE.get(text)
    if cached is not None:
        return cached
    vec = embed_texts([text], _CONTINUITY_EMBED_DIM)[0]
    _CONTINUITY_EMBED_CACHE[text] = vec
    return vec


def _token_overlap_continuity_score(previous: str, current: str) -> float:
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
    if score >= 0.82:
        return "stable"
    if score >= 0.62:
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
