"""Clean-room MiroFish-style swarm runtime for End4D.

This module intentionally does not copy MiroFish code. It borrows the product
shape: prepare a large agent pool, run one fast independent swarm session, emit
many relationship events immediately, then commit one End4D t snapshot.
"""
from __future__ import annotations

import math
import random
import time
from typing import Any, Callable

from app.core.action_ledger import attach_action_record
from app.core.collective_dynamics import compute_group_state
from app.core.scene_events import compute_scene_quality_metrics


MIRO_SWARM_REVISION = "miro-swarm-v1-cleanroom-session"


def run_miro_swarm_step(state: dict) -> dict:
    cells = list(state.get("cells") or [])
    current_t = float(state.get("current_t") or 0.0)
    next_t = current_t + 1.0
    params = dict(state.get("engine_params") or {})
    sink = state.get("scene_event_sink") if callable(state.get("scene_event_sink")) else None
    started = time.perf_counter()

    if not cells:
        return _out(state, cells, current_t=next_t, group_state=dict(state.get("group_state") or {}), scene_events=[], started=started)

    rounds = _int_param(params, "swarm_stream_rounds", _int_param(params, "max_interactions_per_step", 36))
    rounds = max(12, min(96, rounds))
    events_per_round = _int_param(params, "swarm_events_per_round", max(8, min(28, int(math.sqrt(len(cells)) * 1.15))))
    events_per_round = max(4, min(48, events_per_round))
    max_events = _int_param(params, "swarm_max_session_events", rounds * events_per_round)
    max_events = max(events_per_round, min(4096, max_events))
    active_target = _int_param(params, "stream_max_active_agents", min(len(cells), max(120, int(math.sqrt(len(cells)) * 26))))
    active_target = max(12, min(len(cells), active_target))
    start_ratio = _float_param(params, "stream_initial_agent_ratio", 0.18)
    growth_rate = _float_param(params, "stream_growth_rate", 1.55)
    fanout = max(2, min(24, _int_param(params, "internal_max_neighbors", 12)))

    rng = random.Random(_seed_for(cells, current_t, params))
    ordered = _rank_agents(cells)
    scene_events: list[dict[str, Any]] = []
    pressure_delta: dict[str, float] = {}
    relation_delta: dict[str, float] = {}
    participation: dict[str, int] = {}

    _emit_phase(
        sink,
        cells,
        current_t=current_t,
        next_t=next_t,
        phase="swarm_session_start",
        round_index=0,
        round_count=rounds,
        event_index=0,
        summary="Swarm session starts: agents begin rapid topic matching before the next t is committed.",
    )

    event_index = 0
    for round_index in range(rounds):
        if event_index >= max_events:
            break
        progress = (round_index + 1) / max(1, rounds)
        active_count = _active_count(active_target, progress=progress, start_ratio=start_ratio, growth_rate=growth_rate)
        active = ordered[:active_count]
        if not active:
            continue
        round_budget = min(events_per_round, max_events - event_index)
        for local_index in range(round_budget):
            source = active[(round_index * events_per_round + local_index * 3) % len(active)]
            target = _pick_target(source, active, cells, fanout=fanout, rng=rng, round_index=round_index, local_index=local_index)
            if target is None or target.cell_id == source.cell_id:
                continue
            event_index += 1
            scene_t = current_t + (next_t - current_t) * min(0.985, max(0.015, (round_index + (local_index + 1) / max(1, round_budget)) / max(1, rounds)))
            event_type = _interaction_type(source, target, round_index=round_index)
            intensity = _interaction_intensity(source, target, event_type=event_type)
            p_delta = _pressure_delta(event_type, intensity)
            r_delta = _relationship_delta(event_type, intensity)
            for cell_id in (source.cell_id, target.cell_id):
                pressure_delta[cell_id] = pressure_delta.get(cell_id, 0.0) + p_delta
                relation_delta[cell_id] = relation_delta.get(cell_id, 0.0) + r_delta
                participation[cell_id] = participation.get(cell_id, 0) + 1
            event = _event(
                source,
                target,
                current_t=current_t,
                next_t=next_t,
                scene_t=scene_t,
                round_index=round_index + 1,
                round_count=rounds,
                event_index=event_index,
                interaction_type=event_type,
                intensity=intensity,
                pressure_delta=p_delta,
                relationship_delta=r_delta,
            )
            scene_events.append(event)
            _emit(sink, event, cells)

    next_cells = _commit_cells(
        cells,
        next_t=next_t,
        pressure_delta=pressure_delta,
        relation_delta=relation_delta,
        participation=participation,
    )
    group_state = compute_group_state(next_cells, current_t=next_t, previous_group_state=state.get("group_state"))
    scene_count = len(scene_events)
    for idx, event in enumerate(scene_events, start=1):
        event["scene_index"] = idx
        event["scene_count"] = scene_count
    scene_events = [attach_action_record(event) for event in scene_events]
    scene_metrics = compute_scene_quality_metrics(scene_events, next_cells, current_t=current_t, next_t=next_t)

    store = state.get("snapshot_store")
    if store is not None:
        store.save(next_t, next_cells, scene_events=scene_events, scene_metrics=scene_metrics)

    return _out(
        state,
        next_cells,
        current_t=next_t,
        group_state=group_state,
        scene_events=scene_events,
        scene_metrics=scene_metrics,
        started=started,
    )


