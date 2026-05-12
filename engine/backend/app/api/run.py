"""Organic4D Engine — REST 엔드포인트: run (Phase 3.2, 3.3).

POST /worlds/{id}/run — 시뮬레이션 실행
stream=true 시 백그라운드 실행 + WebSocket 스트리밍
IMPLEMENTATION §0: POST /worlds/{id}/run
"""
from __future__ import annotations

import asyncio
import queue
from concurrent.futures import ThreadPoolExecutor
from typing import Union

from fastapi import APIRouter, BackgroundTasks, HTTPException
import numpy as np

from app.core.store import world_store
from app.core.ws_manager import ws_manager
from app.graph.time_flow import create_time_flow_graph
from app.models.cell import Cell
from pydantic import BaseModel


router = APIRouter(prefix="/worlds", tags=["run"])
_executor = ThreadPoolExecutor(max_workers=4)

FOCUS_WEIGHTS = {
    "thought": 1.0,
    "mover": 0.8,
    "zone": 0.55,
    "field": 0.4,
}


def _serialize_live_cell(cell: Cell) -> dict:
    return {
        "cell_id": cell.cell_id,
        "x": float(cell.x),
        "y": float(cell.y),
        "z": float(cell.z),
        "t": float(cell.t),
        "energy": float(cell.energy),
        "gene_vec": [float(v) for v in cell.gene_vec.tolist()],
        "emotion_vec": [float(v) for v in cell.emotion_vec.tolist()],
        "thought_vec": [float(v) for v in cell.thought_vec.tolist()],
        "worldview_vec": [float(v) for v in cell.worldview_vec.tolist()],
        "role_key": cell.role_key,
        "role_label": cell.role_label,
        "persona_id": cell.persona_id,
        "persona_text": cell.persona_text,
        "persona_country": cell.persona_country,
        "persona_attrs": dict(cell.persona_attrs),
        "zone_id": cell.zone_id,
        "zone_label": cell.zone_label,
        "zone_influence": float(cell.zone_influence),
        "zone_friction": float(cell.zone_friction),
        "short_memory": [dict(item) for item in cell.short_memory[-6:]],
        "long_memory": [dict(item) for item in cell.long_memory[-4:]],
        "behavior_log": [dict(item) for item in cell.behavior_log[-10:]],
        "action_state": dict(cell.action_state),
    }


def _normalized_metric(value: float, maximum: float) -> float:
    if maximum <= 0:
        return 0.0
    return max(0.0, min(1.0, float(value) / float(maximum)))


def _observer_features(cells: list[Cell]) -> dict[str, dict[str, object]]:
    if not cells:
        return {}
    max_energy = max(float(cell.energy) for cell in cells) or 1.0
    max_shift = max(float(dict(cell.action_state).get("last_spatial_shift", 0.0) or 0.0) for cell in cells) or 1.0
    max_memory = max(len(cell.short_memory) + len(cell.behavior_log) for cell in cells) or 1
    max_thought_t = max(float(dict(cell.action_state).get("last_thought_t", 0.0) or 0.0) for cell in cells) or 1.0
    max_thought_norm = max(float(np.linalg.norm(cell.thought_vec)) for cell in cells) or 1.0
    zone_representatives: set[str] = set()
    zone_groups: dict[str, list[Cell]] = {}
    for cell in cells:
        zone_groups.setdefault(str(cell.zone_id or "zone-0"), []).append(cell)
    for zone_cells in zone_groups.values():
        representative = max(
            zone_cells,
            key=lambda cell: (
                float(cell.energy),
                len(cell.behavior_log),
                float(np.linalg.norm(cell.thought_vec)),
                str(cell.cell_id),
            ),
        )
        zone_representatives.add(representative.cell_id)

    features: dict[str, dict[str, object]] = {}
    for cell in cells:
        action_state = dict(cell.action_state)
        thought_present = bool(str(action_state.get("last_thought_summary", "")).strip())
        thought_recency = float(action_state.get("last_thought_t", -1.0) or -1.0)
        continuity_score = float(action_state.get("thought_continuity_score", 0.0) or 0.0)
        spatial_shift = float(action_state.get("last_spatial_shift", 0.0) or 0.0)
        mobility_bias = float(action_state.get("mobility_bias", 0.0) or 0.0)
        memory_density = len(cell.short_memory) + len(cell.behavior_log)

        focus_scores = {
            "thought": (
                (0.42 if thought_present else 0.0)
                + 0.28 * continuity_score
                + 0.18 * _normalized_metric(thought_recency, max_thought_t)
                + 0.12 * _normalized_metric(memory_density, max_memory)
            ),
            "mover": (
                0.62 * _normalized_metric(spatial_shift, max_shift)
                + 0.23 * mobility_bias
                + 0.15 * _normalized_metric(float(cell.energy), max_energy)
            ),
            "zone": (
                (0.7 if cell.cell_id in zone_representatives else 0.0)
                + 0.3 * _normalized_metric(float(cell.energy), max_energy)
            ),
            "field": (
                0.45 * _normalized_metric(float(cell.energy), max_energy)
                + 0.25 * _normalized_metric(float(np.linalg.norm(cell.thought_vec)), max_thought_norm)
                + 0.15 * _normalized_metric(memory_density, max_memory)
                + 0.15 * _normalized_metric(spatial_shift, max_shift)
            ),
        }
        primary_focus = max(focus_scores.items(), key=lambda item: item[1])[0]
        weighted_score = sum(FOCUS_WEIGHTS[focus] * score for focus, score in focus_scores.items())
        features[cell.cell_id] = {
            "focus_scores": focus_scores,
            "primary_focus": primary_focus,
            "weighted_score": weighted_score,
            "zone_id": str(cell.zone_id or "zone-0"),
            "role_key": str(cell.role_key or "agent"),
        }
    return features


