"""Structured policy event semantics for long-run simulation."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

import numpy as np

from app.models.cell import Cell
from app.models.world import NutrientEvent


def normalize_policy_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    intensity = _clip01(float(payload.get("intensity", 0.6)))
    duration_steps = max(1, int(payload.get("duration_steps", 24)))
    target_roles = _clean_list(payload.get("target_roles"))
    target_zones = _clean_list(payload.get("target_zones"))
    scope = str(payload.get("scope") or ("world" if not target_zones else "zone")).strip() or "world"
    effect_profile = str(payload.get("effect_profile") or "mixed").strip() or "mixed"
    energy_delta = float(payload.get("energy_delta_per_step", 0.18 * intensity))
    cooperation_delta = float(payload.get("cooperation_delta_per_step", 0.012 * intensity))
    sensitivity_delta = float(payload.get("policy_sensitivity_delta_per_step", 0.018 * intensity))
    mobility_delta = float(payload.get("mobility_delta_per_step", -0.006 * intensity))
    emotion_delta = float(payload.get("emotion_delta_per_step", 0.02 * intensity))
    mechanism_channels = {
        "resource": round(abs(energy_delta) * 0.9 + intensity * 0.1, 3),
        "cooperation": round(abs(cooperation_delta) * 8.0 + intensity * 0.08, 3),
        "policy_sensitivity": round(abs(sensitivity_delta) * 8.0 + intensity * 0.1, 3),
        "mobility": round(abs(mobility_delta) * 10.0 + intensity * 0.06, 3),
        "emotion": round(abs(emotion_delta) * 10.0 + intensity * 0.07, 3),
    }
    dominant_channel = max(mechanism_channels.items(), key=lambda item: (float(item[1]), str(item[0])))[0]
    return {
        "name": str(payload.get("name") or "policy_shift"),
        "summary": str(payload.get("summary") or "policy intervention"),
        "scope": scope,
        "intensity": intensity,
        "duration_steps": duration_steps,
        "target_roles": target_roles,
        "target_zones": target_zones,
        "effect_profile": effect_profile,
        "energy_delta_per_step": energy_delta,
        "cooperation_delta_per_step": cooperation_delta,
        "policy_sensitivity_delta_per_step": sensitivity_delta,
        "mobility_delta_per_step": mobility_delta,
        "emotion_index": _bounded_int(payload.get("emotion_index"), default=5, low=0, high=7),
        "emotion_delta_per_step": emotion_delta,
        "mechanism_channels": mechanism_channels,
        "dominant_channel": dominant_channel,
    }


def active_policy_payloads(
    events: Iterable[NutrientEvent],
    *,
    current_t: float,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for event in events:
        if event.event_type != "policy_shift":
            continue
        payload = normalize_policy_payload(dict(event.payload))
        start_t = float(event.t)
        end_t = start_t + float(payload["duration_steps"])
        if start_t <= float(current_t) < end_t:
            payload["start_t"] = start_t
            payload["end_t"] = end_t
            out.append(payload)
    return out


def apply_active_policies(
    cells: List[Cell],
    *,
    current_t: float,
    events: Iterable[NutrientEvent],
) -> List[Cell]:
    payloads = active_policy_payloads(events, current_t=current_t)
    if not payloads:
        return [cell.copy() for cell in cells]

    out: List[Cell] = []
    for cell in cells:
        updated = cell.copy()
        applied: List[str] = []
        for payload in payloads:
            if not _matches_policy_target(updated, payload):
                continue
            updated = _apply_policy_effect(updated, payload, current_t=current_t)
            applied.append(str(payload["name"]))
        if applied:
            action_state = dict(updated.action_state)
            action_state["active_policy_names"] = applied
            updated = updated.copy(action_state=action_state)
        out.append(updated)
    return out


def _matches_policy_target(cell: Cell, payload: Dict[str, Any]) -> bool:
    target_roles = {str(item).strip() for item in payload.get("target_roles") or [] if str(item).strip()}
    target_zones = {str(item).strip() for item in payload.get("target_zones") or [] if str(item).strip()}
    role = (cell.role_label or cell.role_key or "agent").strip()
    if target_roles and role not in target_roles and cell.role_key not in target_roles:
        return False
    if target_zones and (cell.zone_id or "").strip() not in target_zones:
        return False
    return True


def _apply_policy_effect(cell: Cell, payload: Dict[str, Any], *, current_t: float) -> Cell:
    intensity = _clip01(float(payload.get("intensity", 0.6)))
    zone_multiplier = max(0.5, float(cell.zone_influence))
    effect_profile = str(payload.get("effect_profile") or "mixed")
    energy_delta = float(payload.get("energy_delta_per_step", 0.0)) * zone_multiplier
    coop_delta = float(payload.get("cooperation_delta_per_step", 0.0))
    sensitivity_delta = float(payload.get("policy_sensitivity_delta_per_step", 0.0))
    mobility_delta = float(payload.get("mobility_delta_per_step", 0.0))
    if effect_profile == "restrictive":
        energy_delta *= -0.4
        coop_delta *= -0.7
        mobility_delta = min(mobility_delta, -abs(mobility_delta) - 0.01 * intensity)
    elif effect_profile == "stimulus":
        energy_delta *= 1.5
        coop_delta *= 1.2
        sensitivity_delta *= 0.8

    ev = cell.emotion_vec.copy().astype(np.float32)
    emotion_index = _bounded_int(payload.get("emotion_index"), default=5, low=0, high=7)
    ev[emotion_index] = np.clip(
        float(ev[emotion_index]) + float(payload.get("emotion_delta_per_step", 0.0)) * zone_multiplier,
        -1.0,
        1.0,
    )

    action_state = dict(cell.action_state)
    action_state["cooperation_bias"] = _clip01(float(action_state.get("cooperation_bias", 0.5)) + coop_delta)
    action_state["policy_sensitivity"] = _clip01(
        float(action_state.get("policy_sensitivity", 0.5)) + sensitivity_delta
    )
    action_state["mobility_bias"] = _clip01(float(action_state.get("mobility_bias", 0.5)) + mobility_delta)
    action_state["policy_field_t"] = float(current_t)
    action_state["policy_field_scope"] = str(payload.get("scope") or "world")
    action_state["policy_field_profile"] = str(payload.get("effect_profile") or "mixed")
    action_state["policy_field_dominant_channel"] = str(payload.get("dominant_channel") or "resource")
    action_state["policy_field_channels"] = dict(payload.get("mechanism_channels") or {})

    return cell.copy(
        energy=max(0.0, float(cell.energy) + energy_delta),
        emotion_vec=ev,
        action_state=action_state,
    )


def _clean_list(value: Any) -> List[str]:
    return [str(item).strip() for item in value or [] if str(item).strip()]


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _bounded_int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except Exception:
        return default
