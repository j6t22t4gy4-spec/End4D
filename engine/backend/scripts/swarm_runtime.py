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

from app.swarm import SwarmConfig, run_swarm  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agents", type=int, default=1000)
    parser.add_argument("--groups", type=int, default=24)
    parser.add_argument("--steps", type=int, default=32)
    parser.add_argument("--llm-mode", choices=["packet", "agent"], default="packet")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--policy-intensity", type=float, default=0.35)
    parser.add_argument("--shock-interval", type=int, default=8)
    parser.add_argument("--packet-interval", type=int, default=8)
    parser.add_argument("--agent-llm-sample-size", type=int, default=32)
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
    )
    start = time.perf_counter()
    snapshots = run_swarm(config)
    elapsed = time.perf_counter() - start
    final = snapshots[-1]
    payload = {
        "config": asdict(config),
        "elapsed_sec": round(elapsed, 4),
        "steps_per_sec": round((config.steps / elapsed) if elapsed else 0.0, 4),
        "final": {
            "t": final.t,
            "metrics": final.metrics,
            "macro": asdict(final.macro),
            "top_groups": [asdict(group) for group in final.meso_groups[:8]],
            "agent_sample": [asdict(agent) for agent in final.agents[:8]],
        },
        "trajectory": [
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
        f"avg_pressure={final.macro.avg_pressure:.3f}, "
        f"max_pressure={final.macro.max_pressure:.3f}, "
        f"policy_wave={final.macro.policy_wave:.3f}, "
        f"llm_prompts={final.metrics['llm_prompt_count']}"
    )
    for group in final.meso_groups[:5]:
        print(
            f"- {group.group_id}: pressure={group.pressure:.3f}, "
            f"fracture={group.fracture_risk:.3f}, amplifier={group.llm_amplifier:.3f}"
        )


if __name__ == "__main__":
    main()
