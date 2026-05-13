"""Shared data models for the lightweight Swarm engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


SwarmLlmMode = Literal["packet", "agent"]


@dataclass
class SwarmConfig:
    agent_count: int = 1000
    meso_group_count: int = 24
    steps: int = 32
    llm_mode: SwarmLlmMode = "packet"
    seed: int = 7
    policy_intensity: float = 0.0
    shock_interval: int = 0
    packet_interval: int = 8
    agent_llm_sample_size: int = 32


@dataclass
class SwarmAgent:
    agent_id: str
    group_id: str
    x: float
    y: float
    vx: float
    vy: float
    energy: float
    cooperation: float
    policy_sensitivity: float
    risk: float
    pressure: float = 0.0
    role: str = "agent"


@dataclass
class MesoGroupState:
    group_id: str
    count: int
    center_x: float
    center_y: float
    cohesion: float
    tension: float
    fracture_risk: float
    pressure: float
    drift_velocity: float
    policy_sensitivity: float
    packet_summary: str = ""
    llm_amplifier: float = 1.0


@dataclass
class MacroFieldState:
    t: int
    avg_pressure: float
    max_pressure: float
    shock_strength: float
    rumor_pressure: float
    policy_wave: float


@dataclass
class SwarmSnapshot:
    t: int
    agents: list[SwarmAgent]
    meso_groups: list[MesoGroupState]
    macro: MacroFieldState
    metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class SwarmState:
    config: SwarmConfig
    t: int
    agents: list[SwarmAgent]
    meso_groups: list[MesoGroupState] = field(default_factory=list)
    macro: MacroFieldState | None = None
    llm_packets: list[dict[str, Any]] = field(default_factory=list)

