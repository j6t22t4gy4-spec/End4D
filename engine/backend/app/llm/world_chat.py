"""World-level conversational QA helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping

from app.llm.prompt_registry import build_prompt_contract


def build_world_chat_prompt(payload: Mapping[str, Any], question: str) -> str:
    return build_prompt_contract(
        "world_chat",
        [
            (
                "answer_style",
                (
                    "Answer in Korean if the question is Korean. Stay grounded in the provided snapshot/persona/event data. "
                    "For an agent target, explain what that named persona appears to believe, who recently influenced them, "
                    "and what they may do next. For role/zone/world targets, synthesize the strongest pressure, dialogue, "
                    "and event evidence instead of giving generic scenario commentary. Return strict JSON."
                ),
            ),
            ("question", question),
            ("chat_context", _compact(payload.get("chat_context") or {})),
            ("world", _compact(payload.get("world") or {})),
            ("snapshot", _compact(payload.get("snapshot") or {})),
            ("comparison", _compact(payload.get("comparison") or {})),
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
    target_type = str(target.get("type") or "world")
    target_summary = dict(target.get("summary") or {})
    comparison = dict(payload.get("comparison") or {})
    target_label = str(target.get("label") or target.get("type") or "world")
    t = snapshot.get("t", "n/a")
    answer = _agent_answer(target_label, personas, events, snapshot, world, question, comparison=comparison) if target_type == "agent" else _group_answer(
        target_label, personas, events, snapshot, world, question, target_summary=target_summary, comparison=comparison
    )
    citations = _citation_ids(payload, "snapshot", limit=1)
    citations += _citation_ids(payload, "personas", limit=2)
    citations += _citation_ids(payload, "events", limit=2)
    citations += _citation_ids(payload, "relationships", limit=2)
    return {
        "answer": answer,
        "evidence": [
            (
                f"snapshot t={t}, cells={snapshot.get('cell_count', 0)}, "
                f"target={snapshot.get('target_cell_count', 0)}, "
                f"pressure={snapshot.get('avg_collective_pressure', 0.0)}"
            ),
            f"target={target_label}",
            f"events={len(events)}, dialogues={target_summary.get('dialogue_count', 0)}",
            _comparison_evidence(comparison),
        ],
        "follow_up": _follow_up_questions(target_type, target_label),
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


def _agent_answer(
    target_label: str,
    personas: list[Any],
    events: list[Any],
    snapshot: Mapping[str, Any],
    world: Mapping[str, Any],
    question: str,
    comparison: Mapping[str, Any],
) -> str:
    persona = dict(personas[0] or {}) if personas else {}
    action = dict(persona.get("action_state") or {})
    relationships = [dict(item or {}) for item in list(persona.get("relationships") or [])]
    latest_event = _first_event_for_persona(events, str(persona.get("cell_id") or ""))
    peer = str(action.get("last_dialogue_peer_label") or (relationships[0].get("peer_label") if relationships else "") or "").strip()
    dialogue = str(action.get("last_dialogue_summary") or (relationships[0].get("last_summary") if relationships else "") or "").strip()
    thought = str(action.get("last_thought_summary") or "").strip()
    action_text = str(action.get("last_action_summary") or action.get("strategy_summary") or "").strip()
    pressure = _fmt(action.get("collective_pressure", snapshot.get("avg_collective_pressure", 0.0)))
    decision_delta = _fmt(action.get("decision_pressure_delta", snapshot.get("avg_decision_pressure_delta", 0.0)))
    scene_sentence = ""
    if latest_event:
        scene_sentence = f" 최근 장면에서는 '{latest_event.get('summary') or latest_event.get('label')}' 흐름에 묶여 있습니다."
    peer_sentence = f" 특히 {peer}와의 대화가 남아 있고, 그 대화는 '{dialogue}'로 요약됩니다." if peer and dialogue else ""
    thought_sentence = f" 현재 생각의 핵심은 '{thought}'입니다." if thought else ""
    action_sentence = f" 다음 행동 단서는 '{action_text}'로 보입니다." if action_text else ""
    comparison_sentence = _comparison_sentence(comparison)
    return (
        f"t={snapshot.get('t', 'n/a')}에서 {target_label}은 단순한 역할 표본이 아니라 "
        f"{persona.get('zone_label') or '해당 구역'} 안에서 압력 {pressure}, 결정 압력 {decision_delta}를 받고 있는 개별 페르소나입니다."
        f"{peer_sentence}{thought_sentence}{scene_sentence}{action_sentence}{comparison_sentence} "
        f"따라서 질문 '{question}'에 답하면, 이 에이전트는 시나리오 '{world.get('genesis_prompt') or 'scenario'}'를 "
        "추상 정책이 아니라 주변 사람의 말과 자기 생계/역할 이해를 통해 해석하고 있다고 보는 편이 가장 근거에 맞습니다."
    )


def _group_answer(
    target_label: str,
    personas: list[Any],
    events: list[Any],
    snapshot: Mapping[str, Any],
    world: Mapping[str, Any],
    question: str,
    *,
    target_summary: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> str:
    pressure = _fmt(target_summary.get("avg_collective_pressure", snapshot.get("avg_collective_pressure", 0.0)))
    max_pressure = _fmt(target_summary.get("max_collective_pressure", 0.0))
    decision_delta = _fmt(target_summary.get("avg_decision_pressure_delta", snapshot.get("avg_decision_pressure_delta", 0.0)))
    top_people = [str(dict(item or {}).get("label") or "") for item in list(target_summary.get("top_pressure_personas") or [])[:2]]
    top_people = [item for item in top_people if item]
    event_bits = []
    for event in events[:3]:
        row = dict(event or {})
        label = str(row.get("summary") or row.get("label") or row.get("scene_type") or "").strip()
        if label:
            event_bits.append(label)
    persona_bits = []
    for persona in personas[:3]:
        row = dict(persona or {})
        label = str(row.get("label") or "").strip()
        action = dict(row.get("action_state") or {})
        thought = str(action.get("last_thought_summary") or action.get("last_dialogue_summary") or "").strip()
        if label and thought:
            persona_bits.append(f"{label}: {thought[:90]}")
    event_sentence = f" 최근 장면은 {' / '.join(event_bits)} 쪽으로 모입니다." if event_bits else ""
    persona_sentence = f" 대표 내부 목소리는 {'; '.join(persona_bits)}입니다." if persona_bits else ""
    top_sentence = f" 특히 압력이 큰 표본은 {', '.join(top_people)}입니다." if top_people else ""
    comparison_sentence = _comparison_sentence(comparison)
    return (
        f"t={snapshot.get('t', 'n/a')}의 {target_label}은 평균 압력 {pressure}, 최대 압력 {max_pressure}, "
        f"결정 압력 {decision_delta} 수준으로 관측됩니다.{top_sentence}{event_sentence}{persona_sentence}{comparison_sentence} "
        f"질문 '{question}'에 대한 현재 해석은, 시나리오 '{world.get('genesis_prompt') or 'scenario'}'가 "
        "집단 전체에 균일하게 먹히기보다 일부 페르소나와 최근 상호작용을 통해 국소적으로 증폭되는 상태라는 쪽입니다."
    )


def _first_event_for_persona(events: list[Any], cell_id: str) -> dict[str, Any]:
    if not cell_id:
        return dict(events[0] or {}) if events else {}
    for event in events:
        row = dict(event or {})
        targets = {str(item) for item in list(row.get("target_ids") or [])}
        if str(row.get("source_id") or "") == cell_id or cell_id in targets:
            return row
    return dict(events[0] or {}) if events else {}


def _follow_up_questions(target_type: str, target_label: str) -> list[str]:
    if target_type == "agent":
        return [
            f"{target_label}이 누구의 말에 가장 영향받았어?",
            "이 에이전트가 다음 t에서 어떤 선택을 할 가능성이 커?",
        ]
    if target_type == "zone":
        return [
            f"{target_label} 구역의 긴장을 올리는 사건은 뭐야?",
            "이 구역과 다른 구역의 반응 차이를 비교해줘.",
        ]
    if target_type == "role":
        return [
            f"{target_label} 집단 내부에서 갈라지는 의견은 뭐야?",
            "이 역할 집단이 정책을 어떻게 다르게 해석하고 있어?",
        ]
    return [
        "가장 압력이 높은 집단과 그 이유를 알려줘.",
        "정책 주입 전후로 달라진 상호작용을 비교해줘.",
    ]


def _fmt(value: Any) -> str:
    try:
        return f"{float(value or 0.0):.3f}"
    except (TypeError, ValueError):
        return "0.000"


def _comparison_sentence(comparison: Mapping[str, Any]) -> str:
    if not comparison:
        return ""
    pressure_delta = _fmt(comparison.get("pressure_delta", 0.0))
    decision_delta = _fmt(comparison.get("decision_pressure_delta", 0.0))
    compare_t = comparison.get("compare_t", "이전")
    return f" 비교 기준 t={compare_t} 대비 압력 변화는 {pressure_delta}, 결정 압력 변화는 {decision_delta}입니다."


def _comparison_evidence(comparison: Mapping[str, Any]) -> str:
    if not comparison:
        return "comparison=none"
    return (
        f"comparison t={comparison.get('compare_t')}, "
        f"pressure_delta={comparison.get('pressure_delta', 0.0)}, "
        f"decision_delta={comparison.get('decision_pressure_delta', 0.0)}"
    )
