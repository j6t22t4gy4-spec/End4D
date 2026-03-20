"""Organic4D Engine — 5대 규칙 로직 (Phase 1.4, LLM 제외).

CONCEPT §4: 성장, 분열, 사멸, 융합, 돌연변이
ARCHITECTURE_CHECKLIST 3.1~3.5
Phase 1: emotion/thought/worldview는 고정 또는 임의 값 사용
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.models.cell import Cell
from app.core.coordinates import distance_4d, cosine_similarity


# 기본 상수
DIVISION_ENERGY_THRESHOLD = 100.0
DEATH_ENERGY_THRESHOLD = 0.0
FUSION_DISTANCE_THRESHOLD = 2.0
FUSION_THOUGHT_SIM_THRESHOLD = 0.7
FUSION_WORLDVIEW_SIM_THRESHOLD = 0.5
MUTATION_RATE = 0.05


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
    return [
        cell.copy(energy=cell.energy + nutrient_per_step)
        for cell in cells
    ]


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

        half_energy = cell.energy / 2.0
        offset = 0.5

        child1 = cell.copy(
            energy=half_energy,
            x=cell.x - offset,
            gene_vec=_mutate_vector(cell.gene_vec),
            emotion_vec=_mutate_vector(cell.emotion_vec),
            thought_vec=_mutate_vector(cell.thought_vec),
            worldview_vec=_mutate_vector(cell.worldview_vec),
        )
        child2 = cell.copy(
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

    for dead_cell in dead:
        if not alive:
            break
        dists = [(distance_4d(dead_cell, a), a) for a in alive]
        dists.sort(key=lambda x: x[0])
        k = min(3, len(alive))
        share = nutrient_to_neighbors / k
        for _, neighbor in dists[:k]:
            idx = next(i for i, c in enumerate(alive) if c.cell_id == neighbor.cell_id)
            alive[idx] = neighbor.copy(energy=neighbor.energy + share, cell_id=neighbor.cell_id)

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

    for i, c1 in enumerate(cells):
        if c1.cell_id in used:
            continue

        best_j = -1
        best_sim = thought_sim_threshold

        for j, c2 in enumerate(cells):
            if i >= j or c2.cell_id in used:
                continue

            d = distance_4d(c1, c2)
            if d > distance_threshold:
                continue

            thought_sim = cosine_similarity(c1.thought_vec, c2.thought_vec)
            worldview_sim = cosine_similarity(c1.worldview_vec, c2.worldview_vec)

            if thought_sim >= thought_sim_threshold and worldview_sim >= worldview_sim_threshold:
                if thought_sim > best_sim:
                    best_sim = thought_sim
                    best_j = j

        if best_j >= 0:
            c2 = cells[best_j]
            used.add(c1.cell_id)
            used.add(c2.cell_id)

            merged = c1.copy(
                x=(c1.x + c2.x) / 2,
                y=(c1.y + c2.y) / 2,
                z=(c1.z + c2.z) / 2,
                energy=c1.energy + c2.energy,
                gene_vec=_mutate_vector((c1.gene_vec + c2.gene_vec) / 2),
                emotion_vec=_mutate_vector((c1.emotion_vec + c2.emotion_vec) / 2),
                thought_vec=_mutate_vector((c1.thought_vec + c2.thought_vec) / 2),
                worldview_vec=_mutate_vector((c1.worldview_vec + c2.worldview_vec) / 2),
                memory=c1.memory + c2.memory,
            )
            result.append(merged)
        else:
            result.append(c1)

    return result


def apply_mutation(
    cells: List[Cell],
    rate: float = MUTATION_RATE,
) -> List[Cell]:
    """돌연변이: 분열/융합 외 추가 변이 (선택 적용)."""
    return [
        cell.copy(
            gene_vec=_mutate_vector(cell.gene_vec, rate),
            emotion_vec=_mutate_vector(cell.emotion_vec, rate),
        )
        for cell in cells
    ]
