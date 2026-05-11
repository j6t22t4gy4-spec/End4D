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


def build_review_diff_prompt(diff_payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "review_diff",
        [
            ("base_summary_stats", _compact(diff_payload.get("base_summary_stats") or {})),
            ("target_summary_stats", _compact(diff_payload.get("target_summary_stats") or {})),
            ("group_drift_deltas", _compact_list(diff_payload.get("group_drift_deltas") or [], limit=6)),
            ("zone_z_delta", _compact_list(diff_payload.get("zone_z_delta") or [], limit=6)),
            ("policy_impact_delta", _compact(diff_payload.get("policy_impact_delta") or {})),
            ("timeline_turning_point_delta", _compact(diff_payload.get("timeline_turning_point_delta") or {})),
            ("notable_agent_delta", _compact(diff_payload.get("notable_agent_delta") or {})),
            ("coalition_shift_delta", _compact(diff_payload.get("coalition_shift_delta") or {})),
            ("key_delta_summary", " | ".join(str(item) for item in list(diff_payload.get("key_delta_summary") or [])[:8])),
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


def heuristic_review_diff(diff_payload: Mapping[str, Any]) -> dict[str, Any]:
    base_stats = dict(diff_payload.get("base_summary_stats") or {})
    target_stats = dict(diff_payload.get("target_summary_stats") or {})
    base_signal = str(base_stats.get("overall_signal") or "diffuse")
    target_signal = str(target_stats.get("overall_signal") or "diffuse")
    group_deltas = list(diff_payload.get("group_drift_deltas") or [])
    zone_deltas = list(diff_payload.get("zone_z_delta") or [])
    top_group = dict(group_deltas[0] if group_deltas else {})
    top_zone = dict(zone_deltas[0] if zone_deltas else {})
    key_deltas = [
        (
            f"cell delta moved from {int(base_stats.get('cell_delta', 0)):+d} "
            f"to {int(target_stats.get('cell_delta', 0)):+d}"
        ),
        (
            f"energy delta moved from {float(base_stats.get('energy_delta', 0.0)):+.2f} "
            f"to {float(target_stats.get('energy_delta', 0.0)):+.2f}"
        ),
        (
            f"overall signal shifted from {base_signal} to {target_signal}"
        ),
    ]
    if top_group:
        key_deltas.append(
            f"largest group gap is {top_group.get('role_label', 'group')} "
            f"(cohesion {float(top_group.get('cohesion_gap', 0.0)):+.2f}, tension {float(top_group.get('tension_gap', 0.0)):+.2f})"
        )
    causal = [
        (
            f"baseline 대비 target에서 {top_group.get('role_label', '핵심 집단')}의 stance가 "
            f"{top_group.get('stance_base', 'n/a')} -> {top_group.get('stance_target', 'n/a')}로 달라졌습니다."
        ),
        (
            f"이 집단의 cohesion/tension gap은 "
            f"{float(top_group.get('cohesion_gap', 0.0)):+.2f} / {float(top_group.get('tension_gap', 0.0)):+.2f}입니다."
        ),
    ]
    if top_zone:
        causal.append(
            f"{top_zone.get('zone_label', '주요 zone')}에서 avg z gap {float(top_zone.get('avg_z_gap', 0.0)):+.2f}가 나타났습니다."
        )
    return {
        "headline": f"{base_signal} baseline vs {target_signal} target",
        "executive_summary": (
            f"baseline 대비 target은 세포/에너지/z 변화 양상이 다르며, "
            f"주요 집단과 정책 영향 범위가 달라졌습니다."
        ),
        "key_deltas": key_deltas,
        "causal_comparison": causal,
        "decision_implications": [
            "두 world의 policy target 역할과 zone을 함께 확인해야 합니다.",
            "target world에서 drift가 큰 집단은 추가 intervention에 더 민감할 수 있습니다.",
            "가장 큰 zone z gap이 난 지역은 정책 커뮤니케이션 방식도 별도로 점검해야 합니다.",
        ],
    }


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


def parse_review_diff(raw_text: str, diff_payload: Mapping[str, Any]) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_review_diff(diff_payload)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_review_diff(diff_payload)
    fallback = heuristic_review_diff(diff_payload)
    return {
        "headline": str(parsed.get("headline") or fallback["headline"]),
        "executive_summary": str(parsed.get("executive_summary") or fallback["executive_summary"]),
        "key_deltas": _string_list(parsed.get("key_deltas"), fallback["key_deltas"]),
        "causal_comparison": _string_list(parsed.get("causal_comparison"), fallback["causal_comparison"]),
        "decision_implications": _string_list(
            parsed.get("decision_implications"),
            fallback["decision_implications"],
        ),
    }


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
