"""Provider-agnostic LLM runtime for Thought and Worldview generation."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterable, List

from app.core.settings import (
    get_llm_api_key,
    get_llm_base_url,
    get_llm_chat_enabled,
    get_llm_max_prompts_per_task,
    get_llm_model,
    get_llm_provider,
    get_llm_temperature,
    get_llm_timeout_s,
)


def generate_reasoning_texts(prompts: Iterable[str], *, task: str) -> List[str]:
    items = [str(prompt) for prompt in prompts]
    if not items:
        return []
    if not get_llm_chat_enabled():
        return items

    provider = get_llm_provider()
    max_prompts = get_llm_max_prompts_per_task()
    active_items = items[:max_prompts]
    skipped_items = items[max_prompts:]
    try:
        if provider in ("openai", "openai-compatible"):
            generated = _openai_chat_batch(active_items, task=task)
            return generated + skipped_items
        if provider == "ollama":
            generated = _ollama_chat_batch(active_items, task=task)
            return generated + skipped_items
    except Exception:
        return items
    return items


def _system_prompt(task: str) -> str:
    if task == "genesis":
        return (
            "You design initial conditions for a long-horizon societal simulation. "
            "Return compact JSON only with keys: "
            "t_max, initial_cell_count, role_catalog, rationale, "
            "t_step_semantic, t_step_unit, nutrient_per_step, persona_country, persona_source."
        )
    if task == "action":
        return (
            "You convert an agent state into an action profile for the next simulation interval. "
            "Return compact JSON only with keys: strategy_summary, resource_bias, risk_tolerance, "
            "cooperation_bias, policy_sensitivity, mobility_bias."
        )
    if task == "policy":
        return (
            "You interpret a policy event for one social agent. "
            "Return compact JSON only with keys: memory_summary, emotion_index, emotion_delta, "
            "cooperation_shift, policy_sensitivity_shift, importance."
        )
    if task == "dialogue":
        return (
            "You simulate a compact agent-to-agent dialogue outcome. "
            "Return compact JSON only with keys: summary_a, summary_b, alignment_delta, "
            "tension_delta, cooperation_delta, importance."
        )
    if task == "group_deliberation":
        return (
            "You summarize a group negotiation among social roles in a long-horizon simulation. "
            "Return compact JSON only with keys: stance_summary, cohesion_delta, tension_delta, "
            "coalition_signal, importance."
        )
    if task == "worldview":
        return (
            "You summarize long-term beliefs, social alignment, and durable priorities. "
            "Write compact analytical text that captures ideology, trust structure, and expected behavior."
        )
    return (
        "You summarize immediate strategic thinking for a social agent. "
        "Write compact analytical text about current goals, fears, incentives, and next moves."
    )


def _openai_chat_batch(prompts: List[str], *, task: str) -> List[str]:
    base_url = get_llm_base_url() or "https://api.openai.com/v1"
    api_key = get_llm_api_key()
    model = get_llm_model()
    temperature = get_llm_temperature()
    timeout = get_llm_timeout_s()
    out: List[str] = []
    for prompt in prompts:
        body = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": _system_prompt(task)},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = _post_json(f"{base_url}/chat/completions", body, headers=headers, timeout=timeout)
        content = (
            ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
            if isinstance(data, dict)
            else None
        )
        out.append(str(content or prompt))
    return out


def _ollama_chat_batch(prompts: List[str], *, task: str) -> List[str]:
    base_url = get_llm_base_url() or "http://127.0.0.1:11434"
    model = get_llm_model()
    temperature = get_llm_temperature()
    timeout = get_llm_timeout_s()
    out: List[str] = []
    for prompt in prompts:
        body = {
            "model": model,
            "prompt": f"{_system_prompt(task)}\n\n{prompt}",
            "stream": False,
            "options": {"temperature": temperature},
        }
        data = _post_json(f"{base_url}/api/generate", body, headers={"Content-Type": "application/json"}, timeout=timeout)
        out.append(str((data or {}).get("response") or prompt))
    return out


def _post_json(url: str, body: dict, *, headers: dict, timeout: float) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"LLM request failed: {exc.code} {raw[:240]}")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc.reason}")
    return json.loads(raw or "{}")
