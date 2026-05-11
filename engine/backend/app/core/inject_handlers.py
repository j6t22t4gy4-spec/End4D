"""God View 주입 이벤트 → 세포 상태 변환 (Phase 7.1).

event_type별 payload 규약은 API 문서·프론트 기본값과 맞출 것.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.policy_events import normalize_policy_payload
from app.llm.policy import apply_policy_interpretation
from app.models.cell import Cell


def apply_inject_to_cells(
    cells: List[Cell],
    event_type: str,
    payload: Dict,
) -> List[Cell]:
    """스냅샷 시점의 세포 목록에 주입 효과 적용."""
    if event_type == "nutrient_burst":
        amt = float(payload.get("amount", 10.0))
        return [c.copy(energy=c.energy + amt) for c in cells]

    if event_type == "append_memory":
        text = str(payload.get("text", "injected event"))
        out: List[Cell] = []
        for c in cells:
            entry = memory_entry(
                t=float(c.t),
                kind="injected_memory",
                summary=text,
                importance=0.68,
                source="god_view.inject",
                payload=dict(payload),
                tags=["inject"],
            )
            behavior = behavior_event(
                t=float(c.t),
                event_type="append_memory",
                source="god_view.inject",
                summary=text,
                quality_score=0.68,
                payload=dict(payload),
            )
            out.append(append_memory(c, entry, behavior=behavior, promote=False))
        return out

    if event_type == "emotion_spike":
        idx = int(payload.get("index", 2))
        delta = float(payload.get("delta", 0.35))
        out: List[Cell] = []
        for c in cells:
            ev = c.emotion_vec.copy().astype(np.float32)
            if 0 <= idx < ev.shape[0]:
                ev[idx] = np.clip(float(ev[idx]) + delta, -1.0, 1.0)
            out.append(c.copy(emotion_vec=ev))
        return out

    if event_type == "noop":
        return [c.copy() for c in cells]

    if event_type == "policy_shift":
        policy_payload = normalize_policy_payload(dict(payload))
        return apply_policy_interpretation(
            [c.copy() for c in cells],
            event_type=event_type,
            payload=policy_payload,
        )

    if event_type == "review_feedback":
        text = str(payload.get("text", "analyst review feedback")).strip() or "analyst review feedback"
        worldview_shift = float(payload.get("worldview_shift", 0.04))
        cooperation_delta = float(payload.get("cooperation_delta", 0.05))
        target_roles = {str(item) for item in list(payload.get("target_roles") or []) if str(item).strip()}
        target_zones = {str(item) for item in list(payload.get("target_zones") or []) if str(item).strip()}
        out: List[Cell] = []
        for c in cells:
            role_match = not target_roles or (c.role_label in target_roles or c.role_key in target_roles)
            zone_match = not target_zones or c.zone_id in target_zones or c.zone_label in target_zones
            if not (role_match and zone_match):
                out.append(c.copy())
                continue
            entry = memory_entry(
                t=float(c.t),
                kind="review_feedback",
                summary=text,
                importance=0.82,
                source="review.feedback",
                payload=dict(payload),
                tags=["review", "feedback", "analyst"],
            )
            behavior = behavior_event(
                t=float(c.t),
                event_type="review_feedback",
                source="review.feedback",
                summary=text,
                quality_score=0.8,
                payload=dict(payload),
            )
            updated = append_memory(c, entry, behavior=behavior, promote=True)
            action_state = dict(updated.action_state)
            action_state["cooperation_bias"] = float(np.clip(float(action_state.get("cooperation_bias", 0.5)) + cooperation_delta, 0.0, 1.0))
            action_state["strategy_summary"] = str(action_state.get("strategy_summary") or "")[:220]
            worldview_vec = updated.worldview_vec.copy().astype(np.float32)
            worldview_vec = worldview_vec + np.full_like(worldview_vec, worldview_shift, dtype=np.float32)
            out.append(updated.copy(action_state=action_state, worldview_vec=worldview_vec))
        return out

    # 알 수 없는 타입: 보수적으로 복사만
    return [c.copy() for c in cells]
