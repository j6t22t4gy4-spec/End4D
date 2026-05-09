"""Benchmark Organic4D simulation throughput.

Uses the deterministic embedding stub by default to focus on engine cost.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ORGANIC4D_EMBED_BACKEND", "stub")

from app.core.snapshot import SnapshotStore
from app.graph.time_flow import create_time_flow_graph


def run_once(cells: int, steps: int) -> dict:
    store = SnapshotStore(world_id=f"bench-{cells}-{steps}")
    graph = create_time_flow_graph()
    start = time.perf_counter()
    out = graph.invoke(
        {
            "initial_cell_count": cells,
            "t_max": float(steps),
            "snapshot_store": store,
        },
        config={"recursion_limit": steps + 80},
    )
    elapsed = time.perf_counter() - start
    final_cells = len(out["cells"])
    return {
        "initial_cells": cells,
        "steps": steps,
        "final_cells": final_cells,
        "elapsed_sec": round(elapsed, 6),
        "steps_per_sec": round(steps / elapsed, 4) if elapsed > 0 else 0.0,
        "cell_steps_per_sec": round((cells * steps) / elapsed, 4) if elapsed > 0 else 0.0,
        "snapshots": len(store.list_t()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark simulation runs")
    parser.add_argument("--cells", type=int, nargs="+", default=[100, 1000])
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()

    results = [run_once(c, args.steps) for c in args.cells]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    for r in results:
        print(
            f"cells={r['initial_cells']} steps={r['steps']} "
            f"elapsed={r['elapsed_sec']}s steps/s={r['steps_per_sec']} "
            f"final_cells={r['final_cells']}"
        )


if __name__ == "__main__":
    main()
