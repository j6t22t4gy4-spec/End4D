"""Organic4D Engine — 5대 규칙 로직 (Phase 1.4 + Phase 6 융합 연동).

CONCEPT §4: 성장, 분열, 사멸, 융합, 돌연변이
ARCHITECTURE_CHECKLIST 3.1~3.5, 4.4: 융합 Thought cosine ≥ 0.7
Emotion 갱신은 core/emotion.py (매 t), Thought/Worldview는 llm/ + graph/nodes
"""
from __future__ import annotations

from typing import List
import uuid

import numpy as np

from app.models.cell import Cell
from app.core.coordinates import distance_4d, cosine_similarity
from app.core.memory_store import merge_memory_fields
from app.core.spatial_index import SpatialHashGrid


# 기본 상수
DIVISION_ENERGY_THRESHOLD = 100.0
DEATH_ENERGY_THRESHOLD = 0.0
FUSION_DISTANCE_THRESHOLD = 2.0
FUSION_THOUGHT_SIM_THRESHOLD = 0.7
FUSION_WORLDVIEW_SIM_THRESHOLD = 0.5
MUTATION_RATE = 0.05


def _action_float(cell: Cell, key: str, default: float) -> float:
    try:
        value = float(cell.action_state.get(key, default))
    except Exception:
        return default
    return max(0.0, min(1.0, value))


def _mutate_vector(vec: np.ndarray, rate: float = MUTATION_RATE) -> np.ndarray:
    """벡터에 작은 랜덤 변이 적용 (돌연변이)."""
    out = vec.copy()
    mask = np.random.random(vec.shape) < rate
    out[mask] += np.random.randn(np.sum(mask)) * 0.1
    return np.clip(out, -1.0, 1.0)


def apply_growth(
    cells: List[Cell],
    nutrient_per_step: float = 1.0,
) -> List[Cell]:
    """성장: 영양분 흡수 → 에너지 증가 (CONCEPT §4)."""
    out: List[Cell] = []
    for cell in cells:
        resource_bias = _action_float(cell, "resource_bias", 0.5)
        risk_tolerance = _action_float(cell, "risk_tolerance", 0.5)
        # Neutral action_state should preserve the original growth rule.
        gain = nutrient_per_step * max(0.4, 0.7 + 0.6 * resource_bias)
        upkeep = max(0.0, 0.35 * (risk_tolerance - 0.5))
        out.append(cell.copy(energy=cell.energy + gain - upkeep))
    return out


def apply_division(
    cells: List[Cell],
    energy_threshold: float = DIVISION_ENERGY_THRESHOLD,
    current_t: float = 0.0,
) -> List[Cell]:
    """분열: 에너지 > 임계치 → 1→2, 유전자·벡터 변이 (CONCEPT §4)."""
    result: List[Cell] = []
    for cell in cells:
        if cell.energy <= energy_threshold:
            result.append(cell)
            continue

        risk_tolerance = _action_float(cell, "risk_tolerance", 0.5)
        local_threshold = energy_threshold * max(0.7, 1.08 - 0.32 * risk_tolerance)
        if cell.energy <= local_threshold:
            result.append(cell)
            continue

        half_energy = cell.energy / 2.0
        offset = 0.5

        child1 = cell.copy(
            cell_id=str(uuid.uuid4()),
            energy=half_energy,
            x=cell.x - offset,
            gene_vec=_mutate_vector(cell.gene_vec),
            emotion_vec=_mutate_vector(cell.emotion_vec),
            thought_vec=_mutate_vector(cell.thought_vec),
            worldview_vec=_mutate_vector(cell.worldview_vec),
        )
        child2 = cell.copy(
            cell_id=str(uuid.uuid4()),
            energy=half_energy,
            x=cell.x + offset,
            gene_vec=_mutate_vector(cell.gene_vec),
            emotion_vec=_mutate_vector(cell.emotion_vec),
            thought_vec=_mutate_vector(cell.thought_vec),
            worldview_vec=_mutate_vector(cell.worldview_vec),
        )
        result.extend([child1, child2])
    return result


