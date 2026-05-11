"""Role-level negotiation and coalition updates."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Tuple

from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.relationship_state import average_relationship_metrics
from app.core.settings import (
    get_group_deliberation_interval,
    get_group_deliberation_max_groups,
    get_group_representative_limit,
)
from app.llm.facade import llm_facade
from app.models.cell import Cell

COALITION_HISTORY_LIMIT = 64


def apply_group_deliberation_if_due(
    cells: List[Cell],
    current_t: float,
    *,
    coalition_state: Dict[str, Dict[str, Any]] | None = None,
    coalition_history: List[Dict[str, Any]] | None = None,
) -> Tuple[List[Cell], Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    """Run capped role-level deliberation and propagate group stance pressure."""
    t_int = int(current_t)
    interval = get_group_deliberation_interval()
    current_state = {
        str(role): dict(payload)
        for role, payload in (coalition_state or {}).items()
    }
    history = [dict(item) for item in (coalition_history or [])]
    if not cells or t_int <= 0 or t_int % interval != 0:
        return cells, current_state, history

    groups = _select_role_groups(cells, get_group_deliberation_max_groups())
    if not groups:
        return cells, current_state, history

    prompt_groups = {
        role: members[: min(len(members), 16)]
        for role, members in groups.items()
    }
    generated = llm_facade.deliberate_groups(prompt_groups, current_t=current_t)
    out = [cell.copy() for cell in cells]
    index_by_id = {cell.cell_id: idx for idx, cell in enumerate(out)}
    representative_limit = get_group_representative_limit(len(groups))

    for (role, members), text in zip(groups.items(), generated):
        outcome = _parse_group_outcome(text, role)
        relationship_snapshot = average_relationship_metrics(members)
        outcome["avg_trust"] = relationship_snapshot["avg_trust"]
        outcome["avg_relationship_tension"] = relationship_snapshot["avg_tension"]
        outcome["repeat_peer_density"] = relationship_snapshot["repeat_peer_density"]
        prior_state = dict(current_state.get(role) or {})
        coalition_record = _build_coalition_record(
            role,
            outcome,
            members,
            current_t=current_t,
            prior_state=prior_state,
        )
        current_state[role] = coalition_record
        history.append(dict(coalition_record))
        for member in members:
            idx = index_by_id.get(member.cell_id)
            if idx is None:
                continue
            out[idx] = _apply_group_pressure(
                out[idx],
                outcome,
                coalition_record=coalition_record,
                write_memory=False,
                current_t=current_t,
            )
        for member in members[:representative_limit]:
            idx = index_by_id.get(member.cell_id)
            if idx is None:
                continue
            out[idx] = _apply_group_pressure(
                out[idx],
                outcome,
                coalition_record=coalition_record,
                write_memory=True,
                current_t=current_t,
            )
    return out, current_state, history[-COALITION_HISTORY_LIMIT:]


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
    coalition_record: Dict[str, Any],
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
    current_action["group_cohesion_score"] = _clip01(float(outcome["cohesion_score"]))
    current_action["group_tension_score"] = _clip01(float(outcome["relationship_tension"]))
    current_action["group_cycle_count"] = int(coalition_record.get("cycle_count", 1))
    current_action["group_block_key"] = str(coalition_record.get("block_key") or "")
    updated = cell.copy(action_state=current_action)
    if not write_memory:
        return updated

    entry = memory_entry(
        t=float(current_t),
        kind="group_deliberation",
        summary=str(outcome["stance_summary"]),
        importance=float(outcome["importance"]),
        source="llm.group_deliberation",
        payload={**dict(outcome), "coalition_record": dict(coalition_record)},
        tags=["llm", "group", "deliberation"],
    )
    behavior = behavior_event(
        t=float(current_t),
        event_type="group_deliberation",
        source="llm.group_deliberation",
        summary=str(outcome["stance_summary"]),
        quality_score=float(outcome["importance"]),
        payload={**dict(outcome), "coalition_record": dict(coalition_record)},
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
            "cohesion_score": 0.58,
            "relationship_tension": 0.22,
            "importance": 0.68,
        }
    return {
        "stance_summary": str(payload.get("stance_summary") or f"{role} group stance updated"),
        "cohesion_delta": _signed(payload.get("cohesion_delta"), default=0.04),
        "tension_delta": _signed(payload.get("tension_delta"), default=0.02),
        "coalition_signal": str(payload.get("coalition_signal") or "weak"),
        "cohesion_score": _clip01(float(payload.get("cohesion_score", 0.58))),
        "relationship_tension": _clip01(float(payload.get("relationship_tension", 0.22))),
        "importance": _clip01(float(payload.get("importance", 0.68))),
    }


def _build_coalition_record(
    role: str,
    outcome: Dict[str, float | str],
    members: List[Cell],
    *,
    current_t: float,
    prior_state: Dict[str, Any],
) -> Dict[str, Any]:
    cycle_count = int(prior_state.get("cycle_count", 0)) + 1
    prior_signal = str(prior_state.get("coalition_signal") or "")
    signal = str(outcome.get("coalition_signal") or "weak")
    if signal == prior_signal and cycle_count >= 2:
        block_key = f"{role}:{signal}:stable"
    elif cycle_count >= 3 and signal in {"moderate", "strong"}:
        block_key = f"{role}:{signal}:emergent"
    else:
        block_key = f"{role}:{signal}"
    return {
        "role": role,
        "member_count": len(members),
        "updated_t": float(current_t),
        "cycle_count": cycle_count,
        "coalition_signal": signal,
        "block_key": block_key,
        "stance_summary": str(outcome.get("stance_summary") or f"{role} stance updated"),
        "cohesion_score": _clip01(float(outcome.get("cohesion_score", 0.58))),
        "relationship_tension": _clip01(float(outcome.get("relationship_tension", 0.22))),
        "avg_trust": _clip01(float(outcome.get("avg_trust", 0.0))),
        "avg_relationship_tension": _clip01(float(outcome.get("avg_relationship_tension", 0.0))),
        "repeat_peer_density": max(0.0, float(outcome.get("repeat_peer_density", 0.0))),
        "importance": _clip01(float(outcome.get("importance", 0.68))),
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
