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


def test_build_cases_supports_mega_preset():
    cases = build_cases(cells=[10], steps=8, repeat=1, preset="mega")
    assert [case.cells for case in cases] == [10000, 25000, 50000, 100000]


def test_build_cases_supports_multiple_llm_profiles():
    cases = build_cases(cells=[100], steps=6, repeat=1, preset=None, llm_profiles=["balanced", "llm-first"])
    assert [case.llm_profile for case in cases] == ["balanced", "llm-first"]
    assert [case.label for case in cases] == ["balanced:100c-6s", "llm-first:100c-6s"]


def test_summarize_case_aggregates_repeat_samples():
    case = BenchmarkCase(label="balanced:100c-10s", cells=100, steps=10, repeat=2, llm_profile="balanced")
    samples = [
        BenchmarkSample(
            label=case.label,
            cells=100,
            steps=10,
            repeat_index=1,
            llm_profile="balanced",
            llm_mode="mock-openai",
            final_cells=120,
            snapshots=10,
            elapsed_sec=1.0,
            steps_per_sec=10.0,
            cell_steps_per_sec=1000.0,
            peak_memory_mb=12.5,
            review_payload_sec=0.02,
            review_payload_kb=12.0,
            review_annotation_count=4,
            review_graph_edges=6,
            review_chain_count=2,
            review_curve_points=10,
            llm_live_call_rate=0.8,
            llm_fallback_rate=0.2,
            llm_stability_score=0.72,
            llm_provider_error_pressure=1,
            llm_total_repairs=3,
            llm_top_reasons={"missing_required_key:key_deltas.0": 2},
            llm_task_repairs={"review_diff": 2},
        ),
        BenchmarkSample(
            label=case.label,
            cells=100,
            steps=10,
            repeat_index=2,
            llm_profile="balanced",
            llm_mode="mock-openai",
            final_cells=118,
            snapshots=10,
            elapsed_sec=2.0,
            steps_per_sec=5.0,
            cell_steps_per_sec=500.0,
            peak_memory_mb=15.5,
            review_payload_sec=0.03,
            review_payload_kb=14.0,
            review_annotation_count=5,
            review_graph_edges=8,
            review_chain_count=3,
            review_curve_points=12,
            llm_live_call_rate=0.6,
            llm_fallback_rate=0.4,
            llm_stability_score=0.55,
            llm_provider_error_pressure=2,
            llm_total_repairs=5,
            llm_top_reasons={"missing_required_key:key_deltas.0": 1, "invalid_anchor_id:key_deltas.0": 2},
            llm_task_repairs={"review_diff": 3, "review_summary": 1},
        ),
    ]
    summary = summarize_case(case, samples)
    assert summary["elapsed_sec_avg"] == 1.5
    assert summary["cell_steps_per_sec_max"] == 1000.0
    assert summary["peak_memory_mb_max"] == 15.5
    assert summary["review_payload_kb_avg"] == 13.0
    assert summary["review_chain_count_max"] == 3
    assert summary["review_curve_points_max"] == 12
    assert summary["llm_live_call_rate_avg"] == 0.7
    assert summary["llm_total_repairs_avg"] == 4.0
    assert summary["llm_provider_error_pressure_max"] == 2
    assert summary["llm_top_reasons"][0]["reason"] == "missing_required_key:key_deltas.0"
