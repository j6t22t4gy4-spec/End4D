"""LLM packet adapters for Swarm Mode.

The default implementation is deterministic and local. It gives the Swarm
runner a real packet/agent-mode control surface without making network calls;
production providers can replace the packet provider later.
"""
from __future__ import annotations

from collections import defaultdict
from statistics import fmean
from typing import Any, Protocol

from app.swarm.types import MacroFieldState, MesoGroupState, SwarmAgent, SwarmConfig


class SwarmPacketProvider(Protocol):
    """Provider contract for real or heuristic Swarm LLM amplification."""

    def __call__(
        self,
        *,
        config: SwarmConfig,
        macro: MacroFieldState,
        groups: list[MesoGroupState],
        agents: list[SwarmAgent],
    ) -> list[dict[str, Any]]:
        ...


def default_swarm_packet_provider(
    *,
    config: SwarmConfig,
    macro: MacroFieldState,
    groups: list[MesoGroupState],
    agents: list[SwarmAgent],
) -> list[dict[str, Any]]:
    if config.llm_mode == "agent":
        return _agent_sample_packets(config=config, macro=macro, groups=groups, agents=agents)
    return _meso_group_packets(config=config, macro=macro, groups=groups)


def packet_amplifiers(packets: list[dict[str, Any]]) -> dict[str, float]:
    """Collapse packet outputs into group-level amplifier values."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for packet in packets:
        group_id = str(packet.get("group_id") or "")
        if not group_id:
            continue
        grouped[group_id].append(float(packet.get("amplifier") or 1.0))
    return {
        group_id: _clamp(fmean(values), 0.65, 1.45)
        for group_id, values in grouped.items()
        if values
    }


def _meso_group_packets(
    *,
    config: SwarmConfig,
    macro: MacroFieldState,
    groups: list[MesoGroupState],
) -> list[dict[str, Any]]:
    limit = max(1, min(len(groups), max(2, config.meso_group_count // 4)))
    packets: list[dict[str, Any]] = []
    for group in sorted(groups, key=lambda item: item.pressure + item.fracture_risk, reverse=True)[:limit]:
        amplifier = _clamp(
            1.0
            + group.pressure * 0.18
            + group.tension * 0.12
            + macro.policy_wave * 0.10
            + macro.rumor_pressure * 0.06
            - group.cohesion * 0.05,
            0.72,
            1.34,
        )
        packets.append(
            {
                "kind": "meso_packet",
                "group_id": group.group_id,
                "prompt_count": 1,
                "amplifier": round(amplifier, 4),
                "summary": (
                    f"{group.group_id} amplified by group packet: "
                    f"pressure={group.pressure:.3f}, fracture={group.fracture_risk:.3f}, "
                    f"policy_wave={macro.policy_wave:.3f}"
                ),
            }
        )
    return packets


def _agent_sample_packets(
    *,
    config: SwarmConfig,
    macro: MacroFieldState,
    groups: list[MesoGroupState],
    agents: list[SwarmAgent],
) -> list[dict[str, Any]]:
    sample_size = max(1, min(len(agents), int(config.agent_llm_sample_size)))
    selected = sorted(agents, key=lambda item: item.pressure + item.risk, reverse=True)[:sample_size]
    by_group: dict[str, list[SwarmAgent]] = defaultdict(list)
    group_pressure = {group.group_id: group.pressure for group in groups}
    for agent in selected:
        by_group[agent.group_id].append(agent)

    packets: list[dict[str, Any]] = []
    for group_id, members in by_group.items():
        avg_pressure = fmean([agent.pressure for agent in members])
        avg_risk = fmean([agent.risk for agent in members])
        avg_cooperation = fmean([agent.cooperation for agent in members])
        amplifier = _clamp(
            1.0
            + avg_pressure * 0.20
            + avg_risk * 0.12
            + group_pressure.get(group_id, 0.0) * 0.08
            + macro.policy_wave * 0.08
            - avg_cooperation * 0.06,
            0.74,
            1.38,
        )
        packets.append(
            {
                "kind": "agent_1to1_sample",
                "group_id": group_id,
                "prompt_count": len(members),
                "amplifier": round(amplifier, 4),
                "summary": (
                    f"{group_id} amplified by {len(members)} sampled agents: "
                    f"avg_pressure={avg_pressure:.3f}, avg_risk={avg_risk:.3f}"
                ),
            }
        )
    return packets


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))
