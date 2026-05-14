"""Prompt construction for engine LLM tasks."""
from __future__ import annotations

import numpy as np

from app.core.collective_dynamics import collective_context_from_action_state
from app.core.emotion import EMOTION_LABELS
from app.core.memory_reflection import build_memory_reflection, build_worldview_reflection
from app.core.relationship_state import average_relationship_metrics, summarize_relationship
from app.core.settings import get_ui_language
from app.llm.prompt_registry import build_prompt_contract
from app.models.cell import Cell


def _compact_json_like(mapping: dict[str, object]) -> str:
    return "; ".join(f"{key}={value}" for key, value in mapping.items())


def _compact_persona_attrs(attrs: dict[str, object], limit: int = 8) -> str:
    if not attrs:
        return "none"
    compact: list[str] = []
    for key, value in list(attrs.items())[:limit]:
        value_text = " ".join(str(value).split())
        if value_text:
            compact.append(f"{key}={value_text[:72]}")
    return " ; ".join(compact) or "none"


def _collective_prompt_state(cell: Cell) -> str:
    context = collective_context_from_action_state(dict(cell.action_state))
    return _compact_json_like(
        {
            "signal": context["collective_signal"],
            "pressure": f"{float(context['collective_pressure']):.3f}",
            "bucket": context["pressure_bucket"],
            "role_cohesion": f"{float(context['role_cohesion']):.3f}",
            "role_fracture": f"{float(context['role_fracture']):.3f}",
            "zone_tension": f"{float(context['zone_tension']):.3f}",
            "zone_drift": f"{float(context['zone_drift']):.3f}",
            "fracture_alert": context["fracture_alert"],
            "tension_alert": context["tension_alert"],
        }
    )


def _recent_behavior_context(cell: Cell, limit: int = 4) -> str:
    items: list[str] = []
    for item in reversed(list(cell.behavior_log or [])[-8:]):
        summary = " ".join(str(item.get("summary") or "").split())
        event_type = str(item.get("event_type") or "event").strip()
        if summary:
            items.append(f"{event_type}: {summary[:110]}")
        if len(items) >= limit:
            break
    return " ; ".join(items) or "none"


def _scenario_context(cell: Cell) -> str:
    attrs = dict(cell.persona_attrs or {})
    for key in ("scenario", "scenario_prompt", "context", "world_context"):
        value = " ".join(str(attrs.get(key) or "").split())
        if value:
            return value[:320]
    return "none"


def build_thought_prompt(cell: Cell) -> str:
    language_label = "Korean" if get_ui_language() == "ko" else "English"
    ev = cell.emotion_vec
    dom = int(np.argmax(np.abs(ev))) if ev.size else 0
    label = EMOTION_LABELS[dom] if dom < len(EMOTION_LABELS) else "neutral"
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    recent_short = " ; ".join(
        str(item.get("summary") or "") for item in cell.short_memory[-4:] if str(item.get("summary") or "").strip()
    ) or "none"
    salient_long = " ; ".join(
        str(item.get("summary") or "") for item in cell.long_memory[-3:] if str(item.get("summary") or "").strip()
    ) or "none"
    reflection = build_memory_reflection(cell)
    previous_thought = str(dict(cell.action_state).get("last_thought_summary") or "").strip() or "none"
    return build_prompt_contract(
        "thought",
        [
            (
                "agent_state",
                _compact_json_like(
                    {
                        "role": role,
                        "energy": f"{cell.energy:.2f}",
                        "dominant_affect": label,
                        "gene_norm": f"{float(np.linalg.norm(cell.gene_vec)):.3f}",
                        "zone": getattr(cell, "zone_label", "") or getattr(cell, "zone_id", "") or "none",
                    }
                ),
            ),
            ("recent_short_memory", recent_short[:320]),
            ("salient_long_memory", salient_long[:280]),
            ("reflection", reflection[:360]),
            ("persona", cell.persona_text[:240]),
            ("persona_attrs", _compact_persona_attrs(dict(cell.persona_attrs))[:240]),
            ("scenario_context", _scenario_context(cell)),
            ("collective_context", _collective_prompt_state(cell)),
            ("recent_behavior", _recent_behavior_context(cell)),
            ("previous_thought", previous_thought[:220]),
            ("output_language", language_label),
            (
                "grounding_rules",
                (
                    f"Write in {language_label}. Mention the agent's role/zone pressure, one concrete concern, "
                    "and one next-move consideration. Avoid generic phrases like 'reassessing goals'."
                ),
            ),
        ],
    )


def build_worldview_prompt(cell: Cell) -> str:
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    reflection = build_worldview_reflection(cell)
    return build_prompt_contract(
        "worldview",
        [
            ("agent_state", _compact_json_like({"role": role, "energy": f"{cell.energy:.2f}"})),
            ("persona", cell.persona_text[:240]),
            ("worldview_reflection", reflection),
        ],
    )


