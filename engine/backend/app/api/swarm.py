"""Standalone Swarm Mode runtime endpoints."""
from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, conint

from app.swarm import SwarmConfig, project_swarm_scene, run_swarm_compact

router = APIRouter(prefix="/swarm", tags=["swarm"])


class SwarmRunRequest(BaseModel):
    agent_count: conint(ge=1, le=100_000) = Field(default=1000)
    meso_group_count: conint(ge=1, le=500) = Field(default=24)
    steps: conint(ge=0, le=500) = Field(default=32)
    llm_mode: Literal["packet", "agent"] = Field(default="packet")
    seed: int = Field(default=7)
    policy_intensity: float = Field(default=0.35, ge=0.0, le=1.0)
    shock_interval: conint(ge=0, le=10_000) = Field(default=8)
    packet_interval: conint(ge=1, le=10_000) = Field(default=8)
    agent_llm_sample_size: conint(ge=1, le=10_000) = Field(default=32)
    include_agent_sample: bool = Field(default=True)
    agent_sample_size: conint(ge=0, le=256) = Field(default=24)
    scene_agent_limit: conint(ge=0, le=10_000) = Field(default=1200)
    pressure_grid_size: conint(ge=4, le=96) = Field(default=32)
    include_full_agents: bool = Field(default=False)


class SwarmRunResponse(BaseModel):
    config: dict[str, Any]
    elapsed_sec: float
    steps_per_sec: float
    final: dict[str, Any]
    trajectory: list[dict[str, Any]]


@router.post("/run", response_model=SwarmRunResponse)
def run_swarm_endpoint(req: SwarmRunRequest) -> SwarmRunResponse:
    config = SwarmConfig(
        agent_count=int(req.agent_count),
        meso_group_count=int(req.meso_group_count),
        steps=int(req.steps),
        llm_mode=req.llm_mode,
        seed=int(req.seed),
        policy_intensity=float(req.policy_intensity),
        shock_interval=int(req.shock_interval),
        packet_interval=int(req.packet_interval),
        agent_llm_sample_size=int(req.agent_llm_sample_size),
    )
    started = time.perf_counter()
    state, trajectory = run_swarm_compact(config)
    elapsed = time.perf_counter() - started
    final = state
    macro = final.macro
    if macro is None:
        raise RuntimeError("Swarm runner returned no macro field")
    agent_sample = (
        [asdict(agent) for agent in final.agents[: int(req.agent_sample_size)]]
        if req.include_agent_sample and req.agent_sample_size
        else []
    )
    scene = project_swarm_scene(
        t=final.t,
        agents=final.agents,
        groups=final.meso_groups,
        macro=macro,
        agent_limit=int(req.scene_agent_limit),
        pressure_grid_size=int(req.pressure_grid_size),
    )
    metrics = {
        "simulation_mode": "swarm",
        "agent_count": len(final.agents),
        "meso_group_count": len(final.meso_groups),
        "llm_mode": config.llm_mode,
        "llm_packet_count": len(final.llm_packets),
        "llm_prompt_count": sum(int(packet.get("prompt_count") or 0) for packet in final.llm_packets),
        "avg_pressure": macro.avg_pressure,
        "max_pressure": macro.max_pressure,
        "shock_strength": macro.shock_strength,
        "rumor_pressure": macro.rumor_pressure,
        "policy_wave": macro.policy_wave,
        "scene_agent_count": len(scene["agents"]),
        "pressure_grid_cells": len(scene["pressure_grid"]["cells"]),
        "full_agents_included": bool(req.include_full_agents),
    }
    return SwarmRunResponse(
        config=asdict(config),
        elapsed_sec=round(elapsed, 4),
        steps_per_sec=round((config.steps / elapsed) if elapsed else 0.0, 4),
        final={
            "t": final.t,
            "metrics": metrics,
            "macro": asdict(macro),
            "top_groups": [asdict(group) for group in final.meso_groups[:12]],
            "agent_sample": agent_sample,
            "full_agents": [asdict(agent) for agent in final.agents] if req.include_full_agents else [],
            "scene": scene,
        },
        trajectory=trajectory,
    )