def _out(
    state: dict,
    cells: list,
    *,
    current_t: float,
    group_state: dict,
    scene_events: list[dict[str, Any]],
    started: float,
    scene_metrics: dict | None = None,
) -> dict:
    out = {
        "cells": cells,
        "current_t": current_t,
        "coalition_state": dict(state.get("coalition_state") or {}),
        "coalition_history": [dict(item) for item in state.get("coalition_history") or []],
        "group_state": dict(group_state),
        "scene_events": [dict(item) for item in scene_events],
        "scene_metrics": dict(scene_metrics or {}),
        "scene_events_live_emitted": True,
        "runtime_timing": {
            "total_ms": round((time.perf_counter() - started) * 1000.0, 3),
            "dominant_phase": "miro_swarm_session",
            "phases": {"miro_swarm_session": {"count": 1}},
        },
    }
    for key in ("t_max", "snapshot_store", "world_events", "engine_params"):
        if key in state:
            out[key] = state[key] if key != "world_events" else list(state[key])
    return out


def _rank_agents(cells: list) -> list:
    return sorted(
        cells,
        key=lambda cell: (
            -float(dict(cell.action_state).get("collective_pressure", 0.0) or 0.0),
            -float(dict(cell.action_state).get("policy_sensitivity", 0.0) or 0.0),
            str(cell.role_key),
            str(cell.cell_id),
        ),
    )


def _active_count(target: int, *, progress: float, start_ratio: float, growth_rate: float) -> int:
    start_ratio = max(0.08, min(0.8, start_ratio))
    growth_rate = max(0.5, min(3.0, growth_rate))
    eased = max(0.0, min(1.0, progress)) ** (1.0 / growth_rate)
    start = max(8, int(target * start_ratio))
    return max(1, min(target, int(start + (target - start) * eased)))


def _pick_target(source: Any, active: list, cells: list, *, fanout: int, rng: random.Random, round_index: int, local_index: int) -> Any | None:
    if not active:
        return None
    source_zone = str(getattr(source, "zone_id", ""))
    source_role = str(getattr(source, "role_key", ""))
    window = active[: min(len(active), max(fanout * 4, 16))]
    candidates = [
        cell for cell in window
        if cell.cell_id != source.cell_id and (str(getattr(cell, "zone_id", "")) == source_zone or str(getattr(cell, "role_key", "")) != source_role)
    ]
    if not candidates:
        candidates = [cell for cell in active if cell.cell_id != source.cell_id]
    if not candidates and len(cells) > 1:
        candidates = [cell for cell in cells if cell.cell_id != source.cell_id]
    if not candidates:
        return None
    return candidates[(round_index * 7 + local_index * 11 + rng.randrange(len(candidates))) % len(candidates)]


