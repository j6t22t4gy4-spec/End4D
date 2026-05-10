"""Convenient, task-oriented LLM entrypoints for the simulation engine."""
from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any, Iterable, Mapping, Sequence

from app.core.settings import (
    get_llm_model,
    get_llm_provider,
    get_llm_task_budget,
    get_llm_task_budgets,
)
from app.llm.chat_runtime import generate_reasoning_batch
from app.llm.prompt_engineering import (
    build_action_prompt,
    build_dialogue_prompt,
    build_group_deliberation_prompt,
    build_policy_prompt,
    build_thought_prompt,
    build_worldview_prompt,
)
from app.llm.prompt_registry import get_prompt_version
from app.models.cell import Cell


class LLMFacade:
    """High-level engine-facing LLM interface.

    Engine modules should call these task-specific methods instead of stitching
    prompt construction and provider invocation together on their own.
    """

    def __init__(self):
        self._lock = Lock()
        self._recent_runs: deque[dict[str, Any]] = deque(maxlen=32)
        self._task_totals: dict[str, dict[str, int]] = {}

    def think(self, cells: Sequence[Cell]) -> list[str]:
        prompts = [build_thought_prompt(cell) for cell in cells]
        return self._run_task(prompts, task="thought")

    def update_worldviews(self, cells: Sequence[Cell]) -> list[str]:
        prompts = [build_worldview_prompt(cell) for cell in cells]
        return self._run_task(prompts, task="worldview")

    def decide_actions(self, cells: Sequence[Cell]) -> list[str]:
        prompts = [build_action_prompt(cell) for cell in cells]
        return self._run_task(prompts, task="action")

    def interpret_policy(
        self,
        cells: Sequence[Cell],
        *,
        event_type: str,
        payload: Mapping,
    ) -> list[str]:
        prompts = [build_policy_prompt(cell, event_type, dict(payload)) for cell in cells]
        return self._run_task(prompts, task="policy")

    def run_dialogues(
        self,
        pairs: Sequence[tuple[Cell, Cell]],
        *,
        current_t: float,
    ) -> list[str]:
        prompts = [
            build_dialogue_prompt(a, b, current_t=current_t)
            for a, b in pairs
        ]
        return self._run_task(prompts, task="dialogue")

    def deliberate_groups(
        self,
        groups: Mapping[str, Sequence[Cell]],
        *,
        current_t: float,
    ) -> list[str]:
        prompts = [
            build_group_deliberation_prompt(role, list(cells), current_t=current_t)
            for role, cells in groups.items()
        ]
        return self._run_task(prompts, task="group_deliberation")

    def plan_genesis(self, prompt_text: str, heuristic_payload: Mapping) -> str:
        prompt = (
            f"prompt_version={get_prompt_version('genesis')}\n"
            f"user_prompt={prompt_text}\n"
            "Heuristic baseline:\n"
            f"{heuristic_payload}\n"
            "Return JSON only."
        )
        out = self._run_task([prompt], task="genesis")
        return out[0] if out else prompt

    def snapshot_stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "provider": get_llm_provider(),
                "model": get_llm_model(),
                "task_budgets": get_llm_task_budgets(),
                "recent_runs": [dict(item) for item in self._recent_runs],
                "task_totals": {
                    key: dict(value)
                    for key, value in self._task_totals.items()
                },
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._recent_runs.clear()
            self._task_totals.clear()

    def _run_task(self, prompts: Iterable[str], *, task: str) -> list[str]:
        items = [str(prompt) for prompt in prompts]
        if not items:
            return []
        task_budget = get_llm_task_budget(task)
        active_items = items[:task_budget]
        skipped_items = items[task_budget:]
        batch = generate_reasoning_batch(active_items, task=task)
        texts = list(batch.get("texts") or []) + skipped_items
        meta = dict(batch.get("meta") or {})
        meta.update(
            {
                "task": task,
                "prompt_version": get_prompt_version(task),
                "provider": str(meta.get("provider") or get_llm_provider()),
                "model": str(meta.get("model") or get_llm_model()),
                "task_budget": int(task_budget),
                "prompt_count_in": len(items),
                "prompt_count_sent": int(meta.get("prompt_count_sent", len(active_items))),
                "prompt_count_skipped_by_task_budget": len(skipped_items),
            }
        )
        if skipped_items:
            meta["used_fallback"] = True
            fallback_reason = str(meta.get("fallback_reason") or "")
            meta["fallback_reason"] = (
                f"{fallback_reason}|task_budget_cap"
                if fallback_reason
                else "task_budget_cap"
            )
        self._record_run(meta)
        return texts

    def _record_run(self, meta: Mapping[str, Any]) -> None:
        task = str(meta.get("task") or "unknown")
        prompt_count_in = int(meta.get("prompt_count_in", 0) or 0)
        prompt_count_sent = int(meta.get("prompt_count_sent", 0) or 0)
        skipped = int(meta.get("prompt_count_skipped_by_task_budget", 0) or 0)
        used_fallback = 1 if bool(meta.get("used_fallback")) else 0
        with self._lock:
            totals = self._task_totals.setdefault(
                task,
                {
                    "calls": 0,
                    "prompt_count_in": 0,
                    "prompt_count_sent": 0,
                    "prompt_count_skipped_by_task_budget": 0,
                    "fallback_calls": 0,
                },
            )
            totals["calls"] += 1
            totals["prompt_count_in"] += prompt_count_in
            totals["prompt_count_sent"] += prompt_count_sent
            totals["prompt_count_skipped_by_task_budget"] += skipped
            totals["fallback_calls"] += used_fallback
            self._recent_runs.append(
                {
                    "task": task,
                    "provider": str(meta.get("provider") or ""),
                    "model": str(meta.get("model") or ""),
                    "prompt_version": str(meta.get("prompt_version") or ""),
                    "prompt_count_in": prompt_count_in,
                    "prompt_count_sent": prompt_count_sent,
                    "prompt_count_skipped_by_task_budget": skipped,
                    "task_budget": int(meta.get("task_budget", 0) or 0),
                    "used_fallback": bool(meta.get("used_fallback")),
                    "fallback_reason": str(meta.get("fallback_reason") or ""),
                }
            )


llm_facade = LLMFacade()
