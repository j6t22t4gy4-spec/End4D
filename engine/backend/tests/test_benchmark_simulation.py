from pathlib import Path
import sys


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmark_simulation import build_cases, summarize_case, BenchmarkCase, BenchmarkSample


def test_build_cases_uses_preset_when_requested():
    cases = build_cases(cells=[10], steps=12, repeat=2, preset="smoke")
    assert [case.cells for case in cases] == [100, 1000]
    assert all(case.steps == 12 for case in cases)
    assert all(case.repeat == 2 for case in cases)


def test_summarize_case_aggregates_repeat_samples():
    case = BenchmarkCase(label="100c-10s", cells=100, steps=10, repeat=2)
    samples = [
        BenchmarkSample(
            label=case.label,
            cells=100,
            steps=10,
            repeat_index=1,
            final_cells=120,
            snapshots=10,
            elapsed_sec=1.0,
            steps_per_sec=10.0,
            cell_steps_per_sec=1000.0,
            peak_memory_mb=12.5,
        ),
        BenchmarkSample(
            label=case.label,
            cells=100,
            steps=10,
            repeat_index=2,
            final_cells=118,
            snapshots=10,
            elapsed_sec=2.0,
            steps_per_sec=5.0,
            cell_steps_per_sec=500.0,
            peak_memory_mb=15.5,
        ),
    ]
    summary = summarize_case(case, samples)
    assert summary["elapsed_sec_avg"] == 1.5
    assert summary["cell_steps_per_sec_max"] == 1000.0
    assert summary["peak_memory_mb_max"] == 15.5
