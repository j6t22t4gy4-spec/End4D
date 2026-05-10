"""Convenient, task-oriented LLM entrypoints for the simulation engine."""
from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from app.llm.chat_runtime import generate_reasoning_texts
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

    def _run_task(self, prompts: Iterable[str], *, task: str) -> list[str]:
        return generate_reasoning_texts(prompts, task=task)


llm_facade = LLMFacade()
