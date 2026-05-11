"""Post-simulation LLM review helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from app.llm.prompt_registry import build_prompt_contract
from app.models.cell import Cell


def build_review_summary_prompt(payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "review_summary",
        [
            ("world_meta", _compact(payload.get("world_meta") or {})),
            ("summary_stats", _compact(payload.get("summary_stats") or {})),
            ("belief_drift", _compact(payload.get("belief_drift") or {})),
            ("group_analysis", _compact(payload.get("group_analysis") or {})),
            ("lineage_summary", _compact(payload.get("lineage_summary") or {})),
            ("emergent_dynamics", _compact(payload.get("emergent_dynamics") or {})),
            ("mechanism_summary", _compact(payload.get("mechanism_summary") or {})),
            ("policy_impact", _compact(payload.get("policy_impact") or {})),
            ("policy_lineage_bridge", _compact(payload.get("policy_lineage_bridge") or {})),
            ("causal_chains", _compact_list(payload.get("causal_chains") or [], limit=4)),
            ("key_events", _compact_list(payload.get("key_events") or [], limit=5)),
            ("notable_agents", _compact_list(payload.get("notable_agents") or [], limit=5)),
            ("zone_z_drift", _compact_list(payload.get("zone_z_drift") or [], limit=5)),
            ("anchor_candidates", _compact_anchor_candidates(payload.get("grounding") or {})),
            ("grounding", _compact(payload.get("grounding") or {})),
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
            ("mechanism_delta", _compact(diff_payload.get("mechanism_delta") or {})),
            ("lineage_delta", _compact(diff_payload.get("lineage_delta") or {})),
            ("policy_lineage_delta", _compact(diff_payload.get("policy_lineage_delta") or {})),
            ("timeline_turning_point_delta", _compact(diff_payload.get("timeline_turning_point_delta") or {})),
            ("notable_agent_delta", _compact(diff_payload.get("notable_agent_delta") or {})),
            ("coalition_shift_delta", _compact(diff_payload.get("coalition_shift_delta") or {})),
            ("anchor_candidates", _compact_anchor_candidates(diff_payload.get("grounding") or {})),
            ("grounding", _compact(diff_payload.get("grounding") or {})),
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
            ("group_analysis", _compact(payload.get("group_analysis") or {})),
            ("lineage_summary", _compact(payload.get("lineage_summary") or {})),
            ("emergent_dynamics", _compact(payload.get("emergent_dynamics") or {})),
            ("mechanism_summary", _compact(payload.get("mechanism_summary") or {})),
            ("policy_impact", _compact(payload.get("policy_impact") or {})),
            ("policy_lineage_bridge", _compact(payload.get("policy_lineage_bridge") or {})),
            ("anchor_candidates", _compact_anchor_candidates(payload.get("grounding") or {})),
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
            ("mechanism_delta", _compact(diff_payload.get("mechanism_delta") or {})),
            ("lineage_delta", _compact(diff_payload.get("lineage_delta") or {})),
            ("policy_lineage_delta", _compact(diff_payload.get("policy_lineage_delta") or {})),
            ("timeline_turning_point_delta", _compact(diff_payload.get("timeline_turning_point_delta") or {})),
            ("anchor_candidates", _compact_anchor_candidates(diff_payload.get("grounding") or {})),
            ("key_delta_summary", " | ".join(str(item) for item in list(diff_payload.get("key_delta_summary") or [])[:8])),
        ],
    )


def build_session_review_prompt(payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "session_review",
        [
            ("session_title", str(payload.get("title") or "Session")),
            ("summary_stats", _compact(payload.get("summary_stats") or {})),
            ("lineage_summary", _compact(payload.get("lineage_summary") or {})),
            ("policy_lineage_bridge", _compact(payload.get("policy_lineage_bridge") or {})),
            ("strongest_worlds", _compact_list(payload.get("strongest_worlds") or [], limit=5)),
            ("anchor_candidates", _compact_anchor_candidates(payload.get("grounding") or {})),
            ("grounding", _compact(payload.get("grounding") or {})),
        ],
    )


def build_session_review_query_prompt(payload: Mapping[str, Any], question: str) -> str:
    return build_prompt_contract(
        "session_review_query",
        [
            ("question", question),
            ("session_title", str(payload.get("title") or "Session")),
            ("summary_stats", _compact(payload.get("summary_stats") or {})),
            ("lineage_summary", _compact(payload.get("lineage_summary") or {})),
            ("policy_lineage_bridge", _compact(payload.get("policy_lineage_bridge") or {})),
            ("strongest_worlds", _compact_list(payload.get("strongest_worlds") or [], limit=5)),
            ("anchor_candidates", _compact_anchor_candidates(payload.get("grounding") or {})),
            ("grounding", _compact(payload.get("grounding") or {})),
        ],
    )


def build_citation_repair_prompt(
    *,
    task: str,
    raw_text: str,
    grounding: Mapping[str, Any],
    required_keys: Sequence[str],
    citation_mode: str,
    repair_reason: str = "",
) -> str:
    payload = {
        "task": task,
        "citation_mode": citation_mode,
        "required_keys": list(required_keys),
        "allowed_anchor_ids": sorted(_allowed_anchor_ids(grounding)),
        "repair_reason": str(repair_reason or ""),
    }
    return build_prompt_contract(
        "review_citation_repair",
        [
            ("repair_meta", _compact(payload)),
            ("repair_focus", _repair_focus_instructions(str(repair_reason or ""), citation_mode=citation_mode)),
            ("sentence_anchor_hints", _compact_sentence_anchor_hints(grounding, required_keys, citation_mode=citation_mode)),
            ("anchor_candidates", _compact_anchor_candidates(grounding)),
            ("grounding", _compact(grounding)),
            ("broken_output", str(raw_text or "")[:4000]),
        ],
    )


def build_agent_interview_prompt(
    *,
    cell: Cell,
    question: str,
    grounding: Mapping[str, Any],
) -> str:
    short_memory = " | ".join(
        str(item.get("summary") or "")
        for item in list(cell.short_memory or [])[-4:]
        if str(item.get("summary") or "").strip()
    ) or "none"
    long_memory = " | ".join(
        str(item.get("summary") or "")
        for item in list(cell.long_memory or [])[-4:]
        if str(item.get("summary") or "").strip()
    ) or "none"
    recent_behaviors = " | ".join(
        str(item.get("summary") or item.get("event_type") or "")
        for item in list(cell.behavior_log or [])[-4:]
        if str(item.get("summary") or item.get("event_type") or "").strip()
    ) or "none"
    return build_prompt_contract(
        "agent_interview",
        [
            ("question", question),
            ("identity", f"role={cell.role_label or cell.role_key or 'agent'}; country={cell.persona_country or 'unknown'}; zone={cell.zone_label or cell.zone_id or 'zone'}"),
            ("persona", str(cell.persona_text or "")[:420]),
            ("persona_attrs", _compact(dict(cell.persona_attrs or {}))),
            ("state", _compact({
                "energy": f"{cell.energy:.2f}",
                "z": f"{cell.z:.2f}",
                "cooperation_bias": dict(cell.action_state).get("cooperation_bias", 0.5),
                "policy_sensitivity": dict(cell.action_state).get("policy_sensitivity", 0.5),
                "strategy_summary": dict(cell.action_state).get("strategy_summary", ""),
            })),
            ("recent_short_memory", short_memory[:420]),
            ("salient_long_memory", long_memory[:420]),
            ("recent_behaviors", recent_behaviors[:420]),
            ("grounding", _compact(grounding)),
        ],
    )


def build_agent_interview_diff_prompt(
    *,
    current_cell: Cell,
    base_cell: Cell,
    question: str,
    grounding: Mapping[str, Any],
) -> str:
    return build_prompt_contract(
        "agent_interview_diff",
        [
            ("question", question),
            ("identity", f"role={current_cell.role_label or current_cell.role_key or 'agent'}; country={current_cell.persona_country or 'unknown'}"),
            ("persona", str(current_cell.persona_text or "")[:420]),
            ("base_state", _compact({
                "energy": f"{base_cell.energy:.2f}",
                "z": f"{base_cell.z:.2f}",
                "strategy_summary": dict(base_cell.action_state).get("strategy_summary", ""),
                "memory": " | ".join(str(item.get('summary') or '') for item in list(base_cell.short_memory or [])[-2:] + list(base_cell.long_memory or [])[-2:] if str(item.get('summary') or '').strip())[:320],
            })),
            ("current_state", _compact({
                "energy": f"{current_cell.energy:.2f}",
                "z": f"{current_cell.z:.2f}",
                "strategy_summary": dict(current_cell.action_state).get("strategy_summary", ""),
                "memory": " | ".join(str(item.get('summary') or '') for item in list(current_cell.short_memory or [])[-2:] + list(current_cell.long_memory or [])[-2:] if str(item.get('summary') or '').strip())[:320],
            })),
            ("grounding", _compact(grounding)),
        ],
    )


def heuristic_review_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary_stats = dict(payload.get("summary_stats") or {})
    belief_drift = dict(payload.get("belief_drift") or {})
    top_group = dict((belief_drift.get("groups") or [{}])[0] or {})
    key_events = list(payload.get("key_events") or [])
    notable_agents = list(payload.get("notable_agents") or [])
    emergent = dict(payload.get("emergent_dynamics") or {})
    lineage = dict(payload.get("lineage_summary") or {})
    group_analysis = dict(payload.get("group_analysis") or {})
    mechanism = dict(payload.get("mechanism_summary") or {})
    policy_lineage = dict(payload.get("policy_lineage_bridge") or {})
    primary_chain = dict(mechanism.get("primary_chain") or {})
    causal_hypotheses = list(mechanism.get("causal_hypotheses") or [])
    dominant_bridge = dict(policy_lineage.get("dominant_bridge") or {})

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
    if primary_chain:
        causal_analysis.append(
            f"{primary_chain.get('event_name', 'event')} -> {primary_chain.get('group_label', 'group')} -> "
            f"{primary_chain.get('zone_label', 'zone')} 흐름이 이번 변화의 주된 인과 사슬입니다."
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
    if emergent:
        causal_analysis.append(
            f"장기 emergent 신호는 revolution risk={emergent.get('revolution_risk', 'low')}이며 "
            f"split/block/fracture={float(emergent.get('split_risk', 0.0)):.2f}/"
            f"{float(emergent.get('block_divergence', 0.0)):.2f}/"
            f"{float(emergent.get('cross_zone_fracture', 0.0)):.2f}입니다."
        )
    top_lineage = dict((lineage.get("tracked_roles") or [{}])[0] or {})
    if top_lineage:
        causal_analysis.append(
            f"{top_lineage.get('role_label', '핵심 집단')}은 {top_lineage.get('first_stance', 'n/a')} -> "
            f"{top_lineage.get('last_stance', 'n/a')} 경로를 보이며 transition "
            f"{int(top_lineage.get('transition_count', 0))}회, lineage score {float(top_lineage.get('lineage_score', 0.0)):.2f}입니다."
        )
    if dominant_bridge:
        causal_analysis.append(
            f"{dominant_bridge.get('event_name', 'event')}의 {dominant_bridge.get('dominant_channel', 'channel')} 채널이 "
            f"{dominant_bridge.get('role_label', 'group')}의 {dominant_bridge.get('from_stance', 'n/a')} -> "
            f"{dominant_bridge.get('to_stance', 'n/a')} 전이와 연결되며 bridge strength "
            f"{float(dominant_bridge.get('bridge_strength', 0.0)):.2f}를 보였습니다."
        )
    if causal_hypotheses:
        causal_analysis.append(str(dict(causal_hypotheses[0]).get("summary") or ""))

    decision_implications = [
        "정책 이벤트의 대상 role과 zone이 실제로 어떤 신념 이동을 만들었는지 비교 실험이 필요합니다.",
        "contest 또는 transition pressure가 큰 집단은 후속 intervention에서 불안정성이 커질 수 있습니다.",
        "fracture와 split risk가 큰 집단/지역은 별도 정책 주입 후 재실행이 필요합니다.",
        "핵심 인과 사슬에 포함된 group/zone을 우선적으로 재주입 대상으로 삼는 것이 효율적입니다.",
        "lineage score가 높은 집단은 장기적 이념 재편을 일으킬 수 있으므로 follow-up branch가 필요합니다.",
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
        "causal_analysis": causal_analysis[:6],
        "decision_implications": decision_implications[:4],
        "watch_items": watch_items,
        "citations": {
            "headline": _citation_ids(payload, "groups", limit=1),
            "key_events.0": _citation_ids(payload, "events", limit=1),
            "causal_analysis.0": _citation_ids(payload, "events", limit=1),
            "causal_analysis.1": _citation_ids(payload, "groups", limit=1) + _citation_ids(payload, "zones", limit=1),
            "causal_analysis.2": _citation_ids(payload, "groups", limit=1),
            "causal_analysis.3": _citation_ids(payload, "agents", limit=1),
            "causal_analysis.4": _citation_ids(payload, "groups", limit=1),
            "causal_analysis.5": _citation_ids(payload, "events", limit=1) + _citation_ids(payload, "groups", limit=1),
            "decision_implications.0": _citation_ids(payload, "events", limit=1),
            "decision_implications.1": _citation_ids(payload, "groups", limit=1),
            "decision_implications.2": _citation_ids(payload, "zones", limit=1),
            "decision_implications.3": _citation_ids(payload, "events", limit=1) + _citation_ids(payload, "groups", limit=1),
            "decision_implications.4": _citation_ids(payload, "groups", limit=1),
        },
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
    mechanism_delta = dict(diff_payload.get("mechanism_delta") or {})
    lineage_delta = dict(diff_payload.get("lineage_delta") or {})
    policy_lineage_delta = dict(diff_payload.get("policy_lineage_delta") or {})
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
    if mechanism_delta:
        top_chain = dict(mechanism_delta.get("target_primary_chain") or {})
        causal.append(
            f"target의 주된 메커니즘은 {top_chain.get('event_name', 'event')} -> "
            f"{top_chain.get('group_label', 'group')} -> {top_chain.get('zone_label', 'zone')} 흐름으로 요약됩니다."
        )
    top_lineage_gap = dict((lineage_delta.get("tracked_role_gaps") or [{}])[0] or {})
    if top_lineage_gap:
        causal.append(
            f"{top_lineage_gap.get('role_label', '핵심 집단')}은 baseline 대비 transition gap "
            f"{int(top_lineage_gap.get('transition_gap', 0)):+d}, lineage score gap "
            f"{float(top_lineage_gap.get('lineage_score_gap', 0.0)):+.2f}를 보였습니다."
        )
    top_bridge_gap = dict((policy_lineage_delta.get("bridge_gaps") or [{}])[0] or {})
    if top_bridge_gap:
        causal.append(
            f"{top_bridge_gap.get('event_name', 'event')}의 {top_bridge_gap.get('dominant_channel', 'channel')} 채널이 "
            f"{top_bridge_gap.get('role_label', 'group')} 전이를 baseline보다 더 강하게 밀며 bridge gap "
            f"{float(top_bridge_gap.get('bridge_strength_gap', 0.0)):+.2f}를 만들었습니다."
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
            "mechanism delta가 가장 큰 event/group/zone 조합을 중심으로 다음 what-if 실험을 설계하는 것이 좋습니다.",
        ],
        "citations": {
            "key_deltas.0": _citation_ids(diff_payload, "groups", limit=1),
            "key_deltas.1": _citation_ids(diff_payload, "groups", limit=1),
            "key_deltas.2": _citation_ids(diff_payload, "zones", limit=1),
            "causal_comparison.0": _citation_ids(diff_payload, "events", limit=1),
            "causal_comparison.1": _citation_ids(diff_payload, "groups", limit=1),
            "causal_comparison.2": _citation_ids(diff_payload, "zones", limit=1),
            "causal_comparison.3": _citation_ids(diff_payload, "events", limit=1) + _citation_ids(diff_payload, "groups", limit=1),
            "causal_comparison.4": _citation_ids(diff_payload, "groups", limit=1),
            "causal_comparison.5": _citation_ids(diff_payload, "events", limit=1) + _citation_ids(diff_payload, "groups", limit=1),
            "decision_implications.0": _citation_ids(diff_payload, "zones", limit=1),
            "decision_implications.1": _citation_ids(diff_payload, "groups", limit=1),
            "decision_implications.3": _citation_ids(diff_payload, "events", limit=1),
        },
    }


def heuristic_review_query(payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    prompt = str(question or "").strip().lower()
    belief_drift = dict(payload.get("belief_drift") or {})
    lineage = dict(payload.get("lineage_summary") or {})
    bridge = dict(payload.get("policy_lineage_bridge") or {})
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
            tracked = next(
                (item for item in list(lineage.get("tracked_roles") or []) if str(item.get("role_label") or "") == str(top_group.get("role_label") or "")),
                {},
            )
            evidence.append(
                f"group={top_group.get('role_label', 'n/a')} stance {top_group.get('stance_before', 'n/a')} -> {top_group.get('stance_after', 'n/a')}"
            )
            evidence.append(
                f"cohesion_delta={float(top_group.get('cohesion_delta', 0.0)):+.2f}, tension_delta={float(top_group.get('tension_delta', 0.0)):+.2f}, polarization_delta={float(top_group.get('polarization_delta', 0.0)):+.2f}"
            )
            if tracked:
                evidence.append(
                    f"lineage transition_count={int(tracked.get('transition_count', 0))}, lineage_score={float(tracked.get('lineage_score', 0.0)):.2f}"
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
        dominant_bridge = dict(bridge.get("dominant_bridge") or {})
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
            if dominant_bridge:
                evidence.append(
                    f"bridge={dominant_bridge.get('dominant_channel', 'channel')} -> {dominant_bridge.get('role_label', 'group')} {dominant_bridge.get('from_stance', 'n/a')}->{dominant_bridge.get('to_stance', 'n/a')}"
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
        "citations": _citation_ids(payload, "groups", limit=2) or _citation_ids(payload, "events", limit=2),
    }


def heuristic_review_diff_query(diff_payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    prompt = str(question or "").strip().lower()
    groups = list(diff_payload.get("group_drift_deltas") or [])
    zones = list(diff_payload.get("zone_z_delta") or [])
    policy = dict(diff_payload.get("policy_impact_delta") or {})
    lineage_delta = dict(diff_payload.get("lineage_delta") or {})
    policy_lineage_delta = dict(diff_payload.get("policy_lineage_delta") or {})
    top_group = dict(groups[0] if groups else {})
    top_zone = dict(zones[0] if zones else {})
    answer = "현재 diff evidence로는 질문에 대한 결정적 결론이 제한적입니다."
    evidence: list[str] = []
    if "정책" in prompt or "policy" in prompt:
        top_bridge_gap = dict((policy_lineage_delta.get("bridge_gaps") or [{}])[0] or {})
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
        if top_bridge_gap:
            evidence.append(
                f"bridge_gap={top_bridge_gap.get('dominant_channel', 'channel')}->{top_bridge_gap.get('role_label', 'group')} strength={float(top_bridge_gap.get('bridge_strength_gap', 0.0)):+.2f}"
            )
    elif "집단" in prompt or "group" in prompt or "분열" in prompt or "fracture" in prompt:
        top_lineage_gap = dict((lineage_delta.get("tracked_role_gaps") or [{}])[0] or {})
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
        if top_lineage_gap:
            evidence.append(
                f"lineage transition_gap={int(top_lineage_gap.get('transition_gap', 0)):+d}, lineage_score_gap={float(top_lineage_gap.get('lineage_score_gap', 0.0)):+.2f}"
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
        "citations": _citation_ids(diff_payload, "groups", limit=2) or _citation_ids(diff_payload, "events", limit=2),
    }


def heuristic_session_review(payload: Mapping[str, Any]) -> dict[str, Any]:
    strongest = list(payload.get("strongest_worlds") or [])
    top = dict(strongest[0] if strongest else {})
    stats = dict(payload.get("summary_stats") or {})
    lineage = dict(payload.get("lineage_summary") or {})
    policy_lineage = dict(payload.get("policy_lineage_bridge") or {})
    objective_explanation = str(payload.get("objective_explanation") or "")
    dominant_bridge = dict(policy_lineage.get("dominant_event_role") or {})
    return {
        "headline": f"Session with {int(stats.get('world_count', 0))} worlds and avg split risk {float(stats.get('avg_split_risk', 0.0)):.2f}",
        "executive_summary": (
            f"이 세션은 {int(stats.get('world_count', 0))}개의 world를 포함하며, "
            f"평균 split risk {float(stats.get('avg_split_risk', 0.0)):.2f}, "
            f"평균 block divergence {float(stats.get('avg_block_divergence', 0.0)):.2f}, "
            f"평균 cross-zone fracture {float(stats.get('avg_cross_zone_fracture', 0.0)):.2f}를 보였습니다. "
            f"세션 전반의 regime transition은 {str(lineage.get('dominant_regime_transition') or 'stable')}입니다."
        ),
        "key_findings": [
            f"가장 극적인 world는 {top.get('world_id', 'n/a')}이며 signal={top.get('overall_signal', 'diffuse')}입니다.",
            "세션 단위에서는 split risk와 cross-zone fracture가 높은 world를 우선 비교하는 것이 좋습니다.",
            f"lineage 관점에서는 {str(((lineage.get('tracked_roles') or [{}])[0] or {}).get('role_label') or '핵심 집단')}이 가장 자주 재편됩니다.",
            f"정책-전이 관점에서는 {dominant_bridge.get('event_name', 'event')} / {dominant_bridge.get('role_label', 'group')} 조합이 가장 자주 반복됩니다.",
        ],
        "decision_implications": [
            "같은 세션 내 strongest world와 baseline world를 붙여보면 정책 민감도 차이가 더 잘 드러납니다.",
            "fracture score가 높은 world는 후속 intervention 실험의 우선 후보입니다.",
            "lineage score가 높은 역할 집단은 장기 정책 실험에서 별도 추적 대상으로 삼는 것이 좋습니다.",
        ],
        "objective_explanation": objective_explanation,
        "citations": {
            "key_findings.0": _citation_ids(payload, "worlds", limit=1),
            "key_findings.1": _citation_ids(payload, "worlds", limit=1),
            "key_findings.2": _citation_ids(payload, "worlds", limit=1),
            "key_findings.3": _citation_ids(payload, "worlds", limit=1),
            "decision_implications.0": _citation_ids(payload, "worlds", limit=1),
            "decision_implications.1": _citation_ids(payload, "worlds", limit=1),
            "decision_implications.2": _citation_ids(payload, "worlds", limit=1),
        },
    }


def heuristic_session_review_query(payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    strongest = list(payload.get("strongest_worlds") or [])
    top = dict(strongest[0] if strongest else {})
    answer = (
        f"세션에서 가장 주목할 world는 {top.get('world_id', 'n/a')}입니다. "
        f"split risk {float(top.get('split_risk', 0.0)):.2f}, "
        f"block divergence {float(top.get('block_divergence', 0.0)):.2f}, "
        f"cross-zone fracture {float(top.get('cross_zone_fracture', 0.0)):.2f}가 가장 높았습니다."
    )
    return {
        "answer": answer,
        "evidence": [
            f"world={top.get('world_id', 'n/a')} signal={top.get('overall_signal', 'diffuse')}",
            f"split_risk={float(top.get('split_risk', 0.0)):.2f}, cross_zone_fracture={float(top.get('cross_zone_fracture', 0.0)):.2f}",
        ],
        "follow_up": [
            "이 world를 baseline world와 diff report로 다시 비교해보는 것이 좋습니다.",
            "session strongest worlds 사이의 policy target 차이를 확인해보세요.",
        ],
        "confidence_notes": ["heuristic session query used"],
        "citations": _citation_ids(payload, "worlds", limit=2),
    }


def heuristic_agent_interview(
    *,
    cell: Cell,
    question: str,
    grounding: Mapping[str, Any],
) -> dict[str, Any]:
    role = str(cell.role_label or cell.role_key or "agent")
    strategy = str(dict(cell.action_state).get("strategy_summary") or "current_state_reflection")
    memory_lines = [
        str(item.get("summary") or "")
        for item in list(cell.short_memory or [])[-2:] + list(cell.long_memory or [])[-2:]
        if str(item.get("summary") or "").strip()
    ]
    memory_clause = memory_lines[0] if memory_lines else "최근 상호작용과 기억을 바탕으로 판단하고 있습니다."
    persona = str(cell.persona_text or "").strip()
    persona_clause = persona[:140] if persona else f"{role} 역할의 관점에서 생각하고 있습니다."
    answer = (
        f"저는 {role}로서 {persona_clause} "
        f"지금은 {strategy} 방향으로 움직이고 있고, {memory_clause} "
        f"질문하신 내용에 대해서는 제 현재 기억과 위치에서 그렇게 판단합니다."
    )
    evidence = [
        f"role={role}, zone={cell.zone_label or cell.zone_id or 'zone'}, z={float(cell.z):.2f}",
        f"strategy={strategy}",
    ]
    if memory_lines:
        evidence.append(memory_lines[0])
    return {
        "answer": answer,
        "evidence": evidence[:4],
        "confidence_notes": ["heuristic agent interview used"],
        "citations": _citation_ids(grounding, "memories", limit=2) or _citation_ids(grounding, "persona", limit=1),
    }


def heuristic_agent_interview_diff(
    *,
    current_cell: Cell,
    base_cell: Cell,
    question: str,
    grounding: Mapping[str, Any],
) -> dict[str, Any]:
    role = str(current_cell.role_label or current_cell.role_key or "agent")
    energy_delta = float(current_cell.energy) - float(base_cell.energy)
    z_delta = float(current_cell.z) - float(base_cell.z)
    current_strategy = str(dict(current_cell.action_state).get("strategy_summary") or "current_state")
    base_strategy = str(dict(base_cell.action_state).get("strategy_summary") or "prior_state")
    answer = (
        f"저는 {role}로서 이전보다 에너지가 {energy_delta:+.2f}, social elevation이 {z_delta:+.2f} 변했습니다. "
        f"예전에는 {base_strategy} 쪽에 가까웠다면 지금은 {current_strategy} 쪽으로 이동했습니다."
    )
    return {
        "answer": answer,
        "evidence": [
            f"energy_delta={energy_delta:+.2f}, z_delta={z_delta:+.2f}",
            f"strategy {base_strategy} -> {current_strategy}",
        ],
        "confidence_notes": ["heuristic agent diff used"],
        "citations": _citation_ids(grounding, "base_state", limit=1) + _citation_ids(grounding, "current_state", limit=1),
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
        "citations": _validated_citation_map(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(payload),
            required_keys=(
                "headline",
                "key_events.0",
                "causal_analysis.0",
                "decision_implications.0",
            ),
        ),
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
        "citations": _validated_citation_map(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(diff_payload),
            required_keys=(
                "key_deltas.0",
                "causal_comparison.0",
                "decision_implications.0",
            ),
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
        "citations": _validated_citation_list(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(payload),
        ),
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
        "citations": _validated_citation_list(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(diff_payload),
        ),
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
        "objective_explanation": str(parsed.get("objective_explanation") or fallback.get("objective_explanation") or ""),
        "citations": _validated_citation_map(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(payload),
            required_keys=(
                "key_findings.0",
                "decision_implications.0",
            ),
        ),
    }


def parse_session_review_query(raw_text: str, payload: Mapping[str, Any], question: str) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_session_review_query(payload, question)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_session_review_query(payload, question)
    fallback = heuristic_session_review_query(payload, question)
    return {
        "answer": str(parsed.get("answer") or fallback["answer"]),
        "evidence": _string_list(parsed.get("evidence"), fallback["evidence"]),
        "follow_up": _string_list(parsed.get("follow_up"), fallback["follow_up"]),
        "confidence_notes": _string_list(parsed.get("confidence_notes"), fallback["confidence_notes"]),
        "citations": _validated_citation_list(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(payload),
        ),
    }


def parse_agent_interview(
    raw_text: str,
    *,
    cell: Cell,
    question: str,
    grounding: Mapping[str, Any],
) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_agent_interview(cell=cell, question=question, grounding=grounding)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_agent_interview(cell=cell, question=question, grounding=grounding)
    fallback = heuristic_agent_interview(cell=cell, question=question, grounding=grounding)
    return {
        "answer": str(parsed.get("answer") or fallback["answer"]),
        "evidence": _string_list(parsed.get("evidence"), fallback["evidence"]),
        "confidence_notes": _string_list(parsed.get("confidence_notes"), fallback["confidence_notes"]),
        "citations": _validated_citation_list(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(grounding),
        ),
    }


def parse_agent_interview_diff(
    raw_text: str,
    *,
    current_cell: Cell,
    base_cell: Cell,
    question: str,
    grounding: Mapping[str, Any],
) -> dict[str, Any]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_agent_interview_diff(
            current_cell=current_cell,
            base_cell=base_cell,
            question=question,
            grounding=grounding,
        )
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_agent_interview_diff(
            current_cell=current_cell,
            base_cell=base_cell,
            question=question,
            grounding=grounding,
        )
    fallback = heuristic_agent_interview_diff(
        current_cell=current_cell,
        base_cell=base_cell,
        question=question,
        grounding=grounding,
    )
    return {
        "answer": str(parsed.get("answer") or fallback["answer"]),
        "evidence": _string_list(parsed.get("evidence"), fallback["evidence"]),
        "confidence_notes": _string_list(parsed.get("confidence_notes"), fallback["confidence_notes"]),
        "citations": _validated_citation_list(
            parsed.get("citations"),
            fallback["citations"],
            allowed_ids=_allowed_anchor_ids(grounding),
        ),
    }


def needs_citation_repair(
    raw_text: str,
    *,
    grounding: Mapping[str, Any],
    citation_mode: str,
    required_keys: Sequence[str] = (),
) -> tuple[bool, str]:
    parsed = _parse_json_object(raw_text)
    if parsed is None:
        return True, "json_decode_failed"
    citations = parsed.get("citations")
    allowed_ids = _allowed_anchor_ids(grounding)
    if citation_mode == "map":
        if not isinstance(citations, Mapping):
            return True, "missing_citation_map"
        for key in required_keys:
            rows = citations.get(str(key))
            if not isinstance(rows, list):
                return True, f"missing_required_key:{key}"
            valid = [str(item).strip() for item in rows if str(item).strip() in allowed_ids]
            if not valid:
                return True, f"invalid_required_anchor:{key}"
        for key, rows in citations.items():
            if not isinstance(rows, list):
                return True, f"invalid_citation_shape:{key}"
            invalid = [str(item).strip() for item in rows if str(item).strip() and str(item).strip() not in allowed_ids]
            if invalid:
                return True, f"invalid_anchor_id:{key}"
        return False, ""
    if not isinstance(citations, list):
        return True, "missing_citation_list"
    valid = [str(item).strip() for item in citations if str(item).strip() in allowed_ids]
    if not valid:
        return True, "invalid_or_empty_citation_list"
    invalid = [str(item).strip() for item in citations if str(item).strip() and str(item).strip() not in allowed_ids]
    if invalid:
        return True, "invalid_anchor_id:list"
    return False, ""


def _compact(mapping: Mapping[str, Any]) -> str:
    return "; ".join(f"{key}={value}" for key, value in mapping.items())[:1800]


def _compact_list(items: list[Any], *, limit: int) -> str:
    sliced = items[:limit]
    return " | ".join(_compact(item) if isinstance(item, Mapping) else str(item) for item in sliced)[:1800]


def _compact_anchor_candidates(grounding: Mapping[str, Any]) -> str:
    candidates: list[str] = []
    for section, rows in dict(grounding or {}).items():
        for row in list(rows or [])[:3]:
            anchor_id = str(row.get("anchor_id") or "").strip()
            if not anchor_id:
                continue
            label = str(row.get("label") or row.get("role_label") or row.get("zone_label") or row.get("name") or section[:-1] or "evidence").strip()
            reason = str(row.get("reason") or row.get("summary") or "").strip()
            snippet = f"{anchor_id}::{label}"
            if reason:
                snippet += f"::{reason[:80]}"
            candidates.append(snippet)
    return " | ".join(candidates[:18])[:1800]


def _compact_sentence_anchor_hints(
    grounding: Mapping[str, Any],
    required_keys: Sequence[str],
    *,
    citation_mode: str,
) -> str:
    if citation_mode == "list":
        ids = (
            _citation_ids(grounding, "groups", limit=2)
            + _citation_ids(grounding, "events", limit=2)
            + _citation_ids(grounding, "zones", limit=1)
        )
        return "citations -> " + ", ".join(ids[:5])
    hints: list[str] = []
    for key in required_keys:
        section = str(key).split(".", 1)[0]
        if section == "headline":
            candidates = _citation_ids(grounding, "groups", limit=1) + _citation_ids(grounding, "events", limit=1)
        elif "event" in section:
            candidates = _citation_ids(grounding, "events", limit=2)
        elif "causal" in section:
            candidates = _citation_ids(grounding, "events", limit=1) + _citation_ids(grounding, "groups", limit=1)
        elif "decision" in section:
            candidates = _citation_ids(grounding, "groups", limit=1) + _citation_ids(grounding, "zones", limit=1)
        elif "key_findings" in section:
            candidates = _citation_ids(grounding, "worlds", limit=2) or _citation_ids(grounding, "groups", limit=2)
        else:
            candidates = _citation_ids(grounding, "groups", limit=1)
        if candidates:
            hints.append(f"{key} -> {', '.join(candidates[:3])}")
    return " | ".join(hints)[:1800]


def _repair_focus_instructions(reason: str, *, citation_mode: str) -> str:
    normalized = str(reason or "").strip()
    if normalized.startswith("missing_required_key:"):
        return (
            "Fill every missing required sentence key. Preserve the original analysis text. "
            "For each required key, attach at least one valid anchor id from the hinted candidates."
        )
    if normalized.startswith("invalid_required_anchor:") or normalized.startswith("invalid_anchor_id:"):
        return (
            "Replace invalid anchor ids only. Keep the sentence structure stable, but swap every invalid id with the closest valid candidate."
        )
    if normalized == "missing_citation_map":
        return (
            "Rebuild the citations object as a sentence-key map. Do not rewrite the analysis unless needed for valid compact JSON."
        )
    if normalized == "invalid_or_empty_citation_list":
        return (
            "Rebuild citations as a non-empty list using only valid anchor ids. Prefer group/event anchors before others."
        )
    if normalized == "json_decode_failed":
        return (
            "Reconstruct the compact JSON faithfully from the broken output. Keep the original meaning, but ensure valid JSON and valid citations."
        )
    return (
        "Repair citations using only valid anchor ids from the provided candidate list. "
        f"Keep citation_mode={citation_mode}."
    )


def _string_list(value: Any, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    cleaned = [str(item).strip() for item in value if str(item).strip()]
    return cleaned[:6] or list(fallback)


def _citation_ids(payload: Mapping[str, Any], section: str, *, limit: int) -> list[str]:
    grounding = dict(payload.get("grounding") or payload or {})
    rows = list(grounding.get(section) or [])
    out = [str(item.get("anchor_id") or "") for item in rows if str(item.get("anchor_id") or "").strip()]
    return out[:limit]


def _citation_map(value: Any, fallback: dict[str, list[str]]) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        return dict(fallback)
    cleaned: dict[str, list[str]] = {}
    for key, rows in value.items():
        if isinstance(rows, list):
            items = [str(item).strip() for item in rows if str(item).strip()]
            if items:
                cleaned[str(key)] = items[:6]
    return cleaned or dict(fallback)


def _allowed_anchor_ids(payload: Mapping[str, Any]) -> set[str]:
    grounding = dict(payload.get("grounding") or payload or {})
    out: set[str] = set()
    for rows in grounding.values():
        for row in list(rows or []):
            anchor_id = str(row.get("anchor_id") or "").strip()
            if anchor_id:
                out.add(anchor_id)
    return out


def _validated_citation_map(
    value: Any,
    fallback: dict[str, list[str]],
    *,
    allowed_ids: set[str],
    required_keys: tuple[str, ...] = (),
) -> dict[str, list[str]]:
    cleaned = _citation_map(value, fallback)
    out: dict[str, list[str]] = {}
    for key, rows in cleaned.items():
        valid = [item for item in rows if item in allowed_ids]
        if valid:
            out[str(key)] = valid[:6]
    for key, rows in fallback.items():
        valid = [item for item in rows if item in allowed_ids]
        if not valid:
            continue
        if key in required_keys or key not in out:
            out.setdefault(key, valid[:6])
    return out or {
        key: [item for item in rows if item in allowed_ids][:6]
        for key, rows in fallback.items()
        if any(item in allowed_ids for item in rows)
    }


def _validated_citation_list(value: Any, fallback: list[str], *, allowed_ids: set[str]) -> list[str]:
    candidate = _string_list(value, fallback)
    valid = [item for item in candidate if item in allowed_ids]
    if valid:
        return valid[:6]
    fallback_valid = [item for item in fallback if item in allowed_ids]
    return fallback_valid[:6]


def _severity(score: float) -> str:
    if score >= 1.45:
        return "high"
    if score >= 0.9:
        return "medium"
    return "low"


def _parse_json_object(raw_text: str) -> dict[str, Any] | None:
    text = str(raw_text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None
