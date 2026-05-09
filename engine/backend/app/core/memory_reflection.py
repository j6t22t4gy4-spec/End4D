"""Heuristic reflection over agent memory for Thought and Worldview quality."""
from __future__ import annotations

from collections import Counter
from typing import Iterable, List

from app.models.cell import Cell


def _sample_memory(memory: List[str], limit: int) -> List[str]:
    if len(memory) <= limit:
        return list(memory)
    stride = max(1, len(memory) // limit)
    sampled = memory[::stride][: max(limit - 3, 0)]
    sampled.extend(memory[-3:])
    return sampled[-limit:]


def _extract_role_counts(memory: Iterable[str]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in memory:
        if "roles=[" not in line:
            continue
        role_blob = line.split("roles=[", 1)[1].split("]", 1)[0]
        for chunk in role_blob.split(","):
            part = chunk.strip()
            if not part or ":" not in part:
                continue
            role, count = part.rsplit(":", 1)
            try:
                counts[role.strip()] += int(count.strip())
            except ValueError:
                continue
    return counts


def build_memory_reflection(cell: Cell) -> str:
    """Summarize long-horizon interaction signals into a compact belief string."""
    memory = list(cell.memory)
    if not memory:
        return "no memory yet"

    social_lines = [line for line in memory if "social_observation" in line]
    alignment_lines = [line for line in memory if "alignment=" in line]
    borrowed_lines = [line for line in memory if "borrowed_signal=" in line]
    role_counts = _extract_role_counts(memory)
    recurring_roles = ", ".join(
        f"{role}:{count}" for role, count in role_counts.most_common(3)
    ) or "none"

    alignment_counter = Counter()
    for line in alignment_lines:
        tag = line.split("alignment=", 1)[1].split(" ", 1)[0].strip()
        if tag:
            alignment_counter[tag] += 1
    dominant_alignment = alignment_counter.most_common(1)[0][0] if alignment_counter else "unknown"

    recent = " | ".join(_sample_memory(memory, 4))
    return (
        f"memory_size={len(memory)}; social_events={len(social_lines)}; "
        f"borrowed_signals={len(borrowed_lines)}; dominant_alignment={dominant_alignment}; "
        f"recurring_roles={recurring_roles}; recent={recent[:320]}"
    )


def build_worldview_reflection(cell: Cell) -> str:
    """Longer-horizon belief summary for worldview refreshes."""
    memory = list(cell.memory)
    if not memory:
        return "nascent worldview"
    sampled = _sample_memory(memory, 12)
    role_counts = _extract_role_counts(sampled)
    focus_roles = ", ".join(
        f"{role}:{count}" for role, count in role_counts.most_common(4)
    ) or "none"
    return (
        f"role={cell.role_label or cell.role_key or 'agent'}; "
        f"focus_roles={focus_roles}; "
        f"reflection={build_memory_reflection(cell)}; "
        f"long_horizon={' ; '.join(sampled)[:720]}"
    )
