"""Versioned prompt registry for engine LLM tasks."""
from __future__ import annotations


PROMPT_VERSIONS = {
    "genesis": "genesis-v1",
    "thought": "thought-v1",
    "worldview": "worldview-v1",
}


def get_prompt_version(task: str) -> str:
    return PROMPT_VERSIONS.get(task, "unknown")
