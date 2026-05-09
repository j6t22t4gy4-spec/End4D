"""Role-level negotiation and coalition updates."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Dict, List

from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.settings import (
    get_group_deliberation_interval,
    get_group_deliberation_max_groups,
    get_llm_agent_sample_size,
)
from app.llm.chat_runtime import generate_reasoning_texts
from app.llm.prompt_engineering import build_group_deliberation_prompt
from app.models.cell import Cell


def apply_group_deliberation_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    """Run capped role-level deliberation and propagate group stance pressure."""
    t_int = int(current_t)
    interval = get_group_deliberation_interval()
    if not cells or t_int <= 0 or t_int % interval != 0:
        return cells

    groups = _select_role_groups(cells, get_group_deliberation_max_groups())
    if not groups:
        return cells

    prompts = [
        build_group_deliberation_prompt(role, members[: min(len(members), 16)], current_t=current_t)
        for role, members in groups.items()
    ]
    generated = generate_reasoning_texts(prompts, task="group_deliberation")
    out = [cell.copy() for cell in cells]
    index_by_id = {cell.cell_id: idx for idx, cell in enumerate(out)}
    representative_limit = max(4, get_llm_agent_sample_size() // max(1, len(groups)))

    for (role, members), text in zip(groups.items(), generated):
        outcome = _parse_group_outcome(text, role)
        for member in members:
            idx = index_by_id.get(member.cell_id)
            if idx is None:
                continue
            out[idx] = _apply_group_pressure(out[idx], outcome, write_memory=False, current_t=current_t)
        for member in members[:representative_limit]:
            idx = index_by_id.get(member.cell_id)
            if idx is None:
                continue
            out[idx] = _apply_group_pressure(out[idx], outcome, write_memory=True, current_t=current_t)
    return out


def _select_role_groups(cells: List[Cell], max_groups: int) -> Dict[str, List[Cell]]:
    grouped: dict[str, list[Cell]] = defaultdict(list)
    for cell in cells:
        role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
        grouped[role].append(cell)
    ranked = sorted(
        grouped.items(),
        key=lambda item: (
            -len(item[1]),
            -sum(float(c.action_state.get("policy_sensitivity", 0.5)) for c in item[1]) / max(1, len(item[1])),
            item[0],
        ),
    )
    return dict(ranked[:max_groups])


def _apply_group_pressure(
    cell: Cell,
    outcome: Dict[str, float | str],
    *,
    write_memory: bool,
    current_t: float,
) -> Cell:
    current_action = dict(cell.action_state)
    current_action["cooperation_bias"] = _clip01(
        float(current_action.get("cooperation_bias", 0.5)) + float(outcome["cohesion_delta"]) * 0.4
    )
    current_action["risk_tolerance"] = _clip01(
        float(current_action.get("risk_tolerance", 0.5)) + float(outcome["tension_delta"]) * 0.2
    )
    current_action["group_coalition_signal"] = str(outcome["coalition_signal"])
    current_action["last_group_stance"] = str(outcome["stance_summary"])
    updated = cell.copy(action_state=current_action)
    if not write_memory:
        return updated

    entry = memory_entry(
        t=float(current_t),
        kind="group_deliberation",
        summary=str(outcome["stance_summary"]),
        importance=float(outcome["importance"]),
        source="llm.group_deliberation",
        payload=dict(outcome),
        tags=["llm", "group", "deliberation"],
    )
    behavior = behavior_event(
        t=float(current_t),
        event_type="group_deliberation",
        source="llm.group_deliberation",
        summary=str(outcome["stance_summary"]),
        quality_score=float(outcome["importance"]),
        payload=dict(outcome),
    )
    return append_memory(updated, entry, behavior=behavior, promote=float(outcome["importance"]) >= 0.76)


def _parse_group_outcome(text: str, role: str) -> Dict[str, float | str]:
    payload = _extract_json_object(text)
    if payload is None:
        return {
            "stance_summary": f"{role} group reinforces a pragmatic negotiated stance",
            "cohesion_delta": 0.05,
            "tension_delta": 0.02,
            "coalition_signal": "weak",
            "importance": 0.68,
        }
    return {
        "stance_summary": str(payload.get("stance_summary") or f"{role} group stance updated"),
        "cohesion_delta": _signed(payload.get("cohesion_delta"), default=0.04),
        "tension_delta": _signed(payload.get("tension_delta"), default=0.02),
        "coalition_signal": str(payload.get("coalition_signal") or "weak"),
        "importance": _clip01(float(payload.get("importance", 0.68))),
    }


def _extract_json_object(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
    return None


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _signed(value, *, default: float) -> float:
    try:
        return max(-1.0, min(1.0, float(value)))
    except Exception:
        return default
