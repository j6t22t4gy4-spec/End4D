"""Structured review payload builders for post-simulation analysis."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from app.models.cell import Cell
from app.models.world import Snapshot

MAX_REVIEW_GROUPS = 10
MAX_REVIEW_ZONES = 10
MAX_REVIEW_AGENTS = 12
MAX_REVIEW_EVENTS = 8
MAX_REVIEW_HIGHLIGHTS = 6
MAX_REVIEW_ANNOTATIONS = 8
MAX_REVIEW_GRAPH_EDGES = 18


def _entry_world_id(entry: dict[str, Any]) -> str:
    world = entry.get("world")
    if world is None:
        return ""
    if isinstance(world, dict):
        return str(world.get("world_id") or "")
    return str(getattr(world, "world_id", "") or "")


def build_cached_world_review_payload(entry: dict[str, Any]) -> dict[str, Any]:
    store = entry["snapshot_store"]
    available_t = list(store.list_t())
    key = (
        tuple(available_t[-3:]),
        len(available_t),
        len(list(entry["world"].nutrients or [])),
        len(list(entry.get("coalition_history") or [])),
    )
    cache = dict(entry.get("_review_payload_cache") or {})
    if cache.get("key") == key and isinstance(cache.get("payload"), dict):
        return dict(cache["payload"])
    payload = build_world_review_payload(entry)
    entry["_review_payload_cache"] = {"key": key, "payload": payload}
    return payload


def build_cached_session_review_payload(
    session: dict[str, Any],
    world_entries: list[dict[str, Any]],
    *,
    objective: str = "balanced",
) -> dict[str, Any]:
    world_ids = tuple(_entry_world_id(entry) for entry in world_entries if entry is not None)
    key = (world_ids, objective, len(world_ids))
    cache = dict(session.get("_session_review_payload_cache") or {})
    if cache.get("key") == key and isinstance(cache.get("payload"), dict):
        return dict(cache["payload"])
    payload = build_session_review_payload(session, world_entries, objective=objective)
    session["_session_review_payload_cache"] = {"key": key, "payload": payload}
    return payload


def build_world_review_payload(entry: dict[str, Any]) -> dict[str, Any]:
    world = entry["world"]
    store = entry["snapshot_store"]
    available_t = list(store.list_t())
    if not available_t:
        raise ValueError("No snapshots available")

    first = store.get(available_t[0])
    latest = store.get(available_t[-1])
    if first is None or latest is None:
        raise ValueError("Snapshot data incomplete")

    timeline_points = [_timeline_point(store.get(t)) for t in available_t if store.get(t) is not None]
    first_groups = _group_snapshot(first)
    latest_groups = _group_snapshot(latest)
    belief_drift = _belief_drift_summary(
        first_groups,
        latest_groups,
        coalition_state=dict(entry.get("coalition_state") or {}),
    )
    zone_z_drift = _zone_z_drift(first, latest)
    notable_agents = _notable_agents(first, latest)
    key_events = [_event_summary(event) for event in list(world.nutrients or [])[-MAX_REVIEW_EVENTS:]]
    summary_stats = {
        "initial_cell_count": len(first.cells),
        "final_cell_count": len(latest.cells),
        "cell_delta": len(latest.cells) - len(first.cells),
        "initial_total_energy": _total_energy(first.cells),
        "final_total_energy": _total_energy(latest.cells),
        "energy_delta": _total_energy(latest.cells) - _total_energy(first.cells),
        "initial_avg_z": _avg_z(first.cells),
        "final_avg_z": _avg_z(latest.cells),
        "z_delta": _avg_z(latest.cells) - _avg_z(first.cells),
        "first_t": float(first.t),
        "last_t": float(latest.t),
        "points_count": len(timeline_points),
        "overall_signal": belief_drift["overall_signal"],
        "outcome": _classify_outcome(timeline_points),
    }
    policy_impact = _policy_impact_summary(key_events, belief_drift["groups"], zone_z_drift)
    policy_mechanisms = _policy_mechanism_summary(key_events, belief_drift["groups"], zone_z_drift)
    group_analysis = _group_analysis_summary(belief_drift, zone_z_drift)
    group_tables = _group_tables_summary(belief_drift, zone_z_drift, notable_agents)
    lineage_summary = _lineage_summary(store=store, available_t=available_t, belief_drift=belief_drift)
    emergent_dynamics = _emergent_dynamics_summary(
        timeline_points=timeline_points,
        belief_drift=belief_drift,
        key_events=key_events,
        lineage_summary=lineage_summary,
    )
    mechanism_summary = _mechanism_summary(
        summary_stats=summary_stats,
        key_events=key_events,
        belief_drift=belief_drift,
        zone_z_drift=zone_z_drift,
        notable_agents=notable_agents,
        group_analysis=group_analysis,
        emergent_dynamics=emergent_dynamics,
    )
    highlights = _build_highlights(
        summary_stats=summary_stats,
        belief_drift=belief_drift,
        zone_z_drift=zone_z_drift,
        notable_agents=notable_agents,
        key_events=key_events,
    )

    return {
        "world_id": str(world.world_id),
        "timeline": {
            "first_t": float(first.t),
            "last_t": float(latest.t),
            "points_count": len(timeline_points),
            "points": timeline_points,
            "outcome": summary_stats["outcome"],
        },
        "world_meta": {
            "genesis_prompt": str(entry.get("genesis_prompt") or ""),
            "persona_country": str(entry.get("persona_country") or ""),
            "config_version": str(entry.get("config_version") or ""),
            "session_id": str(entry.get("session_id") or ""),
            "role_catalog": list(entry.get("role_catalog") or []),
            "engine_params": dict(entry.get("engine_params") or {}),
        },
        "summary_stats": summary_stats,
        "belief_drift": belief_drift,
        "group_analysis": group_analysis,
        "group_tables": group_tables,
        "lineage_summary": lineage_summary,
        "emergent_dynamics": emergent_dynamics,
        "mechanism_summary": mechanism_summary,
        "policy_impact": policy_impact,
        "policy_mechanisms": policy_mechanisms,
        "key_events": key_events,
        "notable_agents": notable_agents,
        "zone_z_drift": zone_z_drift,
        "belief_graph": _build_belief_graph(belief_drift),
        "grounding": _build_grounding(
            key_events=key_events,
            belief_drift=belief_drift,
            zone_z_drift=zone_z_drift,
            notable_agents=notable_agents,
            world_id=str(world.world_id),
        ),
        "causal_chains": _build_causal_chains(
            world_id=str(world.world_id),
            key_events=key_events,
            groups=list(belief_drift.get("groups") or []),
            zone_z_drift=zone_z_drift,
            notable_agents=notable_agents,
        ),
        "coalition_shift": {
            "active": dict(entry.get("coalition_state") or {}),
            "history_tail": [dict(item) for item in list(entry.get("coalition_history") or [])[-8:]],
        },
        "highlights": highlights[:MAX_REVIEW_HIGHLIGHTS],
        "annotation_candidates": build_timeline_annotation_candidates(timeline_points, key_events=key_events)[
            :MAX_REVIEW_ANNOTATIONS
        ],
        "legacy_metrics": summary_stats,
    }


def build_session_review_payload(
    session: dict[str, Any],
    world_entries: list[dict[str, Any]],
    *,
    objective: str = "balanced",
) -> dict[str, Any]:
    world_payloads = [build_cached_world_review_payload(entry) for entry in world_entries if entry]
    if not world_payloads:
        raise ValueError("No completed worlds available for session review")
    outcomes = [str((payload.get("summary_stats") or {}).get("outcome") or "stable") for payload in world_payloads]
    signals = [str((payload.get("belief_drift") or {}).get("overall_signal") or "diffuse") for payload in world_payloads]
    split_risks = [float((payload.get("belief_drift") or {}).get("overall_split_risk") or 0.0) for payload in world_payloads]
    block_divergences = [float((payload.get("belief_drift") or {}).get("overall_block_divergence") or 0.0) for payload in world_payloads]
    fracture_scores = [float((payload.get("belief_drift") or {}).get("overall_cross_zone_fracture") or 0.0) for payload in world_payloads]
    ranked = sorted(world_payloads, key=lambda payload: _session_objective_score(payload, objective), reverse=True)
    ranked_worlds = [
        {
            "world_id": str(payload.get("world_id") or ""),
            "outcome": str((payload.get("summary_stats") or {}).get("outcome") or "stable"),
            "overall_signal": str((payload.get("belief_drift") or {}).get("overall_signal") or "diffuse"),
            "split_risk": float((payload.get("belief_drift") or {}).get("overall_split_risk") or 0.0),
            "block_divergence": float((payload.get("belief_drift") or {}).get("overall_block_divergence") or 0.0),
            "cross_zone_fracture": float((payload.get("belief_drift") or {}).get("overall_cross_zone_fracture") or 0.0),
            "score": round(
                _session_objective_score(payload, objective),
                3,
            ),
        }
        for payload in ranked
    ]
    recommended_pairs: list[dict[str, Any]] = []
    for idx, left in enumerate(ranked_worlds[:4]):
        for right in ranked_worlds[idx + 1 : 5]:
            recommended_pairs.append(
                {
                    "base_world_id": str(right.get("world_id") or ""),
                    "target_world_id": str(left.get("world_id") or ""),
                    "objective": objective,
                    "score_gap": round(
                        abs(float(left.get("score", 0.0)) - float(right.get("score", 0.0))),
                        3,
                    ),
                    "reason": (
                        f"score gap {abs(float(left.get('score', 0.0)) - float(right.get('score', 0.0))):.2f}; "
                        f"signal {left.get('overall_signal', 'diffuse')} vs {right.get('overall_signal', 'diffuse')}"
                    ),
                    "recommendation": _pair_recommendation(
                        objective=objective,
                        target=dict(left),
                        base=dict(right),
                    ),
                }
            )
    recommended_pairs.sort(key=lambda item: abs(next((float(w["score"]) for w in ranked_worlds if w["world_id"] == item["target_world_id"]), 0.0) - next((float(w["score"]) for w in ranked_worlds if w["world_id"] == item["base_world_id"]), 0.0)), reverse=True)
    return {
        "session_id": str(session.get("session_id") or ""),
        "title": str(session.get("title") or "Session"),
        "world_count": len(world_payloads),
        "world_ids": [str(payload.get("world_id") or "") for payload in world_payloads],
        "summary_stats": {
            "world_count": len(world_payloads),
            "objective": objective,
            "dominant_outcomes": outcomes[:6],
            "dominant_signals": signals[:6],
            "avg_split_risk": round(float(np.mean(split_risks)) if split_risks else 0.0, 3),
            "avg_block_divergence": round(float(np.mean(block_divergences)) if block_divergences else 0.0, 3),
            "avg_cross_zone_fracture": round(float(np.mean(fracture_scores)) if fracture_scores else 0.0, 3),
        },
        "objective_explanation": _objective_explanation(
            objective=objective,
            strongest=ranked_worlds[:3],
            summary_stats={
                "avg_split_risk": round(float(np.mean(split_risks)) if split_risks else 0.0, 3),
                "avg_block_divergence": round(float(np.mean(block_divergences)) if block_divergences else 0.0, 3),
                "avg_cross_zone_fracture": round(float(np.mean(fracture_scores)) if fracture_scores else 0.0, 3),
            },
        ),
        "strongest_worlds": ranked_worlds[:5],
        "ranked_worlds": ranked_worlds[:8],
        "recommended_pairs": recommended_pairs[:5],
        "group_tables": _session_group_tables(world_payloads),
        "grounding": {
            "worlds": [
                {
                    "anchor_id": f"world:{str(payload.get('world_id') or '')}",
                    "kind": "world",
                    "label": str(payload.get("world_id") or ""),
                    "reason": str((payload.get("summary_stats") or {}).get("outcome") or "stable"),
                    "world_id": str(payload.get("world_id") or ""),
                }
                for payload in ranked[:5]
            ]
        },
        "causal_chains": [
            {
                "anchor_id": f"world:{str(item.get('world_id') or '')}",
                "world_id": str(item.get("world_id") or ""),
                "label": f"{str(item.get('world_id') or '')} ranked for {objective}",
                "reason": str(item.get("overall_signal") or "diffuse"),
                "score": float(item.get("score") or 0.0),
            }
            for item in ranked_worlds[:5]
        ],
    }


def _session_objective_score(payload: dict[str, Any], objective: str) -> float:
    belief = dict(payload.get("belief_drift") or {})
    split_risk = float(belief.get("overall_split_risk") or 0.0)
    block_divergence = float(belief.get("overall_block_divergence") or 0.0)
    cross_zone_fracture = float(belief.get("overall_cross_zone_fracture") or 0.0)
    cohesion = float(belief.get("overall_cohesion") or 0.0)
    polarization = float(belief.get("overall_polarization") or 0.0)
    if objective == "stability":
        return (1.0 - split_risk) * 0.45 + (1.0 - cross_zone_fracture) * 0.35 + cohesion * 0.2
    if objective == "cohesion":
        return cohesion * 0.55 + (1.0 - polarization) * 0.2 + (1.0 - split_risk) * 0.25
    if objective == "polarization":
        return polarization * 0.6 + block_divergence * 0.25 + split_risk * 0.15
    if objective == "fracture":
        return cross_zone_fracture * 0.5 + split_risk * 0.3 + block_divergence * 0.2
    return split_risk + block_divergence + cross_zone_fracture


def _objective_explanation(
    *,
    objective: str,
    strongest: list[dict[str, Any]],
    summary_stats: dict[str, float],
) -> str:
    leader = dict(strongest[0] if strongest else {})
    world_id = str(leader.get("world_id") or "n/a")
    if objective == "stability":
        return (
            f"`{world_id}`가 split risk와 cross-zone fracture를 가장 잘 억제해 안정성 기준에서 상위에 올랐습니다. "
            f"세션 평균 split risk는 {float(summary_stats.get('avg_split_risk', 0.0)):.2f}입니다."
        )
    if objective == "cohesion":
        return (
            f"`{world_id}`가 높은 응집과 낮은 분열 신호를 동시에 보여 cohesion 기준에서 우선 추천됩니다. "
            f"세션 평균 fracture는 {float(summary_stats.get('avg_cross_zone_fracture', 0.0)):.2f}입니다."
        )
    if objective == "polarization":
        return (
            f"`{world_id}`가 가장 강한 polarization/block divergence 신호를 보여, 극화 분석 기준에서 가장 해석 가치가 큽니다."
        )
    if objective == "fracture":
        return (
            f"`{world_id}`가 cross-zone fracture와 split risk가 가장 높아, 사회적 균열을 추적하는 기준에서 최우선 비교 대상으로 잡힙니다."
        )
    return (
        f"`{world_id}`가 split risk, block divergence, cross-zone fracture를 종합했을 때 가장 두드러져 balanced 기준의 대표 world로 선정되었습니다."
    )


def _pair_recommendation(
    *,
    objective: str,
    target: dict[str, Any],
    base: dict[str, Any],
) -> str:
    target_id = str(target.get("world_id") or "target")
    base_id = str(base.get("world_id") or "base")
    if objective == "stability":
        return (
            f"`{target_id}`와 `{base_id}`를 비교하면 split risk 억제와 zone fracture 완화 전략 차이를 가장 잘 볼 수 있습니다."
        )
    if objective == "cohesion":
        return (
            f"`{target_id}`와 `{base_id}`를 비교하면 응집 유지와 긴장 완화가 어떤 설계 차이에서 갈렸는지 읽기 좋습니다."
        )
    if objective == "polarization":
        return (
            f"`{target_id}`와 `{base_id}`를 비교하면 ideology block divergence와 극화 신호 차이를 가장 선명하게 확인할 수 있습니다."
        )
    if objective == "fracture":
        return (
            f"`{target_id}`와 `{base_id}`를 비교하면 cross-zone fracture와 sub-coalition split이 어디서 벌어졌는지 직접 추적하기 좋습니다."
        )
    return (
        f"`{target_id}`와 `{base_id}`를 비교하면 split risk, block divergence, cross-zone fracture의 종합 차이를 가장 넓게 해석할 수 있습니다."
    )


def build_review_diff_payload(
    *,
    base_payload: dict[str, Any],
    target_payload: dict[str, Any],
) -> dict[str, Any]:
    base_stats = dict(base_payload.get("summary_stats") or {})
    target_stats = dict(target_payload.get("summary_stats") or {})
    base_groups = {
        str(item.get("group_id") or ""): dict(item)
        for item in list((base_payload.get("belief_drift") or {}).get("groups") or [])
    }
    target_groups = {
        str(item.get("group_id") or ""): dict(item)
        for item in list((target_payload.get("belief_drift") or {}).get("groups") or [])
    }
    base_zones = {
        str(item.get("zone_id") or ""): dict(item)
        for item in list(base_payload.get("zone_z_drift") or [])
    }
    target_zones = {
        str(item.get("zone_id") or ""): dict(item)
        for item in list(target_payload.get("zone_z_drift") or [])
    }

    group_drift_deltas: list[dict[str, Any]] = []
    for group_id, target_group in target_groups.items():
        base_group = dict(base_groups.get(group_id) or {})
        group_drift_deltas.append(
            {
                "group_id": group_id,
                "role_label": str(target_group.get("role_label") or base_group.get("role_label") or "group"),
                "stance_base": str(base_group.get("stance_after") or base_group.get("stance_before") or "not_present"),
                "stance_target": str(target_group.get("stance_after") or target_group.get("stance_before") or "not_present"),
                "cohesion_gap": round(float(target_group.get("cohesion_after", 0.0)) - float(base_group.get("cohesion_after", 0.0)), 3),
                "tension_gap": round(float(target_group.get("tension_after", 0.0)) - float(base_group.get("tension_after", 0.0)), 3),
                "z_gap": round(float(target_group.get("avg_z_delta", 0.0)) - float(base_group.get("avg_z_delta", 0.0)), 3),
                "cell_gap": int(target_group.get("cell_delta", 0)) - int(base_group.get("cell_delta", 0)),
                "worldview_gap": round(float(target_group.get("worldview_norm_delta", 0.0)) - float(base_group.get("worldview_norm_delta", 0.0)), 3),
                "split_risk_gap": round(float(target_group.get("sub_coalition_split_risk", 0.0)) - float(base_group.get("sub_coalition_split_risk", 0.0)), 3),
                "block_divergence_gap": round(float(target_group.get("ideology_block_divergence", 0.0)) - float(base_group.get("ideology_block_divergence", 0.0)), 3),
                "cross_zone_fracture_gap": round(float(target_group.get("cross_zone_group_fracture", 0.0)) - float(base_group.get("cross_zone_group_fracture", 0.0)), 3),
            }
        )
    group_drift_deltas.sort(
        key=lambda item: (
            abs(float(item["cohesion_gap"]))
            + abs(float(item["tension_gap"]))
            + abs(float(item["z_gap"]))
            + abs(float(item["split_risk_gap"]))
            + abs(float(item["block_divergence_gap"]))
            + abs(float(item["cross_zone_fracture_gap"]))
        ),
        reverse=True,
    )

    zone_z_delta: list[dict[str, Any]] = []
    for zone_id, target_zone in target_zones.items():
        base_zone = dict(base_zones.get(zone_id) or {})
        zone_z_delta.append(
            {
                "zone_id": zone_id,
                "zone_label": str(target_zone.get("zone_label") or base_zone.get("zone_label") or "zone"),
                "avg_z_gap": round(float(target_zone.get("avg_z_delta", 0.0)) - float(base_zone.get("avg_z_delta", 0.0)), 3),
                "avg_energy_gap": round(float(target_zone.get("avg_energy_after", 0.0)) - float(base_zone.get("avg_energy_after", 0.0)), 3),
                "cell_count_gap": int(target_zone.get("cell_count_after", 0)) - int(base_zone.get("cell_count_after", 0)),
            }
        )
    zone_z_delta.sort(key=lambda item: abs(float(item["avg_z_gap"])), reverse=True)

    base_policy = dict(base_payload.get("policy_impact") or {})
    target_policy = dict(target_payload.get("policy_impact") or {})
    base_roles = [str(item) for item in list(base_policy.get("dominant_target_roles") or []) if str(item).strip()]
    target_roles = [str(item) for item in list(target_policy.get("dominant_target_roles") or []) if str(item).strip()]
    base_zones_policy = [str(item) for item in list(base_policy.get("dominant_target_zones") or []) if str(item).strip()]
    target_zones_policy = [str(item) for item in list(target_policy.get("dominant_target_zones") or []) if str(item).strip()]
    policy_impact_delta = {
        "base": base_policy,
        "target": target_policy,
        "event_count_gap": int(target_policy.get("event_count", 0)) - int(base_policy.get("event_count", 0)),
        "shared_roles": [role for role in target_roles if role in set(base_roles)][:6],
        "target_only_roles": [role for role in target_roles if role not in set(base_roles)][:6],
        "base_only_roles": [role for role in base_roles if role not in set(target_roles)][:6],
        "shared_zones": [zone for zone in target_zones_policy if zone in set(base_zones_policy)][:6],
        "target_only_zones": [zone for zone in target_zones_policy if zone not in set(base_zones_policy)][:6],
        "base_only_zones": [zone for zone in base_zones_policy if zone not in set(target_zones_policy)][:6],
        "largest_group_shift_gap": {
            "base_role_label": str((base_policy.get("largest_group_shift") or {}).get("role_label") or ""),
            "target_role_label": str((target_policy.get("largest_group_shift") or {}).get("role_label") or ""),
            "cohesion_gap": round(
                float((target_policy.get("largest_group_shift") or {}).get("cohesion_delta", 0.0))
                - float((base_policy.get("largest_group_shift") or {}).get("cohesion_delta", 0.0)),
                3,
            ),
            "tension_gap": round(
                float((target_policy.get("largest_group_shift") or {}).get("tension_delta", 0.0))
                - float((base_policy.get("largest_group_shift") or {}).get("tension_delta", 0.0)),
                3,
            ),
        },
        "largest_zone_shift_gap": {
            "base_zone_label": str((base_policy.get("largest_zone_z_shift") or {}).get("zone_label") or ""),
            "target_zone_label": str((target_policy.get("largest_zone_z_shift") or {}).get("zone_label") or ""),
            "avg_z_gap": round(
                float((target_policy.get("largest_zone_z_shift") or {}).get("avg_z_delta", 0.0))
                - float((base_policy.get("largest_zone_z_shift") or {}).get("avg_z_delta", 0.0)),
                3,
            ),
        },
    }
    mechanism_delta = _mechanism_delta(
        base_payload=base_payload,
        target_payload=target_payload,
        group_drift_deltas=group_drift_deltas,
        zone_z_delta=zone_z_delta,
    )
    policy_mechanism_delta = _policy_mechanism_delta(base_payload=base_payload, target_payload=target_payload)
    lineage_delta = _lineage_delta(base_payload=base_payload, target_payload=target_payload)

    timeline_turning_point_delta = {
        "base": [dict(item) for item in list(base_payload.get("annotation_candidates") or [])[:4]],
        "target": [dict(item) for item in list(target_payload.get("annotation_candidates") or [])[:4]],
    }

    notable_agent_delta = {
        "base": [dict(item) for item in list(base_payload.get("notable_agents") or [])[:5]],
        "target": [dict(item) for item in list(target_payload.get("notable_agents") or [])[:5]],
    }

    coalition_shift_delta = {
        "base_active_roles": sorted(str(key) for key in dict((base_payload.get("coalition_shift") or {}).get("active") or {}).keys()),
        "target_active_roles": sorted(str(key) for key in dict((target_payload.get("coalition_shift") or {}).get("active") or {}).keys()),
    }

    key_delta_summary = [
        f"cell delta gap {int(target_stats.get('cell_delta', 0)) - int(base_stats.get('cell_delta', 0)):+d}",
        f"energy delta gap {float(target_stats.get('energy_delta', 0.0)) - float(base_stats.get('energy_delta', 0.0)):+.2f}",
        f"z delta gap {float(target_stats.get('z_delta', 0.0)) - float(base_stats.get('z_delta', 0.0)):+.2f}",
        f"signal {base_stats.get('overall_signal', 'diffuse')} -> {target_stats.get('overall_signal', 'diffuse')}",
    ]

    return {
        "base_world_id": str(base_payload.get("world_id") or ""),
        "target_world_id": str(target_payload.get("world_id") or ""),
        "base_summary_stats": base_stats,
        "target_summary_stats": target_stats,
        "group_drift_deltas": group_drift_deltas[:8],
        "zone_z_delta": zone_z_delta[:8],
        "policy_impact_delta": policy_impact_delta,
        "mechanism_delta": mechanism_delta,
        "policy_mechanism_delta": policy_mechanism_delta,
        "lineage_delta": lineage_delta,
        "group_table_delta": _group_table_delta(
            group_drift_deltas=group_drift_deltas,
            zone_z_delta=zone_z_delta,
            base_payload=base_payload,
            target_payload=target_payload,
        ),
        "timeline_turning_point_delta": timeline_turning_point_delta,
        "notable_agent_delta": notable_agent_delta,
        "coalition_shift_delta": coalition_shift_delta,
        "key_delta_summary": key_delta_summary,
    }


def build_timeline_annotation_candidates(
    points: list[dict[str, Any]],
    *,
    key_events: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if len(points) < 2:
        return []
    deltas: list[dict[str, Any]] = []
    max_cell_delta = max(abs(points[i]["cell_count"] - points[i - 1]["cell_count"]) for i in range(1, len(points))) or 1
    max_energy_delta = max(abs(points[i]["total_energy"] - points[i - 1]["total_energy"]) for i in range(1, len(points))) or 1.0
    event_index = {float(item["t"]): item for item in list(key_events or [])}
    for i in range(1, len(points)):
        prev = points[i - 1]
        current = points[i]
        cell_delta = current["cell_count"] - prev["cell_count"]
        energy_delta = current["total_energy"] - prev["total_energy"]
        score = abs(cell_delta) / max_cell_delta + abs(energy_delta) / max_energy_delta
        label = "stability shift"
        if cell_delta > 0 and energy_delta > 0:
            label = "growth surge"
        elif cell_delta < 0 and energy_delta < 0:
            label = "contraction shock"
        elif abs(energy_delta) >= abs(cell_delta):
            label = "energy inflection"
        matched_event = event_index.get(float(current["t"]))
        reason = f"cells {cell_delta:+d}, energy {energy_delta:+.2f}"
        if matched_event:
            label = f"policy: {matched_event['name']}"
            reason = f"{reason}; event={matched_event['event_type']}"
            score += 0.35
        deltas.append(
            {
                "t": float(current["t"]),
                "score": round(float(score), 3),
                "label": label,
                "reason": reason,
            }
        )
    deltas.sort(key=lambda item: (-item["score"], item["t"]))
    return deltas[:6]


def _timeline_point(snapshot: Snapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    return {
        "t": float(snapshot.t),
        "cell_count": len(snapshot.cells),
        "total_energy": _total_energy(snapshot.cells),
        "avg_z": _avg_z(snapshot.cells),
    }


def _group_snapshot(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[Cell]] = defaultdict(list)
    for cell in snapshot.cells:
        role_key = (cell.role_key or "agent").strip() or "agent"
        role_label = (cell.role_label or role_key).strip() or role_key
        grouped[f"{role_key}:{role_label}"].append(cell)

    out: dict[str, dict[str, Any]] = {}
    for group_id, cells in grouped.items():
        role_label = (cells[0].role_label or cells[0].role_key or "agent").strip() or "agent"
        qualities = [
            float(item.get("quality_score", 0.0))
            for cell in cells
            for item in cell.behavior_log[-16:]
            if item.get("event_type") in {"social_observation", "agent_dialogue", "group_deliberation"}
        ]
        tensions = [
            float(item.get("tension", 0.0))
            for cell in cells
            for item in cell.relationship_state.values()
        ]
        trusts = [
            float(item.get("trust", 0.0))
            for cell in cells
            for item in cell.relationship_state.values()
        ]
        cohesion = float(np.mean(qualities)) if qualities else 0.0
        if trusts:
            cohesion = min(1.0, cohesion * 0.65 + float(np.mean(trusts)) * 0.35)
        tension = float(np.mean(tensions)) if tensions else 0.0
        stance = "diffuse"
        if cohesion >= 0.72 and tension < 0.2:
            stance = "cohesive"
        elif tension >= 0.35:
            stance = "contested"
        elif cohesion >= 0.5:
            stance = "emergent"
        out[group_id] = {
            "group_id": group_id,
            "role_label": role_label,
            "cell_count": len(cells),
            "avg_energy": round(sum(float(cell.energy) for cell in cells) / max(len(cells), 1), 3),
            "avg_z": round(_avg_z(cells), 3),
            "cohesion_score": round(cohesion, 3),
            "tension_score": round(tension, 3),
            "trust_score": round(float(np.mean(trusts)) if trusts else 0.0, 3),
            "stance": stance,
            "worldview_norm": round(
                float(np.mean([np.linalg.norm(cell.worldview_vec) for cell in cells])) if cells else 0.0,
                3,
            ),
            "polarization_score": round(
                float(np.std([np.linalg.norm(cell.worldview_vec) for cell in cells])) if len(cells) > 1 else 0.0,
                3,
            ),
            "split_risk_score": round(
                _clip01(
                    tension * 0.4
                    + (float(np.std([np.linalg.norm(cell.worldview_vec) for cell in cells])) if len(cells) > 1 else 0.0) * 0.35
                    + max(0.0, 0.5 - (float(np.mean(trusts)) if trusts else 0.0)) * 0.25
                ),
                3,
            ),
        }
    return out


def _belief_drift_summary(
    first_groups: dict[str, dict[str, Any]],
    latest_groups: dict[str, dict[str, Any]],
    *,
    coalition_state: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    groups: list[dict[str, Any]] = []
    coalition_index = {
        str(role): dict(payload)
        for role, payload in dict(coalition_state or {}).items()
    }
    for group_id, latest in latest_groups.items():
        first = dict(first_groups.get(group_id) or {})
        role_label = str(latest["role_label"])
        coalition = dict(coalition_index.get(role_label) or {})
        groups.append(
            {
                "group_id": group_id,
                "role_label": role_label,
                "stance_before": first.get("stance", "not_present"),
                "stance_after": latest["stance"],
                "cohesion_before": float(first.get("cohesion_score", 0.0)),
                "cohesion_after": float(latest.get("cohesion_score", 0.0)),
                "cohesion_delta": round(float(latest.get("cohesion_score", 0.0)) - float(first.get("cohesion_score", 0.0)), 3),
                "tension_before": float(first.get("tension_score", 0.0)),
                "tension_after": float(latest.get("tension_score", 0.0)),
                "tension_delta": round(float(latest.get("tension_score", 0.0)) - float(first.get("tension_score", 0.0)), 3),
                "trust_before": float(first.get("trust_score", 0.0)),
                "trust_after": float(latest.get("trust_score", 0.0)),
                "trust_delta": round(float(latest.get("trust_score", 0.0)) - float(first.get("trust_score", 0.0)), 3),
                "polarization_before": float(first.get("polarization_score", 0.0)),
                "polarization_after": float(latest.get("polarization_score", 0.0)),
                "polarization_delta": round(
                    float(latest.get("polarization_score", 0.0)) - float(first.get("polarization_score", 0.0)),
                    3,
                ),
                "avg_z_delta": round(float(latest.get("avg_z", 0.0)) - float(first.get("avg_z", 0.0)), 3),
                "cell_delta": int(latest.get("cell_count", 0)) - int(first.get("cell_count", 0)),
                "worldview_norm_delta": round(
                    float(latest.get("worldview_norm", 0.0)) - float(first.get("worldview_norm", 0.0)),
                    3,
                ),
                "coalition_signal": str(coalition.get("coalition_signal") or ""),
                "coalition_block_key": str(coalition.get("block_key") or ""),
                "coalition_cycle_count": int(coalition.get("cycle_count", 0) or 0),
                "coalition_persistence": round(
                    min(1.0, int(coalition.get("cycle_count", 0) or 0) / 4.0),
                    3,
                ),
                "sub_coalition_split_risk": round(float(latest.get("split_risk_score", 0.0)), 3),
                "ideology_block_divergence": round(
                    abs(float(latest.get("worldview_norm", 0.0)) - float(first.get("worldview_norm", 0.0)))
                    + float(latest.get("polarization_score", 0.0)),
                    3,
                ),
                "cross_zone_group_fracture": round(
                    _clip01(
                        abs(float(latest.get("avg_z", 0.0)) - float(first.get("avg_z", 0.0))) * 0.35
                        + float(latest.get("tension_score", 0.0)) * 0.4
                        + float(latest.get("polarization_score", 0.0)) * 0.25
                    ),
                    3,
                ),
            }
        )
    groups.sort(
        key=lambda item: (
            -abs(float(item["cohesion_delta"]))
            - abs(float(item["tension_delta"]))
            - abs(float(item["polarization_delta"])),
            item["role_label"],
        )
    )
    overall_signal = "diffuse"
    if any(group["stance_after"] == "contested" for group in groups):
        overall_signal = "contested"
    elif any(group["stance_after"] == "cohesive" for group in groups):
        overall_signal = "clustered"
    return {
        "overall_signal": overall_signal,
        "overall_polarization": round(float(np.mean([g["polarization_after"] for g in groups])) if groups else 0.0, 3),
        "overall_cohesion": round(float(np.mean([g["cohesion_after"] for g in groups])) if groups else 0.0, 3),
        "overall_tension": round(float(np.mean([g["tension_after"] for g in groups])) if groups else 0.0, 3),
        "overall_split_risk": round(float(np.mean([g["sub_coalition_split_risk"] for g in groups])) if groups else 0.0, 3),
        "overall_block_divergence": round(float(np.mean([g["ideology_block_divergence"] for g in groups])) if groups else 0.0, 3),
        "overall_cross_zone_fracture": round(float(np.mean([g["cross_zone_group_fracture"] for g in groups])) if groups else 0.0, 3),
        "groups": groups[:MAX_REVIEW_GROUPS],
    }


def _zone_z_drift(first: Snapshot, latest: Snapshot) -> list[dict[str, Any]]:
    first_index = _zone_snapshot(first)
    latest_index = _zone_snapshot(latest)
    rows: list[dict[str, Any]] = []
    for zone_id, latest_row in latest_index.items():
        first_row = first_index.get(zone_id, {})
        rows.append(
            {
                "zone_id": zone_id,
                "zone_label": latest_row["zone_label"],
                "avg_z_before": float(first_row.get("avg_z", 0.0)),
                "avg_z_after": float(latest_row.get("avg_z", 0.0)),
                "avg_z_delta": round(float(latest_row.get("avg_z", 0.0)) - float(first_row.get("avg_z", 0.0)), 3),
                "avg_energy_after": float(latest_row.get("avg_energy", 0.0)),
                "cell_count_after": int(latest_row.get("cell_count", 0)),
            }
        )
    rows.sort(key=lambda item: abs(float(item["avg_z_delta"])), reverse=True)
    return rows[:MAX_REVIEW_ZONES]


def _zone_snapshot(snapshot: Snapshot) -> dict[str, dict[str, Any]]:
    zones: dict[str, dict[str, Any]] = {}
    for cell in snapshot.cells:
        zone_id = str(getattr(cell, "zone_id", "") or "unassigned")
        zone_label = str(getattr(cell, "zone_label", "") or zone_id)
        bucket = zones.setdefault(
            zone_id,
            {"zone_id": zone_id, "zone_label": zone_label, "z": [], "energy": [], "count": 0},
        )
        bucket["z"].append(float(getattr(cell, "z", 0.0)))
        bucket["energy"].append(float(cell.energy))
        bucket["count"] += 1
    out: dict[str, dict[str, Any]] = {}
    for zone_id, payload in zones.items():
        out[zone_id] = {
            "zone_id": payload["zone_id"],
            "zone_label": payload["zone_label"],
            "cell_count": int(payload["count"]),
            "avg_z": round(float(np.mean(payload["z"])) if payload["z"] else 0.0, 3),
            "avg_energy": round(float(np.mean(payload["energy"])) if payload["energy"] else 0.0, 3),
        }
    return out


def _notable_agents(first: Snapshot, latest: Snapshot) -> list[dict[str, Any]]:
    first_index = {cell.cell_id: cell for cell in first.cells}
    movers: list[dict[str, Any]] = []
    for cell in latest.cells:
        prev = first_index.get(cell.cell_id)
        if prev is None:
            continue
        z_delta = float(getattr(cell, "z", 0.0)) - float(getattr(prev, "z", 0.0))
        worldview_shift = float(np.linalg.norm(cell.worldview_vec - prev.worldview_vec))
        thought_shift = float(np.linalg.norm(cell.thought_vec - prev.thought_vec))
        score = abs(z_delta) + worldview_shift * 0.2 + thought_shift * 0.1
        movers.append(
            {
                "cell_id": cell.cell_id,
                "role_label": str(cell.role_label or cell.role_key or "agent"),
                "persona_country": str(cell.persona_country or ""),
                "zone_label": str(cell.zone_label or cell.zone_id or ""),
                "z_delta": round(z_delta, 3),
                "worldview_shift": round(worldview_shift, 3),
                "thought_shift": round(thought_shift, 3),
                "belief_shift_score": round(score, 3),
            }
        )
    movers.sort(key=lambda item: float(item["belief_shift_score"]), reverse=True)
    return movers[:MAX_REVIEW_AGENTS]


def _policy_impact_summary(
    key_events: list[dict[str, Any]],
    drift_groups: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    affected_roles = []
    affected_zones = []
    for event in key_events:
        affected_roles.extend(list(event.get("target_roles") or []))
        affected_zones.extend(list(event.get("target_zones") or []))
    strongest_group = drift_groups[0] if drift_groups else {}
    strongest_zone = zone_rows[0] if zone_rows else {}
    channel_totals = defaultdict(float)
    for event in key_events:
        for channel, score in dict(event.get("mechanism_channels") or {}).items():
            channel_totals[str(channel)] += float(score or 0.0)
    return {
        "event_count": len(key_events),
        "dominant_target_roles": list(dict.fromkeys(str(role) for role in affected_roles if str(role).strip()))[:5],
        "dominant_target_zones": list(dict.fromkeys(str(zone) for zone in affected_zones if str(zone).strip()))[:5],
        "largest_group_shift": {
            "role_label": strongest_group.get("role_label", ""),
            "cohesion_delta": strongest_group.get("cohesion_delta", 0.0),
            "tension_delta": strongest_group.get("tension_delta", 0.0),
        },
        "largest_zone_z_shift": {
            "zone_label": strongest_zone.get("zone_label", ""),
            "avg_z_delta": strongest_zone.get("avg_z_delta", 0.0),
        },
        "dominant_channels": [
            {"channel": key, "score": round(value, 3)}
            for key, value in sorted(channel_totals.items(), key=lambda item: (-float(item[1]), str(item[0])))[:5]
        ],
    }


def _policy_mechanism_summary(
    key_events: list[dict[str, Any]],
    drift_groups: list[dict[str, Any]],
    zone_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    channel_scores: dict[str, float] = defaultdict(float)
    propagation_paths: list[dict[str, Any]] = []
    for event in key_events[:MAX_REVIEW_EVENTS]:
        channels = dict(event.get("mechanism_channels") or {})
        dominant = str(event.get("dominant_channel") or "resource")
        for key, value in channels.items():
            channel_scores[str(key)] += float(value or 0.0)
        lead_group = next(
            (group for group in drift_groups if not event.get("target_roles") or str(group.get("role_label") or "") in set(str(role) for role in list(event.get("target_roles") or []))),
            drift_groups[0] if drift_groups else {},
        )
        lead_zone = next(
            (zone for zone in zone_rows if not event.get("target_zones") or str(zone.get("zone_id") or "") in set(str(zone_id) for zone_id in list(event.get("target_zones") or []))),
            zone_rows[0] if zone_rows else {},
        )
        propagation_paths.append(
            {
                "event_name": str(event.get("name") or event.get("event_type") or "policy"),
                "dominant_channel": dominant,
                "group_id": str((lead_group or {}).get("group_id") or ""),
                "group_label": str((lead_group or {}).get("role_label") or "group"),
                "zone_id": str((lead_zone or {}).get("zone_id") or ""),
                "zone_label": str((lead_zone or {}).get("zone_label") or "zone"),
                "group_tension_delta": float((lead_group or {}).get("tension_delta", 0.0)),
                "group_cohesion_delta": float((lead_group or {}).get("cohesion_delta", 0.0)),
                "zone_z_delta": float((lead_zone or {}).get("avg_z_delta", 0.0)),
                "scope": str(event.get("impact_scope") or event.get("scope") or "world"),
            }
        )
    sorted_channels = [
        {"channel": key, "score": round(value, 3)}
        for key, value in sorted(channel_scores.items(), key=lambda item: (-float(item[1]), str(item[0])))
    ]
    return {
        "dominant_channels": sorted_channels[:5],
        "propagation_paths": propagation_paths[:6],
        "mechanism_count": len(propagation_paths),
    }


def _policy_mechanism_delta(*, base_payload: dict[str, Any], target_payload: dict[str, Any]) -> dict[str, Any]:
    def _channel_index(payload: dict[str, Any]) -> dict[str, float]:
        rows = list((payload.get("policy_mechanisms") or {}).get("dominant_channels") or [])
        return {str(item.get("channel") or "resource"): float(item.get("score") or 0.0) for item in rows}
    base_idx = _channel_index(base_payload)
    target_idx = _channel_index(target_payload)
    channels = sorted(set(base_idx.keys()) | set(target_idx.keys()))
    channel_gaps = [
        {
            "channel": channel,
            "base_score": round(base_idx.get(channel, 0.0), 3),
            "target_score": round(target_idx.get(channel, 0.0), 3),
            "score_gap": round(target_idx.get(channel, 0.0) - base_idx.get(channel, 0.0), 3),
        }
        for channel in channels
    ]
    channel_gaps.sort(key=lambda item: abs(float(item["score_gap"])), reverse=True)
    return {
        "channel_gaps": channel_gaps[:6],
        "base_paths": [dict(item) for item in list((base_payload.get("policy_mechanisms") or {}).get("propagation_paths") or [])[:4]],
        "target_paths": [dict(item) for item in list((target_payload.get("policy_mechanisms") or {}).get("propagation_paths") or [])[:4]],
    }


def _build_highlights(
    *,
    summary_stats: dict[str, Any],
    belief_drift: dict[str, Any],
    zone_z_drift: list[dict[str, Any]],
    notable_agents: list[dict[str, Any]],
    key_events: list[dict[str, Any]],
) -> list[str]:
    groups = list(belief_drift.get("groups") or [])
    lines = [
        f"cells moved from {summary_stats['initial_cell_count']} to {summary_stats['final_cell_count']}",
        f"energy changed by {float(summary_stats['energy_delta']):+.2f} and z by {float(summary_stats['z_delta']):+.2f}",
    ]
    if groups:
        top = groups[0]
        lines.append(
            f"{top['role_label']} shifted from {top['stance_before']} to {top['stance_after']} "
            f"(cohesion {float(top['cohesion_delta']):+.2f}, tension {float(top['tension_delta']):+.2f})"
        )
    if zone_z_drift:
        lines.append(
            f"{zone_z_drift[0]['zone_label']} shows the largest z drift {float(zone_z_drift[0]['avg_z_delta']):+.2f}"
        )
    if notable_agents:
        lines.append(
            f"{notable_agents[0]['role_label']} shows the strongest individual belief shift score "
            f"{float(notable_agents[0]['belief_shift_score']):.2f}"
        )
    if key_events:
        lines.append(f"{key_events[0]['name']} is the most recent policy/event intervention")
        dominant_channel = str((key_events[0].get("dominant_channel") or "resource"))
        lines.append(f"policy channel emphasis: {dominant_channel}")
    return lines[:6]


def _mechanism_summary(
    *,
    summary_stats: dict[str, Any],
    key_events: list[dict[str, Any]],
    belief_drift: dict[str, Any],
    zone_z_drift: list[dict[str, Any]],
    notable_agents: list[dict[str, Any]],
    group_analysis: dict[str, Any],
    emergent_dynamics: dict[str, Any],
) -> dict[str, Any]:
    groups = list(belief_drift.get("groups") or [])
    top_group = dict(groups[0] if groups else {})
    top_event = dict(key_events[0] if key_events else {})
    top_zone = dict(zone_z_drift[0] if zone_z_drift else {})
    top_agent = dict(notable_agents[0] if notable_agents else {})
    fracture_groups = list(group_analysis.get("fracture_groups") or [])
    contested_groups = list(group_analysis.get("contested_groups") or [])

    primary_chain = {
        "event_name": str(top_event.get("name") or "no major event"),
        "event_type": str(top_event.get("event_type") or "event"),
        "target_roles": list(top_event.get("target_roles") or [])[:4],
        "target_zones": list(top_event.get("target_zones") or [])[:4],
        "group_label": str(top_group.get("role_label") or "group"),
        "group_stance_transition": (
            f"{top_group.get('stance_before', 'n/a')} -> {top_group.get('stance_after', 'n/a')}"
            if top_group
            else "n/a"
        ),
        "zone_label": str(top_zone.get("zone_label") or "zone"),
        "agent_role": str(top_agent.get("role_label") or "agent"),
    }

    causal_hypotheses: list[dict[str, Any]] = []
    if top_event and top_group:
        causal_hypotheses.append(
            {
                "label": "policy-to-group drift",
                "summary": (
                    f"{top_event.get('name', 'event')} targeted "
                    f"{', '.join(list(top_event.get('target_roles') or [])[:3]) or 'broad groups'}, "
                    f"while {top_group.get('role_label', 'the lead group')} shifted "
                    f"cohesion {float(top_group.get('cohesion_delta', 0.0)):+.2f} and "
                    f"tension {float(top_group.get('tension_delta', 0.0)):+.2f}."
                ),
            }
        )
    if top_zone and top_group:
        causal_hypotheses.append(
            {
                "label": "group-to-zone fracture",
                "summary": (
                    f"{top_group.get('role_label', 'Lead group')} change coincided with "
                    f"{top_zone.get('zone_label', 'top zone')} z drift {float(top_zone.get('avg_z_delta', 0.0)):+.2f}, "
                    f"suggesting regional spillover."
                ),
            }
        )
    if top_agent and top_group:
        causal_hypotheses.append(
            {
                "label": "micro-to-macro reinforcement",
                "summary": (
                    f"{top_agent.get('role_label', 'A leading agent')} moved belief score "
                    f"{float(top_agent.get('belief_shift_score', 0.0)):.2f}, reinforcing "
                    f"{top_group.get('role_label', 'group-level')} drift."
                ),
            }
        )

    return {
        "primary_chain": primary_chain,
        "policy_mechanisms": _policy_mechanism_summary(key_events, groups, zone_z_drift),
        "causal_hypotheses": causal_hypotheses[:4],
        "pressure_points": {
            "fracture_groups": [dict(item) for item in fracture_groups[:3]],
            "contested_groups": [dict(item) for item in contested_groups[:3]],
            "revolution_risk": str(emergent_dynamics.get("revolution_risk") or "low"),
            "overall_signal": str(summary_stats.get("overall_signal") or "diffuse"),
        },
    }


def _group_analysis_summary(
    belief_drift: dict[str, Any],
    zone_z_drift: list[dict[str, Any]],
) -> dict[str, Any]:
    groups = list(belief_drift.get("groups") or [])
    contested = [item for item in groups if str(item.get("stance_after") or "") == "contested"]
    cohesive = sorted(groups, key=lambda item: float(item.get("cohesion_after", 0.0)), reverse=True)[:3]
    fracture = sorted(
        groups,
        key=lambda item: (
            float(item.get("sub_coalition_split_risk", 0.0))
            + float(item.get("cross_zone_group_fracture", 0.0))
        ),
        reverse=True,
    )[:4]
    return {
        "contested_groups": [
            {
                "group_id": str(item.get("group_id") or ""),
                "role_label": str(item.get("role_label") or "group"),
                "tension_after": float(item.get("tension_after", 0.0)),
                "polarization_after": float(item.get("polarization_after", 0.0)),
            }
            for item in contested[:4]
        ],
        "cohesive_groups": [
            {
                "group_id": str(item.get("group_id") or ""),
                "role_label": str(item.get("role_label") or "group"),
                "cohesion_after": float(item.get("cohesion_after", 0.0)),
                "coalition_signal": str(item.get("coalition_signal") or ""),
            }
            for item in cohesive
        ],
        "fracture_groups": [
            {
                "group_id": str(item.get("group_id") or ""),
                "role_label": str(item.get("role_label") or "group"),
                "split_risk": float(item.get("sub_coalition_split_risk", 0.0)),
                "cross_zone_fracture": float(item.get("cross_zone_group_fracture", 0.0)),
                "block_divergence": float(item.get("ideology_block_divergence", 0.0)),
            }
            for item in fracture
        ],
        "zone_hotspots": [
            {
                "zone_id": str(item.get("zone_id") or ""),
                "zone_label": str(item.get("zone_label") or "zone"),
                "avg_z_delta": float(item.get("avg_z_delta", 0.0)),
                "cell_count_after": int(item.get("cell_count_after", 0)),
            }
            for item in zone_z_drift[:4]
        ],
        "transition_groups": [
            {
                "group_id": str(item.get("group_id") or ""),
                "role_label": str(item.get("role_label") or "group"),
                "stance_transition": f"{item.get('stance_before', 'n/a')} -> {item.get('stance_after', 'n/a')}",
                "cohesion_delta": float(item.get("cohesion_delta", 0.0)),
                "tension_delta": float(item.get("tension_delta", 0.0)),
            }
            for item in groups[:4]
        ],
    }


def _group_tables_summary(
    belief_drift: dict[str, Any],
    zone_z_drift: list[dict[str, Any]],
    notable_agents: list[dict[str, Any]],
) -> dict[str, Any]:
    groups = list(belief_drift.get("groups") or [])
    role_table = [
        {
            "group_id": str(item.get("group_id") or ""),
            "role_label": str(item.get("role_label") or "group"),
            "stance_after": str(item.get("stance_after") or "diffuse"),
            "cohesion_after": round(float(item.get("cohesion_after", 0.0)), 3),
            "tension_after": round(float(item.get("tension_after", 0.0)), 3),
            "polarization_after": round(float(item.get("polarization_after", 0.0)), 3),
            "split_risk": round(float(item.get("sub_coalition_split_risk", 0.0)), 3),
            "block_divergence": round(float(item.get("ideology_block_divergence", 0.0)), 3),
            "cross_zone_fracture": round(float(item.get("cross_zone_group_fracture", 0.0)), 3),
            "cell_delta": int(item.get("cell_delta", 0)),
            "coalition_signal": str(item.get("coalition_signal") or ""),
        }
        for item in groups[:MAX_REVIEW_GROUPS]
    ]
    persona_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "shift": 0.0, "z": 0.0, "worldview": 0.0})
    for item in notable_agents[:MAX_REVIEW_AGENTS]:
        country = str(item.get("persona_country") or "unknown") or "unknown"
        bucket = persona_buckets[country]
        bucket["count"] += 1.0
        bucket["shift"] += float(item.get("belief_shift_score", 0.0))
        bucket["z"] += abs(float(item.get("z_delta", 0.0)))
        bucket["worldview"] += float(item.get("worldview_shift", 0.0))
    persona_country_table = [
        {
            "persona_country": country,
            "count": int(values["count"]),
            "avg_belief_shift": round(values["shift"] / max(values["count"], 1.0), 3),
            "avg_z_delta": round(values["z"] / max(values["count"], 1.0), 3),
            "avg_worldview_shift": round(values["worldview"] / max(values["count"], 1.0), 3),
        }
        for country, values in persona_buckets.items()
    ]
    persona_country_table.sort(key=lambda item: (item["avg_belief_shift"], item["avg_z_delta"]), reverse=True)
    zone_table = [
        {
            "zone_id": str(item.get("zone_id") or ""),
            "zone_label": str(item.get("zone_label") or "zone"),
            "avg_z_delta": round(float(item.get("avg_z_delta", 0.0)), 3),
            "avg_energy_after": round(float(item.get("avg_energy_after", 0.0)), 3),
            "cell_count_after": int(item.get("cell_count_after", 0)),
        }
        for item in zone_z_drift[:MAX_REVIEW_ZONES]
    ]
    return {
        "role_table": role_table,
        "persona_country_table": persona_country_table[:6],
        "zone_table": zone_table[:6],
    }


def _lineage_summary(
    *,
    store: Any,
    available_t: list[float],
    belief_drift: dict[str, Any],
) -> dict[str, Any]:
    sampled_t = [float(t) for t in _sample_numeric_points(available_t, limit=8)]
    role_tracks: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in sampled_t:
        snapshot = store.get(t)
        if snapshot is None:
            continue
        group_snapshot = _group_snapshot(snapshot)
        for group in group_snapshot.values():
            role_label = str(group.get("role_label") or "group")
            role_tracks[role_label].append(
                {
                    "t": float(t),
                    "stance": str(group.get("stance") or "diffuse"),
                    "cohesion": float(group.get("cohesion_score", 0.0)),
                    "tension": float(group.get("tension_score", 0.0)),
                    "polarization": float(group.get("polarization_score", 0.0)),
                    "avg_z": float(group.get("avg_z", 0.0)),
                }
            )

    drift_groups = {
        str(item.get("role_label") or "group"): dict(item)
        for item in list(belief_drift.get("groups") or [])
    }
    tracked_roles: list[dict[str, Any]] = []
    ideology_migrations: list[dict[str, Any]] = []
    for role_label, points in role_tracks.items():
        if len(points) < 2:
            continue
        stances = [str(point.get("stance") or "diffuse") for point in points]
        transition_count = sum(1 for idx in range(1, len(stances)) if stances[idx] != stances[idx - 1])
        first_point = dict(points[0])
        last_point = dict(points[-1])
        drift = dict(drift_groups.get(role_label) or {})
        lineage_score = _clip01(
            min(1.0, transition_count / max(len(points) - 1, 1)) * 0.35
            + abs(float(last_point.get("polarization", 0.0)) - float(first_point.get("polarization", 0.0))) * 0.25
            + abs(float(last_point.get("avg_z", 0.0)) - float(first_point.get("avg_z", 0.0))) * 0.15
            + float(drift.get("sub_coalition_split_risk", 0.0)) * 0.15
            + float(drift.get("cross_zone_group_fracture", 0.0)) * 0.10
        )
        tracked_roles.append(
            {
                "role_label": role_label,
                "first_stance": stances[0],
                "last_stance": stances[-1],
                "transition_count": transition_count,
                "lineage_score": round(lineage_score, 3),
                "polarization_delta": round(float(last_point.get("polarization", 0.0)) - float(first_point.get("polarization", 0.0)), 3),
                "avg_z_delta": round(float(last_point.get("avg_z", 0.0)) - float(first_point.get("avg_z", 0.0)), 3),
                "stance_path": stances,
                "t_path": [float(point.get("t", 0.0)) for point in points],
            }
        )
        if transition_count > 0 or stances[0] != stances[-1]:
            ideology_migrations.append(
                {
                    "role_label": role_label,
                    "from_stance": stances[0],
                    "to_stance": stances[-1],
                    "transition_count": transition_count,
                    "lineage_score": round(lineage_score, 3),
                }
            )
    tracked_roles.sort(
        key=lambda item: (
            -float(item.get("lineage_score", 0.0)),
            -int(item.get("transition_count", 0)),
            str(item.get("role_label") or ""),
        )
    )
    ideology_migrations.sort(
        key=lambda item: (
            -int(item.get("transition_count", 0)),
            -float(item.get("lineage_score", 0.0)),
            str(item.get("role_label") or ""),
        )
    )
    unstable_roles = sum(1 for item in tracked_roles if float(item.get("lineage_score", 0.0)) >= 0.55)
    if unstable_roles >= 3:
        regime_transition_signal = "volatile"
    elif ideology_migrations:
        regime_transition_signal = "realigning"
    else:
        regime_transition_signal = "stable"
    return {
        "sampled_t": sampled_t,
        "tracked_roles": tracked_roles[:6],
        "ideology_migrations": ideology_migrations[:6],
        "regime_transition_signal": regime_transition_signal,
    }


def _group_table_delta(
    *,
    group_drift_deltas: list[dict[str, Any]],
    zone_z_delta: list[dict[str, Any]],
    base_payload: dict[str, Any],
    target_payload: dict[str, Any],
) -> dict[str, Any]:
    base_persona = {
        str(item.get("persona_country") or "unknown"): dict(item)
        for item in list((base_payload.get("group_tables") or {}).get("persona_country_table") or [])
    }
    target_persona = {
        str(item.get("persona_country") or "unknown"): dict(item)
        for item in list((target_payload.get("group_tables") or {}).get("persona_country_table") or [])
    }
    persona_country_delta = []
    for country, target_row in target_persona.items():
        base_row = dict(base_persona.get(country) or {})
        persona_country_delta.append(
            {
                "persona_country": country,
                "count_gap": int(target_row.get("count", 0)) - int(base_row.get("count", 0)),
                "avg_belief_shift_gap": round(float(target_row.get("avg_belief_shift", 0.0)) - float(base_row.get("avg_belief_shift", 0.0)), 3),
                "avg_z_delta_gap": round(float(target_row.get("avg_z_delta", 0.0)) - float(base_row.get("avg_z_delta", 0.0)), 3),
                "avg_worldview_shift_gap": round(float(target_row.get("avg_worldview_shift", 0.0)) - float(base_row.get("avg_worldview_shift", 0.0)), 3),
            }
        )
    persona_country_delta.sort(key=lambda item: abs(float(item["avg_belief_shift_gap"])) + abs(float(item["avg_z_delta_gap"])), reverse=True)
    return {
        "role_table_delta": [dict(item) for item in group_drift_deltas[:8]],
        "persona_country_delta": persona_country_delta[:6],
        "zone_table_delta": [dict(item) for item in zone_z_delta[:6]],
    }


def _session_group_tables(world_payloads: list[dict[str, Any]]) -> dict[str, Any]:
    role_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "cohesion": 0.0, "tension": 0.0, "fracture": 0.0, "split": 0.0})
    persona_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "shift": 0.0, "z": 0.0, "worldview": 0.0})
    zone_buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"count": 0.0, "z": 0.0, "energy": 0.0, "cells": 0.0})
    for payload in world_payloads:
        tables = dict(payload.get("group_tables") or {})
        for row in list(tables.get("role_table") or []):
            label = str(row.get("role_label") or "group")
            bucket = role_buckets[label]
            bucket["count"] += 1.0
            bucket["cohesion"] += float(row.get("cohesion_after", 0.0))
            bucket["tension"] += float(row.get("tension_after", 0.0))
            bucket["fracture"] += float(row.get("cross_zone_fracture", 0.0))
            bucket["split"] += float(row.get("split_risk", 0.0))
        for row in list(tables.get("persona_country_table") or []):
            label = str(row.get("persona_country") or "unknown")
            bucket = persona_buckets[label]
            bucket["count"] += 1.0
            bucket["shift"] += float(row.get("avg_belief_shift", 0.0))
            bucket["z"] += float(row.get("avg_z_delta", 0.0))
            bucket["worldview"] += float(row.get("avg_worldview_shift", 0.0))
        for row in list(tables.get("zone_table") or []):
            label = str(row.get("zone_label") or row.get("zone_id") or "zone")
            bucket = zone_buckets[label]
            bucket["count"] += 1.0
            bucket["z"] += abs(float(row.get("avg_z_delta", 0.0)))
            bucket["energy"] += float(row.get("avg_energy_after", 0.0))
            bucket["cells"] += float(row.get("cell_count_after", 0.0))
    role_table = [
        {
            "role_label": label,
            "avg_cohesion": round(v["cohesion"] / max(v["count"], 1.0), 3),
            "avg_tension": round(v["tension"] / max(v["count"], 1.0), 3),
            "avg_fracture": round(v["fracture"] / max(v["count"], 1.0), 3),
            "avg_split_risk": round(v["split"] / max(v["count"], 1.0), 3),
            "world_coverage": int(v["count"]),
        }
        for label, v in role_buckets.items()
    ]
    role_table.sort(key=lambda item: item["avg_fracture"] + item["avg_tension"], reverse=True)
    persona_country_table = [
        {
            "persona_country": label,
            "avg_belief_shift": round(v["shift"] / max(v["count"], 1.0), 3),
            "avg_z_delta": round(v["z"] / max(v["count"], 1.0), 3),
            "avg_worldview_shift": round(v["worldview"] / max(v["count"], 1.0), 3),
            "world_coverage": int(v["count"]),
        }
        for label, v in persona_buckets.items()
    ]
    persona_country_table.sort(key=lambda item: item["avg_belief_shift"], reverse=True)
    zone_table = [
        {
            "zone_label": label,
            "avg_z_delta": round(v["z"] / max(v["count"], 1.0), 3),
            "avg_energy": round(v["energy"] / max(v["count"], 1.0), 3),
            "avg_cells": round(v["cells"] / max(v["count"], 1.0), 3),
            "world_coverage": int(v["count"]),
        }
        for label, v in zone_buckets.items()
    ]
    zone_table.sort(key=lambda item: item["avg_z_delta"], reverse=True)
    return {
        "role_table": role_table[:6],
        "persona_country_table": persona_country_table[:6],
        "zone_table": zone_table[:6],
    }


def _emergent_dynamics_summary(
    *,
    timeline_points: list[dict[str, Any]],
    belief_drift: dict[str, Any],
    key_events: list[dict[str, Any]],
    lineage_summary: dict[str, Any],
) -> dict[str, Any]:
    groups = list(belief_drift.get("groups") or [])
    avg_split = float(belief_drift.get("overall_split_risk", 0.0))
    avg_divergence = float(belief_drift.get("overall_block_divergence", 0.0))
    avg_fracture = float(belief_drift.get("overall_cross_zone_fracture", 0.0))
    ideology_blocks = [
        {
            "label": str(item.get("role_label") or "group"),
            "divergence": float(item.get("ideology_block_divergence", 0.0)),
            "coalition_signal": str(item.get("coalition_signal") or ""),
        }
        for item in sorted(
            groups,
            key=lambda group: float(group.get("ideology_block_divergence", 0.0)),
            reverse=True,
        )[:4]
    ]
    timeline_tail = _sample_timeline_points(timeline_points, limit=18)
    worldview_curve = [
        {
            "t": float(item.get("t", 0.0)),
            "cell_count": int(item.get("cell_count", 0)),
            "avg_z": float(item.get("avg_z", 0.0)),
        }
        for item in timeline_tail
    ]
    if avg_split >= 0.65 or avg_fracture >= 0.65:
        revolution_risk = "high"
    elif avg_divergence >= 0.45 or avg_split >= 0.45:
        revolution_risk = "medium"
    else:
        revolution_risk = "low"
    return {
        "revolution_risk": revolution_risk,
        "split_risk": round(avg_split, 3),
        "block_divergence": round(avg_divergence, 3),
        "cross_zone_fracture": round(avg_fracture, 3),
        "regime_transition_signal": str(lineage_summary.get("regime_transition_signal") or "stable"),
        "ideology_blocks": ideology_blocks,
        "ideology_migrations": [dict(item) for item in list(lineage_summary.get("ideology_migrations") or [])[:5]],
        "worldview_curve": worldview_curve,
        "recent_events": [str(item.get("name") or item.get("event_type") or "event") for item in key_events[:4]],
        "transition_pressure": round(_clip01(avg_split * 0.4 + avg_divergence * 0.35 + avg_fracture * 0.25), 3),
    }


def _mechanism_delta(
    *,
    base_payload: dict[str, Any],
    target_payload: dict[str, Any],
    group_drift_deltas: list[dict[str, Any]],
    zone_z_delta: list[dict[str, Any]],
) -> dict[str, Any]:
    base_mechanism = dict(base_payload.get("mechanism_summary") or {})
    target_mechanism = dict(target_payload.get("mechanism_summary") or {})
    top_group_gap = dict(group_drift_deltas[0] if group_drift_deltas else {})
    top_zone_gap = dict(zone_z_delta[0] if zone_z_delta else {})
    return {
        "base_primary_chain": dict(base_mechanism.get("primary_chain") or {}),
        "target_primary_chain": dict(target_mechanism.get("primary_chain") or {}),
        "top_group_gap": {
            "role_label": str(top_group_gap.get("role_label") or ""),
            "stance_transition": (
                f"{top_group_gap.get('stance_base', 'n/a')} -> {top_group_gap.get('stance_target', 'n/a')}"
                if top_group_gap
                else "n/a"
            ),
            "cohesion_gap": float(top_group_gap.get("cohesion_gap", 0.0)),
            "tension_gap": float(top_group_gap.get("tension_gap", 0.0)),
            "split_risk_gap": float(top_group_gap.get("split_risk_gap", 0.0)),
        },
        "top_zone_gap": {
            "zone_label": str(top_zone_gap.get("zone_label") or ""),
            "avg_z_gap": float(top_zone_gap.get("avg_z_gap", 0.0)),
            "avg_energy_gap": float(top_zone_gap.get("avg_energy_gap", 0.0)),
        },
        "hypothesis_shift": [
            str(item.get("summary") or "")
            for item in list(target_mechanism.get("causal_hypotheses") or [])[:3]
            if str(item.get("summary") or "").strip()
        ],
    }


def _lineage_delta(*, base_payload: dict[str, Any], target_payload: dict[str, Any]) -> dict[str, Any]:
    def _tracked_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            str(item.get("role_label") or "group"): dict(item)
            for item in list((payload.get("lineage_summary") or {}).get("tracked_roles") or [])
        }

    base_idx = _tracked_index(base_payload)
    target_idx = _tracked_index(target_payload)
    role_rows: list[dict[str, Any]] = []
    for role_label in sorted(set(base_idx.keys()) | set(target_idx.keys())):
        base_row = dict(base_idx.get(role_label) or {})
        target_row = dict(target_idx.get(role_label) or {})
        role_rows.append(
            {
                "role_label": role_label,
                "base_transition_count": int(base_row.get("transition_count", 0)),
                "target_transition_count": int(target_row.get("transition_count", 0)),
                "transition_gap": int(target_row.get("transition_count", 0)) - int(base_row.get("transition_count", 0)),
                "lineage_score_gap": round(float(target_row.get("lineage_score", 0.0)) - float(base_row.get("lineage_score", 0.0)), 3),
                "polarization_delta_gap": round(float(target_row.get("polarization_delta", 0.0)) - float(base_row.get("polarization_delta", 0.0)), 3),
                "target_path": list(target_row.get("stance_path") or []),
            }
        )
    role_rows.sort(key=lambda item: (abs(float(item["lineage_score_gap"])) + abs(float(item["transition_gap"])), str(item["role_label"])), reverse=True)
    return {
        "base_regime_transition": str((base_payload.get("lineage_summary") or {}).get("regime_transition_signal") or "stable"),
        "target_regime_transition": str((target_payload.get("lineage_summary") or {}).get("regime_transition_signal") or "stable"),
        "tracked_role_gaps": role_rows[:6],
    }


def _sample_timeline_points(
    timeline_points: list[dict[str, Any]],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if len(timeline_points) <= limit:
        return list(timeline_points)
    step = max(1, len(timeline_points) // max(1, limit - 1))
    sampled = timeline_points[::step]
    if sampled[-1] is not timeline_points[-1]:
        sampled.append(timeline_points[-1])
    return sampled[:limit]


def _sample_numeric_points(points: list[float], *, limit: int) -> list[float]:
    if len(points) <= limit:
        return list(points)
    step = max(1, len(points) // max(1, limit - 1))
    sampled = points[::step]
    if sampled[-1] != points[-1]:
        sampled.append(points[-1])
    return sampled[:limit]


def _build_grounding(
    *,
    key_events: list[dict[str, Any]],
    belief_drift: dict[str, Any],
    zone_z_drift: list[dict[str, Any]],
    notable_agents: list[dict[str, Any]],
    world_id: str,
) -> dict[str, Any]:
    groups = list(belief_drift.get("groups") or [])
    return {
        "events": [
            {
                "anchor_id": f"event:{world_id}:{int(float(item.get('t', 0.0)))}:{idx}",
                "kind": "event",
                "label": str(item.get("name") or "event"),
                "t": float(item.get("t", 0.0)),
                "reason": str(item.get("summary") or item.get("event_type") or ""),
                "target_roles": list(item.get("target_roles") or []),
                "target_zones": list(item.get("target_zones") or []),
                "world_id": world_id,
            }
            for idx, item in enumerate(key_events[:5], start=1)
        ][:MAX_REVIEW_EVENTS],
        "groups": [
            {
                "anchor_id": f"group:{world_id}:{str(item.get('group_id') or '')}",
                "kind": "group",
                "group_id": str(item.get("group_id") or ""),
                "label": str(item.get("role_label") or "group"),
                "stance_after": str(item.get("stance_after") or ""),
                "cohesion_delta": float(item.get("cohesion_delta", 0.0)),
                "tension_delta": float(item.get("tension_delta", 0.0)),
                "polarization_delta": float(item.get("polarization_delta", 0.0)),
                "coalition_signal": str(item.get("coalition_signal") or ""),
                "world_id": world_id,
            }
            for item in groups[: min(5, MAX_REVIEW_GROUPS)]
        ],
        "zones": [
            {
                "anchor_id": f"zone:{world_id}:{str(item.get('zone_id') or '')}",
                "kind": "zone",
                "zone_id": str(item.get("zone_id") or ""),
                "label": str(item.get("zone_label") or "zone"),
                "avg_z_delta": float(item.get("avg_z_delta", 0.0)),
                "cell_count_after": int(item.get("cell_count_after", 0)),
                "world_id": world_id,
            }
            for item in zone_z_drift[: min(5, MAX_REVIEW_ZONES)]
        ],
        "agents": [
            {
                "anchor_id": f"agent:{world_id}:{str(item.get('cell_id') or '')}",
                "kind": "agent",
                "cell_id": str(item.get("cell_id") or ""),
                "label": str(item.get("role_label") or "agent"),
                "zone_label": str(item.get("zone_label") or ""),
                "belief_shift_score": float(item.get("belief_shift_score", 0.0)),
                "z_delta": float(item.get("z_delta", 0.0)),
                "world_id": world_id,
            }
            for item in notable_agents[: min(5, MAX_REVIEW_AGENTS)]
        ],
    }


def _build_causal_chains(
    *,
    world_id: str,
    key_events: list[dict[str, Any]],
    groups: list[dict[str, Any]],
    zone_z_drift: list[dict[str, Any]],
    notable_agents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    chains: list[dict[str, Any]] = []
    for idx, event in enumerate(key_events[:3]):
        group = groups[idx] if idx < len(groups) else (groups[0] if groups else {})
        zone = zone_z_drift[idx] if idx < len(zone_z_drift) else (zone_z_drift[0] if zone_z_drift else {})
        agent = notable_agents[idx] if idx < len(notable_agents) else (notable_agents[0] if notable_agents else {})
        chains.append(
            {
                "anchor_id": f"chain:{world_id}:{idx + 1}",
                "world_id": world_id,
                "label": str(event.get("name") or event.get("event_type") or f"chain-{idx + 1}"),
                "t": float(event.get("t", 0.0)),
                "event": {
                    "anchor_id": f"event:{world_id}:{int(float(event.get('t', 0.0)))}:{idx + 1}",
                    "label": str(event.get("name") or event.get("event_type") or "event"),
                    "summary": str(event.get("summary") or ""),
                },
                "group": {
                    "anchor_id": f"group:{world_id}:{str(group.get('group_id') or '')}",
                    "group_id": str(group.get("group_id") or ""),
                    "label": str(group.get("role_label") or "group"),
                    "stance_after": str(group.get("stance_after") or ""),
                },
                "zone": {
                    "anchor_id": f"zone:{world_id}:{str(zone.get('zone_id') or '')}",
                    "zone_id": str(zone.get("zone_id") or ""),
                    "label": str(zone.get("zone_label") or "zone"),
                    "avg_z_delta": float(zone.get("avg_z_delta", 0.0)),
                },
                "agent": {
                    "anchor_id": f"agent:{world_id}:{str(agent.get('cell_id') or '')}",
                    "cell_id": str(agent.get("cell_id") or ""),
                    "label": str(agent.get("role_label") or "agent"),
                    "belief_shift_score": float(agent.get("belief_shift_score", 0.0)),
                },
            }
        )
    return chains


def _build_belief_graph(belief_drift: dict[str, Any]) -> dict[str, Any]:
    groups = [dict(item) for item in list(belief_drift.get("groups") or [])[:8]]
    nodes = [
        {
            "id": str(item.get("group_id") or ""),
            "label": str(item.get("role_label") or "group"),
            "stance": str(item.get("stance_after") or "diffuse"),
            "cohesion": float(item.get("cohesion_after", 0.0)),
            "tension": float(item.get("tension_after", 0.0)),
            "polarization": float(item.get("polarization_after", 0.0)),
            "split_risk": float(item.get("sub_coalition_split_risk", 0.0)),
            "block_divergence": float(item.get("ideology_block_divergence", 0.0)),
            "cross_zone_fracture": float(item.get("cross_zone_group_fracture", 0.0)),
            "coalition_signal": str(item.get("coalition_signal") or ""),
        }
        for item in groups
    ]
    edges: list[dict[str, Any]] = []
    for i, left in enumerate(groups):
        for right in groups[i + 1 :]:
            cohesion_similarity = 1.0 - abs(float(left.get("cohesion_after", 0.0)) - float(right.get("cohesion_after", 0.0)))
            tension_similarity = 1.0 - abs(float(left.get("tension_after", 0.0)) - float(right.get("tension_after", 0.0)))
            polarization_similarity = 1.0 - abs(float(left.get("polarization_after", 0.0)) - float(right.get("polarization_after", 0.0)))
            weight = round(max(0.0, (cohesion_similarity + tension_similarity + polarization_similarity) / 3.0), 3)
            if weight < 0.45:
                continue
            edges.append(
                {
                    "source": str(left.get("group_id") or ""),
                    "target": str(right.get("group_id") or ""),
                    "weight": weight,
                    "relationship": "aligned" if str(left.get("stance_after")) == str(right.get("stance_after")) else "contested",
                }
            )
    return {"nodes": nodes[:MAX_REVIEW_GROUPS], "edges": edges[:MAX_REVIEW_GRAPH_EDGES]}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _event_summary(event: Any) -> dict[str, Any]:
    payload = dict(getattr(event, "payload", {}) or {})
    return {
        "t": float(getattr(event, "t", 0.0)),
        "event_type": str(getattr(event, "event_type", "")),
        "name": str(payload.get("name") or payload.get("summary") or payload.get("label") or "event"),
        "summary": str(payload.get("summary") or payload.get("name") or "event"),
        "target_roles": list(payload.get("target_roles") or []),
        "target_zones": list(payload.get("target_zones") or []),
        "duration_steps": int(payload.get("duration_steps") or 0),
        "impact_scope": str(payload.get("scope") or "local"),
    }


def _classify_outcome(points: list[dict[str, Any]]) -> str:
    if not points:
        return "not_started"
    first = points[0]
    last = points[-1]
    if last["cell_count"] == 0:
        return "extinct"
    if last["cell_count"] >= max(first["cell_count"] * 1.5, first["cell_count"] + 3):
        return "expanding"
    if last["cell_count"] <= first["cell_count"] * 0.6:
        return "contracting"
    if last["total_energy"] > first["total_energy"] * 1.25:
        return "energy_accumulating"
    if last["total_energy"] < first["total_energy"] * 0.75:
        return "energy_depleted"
    return "stable"


def _total_energy(cells: list[Cell]) -> float:
    return round(sum(float(cell.energy) for cell in cells), 3)


def _avg_z(cells: list[Cell]) -> float:
    if not cells:
        return 0.0
    return round(sum(float(getattr(cell, "z", 0.0)) for cell in cells) / len(cells), 3)
