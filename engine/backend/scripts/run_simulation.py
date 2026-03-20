#!/usr/bin/env python3
"""Organic4D Engine — 커맨드라인 시뮬레이션 (Phase 2.4).

python run_simulation.py 또는 python -m scripts.run_simulation
t=0..t_max 실행, 스냅샷 저장.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# engine/backend 기준으로 app import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.graph.time_flow import create_time_flow_graph
from app.core.snapshot import SnapshotStore


def main():
    parser = argparse.ArgumentParser(description="Organic4D 시뮬레이션 실행")
    parser.add_argument(
        "--t-max",
        type=float,
        default=100.0,
        help="최대 t 스텝 (기본 100)",
    )
    parser.add_argument(
        "--cells",
        type=int,
        default=5,
        help="초기 세포 수 (기본 5)",
    )
    parser.add_argument(
        "--world-id",
        type=str,
        default="default",
        help="월드 ID",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="출력 최소화",
    )
    args = parser.parse_args()

    store = SnapshotStore(world_id=args.world_id)
    graph = create_time_flow_graph()

    result = graph.invoke(
        {
            "t_max": args.t_max,
            "initial_cell_count": args.cells,
            "snapshot_store": store,
            "nutrient_per_step": 1.0,
        },
        config={"recursion_limit": int(args.t_max) + 50},
    )

    if not args.quiet:
        print(f"시뮬레이션 완료: t=0..{result['current_t']}")
        print(f"최종 세포 수: {len(result['cells'])}")
        print(f"저장된 스냅샷 t: {store.list_t()[:10]}{'...' if len(store.list_t()) > 10 else ''}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
