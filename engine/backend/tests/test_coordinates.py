"""Coordinate semantics for the 2D social field refactor."""
import numpy as np

from app.core.coordinates import distance_4d, zone_penalty
from app.models.cell import Cell


def _cell(*, x: float, y: float, zone_id: str, zone_friction: float = 0.0) -> Cell:
    return Cell(
        x=x,
        y=y,
        z=7.0,
        t=0.0,
        energy=10.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        zone_id=zone_id,
        zone_label=zone_id,
        zone_friction=zone_friction,
        action_state={"z_weight": 0.1},
    )


def test_distance_4d_uses_xy_when_social_elevation_is_equal():
    a = _cell(x=0.0, y=0.0, zone_id="zone-a")
    b = _cell(x=3.0, y=4.0, zone_id="zone-a")
    assert distance_4d(a, b, time_weight=0.0) == 5.0


def test_distance_4d_can_include_social_elevation_gap():
    a = _cell(x=0.0, y=0.0, zone_id="zone-a").copy(z=2.0)
    b = _cell(x=0.0, y=4.0, zone_id="zone-a").copy(z=8.0)
    assert distance_4d(a, b, z_weight=0.0, time_weight=0.0) == 4.0
    assert distance_4d(a, b, z_weight=0.5, time_weight=0.0) > 4.0


def test_zone_penalty_applies_across_different_zones():
    a = _cell(x=0.0, y=0.0, zone_id="zone-a", zone_friction=0.2)
    b = _cell(x=0.0, y=0.0, zone_id="zone-b", zone_friction=0.4)
    penalty = zone_penalty(a, b)
    assert penalty > 1.0
    assert distance_4d(a, b, time_weight=0.0) == penalty
