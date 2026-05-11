"""Post-simulation review APIs."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.review_payloads import (
    build_cached_world_review_payload,
    build_review_diff_payload,
)
from app.core.store import world_store
from app.llm.facade import llm_facade

router = APIRouter(prefix="/worlds", tags=["review"])


class TimelineAnnotation(BaseModel):
    t: float
    label: str
    reason: str
    severity: str


class ReviewGroundingItem(BaseModel):
    anchor_id: str = ""
    kind: str
    label: str
    reason: str = ""
    t: Optional[float] = None
    group_id: Optional[str] = None
    zone_id: Optional[str] = None
    cell_id: Optional[str] = None
    world_id: Optional[str] = None


class ReviewSummaryResponse(BaseModel):
    world_id: str
    headline: str
    summary: str
    summary_mode: str
    key_events: List[str] = Field(default_factory=list)
    causal_analysis: List[str] = Field(default_factory=list)
    decision_implications: List[str] = Field(default_factory=list)
    watch_items: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    overall_signal: str
    outcome: str
    timeline_annotations: List[TimelineAnnotation] = Field(default_factory=list)
    annotation_mode: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    stance_groups: List[Dict[str, Any]] = Field(default_factory=list)
    zone_z_summary: List[Dict[str, Any]] = Field(default_factory=list)
    top_z_movers: List[Dict[str, Any]] = Field(default_factory=list)
    policy_events: List[Dict[str, Any]] = Field(default_factory=list)
    belief_graph: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    grounding: Dict[str, List[ReviewGroundingItem]] = Field(default_factory=dict)
    citations: Dict[str, List[ReviewGroundingItem]] = Field(default_factory=dict)
    review_meta: Dict[str, Any] = Field(default_factory=dict)


class ReviewDiffResponse(BaseModel):
    base_world_id: str
    target_world_id: str
    headline: str
    summary: str
    diff_mode: str
    key_deltas: List[str] = Field(default_factory=list)
    causal_comparison: List[str] = Field(default_factory=list)
    decision_implications: List[str] = Field(default_factory=list)
    compared_metrics: Dict[str, Any] = Field(default_factory=dict)
    citations: Dict[str, List[ReviewGroundingItem]] = Field(default_factory=dict)
    review_meta: Dict[str, Any] = Field(default_factory=dict)


class ReviewQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class ReviewQueryResponse(BaseModel):
    world_id: str
    question: str
    answer: str
    evidence: List[str] = Field(default_factory=list)
    follow_up: List[str] = Field(default_factory=list)
    confidence_notes: List[str] = Field(default_factory=list)
    mode: str
    grounding: Dict[str, List[ReviewGroundingItem]] = Field(default_factory=dict)
    citations: List[ReviewGroundingItem] = Field(default_factory=list)
    review_meta: Dict[str, Any] = Field(default_factory=dict)


class ReviewDiffQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class ReviewDiffQueryResponse(BaseModel):
    base_world_id: str
    target_world_id: str
    question: str
    answer: str
    evidence: List[str] = Field(default_factory=list)
    follow_up: List[str] = Field(default_factory=list)
    confidence_notes: List[str] = Field(default_factory=list)
    mode: str
    grounding: Dict[str, List[ReviewGroundingItem]] = Field(default_factory=dict)
    citations: List[ReviewGroundingItem] = Field(default_factory=list)
    review_meta: Dict[str, Any] = Field(default_factory=dict)


@router.get("/{world_id}/review/summary", response_model=ReviewSummaryResponse)
def get_review_summary(world_id: str):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    try:
        payload = build_cached_world_review_payload(entry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    summary = llm_facade.summarize_review(payload)
    annotations = llm_facade.annotate_timeline(payload)
    return ReviewSummaryResponse(
        world_id=world_id,
        headline=str(summary["summary"].get("headline") or ""),
        summary=str(summary["summary"].get("executive_summary") or ""),
        summary_mode=str(summary["mode"]),
        key_events=[str(item) for item in list(summary["summary"].get("key_events") or [])],
        causal_analysis=[str(item) for item in list(summary["summary"].get("causal_analysis") or [])],
        decision_implications=[
            str(item) for item in list(summary["summary"].get("decision_implications") or [])
        ],
        watch_items=[str(item) for item in list(summary["summary"].get("watch_items") or [])],
        highlights=[str(item) for item in list(payload.get("highlights") or [])],
        overall_signal=str((payload.get("belief_drift") or {}).get("overall_signal") or "diffuse"),
        outcome=str((payload.get("summary_stats") or {}).get("outcome") or "stable"),
        timeline_annotations=[TimelineAnnotation(**item) for item in list(annotations["annotations"] or [])],
        annotation_mode=str(annotations["mode"]),
        metrics=dict(payload.get("summary_stats") or {}),
        stance_groups=[dict(item) for item in list((payload.get("belief_drift") or {}).get("groups") or [])],
        zone_z_summary=[dict(item) for item in list(payload.get("zone_z_drift") or [])],
        top_z_movers=[dict(item) for item in list(payload.get("notable_agents") or [])],
        policy_events=[dict(item) for item in list(payload.get("key_events") or [])],
        belief_graph={
            "nodes": [dict(item) for item in list((payload.get("belief_graph") or {}).get("nodes") or [])],
            "edges": [dict(item) for item in list((payload.get("belief_graph") or {}).get("edges") or [])],
        },
        grounding={
            key: [
                ReviewGroundingItem(
                    anchor_id=str(item.get("anchor_id") or ""),
                    kind=str(item.get("kind") or key[:-1] or "evidence"),
                    label=str(item.get("label") or item.get("role_label") or item.get("zone_label") or item.get("name") or "evidence"),
                    reason=str(item.get("reason") or item.get("summary") or ""),
                    t=float(item.get("t")) if item.get("t") is not None else None,
                    group_id=str(item.get("group_id")) if item.get("group_id") is not None else None,
                    zone_id=str(item.get("zone_id")) if item.get("zone_id") is not None else None,
                    cell_id=str(item.get("cell_id")) if item.get("cell_id") is not None else None,
                    world_id=str(item.get("world_id")) if item.get("world_id") is not None else None,
                )
                for item in list(value or [])
            ]
            for key, value in dict(payload.get("grounding") or {}).items()
        },
        citations=_build_summary_citations(payload, summary["summary"].get("citations")),
        review_meta={
            "summary": {
                "prompt_version": summary["prompt_version"],
                "prompt_meta": dict(summary["prompt_meta"]),
                "provider": str(summary.get("provider") or ""),
                "model": str(summary.get("model") or ""),
                "fallback_reason": str(summary.get("fallback_reason") or ""),
            },
            "timeline_annotation": {
                "prompt_version": annotations["prompt_version"],
                "prompt_meta": dict(annotations["prompt_meta"]),
                "provider": str(annotations.get("provider") or ""),
                "model": str(annotations.get("model") or ""),
                "fallback_reason": str(annotations.get("fallback_reason") or ""),
            },
        },
    )


@router.get("/{world_id}/review/diff", response_model=ReviewDiffResponse)
def get_review_diff(world_id: str, base_world_id: str):
    target_entry = world_store.get(world_id)
    if target_entry is None:
        raise HTTPException(status_code=404, detail="Target world not found")
    base_entry = world_store.get(base_world_id)
    if base_entry is None:
        raise HTTPException(status_code=404, detail="Base world not found")
    try:
        target_payload = build_cached_world_review_payload(target_entry)
        base_payload = build_cached_world_review_payload(base_entry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    diff_payload = build_review_diff_payload(base_payload=base_payload, target_payload=target_payload)
    diff = llm_facade.compare_reviews(diff_payload=diff_payload)
    base_stats = dict(diff_payload.get("base_summary_stats") or {})
    target_stats = dict(diff_payload.get("target_summary_stats") or {})
    compared_metrics = {
        "base": base_stats,
        "target": target_stats,
        "delta": {
            "cell_delta_gap": int(target_stats.get("cell_delta", 0)) - int(base_stats.get("cell_delta", 0)),
            "energy_delta_gap": round(float(target_stats.get("energy_delta", 0.0)) - float(base_stats.get("energy_delta", 0.0)), 3),
            "z_delta_gap": round(float(target_stats.get("z_delta", 0.0)) - float(base_stats.get("z_delta", 0.0)), 3),
        },
        "group_drift_deltas": [dict(item) for item in list(diff_payload.get("group_drift_deltas") or [])],
        "zone_z_delta": [dict(item) for item in list(diff_payload.get("zone_z_delta") or [])],
        "policy_impact_delta": dict(diff_payload.get("policy_impact_delta") or {}),
        "timeline_turning_point_delta": dict(diff_payload.get("timeline_turning_point_delta") or {}),
        "coalition_shift_delta": dict(diff_payload.get("coalition_shift_delta") or {}),
    }
    return ReviewDiffResponse(
        base_world_id=base_world_id,
        target_world_id=world_id,
        headline=str(diff["diff"].get("headline") or ""),
        summary=str(diff["diff"].get("executive_summary") or ""),
        diff_mode=str(diff["mode"]),
        key_deltas=[str(item) for item in list(diff["diff"].get("key_deltas") or [])],
        causal_comparison=[str(item) for item in list(diff["diff"].get("causal_comparison") or [])],
        decision_implications=[str(item) for item in list(diff["diff"].get("decision_implications") or [])],
        compared_metrics=compared_metrics,
        citations=_build_diff_citations(diff_payload, diff["diff"].get("citations")),
        review_meta={
            "diff": {
                "prompt_version": diff["prompt_version"],
                "prompt_meta": dict(diff["prompt_meta"]),
                "provider": str(diff.get("provider") or ""),
                "model": str(diff.get("model") or ""),
                "fallback_reason": str(diff.get("fallback_reason") or ""),
            }
        },
    )


@router.post("/{world_id}/review/query", response_model=ReviewQueryResponse)
def post_review_query(world_id: str, body: ReviewQueryRequest):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    try:
        payload = build_cached_world_review_payload(entry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    query = llm_facade.query_review(payload, question=body.question)
    answer = dict(query.get("query") or {})
    return ReviewQueryResponse(
        world_id=world_id,
        question=body.question,
        answer=str(answer.get("answer") or ""),
        evidence=[str(item) for item in list(answer.get("evidence") or [])],
        follow_up=[str(item) for item in list(answer.get("follow_up") or [])],
        confidence_notes=[str(item) for item in list(answer.get("confidence_notes") or [])],
        mode=str(query.get("mode") or "heuristic"),
        grounding={
            key: [
                ReviewGroundingItem(
                    anchor_id=str(item.get("anchor_id") or ""),
                    kind=str(item.get("kind") or key[:-1] or "evidence"),
                    label=str(item.get("label") or item.get("role_label") or item.get("zone_label") or item.get("name") or "evidence"),
                    reason=str(item.get("reason") or item.get("summary") or ""),
                    t=float(item.get("t")) if item.get("t") is not None else None,
                    group_id=str(item.get("group_id")) if item.get("group_id") is not None else None,
                    zone_id=str(item.get("zone_id")) if item.get("zone_id") is not None else None,
                    cell_id=str(item.get("cell_id")) if item.get("cell_id") is not None else None,
                    world_id=str(item.get("world_id")) if item.get("world_id") is not None else None,
                )
                for item in list(value or [])
            ]
            for key, value in dict(payload.get("grounding") or {}).items()
        },
        citations=_citations_from_ids(payload, list(answer.get("citations") or [])),
        review_meta={
            "query": {
                "prompt_version": str(query.get("prompt_version") or ""),
                "prompt_meta": dict(query.get("prompt_meta") or {}),
                "provider": str(query.get("provider") or ""),
                "model": str(query.get("model") or ""),
                "fallback_reason": str(query.get("fallback_reason") or ""),
            }
        },
    )


@router.post("/{world_id}/review/diff-query", response_model=ReviewDiffQueryResponse)
def post_review_diff_query(world_id: str, base_world_id: str, body: ReviewDiffQueryRequest):
    target_entry = world_store.get(world_id)
    if target_entry is None:
        raise HTTPException(status_code=404, detail="Target world not found")
    base_entry = world_store.get(base_world_id)
    if base_entry is None:
        raise HTTPException(status_code=404, detail="Base world not found")
    try:
        target_payload = build_cached_world_review_payload(target_entry)
        base_payload = build_cached_world_review_payload(base_entry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    diff_payload = build_review_diff_payload(base_payload=base_payload, target_payload=target_payload)
    query = llm_facade.query_review_diff(diff_payload, question=body.question)
    answer = dict(query.get("query") or {})
    return ReviewDiffQueryResponse(
        base_world_id=base_world_id,
        target_world_id=world_id,
        question=body.question,
        answer=str(answer.get("answer") or ""),
        evidence=[str(item) for item in list(answer.get("evidence") or [])],
        follow_up=[str(item) for item in list(answer.get("follow_up") or [])],
        confidence_notes=[str(item) for item in list(answer.get("confidence_notes") or [])],
        mode=str(query.get("mode") or "heuristic"),
        grounding=_build_diff_citations(diff_payload),
        citations=_citations_from_ids(diff_payload, list(answer.get("citations") or [])),
        review_meta={
            "query": {
                "prompt_version": str(query.get("prompt_version") or ""),
                "prompt_meta": dict(query.get("prompt_meta") or {}),
                "provider": str(query.get("provider") or ""),
                "model": str(query.get("model") or ""),
                "fallback_reason": str(query.get("fallback_reason") or ""),
            }
        },
    )


def _ground_item(*, kind: str, label: str, reason: str = "", t: Optional[float] = None, group_id: Optional[str] = None, zone_id: Optional[str] = None, cell_id: Optional[str] = None, world_id: Optional[str] = None) -> ReviewGroundingItem:
    return ReviewGroundingItem(
        anchor_id=f"{kind}:{label}:{int(t) if t is not None else 'static'}",
        kind=kind,
        label=label,
        reason=reason,
        t=t,
        group_id=group_id,
        zone_id=zone_id,
        cell_id=cell_id,
        world_id=world_id,
    )


def _build_summary_citations(
    payload: Dict[str, Any],
    citation_ids: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[ReviewGroundingItem]]:
    if citation_ids:
        resolved = _citation_sections_from_ids(payload, citation_ids)
        if any(resolved.values()):
            return resolved
    groups = list((payload.get("belief_drift") or {}).get("groups") or [])
    events = list(payload.get("key_events") or [])
    zones = list(payload.get("zone_z_drift") or [])
    top_group = dict(groups[0] if groups else {})
    top_event = dict(events[0] if events else {})
    top_zone = dict(zones[0] if zones else {})
    return {
        "headline": [
            _ground_item(
                kind="group",
                label=str(top_group.get("role_label") or "group"),
                reason=f"stance {top_group.get('stance_before', 'n/a')} -> {top_group.get('stance_after', 'n/a')}",
                group_id=str(top_group.get("group_id")) if top_group.get("group_id") is not None else None,
            )
        ]
        if top_group
        else [],
        "causal_analysis": [
            _ground_item(
                kind="event",
                label=str(top_event.get("name") or "event"),
                reason=str(top_event.get("summary") or top_event.get("event_type") or ""),
                t=float(top_event.get("t")) if top_event.get("t") is not None else None,
            )
        ]
        if top_event
        else [],
        "decision_implications": [
            _ground_item(
                kind="zone",
                label=str(top_zone.get("zone_label") or "zone"),
                reason=f"avg z delta {float(top_zone.get('avg_z_delta', 0.0)):+.2f}",
                zone_id=str(top_zone.get("zone_id")) if top_zone.get("zone_id") is not None else None,
            )
        ]
        if top_zone
        else [],
    }


def _build_diff_citations(
    diff_payload: Dict[str, Any],
    citation_ids: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[ReviewGroundingItem]]:
    if citation_ids:
        resolved = _citation_sections_from_ids(diff_payload, citation_ids)
        if any(resolved.values()):
            return resolved
    target_world_id = str(diff_payload.get("target_world_id") or "")
    base_world_id = str(diff_payload.get("base_world_id") or "")
    groups = list(diff_payload.get("group_drift_deltas") or [])
    zones = list(diff_payload.get("zone_z_delta") or [])
    target_turning = list((diff_payload.get("timeline_turning_point_delta") or {}).get("target") or [])
    base_turning = list((diff_payload.get("timeline_turning_point_delta") or {}).get("base") or [])
    top_group = dict(groups[0] if groups else {})
    top_zone = dict(zones[0] if zones else {})
    top_target = dict(target_turning[0] if target_turning else {})
    top_base = dict(base_turning[0] if base_turning else {})
    return {
        "key_deltas": [
            _ground_item(
                kind="group",
                label=str(top_group.get("role_label") or "group"),
                reason=f"cohesion {float(top_group.get('cohesion_gap', 0.0)):+.2f}, tension {float(top_group.get('tension_gap', 0.0)):+.2f}",
                group_id=str(top_group.get("group_id")) if top_group.get("group_id") is not None else None,
            )
        ]
        if top_group
        else [],
        "causal_comparison": [
            _ground_item(
                kind="event",
                label=str(top_target.get("label") or "target shift"),
                reason=str(top_target.get("reason") or ""),
                t=float(top_target.get("t")) if top_target.get("t") is not None else None,
                world_id=target_world_id or None,
            ),
            _ground_item(
                kind="event",
                label=str(top_base.get("label") or "baseline shift"),
                reason=str(top_base.get("reason") or ""),
                t=float(top_base.get("t")) if top_base.get("t") is not None else None,
                world_id=base_world_id or None,
            ),
        ]
        if top_target or top_base
        else [],
        "decision_implications": [
            _ground_item(
                kind="zone",
                label=str(top_zone.get("zone_label") or "zone"),
                reason=f"avg z gap {float(top_zone.get('avg_z_gap', 0.0)):+.2f}",
                zone_id=str(top_zone.get("zone_id")) if top_zone.get("zone_id") is not None else None,
            )
        ]
        if top_zone
        else [],
    }


def _grounding_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    grounding = dict(payload.get("grounding") or {})
    rows: List[Dict[str, Any]] = []
    for value in grounding.values():
        rows.extend(dict(item) for item in list(value or []))
    return rows


def _grounding_index(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows = _grounding_rows(payload)
    return {
        str(item.get("anchor_id") or ""): item
        for item in rows
        if str(item.get("anchor_id") or "").strip()
    }


def _citations_from_ids(payload: Dict[str, Any], anchor_ids: List[str]) -> List[ReviewGroundingItem]:
    index = _grounding_index(payload)
    items: List[ReviewGroundingItem] = []
    for anchor_id in anchor_ids[:6]:
        row = index.get(str(anchor_id))
        if row is None:
            continue
        items.append(
            ReviewGroundingItem(
                anchor_id=str(row.get("anchor_id") or ""),
                kind=str(row.get("kind") or "evidence"),
                label=str(row.get("label") or "evidence"),
                reason=str(row.get("reason") or ""),
                t=float(row.get("t")) if row.get("t") is not None else None,
                group_id=str(row.get("group_id")) if row.get("group_id") is not None else None,
                zone_id=str(row.get("zone_id")) if row.get("zone_id") is not None else None,
                cell_id=str(row.get("cell_id")) if row.get("cell_id") is not None else None,
                world_id=str(row.get("world_id")) if row.get("world_id") is not None else None,
            )
        )
    return items


def _citation_sections_from_ids(
    payload: Dict[str, Any],
    citation_ids: Dict[str, List[str]],
) -> Dict[str, List[ReviewGroundingItem]]:
    return {
        str(section): _citations_from_ids(payload, list(anchor_ids or []))
        for section, anchor_ids in citation_ids.items()
    }
