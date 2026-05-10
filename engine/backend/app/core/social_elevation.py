"""Low-cost social elevation helpers for 2.5D / 4D semantics."""
from __future__ import annotations

from typing import Any, Dict, List

from app.models.cell import Cell

DEFAULT_Z_MODE = "hybrid"
DEFAULT_Z_WEIGHT = 0.08


def refresh_social_elevation(
    cells: List[Cell],
    *,
    current_t: float,
    engine_params: Dict[str, Any] | None = None,
) -> List[Cell]:
    params = dict(engine_params or {})
    z_mode = str(params.get("z_mode", DEFAULT_Z_MODE)).strip() or DEFAULT_Z_MODE
    z_weight = max(0.0, float(params.get("z_weight", DEFAULT_Z_WEIGHT)))
    z_scale = max(0.1, float(params.get("z_scale", 12.0)))

    max_energy = max((float(cell.energy) for cell in cells), default=1.0)
    max_long_memory = max((len(cell.long_memory) for cell in cells), default=1)
    max_relationships = max((len(cell.relationship_state) for cell in cells), default=1)

    out: List[Cell] = []
    for cell in cells:
        z_value = compute_social_elevation(
            cell,
            z_mode=z_mode,
            z_scale=z_scale,
            max_energy=max_energy,
            max_long_memory=max_long_memory,
            max_relationships=max_relationships,
        )
        action_state = dict(cell.action_state)
        action_state["z_mode"] = z_mode
        action_state["z_weight"] = z_weight
        action_state["z_scale"] = z_scale
        action_state["social_elevation"] = z_value
        action_state["social_elevation_t"] = float(current_t)
        out.append(cell.copy(z=z_value, action_state=action_state))
    return out


def compute_social_elevation(
    cell: Cell,
    *,
    z_mode: str,
    z_scale: float,
    max_energy: float,
    max_long_memory: int,
    max_relationships: int,
) -> float:
    energy_norm = _clip01(float(cell.energy) / max(max_energy, 1.0))
    memory_norm = _clip01(len(cell.long_memory) / max(1, max_long_memory))
    relationship_norm = _clip01(len(cell.relationship_state) / max(1, max_relationships))
    zone_norm = _clip01((float(cell.zone_influence) - 0.5) / 1.5)
    policy_norm = _clip01(float(cell.action_state.get("policy_sensitivity", 0.5)))
    cooperation_norm = _clip01(float(cell.action_state.get("cooperation_bias", 0.5)))
    resource_norm = _clip01(float(cell.action_state.get("resource_bias", 0.5)))
    risk_norm = _clip01(float(cell.action_state.get("risk_tolerance", 0.5)))

    if z_mode == "flat":
        base = 0.0
    elif z_mode == "wealth":
        base = 0.72 * energy_norm + 0.28 * resource_norm
    elif z_mode == "influence":
        base = 0.4 * zone_norm + 0.25 * relationship_norm + 0.2 * memory_norm + 0.15 * cooperation_norm
    elif z_mode == "policy":
        base = 0.65 * policy_norm + 0.35 * zone_norm
    elif z_mode == "memory":
        base = 0.7 * memory_norm + 0.3 * relationship_norm
    else:
        base = (
            0.28 * energy_norm
            + 0.2 * zone_norm
            + 0.18 * policy_norm
            + 0.14 * memory_norm
            + 0.1 * relationship_norm
            + 0.06 * cooperation_norm
            + 0.04 * risk_norm
        )

    return round(_clip01(base) * z_scale, 4)


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
