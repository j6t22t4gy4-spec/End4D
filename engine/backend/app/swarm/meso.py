"""Meso-group aggregation and dynamics for Swarm Mode."""
from __future__ import annotations

from collections import defaultdict
import math
from statistics import fmean, pstdev

from app.swarm.types import MesoGroupState, SwarmAgent


def aggregate_meso_groups(
    agents: list[SwarmAgent],
    *,
    previous: dict[str, MesoGroupState] | None = None,
    packet_amplifiers: dict[str, float] | None = None,
) -> list[MesoGroupState]:
    buckets: dict[str, list[SwarmAgent]] = defaultdict(list)
    for agent in agents:
        buckets[agent.group_id].append(agent)
    previous = previous or {}
    packet_amplifiers = packet_amplifiers or {}
    groups: list[MesoGroupState] = []
    for group_id, members in buckets.items():
        xs = [agent.x for agent in members]
        ys = [agent.y for agent in members]
        risks = [agent.risk for agent in members]
        coops = [agent.cooperation for agent in members]
        policies = [agent.policy_sensitivity for agent in members]
        pressures = [agent.pressure for agent in members]
        center_x = fmean(xs)
        center_y = fmean(ys)
        prev = previous.get(group_id)
        drift = math.hypot(center_x - (prev.center_x if prev else center_x), center_y - (prev.center_y if prev else center_y))
        dispersion = (pstdev(xs) if len(xs) > 1 else 0.0) + (pstdev(ys) if len(ys) > 1 else 0.0)
        cohesion = _clip01(1.0 - min(1.0, dispersion * 0.12 + pstdev(coops) * 0.6 if len(coops) > 1 else dispersion * 0.12))
        tension = _clip01((pstdev(risks) if len(risks) > 1 else 0.0) * 0.55 + fmean(pressures) * 0.45)
        amplifier = max(0.65, min(1.45, packet_amplifiers.get(group_id, prev.llm_amplifier if prev else 1.0)))
        fracture = _clip01(((1.0 - cohesion) * 0.38 + tension * 0.42 + drift * 0.08 + fmean(risks) * 0.12) * amplifier)
        pressure = _clip01((fracture * 0.56 + tension * 0.34 + fmean(pressures) * 0.10) * amplifier)
        groups.append(
            MesoGroupState(
                group_id=group_id,
                count=len(members),
                center_x=round(center_x, 4),
                center_y=round(center_y, 4),
                cohesion=round(cohesion, 4),
                tension=round(tension, 4),
                fracture_risk=round(fracture, 4),
                pressure=round(pressure, 4),
                drift_velocity=round(drift, 4),
                policy_sensitivity=round(fmean(policies), 4),
                packet_summary=prev.packet_summary if prev else "",
                llm_amplifier=round(amplifier, 4),
            )
        )
    groups.sort(key=lambda item: item.pressure, reverse=True)
    return groups


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
