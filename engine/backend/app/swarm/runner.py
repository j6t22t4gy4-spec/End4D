"""Standalone lightweight Swarm Mode runner."""
from __future__ import annotations

import random
from dataclasses import replace
from typing import Any

from app.swarm.llm_packets import (
    SwarmPacketProvider,
    default_swarm_packet_provider,
    packet_amplifiers,
)
from app.swarm.macro import compute_macro_field
from app.swarm.meso import aggregate_meso_groups
from app.swarm.micro import seed_micro_agents, tick_micro_agents
from app.swarm.types import MacroFieldState, MesoGroupState, SwarmConfig, SwarmSnapshot, SwarmState


def initialize_swarm(config: SwarmConfig) -> SwarmState:
    agents = seed_micro_agents(config)
    groups = aggregate_meso_groups(agents)
    macro = compute_macro_field(t=0, config=config, groups=groups)
    return SwarmState(config=config, t=0, agents=agents, meso_groups=groups, macro=macro)


def run_swarm(
    config: SwarmConfig | None = None,
    *,
    packet_provider: SwarmPacketProvider | None = None,
) -> list[SwarmSnapshot]:
    state = initialize_swarm(config or SwarmConfig())
    snapshots = [snapshot_swarm(state)]
    provider = packet_provider or default_swarm_packet_provider
    for _ in range(max(0, state.config.steps)):
        state = tick_swarm(state, packet_provider=provider)
        snapshots.append(snapshot_swarm(state))
    return snapshots


def tick_swarm(
    state: SwarmState,
    *,
    packet_provider: SwarmPacketProvider | None = None,
) -> SwarmState:
    config = state.config
    provider = packet_provider or default_swarm_packet_provider
    rng = random.Random(config.seed + state.t + 1)
    current_macro = state.macro or MacroFieldState(
        t=state.t,
        avg_pressure=0.0,
        max_pressure=0.0,
        shock_strength=0.0,
        rumor_pressure=0.0,
        policy_wave=0.0,
    )
    previous_groups = {group.group_id: group for group in state.meso_groups}

    packets: list[dict[str, Any]] = []
    amplifiers: dict[str, float] = {}
    if _should_run_llm_packet(state):
        packets = provider(
            config=config,
            macro=current_macro,
            groups=state.meso_groups,
            agents=state.agents,
        )
        amplifiers = packet_amplifiers(packets)

    agents = tick_micro_agents(
        state.agents,
        groups=previous_groups,
        macro=current_macro,
        rng=rng,
    )
    groups = aggregate_meso_groups(
        agents,
        previous=previous_groups,
        packet_amplifiers=amplifiers,
    )
    groups = _attach_packet_summaries(groups, packets)
    macro = compute_macro_field(
        t=state.t + 1,
        config=config,
        groups=groups,
        previous=current_macro,
    )
    return SwarmState(
        config=config,
        t=state.t + 1,
        agents=agents,
        meso_groups=groups,
        macro=macro,
        llm_packets=[*state.llm_packets, *packets],
    )


def snapshot_swarm(state: SwarmState) -> SwarmSnapshot:
    macro = state.macro or MacroFieldState(
        t=state.t,
        avg_pressure=0.0,
        max_pressure=0.0,
        shock_strength=0.0,
        rumor_pressure=0.0,
        policy_wave=0.0,
    )
    metrics = {
        "simulation_mode": "swarm",
        "agent_count": len(state.agents),
        "meso_group_count": len(state.meso_groups),
        "llm_mode": state.config.llm_mode,
        "llm_packet_count": len(state.llm_packets),
        "llm_prompt_count": sum(int(packet.get("prompt_count") or 0) for packet in state.llm_packets),
        "avg_pressure": macro.avg_pressure,
        "max_pressure": macro.max_pressure,
        "shock_strength": macro.shock_strength,
        "rumor_pressure": macro.rumor_pressure,
        "policy_wave": macro.policy_wave,
    }
    return SwarmSnapshot(
        t=state.t,
        agents=state.agents,
        meso_groups=state.meso_groups,
        macro=macro,
        metrics=metrics,
    )


def _should_run_llm_packet(state: SwarmState) -> bool:
    interval = max(1, int(state.config.packet_interval))
    return state.t > 0 and state.t % interval == 0


def _attach_packet_summaries(
    groups: list[MesoGroupState],
    packets: list[dict[str, Any]],
) -> list[MesoGroupState]:
    summaries = {
        str(packet.get("group_id")): str(packet.get("summary") or "")
        for packet in packets
        if packet.get("group_id")
    }
    if not summaries:
        return groups
    return [
        replace(group, packet_summary=summaries.get(group.group_id, group.packet_summary))
        for group in groups
    ]
