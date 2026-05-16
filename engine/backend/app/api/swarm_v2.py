"""Standalone Swarm V2 API."""
from __future__ import annotations

import asyncio
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, conint

from app.core.scenario_compiler import prepare_swarm_v2_scenario
from app.swarm_v2.runtime import iter_streaming_events, run_session
from app.swarm_v2.sessions import swarm_v2_sessions

router = APIRouter(prefix="/swarm-v2", tags=["swarm-v2"])


class SwarmV2RunRequest(BaseModel):
    prompt: str = Field(default="", max_length=16_000)
    agent_count: conint(ge=32, le=10_000) = 1200
    rounds: conint(ge=4, le=160) = 48
    events_per_round: conint(ge=4, le=80) = 18
    zone_count: conint(ge=2, le=128) = 24
    pace_ms: conint(ge=0, le=250) = 0
    llm_mode: str = Field(default="hybrid", pattern="^(off|packet|agent|hybrid|full-agent)$")
    llm_sample_size: conint(ge=1, le=512) = 96
    llm_parallelism: conint(ge=1, le=16) = 4


class SwarmV2RunResponse(BaseModel):
    runtime: str
    raw_prompt: Optional[str] = None
    prompt: str
    agent_count: int
    rounds: int
    events_per_round: int
    zone_count: int
    llm_mode: str = "packet"
    llm_parallelism: int = 1
    agents: list[dict[str, Any]]
    events: list[dict[str, Any]]
    summary: dict[str, Any]
    scenario: Optional[dict[str, Any]] = None


class SwarmV2SessionResponse(BaseModel):
    session_id: str
    runtime: str
    raw_prompt: Optional[str] = None
    prompt: str
    agent_count: int
    rounds: int
    events_per_round: int
    zone_count: int
    pace_ms: int
    llm_mode: str = "packet"
    llm_parallelism: int = 1
    persisted: bool = True
    agents: list[dict[str, Any]]
    summary: dict[str, Any]
    event_count: int
    scenario: Optional[dict[str, Any]] = None


class SwarmV2SessionListResponse(BaseModel):
    sessions: list[dict[str, Any]]


class SwarmV2ReplayResponse(SwarmV2SessionResponse):
    events: list[dict[str, Any]]


@router.post("/run", response_model=SwarmV2RunResponse)
def run_swarm_v2(req: SwarmV2RunRequest):
    scenario = prepare_swarm_v2_scenario(req.prompt)
    result = run_session(
        prompt=str(scenario.get("scenario_prompt") or req.prompt),
        agent_count=int(req.agent_count),
        rounds=int(req.rounds),
        events_per_round=int(req.events_per_round),
        zone_count=int(req.zone_count),
        llm_mode=req.llm_mode,
        llm_sample_size=int(req.llm_sample_size),
        llm_parallelism=int(req.llm_parallelism),
        scenario_roles=list(scenario.get("scenario_actor_roles") or []),
        scenario_zones=list(scenario.get("scenario_initial_zones") or []),
    )
    result["raw_prompt"] = scenario.get("raw_prompt") or req.prompt
    result["scenario"] = scenario
    result["summary"] = {
        **dict(result.get("summary") or {}),
        "scenario_director_mode": scenario.get("scenario_director_mode"),
        "scenario_director_fallback_reason": scenario.get("scenario_director_fallback_reason"),
        "scenario_actor_roles": scenario.get("scenario_actor_roles"),
        "scenario_initial_zones": scenario.get("scenario_initial_zones"),
    }
    return result


@router.post("/sessions", response_model=SwarmV2SessionResponse)
def create_swarm_v2_session(req: SwarmV2RunRequest):
    session = swarm_v2_sessions.create(
        prompt=req.prompt,
        agent_count=int(req.agent_count),
        rounds=int(req.rounds),
        events_per_round=int(req.events_per_round),
        zone_count=int(req.zone_count),
        pace_ms=int(req.pace_ms),
        llm_mode=req.llm_mode,
        llm_sample_size=int(req.llm_sample_size),
        llm_parallelism=int(req.llm_parallelism),
    )
    result = session.result
    return {
        "session_id": session.session_id,
        "runtime": result["runtime"],
        "raw_prompt": result.get("raw_prompt"),
        "prompt": result["prompt"],
        "agent_count": result["agent_count"],
        "rounds": result["rounds"],
        "events_per_round": result["events_per_round"],
        "zone_count": result["zone_count"],
        "pace_ms": session.pace_ms,
        "llm_mode": str(result.get("llm_mode") or req.llm_mode),
        "llm_parallelism": int(result.get("llm_parallelism") or req.llm_parallelism),
        "persisted": True,
        "agents": result["agents"],
        "summary": result["summary"],
        "event_count": int(result.get("summary", {}).get("expected_event_count") or len(result["events"])),
        "scenario": result.get("scenario"),
    }


@router.get("/sessions", response_model=SwarmV2SessionListResponse)
def list_swarm_v2_sessions(limit: int = 20):
    return {"sessions": swarm_v2_sessions.list(limit=limit)}


