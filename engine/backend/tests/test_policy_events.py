"""Structured policy event semantics tests."""
import numpy as np

from app.core.policy_events import apply_active_policies, normalize_policy_payload
from app.models.cell import Cell
from app.models.world import NutrientEvent


def _cell(role: str, zone_id: str) -> Cell:
    return Cell(
        cell_id=f"{role}-{zone_id}",
        x=0.0,
        y=0.0,
        z=0.0,
        t=0.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key=role,
        role_label=role,
        zone_id=zone_id,
        zone_label=zone_id,
    )


def test_normalize_policy_payload_adds_duration_and_scope_defaults():
    payload = normalize_policy_payload({"name": "tax credit", "intensity": 0.8})
    assert payload["duration_steps"] == 24
    assert payload["scope"] == "world"
    assert payload["energy_delta_per_step"] > 0


def test_active_policy_targets_only_matching_role_and_zone():
    event = NutrientEvent(
        t=3.0,
        event_type="policy_shift",
        payload={
            "name": "special economic zone credit",
            "intensity": 0.9,
            "duration_steps": 5,
            "target_roles": ["기업"],
            "target_zones": ["zone-1"],
            "effect_profile": "stimulus",
        },
    )
    matching = _cell("기업", "zone-1")
    other_role = _cell("시민", "zone-1")
    other_zone = _cell("기업", "zone-3")
    updated = apply_active_policies(
        [matching, other_role, other_zone],
        current_t=4.0,
        events=[event],
    )
    assert updated[0].energy > matching.energy
    assert updated[0].action_state["policy_field_profile"] == "stimulus"
    assert updated[1].energy == other_role.energy
    assert updated[2].energy == other_zone.energy
