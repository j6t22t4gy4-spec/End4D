"""Organic4D Engine — 5대 규칙 단위 테스트 (Phase 1.5)."""
import numpy as np
import pytest

from app.models.cell import Cell
from app.core.rules import (
    apply_growth,
    apply_division,
    apply_death,
    apply_fusion,
    apply_mutation,
    DIVISION_ENERGY_THRESHOLD,
)


def _make_cell(
    x=0.0, y=0.0, z=0.0, t=0.0,
    energy=50.0,
    gene_dim=32,
) -> Cell:
    return Cell(
        x=x, y=y, z=z, t=t,
        energy=energy,
        gene_vec=np.random.randn(gene_dim).astype(np.float32) * 0.1,
        emotion_vec=np.zeros(8),
        thought_vec=np.random.randn(256).astype(np.float32) * 0.1,
        worldview_vec=np.random.randn(384).astype(np.float32) * 0.1,
    )


class TestGrowth:
    """성장: 영양분 흡수 → 에너지 증가."""

    def test_energy_increases(self):
        cell = _make_cell(energy=10.0)
        out = apply_growth([cell], nutrient_per_step=5.0)
        assert len(out) == 1
        assert out[0].energy == 15.0

    def test_multiple_cells(self):
        cells = [_make_cell(energy=i) for i in [10, 20, 30]]
        out = apply_growth(cells, nutrient_per_step=1.0)
        assert [c.energy for c in out] == [11.0, 21.0, 31.0]


class TestDivision:
    """분열: 에너지 > 임계치 → 1→2."""

    def test_no_division_below_threshold(self):
        cell = _make_cell(energy=DIVISION_ENERGY_THRESHOLD - 1)
        out = apply_division([cell])
        assert len(out) == 1
        assert out[0].energy == cell.energy

    def test_division_above_threshold(self):
        cell = _make_cell(energy=150.0)
        out = apply_division([cell])
        assert len(out) == 2
        assert out[0].energy == 75.0
        assert out[1].energy == 75.0
        assert out[0].x != out[1].x

    def test_gene_vec_mutated(self):
        np.random.seed(42)
        cell = _make_cell(energy=200.0)
        out = apply_division([cell])
        assert len(out) == 2
        assert not np.allclose(out[0].gene_vec, out[1].gene_vec)


class TestDeath:
    """사멸: 에너지=0 → 죽음 + 주변에 영양분 분배."""

    def test_dead_removed(self):
        alive = _make_cell(energy=10.0)
        dead = _make_cell(energy=0.0)
        out = apply_death([alive, dead])
        assert len(out) == 1
        assert out[0].cell_id == alive.cell_id

    def test_nutrient_distributed_to_neighbors(self):
        alive = _make_cell(energy=10.0, x=0, y=0, z=0)
        dead = _make_cell(energy=0.0, x=1, y=0, z=0)
        out = apply_death([alive, dead], nutrient_to_neighbors=6.0)
        assert len(out) == 1
        assert out[0].energy > 10.0


class TestFusion:
    """융합: 가까운 거리 + Thought 0.7+ + Worldview 호환."""

    def test_fusion_when_close_and_similar(self):
        vec = np.random.randn(256).astype(np.float32) * 0.1
        vec = vec / (np.linalg.norm(vec) + 1e-8)
        c1 = _make_cell(x=0, y=0, z=0)
        c1.thought_vec = vec.copy()
        c1.worldview_vec = np.random.randn(384).astype(np.float32) * 0.1
        c2 = _make_cell(x=0.5, y=0, z=0)
        c2.thought_vec = vec.copy()
        c2.worldview_vec = c1.worldview_vec.copy()

        out = apply_fusion([c1, c2], distance_threshold=2.0)
        assert len(out) == 1
        assert out[0].energy == c1.energy + c2.energy

    def test_no_fusion_when_far(self):
        c1 = _make_cell(x=0, y=0, z=0)
        c2 = _make_cell(x=100, y=0, z=0)
        c2.thought_vec = c1.thought_vec.copy()
        c2.worldview_vec = c1.worldview_vec.copy()
        out = apply_fusion([c1, c2], distance_threshold=2.0)
        assert len(out) == 2

    def test_no_fusion_when_dissimilar_thought(self):
        c1 = _make_cell(x=0, y=0, z=0)
        c1.thought_vec = np.ones(256)
        c2 = _make_cell(x=0.5, y=0, z=0)
        c2.thought_vec = -np.ones(256)
        c2.worldview_vec = c1.worldview_vec.copy()
        out = apply_fusion([c1, c2], distance_threshold=2.0)
        assert len(out) == 2


class TestMutation:
    """돌연변이: 벡터 변이."""

    def test_vectors_change(self):
        cell = _make_cell()
        out = apply_mutation([cell], rate=0.5)
        assert len(out) == 1
        assert not np.allclose(out[0].gene_vec, cell.gene_vec)
