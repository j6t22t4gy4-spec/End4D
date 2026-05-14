"""World-level conversational QA helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping

from app.llm.prompt_registry import build_prompt_contract


def build_world_chat_prompt(payload: Mapping[str, Any], question: str) -> str:
    return build_prompt_contract(
        "world_chat",
        [
            ("question", question),
            ("chat_context", _compact(payload.get("chat_context") or {})),
            ("world", _compact(payload.get("world") or {})),
            ("snapshot", _compact(payload.get("snapshot") or {})),
            ("target", _compact(payload.get("target") or {})),
            ("personas", _compact(payload.get("personas") or [])),
            ("events", _compact(payload.get("events") or [])),
            ("group_state", _compact(payload.get("group_state") or {})),
            ("grounding", _compact(payload.get("grounding") or {})),
        ],
    )


def heuristic_world_chat(payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    world = dict(payload.get("world") or {})
    snapshot = dict(payload.get("snapshot") or {})
    target = dict(payload.get("target") or {})
    personas = list(payload.get("personas") or [])
    events = list(payload.get("events") or [])
    target_label = str(target.get("label") or target.get("type") or "world")
    t = snapshot.get("t", "n/a")
    event_text = ""
    if events:
        top = dict(events[0] or {})
        event_text = f" 최근 장면으로는 {top.get('summary') or top.get('label') or top.get('scene_type') or 'interaction'}가 관측됩니다."
    persona_text = ""
    if personas:
        top_persona = dict(personas[0] or {})
        persona_text = (
            f" 대표 페르소나는 {top_persona.get('label') or top_persona.get('role_label') or 'agent'}이며 "
            f"{top_persona.get('zone_label') or 'zone'}에 있습니다."
        )
    answer = (
        f"t={t} 기준으로 {target_label} 맥락에서 보면, 이 세계는 "
        f"'{world.get('genesis_prompt') or 'scenario'}'의 압력과 집단 반응을 중심으로 해석해야 합니다."
        f"{persona_text}{event_text} 질문 '{question}'에 대한 확실한 판단은 snapshot/persona/event 근거 안에서만 제한적으로 가능합니다."
    )
    citations = _citation_ids(payload, "snapshot", limit=1)
    citations += _citation_ids(payload, "personas", limit=2)
    citations += _citation_ids(payload, "events", limit=2)
    return {
        "answer": answer,
        "evidence": [
            f"snapshot t={t}, cells={snapshot.get('cell_count', 0)}",
            f"target={target_label}",
            f"events={len(events)}",
        ],
        "follow_up": [
            "특정 역할 집단만 골라 다시 질문해보세요.",
            "정책 주입 전후 t를 비교해 질문하면 인과 해석이 더 선명해집니다.",
        ],
        "confidence_notes": ["heuristic world chat used; answer is grounded in available snapshot metadata"],
        "citations": citations[:6],
    }


def parse_world_chat(raw_text: str, payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_world_chat(payload, question)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_world_chat(payload, question)
    fallback = heuristic_world_chat(payload, question)
    return {
        "answer": str(parsed.get("answer") or fallback["answer"]),
        "evidence": _string_list(parsed.get("evidence"), fallback["evidence"]),
        "follow_up": _string_list(parsed.get("follow_up"), fallback["follow_up"]),
        "confidence_notes": _string_list(parsed.get("confidence_notes"), fallback["confidence_notes"]),
        "citations": _validated_citation_list(parsed.get("citations"), fallback["citations"], payload),
    }


def _compact(value: Any, limit: int = 6000) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"


def _string_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        out = [str(item).strip() for item in value if str(item).strip()]
        return out or fallback
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


def _allowed_anchor_ids(payload: Mapping[str, Any]) -> set[str]:
    ids: set[str] = set()
    for value in dict(payload.get("grounding") or {}).values():
        for item in list(value or []):
            anchor_id = str(dict(item).get("anchor_id") or "").strip()
            if anchor_id:
                ids.add(anchor_id)
    return ids


def _validated_citation_list(value: Any, fallback: list[str], payload: Mapping[str, Any]) -> list[str]:
    allowed = _allowed_anchor_ids(payload)
    if not allowed:
        return []
    if isinstance(value, list):
        out = [str(item).strip() for item in value if str(item).strip() in allowed]
        if out:
            return out[:6]
    return [item for item in fallback if item in allowed][:6]


def _citation_ids(payload: Mapping[str, Any], section: str, limit: int = 2) -> list[str]:
    rows = list((dict(payload.get("grounding") or {}).get(section) or []))
    return [str(dict(item).get("anchor_id") or "") for item in rows[:limit] if str(dict(item).get("anchor_id") or "")]
