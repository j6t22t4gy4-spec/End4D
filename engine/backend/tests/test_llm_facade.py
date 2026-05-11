"""Convenient LLM facade tests."""
import numpy as np

from app.llm.facade import llm_facade
from app.models.cell import Cell


def _cell(role: str = "citizen") -> Cell:
    return Cell(
        cell_id=f"{role}-1",
        x=0.0,
        y=0.0,
        z=0.0,
        t=0.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key=role,
        role_label=role,
        persona_text=f"{role} persona",
    )


def test_facade_think_calls_runtime(monkeypatch):
    llm_facade.reset_stats()
    captured = {}

    def fake_run(prompts, *, task):
        captured["task"] = task
        captured["prompt_count"] = len(list(prompts))
        return {
            "texts": ["ok"],
            "meta": {
                "task": task,
                "provider": "stub",
                "model": "stub",
                "prompt_count_in": 1,
                "prompt_count_sent": 1,
                "used_fallback": False,
                "fallback_reason": "",
            },
        }

    monkeypatch.setattr("app.llm.facade.generate_reasoning_batch", fake_run)
    out = llm_facade.think([_cell()])
    assert out == ["ok"]
    assert captured == {"task": "thought", "prompt_count": 1}
    stats = llm_facade.snapshot_stats()
    assert stats["recent_runs"][-1]["task"] == "thought"
    assert stats["recent_runs"][-1]["prompt_output_mode"] == "text"
    assert stats["task_totals"]["thought"]["calls"] == 1
    assert stats["health"]["live_call_rate"] == 1.0
    assert stats["task_insights"][0]["task"] == "thought"


def test_facade_exposes_convenient_task_methods(monkeypatch):
    llm_facade.reset_stats()
    calls = []

    def fake_run(prompts, *, task):
        calls.append((task, len(list(prompts))))
        return {
            "texts": ["x"],
            "meta": {
                "task": task,
                "provider": "stub",
                "model": "stub",
                "prompt_count_in": 1,
                "prompt_count_sent": 1,
                "used_fallback": False,
                "fallback_reason": "",
            },
        }

    monkeypatch.setattr("app.llm.facade.generate_reasoning_batch", fake_run)
    cell = _cell()
    llm_facade.decide_actions([cell])
    llm_facade.interpret_policy([cell], event_type="policy_shift", payload={"name": "tax"})
    llm_facade.run_dialogues([(cell, _cell("regulator"))], current_t=10.0)
    llm_facade.deliberate_groups({"citizen": [cell]}, current_t=20.0)
    assert calls == [
        ("action", 1),
        ("policy", 1),
        ("dialogue", 1),
        ("group_deliberation", 1),
    ]


def test_facade_records_task_budget_fallback(monkeypatch):
    llm_facade.reset_stats()
    monkeypatch.setenv("ORGANIC4D_LLM_BUDGET_THOUGHT", "1")

    def fake_batch(prompts, *, task):
        assert task == "thought"
        return {
            "texts": ["ok"],
            "meta": {
                "task": "thought",
                "provider": "stub",
                "model": "stub",
                "prompt_count_in": 1,
                "prompt_count_sent": 1,
                "used_fallback": False,
                "fallback_reason": "",
            },
        }

    monkeypatch.setattr("app.llm.facade.generate_reasoning_batch", fake_batch)
    out = llm_facade.think([_cell("citizen"), _cell("regulator")])
    assert out[0] == "ok"
    stats = llm_facade.snapshot_stats()
    recent = stats["recent_runs"][-1]
    assert recent["prompt_count_skipped_by_task_budget"] == 1
    assert recent["used_fallback"] is True
    assert "task_budget_cap" in recent["fallback_reason"]
    assert stats["fallback_reason_counts"]["task_budget_cap"] >= 1


def test_facade_tracks_cycle_budget_and_priority(monkeypatch):
    llm_facade.reset_stats()
    monkeypatch.setenv("ORGANIC4D_LLM_BUDGET_THOUGHT", "8")
    monkeypatch.setenv("ORGANIC4D_LLM_BUDGET_WORLDVIEW", "8")
    monkeypatch.setenv("ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET", "3")
    llm_facade.begin_cycle("test-cycle", context={"cell_count": 4})

    def fake_batch(prompts, *, task):
        prompt_list = list(prompts)
        return {
            "texts": [task for _ in prompt_list],
            "meta": {
                "task": task,
                "provider": "stub",
                "model": "stub",
                "prompt_count_in": len(prompt_list),
                "prompt_count_sent": len(prompt_list),
                "used_fallback": False,
                "fallback_reason": "",
            },
        }

    monkeypatch.setattr("app.llm.facade.generate_reasoning_batch", fake_batch)
    thought_out = llm_facade.think([_cell("a"), _cell("b")])
    worldview_out = llm_facade.update_worldviews([_cell("c"), _cell("d")])
    assert thought_out == ["thought", "thought"]
    assert worldview_out[0] == "worldview"
    assert len(worldview_out) == 2
    stats = llm_facade.snapshot_stats()
    assert stats["scheduler"]["cycle_key"] == "test-cycle"
    assert stats["task_totals"]["worldview"]["prompt_count_skipped_by_cycle_budget"] == 1
    recent = stats["recent_runs"][-1]
    assert recent["cycle_key"] == "test-cycle"
    assert recent["prompt_count_skipped_by_cycle_budget"] == 1


def test_facade_adaptive_priority_skip(monkeypatch):
    llm_facade.reset_stats()
    monkeypatch.setenv("ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET", "2")
    monkeypatch.setenv("ORGANIC4D_LLM_BUDGET_DIALOGUE", "4")
    llm_facade.begin_cycle("low-budget", context={"cell_count": 10})

    def fake_batch(prompts, *, task):
        prompt_list = list(prompts)
        return {
            "texts": [task for _ in prompt_list],
            "meta": {
                "task": task,
                "provider": "stub",
                "model": "stub",
                "prompt_count_in": len(prompt_list),
                "prompt_count_sent": len(prompt_list),
                "used_fallback": False,
                "fallback_reason": "",
            },
        }

    monkeypatch.setattr("app.llm.facade.generate_reasoning_batch", fake_batch)
    llm_facade.think([_cell("a"), _cell("b")])
    out = llm_facade.run_dialogues([(_cell("c"), _cell("d")), (_cell("e"), _cell("f"))], current_t=10.0)
    assert len(out) == 2
    stats = llm_facade.snapshot_stats()
    recent = stats["recent_runs"][-1]
    assert recent["task"] == "dialogue"
    assert recent["used_fallback"] is True
    assert "cycle_budget_cap" in recent["fallback_reason"] or "adaptive_priority_skip" in recent["fallback_reason"]
