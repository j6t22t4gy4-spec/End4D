"""Tiny runtime-config live smoke harness for real-provider checks.

Purpose:
- prove the live provider path can complete end-to-end
- keep prompt volume small enough for practical iteration
- provide one reproducible baseline before larger conflict experiments
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Iterator

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.collective_dynamics import apply_collective_dynamics  # noqa: E402
from app.core.inject_handlers import apply_inject_to_cells  # noqa: E402
from app.core.policy_events import normalize_policy_payload  # noqa: E402
from app.core.settings import (  # noqa: E402
    get_llm_api_key,
    get_llm_base_url,
    get_llm_chat_enabled,
    get_llm_model,
    get_llm_provider,
)
from app.core.snapshot import SnapshotStore  # noqa: E402
from app.graph.time_flow import create_time_flow_graph, create_resume_time_flow_graph  # noqa: E402
from app.llm.facade import llm_facade  # noqa: E402
from app.models.cell import Cell  # noqa: E402
from app.models.world import NutrientEvent  # noqa: E402


def runtime_preflight() -> dict[str, object]:
    provider = str(get_llm_provider() or "stub")
    enabled = bool(get_llm_chat_enabled())
    model = str(get_llm_model() or "stub")
    base_url = str(get_llm_base_url() or "")
    has_api_key = bool(get_llm_api_key())
    reasons: list[str] = []
    ready = True
    if not enabled:
        ready = False
        reasons.append("llm_disabled")
    if provider == "stub":
        ready = False
        reasons.append("provider=stub")
    if provider in {"openai", "openai-compatible"} and not has_api_key:
        ready = False
        reasons.append("api_key_missing")
    if provider != "stub" and not base_url:
        ready = False
        reasons.append("base_url_missing")
    return {
        "ready": ready,
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "has_api_key": has_api_key,
        "diagnosis": "ready" if ready else ", ".join(reasons),
    }


@contextlib.contextmanager
def temporary_live_env(
    *,
    profile: str,
    strict_mode: str,
    cycle_prompt_budget: int,
    agent_sample_size: int,
    dialogue_max_pairs: int,
    group_deliberation_max_groups: int,
    action_interval: int,
    dialogue_interval: int,
    group_deliberation_interval: int,
    thought_interval: int,
    worldview_interval: int,
) -> Iterator[None]:
    keys = [
        "ORGANIC4D_LLM_CHAT_ENABLED",
        "ORGANIC4D_LLM_RUNTIME_PROFILE",
        "ORGANIC4D_LLM_STRICT_MODE",
        "ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET",
        "ORGANIC4D_LLM_AGENT_SAMPLE_SIZE",
        "ORGANIC4D_DIALOGUE_MAX_PAIRS",
        "ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS",
        "ORGANIC4D_ACTION_INTERVAL",
        "ORGANIC4D_DIALOGUE_INTERVAL",
        "ORGANIC4D_GROUP_DELIBERATION_INTERVAL",
        "ORGANIC4D_THOUGHT_INTERVAL",
        "ORGANIC4D_WORLDVIEW_INTERVAL",
    ]
    previous = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["ORGANIC4D_LLM_CHAT_ENABLED"] = "1"
        os.environ["ORGANIC4D_LLM_RUNTIME_PROFILE"] = profile
        os.environ["ORGANIC4D_LLM_STRICT_MODE"] = strict_mode
        os.environ["ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET"] = str(int(cycle_prompt_budget))
        os.environ["ORGANIC4D_LLM_AGENT_SAMPLE_SIZE"] = str(int(agent_sample_size))
        os.environ["ORGANIC4D_DIALOGUE_MAX_PAIRS"] = str(int(dialogue_max_pairs))
        os.environ["ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS"] = str(int(group_deliberation_max_groups))
        os.environ["ORGANIC4D_ACTION_INTERVAL"] = str(int(action_interval))
        os.environ["ORGANIC4D_DIALOGUE_INTERVAL"] = str(int(dialogue_interval))
        os.environ["ORGANIC4D_GROUP_DELIBERATION_INTERVAL"] = str(int(group_deliberation_interval))
        os.environ["ORGANIC4D_THOUGHT_INTERVAL"] = str(int(thought_interval))
        os.environ["ORGANIC4D_WORLDVIEW_INTERVAL"] = str(int(worldview_interval))
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _make_cell(
    cell_id: str,
    *,
    x: float,
    y: float,
    role_key: str,
    zone_id: str,
    worldview_base: float,
    emotion_level: float,
    action_state: dict[str, float],
    persona_text: str,
) -> Cell:
    return Cell(
        cell_id=cell_id,
        x=float(x),
        y=float(y),
        z=0.0,
        t=0.0,
        energy=48.0,
        gene_vec=np.full(32, 0.02, dtype=np.float32),
        emotion_vec=np.full(8, emotion_level, dtype=np.float32),
        thought_vec=np.full(256, 0.01, dtype=np.float32),
        worldview_vec=np.full(384, worldview_base, dtype=np.float32),
        role_key=role_key,
        role_label=role_key,
        zone_id=zone_id,
        zone_label=zone_id,
        zone_influence=1.15 if zone_id == "zone-south" else 0.95,
        zone_friction=0.18 if zone_id == "zone-south" else 0.06,
        persona_text=persona_text,
        action_state=dict(action_state),
    )


def build_mini_conflict_world(cell_count: int, *, aggressive: bool = False) -> list[Cell]:
    north = {
        "cooperation_bias": 0.72,
        "policy_sensitivity": 0.32,
        "resource_bias": 0.35,
        "mobility_bias": 0.24,
        "risk_tolerance": 0.28,
    }
    south = {
        "cooperation_bias": 0.22,
        "policy_sensitivity": 0.82,
        "resource_bias": 0.62,
        "mobility_bias": 0.76,
        "risk_tolerance": 0.74,
    }
    producer = {
        "cooperation_bias": 0.3,
        "policy_sensitivity": 0.64,
        "resource_bias": 0.84,
        "mobility_bias": 0.56,
        "risk_tolerance": 0.68,
    }
    organizer = {
        "cooperation_bias": 0.38,
        "policy_sensitivity": 0.78,
        "resource_bias": 0.46,
        "mobility_bias": 0.8,
        "risk_tolerance": 0.8,
    }
    if aggressive:
        north.update({"cooperation_bias": 0.84, "policy_sensitivity": 0.18, "mobility_bias": 0.14})
        south.update({"cooperation_bias": 0.08, "policy_sensitivity": 0.94, "mobility_bias": 0.9, "risk_tolerance": 0.9})
        producer.update({"cooperation_bias": 0.18, "policy_sensitivity": 0.76, "resource_bias": 0.92, "risk_tolerance": 0.82})
        organizer.update({"cooperation_bias": 0.28, "policy_sensitivity": 0.9, "mobility_bias": 0.92, "risk_tolerance": 0.92})
    base: list[Cell] = [
        _make_cell(
            "north-citizen-0",
            x=0.0,
            y=0.0,
            role_key="citizen",
            zone_id="zone-north",
            worldview_base=0.02,
            emotion_level=0.01,
            action_state=north,
            persona_text="north citizen, stability-first",
        ),
        _make_cell(
            "north-citizen-1",
            x=0.7,
            y=0.0,
            role_key="citizen",
            zone_id="zone-north",
            worldview_base=0.03,
            emotion_level=0.01,
            action_state=north,
            persona_text="north citizen, low policy sensitivity",
        ),
        _make_cell(
            "south-citizen-0",
            x=0.0,
            y=5.0,
            role_key="citizen",
            zone_id="zone-south",
            worldview_base=0.22,
            emotion_level=0.08,
            action_state=south,
            persona_text="south citizen, grievance-heavy",
        ),
        _make_cell(
            "south-citizen-1",
            x=0.8,
            y=5.3,
            role_key="citizen",
            zone_id="zone-south",
            worldview_base=0.24,
            emotion_level=0.09,
            action_state=south,
            persona_text="south citizen, highly reactive to policy shocks",
        ),
        _make_cell(
            "south-producer-0",
            x=1.2,
            y=6.1,
            role_key="producer",
            zone_id="zone-south",
            worldview_base=0.26,
            emotion_level=0.05,
            action_state=producer,
            persona_text="southern producer under cost pressure",
        ),
        _make_cell(
            "south-organizer-0",
            x=0.2,
            y=4.4,
            role_key="organizer",
            zone_id="zone-south",
            worldview_base=0.3,
            emotion_level=0.11,
            action_state=organizer,
            persona_text="southern organizer amplifying dissent",
        ),
        _make_cell(
            "central-enforcer-0",
            x=1.0,
            y=2.8,
            role_key="enforcer",
            zone_id="zone-central",
            worldview_base=0.28,
            emotion_level=0.03,
            action_state=producer,
            persona_text="central enforcer prioritizing compliance",
        ),
        _make_cell(
            "central-enforcer-1",
            x=1.6,
            y=2.9,
            role_key="enforcer",
            zone_id="zone-central",
            worldview_base=0.29,
            emotion_level=0.03,
            action_state=producer,
            persona_text="central enforcer responding to unrest",
        ),
    ]
    return base[: max(4, min(cell_count, len(base)))]


def summarize_cells(cells: list[Cell]) -> dict[str, float | int]:
    states = [dict(cell.action_state) for cell in cells]
    pressures = [float(state.get("collective_pressure", 0.0) or 0.0) for state in states]
    variance = statistics.pvariance(pressures) if len(pressures) > 1 else 0.0
    fracture_count = sum(1 for state in states if bool(state.get("fracture_signal_received")))
    watch_count = sum(1 for state in states if str(state.get("collective_pressure_bucket") or "") == "watch")
    elevated_count = sum(1 for state in states if str(state.get("collective_pressure_bucket") or "") == "elevated")
    critical_count = sum(1 for state in states if str(state.get("collective_pressure_bucket") or "") == "critical")
    return {
        "avg_pressure": round(statistics.fmean(pressures), 4) if pressures else 0.0,
        "max_pressure": round(max(pressures), 4) if pressures else 0.0,
        "pressure_variance": round(float(variance), 5),
        "fracture_signal_count": fracture_count,
        "watch_count": watch_count,
        "elevated_count": elevated_count,
        "critical_count": critical_count,
    }


def summarize_store(store: SnapshotStore) -> dict[str, object]:
    timeline: list[dict[str, object]] = []
    for t in store.list_t():
        snap = store.get(t)
        if snap is None:
            continue
        timeline.append({"t": float(t), **summarize_cells(snap.cells)})
    return {
        "timeline": timeline,
        "max_pressure_seen": round(max((float(item["max_pressure"]) for item in timeline), default=0.0), 4),
        "max_fracture_signal_count": max((int(item["fracture_signal_count"]) for item in timeline), default=0),
        "first_critical_t": next((float(item["t"]) for item in timeline if int(item["critical_count"]) > 0), None),
    }


def _build_policy_payload(args: argparse.Namespace, *, second_shock: bool = False) -> dict[str, object]:
    intensity = float(args.policy_intensity)
    if second_shock:
        intensity = min(1.0, intensity + float(args.second_shock_bonus))
    effect_profile = "restrictive"
    cooperation_delta = -0.03 if not args.aggressive else -0.045
    sensitivity_delta = 0.06 if not args.aggressive else 0.082
    mobility_delta = 0.025 if not args.aggressive else 0.04
    energy_delta = -0.15 if not args.aggressive else -0.22
    emotion_delta = 0.05 if not args.aggressive else 0.068
    if second_shock:
        cooperation_delta *= 1.15
        sensitivity_delta *= 1.1
        mobility_delta *= 1.15
        energy_delta *= 0.9
        emotion_delta *= 1.1
    return normalize_policy_payload(
        {
            "name": "mini southern restriction" if not second_shock else "mini enforcement surge",
            "summary": "small restrictive shock aimed at the southern bloc" if not second_shock else "follow-up restrictive shock around the southern corridor",
            "intensity": intensity,
            "duration_steps": max(2, args.steps // 2),
            "target_roles": ["citizen", "producer", "organizer"] if not second_shock else ["citizen", "organizer", "enforcer"],
            "target_zones": ["zone-south"] if not second_shock else ["zone-south", "zone-central"],
            "effect_profile": effect_profile,
            "cooperation_delta_per_step": cooperation_delta,
            "policy_sensitivity_delta_per_step": sensitivity_delta,
            "mobility_delta_per_step": mobility_delta,
            "energy_delta_per_step": energy_delta,
            "emotion_delta_per_step": emotion_delta,
        }
    )


def run_live_smoke(args: argparse.Namespace) -> dict[str, object]:
    store = SnapshotStore(world_id=f"live-smoke-{args.profile}")
    graph = create_time_flow_graph()
    resume_graph = create_resume_time_flow_graph()
    initial_cells = build_mini_conflict_world(args.cells, aggressive=args.aggressive)
    policy_payload = _build_policy_payload(args, second_shock=False)

    inject_t = max(2, min(args.steps - 2, args.inject_t))
    second_inject_t = None
    if args.second_shock:
        second_inject_t = max(inject_t + 1, min(args.steps - 1, args.second_inject_t))
    llm_facade.reset_stats()

    started = time.perf_counter()
    with temporary_live_env(
        profile=args.profile,
        strict_mode=args.strict_mode,
        cycle_prompt_budget=args.cycle_prompt_budget,
        agent_sample_size=args.agent_sample_size,
        dialogue_max_pairs=args.dialogue_max_pairs,
        group_deliberation_max_groups=args.group_deliberation_max_groups,
        action_interval=args.action_interval,
        dialogue_interval=args.dialogue_interval,
        group_deliberation_interval=args.group_deliberation_interval,
        thought_interval=args.thought_interval,
        worldview_interval=args.worldview_interval,
    ):
        pre = graph.invoke(
            {
                "initial_cells": initial_cells,
                "t_max": float(inject_t),
                "snapshot_store": store,
                "world_events": [],
            },
            config={"recursion_limit": args.steps + 80},
        )
        injected_cells = apply_inject_to_cells([cell.copy() for cell in pre["cells"]], "policy_shift", policy_payload)
        injected_cells, injected_group_state = apply_collective_dynamics(
            injected_cells,
            current_t=float(inject_t),
            previous_group_state=pre.get("group_state"),
        )
        store.save(float(inject_t), injected_cells)
        world_events = [NutrientEvent(t=float(inject_t), event_type="policy_shift", payload=policy_payload)]
        if second_inject_t is None:
            out = resume_graph.invoke(
                {
                    "cells": injected_cells,
                    "current_t": float(inject_t),
                    "t_max": float(args.steps),
                    "snapshot_store": store,
                    "world_events": world_events,
                    "coalition_state": dict(pre.get("coalition_state") or {}),
                    "coalition_history": [dict(item) for item in pre.get("coalition_history") or []],
                    "group_state": dict(injected_group_state),
                },
                config={"recursion_limit": args.steps + 80},
            )
        else:
            mid = resume_graph.invoke(
                {
                    "cells": injected_cells,
                    "current_t": float(inject_t),
                    "t_max": float(second_inject_t),
                    "snapshot_store": store,
                    "world_events": world_events,
                    "coalition_state": dict(pre.get("coalition_state") or {}),
                    "coalition_history": [dict(item) for item in pre.get("coalition_history") or []],
                    "group_state": dict(injected_group_state),
                },
                config={"recursion_limit": args.steps + 80},
            )
            second_payload = _build_policy_payload(args, second_shock=True)
            second_cells = apply_inject_to_cells([cell.copy() for cell in mid["cells"]], "policy_shift", second_payload)
            second_cells, second_group_state = apply_collective_dynamics(
                second_cells,
                current_t=float(second_inject_t),
                previous_group_state=mid.get("group_state"),
            )
            store.save(float(second_inject_t), second_cells)
            world_events.append(NutrientEvent(t=float(second_inject_t), event_type="policy_shift", payload=second_payload))
            out = resume_graph.invoke(
                {
                    "cells": second_cells,
                    "current_t": float(second_inject_t),
                    "t_max": float(args.steps),
                    "snapshot_store": store,
                    "world_events": world_events,
                    "coalition_state": dict(mid.get("coalition_state") or {}),
                    "coalition_history": [dict(item) for item in mid.get("coalition_history") or []],
                    "group_state": dict(second_group_state),
                },
                config={"recursion_limit": args.steps + 80},
            )
        runtime = llm_facade.snapshot_stats()
    elapsed = round(time.perf_counter() - started, 3)

    return {
        "scenario": "runtime-config-live-smoke",
        "profile": args.profile,
        "provider": str(get_llm_provider() or "stub"),
        "model": str(get_llm_model() or "stub"),
        "elapsed_sec": elapsed,
        "config": {
            "cells": args.cells,
            "steps": args.steps,
            "inject_t": inject_t,
            "second_inject_t": second_inject_t,
            "aggressive": args.aggressive,
            "policy_intensity": args.policy_intensity,
            "agent_sample_size": args.agent_sample_size,
            "dialogue_max_pairs": args.dialogue_max_pairs,
            "group_deliberation_max_groups": args.group_deliberation_max_groups,
            "cycle_prompt_budget": args.cycle_prompt_budget,
            "action_interval": args.action_interval,
            "dialogue_interval": args.dialogue_interval,
            "group_deliberation_interval": args.group_deliberation_interval,
            "thought_interval": args.thought_interval,
            "worldview_interval": args.worldview_interval,
        },
        "final": summarize_cells(out["cells"]),
        "timeline_summary": summarize_store(store),
        "runtime_health": {
            "live_call_rate": round(float((runtime.get("health") or {}).get("live_call_rate") or 0.0), 4),
            "fallback_rate": round(float((runtime.get("health") or {}).get("recent_fallback_rate") or 0.0), 4),
            "stability_score": round(float((runtime.get("health") or {}).get("stability_score") or 0.0), 4),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tiny real-provider runtime smoke harness")
    parser.add_argument("--profile", default="balanced", choices=["rules-first", "balanced", "llm-first"])
    parser.add_argument("--strict-mode", default="llm-preferred", choices=["adaptive", "llm-preferred", "fail-hard"])
    parser.add_argument("--cells", type=int, default=6)
    parser.add_argument("--steps", type=int, default=8)
    parser.add_argument("--inject-t", type=int, default=3)
    parser.add_argument("--second-inject-t", type=int, default=5)
    parser.add_argument("--second-shock", action="store_true")
    parser.add_argument("--aggressive", action="store_true")
    parser.add_argument("--policy-intensity", type=float, default=0.88)
    parser.add_argument("--second-shock-bonus", type=float, default=0.08)
    parser.add_argument("--cycle-prompt-budget", type=int, default=24)
    parser.add_argument("--agent-sample-size", type=int, default=3)
    parser.add_argument("--dialogue-max-pairs", type=int, default=2)
    parser.add_argument("--group-deliberation-max-groups", type=int, default=1)
    parser.add_argument("--action-interval", type=int, default=4)
    parser.add_argument("--dialogue-interval", type=int, default=99)
    parser.add_argument("--group-deliberation-interval", type=int, default=99)
    parser.add_argument("--thought-interval", type=int, default=4)
    parser.add_argument("--worldview-interval", type=int, default=99)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    preflight = runtime_preflight()
    if not bool(preflight["ready"]):
        print(
            f"runtime live smoke is not ready: {preflight['diagnosis']}",
            file=sys.stderr,
        )
        return 1
    result = run_live_smoke(args)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "elapsed_sec": result["elapsed_sec"],
                    "final": result["final"],
                    "runtime_health": result["runtime_health"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
