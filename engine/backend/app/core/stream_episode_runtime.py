"""MiroFish-style stream episode runtime for one End4D t.

One `t` is treated as a complete game/episode: a fast social stream runs first,
agents consult in many lightweight rounds, and only after that stream completes
does the graph commit deeper cognition and advance to the next t.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from app.core.agent_interactions import apply_agent_interactions, apply_lightweight_consultations
from app.core.collective_dynamics import apply_collective_dynamics
from app.core.consultation_kernel import (
    consultation_neighbor_fanout,
    live_scene_cap,
    microbeat_scene_limit,
    precision_active_agent_limit,
    precision_internal_interaction_count,
    scene_source_cells,
    scene_source_limit,
    stream_round_active_agent_limit,
)
from app.core.emotion import update_emotions
from app.core.microbeat_events import build_microbeat_consultation_events
from app.core.scene_events import build_intra_t_scene_events
from app.core.spatial_dynamics import update_spatial_positions


@dataclass(frozen=True)
class StreamEpisodeResult:
    cells: list
    group_state: dict
    round_count: int
    live_scene_events: list[dict[str, Any]]


def run_stream_episode(
    cells: list,
    *,
    current_t: float,
    next_t: float,
    engine_params: dict | None,
    previous_group_state: dict | None,
    scene_event_sink: Optional[Callable[..., None]] = None,
) -> StreamEpisodeResult:
    """Run one complete MiroFish-style stream episode for a t interval."""
    params = dict(engine_params or {})
    rounds = precision_internal_interaction_count(
        cells,
        engine_params=params,
        previous_group_state=previous_group_state,
    )
    group_state = dict(previous_group_state or {})
    scene_events: list[dict[str, Any]] = []
    emitted_keys: set[tuple[str, str, str, str]] = set()
    emit_stream_phase(
        cells,
        current_t=current_t,
        next_t=next_t,
        progress=0.06,
        phase="agent_matching",
        round_count=rounds,
        scene_event_sink=scene_event_sink,
    )

    if rounds <= 1:
        cells = apply_agent_interactions(cells, next_t)
        cells = update_spatial_positions(cells, current_t=next_t, engine_params=params)
        cells = update_emotions(cells, next_t)
        cells, group_state = apply_collective_dynamics(
            cells,
            current_t=next_t,
            previous_group_state=group_state,
        )
        _collect_live_scene_events(
            cells,
            current_t=current_t,
            next_t=next_t,
            scene_t=next_t,
            rounds=1,
            group_state=group_state,
            scene_events=scene_events,
            emitted_keys=emitted_keys,
            scene_event_sink=scene_event_sink,
            engine_params=params,
        )
        return StreamEpisodeResult(cells=cells, group_state=group_state, round_count=1, live_scene_events=scene_events)

    active_limit = precision_active_agent_limit(cells, engine_params=params)
    final_active_limit = active_limit
    for idx in range(rounds):
        progress = (idx + 1) / rounds
        internal_t = float(current_t) + (float(next_t) - float(current_t)) * progress
        round_active_limit = stream_round_active_agent_limit(
            cells,
            base_limit=active_limit,
            round_index=idx,
            round_count=rounds,
            engine_params=params,
        )
        final_active_limit = round_active_limit
        cells = apply_lightweight_consultations(
            cells,
            internal_t,
            radius=float(params.get("internal_interaction_radius", params.get("interaction_radius", 4.0))),
            max_neighbors=consultation_neighbor_fanout(params),
            active_cell_limit=round_active_limit,
            beat_index=idx,
        )
        cells = update_spatial_positions(cells, current_t=internal_t, engine_params=params)
        if idx == rounds - 1 or idx % 2 == 1:
            cells = update_emotions(cells, internal_t)
            cells, group_state = apply_collective_dynamics(
                cells,
                current_t=internal_t,
                previous_group_state=group_state,
            )
        _collect_live_scene_events(
            cells,
            current_t=current_t,
            next_t=next_t,
            scene_t=internal_t,
            beat_index=idx,
            active_limit=round_active_limit,
            rounds=rounds,
            group_state=group_state,
            scene_events=scene_events,
            emitted_keys=emitted_keys,
            scene_event_sink=scene_event_sink,
            engine_params=params,
        )

    memory_t = float(current_t) + (float(next_t) - float(current_t)) * 0.98
    cells = apply_agent_interactions(
        cells,
        memory_t,
        interval=1,
        radius=float(params.get("internal_interaction_radius", params.get("interaction_radius", 4.0))),
        max_neighbors=consultation_neighbor_fanout(params),
        active_cell_limit=final_active_limit,
        force=True,
    )
    cells = update_emotions(cells, next_t)
    return StreamEpisodeResult(cells=cells, group_state=group_state, round_count=rounds, live_scene_events=scene_events)


def emit_stream_phase(
    cells: list,
    *,
    current_t: float,
    next_t: float,
    progress: float,
    phase: str,
    round_count: int | None = None,
    scene_event_sink: Optional[Callable[..., None]],
) -> None:
    if scene_event_sink is None:
        return
    scene_t = float(current_t) + (float(next_t) - float(current_t)) * max(0.04, min(0.96, float(progress)))
    source, target = _top_live_pair(cells)
    pressure = float(dict(source.action_state).get("collective_pressure", 0.0) or 0.0) if source is not None else 0.0
    interaction_type = "hostile" if pressure >= 0.58 else "negative" if pressure >= 0.36 else "dialogue"
    phase_label = _stream_phase_label(phase)
    source_label = _live_agent_label(source) if source is not None else "field"
    target_label = _live_agent_label(target) if target is not None else "주변 집단"
    round_total = int(max(1, round_count or 24))
    round_index = max(1, min(round_total, int(round(_scene_progress(current_t=current_t, next_t=next_t, scene_t=scene_t) * round_total))))
    event = {
        "scene_id": f"phase-{phase}-{_safe_t(next_t)}",
        "t": float(next_t),
        "start_t": float(current_t),
        "scene_t": scene_t,
        "scene_progress": _scene_progress(current_t=current_t, next_t=next_t, scene_t=scene_t),
        "scene_type": "stream_phase",
        "stream_episode_id": f"t{_safe_t(next_t)}-mirofish-stream",
        "stream_session_id": f"t{_safe_t(next_t)}-mirofish-stream",
        "stream_round_index": round_index,
        "stream_round_count": round_total,
        "stream_event_index": 1,
        "t_composition_role": "mirofish_style_stream_episode",
        "interaction_type": interaction_type,
        "source_id": getattr(source, "cell_id", ""),
        "source_label": source_label,
        "target_ids": [getattr(target, "cell_id", "")] if target is not None else [],
        "target_label": target_label,
        "group_ids": _live_groups_for(source, target) if source is not None else [],
        "summary": f"{phase_label}: {source_label}와 {target_label} 주변의 계산이 진행 중입니다.",
        "narrative_reason": "MiroFish식 스트림이 끝난 뒤 t 경계 심층 커밋으로 넘어갑니다.",
        "scenario_relevance": "실행 중에도 에이전트 상호작용과 결정 압력이 계속 흐르고 있음을 표시합니다.",
        "sentiment": interaction_type,
        "pressure_delta": round(pressure * 0.02, 4),
        "relationship_delta": 0.0,
        "visual_hint": {"kind": "phase", "color_role": interaction_type, "pulse": True},
        "scene_index": 0,
        "scene_count": 0,
        "live_computed": True,
        "stream_phase": phase,
    }
    try:
        scene_event_sink(event, cells)
    except TypeError:
        scene_event_sink(event)


def merge_stream_episode_events(
    live_events: list[dict[str, Any]],
    final_events: list[dict[str, Any]],
    *,
    round_count: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for event in [*live_events, *final_events]:
        key = (
            str(event.get("source_id") or ""),
            ",".join(str(item) for item in event.get("target_ids") or []),
            str(event.get("interaction_type") or event.get("scene_type") or ""),
            str(round(float(event.get("scene_t") or event.get("t") or 0.0), 3)),
        )
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(event))
        if len(merged) >= live_scene_cap(round_count):
            break
    merged.sort(key=lambda item: float(item.get("scene_progress", 0.0) or 0.0))
    scene_count = len(merged)
    for idx, event in enumerate(merged, start=1):
        event["scene_index"] = idx
        event["scene_count"] = scene_count
        event["internal_interactions"] = int(max(1, round_count))
        _stamp_stream_episode_fields(event, next_t=float(event.get("t") or 0.0), rounds=round_count, fallback_index=idx)
    return merged


def _collect_live_scene_events(
    cells: list,
    *,
    current_t: float,
    next_t: float,
    scene_t: float,
    rounds: int,
    group_state: dict,
    scene_events: list[dict[str, Any]],
    emitted_keys: set[tuple[str, str, str, str]],
    scene_event_sink: Optional[Callable[..., None]],
    engine_params: dict | None = None,
    beat_index: int = 0,
    active_limit: int | None = None,
) -> None:
    params = dict(engine_params or {})
    source_cells = scene_source_cells(
        cells,
        scene_t=scene_t,
        limit=scene_source_limit(cells, interactions=rounds),
    )
    microbeats = build_microbeat_consultation_events(
        source_cells,
        current_t=current_t,
        next_t=next_t,
        scene_t=scene_t,
        beat_index=beat_index,
        beat_count=rounds,
        limit=microbeat_scene_limit(cells, interactions=rounds, active_limit=active_limit, engine_params=params),
    )
    if microbeats:
        _emit_scene_batch(
            microbeats,
            cells=source_cells,
            current_t=current_t,
            next_t=next_t,
            scene_t=scene_t,
            rounds=rounds,
            scene_events=scene_events,
            emitted_keys=emitted_keys,
            scene_event_sink=scene_event_sink,
        )
        if len(scene_events) >= live_scene_cap(rounds):
            return
    batch = build_intra_t_scene_events(
        source_cells,
        current_t=current_t,
        next_t=next_t,
        internal_interactions=rounds,
        group_state=group_state,
        limit=max(6, min(10, rounds * 3)),
    )
    emitted_count = _emit_scene_batch(
        batch,
        cells=source_cells,
        current_t=current_t,
        next_t=next_t,
        scene_t=scene_t,
        rounds=rounds,
        scene_events=scene_events,
        emitted_keys=emitted_keys,
        scene_event_sink=scene_event_sink,
    )
    if len(scene_events) >= live_scene_cap(rounds):
        return
    if emitted_count == 0 and len(scene_events) < live_scene_cap(rounds):
        event = _fallback_live_frame_event(
            source_cells,
            current_t=current_t,
            next_t=next_t,
            scene_t=scene_t,
            rounds=rounds,
            scene_index=len(scene_events) + 1,
        )
        scene_events.append(event)
        if scene_event_sink is not None:
            try:
                scene_event_sink(dict(event), source_cells)
            except TypeError:
                scene_event_sink(dict(event))


def _emit_scene_batch(
    batch: list[dict[str, Any]],
    *,
    cells: list,
    current_t: float,
    next_t: float,
    scene_t: float,
    rounds: int,
    scene_events: list[dict[str, Any]],
    emitted_keys: set[tuple[str, str, str, str]],
    scene_event_sink: Optional[Callable[..., None]],
) -> int:
    emitted_count = 0
    for event in batch:
        key = (
            str(event.get("source_id") or ""),
            ",".join(str(item) for item in event.get("target_ids") or []),
            str(event.get("interaction_type") or event.get("scene_type") or ""),
            str(round(float(scene_t), 3)),
        )
        if key in emitted_keys:
            continue
        emitted_keys.add(key)
        event = dict(event)
        event["scene_t"] = float(scene_t)
        event["scene_progress"] = _scene_progress(current_t=current_t, next_t=next_t, scene_t=scene_t)
        _stamp_stream_episode_fields(event, next_t=next_t, rounds=rounds, fallback_index=len(scene_events) + 1)
        event["scene_index"] = len(scene_events) + 1
        event["scene_count"] = live_scene_cap(rounds)
        event["live_computed"] = True
        event["stream_phase"] = str(event.get("stream_phase") or "internal_interaction")
        event["scene_id"] = f"live-scene-{_safe_t(next_t)}-{event['scene_index']}"
        scene_events.append(event)
        emitted_count += 1
        if scene_event_sink is not None:
            try:
                scene_event_sink(dict(event), cells)
            except TypeError:
                scene_event_sink(dict(event))
        if len(scene_events) >= live_scene_cap(rounds):
            return emitted_count
    return emitted_count


def _fallback_live_frame_event(
    cells: list,
    *,
    current_t: float,
    next_t: float,
    scene_t: float,
    rounds: int,
    scene_index: int,
) -> dict[str, Any]:
    source, target = _top_live_pair(cells)
    pressure = float(dict(source.action_state).get("collective_pressure", 0.0) or 0.0) if source is not None else 0.0
    interaction_type = "hostile" if pressure >= 0.58 else "negative" if pressure >= 0.36 else "dialogue"
    source_label = _live_agent_label(source) if source is not None else "field"
    target_label = _live_agent_label(target) if target is not None else "주변 집단"
    round_index = max(1, min(int(max(1, rounds)), int(round(_scene_progress(current_t=current_t, next_t=next_t, scene_t=scene_t) * max(1, rounds)))))
    return {
        "scene_id": f"live-frame-{_safe_t(next_t)}-{scene_index}",
        "t": float(next_t),
        "start_t": float(current_t),
        "scene_t": float(scene_t),
        "scene_progress": _scene_progress(current_t=current_t, next_t=next_t, scene_t=scene_t),
        "scene_type": "stream_frame",
        "stream_episode_id": f"t{_safe_t(next_t)}-mirofish-stream",
        "stream_session_id": f"t{_safe_t(next_t)}-mirofish-stream",
        "stream_round_index": round_index,
        "stream_round_count": int(max(1, rounds)),
        "stream_event_index": 1,
        "session_index": round_index,
        "session_count": int(max(1, rounds)),
        "session_event_index": 1,
        "t_composition_role": "mirofish_style_stream_episode",
        "interaction_type": interaction_type,
        "source_id": getattr(source, "cell_id", ""),
        "source_label": source_label,
        "target_ids": [getattr(target, "cell_id", "")] if target is not None else [],
        "target_label": target_label,
        "group_ids": _live_groups_for(source, target) if source is not None else [],
        "summary": f"{source_label} 주변의 압력장이 갱신되고, {target_label} 쪽 상호작용 가능성이 재계산됩니다.",
        "narrative_reason": "이 장면은 긴 계산 완료를 기다리지 않고 내부 협의/위치/압력 변화를 먼저 보여주는 live frame입니다.",
        "scenario_relevance": "t 내부에서 사회적 접촉이 계속 진행 중임을 표시합니다.",
        "sentiment": interaction_type,
        "pressure_delta": round(pressure * 0.035, 4),
        "relationship_delta": 0.0,
        "visual_hint": {"kind": "live_frame", "color_role": interaction_type, "pulse": True},
        "scene_index": int(scene_index),
        "scene_count": live_scene_cap(rounds),
        "internal_interactions": int(max(1, rounds)),
        "live_computed": True,
        "stream_phase": "live_frame",
    }


def _stamp_stream_episode_fields(event: dict[str, Any], *, next_t: float, rounds: int, fallback_index: int) -> None:
    if "session_index" not in event:
        event["session_index"] = max(1, min(int(max(1, rounds)), int(round(float(event.get("scene_progress", 0.0) or 0.0) * max(1, rounds)))))
    event["session_count"] = int(max(1, rounds))
    event["stream_round_index"] = int(event.get("stream_round_index") or event.get("session_index") or 1)
    event["stream_round_count"] = int(event.get("stream_round_count") or rounds)
    event["stream_event_index"] = int(event.get("stream_event_index") or event.get("session_event_index") or fallback_index)
    event["stream_episode_id"] = str(event.get("stream_episode_id") or f"t{_safe_t(next_t)}-mirofish-stream")
    event["stream_session_id"] = str(event.get("stream_session_id") or event["stream_episode_id"])
    event["t_composition_role"] = str(event.get("t_composition_role") or "mirofish_style_stream_episode")


def _top_live_pair(cells: list) -> tuple[Any | None, Any | None]:
    source = None
    target = None
    source_score = float("-inf")
    target_score = float("-inf")
    for cell in cells:
        action_state = dict(cell.action_state)
        score = (
            float(action_state.get("collective_pressure", 0.0) or 0.0)
            + float(action_state.get("decision_pressure_delta", 0.0) or 0.0)
            + float(cell.energy) * 0.002
        )
        if score > source_score:
            target = source
            target_score = source_score
            source = cell
            source_score = score
        elif score > target_score:
            target = cell
            target_score = score
    return source, target


def _stream_phase_label(phase: str) -> str:
    labels = {
        "stream_bootstrap": "스트림 시행 시작",
        "agent_matching": "에이전트 매칭",
        "deep_commit": "t 경계 심층 계산",
        "live_frame": "라이브 프레임",
    }
    return labels.get(phase, phase.replace("_", " "))


def _live_agent_label(cell: Any) -> str:
    attrs = dict(getattr(cell, "persona_attrs", {}) or {})
    name = str(attrs.get("display_name") or attrs.get("agent_name") or attrs.get("name") or "").strip()
    role = str(getattr(cell, "role_label", "") or getattr(cell, "role_key", "") or "agent").strip()
    if name:
        return name if role in name else f"{name}({role})"
    return role


def _live_groups_for(source: Any, target: Any | None) -> list[str]:
    groups: list[str] = []
    for cell in (source, target):
        if cell is None:
            continue
        role = str(getattr(cell, "role_key", "") or "").strip()
        zone = str(getattr(cell, "zone_id", "") or "").strip()
        if role:
            groups.append(f"role:{role}")
        if zone:
            groups.append(f"zone:{zone}")
    return list(dict.fromkeys(groups))


def _scene_progress(*, current_t: float, next_t: float, scene_t: float) -> float:
    span = max(1e-6, float(next_t) - float(current_t))
    return max(0.04, min(0.96, round((float(scene_t) - float(current_t)) / span, 4)))


def _safe_t(value: float) -> str:
    return f"{float(value):.2f}".replace(".", "-")
