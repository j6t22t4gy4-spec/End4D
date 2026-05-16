"""Fast intra-t consultation planning for End4D.

MiroFish/OASIS-style systems feel responsive because each round activates a
small slice of agents instead of forcing every actor through expensive cognition.
This module keeps that performance shape while preserving End4D's identity:
the score comes from the 4D social field, collective pressure, decision
influence, local density, and relationship events.
"""
from __future__ import annotations

from typing import Any

CONSULTATION_KERNEL_REVISION = "consultation-kernel-v9-fast-visible-stream"


def precision_internal_interaction_count(
    cells: list,
    *,
    engine_params: dict,
    previous_group_state: dict | None,
) -> int:
    mode = str(engine_params.get("simulation_mode") or "precision").strip().lower()
    cell_count = len(cells)
    if mode == "swarm":
        default_min = 2
        default_max = 4
        if cell_count >= 3000:
            default_max = 2
        elif cell_count >= 1000:
            default_max = 3
        min_steps = max(2, int(engine_params.get("min_interactions_per_step", default_min)))
        max_steps = max(min_steps, int(engine_params.get("max_interactions_per_step", default_max)))
        max_steps = min(max_steps, default_max)
    else:
        configured_min = engine_params.get("min_interactions_per_step")
        configured_max = engine_params.get("max_interactions_per_step")
        min_steps = max(1, int(configured_min)) if configured_min is not None else 20
        max_steps = max(min_steps, int(configured_max)) if configured_max is not None else max(min_steps, 42)
        if cell_count >= 1500:
            max_steps = min(max_steps, 20)
        elif cell_count >= 600:
            max_steps = min(max_steps, 30)
    sensitivity = max(0.1, float(engine_params.get("interaction_sensitivity", 1.0)))
    pressure = 0.0
    fracture = 0.0
    if previous_group_state:
        groups = list((previous_group_state.get("groups") or {}).values()) if isinstance(previous_group_state, dict) else []
        if groups:
            pressure = max(float(group.get("avg_collective_pressure", group.get("pressure", 0.0)) or 0.0) for group in groups)
            fracture = max(float(group.get("fracture_risk", 0.0) or 0.0) for group in groups)
    local_density = avg_action_value(cells, "local_density", 0.0)
    policy = avg_action_value(cells, "policy_sensitivity", 0.5)
    scenario_need = min(1.0, (pressure * 0.32 + fracture * 0.28 + local_density * 0.16 + policy * 0.12) * sensitivity)
    if mode == "swarm":
        scenario_need = max(0.34, scenario_need)
    return max(min_steps, min(max_steps, min_steps + round((max_steps - min_steps) * scenario_need)))


def precision_active_agent_limit(cells: list, *, engine_params: dict) -> int | None:
    cell_count = len(cells)
    if cell_count <= 0:
        return None
    configured = engine_params.get("internal_active_agents_per_beat")
    if configured is not None:
        try:
            return max(1, min(cell_count, int(configured)))
        except (TypeError, ValueError):
            pass
    mode = str(engine_params.get("simulation_mode") or "precision").strip().lower()
    density = _stream_density(engine_params)
    configured_max = _positive_int(engine_params.get("stream_max_active_agents"))
    if configured_max is not None:
        return max(8, min(cell_count, configured_max))
    if mode == "swarm":
        target = min(640, int(cell_count ** 0.5 * 7.0 * density))
    else:
        target = min(520, int(cell_count ** 0.5 * 12.0 * density))
    full_scan_guard = cell_count - 1 if cell_count > 256 else cell_count
    return max(24, min(full_scan_guard, target))


def stream_round_active_agent_limit(
    cells: list,
    *,
    base_limit: int | None,
    round_index: int,
    round_count: int,
    engine_params: dict | None,
) -> int | None:
    """Grow the active cast during one intra-t stream episode.

    The stream should feel like one topic attracting more participants over
    time: the opening beat starts with a compact local cast, then nearby and
    pressure-relevant agents join until the final beat reaches the configured
    active-agent ceiling. This keeps the MiroFish-like "crowd gathers around a
    topic" feel without forcing full-world work on every microbeat.
    """
    if not cells:
        return None
    params = engine_params or {}
    enabled = _bool_param(params.get("stream_topic_expansion"), default=True)
    if not enabled:
        return base_limit
    total = len(cells)
    target = base_limit if base_limit is not None else total
    configured_max = _positive_int(params.get("stream_max_active_agents"))
    if configured_max is not None:
        target = max(target, configured_max)
    target = max(1, min(total, int(target)))
    if round_count <= 1:
        return target

    try:
        start_ratio = float(params.get("stream_initial_agent_ratio", 0.38))
    except (TypeError, ValueError):
        start_ratio = 0.38
    start_ratio = max(0.12, min(1.0, start_ratio))
    try:
        growth_rate = float(params.get("stream_growth_rate", 1.35))
    except (TypeError, ValueError):
        growth_rate = 1.35
    growth_rate = max(0.35, min(3.0, growth_rate))

    progress = max(0.0, min(1.0, (int(round_index) + 1) / max(1, int(round_count))))
    eased = progress ** (1.0 / growth_rate)
    start = max(4, int(round(target * start_ratio)))
    current = int(round(start + (target - start) * eased))
    return max(1, min(total, current))


