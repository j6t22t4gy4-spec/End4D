"""Lightweight Swarm Mode engine.

Swarm Mode is intentionally separate from the precision time-flow graph. It
keeps micro agents cheap, lets meso groups own most dynamics, and reserves LLM
work for packet/strategic amplification.
"""

from app.swarm.runner import run_swarm
from app.swarm.types import (
    MacroFieldState,
    MesoGroupState,
    SwarmAgent,
    SwarmConfig,
    SwarmSnapshot,
    SwarmState,
)

__all__ = [
    "MacroFieldState",
    "MesoGroupState",
    "SwarmAgent",
    "SwarmConfig",
    "SwarmSnapshot",
    "SwarmState",
    "run_swarm",
]
