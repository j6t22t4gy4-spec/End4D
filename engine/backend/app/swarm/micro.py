"""Micro-agent layer for Swarm Mode."""
from __future__ import annotations

import math
import random
import re
from typing import Any

from app.swarm.types import MacroFieldState, MesoGroupState, SwarmAgent, SwarmConfig


def seed_micro_agents(config: SwarmConfig) -> list[SwarmAgent]:
    rng = random.Random(config.seed)
    group_count = max(1, int(config.meso_group_count))
    personas = [dict(item) for item in config.persona_catalog if isinstance(item, dict)]
    group_map = _build_persona_group_map(personas, config=config)
    scenario_tokens = _tokens(config.scenario_prompt)
    agents: list[SwarmAgent] = []
    for idx in range(max(1, int(config.agent_count))):
        persona = personas[idx % len(personas)] if personas else {}
        role = _persona_role(persona, config=config, fallback_idx=idx)
        zone_id, zone_label = _persona_zone(persona, fallback_idx=idx, group_count=group_count)
        group_key = f"{role}|{zone_id}" if personas else f"fallback|{idx % group_count}"
        group_idx = group_map.get(group_key, idx % group_count)
        theta = (2.0 * math.pi * group_idx) / group_count
        local = rng.random() * 2.0 * math.pi
        persona_grounding = 0.25 if personas else 0.0
        if role and not role.startswith("role-"):
            persona_grounding += 0.28
        if zone_label and not zone_label.startswith("Zone "):
            persona_grounding += 0.22
        if str(persona.get("persona_text") or "").strip():
            persona_grounding += 0.18
        scenario_relevance = _scenario_relevance(persona=persona, role=role, zone_label=zone_label, scenario_tokens=scenario_tokens)
        persona_grounding = _clip01(persona_grounding)
        radius = 7.5 + group_idx * 0.18 + (1.0 - persona_grounding) * 2.0 + rng.random() * 1.8
        role_offset = (_stable_unit(role) - 0.5) * 1.4
        zone_offset = (_stable_unit(zone_id) - 0.5) * 1.4
        x = math.cos(theta) * radius + math.cos(local) * rng.random() * 1.2 + role_offset
        y = math.sin(theta) * radius + math.sin(local) * rng.random() * 1.2 + zone_offset
        traits = _persona_traits(persona=persona, role=role, scenario_relevance=scenario_relevance, rng=rng)
        agents.append(
            SwarmAgent(
                agent_id=f"swarm-agent-{idx}",
                group_id=f"group-{group_idx}",
                x=x,
                y=y,
                vx=rng.uniform(-0.025, 0.025),
                vy=rng.uniform(-0.025, 0.025),
                energy=traits["energy"],
                cooperation=traits["cooperation"],
                policy_sensitivity=traits["policy_sensitivity"],
                risk=traits["risk"],
                role=role,
                zone_id=zone_id,
                zone_label=zone_label,
                persona_id=str(persona.get("persona_id") or persona.get("uuid") or ""),
                persona_text=str(persona.get("persona_text") or persona.get("professional_persona") or "")[:360],
                persona_attrs=dict(persona.get("attrs") or {}),
                persona_grounding_score=round(persona_grounding, 4),
                scenario_relevance_score=round(scenario_relevance, 4),
            )
        )
    return agents


def tick_micro_agents(
    agents: list[SwarmAgent],
    *,
    groups: dict[str, MesoGroupState],
    macro: MacroFieldState,
    rng: random.Random,
    interaction_scale: float = 1.0,
) -> list[SwarmAgent]:
    updated: list[SwarmAgent] = []
    for agent in agents:
        group = groups.get(agent.group_id)
        group_pressure = group.pressure if group else 0.0
        group_tension = group.tension if group else 0.0
        agent_pressure = min(1.0, group_pressure * 0.72 + macro.policy_wave * agent.policy_sensitivity * 0.22 + macro.rumor_pressure * 0.06)
        pull_x = ((group.center_x if group else agent.x) - agent.x) * max(0.002, 0.016 - group_tension * 0.008)
        pull_y = ((group.center_y if group else agent.y) - agent.y) * max(0.002, 0.016 - group_tension * 0.008)
        jitter = 0.012 + agent_pressure * 0.045 + group_tension * 0.025
        vx = (agent.vx * 0.86) + pull_x + rng.uniform(-jitter, jitter)
        vy = (agent.vy * 0.86) + pull_y + rng.uniform(-jitter, jitter)
        scale = max(0.1, float(interaction_scale))
        risk = _clip01(agent.risk + (agent_pressure * 0.018 - agent.cooperation * 0.006) * scale)
        cooperation = _clip01(agent.cooperation + ((0.5 - group_tension) * 0.012 - agent_pressure * 0.014) * scale)
        updated.append(
            SwarmAgent(
                agent_id=agent.agent_id,
                group_id=agent.group_id,
                x=agent.x + vx,
                y=agent.y + vy,
                vx=vx,
                vy=vy,
                energy=_clip01(agent.energy - 0.001 + cooperation * 0.0015 - risk * 0.001),
                cooperation=cooperation,
                policy_sensitivity=_clip01(agent.policy_sensitivity + macro.policy_wave * 0.006),
                risk=risk,
                pressure=agent_pressure,
                role=agent.role,
                zone_id=agent.zone_id,
                zone_label=agent.zone_label,
                persona_id=agent.persona_id,
                persona_text=agent.persona_text,
                persona_attrs=dict(agent.persona_attrs),
                persona_grounding_score=agent.persona_grounding_score,
                scenario_relevance_score=agent.scenario_relevance_score,
            )
        )
    return updated


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _build_persona_group_map(personas: list[dict[str, Any]], *, config: SwarmConfig) -> dict[str, int]:
    group_count = max(1, int(config.meso_group_count))
    keys: list[str] = []
    seen: set[str] = set()
    for idx, persona in enumerate(personas):
        role = _persona_role(persona, config=config, fallback_idx=idx)
        zone_id, _ = _persona_zone(persona, fallback_idx=idx, group_count=group_count)
        key = f"{role}|{zone_id}"
        if key not in seen:
            seen.add(key)
            keys.append(key)
    if not keys:
        return {}
    keys.sort(key=lambda item: _stable_unit(item))
    return {key: idx % group_count for idx, key in enumerate(keys)}


