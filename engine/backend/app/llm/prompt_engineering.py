"""Prompt construction for Thought and Worldview updates."""
from __future__ import annotations

import numpy as np

from app.core.emotion import EMOTION_LABELS
from app.core.memory_reflection import build_memory_reflection, build_worldview_reflection
from app.llm.prompt_registry import get_prompt_version
from app.models.cell import Cell


def build_thought_prompt(cell: Cell) -> str:
    ev = cell.emotion_vec
    dom = int(np.argmax(np.abs(ev))) if ev.size else 0
    label = EMOTION_LABELS[dom] if dom < len(EMOTION_LABELS) else "neutral"
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    recent_short = " ; ".join(
        str(item.get("summary") or "") for item in cell.short_memory[-4:] if str(item.get("summary") or "").strip()
    ) or "none"
    salient_long = " ; ".join(
        str(item.get("summary") or "") for item in cell.long_memory[-3:] if str(item.get("summary") or "").strip()
    ) or "none"
    reflection = build_memory_reflection(cell)
    return (
        f"strategy for role={role}: energy {cell.energy:.2f}, "
        f"dominant affect {label}, "
        f"gene_norm {float(np.linalg.norm(cell.gene_vec)):.3f}, "
        f"recent_short_memory={recent_short[:320]}, "
        f"salient_long_memory={salient_long[:280]}, "
        f"reflection={reflection[:360]}, "
        f"persona={cell.persona_text[:240]}"
    )


def build_worldview_prompt(cell: Cell) -> str:
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    reflection = build_worldview_reflection(cell)
    return f"role={role}; persona={cell.persona_text[:240]}; {reflection}"


def build_action_prompt(cell: Cell) -> str:
    ev = cell.emotion_vec
    dom = int(np.argmax(np.abs(ev))) if ev.size else 0
    label = EMOTION_LABELS[dom] if dom < len(EMOTION_LABELS) else "neutral"
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    reflection = build_memory_reflection(cell)
    worldview = build_worldview_reflection(cell)
    return (
        f"prompt_version={get_prompt_version('action')}; "
        f"role={role}; energy={cell.energy:.2f}; dominant_emotion={label}; "
        f"persona={cell.persona_text[:220]}; recent_memory={reflection[:320]}; "
        f"worldview={worldview[:320]}"
    )


def build_policy_prompt(cell: Cell, event_type: str, payload: dict) -> str:
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    worldview = build_worldview_reflection(cell)
    return (
        f"prompt_version={get_prompt_version('policy')}; "
        f"role={role}; persona={cell.persona_text[:220]}; "
        f"event_type={event_type}; payload={payload}; worldview={worldview[:320]}"
    )
