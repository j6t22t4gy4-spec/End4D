"""Interaction quality scoring for cluster and ideology formation."""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from app.core.coordinates import cosine_similarity
from app.models.cell import Cell


def evaluate_interaction_quality(cell: Cell, neighbors: List[Cell]) -> Dict[str, float | str | int]:
    if not neighbors:
        return {
            "quality_score": 0.0,
            "thought_similarity": 0.0,
            "worldview_similarity": 0.0,
            "energy_stability": 0.0,
            "role_diversity": 0.0,
            "cluster_signal": "isolated",
            "neighbor_count": 0,
        }

    thought_sims = [cosine_similarity(cell.thought_vec, n.thought_vec) for n in neighbors]
    worldview_sims = [cosine_similarity(cell.worldview_vec, n.worldview_vec) for n in neighbors]
    energy_diffs = [abs(float(cell.energy) - float(n.energy)) for n in neighbors]
    distinct_roles = len({(n.role_label or n.role_key or "agent") for n in neighbors})

    thought_similarity = float(np.mean(thought_sims))
    worldview_similarity = float(np.mean(worldview_sims))
    energy_stability = max(0.0, 1.0 - min(float(np.mean(energy_diffs)) / 60.0, 1.0))
    role_diversity = min(1.0, distinct_roles / max(len(neighbors), 1))

    quality_score = (
        0.38 * max(0.0, thought_similarity)
        + 0.34 * max(0.0, worldview_similarity)
        + 0.18 * energy_stability
        + 0.10 * role_diversity
    )

    if quality_score >= 0.72 and worldview_similarity >= 0.25:
        cluster_signal = "cohesive_cluster"
    elif quality_score >= 0.52:
        cluster_signal = "emergent_cluster"
    elif worldview_similarity < -0.05 or thought_similarity < -0.05:
        cluster_signal = "ideological_tension"
    else:
        cluster_signal = "weak_signal"

    return {
        "quality_score": float(max(0.0, min(1.0, quality_score))),
        "thought_similarity": thought_similarity,
        "worldview_similarity": worldview_similarity,
        "energy_stability": energy_stability,
        "role_diversity": role_diversity,
        "cluster_signal": cluster_signal,
        "neighbor_count": len(neighbors),
    }
