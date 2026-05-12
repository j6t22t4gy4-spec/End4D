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


def _build_live_observer_cells(cells: list[Cell], limit: int = 72) -> tuple[list[dict], bool]:
    if not cells:
        return [], False
    ranked = sorted(
        cells,
        key=lambda cell: (
            -int(bool(dict(cell.action_state).get("last_thought_summary"))),
            -float(dict(cell.action_state).get("last_thought_t", -1.0) or -1.0),
            -len(cell.short_memory),
            -len(cell.behavior_log),
            -float(np.linalg.norm(cell.thought_vec)),
            str(cell.cell_id),
        ),
    )
    sampled = len(ranked) > limit
    selected = ranked[:limit] if sampled else ranked
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
                observer_cells, observer_sampled = _build_live_observer_cells(s["cells"])
                msg_queue.put({
                    "type": "step",
                    "t": s["current_t"],
                    "cell_count": len(s["cells"]),
                    "observer_cells": observer_cells,
                    "observer_total_cells": len(s["cells"]),
                    "observer_sampled": observer_sampled,
                })
            elif "init" in chunk:
                s = chunk["init"]
                observer_cells, observer_sampled = _build_live_observer_cells(s["cells"])
                msg_queue.put({
                    "type": "step",
                    "t": 0.0,
                    "cell_count": len(s["cells"]),
                    "observer_cells": observer_cells,
                    "observer_total_cells": len(s["cells"]),
                    "observer_sampled": observer_sampled,
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
    finally:
        world_store.set_status(world_id, "done")

    return RunResponse(
        world_id=world_id,
        status="done",
        final_t=final_t,
        cell_count=cell_count,
    )