def build_action_prompt(cell: Cell) -> str:
    language_label = "Korean" if get_ui_language() == "ko" else "English"
    ev = cell.emotion_vec
    dom = int(np.argmax(np.abs(ev))) if ev.size else 0
    label = EMOTION_LABELS[dom] if dom < len(EMOTION_LABELS) else "neutral"
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    reflection = build_memory_reflection(cell)
    worldview = build_worldview_reflection(cell)
    return build_prompt_contract(
        "action",
        [
            (
                "agent_state",
                _compact_json_like(
                    {
                        "role": role,
                        "energy": f"{cell.energy:.2f}",
                        "dominant_emotion": label,
                        "cooperation_bias": dict(cell.action_state).get("cooperation_bias", 0.5),
                        "policy_sensitivity": dict(cell.action_state).get("policy_sensitivity", 0.5),
                    }
                ),
            ),
            ("persona", cell.persona_text[:220]),
            ("persona_attrs", _compact_persona_attrs(dict(cell.persona_attrs))[:220]),
            ("scenario_context", _scenario_context(cell)),
            ("recent_memory", reflection[:320]),
            ("recent_behavior", _recent_behavior_context(cell)),
            ("worldview", worldview[:320]),
            ("collective_context", _collective_prompt_state(cell)),
            (
                "output_rules",
                (
                    "Return JSON only. In addition to the numeric fields, include action_reason, action_target, "
                    f"and last_action_summary in {language_label}. The summary must be concrete: action + reason + target, "
                    "grounded in persona, zone, recent behavior, and collective pressure."
                ),
            ),
        ],
    )


def build_policy_prompt(cell: Cell, event_type: str, payload: dict) -> str:
    role = (cell.role_label or cell.role_key or "agent").strip() or "agent"
    worldview = build_worldview_reflection(cell)
    return build_prompt_contract(
        "policy",
        [
            ("agent_state", _compact_json_like({"role": role, "energy": f"{cell.energy:.2f}"})),
            ("persona", cell.persona_text[:220]),
            ("collective_context", _collective_prompt_state(cell)),
            ("policy_event", _compact_json_like({"event_type": event_type, "payload": payload})),
            ("worldview", worldview[:320]),
        ],
    )


def build_dialogue_prompt(a: Cell, b: Cell, *, current_t: float) -> str:
    role_a = (a.role_label or a.role_key or "agent").strip() or "agent"
    role_b = (b.role_label or b.role_key or "agent").strip() or "agent"
    relation_a = summarize_relationship(a, b.cell_id)
    relation_b = summarize_relationship(b, a.cell_id)
    return build_prompt_contract(
        "dialogue",
        [
            ("context", f"t={float(current_t):.1f}"),
            (
                "agent_a",
                _compact_json_like(
                    {
                        "role": role_a,
                        "energy": f"{a.energy:.2f}",
                        "action": dict(a.action_state),
                        "collective": _collective_prompt_state(a),
                        "memory": build_memory_reflection(a)[:260],
                        "relation_to_b": relation_a,
                    }
                ),
            ),
            (
                "agent_b",
                _compact_json_like(
                    {
                        "role": role_b,
                        "energy": f"{b.energy:.2f}",
                        "action": dict(b.action_state),
                        "collective": _collective_prompt_state(b),
                        "memory": build_memory_reflection(b)[:260],
                        "relation_to_a": relation_b,
                    }
                ),
            ),
        ],
    )


def build_group_deliberation_prompt(role: str, cells: list[Cell], *, current_t: float) -> str:
    if not cells:
        return build_prompt_contract("group_deliberation", [("group_state", f"empty_group={role}")])
    avg_energy = sum(float(c.energy) for c in cells) / len(cells)
    avg_coop = sum(float(c.action_state.get("cooperation_bias", 0.5)) for c in cells) / len(cells)
    avg_policy = sum(float(c.action_state.get("policy_sensitivity", 0.5)) for c in cells) / len(cells)
    avg_collective_pressure = sum(float(c.action_state.get("collective_pressure", 0.0)) for c in cells) / len(cells)
    avg_role_fracture = sum(float(c.action_state.get("role_group_fracture_risk", 0.0)) for c in cells) / len(cells)
    avg_zone_tension = sum(float(c.action_state.get("zone_group_tension", 0.0)) for c in cells) / len(cells)
    relationship_metrics = average_relationship_metrics(cells)
    memories = " | ".join(
        build_memory_reflection(c)[:180]
        for c in cells[:5]
        if build_memory_reflection(c).strip()
    ) or "none"
    return build_prompt_contract(
        "group_deliberation",
        [
            ("context", f"t={float(current_t):.1f}"),
            (
                "group_state",
                _compact_json_like(
                    {
                        "role": role,
                        "sample_size": len(cells),
                        "avg_energy": f"{avg_energy:.2f}",
                        "avg_cooperation": f"{avg_coop:.3f}",
                        "avg_policy_sensitivity": f"{avg_policy:.3f}",
                        "avg_collective_pressure": f"{avg_collective_pressure:.3f}",
                        "avg_role_fracture": f"{avg_role_fracture:.3f}",
                        "avg_zone_tension": f"{avg_zone_tension:.3f}",
                        "avg_trust": f"{relationship_metrics['avg_trust']:.3f}",
                        "avg_tension": f"{relationship_metrics['avg_tension']:.3f}",
                        "repeat_peer_density": f"{relationship_metrics['repeat_peer_density']:.3f}",
                    }
                ),
            ),
            ("sample_memories", memories[:800]),
        ],
    )