@router.get("/sessions/{session_id}", response_model=SwarmV2SessionResponse)
def get_swarm_v2_session(session_id: str):
    session = swarm_v2_sessions.get(session_id)
    if session is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Swarm V2 session not found")
    result = session.result
    return {
        "session_id": session.session_id,
        "runtime": result["runtime"],
        "raw_prompt": result.get("raw_prompt"),
        "prompt": result["prompt"],
        "agent_count": result["agent_count"],
        "rounds": result["rounds"],
        "events_per_round": result["events_per_round"],
        "zone_count": result["zone_count"],
        "pace_ms": session.pace_ms,
        "llm_mode": str(result.get("llm_mode") or "packet"),
        "llm_parallelism": int(result.get("llm_parallelism") or 1),
        "persisted": True,
        "agents": result["agents"],
        "summary": result["summary"],
        "event_count": int(result.get("summary", {}).get("expected_event_count") or len(result["events"])),
        "scenario": result.get("scenario"),
    }


@router.get("/sessions/{session_id}/replay", response_model=SwarmV2ReplayResponse)
def replay_swarm_v2_session(session_id: str):
    session = swarm_v2_sessions.get(session_id)
    if session is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Swarm V2 session not found")
    result = session.result
    return {
        "session_id": session.session_id,
        "runtime": result["runtime"],
        "raw_prompt": result.get("raw_prompt"),
        "prompt": result["prompt"],
        "agent_count": result["agent_count"],
        "rounds": result["rounds"],
        "events_per_round": result["events_per_round"],
        "zone_count": result["zone_count"],
        "pace_ms": session.pace_ms,
        "llm_mode": str(result.get("llm_mode") or "packet"),
        "llm_parallelism": int(result.get("llm_parallelism") or 1),
        "persisted": True,
        "agents": result["agents"],
        "events": result["events"],
        "summary": result["summary"],
        "event_count": len(result["events"]),
        "scenario": result.get("scenario"),
    }


@router.websocket("/sessions/{session_id}/ws")
async def stream_swarm_v2_session(websocket: WebSocket, session_id: str):
    session = swarm_v2_sessions.get(session_id)
    if session is None:
        await websocket.close(code=4000, reason="Swarm V2 session not found")
        return

    await websocket.accept()
    result = session.result
    existing_events = list(result.get("events") or [])
    expected_events = int(result.get("summary", {}).get("expected_event_count") or result.get("rounds", 0) * result.get("events_per_round", 0))
    try:
        await websocket.send_json(
            {
                "type": "session_started",
                "session_id": session.session_id,
                "runtime": result["runtime"],
                "raw_prompt": result.get("raw_prompt"),
                "prompt": result["prompt"],
                "agent_count": result["agent_count"],
                "rounds": result["rounds"],
                "events_per_round": result["events_per_round"],
                "zone_count": result["zone_count"],
                "pace_ms": session.pace_ms,
                "llm_mode": str(result.get("llm_mode") or "packet"),
                "llm_parallelism": int(result.get("llm_parallelism") or 1),
                "persisted": True,
                "agents": result["agents"],
                "summary": result["summary"],
                "event_count": expected_events or len(existing_events),
                "scenario": result.get("scenario"),
            }
        )
        previous_round = 0
        event_iter = existing_events if existing_events else iter_streaming_events(result)
        sent_events = 0
        for event in event_iter:
            if str(event.get("_stream_type") or "") == "agent_thinking":
                await websocket.send_json(
                    {
                        "type": "agent_thinking",
                        "session_id": session.session_id,
                        "round": int(event.get("round") or 0),
                        "event_index": int(event.get("event_index") or 0),
                        "source_id": str(event.get("source_id") or ""),
                        "target_id": str(event.get("target_id") or ""),
                        "source_label": str(event.get("source_label") or ""),
                        "target_label": str(event.get("target_label") or ""),
                        "topic": str(event.get("topic") or ""),
                        "phase": str(event.get("phase") or ""),
                        "llm_mode": str(event.get("llm_mode") or "full-agent"),
                    }
                )
                continue
            if str(event.get("_stream_type") or "") == "llm_log":
                await websocket.send_json(
                    {
                        "type": "llm_log",
                        "session_id": session.session_id,
                        "status": str(event.get("status") or "info"),
                        "task": str(event.get("task") or "swarm_agent"),
                        "event_id": str(event.get("event_id") or ""),
                        "event_ids": list(event.get("event_ids") or []),
                        "source_label": str(event.get("source_label") or ""),
                        "target_label": str(event.get("target_label") or ""),
                        "topic": str(event.get("topic") or ""),
                        "batch_size": int(event.get("batch_size") or 0),
                        "parallelism": int(event.get("parallelism") or 1),
                        "elapsed_ms": float(event.get("elapsed_ms") or 0),
                        "llm_enriched": bool(event.get("llm_enriched")),
                        "fallback_reason": str(event.get("fallback_reason") or ""),
                    }
                )
                continue
            if event["round"] != previous_round:
                previous_round = int(event["round"])
                await websocket.send_json(
                    {
                        "type": "round_started",
                        "session_id": session.session_id,
                        "round": previous_round,
                        "progress": round(previous_round / max(1, int(result["rounds"])), 4),
                    }
                )
            sent_events += 1
            await websocket.send_json(
                {
                    "type": "event",
                    "session_id": session.session_id,
                    "cursor": sent_events,
                    "event": event,
                }
            )
            swarm_v2_sessions.set_cursor(session.session_id, sent_events)
            if session.pace_ms:
                await asyncio.sleep(session.pace_ms / 1000)
        swarm_v2_sessions.persist(session)
        await websocket.send_json(
            {
                "type": "session_completed",
                "session_id": session.session_id,
                "agents": result["agents"],
                "summary": result["summary"],
                "events_sent": len(result.get("events") or existing_events),
            }
        )
    except WebSocketDisconnect:
        return