def _interaction_type(source: Any, target: Any, *, round_index: int) -> str:
    s = dict(source.action_state)
    t = dict(target.action_state)
    pressure = (float(s.get("collective_pressure", 0.0) or 0.0) + float(t.get("collective_pressure", 0.0) or 0.0)) / 2.0
    policy_gap = abs(float(s.get("policy_sensitivity", 0.5) or 0.5) - float(t.get("policy_sensitivity", 0.5) or 0.5))
    same_role = str(source.role_key) == str(target.role_key)
    if pressure + policy_gap > 0.86:
        return "hostile"
    if policy_gap > 0.22 or pressure > 0.46:
        return "negative"
    if same_role or round_index % 5 == 0:
        return "positive"
    return "dialogue"


def _interaction_intensity(source: Any, target: Any, *, event_type: str) -> float:
    s = dict(source.action_state)
    t = dict(target.action_state)
    base = 0.24 + abs(float(s.get("policy_sensitivity", 0.5) or 0.5) - float(t.get("policy_sensitivity", 0.5) or 0.5))
    base += (float(s.get("collective_pressure", 0.0) or 0.0) + float(t.get("collective_pressure", 0.0) or 0.0)) * 0.22
    if event_type == "hostile":
        base += 0.24
    elif event_type == "negative":
        base += 0.12
    elif event_type == "positive":
        base += 0.06
    return round(max(0.16, min(1.0, base)), 4)


def _event(source: Any, target: Any, *, current_t: float, next_t: float, scene_t: float, round_index: int, round_count: int, event_index: int, interaction_type: str, intensity: float, pressure_delta: float, relationship_delta: float) -> dict[str, Any]:
    source_label = _agent_label(source)
    target_label = _agent_label(target)
    return {
        "scene_id": f"miro-swarm-{int(next_t)}-{round_index}-{event_index}",
        "stream_episode_id": f"t{next_t:.2f}-miro-swarm",
        "stream_session_id": f"t{next_t:.2f}-miro-swarm",
        "stream_round_index": round_index,
        "stream_round_count": round_count,
        "stream_event_index": event_index,
        "session_index": round_index,
        "session_count": round_count,
        "session_event_index": event_index,
        "t_composition_role": "mirofish_cleanroom_swarm_session",
        "t": float(next_t),
        "start_t": float(current_t),
        "scene_t": float(scene_t),
        "scene_progress": max(0.01, min(0.99, (scene_t - current_t) / max(1e-6, next_t - current_t))),
        "scene_type": "swarm_consultation",
        "interaction_type": interaction_type,
        "source_id": source.cell_id,
        "target_ids": [target.cell_id],
        "source_label": source_label,
        "target_label": target_label,
        "group_ids": [str(source.role_key), str(target.role_key), str(source.zone_id), str(target.zone_id)],
        "pressure_delta": pressure_delta,
        "relationship_delta": relationship_delta,
        "visual_hint": {"kind": "miro_swarm_arc", "pulse": True, "intensity": intensity, "color_role": interaction_type},
        "salience": intensity,
        "live_computed": True,
        "stream_phase": "miro_swarm_consultation",
        "summary": f"{source_label} → {target_label}: { _tone_text(interaction_type) }",
        "narrative_reason": "한 주제에 모인 에이전트들이 빠른 관계 접촉으로 입장과 압력을 교환합니다.",
        "scenario_relevance": "이 이벤트는 t 내부 swarm session의 일부이며, session 완료 후 다음 t 스냅샷으로 커밋됩니다.",
        "llm_agent_channel": f"agent:{source.cell_id}",
    }


