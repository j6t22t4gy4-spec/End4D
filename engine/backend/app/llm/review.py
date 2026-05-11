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


def build_review_query_prompt(payload: Mapping[str, Any], question: str) -> str:
    return build_prompt_contract(
        "review_query",
        [
            ("question", question),
            ("summary_stats", _compact(payload.get("summary_stats") or {})),
            ("belief_drift", _compact(payload.get("belief_drift") or {})),
            ("policy_impact", _compact(payload.get("policy_impact") or {})),
            ("grounding", _compact(payload.get("grounding") or {})),
            ("annotation_candidates", _compact_list(payload.get("annotation_candidates") or [], limit=5)),
            ("highlights", " | ".join(str(item) for item in list(payload.get("highlights") or [])[:6])),
        ],
    )


def build_review_diff_query_prompt(diff_payload: Mapping[str, Any], question: str) -> str:
    return build_prompt_contract(
        "review_diff_query",
        [
            ("question", question),
            ("base_summary_stats", _compact(diff_payload.get("base_summary_stats") or {})),
            ("target_summary_stats", _compact(diff_payload.get("target_summary_stats") or {})),
            ("group_drift_deltas", _compact_list(diff_payload.get("group_drift_deltas") or [], limit=6)),
            ("zone_z_delta", _compact_list(diff_payload.get("zone_z_delta") or [], limit=6)),
            ("policy_impact_delta", _compact(diff_payload.get("policy_impact_delta") or {})),
            ("timeline_turning_point_delta", _compact(diff_payload.get("timeline_turning_point_delta") or {})),
            ("key_delta_summary", " | ".join(str(item) for item in list(diff_payload.get("key_delta_summary") or [])[:8])),
        ],
    )


