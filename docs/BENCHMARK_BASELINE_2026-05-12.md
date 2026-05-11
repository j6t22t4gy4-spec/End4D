# Benchmark Baseline (2026-05-12)

Short-run large-world baseline collected on the current local machine with review payload generation enabled.

Command pattern:

```bash
engine/backend/.venv/bin/python engine/backend/scripts/benchmark_simulation.py \
  --cells <COUNT> --steps 2 --repeat 1 --include-review-payload --json
```

Environment:

- `ORGANIC4D_EMBED_BACKEND=stub`
- `ORGANIC4D_LLM_CHAT_ENABLED=0`
- Review payload generation: enabled

## Results

| Cells | Steps | Elapsed (s) | Cell-steps / s | Peak memory (MB) | Review payload (s) | Review payload (KB) |
|------:|------:|------------:|---------------:|-----------------:|-------------------:|--------------------:|
| 10,000 | 2 | 5.896894 | 3391.6160 | 178.7609 | 0.233079 | 12.658 |
| 25,000 | 2 | 15.456416 | 3234.9026 | 444.8534 | 0.755402 | 12.678 |
| 50,000 | 2 | 33.128145 | 3018.5813 | 887.9933 | 1.589029 | 12.679 |

## Stored JSON Reports

- [baseline-2026-05-12-10k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-10k.json)
- [baseline-2026-05-12-25k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-25k.json)
- [baseline-2026-05-12-50k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-50k.json)

## Reading Notes

- Throughput falls gradually as cell count rises, but not catastrophically at 50k.
- Peak memory scales close to linearly enough to make 50k a meaningful stress marker.
- Review payload build time is still relatively small compared with total simulation time, but it is no longer negligible at 50k.
- This is a short-run baseline. Long-run baselines with larger `steps` should be collected separately once runtime stability tuning settles.
