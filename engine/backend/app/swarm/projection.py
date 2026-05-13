"""Compact scene projection for Swarm visualization."""
from __future__ import annotations

import math
from typing import Any

from app.swarm.types import MacroFieldState, MesoGroupState, SwarmAgent


def project_swarm_scene(
    *,
    t: int,
    agents: list[SwarmAgent],
    groups: list[MesoGroupState],
    macro: MacroFieldState,
    agent_limit: int = 1200,
    pressure_grid_size: int = 32,
) -> dict[str, Any]:
    bounds = _bounds(agents, groups)
    stride = max(1, math.ceil(len(agents) / max(1, int(agent_limit))))
    sampled_agents = agents[::stride][: max(0, int(agent_limit))]
    return {
        "schema_version": "swarm-scene/v1",
        "t": int(t),
        "bounds": bounds,
        "agent_count": len(agents),
        "agent_stride": stride,
        "agents": [
            {
                "id": agent.agent_id,
                "g": agent.group_id,
                "x": round(agent.x, 4),
                "y": round(agent.y, 4),
                "p": round(agent.pressure, 4),
                "r": round(agent.risk, 4),
            }
            for agent in sampled_agents
        ],
        "groups": [
            {
                "id": group.group_id,
                "x": group.center_x,
                "y": group.center_y,
                "n": group.count,
                "p": group.pressure,
                "c": group.cohesion,
                "f": group.fracture_risk,
                "a": group.llm_amplifier,
            }
            for group in groups
        ],
        "macro": {
            "avg_pressure": macro.avg_pressure,
            "max_pressure": macro.max_pressure,
            "shock_strength": macro.shock_strength,
            "rumor_pressure": macro.rumor_pressure,
            "policy_wave": macro.policy_wave,
        },
        "pressure_grid": _pressure_grid(
            groups=groups,
            bounds=bounds,
            grid_size=max(4, min(96, int(pressure_grid_size))),
        ),
    }


def _bounds(agents: list[SwarmAgent], groups: list[MesoGroupState]) -> dict[str, float]:
    xs = [agent.x for agent in agents] + [group.center_x for group in groups]
    ys = [agent.y for agent in agents] + [group.center_y for group in groups]
    if not xs or not ys:
        return {"min_x": -1.0, "max_x": 1.0, "min_y": -1.0, "max_y": 1.0}
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    pad = max(1.0, max(max_x - min_x, max_y - min_y) * 0.08)
    return {
        "min_x": round(min_x - pad, 4),
        "max_x": round(max_x + pad, 4),
        "min_y": round(min_y - pad, 4),
        "max_y": round(max_y + pad, 4),
    }


def _pressure_grid(
    *,
    groups: list[MesoGroupState],
    bounds: dict[str, float],
    grid_size: int,
) -> dict[str, Any]:
    min_x = float(bounds["min_x"])
    max_x = float(bounds["max_x"])
    min_y = float(bounds["min_y"])
    max_y = float(bounds["max_y"])
    width = max(0.001, max_x - min_x)
    height = max(0.001, max_y - min_y)
    radius = max(width, height) / max(4.0, grid_size / 2.0)
    cells: list[float] = []
    for row in range(grid_size):
        y = min_y + height * ((row + 0.5) / grid_size)
        for col in range(grid_size):
            x = min_x + width * ((col + 0.5) / grid_size)
            pressure = 0.0
            weight_sum = 0.0
            for group in groups:
                dist = math.hypot(x - group.center_x, y - group.center_y)
                weight = math.exp(-((dist / radius) ** 2))
                pressure += group.pressure * weight
                weight_sum += weight
            cells.append(round(pressure / weight_sum, 4) if weight_sum else 0.0)
    return {
        "cols": grid_size,
        "rows": grid_size,
        "bounds": bounds,
        "cells": cells,
    }
