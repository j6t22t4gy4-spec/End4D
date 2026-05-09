"""Sample a Hugging Face persona dataset into a local JSONL file.

Example:
  python scripts/sample_personas.py \
    --dataset nvidia/Nemotron-Personas-Korea \
    --country KR \
    --output data/personas/kr.jsonl \
    --count 1000
"""
from __future__ import annotations

import argparse
import hashlib
import heapq
import json
from pathlib import Path
from typing import Any, Dict


def _score(seed: str, row: Dict[str, Any], idx: int) -> int:
    raw_id = str(row.get("uuid") or row.get("id") or idx)
    digest = hashlib.sha256(f"{seed}|{raw_id}|{idx}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sample persona rows to JSONL")
    parser.add_argument("--dataset", required=True, help="Hugging Face dataset id")
    parser.add_argument("--country", default="", help="Country code to inject when missing")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument("--count", type=int, default=1000, help="Rows to write")
    parser.add_argument("--max-scan", type=int, default=50000, help="Max streaming rows to scan")
    parser.add_argument("--seed", default="organic4d", help="Deterministic sampling seed")
    args = parser.parse_args()

    from datasets import load_dataset

    heap: list[tuple[int, int, Dict[str, Any]]] = []
    ds = load_dataset(args.dataset, split="train", streaming=True)
    for idx, row in enumerate(ds):
        if idx >= args.max_scan:
            break
        if args.country and not row.get("country"):
            row = dict(row)
            row["country"] = args.country
        item = (-_score(args.seed, row, idx), idx, row)
        if len(heap) < args.count:
            heapq.heappush(heap, item)
        elif item > heap[0]:
            heapq.heapreplace(heap, item)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for _, _, row in sorted(heap, reverse=True):
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"wrote {len(heap)} rows to {out_path}")


if __name__ == "__main__":
    main()
