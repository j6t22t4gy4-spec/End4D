"""Post-simulation review APIs."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.review_payloads import build_world_review_payload
from app.core.store import world_store
from app.llm.facade import llm_facade

router = APIRouter(prefix="/worlds", tags=["review"])


class TimelineAnnotation(BaseModel):
    t: float
    label: str
    reason: str
    severity: str


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
    review_meta: Dict[str, Any] = Field(default_factory=dict)


@router.get("/{world_id}/review/summary", response_model=ReviewSummaryResponse)
def get_review_summary(world_id: str):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    try:
        payload = build_world_review_payload(entry)
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
        target_payload = build_world_review_payload(target_entry)
        base_payload = build_world_review_payload(base_entry)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    diff = llm_facade.compare_reviews(base_payload=base_payload, target_payload=target_payload)
    base_stats = dict(base_payload.get("summary_stats") or {})
    target_stats = dict(target_payload.get("summary_stats") or {})
    compared_metrics = {
        "base": base_stats,
        "target": target_stats,
        "delta": {
            "cell_delta_gap": int(target_stats.get("cell_delta", 0)) - int(base_stats.get("cell_delta", 0)),
            "energy_delta_gap": round(float(target_stats.get("energy_delta", 0.0)) - float(base_stats.get("energy_delta", 0.0)), 3),
            "z_delta_gap": round(float(target_stats.get("z_delta", 0.0)) - float(base_stats.get("z_delta", 0.0)), 3),
        },
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
