"""Standalone Swarm Mode runtime endpoints."""
from __future__ import annotations

import time
from dataclasses import asdict
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, conint

from app.swarm import SwarmConfig, run_swarm

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
    snapshots = run_swarm(config)
    elapsed = time.perf_counter() - started
    final = snapshots[-1]
    agent_sample = (
        [asdict(agent) for agent in final.agents[: int(req.agent_sample_size)]]
        if req.include_agent_sample and req.agent_sample_size
        else []
    )
    return SwarmRunResponse(
        config=asdict(config),
        elapsed_sec=round(elapsed, 4),
        steps_per_sec=round((config.steps / elapsed) if elapsed else 0.0, 4),
        final={
            "t": final.t,
            "metrics": final.metrics,
            "macro": asdict(final.macro),
            "top_groups": [asdict(group) for group in final.meso_groups[:12]],
            "agent_sample": agent_sample,
        },
        trajectory=[
            {
                "t": snapshot.t,
                "avg_pressure": snapshot.macro.avg_pressure,
                "max_pressure": snapshot.macro.max_pressure,
                "policy_wave": snapshot.macro.policy_wave,
                "shock_strength": snapshot.macro.shock_strength,
                "llm_packet_count": snapshot.metrics["llm_packet_count"],
                "llm_prompt_count": snapshot.metrics["llm_prompt_count"],
            }
            for snapshot in snapshots
        ],
    )
