"""Engine observability API for agent groups.

This is intentionally not a chatbot surface. It exposes the internal agent
state needed to inspect whether role/persona groups are forming distinct
energy, emotion, and memory trajectories.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.emotion import EMOTION_LABELS
from app.core.store import world_store
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


class AgentSummaryResponse(BaseModel):
    world_id: str
    t: float
    group_count: int
    cell_count: int
    groups: List[AgentGroupSummary]


def _role_group_id(cell: Cell) -> str:
    role_key = (cell.role_key or "agent").strip() or "agent"
    role_label = (cell.role_label or role_key).strip() or role_key
    return f"{role_key}:{role_label}"


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
            },
        )
        bucket["cells"].append(cell)
        country = (cell.persona_country or "unknown").strip() or "unknown"
        bucket["countries"][country] = bucket["countries"].get(country, 0) + 1
        bucket["emotion_sum"] += np.abs(cell.emotion_vec[: len(EMOTION_LABELS)])
        bucket["memory_count"] += len(cell.memory[-5:])

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
