"""Meso-group aggregation and dynamics for Swarm Mode."""
from __future__ import annotations

import math

from app.swarm.types import MesoGroupState, SwarmAgent


def aggregate_meso_groups(
    agents: list[SwarmAgent],
    *,
    previous: dict[str, MesoGroupState] | None = None,
    packet_amplifiers: dict[str, float] | None = None,
) -> list[MesoGroupState]:
    buckets: dict[str, dict[str, float]] = {}
    for agent in agents:
        bucket = buckets.setdefault(
            agent.group_id,
            {
                "count": 0.0,
                "sum_x": 0.0,
                "sum_y": 0.0,
                "sum_x2": 0.0,
                "sum_y2": 0.0,
                "sum_risk": 0.0,
                "sum_risk2": 0.0,
                "sum_coop": 0.0,
                "sum_coop2": 0.0,
                "sum_policy": 0.0,
                "sum_pressure": 0.0,
            },
        )
        bucket["count"] += 1.0
        bucket["sum_x"] += agent.x
        bucket["sum_y"] += agent.y
        bucket["sum_x2"] += agent.x * agent.x
        bucket["sum_y2"] += agent.y * agent.y
        bucket["sum_risk"] += agent.risk
        bucket["sum_risk2"] += agent.risk * agent.risk
        bucket["sum_coop"] += agent.cooperation
        bucket["sum_coop2"] += agent.cooperation * agent.cooperation
        bucket["sum_policy"] += agent.policy_sensitivity
        bucket["sum_pressure"] += agent.pressure
    previous = previous or {}
    packet_amplifiers = packet_amplifiers or {}
    groups: list[MesoGroupState] = []
    for group_id, stats in buckets.items():
        count = max(1.0, stats["count"])
        center_x = stats["sum_x"] / count
        center_y = stats["sum_y"] / count
        risk_mean = stats["sum_risk"] / count
        coop_mean = stats["sum_coop"] / count
        policy_mean = stats["sum_policy"] / count
        pressure_mean = stats["sum_pressure"] / count
        x_std = _stddev(stats["sum_x2"], stats["sum_x"], count)
        y_std = _stddev(stats["sum_y2"], stats["sum_y"], count)
        risk_std = _stddev(stats["sum_risk2"], stats["sum_risk"], count)
        coop_std = _stddev(stats["sum_coop2"], stats["sum_coop"], count)
        prev = previous.get(group_id)
        drift = math.hypot(center_x - (prev.center_x if prev else center_x), center_y - (prev.center_y if prev else center_y))
        dispersion = x_std + y_std
        cohesion = _clip01(1.0 - min(1.0, dispersion * 0.12 + coop_std * 0.6))
        tension = _clip01(risk_std * 0.55 + pressure_mean * 0.45)
        amplifier = max(0.65, min(1.45, packet_amplifiers.get(group_id, prev.llm_amplifier if prev else 1.0)))
        fracture = _clip01(((1.0 - cohesion) * 0.38 + tension * 0.42 + drift * 0.08 + risk_mean * 0.12) * amplifier)
        pressure = _clip01((fracture * 0.56 + tension * 0.34 + pressure_mean * 0.10) * amplifier)
        groups.append(
            MesoGroupState(
                group_id=group_id,
                count=int(count),
                center_x=round(center_x, 4),
                center_y=round(center_y, 4),
                cohesion=round(cohesion, 4),
                tension=round(tension, 4),
                fracture_risk=round(fracture, 4),
                pressure=round(pressure, 4),
                drift_velocity=round(drift, 4),
                policy_sensitivity=round(policy_mean, 4),
                packet_summary=prev.packet_summary if prev else "",
                llm_amplifier=round(amplifier, 4),
            )
        )
    groups.sort(key=lambda item: item.pressure, reverse=True)
    return groups


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _stddev(sum_sq: float, total: float, count: float) -> float:
    if count <= 1.0:
        return 0.0
    mean = total / count
    variance = max(0.0, (sum_sq / count) - mean * mean)
    return math.sqrt(variance)