def _build_live_observer_cells(cells: list[Cell], limit: int = 72) -> tuple[list[dict], bool]:
    if not cells:
        return [], False
    features = _observer_features(cells)
    selected_ids: set[str] = set()
    selected: list[Cell] = []
    covered_focuses: set[str] = set()
    covered_zones: set[str] = set()
    covered_roles: set[str] = set()
    target_count = min(limit, len(cells))

    while len(selected) < target_count:
        best_cell: Cell | None = None
        best_score = -1.0
        for cell in cells:
            if cell.cell_id in selected_ids:
                continue
            feature = features[cell.cell_id]
            score = float(feature["weighted_score"])
            primary_focus = str(feature["primary_focus"])
            zone_id = str(feature["zone_id"])
            role_key = str(feature["role_key"])
            focus_scores = feature["focus_scores"]
            if primary_focus not in covered_focuses:
                score += 0.32
            if zone_id not in covered_zones:
                score += 0.26
            if role_key not in covered_roles:
                score += 0.12
            score += 0.04 * sum(
                float(value)
                for focus, value in focus_scores.items()
                if focus not in covered_focuses
            )
            if score > best_score:
                best_score = score
                best_cell = cell
        if best_cell is None:
            break
        feature = features[best_cell.cell_id]
        current_state = dict(best_cell.action_state)
        current_state["observer_focus"] = str(feature["primary_focus"])
        current_state["observer_score"] = round(float(feature["weighted_score"]), 3)
        current_state["observer_focus_scores"] = {
            key: round(float(value), 3)
            for key, value in dict(feature["focus_scores"]).items()
        }
        selected.append(best_cell.copy(action_state=current_state))
        selected_ids.add(best_cell.cell_id)
        covered_focuses.add(str(feature["primary_focus"]))
        covered_zones.add(str(feature["zone_id"]))
        covered_roles.add(str(feature["role_key"]))

    sampled = len(cells) > target_count
    return [_serialize_live_cell(cell) for cell in selected], sampled


class RunRequest(BaseModel):
    """POST /worlds/{id}/run 요청."""
    stream: bool = False


class RunResponse(BaseModel):
    """POST /worlds/{id}/run 응답."""
    world_id: str
    status: str
    final_t: float = 0.0
    cell_count: int = 0


class RunAcceptedResponse(BaseModel):
    """stream=true 시 202 응답."""
    world_id: str
    status: str = "running"
    message: str = "Simulation started, connect to WebSocket for streaming"


