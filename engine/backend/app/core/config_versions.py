"""Simulation configuration version helpers."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List


def build_simulation_config(
    *,
    t_max: float,
    initial_cell_count: int,
    role_catalog: List[str],
    t_step_semantic: str,
    t_step_unit: str,
    nutrient_per_step: float,
    persona_country: str,
    persona_source: str,
    engine_params: Dict[str, Any] | None = None,
    comparison_meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "schema_version": "simulation-config/v1",
        "t_max": float(t_max),
        "initial_cell_count": int(initial_cell_count),
        "role_catalog": list(role_catalog),
        "t_step_semantic": t_step_semantic,
        "t_step_unit": t_step_unit,
        "nutrient_per_step": float(nutrient_per_step),
        "persona_country": persona_country,
        "persona_source": persona_source,
        "engine_params": dict(engine_params or {}),
        "comparison_meta": dict(comparison_meta or {}),
    }


def simulation_config_version(config: Dict[str, Any]) -> str:
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
