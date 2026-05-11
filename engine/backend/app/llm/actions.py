"""LLM-backed action planning for agents."""
from __future__ import annotations

import json
from typing import Dict, List

from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.settings import get_action_refresh_interval, get_llm_agent_sample_size, get_llm_runtime_profile
from app.llm.facade import llm_facade
from app.models.cell import Cell


def update_action_states_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    interval = get_action_refresh_interval()
    if t_int < 0 or t_int % interval != 0:
        return cells

    selected = _selected_indices(cells, t_int, get_llm_agent_sample_size())
    selected_cells = [cells[idx] for idx in selected]
    generated = llm_facade.decide_actions(selected_cells)
    out: List[Cell] = [cell.copy() for cell in cells]
    for idx, cell, text in zip(selected, selected_cells, generated):
        action_state = _parse_action_state(text, cell)
        entry = memory_entry(
            t=float(current_t),
            kind="action_plan",
            summary=str(action_state.get("strategy_summary") or "action plan"),
            importance=0.62,
            source="llm.action",
            payload=dict(action_state),
            tags=["llm", "action_plan"],
        )
        behavior = behavior_event(
            t=float(current_t),
            event_type="action_plan",
            source="llm.action",
            summary=str(action_state.get("strategy_summary") or "action plan"),
            quality_score=0.66,
            payload=dict(action_state),
        )
        updated = append_memory(cell.copy(action_state=action_state), entry, behavior=behavior, promote=False)
        out[idx] = updated
    selected_set = set(selected)
    for idx, cell in enumerate(out):
        if idx in selected_set:
            continue
        if not cell.action_state:
            out[idx] = cell.copy(action_state=_heuristic_action_state(cell))
    return out


def _selected_indices(cells: List[Cell], t_int: int, limit: int) -> List[int]:
    if len(cells) <= limit:
        return list(range(len(cells)))
    profile = get_llm_runtime_profile()
    ranked = sorted(
        range(len(cells)),
        key=lambda idx: (
            -(0 if cells[idx].action_state else 1),
            -len(cells[idx].short_memory) - len(cells[idx].behavior_log),
            -float(cells[idx].energy),
            f"{t_int}:{cells[idx].cell_id}",
        ),
    )
    if profile == "llm-first":
        return ranked[: min(len(ranked), limit)]
    return ranked[:limit]


def _parse_action_state(text: str, cell: Cell) -> Dict[str, float | str]:
    payload = _extract_json_object(text)
    if payload is None:
        return _heuristic_action_state(cell)
    try:
        state = {
            "strategy_summary": str(payload.get("strategy_summary") or "adaptive planning"),
            "resource_bias": _bounded_float(payload.get("resource_bias"), default=0.55),
            "risk_tolerance": _bounded_float(payload.get("risk_tolerance"), default=0.5),
            "cooperation_bias": _bounded_float(payload.get("cooperation_bias"), default=0.5),
            "policy_sensitivity": _bounded_float(payload.get("policy_sensitivity"), default=0.5),
            "mobility_bias": _bounded_float(payload.get("mobility_bias"), default=0.4),
        }
        return state
    except Exception:
        return _heuristic_action_state(cell)


def _heuristic_action_state(cell: Cell) -> Dict[str, float | str]:
    long_factor = min(1.0, len(cell.long_memory) / 12.0)
    short_factor = min(1.0, len(cell.short_memory) / 12.0)
    energy_factor = max(0.0, min(1.0, float(cell.energy) / 120.0))
    return {
        "strategy_summary": "heuristic adaptive stance",
        "resource_bias": 0.45 + 0.35 * energy_factor,
        "risk_tolerance": 0.35 + 0.25 * short_factor,
        "cooperation_bias": 0.45 + 0.3 * long_factor,
        "policy_sensitivity": 0.4 + 0.35 * short_factor,
        "mobility_bias": 0.35 + 0.2 * (1.0 - long_factor),
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


def _bounded_float(value, *, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default