def apply_death(
    cells: List[Cell],
    energy_threshold: float = DEATH_ENERGY_THRESHOLD,
    nutrient_to_neighbors: float = 5.0,
) -> List[Cell]:
    """사멸: 에너지=0 → 죽음 + 주변에 영양분 분배 (CONCEPT §4)."""
    alive = [c for c in cells if c.energy > energy_threshold]
    dead = [c for c in cells if c.energy <= energy_threshold]

    if not dead:
        return alive

    spatial_index = SpatialHashGrid(alive, cell_size=FUSION_DISTANCE_THRESHOLD)
    for dead_cell in dead:
        if not alive:
            break
        candidates = spatial_index.nearest_candidates(
            dead_cell,
            k=min(3, len(alive)),
            initial_radius=FUSION_DISTANCE_THRESHOLD,
        )
        dists = [(distance_4d(dead_cell, a), a) for a in candidates]
        dists.sort(key=lambda x: x[0])
        k = min(3, len(alive))
        share = nutrient_to_neighbors / k
        for _, neighbor in dists[:k]:
            idx = next(i for i, c in enumerate(alive) if c.cell_id == neighbor.cell_id)
            current = alive[idx]
            alive[idx] = current.copy(energy=current.energy + share, cell_id=current.cell_id)

    return alive


def apply_fusion(
    cells: List[Cell],
    distance_threshold: float = FUSION_DISTANCE_THRESHOLD,
    thought_sim_threshold: float = FUSION_THOUGHT_SIM_THRESHOLD,
    worldview_sim_threshold: float = FUSION_WORLDVIEW_SIM_THRESHOLD,
    current_t: float = 0.0,
) -> List[Cell]:
    """융합: 가까운 거리 + Thought 0.7+ + Worldview 호환 → 합체 (CONCEPT §4)."""
    if len(cells) < 2:
        return cells

    used: set[str] = set()
    result: List[Cell] = []
    index_by_id = {cell.cell_id: idx for idx, cell in enumerate(cells)}
    spatial_index = SpatialHashGrid(cells, cell_size=distance_threshold)

    for i, c1 in enumerate(cells):
        if c1.cell_id in used:
            continue

        best_j = -1
        best_sim = -1.0

        for c2 in spatial_index.candidate_cells(c1, distance_threshold):
            j = index_by_id.get(c2.cell_id, -1)
            if i >= j or c2.cell_id in used:
                continue

            d = distance_4d(c1, c2)
            if d > distance_threshold:
                continue

            thought_sim = cosine_similarity(c1.thought_vec, c2.thought_vec)
            worldview_sim = cosine_similarity(c1.worldview_vec, c2.worldview_vec)
            coop_bias = (
                _action_float(c1, "cooperation_bias", 0.5)
                + _action_float(c2, "cooperation_bias", 0.5)
            ) / 2.0
            local_thought_threshold = max(0.52, thought_sim_threshold - 0.16 * (coop_bias - 0.5))

            if thought_sim >= local_thought_threshold and worldview_sim >= worldview_sim_threshold:
                if thought_sim > best_sim:
                    best_sim = thought_sim
                    best_j = j

        if best_j >= 0:
            c2 = cells[best_j]
            used.add(c1.cell_id)
            used.add(c2.cell_id)
            merged_memory = merge_memory_fields(c1, c2)

            merged = c1.copy(
                cell_id=str(uuid.uuid4()),
                x=(c1.x + c2.x) / 2,
                y=(c1.y + c2.y) / 2,
                z=(c1.z + c2.z) / 2,
                energy=c1.energy + c2.energy,
                gene_vec=_mutate_vector((c1.gene_vec + c2.gene_vec) / 2),
                emotion_vec=_mutate_vector((c1.emotion_vec + c2.emotion_vec) / 2),
                thought_vec=_mutate_vector((c1.thought_vec + c2.thought_vec) / 2),
                worldview_vec=_mutate_vector((c1.worldview_vec + c2.worldview_vec) / 2),
                memory=merged_memory["memory"],
                short_memory=merged_memory["short_memory"],
                long_memory=merged_memory["long_memory"],
                behavior_log=merged_memory["behavior_log"],
            )
            result.append(merged)
        else:
            result.append(c1)

    return result


def apply_mutation(
    cells: List[Cell],
    rate: float = MUTATION_RATE,
) -> List[Cell]:
    """돌연변이: 유전자 등 추가 변이. 감정은 core/emotion 규칙이 매 t 담당."""
    return [
        cell.copy(
            gene_vec=_mutate_vector(cell.gene_vec, rate),
        )
        for cell in cells
    ]
