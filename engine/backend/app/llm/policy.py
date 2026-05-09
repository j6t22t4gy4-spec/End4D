"""LLM-backed policy event interpretation for agents."""
from __future__ import annotations

import json
from typing import Dict, Iterable, List

import numpy as np

from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.llm.chat_runtime import generate_reasoning_texts
from app.llm.prompt_engineering import build_policy_prompt
from app.models.cell import Cell


def apply_policy_interpretation(
    cells: List[Cell],
    *,
    event_type: str,
    payload: Dict,
) -> List[Cell]:
    target_roles = {str(role).strip() for role in payload.get("target_roles") or [] if str(role).strip()}
    selected: List[Cell] = []
    indices: List[int] = []
    for idx, cell in enumerate(cells):
        role = (cell.role_label or cell.role_key or "agent").strip()
        if target_roles and role not in target_roles and cell.role_key not in target_roles:
            continue
        selected.append(cell)
        indices.append(idx)

    if not selected:
        return [cell.copy() for cell in cells]

    prompts = [build_policy_prompt(cell, event_type, payload) for cell in selected]
    generated = generate_reasoning_texts(prompts, task="policy")

    out = [cell.copy() for cell in cells]
    for idx, cell, text in zip(indices, selected, generated):
        out[idx] = _apply_policy_to_cell(cell, text, payload)
    return out


def _apply_policy_to_cell(cell: Cell, text: str, payload: Dict) -> Cell:
    interp = _parse_policy_state(text, payload)
    ev = cell.emotion_vec.copy().astype(np.float32)
    emotion_index = int(interp["emotion_index"])
    if 0 <= emotion_index < ev.shape[0]:
        ev[emotion_index] = np.clip(ev[emotion_index] + float(interp["emotion_delta"]), -1.0, 1.0)

    current_action = dict(cell.action_state)
    current_action["cooperation_bias"] = _clip01(
        float(current_action.get("cooperation_bias", 0.5)) + float(interp["cooperation_shift"])
    )
    current_action["policy_sensitivity"] = _clip01(
        float(current_action.get("policy_sensitivity", 0.5)) + float(interp["policy_sensitivity_shift"])
    )
    current_action["last_policy_summary"] = str(interp["memory_summary"])

    entry = memory_entry(
        t=float(cell.t),
        kind="policy_interpretation",
        summary=str(interp["memory_summary"]),
        importance=float(interp["importance"]),
        source="llm.policy",
        payload=dict(interp),
        tags=["llm", "policy", str(payload.get("name") or event_type)],
    )
    behavior = behavior_event(
        t=float(cell.t),
        event_type="policy_interpretation",
        source="llm.policy",
        summary=str(interp["memory_summary"]),
        quality_score=float(interp["importance"]),
        payload=dict(interp),
    )
    return append_memory(
        cell.copy(emotion_vec=ev, action_state=current_action),
        entry,
        behavior=behavior,
        promote=float(interp["importance"]) >= 0.72,
    )


def _parse_policy_state(text: str, payload: Dict) -> Dict[str, float | str | int]:
    parsed = _extract_json_object(text)
    intensity = _clip01(float(payload.get("intensity", 0.6)))
    default_summary = f"policy event interpreted: {payload.get('name') or payload.get('summary') or 'policy shift'}"
    if parsed is None:
        return {
            "memory_summary": default_summary,
            "emotion_index": 2,
            "emotion_delta": 0.18 * intensity,
            "cooperation_shift": -0.05 + 0.1 * intensity,
            "policy_sensitivity_shift": 0.16 * intensity,
            "importance": 0.72,
        }
    return {
        "memory_summary": str(parsed.get("memory_summary") or default_summary),
        "emotion_index": _bounded_int(parsed.get("emotion_index"), default=2, low=0, high=7),
        "emotion_delta": _bounded_signed_float(parsed.get("emotion_delta"), default=0.18 * intensity),
        "cooperation_shift": _bounded_signed_float(parsed.get("cooperation_shift"), default=0.05 * intensity),
        "policy_sensitivity_shift": _bounded_signed_float(
            parsed.get("policy_sensitivity_shift"),
            default=0.14 * intensity,
        ),
        "importance": _clip01(float(parsed.get("importance", 0.72))),
    }


def _extract_json_object(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
    return None


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bounded_int(value, *, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except Exception:
        return default


def _bounded_signed_float(value, *, default: float) -> float:
    try:
        return max(-1.0, min(1.0, float(value)))
    except Exception:
        return default
