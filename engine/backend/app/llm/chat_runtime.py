"""Provider-agnostic LLM runtime for engine cognition tasks."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Iterable, List

from app.core.settings import (
    get_llm_api_key,
    get_llm_base_url,
    get_llm_chat_enabled,
    get_llm_max_prompts_per_task,
    get_llm_model,
    get_llm_provider,
    get_llm_strict_mode,
    get_llm_temperature,
    get_llm_timeout_s,
)
from app.llm.prompt_registry import get_prompt_meta, get_prompt_system_instruction


def generate_reasoning_texts(prompts: Iterable[str], *, task: str) -> List[str]:
    return generate_reasoning_batch(prompts, task=task)["texts"]


def generate_reasoning_batch(prompts: Iterable[str], *, task: str) -> dict[str, Any]:
    items = [str(prompt) for prompt in prompts]
    if not items:
        return {
            "texts": [],
            "meta": {
                "task": task,
                "enabled": get_llm_chat_enabled(),
                "provider": get_llm_provider(),
                "model": get_llm_model(),
                "prompt_meta": get_prompt_meta(task),
                "prompt_count_in": 0,
                "prompt_count_sent": 0,
                "used_fallback": False,
                "fallback_reason": "",
            },
        }
    if not get_llm_chat_enabled():
        return {
            "texts": items,
            "meta": {
                "task": task,
                "enabled": False,
                "provider": get_llm_provider(),
                "model": get_llm_model(),
                "prompt_meta": get_prompt_meta(task),
                "prompt_count_in": len(items),
                "prompt_count_sent": 0,
                "used_fallback": True,
                "fallback_reason": "llm_disabled",
            },
        }

    provider = get_llm_provider()
    max_prompts = get_llm_max_prompts_per_task()
    active_items = items[:max_prompts]
    skipped_items = items[max_prompts:]
    meta = {
        "task": task,
        "enabled": True,
        "provider": provider,
        "model": get_llm_model(),
        "prompt_meta": get_prompt_meta(task),
        "prompt_count_in": len(items),
        "prompt_count_sent": len(active_items),
        "used_fallback": bool(skipped_items),
        "fallback_reason": "global_prompt_cap" if skipped_items else "",
        "strict_mode": get_llm_strict_mode(),
    }
    try:
        if provider in ("openai", "openai-compatible"):
            generated = _openai_chat_batch(active_items, task=task)
            return {"texts": generated + skipped_items, "meta": meta}
        if provider == "ollama":
            generated = _ollama_chat_batch(active_items, task=task)
            return {"texts": generated + skipped_items, "meta": meta}
    except Exception as exc:
        meta["used_fallback"] = True
        meta["fallback_reason"] = f"provider_error:{type(exc).__name__}"
        raise RuntimeError(meta["fallback_reason"]) from exc
    meta["used_fallback"] = True
    meta["fallback_reason"] = "provider_stub"
    return {"texts": items, "meta": meta}


def _openai_chat_batch(prompts: List[str], *, task: str) -> List[str]:
    base_url = get_llm_base_url() or "https://api.openai.com/v1"
    api_key = get_llm_api_key()
    model = get_llm_model()
    temperature = get_llm_temperature()
    timeout = get_llm_timeout_s(task)
    retries = 0 if get_llm_strict_mode() == "adaptive" else 1
    out: List[str] = []
    for prompt in prompts:
        body = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": get_prompt_system_instruction(task)},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        data = _post_json(
            f"{base_url}/chat/completions",
            body,
            headers=headers,
            timeout=timeout,
            retries=retries,
        )
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
    timeout = get_llm_timeout_s(task)
    retries = 0 if get_llm_strict_mode() == "adaptive" else 1
    out: List[str] = []
    for prompt in prompts:
        body = {
            "model": model,
            "prompt": f"{get_prompt_system_instruction(task)}\n\n{prompt}",
            "stream": False,
            "options": {"temperature": temperature},
        }
        data = _post_json(
            f"{base_url}/api/generate",
            body,
            headers={"Content-Type": "application/json"},
            timeout=timeout,
            retries=retries,
        )
        out.append(str((data or {}).get("response") or prompt))
    return out


def _post_json(url: str, body: dict, *, headers: dict, timeout: float, retries: int = 0) -> dict:
    last_error: Exception | None = None
    for _attempt in range(retries + 1):
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
            return json.loads(raw or "{}")
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="ignore")
            last_error = RuntimeError(f"LLM request failed: {exc.code} {raw[:240]}")
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"LLM request failed: {exc.reason}")
    if last_error is not None:
        raise last_error
    return {}
