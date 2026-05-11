"""Post-simulation LLM review helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping

from app.llm.prompt_registry import build_prompt_contract


def build_review_summary_prompt(payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "review_summary",
        [
            ("world_meta", _compact(payload.get("world_meta") or {})),
            ("summary_stats", _compact(payload.get("summary_stats") or {})),
            ("belief_drift", _compact(payload.get("belief_drift") or {})),
            ("policy_impact", _compact(payload.get("policy_impact") or {})),
            ("key_events", _compact_list(payload.get("key_events") or [], limit=5)),
            ("notable_agents", _compact_list(payload.get("notable_agents") or [], limit=5)),
            ("zone_z_drift", _compact_list(payload.get("zone_z_drift") or [], limit=5)),
            ("highlights", " | ".join(str(item) for item in list(payload.get("highlights") or [])[:6])),
        ],
    )


def build_timeline_annotation_prompt(payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "timeline_annotation",
        [
            ("summary_stats", _compact(payload.get("summary_stats") or {})),
            ("key_events", _compact_list(payload.get("key_events") or [], limit=5)),
            ("annotation_candidates", _compact_list(payload.get("annotation_candidates") or [], limit=6)),
            ("highlights", " | ".join(str(item) for item in list(payload.get("highlights") or [])[:6])),
        ],
    )


def heuristic_review_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary_stats = dict(payload.get("summary_stats") or {})
    belief_drift = dict(payload.get("belief_drift") or {})
    top_group = dict((belief_drift.get("groups") or [{}])[0] or {})
    key_events = list(payload.get("key_events") or [])
    notable_agents = list(payload.get("notable_agents") or [])

    headline = (
        f"{summary_stats.get('outcome', 'stable')} trajectory with "
        f"{summary_stats.get('overall_signal', 'diffuse')} group signal"
    )
    executive_summary = (
        f"세포 수는 {summary_stats.get('initial_cell_count', 0)}에서 "
        f"{summary_stats.get('final_cell_count', 0)}로 변했고, 총 에너지는 "
        f"{float(summary_stats.get('energy_delta', 0.0)):+.2f} 이동했습니다. "
        f"집단 신호는 {summary_stats.get('overall_signal', 'diffuse')}이며 "
        f"가장 큰 역할 집단은 {top_group.get('role_label', 'n/a')}입니다."
    )

    causal_analysis = []
    if key_events:
        event = key_events[0]
        causal_analysis.append(
            f"{event.get('name', '주요 이벤트')}가 role/zone 표적을 가지며 belief drift를 촉발한 것으로 보입니다."
        )
    causal_analysis.append(
        f"{top_group.get('role_label', '핵심 집단')}의 cohesion 변화 "
        f"{float(top_group.get('cohesion_delta', 0.0)):+.2f}와 tension 변화 "
        f"{float(top_group.get('tension_delta', 0.0)):+.2f}가 전체 시그널에 영향을 줬습니다."
    )
    if notable_agents:
        mover = notable_agents[0]
        causal_analysis.append(
            f"{mover.get('role_label', 'agent')}에서 worldview/z 변화가 크게 나타나 미시적 전환 신호가 확인됩니다."
        )

    decision_implications = [
        "정책 이벤트의 대상 role과 zone이 실제로 어떤 신념 이동을 만들었는지 비교 실험이 필요합니다.",
        "contest 신호가 있는 집단은 후속 intervention에서 불안정성이 커질 수 있습니다.",
    ]

    watch_items = list(payload.get("highlights") or [])[:4]
    key_event_lines = [
        f"t={event.get('t', 0)} {event.get('name', 'event')} ({event.get('event_type', 'event')})"
        for event in key_events[:4]
    ]

    return {
        "headline": headline,
        "executive_summary": executive_summary,
        "key_events": key_event_lines,
        "causal_analysis": causal_analysis[:4],
        "decision_implications": decision_implications[:4],
        "watch_items": watch_items,
    }


def heuristic_timeline_annotations(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for item in list(payload.get("annotation_candidates") or [])[:4]:
        annotations.append(
            {
                "t": float(item.get("t", 0.0)),
                "label": str(item.get("label") or "timeline shift"),
                "reason": str(item.get("reason") or ""),
                "severity": _severity(float(item.get("score", 0.0))),
            }
        )
    return annotations


def parse_review_summary(raw_text: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_review_summary(payload)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_review_summary(payload)

    fallback = heuristic_review_summary(payload)
    return {
        "headline": str(parsed.get("headline") or fallback["headline"]),
        "executive_summary": str(parsed.get("executive_summary") or fallback["executive_summary"]),
        "key_events": _string_list(parsed.get("key_events"), fallback["key_events"]),
        "causal_analysis": _string_list(parsed.get("causal_analysis"), fallback["causal_analysis"]),
        "decision_implications": _string_list(
            parsed.get("decision_implications"),
            fallback["decision_implications"],
        ),
        "watch_items": _string_list(parsed.get("watch_items"), fallback["watch_items"]),
    }


def parse_timeline_annotations(raw_text: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_timeline_annotations(payload)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_timeline_annotations(payload)
    rows = list(parsed.get("annotations") or [])
    out: list[dict[str, Any]] = []
    for item in rows[:6]:
        out.append(
            {
                "t": float(item.get("t", 0.0)),
                "label": str(item.get("label") or "timeline shift"),
                "reason": str(item.get("reason") or ""),
                "severity": str(item.get("severity") or "medium"),
            }
        )
    return out or heuristic_timeline_annotations(payload)


def _compact(mapping: Mapping[str, Any]) -> str:
    return "; ".join(f"{key}={value}" for key, value in mapping.items())[:1800]


def _compact_list(items: list[Any], *, limit: int) -> str:
    sliced = items[:limit]
    return " | ".join(_compact(item) if isinstance(item, Mapping) else str(item) for item in sliced)[:1800]


def _string_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:6] or list(fallback)


def _severity(score: float) -> str:
    if score >= 1.45:
        return "high"
    if score >= 0.9:
        return "medium"
    return "low"
