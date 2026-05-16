"""t-boundary deep cognition runtime.

The live consultation loop should stay fast and visible. This module owns the
heavier t-boundary cognition work so graph nodes can remain orchestration code.
"""
from __future__ import annotations

from typing import Any

from app.llm.actions import update_action_states_if_due
from app.llm.dialogue import apply_agent_dialogues_if_due
from app.llm.group_deliberation import apply_group_deliberation_if_due


def run_deep_commit(
    cells: list,
    *,
    next_t: float,
    coalition_state: dict[str, Any] | None = None,
    coalition_history: list[dict[str, Any]] | None = None,
) -> tuple[list, dict[str, Any], list[dict[str, Any]]]:
    """Run heavier cognition and group deliberation at the t boundary."""
    cells = update_action_states_if_due(cells, next_t)
    cells = apply_agent_dialogues_if_due(cells, next_t)
    cells, next_coalition_state, next_coalition_history = apply_group_deliberation_if_due(
        cells,
        next_t,
        coalition_state=coalition_state,
        coalition_history=coalition_history,
    )
    return cells, dict(next_coalition_state), [dict(item) for item in next_coalition_history]