def live_scene_cap(interactions: int) -> int:
    return max(320, min(780, int(max(1, interactions) * 30)))


def microbeat_scene_limit(
    cells: list,
    *,
    interactions: int,
    active_limit: int | None,
    engine_params: dict | None = None,
) -> int:
    """How many relationship strokes to expose per intra-t beat."""
    density = _stream_density(engine_params or {})
    base = max(24, min(82, int(max(1, active_limit or len(cells)) * 0.62 * density)))
    if len(cells) >= 1000:
        base = min(base, 42)
    elif len(cells) >= 400:
        base = min(base, 58)
    return max(18, min(base, max(18, live_scene_cap(interactions) // max(1, interactions))))


def consultation_neighbor_fanout(engine_params: dict | None = None) -> int:
    configured = (engine_params or {}).get("internal_max_neighbors")
    if configured is not None:
        try:
            return max(2, min(24, int(configured)))
        except (TypeError, ValueError):
            pass
    return 12


def scene_source_limit(cells: list, *, interactions: int) -> int:
    if len(cells) <= 256:
        return len(cells)
    return min(len(cells) - 1, max(64, min(420, live_scene_cap(interactions) * 4)))


def scene_source_cells(cells: list, *, scene_t: float, limit: int) -> list:
    """Return a compact local cast for the current live beat.

    Full-world snapshots can contain thousands of agents. Live scene generation
    only needs active consultation sources plus immediate targets; the deep
    t-boundary pass still sees the full world.
    """
    if not cells or limit <= 0 or len(cells) <= limit:
        return cells
    by_id = {str(getattr(cell, "cell_id", "")): cell for cell in cells}
    selected: dict[str, Any] = {}
    scored: list[tuple[float, str]] = []
    for cell in cells:
        action_state = dict(getattr(cell, "action_state", {}) or {})
        last_t = float(action_state.get("last_consultation_t", -999.0) or -999.0)
        recent = abs(last_t - float(scene_t)) <= 1e-4
        pressure = float(action_state.get("collective_pressure", 0.0) or 0.0)
        decision = float(action_state.get("decision_pressure_delta", 0.0) or 0.0)
        quality = float(action_state.get("last_consultation_quality", 0.0) or 0.0)
        score = (1.0 if recent else 0.0) + quality * 0.36 + pressure * 0.24 + decision * 0.22
        cell_id = str(getattr(cell, "cell_id", ""))
        if recent and cell_id:
            selected[cell_id] = cell
            for item in reversed(list(getattr(cell, "behavior_log", []) or [])[-3:]):
                payload = dict(item.get("payload") or {})
                for target_id in list(payload.get("neighbor_ids") or [])[:4]:
                    target = by_id.get(str(target_id))
                    if target is not None:
                        selected[str(target_id)] = target
        if cell_id:
            scored.append((score, cell_id))
    if len(selected) < min(8, limit):
        scored.sort(reverse=True)
        for _, cell_id in scored:
            if cell_id in by_id:
                selected[cell_id] = by_id[cell_id]
            if len(selected) >= limit:
                break
    return list(selected.values())[:limit]


def stamp_precision_internal_metrics(cell: Any, next_t: float, interactions: int):
    action_state = dict(cell.action_state)
    action_state["internal_interactions"] = int(interactions)
    action_state["last_internal_interaction_t"] = float(next_t)
    return cell.copy(t=next_t, action_state=action_state)


def avg_action_value(cells: list, key: str, fallback: float) -> float:
    if not cells:
        return 0.0
    values = []
    for cell in cells:
        try:
            values.append(float(dict(cell.action_state).get(key, fallback) or fallback))
        except (TypeError, ValueError):
            values.append(float(fallback))
    return sum(values) / max(1, len(values))


def _stream_density(engine_params: dict | None) -> float:
    raw = (engine_params or {}).get("social_stream_density", (engine_params or {}).get("stream_density", 1.0))
    try:
        return max(0.35, min(4.0, float(raw)))
    except (TypeError, ValueError):
        return 1.0


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _bool_param(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "off", "no", "disabled"}
