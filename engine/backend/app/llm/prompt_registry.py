"""Versioned prompt registry and contracts for engine LLM tasks."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

PromptOutputMode = Literal["text", "json"]
PROMPT_SCHEMA_VERSION = "prompt-spec/v1"


@dataclass(frozen=True)
class PromptSpec:
    task: str
    version: str
    output_mode: PromptOutputMode
    system_prompt: str
    description: str
    expected_keys: tuple[str, ...] = ()

    def system_instruction(self) -> str:
        parts = [
            f"prompt_schema_version={PROMPT_SCHEMA_VERSION}",
            f"task={self.task}",
            f"prompt_version={self.version}",
            f"output_mode={self.output_mode}",
            f"description={self.description}",
            self.system_prompt.strip(),
        ]
        if self.expected_keys:
            parts.append(f"expected_keys={', '.join(self.expected_keys)}")
        return "\n".join(part for part in parts if part)

    def meta(self) -> dict[str, Any]:
        return {
            "schema_version": PROMPT_SCHEMA_VERSION,
            "task": self.task,
            "prompt_version": self.version,
            "output_mode": self.output_mode,
            "description": self.description,
            "expected_keys": list(self.expected_keys),
        }


PROMPT_SPECS: dict[str, PromptSpec] = {
    "genesis": PromptSpec(
        task="genesis",
        version="genesis-v2",
        output_mode="json",
        description="Initial condition planner for long-horizon social simulation worlds.",
        system_prompt=(
            "Design initial conditions for a long-horizon societal simulation. "
            "Return compact JSON only."
        ),
        expected_keys=(
            "t_max",
            "initial_cell_count",
            "role_catalog",
            "rationale",
            "t_step_semantic",
            "t_step_unit",
            "nutrient_per_step",
            "persona_country",
            "persona_source",
        ),
    ),
    "thought": PromptSpec(
        task="thought",
        version="thought-v2",
        output_mode="text",
        description="Immediate strategic thought update for one social agent.",
        system_prompt=(
            "Write compact analytical text about current goals, fears, incentives, "
            "and next moves. Keep it concise and state-like rather than conversational."
        ),
    ),
    "worldview": PromptSpec(
        task="worldview",
        version="worldview-v2",
        output_mode="text",
        description="Long-horizon belief and alignment update for one social agent.",
        system_prompt=(
            "Write compact analytical text about ideology, trust structure, durable "
            "priorities, and expected long-run behavior."
        ),
    ),
    "action": PromptSpec(
        task="action",
        version="action-v2",
        output_mode="json",
        description="Action profile inference for the next simulation interval.",
        system_prompt=(
            "Convert an agent state into an action profile for the next simulation interval. "
            "Return compact JSON only."
        ),
        expected_keys=(
            "strategy_summary",
            "resource_bias",
            "risk_tolerance",
            "cooperation_bias",
            "policy_sensitivity",
            "mobility_bias",
        ),
    ),
    "policy": PromptSpec(
        task="policy",
        version="policy-v2",
        output_mode="json",
        description="Interpret a policy event for one social agent.",
        system_prompt=(
            "Interpret a policy event for one social agent. Return compact JSON only."
        ),
        expected_keys=(
            "memory_summary",
            "emotion_index",
            "emotion_delta",
            "cooperation_shift",
            "policy_sensitivity_shift",
            "importance",
        ),
    ),
    "dialogue": PromptSpec(
        task="dialogue",
        version="dialogue-v2",
        output_mode="json",
        description="Compact outcome of an agent-to-agent dialogue.",
        system_prompt=(
            "Simulate a compact agent-to-agent dialogue outcome. Return compact JSON only."
        ),
        expected_keys=(
            "summary_a",
            "summary_b",
            "alignment_delta",
            "tension_delta",
            "cooperation_delta",
            "importance",
        ),
    ),
    "group_deliberation": PromptSpec(
        task="group_deliberation",
        version="group-deliberation-v2",
        output_mode="json",
        description="Compact summary of a role-group negotiation block.",
        system_prompt=(
            "Summarize a group negotiation among social roles in a long-horizon simulation. "
            "Return compact JSON only."
        ),
        expected_keys=(
            "stance_summary",
            "cohesion_delta",
            "tension_delta",
            "coalition_signal",
            "importance",
        ),
    ),
    "review_summary": PromptSpec(
        task="review_summary",
        version="review-summary-v2",
        output_mode="json",
        description="Executive summary for a completed simulation world.",
        system_prompt=(
            "Act as an analyst reviewing a completed long-horizon societal simulation. "
            "Return compact JSON only, focusing on major events, belief shifts, causes, and decision implications."
        ),
        expected_keys=(
            "headline",
            "executive_summary",
            "key_events",
            "causal_analysis",
            "decision_implications",
            "watch_items",
        ),
    ),
    "timeline_annotation": PromptSpec(
        task="timeline_annotation",
        version="timeline-annotation-v1",
        output_mode="json",
        description="Annotate key turning points in a completed simulation timeline.",
        system_prompt=(
            "Identify the most meaningful turning points in the timeline and return compact JSON only."
        ),
        expected_keys=("annotations",),
    ),
    "review_diff": PromptSpec(
        task="review_diff",
        version="review-diff-v1",
        output_mode="json",
        description="Compare two simulation worlds and explain the most decision-relevant differences.",
        system_prompt=(
            "Compare a baseline simulation and a target simulation. Return compact JSON only, "
            "focusing on key deltas, causal interpretation, and decision implications."
        ),
        expected_keys=(
            "headline",
            "executive_summary",
            "key_deltas",
            "causal_comparison",
            "decision_implications",
        ),
    ),
    "review_query": PromptSpec(
        task="review_query",
        version="review-query-v1",
        output_mode="json",
        description="Answer a focused analyst question about a completed simulation world using structured review evidence.",
        system_prompt=(
            "Answer the analyst question using only the structured simulation evidence provided. "
            "Return compact JSON only, with a direct answer, supporting evidence, and confidence notes."
        ),
        expected_keys=(
            "answer",
            "evidence",
            "follow_up",
            "confidence_notes",
        ),
    ),
    "review_diff_query": PromptSpec(
        task="review_diff_query",
        version="review-diff-query-v1",
        output_mode="json",
        description="Answer an analyst question about differences between a baseline world and a target world.",
        system_prompt=(
            "Answer the analyst question using only the structured baseline-vs-target evidence. "
            "Return compact JSON only with answer, evidence, follow-up, and confidence notes."
        ),
        expected_keys=(
            "answer",
            "evidence",
            "follow_up",
            "confidence_notes",
        ),
    ),
    "session_review": PromptSpec(
        task="session_review",
        version="session-review-v1",
        output_mode="json",
        description="Summarize a session containing multiple world runs and identify the most decision-relevant contrasts.",
        system_prompt=(
            "Summarize a session of multiple simulation worlds. Return compact JSON only with a headline, summary, key findings, and recommended next comparisons."
        ),
        expected_keys=(
            "headline",
            "executive_summary",
            "key_findings",
            "decision_implications",
        ),
    ),
}


def get_prompt_spec(task: str) -> PromptSpec:
    return PROMPT_SPECS.get(task, PROMPT_SPECS["thought"])


def get_prompt_version(task: str) -> str:
    return get_prompt_spec(task).version


def get_prompt_system_instruction(task: str) -> str:
    return get_prompt_spec(task).system_instruction()


def get_prompt_meta(task: str) -> dict[str, Any]:
    return get_prompt_spec(task).meta()


def build_prompt_contract(task: str, sections: list[tuple[str, str]]) -> str:
    spec = get_prompt_spec(task)
    blocks = [
        "[PROMPT_CONTRACT]",
        f"task={spec.task}",
        f"prompt_version={spec.version}",
        f"output_mode={spec.output_mode}",
    ]
    if spec.expected_keys:
        blocks.append(f"expected_keys={', '.join(spec.expected_keys)}")
    for label, value in sections:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        blocks.extend((f"[{label.upper()}]", cleaned))
    return "\n".join(blocks)
