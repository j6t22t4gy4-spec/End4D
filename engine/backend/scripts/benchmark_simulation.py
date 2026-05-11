"""Benchmark Organic4D simulation throughput and memory behavior.

Uses the deterministic embedding stub by default to focus on engine cost and
provide commit-to-commit regression checks on the same machine.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import tracemalloc
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ORGANIC4D_EMBED_BACKEND", "stub")
os.environ.setdefault("ORGANIC4D_LLM_CHAT_ENABLED", "0")

from app.core.snapshot import SnapshotStore
from app.core.review_payloads import build_world_review_payload
from app.graph.time_flow import create_time_flow_graph


PRESETS: dict[str, list[int]] = {
    "smoke": [100, 1000],
    "scale": [1000, 5000, 10000],
    "stress": [10000, 25000, 50000],
    "mega": [10000, 25000, 50000, 100000],
}


@dataclass(frozen=True)
class BenchmarkCase:
    label: str
    cells: int
    steps: int
    repeat: int


@dataclass(frozen=True)
class BenchmarkSample:
    label: str
    cells: int
    steps: int
    repeat_index: int
    final_cells: int
    snapshots: int
    elapsed_sec: float
    steps_per_sec: float
    cell_steps_per_sec: float
    peak_memory_mb: float
    review_payload_sec: float = 0.0
    review_payload_kb: float = 0.0
    review_annotation_count: int = 0
    review_graph_edges: int = 0
    review_chain_count: int = 0
    review_curve_points: int = 0


def run_sample(case: BenchmarkCase, repeat_index: int, *, include_review_payload: bool = False) -> BenchmarkSample:
    store = SnapshotStore(world_id=f"bench-{case.label}-{case.cells}-{case.steps}-{repeat_index}")
    graph = create_time_flow_graph()
    tracemalloc.start()
    start = time.perf_counter()
    out = graph.invoke(
        {
            "initial_cell_count": case.cells,
            "t_max": float(case.steps),
            "snapshot_store": store,
        },
        config={"recursion_limit": case.steps + 80},
    )
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    final_cells = len(out["cells"])
    review_payload_sec = 0.0
    review_payload_kb = 0.0
    review_annotation_count = 0
    review_graph_edges = 0
    review_chain_count = 0
    review_curve_points = 0
    if include_review_payload:
        review_start = time.perf_counter()
        payload = build_world_review_payload(
            {
                "world": SimpleNamespace(world_id=store.world_id, nutrients=[]),
                "snapshot_store": store,
                "genesis_prompt": f"benchmark:{case.label}",
                "persona_country": "bench",
                "config_version": "bench",
                "session_id": "bench-session",
                "role_catalog": [],
                "engine_params": {},
                "coalition_state": {},
                "coalition_history": [],
            }
        )
        review_payload_sec = round(time.perf_counter() - review_start, 6)
        review_payload_kb = round(len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) / 1024.0, 3)
        review_annotation_count = len(list(payload.get("annotation_candidates") or []))
        review_graph_edges = len(list((payload.get("belief_graph") or {}).get("edges") or []))
        review_chain_count = len(list(payload.get("causal_chains") or []))
        review_curve_points = len(list((payload.get("emergent_dynamics") or {}).get("worldview_curve") or []))
    return BenchmarkSample(
        label=case.label,
        cells=case.cells,
        steps=case.steps,
        repeat_index=repeat_index,
        final_cells=final_cells,
        snapshots=len(store.list_t()),
        elapsed_sec=round(elapsed, 6),
        steps_per_sec=round(case.steps / elapsed, 4) if elapsed > 0 else 0.0,
        cell_steps_per_sec=round((case.cells * case.steps) / elapsed, 4) if elapsed > 0 else 0.0,
        peak_memory_mb=round(peak / (1024 * 1024), 4),
        review_payload_sec=review_payload_sec,
        review_payload_kb=review_payload_kb,
        review_annotation_count=review_annotation_count,
        review_graph_edges=review_graph_edges,
        review_chain_count=review_chain_count,
        review_curve_points=review_curve_points,
    )


def build_cases(*, cells: list[int], steps: int, repeat: int, preset: str | None) -> list[BenchmarkCase]:
    if preset:
        cells = list(PRESETS.get(preset, cells))
    return [
        BenchmarkCase(
            label=f"{cells_count}c-{steps}s",
            cells=int(cells_count),
            steps=int(steps),
            repeat=int(repeat),
        )
        for cells_count in cells
    ]


def summarize_case(case: BenchmarkCase, samples: list[BenchmarkSample]) -> dict[str, Any]:
    elapsed = [sample.elapsed_sec for sample in samples]
    throughput = [sample.cell_steps_per_sec for sample in samples]
    memory = [sample.peak_memory_mb for sample in samples]
    payload_sec = [sample.review_payload_sec for sample in samples]
    payload_kb = [sample.review_payload_kb for sample in samples]
    annotation_counts = [sample.review_annotation_count for sample in samples]
    graph_edges = [sample.review_graph_edges for sample in samples]
    chain_counts = [sample.review_chain_count for sample in samples]
    curve_points = [sample.review_curve_points for sample in samples]
    return {
        "label": case.label,
        "cells": case.cells,
        "steps": case.steps,
        "repeat": case.repeat,
        "final_cells_last": samples[-1].final_cells if samples else case.cells,
        "snapshots_last": samples[-1].snapshots if samples else 0,
        "elapsed_sec_avg": round(statistics.fmean(elapsed), 6) if elapsed else 0.0,
        "elapsed_sec_min": round(min(elapsed), 6) if elapsed else 0.0,
        "elapsed_sec_max": round(max(elapsed), 6) if elapsed else 0.0,
        "cell_steps_per_sec_avg": round(statistics.fmean(throughput), 4) if throughput else 0.0,
        "cell_steps_per_sec_min": round(min(throughput), 4) if throughput else 0.0,
        "cell_steps_per_sec_max": round(max(throughput), 4) if throughput else 0.0,
        "peak_memory_mb_avg": round(statistics.fmean(memory), 4) if memory else 0.0,
        "peak_memory_mb_max": round(max(memory), 4) if memory else 0.0,
        "review_payload_sec_avg": round(statistics.fmean(payload_sec), 6) if payload_sec else 0.0,
        "review_payload_kb_avg": round(statistics.fmean(payload_kb), 3) if payload_kb else 0.0,
        "review_annotation_count_max": max(annotation_counts) if annotation_counts else 0,
        "review_graph_edges_max": max(graph_edges) if graph_edges else 0,
        "review_chain_count_max": max(chain_counts) if chain_counts else 0,
        "review_curve_points_max": max(curve_points) if curve_points else 0,
    }


def run_benchmarks(cases: list[BenchmarkCase], *, include_review_payload: bool = False) -> dict[str, Any]:
    all_samples: list[BenchmarkSample] = []
    summaries: list[dict[str, Any]] = []
    for case in cases:
        case_samples = [
            run_sample(case, idx + 1, include_review_payload=include_review_payload)
            for idx in range(case.repeat)
        ]
        all_samples.extend(case_samples)
        summaries.append(summarize_case(case, case_samples))
    return {
        "schema_version": "benchmark-report/v2",
        "environment": {
            "embed_backend": os.getenv("ORGANIC4D_EMBED_BACKEND", ""),
            "llm_chat_enabled": os.getenv("ORGANIC4D_LLM_CHAT_ENABLED", ""),
            "snapshot_interval": os.getenv("ORGANIC4D_SNAPSHOT_INTERVAL", ""),
            "include_review_payload": include_review_payload,
        },
        "summaries": summaries,
        "samples": [asdict(sample) for sample in all_samples],
    }


def _render_text_report(report: dict[str, Any]) -> str:
    lines = []
    for summary in report["summaries"]:
        lines.append(
            " ".join(
                [
                    f"label={summary['label']}",
                    f"cells={summary['cells']}",
                    f"steps={summary['steps']}",
                    f"repeat={summary['repeat']}",
                    f"elapsed_avg={summary['elapsed_sec_avg']}s",
                    f"cell_steps/s_avg={summary['cell_steps_per_sec_avg']}",
                    f"peak_mem_max={summary['peak_memory_mb_max']}MB",
                    f"review_payload_avg={summary['review_payload_sec_avg']}s",
                    f"review_payload_kb_avg={summary['review_payload_kb_avg']}",
                    f"review_chains_max={summary['review_chain_count_max']}",
                    f"review_curve_points_max={summary['review_curve_points_max']}",
                ]
            )
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark simulation runs")
    parser.add_argument("--cells", type=int, nargs="+", default=[100, 1000])
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()))
    parser.add_argument("--snapshot-interval", type=int, default=None)
    parser.add_argument(
        "--include-review-payload",
        action="store_true",
        help="Also benchmark review payload build time/size on the latest snapshot set",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--output", type=str, default="", help="Optional path to write JSON report")
    args = parser.parse_args()

    if args.snapshot_interval is not None:
        os.environ["ORGANIC4D_SNAPSHOT_INTERVAL"] = str(max(1, int(args.snapshot_interval)))

    cases = build_cases(cells=list(args.cells), steps=args.steps, repeat=args.repeat, preset=args.preset)
    report = run_benchmarks(cases, include_review_payload=args.include_review_payload)

    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(_render_text_report(report))


if __name__ == "__main__":
    main()