def build_session_review_prompt(payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "session_review",
        [
            ("session_title", str(payload.get("title") or "Session")),
            ("summary_stats", _compact(payload.get("summary_stats") or {})),
            ("strongest_worlds", _compact_list(payload.get("strongest_worlds") or [], limit=5)),
            ("grounding", _compact(payload.get("grounding") or {})),
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


def heuristic_review_query(payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    prompt = str(question or "").strip().lower()
    belief_drift = dict(payload.get("belief_drift") or {})
    groups = list(belief_drift.get("groups") or [])
    zones = list(payload.get("zone_z_drift") or [])
    agents = list(payload.get("notable_agents") or [])
    events = list(payload.get("key_events") or [])

    answer = "현재 리뷰 데이터에서 질문에 대한 명확한 근거를 찾지 못했습니다."
    evidence: list[str] = []
    follow_up: list[str] = []

    if "집단" in prompt or "group" in prompt or "stance" in prompt:
        top_group = dict(groups[0] if groups else {})
        if top_group:
            answer = (
                f"{top_group.get('role_label', '핵심 집단')}이 가장 큰 집단 신념 변화를 보였습니다. "
                f"stance는 {top_group.get('stance_before', 'n/a')}에서 {top_group.get('stance_after', 'n/a')}로 이동했고, "
                f"cohesion {float(top_group.get('cohesion_delta', 0.0)):+.2f}, tension {float(top_group.get('tension_delta', 0.0)):+.2f}, "
                f"polarization {float(top_group.get('polarization_delta', 0.0)):+.2f} 변화가 나타났습니다."
            )
            evidence.append(
                f"group={top_group.get('role_label', 'n/a')} stance {top_group.get('stance_before', 'n/a')} -> {top_group.get('stance_after', 'n/a')}"
            )
            evidence.append(
                f"cohesion_delta={float(top_group.get('cohesion_delta', 0.0)):+.2f}, tension_delta={float(top_group.get('tension_delta', 0.0)):+.2f}, polarization_delta={float(top_group.get('polarization_delta', 0.0)):+.2f}"
            )
    elif "지역" in prompt or "zone" in prompt or "고도" in prompt or "z" in prompt:
        top_zone = dict(zones[0] if zones else {})
        if top_zone:
            answer = (
                f"{top_zone.get('zone_label', '주요 zone')}이 가장 큰 social elevation 변화를 보였습니다. "
                f"avg z delta는 {float(top_zone.get('avg_z_delta', 0.0)):+.2f}이고, "
                f"final cell 수는 {int(top_zone.get('cell_count_after', 0))}입니다."
            )
            evidence.append(
                f"zone={top_zone.get('zone_label', 'n/a')} avg_z_delta={float(top_zone.get('avg_z_delta', 0.0)):+.2f}"
            )
            evidence.append(
                f"avg_energy_after={float(top_zone.get('avg_energy_after', 0.0)):.2f}, cell_count_after={int(top_zone.get('cell_count_after', 0))}"
            )
    elif "에이전트" in prompt or "agent" in prompt or "worldview" in prompt:
        top_agent = dict(agents[0] if agents else {})
        if top_agent:
            answer = (
                f"{top_agent.get('role_label', 'agent')} 에이전트가 가장 큰 개별 belief shift를 보였습니다. "
                f"score는 {float(top_agent.get('belief_shift_score', 0.0)):.2f}, z delta는 {float(top_agent.get('z_delta', 0.0)):+.2f}입니다."
            )
            evidence.append(
                f"agent_role={top_agent.get('role_label', 'n/a')} belief_shift_score={float(top_agent.get('belief_shift_score', 0.0)):.2f}"
            )
            evidence.append(
                f"zone={top_agent.get('zone_label', 'n/a')}, worldview_shift={float(top_agent.get('worldview_shift', 0.0)):.2f}"
            )
    elif "정책" in prompt or "policy" in prompt or "이벤트" in prompt:
        top_event = dict(events[0] if events else {})
        if top_event:
            answer = (
                f"가장 최근 주요 정책/이벤트는 {top_event.get('name', 'event')}이며 "
                f"target role {', '.join(list(top_event.get('target_roles') or [])[:3]) or 'n/a'}과 "
                f"target zone {', '.join(list(top_event.get('target_zones') or [])[:3]) or 'n/a'}에 집중되었습니다."
            )
            evidence.append(
                f"event={top_event.get('name', 'n/a')} t={float(top_event.get('t', 0.0)):.0f} type={top_event.get('event_type', 'event')}"
            )
            evidence.append(
                f"roles={', '.join(list(top_event.get('target_roles') or [])[:4]) or 'n/a'}, zones={', '.join(list(top_event.get('target_zones') or [])[:4]) or 'n/a'}"
            )

    if not evidence:
        highlights = list(payload.get("highlights") or [])
        evidence = [str(item) for item in highlights[:2]]
    follow_up = [
        "Review diff와 함께 보면 baseline 대비 차이를 더 명확하게 해석할 수 있습니다.",
        "관련 turning point로 이동해 해당 시점 snapshot을 직접 확인해보는 것이 좋습니다.",
    ]
    return {
        "answer": answer,
        "evidence": evidence[:4],
        "follow_up": follow_up[:3],
        "confidence_notes": ["heuristic fallback used" if evidence else "limited evidence available"],
    }


def heuristic_review_diff_query(diff_payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    prompt = str(question or "").strip().lower()
    groups = list(diff_payload.get("group_drift_deltas") or [])
    zones = list(diff_payload.get("zone_z_delta") or [])
    policy = dict(diff_payload.get("policy_impact_delta") or {})
    top_group = dict(groups[0] if groups else {})
    top_zone = dict(zones[0] if zones else {})
    answer = "현재 diff evidence로는 질문에 대한 결정적 결론이 제한적입니다."
    evidence: list[str] = []
    if "정책" in prompt or "policy" in prompt:
        answer = (
            f"target 쪽 정책 영향은 role {', '.join(list(policy.get('target_only_roles') or [])[:3]) or 'n/a'}와 "
            f"zone {', '.join(list(policy.get('target_only_zones') or [])[:3]) or 'n/a'}에서 baseline과 가장 크게 갈렸습니다."
        )
        evidence.append(
            f"target_only_roles={', '.join(list(policy.get('target_only_roles') or [])[:4]) or 'n/a'}"
        )
        evidence.append(
            f"target_only_zones={', '.join(list(policy.get('target_only_zones') or [])[:4]) or 'n/a'}"
        )
    elif "집단" in prompt or "group" in prompt or "분열" in prompt or "fracture" in prompt:
        answer = (
            f"{top_group.get('role_label', '핵심 집단')}이 baseline 대비 가장 큰 집단 차이를 보였습니다. "
            f"split risk {float(top_group.get('split_risk_gap', 0.0)):+.2f}, "
            f"block divergence {float(top_group.get('block_divergence_gap', 0.0)):+.2f}, "
            f"cross-zone fracture {float(top_group.get('cross_zone_fracture_gap', 0.0)):+.2f}입니다."
        )
        evidence.append(
            f"group={top_group.get('role_label', 'n/a')} split_risk_gap={float(top_group.get('split_risk_gap', 0.0)):+.2f}"
        )
        evidence.append(
            f"block_divergence_gap={float(top_group.get('block_divergence_gap', 0.0)):+.2f}, cross_zone_fracture_gap={float(top_group.get('cross_zone_fracture_gap', 0.0)):+.2f}"
        )
    elif "지역" in prompt or "zone" in prompt:
        answer = (
            f"{top_zone.get('zone_label', '주요 zone')}이 baseline 대비 가장 큰 지역 차이를 보였습니다. "
            f"avg z gap {float(top_zone.get('avg_z_gap', 0.0)):+.2f}, energy gap {float(top_zone.get('avg_energy_gap', 0.0)):+.2f}입니다."
        )
        evidence.append(
            f"zone={top_zone.get('zone_label', 'n/a')} avg_z_gap={float(top_zone.get('avg_z_gap', 0.0)):+.2f}"
        )
    else:
        answer = (
            f"가장 큰 차이는 {top_group.get('role_label', '집단')}의 집단 동학 변화와 "
            f"{top_zone.get('zone_label', '지역')}의 regional elevation shift에 집중됩니다."
        )
        evidence.append(
            f"group={top_group.get('role_label', 'n/a')} cohesion_gap={float(top_group.get('cohesion_gap', 0.0)):+.2f}, tension_gap={float(top_group.get('tension_gap', 0.0)):+.2f}"
        )
        evidence.append(
            f"zone={top_zone.get('zone_label', 'n/a')} avg_z_gap={float(top_zone.get('avg_z_gap', 0.0)):+.2f}"
        )
    return {
        "answer": answer,
        "evidence": evidence[:4],
        "follow_up": [
            "target와 baseline turning point를 각각 열어 같은 시점을 직접 비교해보는 것이 좋습니다.",
            "policy impact delta와 group drift table을 함께 보면 원인 해석이 더 선명해집니다.",
        ],
        "confidence_notes": ["heuristic diff query used"],
    }


def heuristic_session_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    strongest = list(payload.get("strongest_worlds") or [])
    top = dict(strongest[0] if strongest else {})
    stats = dict(payload.get("summary_stats") or {})
    return {
        "headline": f"Session with {int(stats.get('world_count', 0))} worlds and avg split risk {float(stats.get('avg_split_risk', 0.0)):.2f}",
        "executive_summary": (
            f"이 세션은 {int(stats.get('world_count', 0))}개의 world를 포함하며, "
            f"평균 split risk {float(stats.get('avg_split_risk', 0.0)):.2f}, "
            f"평균 block divergence {float(stats.get('avg_block_divergence', 0.0)):.2f}, "
            f"평균 cross-zone fracture {float(stats.get('avg_cross_zone_fracture', 0.0)):.2f}를 보였습니다."
        ),
        "key_findings": [
            f"가장 극적인 world는 {top.get('world_id', 'n/a')}이며 signal={top.get('overall_signal', 'diffuse')}입니다.",
            "세션 단위에서는 split risk와 cross-zone fracture가 높은 world를 우선 비교하는 것이 좋습니다.",
        ],
        "decision_implications": [
            "같은 세션 내 strongest world와 baseline world를 붙여보면 정책 민감도 차이가 더 잘 드러납니다.",
            "fracture score가 높은 world는 후속 intervention 실험의 우선 후보입니다.",
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


def parse_review_query(raw_text: str, payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_review_query(payload, question)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_review_query(payload, question)
    fallback = heuristic_review_query(payload, question)
    return {
        "answer": str(parsed.get("answer") or fallback["answer"]),
        "evidence": _string_list(parsed.get("evidence"), fallback["evidence"]),
        "follow_up": _string_list(parsed.get("follow_up"), fallback["follow_up"]),
        "confidence_notes": _string_list(parsed.get("confidence_notes"), fallback["confidence_notes"]),
    }


def parse_review_diff_query(raw_text: str, diff_payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_review_diff_query(diff_payload, question)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_review_diff_query(diff_payload, question)
    fallback = heuristic_review_diff_query(diff_payload, question)
    return {
        "answer": str(parsed.get("answer") or fallback["answer"]),
        "evidence": _string_list(parsed.get("evidence"), fallback["evidence"]),
        "follow_up": _string_list(parsed.get("follow_up"), fallback["follow_up"]),
        "confidence_notes": _string_list(parsed.get("confidence_notes"), fallback["confidence_notes"]),
    }


def parse_session_review(raw_text: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_session_review(payload)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_session_review(payload)
    fallback = heuristic_session_review(payload)
    return {
        "headline": str(parsed.get("headline") or fallback["headline"]),
        "executive_summary": str(parsed.get("executive_summary") or fallback["executive_summary"]),
        "key_findings": _string_list(parsed.get("key_findings"), fallback["key_findings"]),
        "decision_implications": _string_list(parsed.get("decision_implications"), fallback["decision_implications"]),
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
