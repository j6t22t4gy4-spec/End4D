"""Versioned prompt registry for engine LLM tasks."""
from __future__ import annotations


PROMPT_VERSIONS = {
    "genesis": "genesis-v1",
    "thought": "thought-v1",
    "worldview": "worldview-v1",
    "action": "action-v1",
    "policy": "policy-v1",
    "dialogue": "dialogue-v1",
    "group_deliberation": "group-deliberation-v1",
}


def get_prompt_version(task: str) -> str:
    return PROMPT_VERSIONS.get(task, "unknown")
