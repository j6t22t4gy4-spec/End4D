"""Run the standalone lightweight Swarm Mode engine.

This harness is intentionally separate from the precision graph runner. It is
for quick checks of Micro -> Meso -> Macro dynamics and LLM packet strategy.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.swarm import SwarmConfig, project_swarm_scene, run_swarm_compact  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=1000)
    parser.add_argument("--groups", type=int, default=24)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--llm-mode", choices=["packet", "agent"], default="packet")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--policy-intensity", type=float, default=0.35)
    parser.add_argument("--scenario-prompt", type=str, default="")
    parser.add_argument("--shock-interval", type=int, default=8)
    parser.add_argument("--packet-interval", type=int, default=8)
    parser.add_argument("--agent-llm-sample-size", type=int, default=32)
    parser.add_argument("--min-interactions-per-step", type=int, default=2)
    parser.add_argument("--max-interactions-per-step", type=int, default=10)
    parser.add_argument("--interaction-sensitivity", type=float, default=1.0)
    parser.add_argument("--scene-agent-limit", type=int, default=1200)
    parser.add_argument("--pressure-grid-size", type=int, default=32)
    parser.add_argument("--include-full-agents", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config = SwarmConfig(
        agent_count=max(1, args.agents),
        meso_group_count=max(1, args.groups),
        steps=max(0, args.steps),
        llm_mode=args.llm_mode,
        seed=args.seed,
        policy_intensity=max(0.0, min(1.0, args.policy_intensity)),
        shock_interval=max(0, args.shock_interval),
        packet_interval=max(1, args.packet_interval),
        agent_llm_sample_size=max(1, args.agent_llm_sample_size),
        min_interactions_per_step=max(1, args.min_interactions_per_step),
        max_interactions_per_step=max(1, args.max_interactions_per_step),
        interaction_sensitivity=max(0.1, args.interaction_sensitivity),
        scenario_prompt=str(args.scenario_prompt or ""),
    )
    start = time.perf_counter()
    state, trajectory = run_swarm_compact(config)
    elapsed = time.perf_counter() - start
    macro = state.macro
    if macro is None:
        raise RuntimeError("Swarm runner returned no macro field")
    scene = project_swarm_scene(
        t=state.t,
        agents=state.agents,
        groups=state.meso_groups,
        macro=macro,
        agent_limit=max(0, args.scene_agent_limit),
        pressure_grid_size=max(4, args.pressure_grid_size),
    )
    metrics = {
        "simulation_mode": "swarm",
        "agent_count": len(state.agents),
        "meso_group_count": len(state.meso_groups),
        "llm_mode": config.llm_mode,
        "llm_packet_count": len(state.llm_packets),
        "llm_prompt_count": sum(int(packet.get("prompt_count") or 0) for packet in state.llm_packets),
        "internal_interactions": state.internal_interactions,
        "last_interactions_per_step": state.last_interactions_per_step,
        "avg_persona_grounding": round(sum(agent.persona_grounding_score for agent in state.agents) / max(1, len(state.agents)), 4),
        "avg_scenario_relevance": round(sum(agent.scenario_relevance_score for agent in state.agents) / max(1, len(state.agents)), 4),
        "avg_pressure": macro.avg_pressure,
        "max_pressure": macro.max_pressure,
        "shock_strength": macro.shock_strength,
        "rumor_pressure": macro.rumor_pressure,
        "policy_wave": macro.policy_wave,
        "scene_agent_count": len(scene["agents"]),
        "pressure_grid_cells": len(scene["pressure_grid"]["cells"]),
        "full_agents_included": bool(args.include_full_agents),
    }
    payload = {
        "config": asdict(config),
        "elapsed_sec": round(elapsed, 4),
        "steps_per_sec": round((config.steps / elapsed) if elapsed else 0.0, 4),
        "final": {
            "t": state.t,
            "metrics": metrics,
            "macro": asdict(macro),
            "top_groups": [asdict(group) for group in state.meso_groups[:8]],
            "agent_sample": [asdict(agent) for agent in state.agents[:8]],
            "full_agents": [asdict(agent) for agent in state.agents] if args.include_full_agents else [],
            "scene": scene,
        },
        "trajectory": trajectory,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    print(
        "Swarm complete: "
        f"agents={config.agent_count}, groups={config.meso_group_count}, "
        f"steps={config.steps}, mode={config.llm_mode}, elapsed={elapsed:.3f}s"
    )
    print(
        "Final field: "
        f"avg_pressure={macro.avg_pressure:.3f}, "
        f"max_pressure={macro.max_pressure:.3f}, "
        f"policy_wave={macro.policy_wave:.3f}, "
        f"llm_prompts={metrics['llm_prompt_count']}, "
        f"scene_agents={metrics['scene_agent_count']}, "
        f"internal_interactions={metrics['internal_interactions']}"
    )
    for group in state.meso_groups[:5]:
        print(
            f"- {group.group_id}: pressure={group.pressure:.3f}, "
            f"fracture={group.fracture_risk:.3f}, amplifier={group.llm_amplifier:.3f}"
        )


if __name__ == "__main__":
    main()
