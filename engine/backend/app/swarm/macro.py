"""Macro field layer for Swarm Mode."""
from __future__ import annotations

from statistics import fmean

from app.swarm.types import MacroFieldState, MesoGroupState, SwarmConfig


def compute_macro_field(
    *,
    t: int,
    config: SwarmConfig,
    groups: list[MesoGroupState],
    previous: MacroFieldState | None = None,
) -> MacroFieldState:
    pressures = [group.pressure for group in groups]
    avg_pressure = fmean(pressures) if pressures else 0.0
    max_pressure = max(pressures) if pressures else 0.0
    shock = 0.0
    if config.shock_interval and t > 0 and t % config.shock_interval == 0:
        shock = min(1.0, 0.35 + config.policy_intensity * 0.55)
    prior_rumor = previous.rumor_pressure if previous else 0.0
    rumor = min(1.0, prior_rumor * 0.82 + max_pressure * 0.12 + shock * 0.25)
    policy_wave = min(1.0, config.policy_intensity * 0.72 + shock * 0.35 + avg_pressure * 0.08)
    return MacroFieldState(
        t=int(t),
        avg_pressure=round(avg_pressure, 4),
        max_pressure=round(max_pressure, 4),
        shock_strength=round(shock, 4),
        rumor_pressure=round(rumor, 4),
        policy_wave=round(policy_wave, 4),
    )
