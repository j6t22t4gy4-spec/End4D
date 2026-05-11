"""Engine observability API for agent groups.

This is intentionally not a chatbot surface. It exposes the internal agent
state needed to inspect whether role/persona groups are forming distinct
energy, emotion, and memory trajectories.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.emotion import EMOTION_LABELS
from app.core.memory_reflection import build_memory_reflection
from app.core.store import world_store
from app.llm.facade import llm_facade
from app.models.cell import Cell

router = APIRouter(prefix="/worlds", tags=["agents"])


class AgentGroupSummary(BaseModel):
    group_id: str
    role_key: str
    role_label: str
    cell_count: int
    total_energy: float
    avg_energy: float
    dominant_emotion: str
    avg_emotion_magnitude: float
    countries: Dict[str, int] = Field(default_factory=dict)
    recent_memory_count: int = 0
    long_memory_count: int = 0
    avg_interaction_quality: float = 0.0


class AgentSummaryResponse(BaseModel):
    world_id: str
    t: float
    group_count: int
    cell_count: int
    groups: List[AgentGroupSummary]


class AgentStanceGroup(BaseModel):
    group_id: str
    role_label: str
    stance: str
    cohesion_score: float
    tension_score: float
    avg_interaction_quality: float
    long_memory_count: int
    summary: str


class AgentStanceSummaryResponse(BaseModel):
    world_id: str
    t: float
    overall_signal: str
    groups: List[AgentStanceGroup]


class AgentInterviewRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    t: Optional[float] = None


class AgentInterviewGroundingItem(BaseModel):
    anchor_id: str
    kind: str
    label: str
    reason: str = ""
    t: Optional[float] = None
    cell_id: Optional[str] = None
    world_id: Optional[str] = None


class AgentInterviewResponse(BaseModel):
    world_id: str
    cell_id: str
    question: str
    answer: str
    evidence: List[str] = Field(default_factory=list)
    confidence_notes: List[str] = Field(default_factory=list)
    mode: str
    grounding: Dict[str, List[AgentInterviewGroundingItem]] = Field(default_factory=dict)
    citations: List[AgentInterviewGroundingItem] = Field(default_factory=list)
    interview_meta: Dict[str, Any] = Field(default_factory=dict)


def _role_group_id(cell: Cell) -> str:
    role_key = (cell.role_key or "agent").strip() or "agent"
    role_label = (cell.role_label or role_key).strip() or role_key
    return f"{role_key}:{role_label}"


def _resolve_snapshot(entry: dict, t: Optional[float]):
    store = entry["snapshot_store"]
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")
    if t is None:
        available_t = store.list_t()
        if not available_t:
            raise HTTPException(status_code=404, detail="No snapshot available")
        snap = store.get(available_t[-1])
    else:
        snap = store.get(t) or store.get_nearest(t)
    if snap is None:
        raise HTTPException(status_code=404, detail="No snapshot available")
    return snap


def _find_cell(snapshot, cell_id: str) -> Cell:
    for cell in snapshot.cells:
        if cell.cell_id == cell_id:
            return cell
    raise HTTPException(status_code=404, detail="Agent not found")


def _build_agent_grounding(*, world_id: str, cell: Cell) -> dict[str, list[dict[str, Any]]]:
    persona_attrs = dict(cell.persona_attrs or {})
    return {
        "persona": [
            {
                "anchor_id": f"persona:{world_id}:{cell.cell_id}",
                "kind": "persona",
                "label": str(cell.role_label or cell.role_key or "agent"),
                "reason": str(cell.persona_text or ""),
                "cell_id": cell.cell_id,
                "world_id": world_id,
            }
        ],
        "memories": [
            {
                "anchor_id": f"memory:{world_id}:{cell.cell_id}:{idx}",
                "kind": "memory",
                "label": str(item.get("summary") or "memory"),
                "reason": str(item.get("payload", {}).get("belief_polarity") or item.get("summary") or ""),
                "t": float(item.get("t")) if item.get("t") is not None else None,
                "cell_id": cell.cell_id,
                "world_id": world_id,
            }
            for idx, item in enumerate((list(cell.short_memory or [])[-3:] + list(cell.long_memory or [])[-3:]), start=1)
            if str(item.get("summary") or "").strip()
        ],
        "behaviors": [
            {
                "anchor_id": f"behavior:{world_id}:{cell.cell_id}:{idx}",
                "kind": "behavior",
                "label": str(item.get("event_type") or "behavior"),
                "reason": str(item.get("summary") or ""),
                "t": float(item.get("t")) if item.get("t") is not None else None,
                "cell_id": cell.cell_id,
                "world_id": world_id,
            }
            for idx, item in enumerate(list(cell.behavior_log or [])[-4:], start=1)
        ],
        "state": [
            {
                "anchor_id": f"state:{world_id}:{cell.cell_id}",
                "kind": "state",
                "label": str(cell.zone_label or cell.zone_id or "zone"),
                "reason": build_memory_reflection(cell)[:240],
                "t": float(cell.t),
                "cell_id": cell.cell_id,
                "world_id": world_id,
            }
        ],
        "attrs": [
            {
                "anchor_id": f"attrs:{world_id}:{cell.cell_id}",
                "kind": "attrs",
                "label": str(persona_attrs.get("occupation") or persona_attrs.get("region") or "persona_attrs"),
                "reason": "; ".join(f"{key}={value}" for key, value in list(persona_attrs.items())[:6]),
                "cell_id": cell.cell_id,
                "world_id": world_id,
            }
        ] if persona_attrs else [],
    }


def _citation_items(grounding: dict[str, list[dict[str, Any]]], anchor_ids: list[str]) -> list[AgentInterviewGroundingItem]:
    index = {
        str(item.get("anchor_id") or ""): item
        for values in grounding.values()
        for item in list(values or [])
        if str(item.get("anchor_id") or "").strip()
    }
    return [
        AgentInterviewGroundingItem(**dict(index[anchor_id]))
        for anchor_id in anchor_ids[:6]
        if anchor_id in index
    ]


@router.get("/{world_id}/agents/summary", response_model=AgentSummaryResponse)
def get_agent_summary(
    world_id: str,
    t: Optional[float] = Query(None, description="시점 t. 미지정 시 최신 스냅샷 사용"),
):
    """Aggregate the latest/selected snapshot by role/persona group."""
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")

    store = entry["snapshot_store"]
    snap = _resolve_snapshot(entry, t)

    buckets: dict[str, dict] = {}
    for cell in snap.cells:
        group_id = _role_group_id(cell)
        role_key = (cell.role_key or "agent").strip() or "agent"
        role_label = (cell.role_label or role_key).strip() or role_key
        bucket = buckets.setdefault(
            group_id,
            {
                "role_key": role_key,
                "role_label": role_label,
                "cells": [],
                "countries": {},
                "emotion_sum": np.zeros(len(EMOTION_LABELS), dtype=float),
                "memory_count": 0,
                "long_memory_count": 0,
                "interaction_quality_sum": 0.0,
            },
        )
        bucket["cells"].append(cell)
        country = (cell.persona_country or "unknown").strip() or "unknown"
        bucket["countries"][country] = bucket["countries"].get(country, 0) + 1
        bucket["emotion_sum"] += np.abs(cell.emotion_vec[: len(EMOTION_LABELS)])
        bucket["memory_count"] += len(cell.memory[-5:])
        bucket["long_memory_count"] += len(cell.long_memory)
        qualities = [
            float(item.get("quality_score", 0.0))
            for item in cell.behavior_log[-12:]
            if item.get("event_type") == "social_observation"
        ]
        bucket["interaction_quality_sum"] += sum(qualities) / len(qualities) if qualities else 0.0

    groups: List[AgentGroupSummary] = []
    for group_id, bucket in buckets.items():
        cells = bucket["cells"]
        count = len(cells)
        total_energy = float(sum(c.energy for c in cells))
        avg_energy = total_energy / count if count else 0.0
        emotion_avg = bucket["emotion_sum"] / count if count else bucket["emotion_sum"]
        dominant_idx = int(np.argmax(emotion_avg)) if emotion_avg.size else 0
        dominant_emotion = (
            EMOTION_LABELS[dominant_idx]
            if dominant_idx < len(EMOTION_LABELS)
            else "neutral"
        )
        groups.append(
            AgentGroupSummary(
                group_id=group_id,
                role_key=bucket["role_key"],
                role_label=bucket["role_label"],
                cell_count=count,
                total_energy=total_energy,
                avg_energy=avg_energy,
                dominant_emotion=dominant_emotion,
                avg_emotion_magnitude=float(np.linalg.norm(emotion_avg)),
                countries=dict(sorted(bucket["countries"].items())),
                recent_memory_count=int(bucket["memory_count"]),
                long_memory_count=int(bucket["long_memory_count"]),
                avg_interaction_quality=(
                    float(bucket["interaction_quality_sum"]) / count if count else 0.0
                ),
            )
        )

    groups.sort(key=lambda g: (-g.cell_count, g.role_label, g.role_key))
    return AgentSummaryResponse(
        world_id=world_id,
        t=float(snap.t),
        group_count=len(groups),
        cell_count=len(snap.cells),
        groups=groups,
    )


@router.get("/{world_id}/agents/stance-summary", response_model=AgentStanceSummaryResponse)
def get_agent_stance_summary(
    world_id: str,
    t: Optional[float] = Query(None, description="시점 t. 미지정 시 최신 스냅샷 사용"),
):
    """Summarize emerging stance and cohesion per role group."""
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    snap = _resolve_snapshot(entry, t)

    grouped: dict[str, list[Cell]] = {}
    for cell in snap.cells:
        grouped.setdefault(_role_group_id(cell), []).append(cell)

    groups: List[AgentStanceGroup] = []
    for group_id, cells in grouped.items():
        role_label = (cells[0].role_label or cells[0].role_key or "agent").strip() or "agent"
        qualities = [
            float(item.get("quality_score", 0.0))
            for cell in cells
            for item in cell.behavior_log[-16:]
            if item.get("event_type") in {"social_observation", "agent_dialogue", "group_deliberation"}
        ]
        polarities = [
            str(item.get("payload", {}).get("belief_polarity") or "")
            for cell in cells
            for item in cell.behavior_log[-16:]
            if item.get("event_type") == "social_observation"
        ]
        dialogue_trust = [
            float(item.get("trust", 0.0))
            for cell in cells
            for item in cell.relationship_state.values()
        ]
        dialogue_tension = [
            float(item.get("tension", 0.0))
            for cell in cells
            for item in cell.relationship_state.values()
        ]
        cluster_signals = [
            str(item.get("payload", {}).get("cluster_signal") or "")
            for cell in cells
            for item in cell.behavior_log[-16:]
            if item.get("event_type") == "social_observation"
        ]
        cohesion_score = float(np.mean(qualities)) if qualities else 0.0
        if dialogue_trust:
            cohesion_score = min(1.0, cohesion_score * 0.7 + float(np.mean(dialogue_trust)) * 0.3)
        tension_score = float(sum(1 for p in polarities if p == "counter_alignment")) / max(len(polarities), 1)
        if dialogue_tension:
            tension_score = min(1.0, tension_score * 0.7 + float(np.mean(dialogue_tension)) * 0.3)
        long_memory_count = sum(len(cell.long_memory) for cell in cells)
        if cohesion_score >= 0.72 and tension_score < 0.2:
            stance = "cohesive"
        elif tension_score >= 0.35:
            stance = "contested"
        elif "emergent_cluster" in cluster_signals or cohesion_score >= 0.5:
            stance = "emergent"
        else:
            stance = "diffuse"
        summary = (
            f"role={role_label} stance={stance} cohesion={cohesion_score:.2f} "
            f"tension={tension_score:.2f} long_memory={long_memory_count}"
        )
        groups.append(
            AgentStanceGroup(
                group_id=group_id,
                role_label=role_label,
                stance=stance,
                cohesion_score=cohesion_score,
                tension_score=tension_score,
                avg_interaction_quality=cohesion_score,
                long_memory_count=long_memory_count,
                summary=summary,
            )
        )

    groups.sort(key=lambda g: (-g.cohesion_score, g.role_label))
    overall_signal = "diffuse"
    if groups and sum(1 for g in groups if g.stance == "cohesive") >= 1:
        overall_signal = "clustered"
    if groups and any(g.stance == "contested" for g in groups):
        overall_signal = "contested"
    return AgentStanceSummaryResponse(
        world_id=world_id,
        t=float(snap.t),
        overall_signal=overall_signal,
        groups=groups,
    )


@router.post("/{world_id}/agents/{cell_id}/query", response_model=AgentInterviewResponse)
def post_agent_interview(world_id: str, cell_id: str, body: AgentInterviewRequest):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    snap = _resolve_snapshot(entry, body.t)
    cell = _find_cell(snap, cell_id)
    grounding = _build_agent_grounding(world_id=world_id, cell=cell)
    interview = llm_facade.interview_agent(cell=cell, question=body.question, grounding=grounding)
    answer = dict(interview.get("query") or {})
    return AgentInterviewResponse(
        world_id=world_id,
        cell_id=cell_id,
        question=body.question,
        answer=str(answer.get("answer") or ""),
        evidence=[str(item) for item in list(answer.get("evidence") or [])],
        confidence_notes=[str(item) for item in list(answer.get("confidence_notes") or [])],
        mode=str(interview.get("mode") or "heuristic"),
        grounding={
            key: [AgentInterviewGroundingItem(**dict(item)) for item in list(values or [])]
            for key, values in grounding.items()
        },
        citations=_citation_items(grounding, [str(item) for item in list(answer.get("citations") or [])]),
        interview_meta={
            "query": {
                "prompt_version": str(interview.get("prompt_version") or ""),
                "prompt_meta": dict(interview.get("prompt_meta") or {}),
                "provider": str(interview.get("provider") or ""),
                "model": str(interview.get("model") or ""),
                "fallback_reason": str(interview.get("fallback_reason") or ""),
            }
        },
    )
