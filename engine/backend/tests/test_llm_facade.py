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
    captured = {}

    def fake_run(prompts, *, task):
        captured["task"] = task
        captured["prompt_count"] = len(list(prompts))
        return ["ok"]

    monkeypatch.setattr("app.llm.facade.generate_reasoning_texts", fake_run)
    out = llm_facade.think([_cell()])
    assert out == ["ok"]
    assert captured == {"task": "thought", "prompt_count": 1}


def test_facade_exposes_convenient_task_methods(monkeypatch):
    calls = []

    def fake_run(prompts, *, task):
        calls.append((task, len(list(prompts))))
        return ["x"]

    monkeypatch.setattr("app.llm.facade.generate_reasoning_texts", fake_run)
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
