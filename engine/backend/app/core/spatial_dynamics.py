"""Spatial drift and neighbor-sensitive movement for the 2D social field."""
from __future__ import annotations

import hashlib
import math
from typing import Any, Dict, List

import numpy as np

from app.core.coordinates import cosine_similarity, distance_4d
from app.core.spatial_index import SpatialHashGrid
from app.models.cell import Cell

DEFAULT_NEIGHBOR_RADIUS = 4.5
DEFAULT_BASE_STEP = 0.24


def update_spatial_positions(
    cells: List[Cell],
    *,
    current_t: float,
    engine_params: Dict[str, Any] | None = None,
) -> List[Cell]:
    """Move cells through the field so x/y affects who influences whom over time."""
    if len(cells) <= 1:
        return cells

    params = dict(engine_params or {})
    radius = max(1.5, float(params.get("interaction_radius", DEFAULT_NEIGHBOR_RADIUS)))
    base_step = max(0.04, float(params.get("spatial_step_size", DEFAULT_BASE_STEP)))
    alignment_weight = max(0.0, float(params.get("alignment_pull_weight", 0.34)))
    tension_weight = max(0.0, float(params.get("tension_push_weight", 0.26)))
    crowding_weight = max(0.0, float(params.get("crowding_push_weight", 0.18)))
    zone_weight = max(0.0, float(params.get("zone_cluster_weight", 0.14)))
    exploration_weight = max(0.0, float(params.get("exploration_weight", 0.09)))
    boundary_padding = max(2.0, float(params.get("field_boundary_padding", 3.5)))

    grid = SpatialHashGrid(cells, cell_size=radius)
    zone_centroids = _zone_centroids(cells)
    min_x = min(float(cell.x) for cell in cells) - boundary_padding
    max_x = max(float(cell.x) for cell in cells) + boundary_padding
    min_y = min(float(cell.y) for cell in cells) - boundary_padding
    max_y = max(float(cell.y) for cell in cells) + boundary_padding

    out: List[Cell] = []
    for cell in cells:
        mobility = _clip01(float(cell.action_state.get("mobility_bias", 0.4)))
        neighbors = [
            other
            for other in grid.candidate_cells(cell, radius)
            if other.cell_id != cell.cell_id and distance_4d(cell, other, time_weight=0.0) <= radius
        ]
        neighbors.sort(key=lambda other: distance_4d(cell, other, time_weight=0.0))

        net = np.zeros(2, dtype=np.float32)
        local_density = 0.0
        for other in neighbors:
            delta = np.array([other.x - cell.x, other.y - cell.y], dtype=np.float32)
            dist = float(np.linalg.norm(delta))
            if dist <= 1e-6:
                continue
            direction = delta / dist
            proximity = max(0.0, 1.0 - dist / radius)
            thought_sim = cosine_similarity(cell.thought_vec, other.thought_vec)
            worldview_sim = cosine_similarity(cell.worldview_vec, other.worldview_vec)
            alignment = (thought_sim + worldview_sim) / 2.0
            same_zone = (cell.zone_id or "") == (other.zone_id or "")
            zone_factor = 1.0 if same_zone else max(0.3, 1.0 - ((cell.zone_friction + other.zone_friction) / 2.0) * 0.45)

            if alignment >= 0.08:
                net += direction * np.float32(alignment_weight * alignment * proximity * zone_factor)
            elif alignment <= -0.04:
                net -= direction * np.float32(tension_weight * abs(alignment) * (0.55 + proximity))

            if dist < radius * 0.45:
                crowding = 1.0 - (dist / max(radius * 0.45, 1e-6))
                net -= direction * np.float32(crowding_weight * crowding)

            local_density += proximity

        centroid = zone_centroids.get(cell.zone_id or "")
        if centroid is not None:
            toward_zone = np.array([centroid[0] - cell.x, centroid[1] - cell.y], dtype=np.float32)
            zone_dist = float(np.linalg.norm(toward_zone))
            if zone_dist > 1e-6:
                net += (toward_zone / zone_dist) * np.float32(zone_weight * _clip01(float(cell.zone_influence) / 2.0))

        exploration = _deterministic_direction(cell.cell_id, current_t) * np.float32(
            exploration_weight * (0.25 + mobility) * (1.25 if not neighbors else 0.65)
        )
        move = net + exploration
        move_norm = float(np.linalg.norm(move))
        max_step = base_step * (0.35 + mobility) * (1.0 + min(0.55, local_density * 0.12))
        if move_norm > max_step and move_norm > 1e-6:
            move = move / np.float32(move_norm) * np.float32(max_step)

        next_x = min(max_x, max(min_x, float(cell.x + move[0])))
        next_y = min(max_y, max(min_y, float(cell.y + move[1])))
        shift = math.dist((float(cell.x), float(cell.y)), (next_x, next_y))

        action_state = dict(cell.action_state)
        action_state["last_spatial_shift"] = round(shift, 4)
        action_state["last_spatial_t"] = float(current_t)
        action_state["local_density"] = round(local_density, 4)
        action_state["mobility_state"] = "drifting" if shift >= 0.02 else "anchored"

        behavior_log = list(cell.behavior_log)
        if shift >= 0.06:
            behavior_log.append(
                {
                    "t": float(current_t),
                    "event_type": "spatial_shift",
                    "summary": f"t={int(current_t)} drift=({next_x - cell.x:.2f},{next_y - cell.y:.2f}) density={local_density:.2f}",
                    "payload": {
                        "dx": round(next_x - cell.x, 4),
                        "dy": round(next_y - cell.y, 4),
                        "density": round(local_density, 4),
                        "neighbor_count": len(neighbors),
                    },
                }
            )
            behavior_log = behavior_log[-40:]

        out.append(
            cell.copy(
                x=next_x,
                y=next_y,
                action_state=action_state,
                behavior_log=behavior_log,
            )
        )
    return out


def _deterministic_direction(cell_id: str, current_t: float) -> np.ndarray:
    digest = hashlib.sha256(f"{cell_id}:{int(current_t)}".encode("utf-8")).digest()
    angle = (int.from_bytes(digest[:4], "big") / 2**32) * math.tau
    return np.array([math.cos(angle), math.sin(angle)], dtype=np.float32)


def _zone_centroids(cells: List[Cell]) -> Dict[str, tuple[float, float]]:
    buckets: Dict[str, List[Cell]] = {}
    for cell in cells:
        zone_id = cell.zone_id or ""
        buckets.setdefault(zone_id, []).append(cell)
    out: Dict[str, tuple[float, float]] = {}
    for zone_id, members in buckets.items():
        out[zone_id] = (
            float(sum(cell.x for cell in members) / len(members)),
            float(sum(cell.y for cell in members) / len(members)),
        )
    return out


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))
