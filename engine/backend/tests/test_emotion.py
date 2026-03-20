"""규칙 기반 Emotion (Phase 6.1)."""
import numpy as np

from app.core.emotion import (
    EMOTION_DIM,
    compute_emotion_proposal,
    count_neighbors,
    update_emotions,
)
from app.models.cell import Cell


def _cell(energy: float, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> Cell:
    return Cell(
        x=x,
        y=y,
        z=z,
        t=0.0,
        energy=energy,
        gene_vec=np.zeros(8, dtype=np.float32),
        emotion_vec=np.zeros(EMOTION_DIM, dtype=np.float32),
        thought_vec=np.zeros(256, dtype=np.float32),
        worldview_vec=np.zeros(384, dtype=np.float32),
    )


def test_emotion_dim():
    c = _cell(50.0)
    v = compute_emotion_proposal(c, neighbor_count=0)
    assert v.shape == (EMOTION_DIM,)


def test_low_energy_more_fear_than_high():
    low = compute_emotion_proposal(_cell(5.0), 0)
    high = compute_emotion_proposal(_cell(95.0), 0)
    assert low[2] > high[2]  # fear index


def test_crowding_increases_fear():
    alone = compute_emotion_proposal(_cell(50.0), 0)
    crowded = compute_emotion_proposal(_cell(50.0), 20)
    assert crowded[2] >= alone[2]


def test_count_neighbors():
    a = _cell(40.0, x=0, y=0, z=0)
    b = _cell(40.0, x=0.5, y=0, z=0)
    c = _cell(40.0, x=50, y=0, z=0)
    n = count_neighbors([a, b, c], a)
    assert n == 1


def test_update_emotions_blends():
    c = _cell(80.0)
    c.emotion_vec[:] = 0.5
    out = update_emotions([c], current_t=1.0)
    assert len(out) == 1
    assert not np.allclose(out[0].emotion_vec, c.emotion_vec)
