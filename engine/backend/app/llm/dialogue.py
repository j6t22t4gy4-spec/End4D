"""Agent-to-agent LLM dialogue outcomes for long-run social dynamics."""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

from app.core.collective_dynamics import collective_context_from_action_state, collective_decision_influence
from app.core.coordinates import distance_4d
from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.relationship_state import relationship_score, update_relationship
from app.core.settings import (
    get_collective_dialogue_scale,
    get_dialogue_interval,
    get_dialogue_max_pairs,
)
from app.core.spatial_index import SpatialHashGrid
from app.llm.facade import llm_facade
from app.models.cell import Cell

DIALOGUE_RADIUS = 5.0


def apply_agent_dialogues_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    """Run a capped direct dialogue layer between nearby agents."""
    t_int = int(current_t)
    interval = get_dialogue_interval()
    if not cells or t_int <= 0 or t_int % interval != 0:
        return cells

    pairs = _select_dialogue_pairs(cells, radius=DIALOGUE_RADIUS, max_pairs=get_dialogue_max_pairs())
    if not pairs:
        return cells

    generated = llm_facade.run_dialogues(
        [(cells[i], cells[j]) for i, j in pairs],
        current_t=current_t,
    )
    out = [cell.copy() for cell in cells]
    for (i, j), text in zip(pairs, generated):
        outcome = _parse_dialogue_outcome(text, out[i], out[j])
        out[i] = _apply_dialogue_to_cell(out[i], outcome, side="a", peer=out[j], current_t=current_t)
        out[j] = _apply_dialogue_to_cell(out[j], outcome, side="b", peer=out[i], current_t=current_t)
    return out


def _select_dialogue_pairs(cells: List[Cell], *, radius: float, max_pairs: int) -> List[Tuple[int, int]]:
    grid = SpatialHashGrid(cells, cell_size=radius)
    by_id = {cell.cell_id: idx for idx, cell in enumerate(cells)}
    used: set[str] = set()
    pairs: List[Tuple[int, int]] = []
    for i, cell in enumerate(cells):
        if cell.cell_id in used:
            continue
        candidates = [
            other
            for other in grid.candidate_cells(cell, radius)
            if other.cell_id != cell.cell_id and other.cell_id not in used and distance_4d(cell, other) <= radius
        ]
        if not candidates:
            continue
        candidates.sort(
            key=lambda other: (
                -(
                    relationship_score(cell, other.cell_id)
                    + relationship_score(other, cell.cell_id)
                ),
                -abs(
                    float(cell.action_state.get("policy_sensitivity", 0.5))
                    - float(other.action_state.get("policy_sensitivity", 0.5))
                ),
                distance_4d(cell, other),
                other.cell_id,
            )
        )
        peer = candidates[0]
        j = by_id.get(peer.cell_id)
        if j is None:
            continue
        used.add(cell.cell_id)
        used.add(peer.cell_id)
        pairs.append((i, j))
        if len(pairs) >= max_pairs:
            break
    return pairs


def _apply_dialogue_to_cell(
    cell: Cell,
    outcome: Dict[str, float | str],
    *,
    side: str,
    peer: Cell,
    current_t: float,
) -> Cell:
    summary_key = "summary_a" if side == "a" else "summary_b"
    summary = str(outcome.get(summary_key) or outcome.get("summary_a") or "direct dialogue")
    summary = _humanize_dialogue_summary(summary, cell=cell, peer=peer)
    current_action = dict(cell.action_state)
    collective = collective_context_from_action_state(current_action)
    influence = collective_decision_influence(current_action)
    decision_delta = float(influence["decision_pressure_delta"])
    dialogue_scale = get_collective_dialogue_scale()
    fracture_boost = (
        1.0
        + (0.25 if bool(collective["fracture_alert"]) else 0.0)
        + (0.12 if bool(collective["drift_alert"]) else 0.0)
        + decision_delta * 0.85
    )
    pressure = float(collective["collective_pressure"])
    trust_delta = max(0.0, float(outcome["cooperation_delta"])) * 0.7 + max(0.0, float(outcome["alignment_delta"])) * 0.35
    tension_delta = max(0.0, float(outcome["tension_delta"])) + max(0.0, -float(outcome["cooperation_delta"])) * 0.45
    cooperation_delta = (
        float(outcome["cooperation_delta"])
        * max(0.48, 1.0 + (float(collective["role_cohesion"]) - 0.5) * 0.35 - pressure * 0.15 - decision_delta * 0.5)
        * dialogue_scale
    )
    risk_delta = float(outcome["tension_delta"]) * 0.15 * fracture_boost * dialogue_scale
    current_action["cooperation_bias"] = _clip01(
        float(current_action.get("cooperation_bias", 0.5)) + cooperation_delta
    )
    current_action["risk_tolerance"] = _clip01(
        float(current_action.get("risk_tolerance", 0.5)) + risk_delta
    )
    current_action["last_dialogue_summary"] = summary
    current_action["last_dialogue_peer_id"] = peer.cell_id
    current_action["last_dialogue_peer_label"] = _agent_display(peer)
    current_action["collective_dialogue_effect"] = round(abs(cooperation_delta) + abs(risk_delta), 4)
    current_action["collective_dialogue_pressure"] = round(pressure, 3)
    current_action["collective_dialogue_decision_delta"] = round(decision_delta, 4)
    current_action.update(influence)
    current_action["fracture_signal_received"] = bool(current_action.get("fracture_signal_received") or collective["fracture_alert"])

    entry = memory_entry(
        t=float(current_t),
        kind="agent_dialogue",
        summary=summary,
        importance=float(outcome["importance"]),
        source="llm.dialogue",
        payload={
            "peer_id": peer.cell_id,
            "peer_label": _agent_display(peer),
            "self_label": _agent_display(cell),
            "alignment_delta": outcome["alignment_delta"],
            "tension_delta": outcome["tension_delta"],
            "cooperation_delta": cooperation_delta,
            "trust_delta": trust_delta,
            "collective_pressure": pressure,
            "decision_pressure_delta": decision_delta,
            "group_pressure_reason": influence["group_pressure_reason"],
            "fracture_alert": collective["fracture_alert"],
        },
        tags=["llm", "dialogue"],
    )
    behavior = behavior_event(
        t=float(current_t),
        event_type="agent_dialogue",
        source="llm.dialogue",
        summary=summary,
        quality_score=float(outcome["importance"]),
        payload=dict(entry["payload"]),
    )
    updated = update_relationship(
        cell.copy(action_state=current_action),
        peer.cell_id,
        current_t=current_t,
        trust_delta=trust_delta,
        tension_delta=tension_delta,
        alignment_delta=float(outcome["alignment_delta"]),
        summary=summary,
    )
    return append_memory(
        updated,
        entry,
        behavior=behavior,
        promote=float(outcome["importance"]) >= 0.74,
    )


