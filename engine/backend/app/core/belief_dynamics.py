"""Belief update dynamics derived from interaction quality and memory."""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from app.models.cell import Cell


def _unit(vec: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vec))
    if norm <= 1e-8:
        return vec.copy()
    return vec / norm


def _alignment_bias(alignment: str) -> float:
    if alignment == "ally":
        return 0.18
    if alignment == "mixed":
        return 0.06
    if alignment == "tension":
        return -0.12
    return 0.0


def apply_belief_update(
    cell: Cell,
    *,
    neighbors: List[Cell],
    quality: Dict[str, float | str | int],
    alignment: str,
) -> Dict[str, object]:
    """Derive a more stable belief shift from repeated interactions."""
    quality_score = float(quality.get("quality_score", 0.0))
    cluster_signal = str(quality.get("cluster_signal") or "weak_signal")
    if not neighbors or quality_score <= 0.0:
        return {
            "thought_vec": cell.thought_vec.copy(),
            "worldview_vec": cell.worldview_vec.copy(),
            "belief_shift": 0.0,
            "belief_summary": "no belief shift",
            "belief_polarity": "stable",
        }

    thought_anchor = np.mean([n.thought_vec for n in neighbors], axis=0)
    worldview_anchor = np.mean([n.worldview_vec for n in neighbors], axis=0)

    long_memory_bias = min(0.18, len(cell.long_memory) / 120.0)
    short_memory_bias = min(0.10, len(cell.short_memory) / 80.0)
    alignment_bias = _alignment_bias(alignment)
    worldview_weight = max(0.0, min(0.24, 0.08 + quality_score * 0.12 + long_memory_bias))
    thought_weight = max(0.0, min(0.28, 0.10 + quality_score * 0.14 + short_memory_bias))

    if alignment == "tension":
        thought_target = -thought_anchor
        worldview_target = -worldview_anchor
        polarity = "counter_alignment"
    else:
        thought_target = thought_anchor
        worldview_target = worldview_anchor
        polarity = "alignment" if alignment == "ally" else "adaptive"

    thought_vec = _unit((1.0 - thought_weight) * cell.thought_vec + thought_weight * thought_target)
    worldview_vec = _unit(
        (1.0 - worldview_weight) * cell.worldview_vec
        + worldview_weight * worldview_target
        + alignment_bias * _unit(worldview_target)
    )
    belief_shift = float(np.linalg.norm(worldview_vec - cell.worldview_vec))
    belief_summary = (
        f"cluster_signal={cluster_signal} alignment={alignment} "
        f"belief_shift={belief_shift:.3f} quality={quality_score:.2f}"
    )
    return {
        "thought_vec": thought_vec,
        "worldview_vec": worldview_vec,
        "belief_shift": belief_shift,
        "belief_summary": belief_summary,
        "belief_polarity": polarity,
    }