def _persona_role(persona: dict[str, Any], *, config: SwarmConfig, fallback_idx: int) -> str:
    attrs = dict(persona.get("attrs") or {})
    role = str(
        persona.get("role_key")
        or persona.get("role_label")
        or attrs.get("occupation")
        or persona.get("occupation")
        or ""
    ).strip()
    if role:
        return role[:48]
    if config.role_catalog:
        return str(config.role_catalog[fallback_idx % len(config.role_catalog)])[:48]
    return f"role-{fallback_idx % 6}"


def _persona_zone(persona: dict[str, Any], *, fallback_idx: int, group_count: int) -> tuple[str, str]:
    attrs = dict(persona.get("attrs") or {})
    label = str(
        persona.get("zone_label")
        or attrs.get("district")
        or attrs.get("province")
        or attrs.get("region")
        or persona.get("country")
        or ""
    ).strip()
    if label:
        return f"zone-{_slug(label)}", label[:64]
    zone_idx = fallback_idx % max(1, min(12, group_count))
    return f"zone-{zone_idx}", f"Zone {zone_idx}"


def _persona_traits(
    *,
    persona: dict[str, Any],
    role: str,
    scenario_relevance: float,
    rng: random.Random,
) -> dict[str, float]:
    attrs = dict(persona.get("attrs") or {})
    text = " ".join([role, str(persona.get("persona_text") or ""), str(persona.get("professional_persona") or "")]).lower()
    cooperation = rng.uniform(0.38, 0.68)
    policy = rng.uniform(0.30, 0.70)
    risk = rng.uniform(0.24, 0.68)
    energy = rng.uniform(0.48, 0.78)
    if any(token in text for token in ("teacher", "nurse", "public", "care", "교사", "간호", "복지", "공무")):
        cooperation += 0.12
        policy += 0.06
    if any(token in text for token in ("business", "founder", "investor", "market", "자영업", "사업", "투자", "기업")):
        risk += 0.10
        energy += 0.06
    if any(token in text for token in ("driver", "delivery", "logistics", "운전", "배송", "물류")):
        risk += 0.08
    if attrs.get("age"):
        try:
            age = int(attrs["age"])
            if age < 30:
                risk += 0.05
                energy -= 0.03
            elif age >= 55:
                cooperation += 0.05
                risk -= 0.04
        except (TypeError, ValueError):
            pass
    policy += scenario_relevance * 0.14
    risk += scenario_relevance * 0.06
    return {
        "energy": _clip01(energy),
        "cooperation": _clip01(cooperation),
        "policy_sensitivity": _clip01(policy),
        "risk": _clip01(risk),
    }


def _scenario_relevance(
    *,
    persona: dict[str, Any],
    role: str,
    zone_label: str,
    scenario_tokens: set[str],
) -> float:
    if not scenario_tokens:
        return 0.35 if persona else 0.0
    attrs = dict(persona.get("attrs") or {})
    haystack = " ".join(
        [
            role,
            zone_label,
            str(persona.get("persona_text") or ""),
            str(persona.get("professional_persona") or ""),
            " ".join(str(value) for value in attrs.values()),
        ]
    ).lower()
    hay_tokens = _tokens(haystack)
    overlap = len(scenario_tokens.intersection(hay_tokens))
    return _clip01(0.22 + min(0.58, overlap / max(4.0, len(scenario_tokens) * 0.35)))


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z가-힣0-9]{2,}", str(text or ""))}


def _slug(text: str) -> str:
    tokens = re.findall(r"[A-Za-z0-9가-힣]+", str(text).lower())
    return "-".join(tokens[:4]) or "unknown"


def _stable_unit(text: str) -> float:
    value = 0
    for char in str(text):
        value = (value * 131 + ord(char)) % 10_000
    return value / 10_000.0