def _parse_dialogue_outcome(text: str, a: Cell, b: Cell) -> Dict[str, float | str]:
    payload = _extract_json_object(text)
    if payload is None:
        return _heuristic_dialogue(a, b)
    return {
        "summary_a": str(payload.get("summary_a") or _dialogue_line(a, b, tension=float(payload.get("tension_delta", 0.02) or 0.02))),
        "summary_b": str(payload.get("summary_b") or _dialogue_line(b, a, tension=float(payload.get("tension_delta", 0.02) or 0.02))),
        "alignment_delta": _signed(payload.get("alignment_delta"), default=0.04),
        "tension_delta": _signed(payload.get("tension_delta"), default=0.02),
        "cooperation_delta": _signed(payload.get("cooperation_delta"), default=0.03),
        "importance": _clip01(float(payload.get("importance", 0.68))),
    }


def _heuristic_dialogue(a: Cell, b: Cell) -> Dict[str, float | str]:
    coop_a = float(a.action_state.get("cooperation_bias", 0.5))
    coop_b = float(b.action_state.get("cooperation_bias", 0.5))
    delta = 0.04 if (coop_a + coop_b) / 2.0 >= 0.5 else -0.02
    return {
        "summary_a": _dialogue_line(a, b, tension=max(0.0, -delta)),
        "summary_b": _dialogue_line(b, a, tension=max(0.0, -delta)),
        "alignment_delta": abs(delta),
        "tension_delta": max(0.0, -delta),
        "cooperation_delta": delta,
        "importance": 0.66,
    }


def _extract_json_object(text: str) -> dict | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
    return None


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _signed(value, *, default: float) -> float:
    try:
        return max(-1.0, min(1.0, float(value)))
    except Exception:
        return default


def _agent_display(cell: Cell) -> str:
    attrs = dict(cell.persona_attrs or {})
    name = str(attrs.get("agent_name") or attrs.get("display_name") or "").strip()
    role = str(cell.role_label or cell.role_key or "agent").strip() or "agent"
    if name:
        base = name if "(" in name else f"{name}({role})"
    else:
        base = role
    return base[:60]


def _agent_concern(cell: Cell) -> str:
    state = dict(cell.action_state or {})
    for key in ("last_action_summary", "last_thought_summary", "strategy_summary", "persona_prior_summary"):
        value = " ".join(str(state.get(key) or "").split())
        if value:
            return value[:90]
    attrs = dict(cell.persona_attrs or {})
    for key in ("occupation", "identity_summary", "scenario_prompt"):
        value = " ".join(str(attrs.get(key) or "").split())
        if value:
            return value[:90]
    return "지금 상황이 자기 생활에 어떤 비용을 만들지 따져보고 있음"


def _dialogue_line(cell: Cell, peer: Cell, *, tension: float) -> str:
    me = _agent_display(cell)
    peer_name = _agent_display(peer)
    concern = _agent_concern(cell)
    peer_concern = _agent_concern(peer)
    if tension >= 0.04:
        return f"{me}은 {peer_name}에게서 '{peer_concern}'라는 걱정을 듣고, 내 입장인 '{concern}'이 쉽게 받아들여지지 않겠다고 느꼈다."
    return f"{me}은 {peer_name}에게서 '{peer_concern}'라는 말을 듣고, 내 다음 행동을 '{concern}' 쪽으로 조심스럽게 맞춰볼 수 있겠다고 생각했다."


def _humanize_dialogue_summary(summary: str, *, cell: Cell, peer: Cell) -> str:
    text = " ".join(str(summary or "").split())
    lowered = text.lower()
    if not text or "dialogue updated" in lowered or "direct dialogue" in lowered or "changed cooperation" in lowered:
        return _dialogue_line(cell, peer, tension=0.02)
    peer_label = _agent_display(peer)
    if peer_label not in text:
        return f"{peer_label}와의 대화에서 {text}"
    return text[:260]
