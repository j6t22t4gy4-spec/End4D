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


def build_dialogue_prompt(a: Cell, b: Cell, *, current_t: float) -> str:
    role_a = (a.role_label or a.role_key or "agent").strip() or "agent"
    role_b = (b.role_label or b.role_key or "agent").strip() or "agent"
    return (
        f"prompt_version={get_prompt_version('dialogue')}; t={float(current_t):.1f}; "
        f"agent_a={{role:{role_a}, energy:{a.energy:.2f}, action:{dict(a.action_state)}, "
        f"memory:{build_memory_reflection(a)[:260]}}}; "
        f"agent_b={{role:{role_b}, energy:{b.energy:.2f}, action:{dict(b.action_state)}, "
        f"memory:{build_memory_reflection(b)[:260]}}}"
    )


def build_group_deliberation_prompt(role: str, cells: list[Cell], *, current_t: float) -> str:
    if not cells:
        return f"prompt_version={get_prompt_version('group_deliberation')}; empty_group={role}"
    avg_energy = sum(float(c.energy) for c in cells) / len(cells)
    avg_coop = sum(float(c.action_state.get("cooperation_bias", 0.5)) for c in cells) / len(cells)
    avg_policy = sum(float(c.action_state.get("policy_sensitivity", 0.5)) for c in cells) / len(cells)
    memories = " | ".join(
        build_memory_reflection(c)[:180]
        for c in cells[:5]
        if build_memory_reflection(c).strip()
    ) or "none"
    return (
        f"prompt_version={get_prompt_version('group_deliberation')}; t={float(current_t):.1f}; "
        f"role={role}; sample_size={len(cells)}; avg_energy={avg_energy:.2f}; "
        f"avg_cooperation={avg_coop:.3f}; avg_policy_sensitivity={avg_policy:.3f}; "
        f"sample_memories={memories[:800]}"
    )
