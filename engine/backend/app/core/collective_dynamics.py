"""Collective dynamics layer for role/zone group state and feedback."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from app.core.settings import (
    get_collective_drift_threshold,
    get_collective_fracture_threshold,
    get_collective_influence_scale,
    get_collective_tension_threshold,
)
from app.models.cell import Cell


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.mean(values))


def _safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    return float(np.std(values))


def _vector_norm_mean(vectors: list[np.ndarray]) -> float:
    if not vectors:
        return 0.0
    return float(np.mean([float(np.linalg.norm(vec)) for vec in vectors]))


def _stance_signature(cells: list[Cell]) -> dict[str, float]:
    cooperation = [float(dict(cell.action_state).get("cooperation_bias", 0.0) or 0.0) for cell in cells]
    policy = [float(dict(cell.action_state).get("policy_sensitivity", 0.0) or 0.0) for cell in cells]
    resource = [float(dict(cell.action_state).get("resource_bias", 0.0) or 0.0) for cell in cells]
    mobility = [float(dict(cell.action_state).get("mobility_bias", 0.0) or 0.0) for cell in cells]
    return {
        "cooperation": round(_safe_mean(cooperation), 3),
        "policy": round(_safe_mean(policy), 3),
        "resource": round(_safe_mean(resource), 3),
        "mobility": round(_safe_mean(mobility), 3),
    }


def _pressure_bucket(pressure: float) -> str:
    if pressure >= 0.72:
        return "critical"
    if pressure >= 0.5:
        return "elevated"
    if pressure >= 0.3:
        return "watch"
    return "low"


def collective_context_from_action_state(action_state: dict[str, Any] | None) -> dict[str, float | str | bool]:
    state = dict(action_state or {})
    role_cohesion = _clip01(float(state.get("role_group_cohesion", 0.0) or 0.0))
    role_tension = _clip01(float(state.get("role_group_tension", 0.0) or 0.0))
    role_fracture = _clip01(float(state.get("role_group_fracture_risk", 0.0) or 0.0))
    zone_tension = _clip01(float(state.get("zone_group_tension", 0.0) or 0.0))
    zone_fracture = _clip01(float(state.get("zone_group_fracture_risk", 0.0) or 0.0))
    zone_drift = max(0.0, float(state.get("zone_group_drift_velocity", 0.0) or 0.0))
    pressure = _clip01(float(state.get("collective_pressure", 0.0) or 0.0))
    return {
        "collective_signal": str(state.get("collective_signal") or "stable"),
        "collective_pressure": pressure,
        "pressure_bucket": _pressure_bucket(pressure),
        "role_cohesion": role_cohesion,
        "role_tension": role_tension,
        "role_fracture": role_fracture,
        "zone_tension": zone_tension,
        "zone_fracture": zone_fracture,
        "zone_drift": zone_drift,
        "fracture_alert": role_fracture >= get_collective_fracture_threshold() or zone_fracture >= get_collective_fracture_threshold(),
        "tension_alert": role_tension >= get_collective_tension_threshold() or zone_tension >= get_collective_tension_threshold(),
        "drift_alert": zone_drift >= get_collective_drift_threshold(),
    }


def _collective_deltas(
    *,
    role_cohesion: float,
    role_fracture: float,
    zone_tension: float,
    zone_fracture: float,
    zone_drift: float,
    pressure: float,
) -> dict[str, float]:
    scale = get_collective_influence_scale()
    cooperation_delta = (
        (role_cohesion - 0.5) * 0.09
        - role_fracture * 0.05
        - zone_tension * 0.02
    ) * scale
    policy_delta = (
        zone_tension * 0.045
        + pressure * 0.035
        + zone_fracture * 0.015
    ) * scale
    mobility_delta = (
        zone_drift * 0.06
        + role_fracture * 0.045
        + zone_tension * 0.015
        - role_cohesion * 0.012
    ) * scale
    resource_delta = (
        pressure * 0.03
        + zone_fracture * 0.02
        - role_cohesion * 0.01
    ) * scale
    risk_delta = (
        zone_tension * 0.03
        + role_fracture * 0.04
        + pressure * 0.02
    ) * scale
    return {
        "cooperation_delta": max(-0.22, min(0.22, cooperation_delta)),
        "policy_delta": max(-0.18, min(0.22, policy_delta)),
        "mobility_delta": max(-0.14, min(0.25, mobility_delta)),
        "resource_delta": max(-0.12, min(0.18, resource_delta)),
        "risk_delta": max(-0.12, min(0.18, risk_delta)),
    }


def _group_metrics(
    *,
    group_kind: str,
    group_id: str,
    group_label: str,
    cells: list[Cell],
    prev_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    xs = [float(cell.x) for cell in cells]
    ys = [float(cell.y) for cell in cells]
    zs = [float(cell.z) for cell in cells]
    energies = [float(cell.energy) for cell in cells]
    emotion_norms = [float(np.linalg.norm(cell.emotion_vec)) for cell in cells]
    worldview_norms = [float(np.linalg.norm(cell.worldview_vec)) for cell in cells]
    thought_norms = [float(np.linalg.norm(cell.thought_vec)) for cell in cells]
    policy_exposure = [
        float(dict(cell.action_state).get("policy_sensitivity", 0.0) or 0.0)
        for cell in cells
    ]
    mobility_bias = [
        float(dict(cell.action_state).get("mobility_bias", 0.0) or 0.0)
        for cell in cells
    ]
    spatial_shifts = [
        float(dict(cell.action_state).get("last_spatial_shift", 0.0) or 0.0)
        for cell in cells
    ]
    unique_roles = len({str(cell.role_key or "agent") for cell in cells})
    unique_zones = len({str(cell.zone_id or "zone-0") for cell in cells})
    count = len(cells)

    avg_x = _safe_mean(xs)
    avg_y = _safe_mean(ys)
    avg_z = _safe_mean(zs)
    avg_energy = _safe_mean(energies)

    z_dispersion = _safe_std(zs)
    energy_dispersion = _safe_std(energies)
    emotion_dispersion = _safe_std(emotion_norms)
    worldview_dispersion = _safe_std(worldview_norms)
    thought_density = _safe_mean(thought_norms)

    if group_kind == "role":
        cross_diversity = unique_zones / max(count, 1)
    else:
        cross_diversity = unique_roles / max(count, 1)

    cohesion = _clip01(
        1.0
        - min(
            1.0,
            z_dispersion * 0.42 + worldview_dispersion * 0.22 + emotion_dispersion * 0.16 + cross_diversity * 0.20,
        )
    )
    tension = _clip01(
        min(
            1.0,
            emotion_dispersion * 0.40 + energy_dispersion * 0.20 + worldview_dispersion * 0.16 + cross_diversity * 0.24,
        )
    )
    fracture_risk = _clip01(
        (1.0 - cohesion) * 0.42
        + tension * 0.33
        + cross_diversity * 0.15
        + _safe_mean(spatial_shifts) * 0.10
    )
    polarization = _clip01(
        min(
            1.0,
            worldview_dispersion * 0.40 + z_dispersion * 0.35 + abs(avg_z) * 0.10 + cross_diversity * 0.15,
        )
    )
    pressure = _clip01(fracture_risk * 0.55 + tension * 0.45)

    prev_avg_x = float((prev_entry or {}).get("avg_x", avg_x))
    prev_avg_y = float((prev_entry or {}).get("avg_y", avg_y))
    prev_avg_z = float((prev_entry or {}).get("avg_z", avg_z))
    drift_velocity = float(
        np.linalg.norm(
            np.asarray([avg_x - prev_avg_x, avg_y - prev_avg_y, avg_z - prev_avg_z], dtype=np.float32)
        )
    )

    return {
        "group_kind": group_kind,
        "group_id": group_id,
        "group_label": group_label,
        "count": count,
        "avg_x": round(avg_x, 3),
        "avg_y": round(avg_y, 3),
        "avg_z": round(avg_z, 3),
        "avg_energy": round(avg_energy, 3),
        "cohesion": round(cohesion, 3),
        "tension": round(tension, 3),
        "fracture_risk": round(fracture_risk, 3),
        "polarization": round(polarization, 3),
        "drift_velocity": round(drift_velocity, 3),
        "policy_exposure": round(_safe_mean(policy_exposure), 3),
        "mobility_drift": round(_safe_mean(mobility_bias) * 0.6 + _safe_mean(spatial_shifts) * 0.4, 3),
        "thought_density": round(thought_density, 3),
        "collective_pressure": round(pressure, 3),
        "stance_signature": _stance_signature(cells),
        "cross_diversity": round(cross_diversity, 3),
        "member_ids": [str(cell.cell_id) for cell in cells[:12]],
    }


def _summarize_groups(groups: list[dict[str, Any]]) -> dict[str, Any]:
    if not groups:
        return {
            "count": 0,
            "avg_cohesion": 0.0,
            "avg_tension": 0.0,
            "avg_fracture_risk": 0.0,
            "avg_drift_velocity": 0.0,
            "top_fracturing": [],
            "top_drifting": [],
        }
    return {
        "count": len(groups),
        "avg_cohesion": round(_safe_mean([float(item.get("cohesion", 0.0)) for item in groups]), 3),
        "avg_tension": round(_safe_mean([float(item.get("tension", 0.0)) for item in groups]), 3),
        "avg_fracture_risk": round(_safe_mean([float(item.get("fracture_risk", 0.0)) for item in groups]), 3),
        "avg_drift_velocity": round(_safe_mean([float(item.get("drift_velocity", 0.0)) for item in groups]), 3),
        "top_fracturing": [
            {
                "group_id": str(item.get("group_id") or ""),
                "group_label": str(item.get("group_label") or "group"),
                "fracture_risk": float(item.get("fracture_risk", 0.0)),
                "tension": float(item.get("tension", 0.0)),
            }
            for item in sorted(groups, key=lambda row: (float(row.get("fracture_risk", 0.0)), float(row.get("tension", 0.0))), reverse=True)[:4]
        ],
        "top_drifting": [
            {
                "group_id": str(item.get("group_id") or ""),
                "group_label": str(item.get("group_label") or "group"),
                "drift_velocity": float(item.get("drift_velocity", 0.0)),
                "cohesion": float(item.get("cohesion", 0.0)),
            }
            for item in sorted(groups, key=lambda row: float(row.get("drift_velocity", 0.0)), reverse=True)[:4]
        ],
    }


def compute_group_state(
    cells: list[Cell],
    *,
    current_t: float,
    previous_group_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role_buckets: dict[str, list[Cell]] = defaultdict(list)
    zone_buckets: dict[str, list[Cell]] = defaultdict(list)
    for cell in cells:
        role_buckets[str(cell.role_key or "agent")].append(cell)
        zone_buckets[str(cell.zone_id or "zone-0")].append(cell)

    prev_roles = dict((previous_group_state or {}).get("role_groups") or {})
    prev_zones = dict((previous_group_state or {}).get("zone_groups") or {})

    role_groups = {
        role_key: _group_metrics(
            group_kind="role",
            group_id=role_key,
            group_label=str(cells_for_role[0].role_label or role_key),
            cells=cells_for_role,
            prev_entry=dict(prev_roles.get(role_key) or {}),
        )
        for role_key, cells_for_role in role_buckets.items()
    }
    zone_groups = {
        zone_id: _group_metrics(
            group_kind="zone",
            group_id=zone_id,
            group_label=str(cells_for_zone[0].zone_label or zone_id),
            cells=cells_for_zone,
            prev_entry=dict(prev_zones.get(zone_id) or {}),
        )
        for zone_id, cells_for_zone in zone_buckets.items()
    }

    role_list = list(role_groups.values())
    zone_list = list(zone_groups.values())
    summary = {
        "role": _summarize_groups(role_list),
        "zone": _summarize_groups(zone_list),
    }
    collective_signal = "stable"
    role_fracture = float(summary["role"]["avg_fracture_risk"])
    zone_fracture = float(summary["zone"]["avg_fracture_risk"])
    role_drift = float(summary["role"]["avg_drift_velocity"])
    if role_fracture >= 0.72 or zone_fracture >= 0.72:
        collective_signal = "fracturing"
    elif role_drift >= 0.42 or float(summary["zone"]["avg_drift_velocity"]) >= 0.42:
        collective_signal = "realigning"

    return {
        "t": float(current_t),
        "collective_signal": collective_signal,
        "role_groups": role_groups,
        "zone_groups": zone_groups,
        "summary": summary,
    }


def apply_collective_dynamics(
    cells: list[Cell],
    *,
    current_t: float,
    previous_group_state: dict[str, Any] | None = None,
) -> tuple[list[Cell], dict[str, Any]]:
    group_state = compute_group_state(
        cells,
        current_t=current_t,
        previous_group_state=previous_group_state,
    )
    role_groups = dict(group_state.get("role_groups") or {})
    zone_groups = dict(group_state.get("zone_groups") or {})
    updated: list[Cell] = []

    for cell in cells:
        role_entry = dict(role_groups.get(str(cell.role_key or "agent")) or {})
        zone_entry = dict(zone_groups.get(str(cell.zone_id or "zone-0")) or {})
        action_state = dict(cell.action_state)
        role_cohesion = float(role_entry.get("cohesion", 0.0))
        role_fracture = float(role_entry.get("fracture_risk", 0.0))
        zone_tension = float(zone_entry.get("tension", 0.0))
        zone_drift = float(zone_entry.get("drift_velocity", 0.0))
        zone_fracture = float(zone_entry.get("fracture_risk", 0.0))
        pressure = _clip01(
            role_fracture * 0.34
            + zone_tension * 0.26
            + zone_fracture * 0.20
            + zone_drift * 0.20
        )

        cooperation_bias = float(action_state.get("cooperation_bias", 0.5) or 0.5)
        policy_sensitivity = float(action_state.get("policy_sensitivity", 0.5) or 0.5)
        mobility_bias = float(action_state.get("mobility_bias", 0.5) or 0.5)
        resource_bias = float(action_state.get("resource_bias", 0.5) or 0.5)
        risk_tolerance = float(action_state.get("risk_tolerance", 0.5) or 0.5)
        deltas = _collective_deltas(
            role_cohesion=role_cohesion,
            role_fracture=role_fracture,
            zone_tension=zone_tension,
            zone_fracture=zone_fracture,
            zone_drift=zone_drift,
            pressure=pressure,
        )

        cooperation_bias = _clip01(cooperation_bias + deltas["cooperation_delta"])
        policy_sensitivity = _clip01(policy_sensitivity + deltas["policy_delta"])
        mobility_bias = _clip01(mobility_bias + deltas["mobility_delta"])
        resource_bias = _clip01(resource_bias + deltas["resource_delta"])
        risk_tolerance = _clip01(risk_tolerance + deltas["risk_delta"])
        collective_effect = (
            abs(deltas["cooperation_delta"])
            + abs(deltas["policy_delta"])
            + abs(deltas["mobility_delta"])
            + abs(deltas["resource_delta"])
            + abs(deltas["risk_delta"])
        )
        fracture_alert = role_fracture >= get_collective_fracture_threshold() or zone_fracture >= get_collective_fracture_threshold()
        tension_alert = zone_tension >= get_collective_tension_threshold() or float(role_entry.get("tension", 0.0)) >= get_collective_tension_threshold()
        drift_alert = zone_drift >= get_collective_drift_threshold()

        action_state.update(
            {
                "cooperation_bias": round(cooperation_bias, 4),
                "policy_sensitivity": round(policy_sensitivity, 4),
                "mobility_bias": round(mobility_bias, 4),
                "resource_bias": round(resource_bias, 4),
                "risk_tolerance": round(risk_tolerance, 4),
                "role_group_id": str(role_entry.get("group_id") or cell.role_key),
                "role_group_label": str(role_entry.get("group_label") or cell.role_label or cell.role_key),
                "role_group_cohesion": float(role_entry.get("cohesion", 0.0)),
                "role_group_tension": float(role_entry.get("tension", 0.0)),
                "role_group_fracture_risk": float(role_entry.get("fracture_risk", 0.0)),
                "role_group_drift_velocity": float(role_entry.get("drift_velocity", 0.0)),
                "zone_group_id": str(zone_entry.get("group_id") or cell.zone_id),
                "zone_group_label": str(zone_entry.get("group_label") or cell.zone_label or cell.zone_id),
                "zone_group_cohesion": float(zone_entry.get("cohesion", 0.0)),
                "zone_group_tension": float(zone_entry.get("tension", 0.0)),
                "zone_group_fracture_risk": float(zone_entry.get("fracture_risk", 0.0)),
                "zone_group_drift_velocity": float(zone_entry.get("drift_velocity", 0.0)),
                "collective_pressure": round(pressure, 3),
                "collective_pressure_bucket": _pressure_bucket(pressure),
                "collective_signal": str(group_state.get("collective_signal") or "stable"),
                "collective_updated_t": float(current_t),
                "group_influence_applied": True,
                "fracture_signal_received": bool(fracture_alert),
                "collective_tension_alert": bool(tension_alert),
                "collective_drift_alert": bool(drift_alert),
                "collective_bias_effect": round(collective_effect, 4),
                "collective_delta_cooperation": round(deltas["cooperation_delta"], 4),
                "collective_delta_policy": round(deltas["policy_delta"], 4),
                "collective_delta_mobility": round(deltas["mobility_delta"], 4),
                "collective_delta_resource": round(deltas["resource_delta"], 4),
                "collective_delta_risk": round(deltas["risk_delta"], 4),
            }
        )
        updated.append(cell.copy(action_state=action_state))

    return updated, group_state
