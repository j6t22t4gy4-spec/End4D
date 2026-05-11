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

## Short Long-Run Checks

| Cells | Steps | Elapsed (s) | Cell-steps / s | Peak memory (MB) | Review payload (s) | Review payload (KB) |
|------:|------:|------------:|---------------:|-----------------:|-------------------:|--------------------:|
| 10,000 | 10 | 25.240684 | 3961.8578 | 578.3784 | 0.356507 | 14.252 |
| 25,000 | 6 | 29.008368 | 5170.9218 | 880.1224 | 0.767318 | 13.631 |

## Stored JSON Reports

- [baseline-2026-05-12-10k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-10k.json)
- [baseline-2026-05-12-25k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-25k.json)
- [baseline-2026-05-12-50k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-50k.json)
- [baseline-2026-05-12-long-10k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-long-10k.json)
- [baseline-2026-05-12-long-25k.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-long-25k.json)

## Reading Notes

- Throughput falls gradually as cell count rises, but not catastrophically at 50k.
- Peak memory scales close to linearly enough to make 50k a meaningful stress marker.
- Review payload build time is still relatively small compared with total simulation time, but it is no longer negligible at 50k.
- This is a short-run baseline. Long-run baselines with larger `steps` should be collected separately once runtime stability tuning settles.
- The short long-run checks above are still `stub + LLM off` measurements. They are useful for engine-side pressure and payload growth, but not yet for observing citation repair pressure under `llm-first`.

## Mock LLM Path Checks

Because no external provider was configured on this machine during this pass, the `LLM on` benchmark used the new `mock-openai` mode to exercise the real HTTP runtime path, review suite, citation repair pass, and runtime telemetry without depending on a remote model.

Command pattern:

```bash
engine/backend/.venv/bin/python engine/backend/scripts/benchmark_simulation.py \
  --cells <COUNT> --steps <STEPS> --repeat 1 \
  --llm-mode mock-openai \
  --llm-profiles balanced llm-first \
  --llm-strict-mode llm-preferred \
  --include-review-payload \
  --include-review-suite \
  --json
```

### Profile Comparison

| Cells | Steps | Profile | Elapsed (s) | Cell-steps / s | Live call rate | Fallback rate | Stability | Repairs | Top repair reason |
|------:|------:|---------|------------:|---------------:|---------------:|--------------:|----------:|--------:|-------------------|
| 1,000 | 4 | `balanced` | 0.795793 | 5026.4301 | 0.9231 | 0.0769 | 0.9423 | 6 | `missing_citation_list` |
| 1,000 | 4 | `llm-first` | 0.803332 | 4979.2593 | 0.8571 | 0.1429 | 0.8929 | 6 | `missing_citation_list` |
| 2,500 | 6 | `balanced` | 2.655336 | 5649.0028 | 0.9231 | 0.0769 | 0.9423 | 6 | `missing_citation_list` |
| 2,500 | 6 | `llm-first` | 2.809409 | 5339.2004 | 0.7500 | 0.2500 | 0.8125 | 6 | `missing_citation_list` |

### Reading Notes

- The mock path is **not** a substitute for an external provider baseline. It is a deterministic way to exercise:
  - live provider HTTP calls
  - strict citation contracts
  - citation repair pass
  - runtime stability telemetry
- In this deterministic mock setup, repair reason distribution stayed the same across `balanced` and `llm-first`:
  - `missing_citation_list`
  - `invalid_required_anchor:headline`
  - `invalid_required_anchor:key_deltas.0`
  - `invalid_required_anchor:key_findings.0`
- The useful signal here is that `llm-first` already shows higher runtime pressure:
  - lower live call rate
  - higher fallback rate
  - lower stability score
- This means the next real-provider pass should focus on:
  - whether `llm-first` still preserves acceptable live-call dominance
  - whether repair reasons remain the same once the model is no longer deterministic

### Stored JSON Reports

- [baseline-2026-05-12-llm-mock-profiles.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-llm-mock-profiles.json)
- [baseline-2026-05-12-llm-mock-profiles-2500.json](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/backend/benchmarks/baseline-2026-05-12-llm-mock-profiles-2500.json)