def _run_stream_producer(
    world_id: str,
    t_max: float,
    initial_cell_count: int,
    msg_queue: queue.Queue,
) -> None:
    """스레드에서 graph.stream() 실행, 메시지를 큐에 넣음."""
    from app.core.snapshot import SnapshotStore

    entry = world_store.get(world_id)
    if entry is None:
        msg_queue.put({"type": "error", "message": "World not found"})
        return
    store = world_store.get_snapshot_store(world_id)
    if store is None:
        msg_queue.put({"type": "error", "message": "Store not found"})
        return

    graph = create_time_flow_graph()
    try:
        nps = world_store.get_nutrient_per_step(world_id)
        for chunk in graph.stream(
            {
                "t_max": t_max,
                "initial_cell_count": initial_cell_count,
                "role_catalog": world_store.get_role_catalog(world_id),
                "persona_catalog": world_store.get_persona_catalog(world_id),
                "engine_params": world_store.get_engine_params(world_id),
                "coalition_state": dict(entry.get("coalition_state") or {}),
                "coalition_history": list(entry.get("coalition_history") or []),
                "group_state": dict(entry.get("group_state") or {}),
                "world_events": list(entry["world"].nutrients),
                "snapshot_store": store,
                "nutrient_per_step": nps,
            },
            config={"recursion_limit": int(t_max) + 50},
        ):
            if "step_loop" in chunk:
                s = chunk["step_loop"]
                world_store.update_coalition_state(
                    world_id,
                    coalition_state=s.get("coalition_state"),
                    coalition_history=s.get("coalition_history"),
                )
                world_store.update_group_state(
                    world_id,
                    group_state=s.get("group_state"),
                )
                observer_cells, observer_sampled = _build_live_observer_cells(s["cells"])
                msg_queue.put({
                    "type": "step",
                    "t": s["current_t"],
                    "cell_count": len(s["cells"]),
                    "observer_cells": observer_cells,
                    "observer_total_cells": len(s["cells"]),
                    "observer_sampled": observer_sampled,
                    "group_state_summary": dict((s.get("group_state") or {}).get("summary") or {}),
                })
            elif "init" in chunk:
                s = chunk["init"]
                world_store.update_group_state(
                    world_id,
                    group_state=s.get("group_state"),
                )
                observer_cells, observer_sampled = _build_live_observer_cells(s["cells"])
                msg_queue.put({
                    "type": "step",
                    "t": 0.0,
                    "cell_count": len(s["cells"]),
                    "observer_cells": observer_cells,
                    "observer_total_cells": len(s["cells"]),
                    "observer_sampled": observer_sampled,
                    "group_state_summary": dict((s.get("group_state") or {}).get("summary") or {}),
                })
        msg_queue.put({"type": "done"})
    except Exception as e:
        msg_queue.put({"type": "error", "message": str(e)})


async def _stream_consumer(world_id: str, msg_queue: queue.Queue) -> None:
    """큐에서 메시지 읽어 WebSocket으로 전송."""
    loop = asyncio.get_event_loop()
    try:
        while True:
            msg = await loop.run_in_executor(None, msg_queue.get)
            if msg.get("type") == "done":
                world_store.set_status(world_id, "done")
                await ws_manager.send_to_world(world_id, msg)
                break
            if msg.get("type") == "error":
                world_store.set_status(world_id, "idle")
                await ws_manager.send_to_world(world_id, msg)
                break
            await ws_manager.send_to_world(world_id, msg)
    except Exception:
        world_store.set_status(world_id, "idle")


@router.post("/{world_id}/run", response_model=Union[RunResponse, RunAcceptedResponse])
def run_simulation(
    world_id: str,
    background_tasks: BackgroundTasks,
    req: RunRequest = RunRequest(),
):
    """월드 시뮬레이션 실행. stream=true 시 백그라운드 + WS 스트리밍."""
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    if entry["status"] == "running":
        raise HTTPException(status_code=409, detail="Simulation already running")

    world = entry["world"]
    store = entry["snapshot_store"]
    initial_cell_count = world_store.get_initial_cell_count(world_id)

    if req.stream:
        world_store.set_status(world_id, "running")
        msg_queue = queue.Queue()
        _executor.submit(
            _run_stream_producer,
            world_id,
            world.t_max,
            initial_cell_count,
            msg_queue,
        )
        background_tasks.add_task(_stream_consumer, world_id, msg_queue)
        return RunAcceptedResponse(world_id=world_id)

    world_store.set_status(world_id, "running")
    try:
        graph = create_time_flow_graph()
        nps = world_store.get_nutrient_per_step(world_id)
        result = graph.invoke(
            {
                "t_max": world.t_max,
                "initial_cell_count": initial_cell_count,
                "role_catalog": world_store.get_role_catalog(world_id),
                "persona_catalog": world_store.get_persona_catalog(world_id),
                "engine_params": world_store.get_engine_params(world_id),
                "coalition_state": dict(entry.get("coalition_state") or {}),
                "coalition_history": list(entry.get("coalition_history") or []),
                "group_state": dict(entry.get("group_state") or {}),
                "world_events": list(world.nutrients),
                "snapshot_store": store,
                "nutrient_per_step": nps,
            },
            config={"recursion_limit": int(world.t_max) + 50},
        )
        final_t = result["current_t"]
        cell_count = len(result["cells"])
        world_store.update_coalition_state(
            world_id,
            coalition_state=result.get("coalition_state"),
            coalition_history=result.get("coalition_history"),
        )
        world_store.update_group_state(
            world_id,
            group_state=result.get("group_state"),
        )
    finally:
        world_store.set_status(world_id, "done")

    return RunResponse(
        world_id=world_id,
        status="done",
        final_t=final_t,
        cell_count=cell_count,
    )
