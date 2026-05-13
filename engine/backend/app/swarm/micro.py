"""Micro-agent layer for Swarm Mode."""
from __future__ import annotations

import math
import random

from app.swarm.types import MacroFieldState, MesoGroupState, SwarmAgent, SwarmConfig


def seed_micro_agents(config: SwarmConfig) -> list[SwarmAgent]:
    rng = random.Random(config.seed)
    group_count = max(1, int(config.meso_group_count))
    agents: list[SwarmAgent] = []
    for idx in range(max(1, int(config.agent_count))):
        group_idx = idx % group_count
        theta = (2.0 * math.pi * group_idx) / group_count
        local = rng.random() * 2.0 * math.pi
        radius = 10.0 + group_idx * 0.04 + rng.random() * 2.5
        x = math.cos(theta) * radius + math.cos(local) * rng.random() * 1.6
        y = math.sin(theta) * radius + math.sin(local) * rng.random() * 1.6
        agents.append(
            SwarmAgent(
                agent_id=f"swarm-agent-{idx}",
                group_id=f"group-{group_idx}",
                x=x,
                y=y,
                vx=rng.uniform(-0.025, 0.025),
                vy=rng.uniform(-0.025, 0.025),
                energy=rng.uniform(0.45, 0.75),
                cooperation=rng.uniform(0.35, 0.75),
                policy_sensitivity=rng.uniform(0.25, 0.82),
                risk=rng.uniform(0.2, 0.72),
                role=f"role-{group_idx % 6}",
            )
        )
    return agents


def tick_micro_agents(
    agents: list[SwarmAgent],
    *,
    groups: dict[str, MesoGroupState],
    macro: MacroFieldState,
    rng: random.Random,
    interaction_scale: float = 1.0,
) -> list[SwarmAgent]:
    updated: list[SwarmAgent] = []
    for agent in agents:
        group = groups.get(agent.group_id)
        group_pressure = group.pressure if group else 0.0
        group_tension = group.tension if group else 0.0
        agent_pressure = min(1.0, group_pressure * 0.72 + macro.policy_wave * agent.policy_sensitivity * 0.22 + macro.rumor_pressure * 0.06)
        pull_x = ((group.center_x if group else agent.x) - agent.x) * max(0.002, 0.016 - group_tension * 0.008)
        pull_y = ((group.center_y if group else agent.y) - agent.y) * max(0.002, 0.016 - group_tension * 0.008)
        jitter = 0.012 + agent_pressure * 0.045 + group_tension * 0.025
        vx = (agent.vx * 0.86) + pull_x + rng.uniform(-jitter, jitter)
        vy = (agent.vy * 0.86) + pull_y + rng.uniform(-jitter, jitter)
        scale = max(0.1, float(interaction_scale))
        risk = _clip01(agent.risk + (agent_pressure * 0.018 - agent.cooperation * 0.006) * scale)
        cooperation = _clip01(agent.cooperation + ((0.5 - group_tension) * 0.012 - agent_pressure * 0.014) * scale)
        updated.append(
            SwarmAgent(
                agent_id=agent.agent_id,
                group_id=agent.group_id,
                x=agent.x + vx,
                y=agent.y + vy,
                vx=vx,
                vy=vy,
                energy=_clip01(agent.energy - 0.001 + cooperation * 0.0015 - risk * 0.001),
                cooperation=cooperation,
                policy_sensitivity=_clip01(agent.policy_sensitivity + macro.policy_wave * 0.006),
                risk=risk,
                pressure=agent_pressure,
                role=agent.role,
            )
        )
    return updated


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