def _commit_cells(cells: list, *, next_t: float, pressure_delta: dict[str, float], relation_delta: dict[str, float], participation: dict[str, int]) -> list:
    out = []
    for idx, cell in enumerate(cells):
        action = dict(cell.action_state)
        p = float(pressure_delta.get(cell.cell_id, 0.0))
        r = float(relation_delta.get(cell.cell_id, 0.0))
        count = int(participation.get(cell.cell_id, 0))
        previous = float(action.get("collective_pressure", 0.0) or 0.0)
        action["swarm_session_participation"] = count
        action["swarm_session_pressure_delta"] = round(p, 4)
        action["swarm_session_relationship_delta"] = round(r, 4)
        action["collective_pressure"] = max(0.0, min(1.0, previous + p * 0.08))
        action["last_consultation_t"] = float(next_t)
        drift = min(0.22, 0.012 * count)
        angle = (idx * 2.399963 + next_t * 0.41) % math.tau
        out.append(cell.copy(
            x=float(cell.x + math.cos(angle) * drift),
            y=float(cell.y + math.sin(angle) * drift),
            t=float(next_t),
            action_state=action,
        ))
    return out


def _emit_phase(sink: Callable[..., None] | None, cells: list, *, current_t: float, next_t: float, phase: str, round_index: int, round_count: int, event_index: int, summary: str) -> None:
    if sink is None:
        return
    source = cells[0] if cells else None
    target = cells[1] if len(cells) > 1 else None
    event = {
        "scene_id": f"miro-swarm-phase-{phase}-{next_t:.2f}",
        "t": float(next_t),
        "start_t": float(current_t),
        "scene_t": float(current_t + 0.01),
        "scene_progress": 0.01,
        "scene_type": "swarm_phase",
        "interaction_type": "dialogue",
        "source_id": getattr(source, "cell_id", ""),
        "target_ids": [getattr(target, "cell_id", "")] if target is not None else [],
        "summary": summary,
        "stream_phase": phase,
        "stream_round_index": round_index,
        "stream_round_count": round_count,
        "stream_event_index": event_index,
        "stream_episode_id": f"t{next_t:.2f}-miro-swarm",
        "live_computed": True,
        "visual_hint": {"kind": "miro_swarm_phase", "pulse": True, "intensity": 0.45},
    }
    _emit(sink, event, cells)


def _emit(sink: Callable[..., None] | None, event: dict[str, Any], cells: list) -> None:
    if sink is None:
        return
    try:
        sink(event, cells)
    except TypeError:
        sink(event)


def _pressure_delta(event_type: str, intensity: float) -> float:
    sign = -1.0 if event_type == "positive" else 1.0 if event_type in {"negative", "hostile"} else 0.18
    return round(sign * min(0.18, intensity * 0.045), 4)


def _relationship_delta(event_type: str, intensity: float) -> float:
    sign = 1.0 if event_type == "positive" else -1.0 if event_type in {"negative", "hostile"} else 0.08
    return round(sign * min(0.2, intensity * 0.07), 4)


def _agent_label(cell: Any) -> str:
    attrs = dict(getattr(cell, "persona_attrs", {}) or {})
    name = str(attrs.get("display_name") or attrs.get("agent_name") or attrs.get("name") or "").strip()
    role = str(getattr(cell, "role_label", "") or getattr(cell, "role_key", "") or "agent").strip()
    if name:
        return name if role in name else f"{name}({role})"
    return role


def _tone_text(interaction_type: str) -> str:
    if interaction_type == "positive":
        return "협력 신호를 교환합니다"
    if interaction_type == "negative":
        return "긴장과 이견을 교환합니다"
    if interaction_type == "hostile":
        return "강한 충돌 신호를 드러냅니다"
    return "상황을 확인하고 다음 접촉 대상을 찾습니다"


def _seed_for(cells: list, current_t: float, params: dict) -> int:
    prompt = str(params.get("scenario_prompt") or params.get("raw_prompt") or "")
    return hash((len(cells), round(current_t, 3), prompt[:80])) & 0xFFFFFFFF


def _int_param(params: dict, key: str, fallback: int) -> int:
    try:
        return int(params.get(key, fallback))
    except (TypeError, ValueError):
        return int(fallback)


def _float_param(params: dict, key: str, fallback: float) -> float:
    try:
        return float(params.get(key, fallback))
    except (TypeError, ValueError):
        return float(fallback)
