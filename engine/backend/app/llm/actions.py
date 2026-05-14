"""LLM-backed action planning for agents."""
from __future__ import annotations

import json
from typing import Dict, List

from app.core.collective_dynamics import collective_decision_influence
from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.settings import get_action_refresh_interval, get_llm_agent_sample_size, get_llm_runtime_profile, get_ui_language
from app.llm.facade import llm_facade
from app.models.cell import Cell


def update_action_states_if_due(cells: List[Cell], current_t: float) -> List[Cell]:
    t_int = int(current_t)
    interval = get_action_refresh_interval()
    if t_int < 0 or t_int % interval != 0:
        return cells

    selected = _selected_indices(cells, t_int, get_llm_agent_sample_size())
    selected_cells = [cells[idx] for idx in selected]
    generated = llm_facade.decide_actions(selected_cells)
    out: List[Cell] = [cell.copy() for cell in cells]
    for idx, cell, text in zip(selected, selected_cells, generated):
        action_state = _parse_action_state(text, cell)
        merged_action_state = dict(cell.action_state)
        merged_action_state.update(action_state)
        _apply_collective_action_pressure(merged_action_state)
        merged_action_state["last_action_t"] = float(current_t)
        entry = memory_entry(
            t=float(current_t),
            kind="action_plan",
            summary=str(merged_action_state.get("strategy_summary") or "action plan"),
            importance=0.62,
            source="llm.action",
            payload=dict(merged_action_state),
            tags=["llm", "action_plan"],
        )
        behavior = behavior_event(
            t=float(current_t),
            event_type="action_plan",
            source="llm.action",
            summary=str(merged_action_state.get("strategy_summary") or "action plan"),
            quality_score=0.66,
            payload=dict(merged_action_state),
        )
        updated = append_memory(cell.copy(action_state=merged_action_state), entry, behavior=behavior, promote=False)
        out[idx] = updated
    selected_set = set(selected)
    for idx, cell in enumerate(out):
        if idx in selected_set:
            continue
        if not cell.action_state:
            action_state = _heuristic_action_state(cell)
            _apply_collective_action_pressure(action_state)
            out[idx] = cell.copy(action_state=action_state)
    return out


def _selected_indices(cells: List[Cell], t_int: int, limit: int) -> List[int]:
    if len(cells) <= limit:
        return list(range(len(cells)))
    profile = get_llm_runtime_profile()
    ranked = sorted(
        range(len(cells)),
        key=lambda idx: (
            -(0 if cells[idx].action_state else 1),
            -len(cells[idx].short_memory) - len(cells[idx].behavior_log),
            -float(cells[idx].energy),
            f"{t_int}:{cells[idx].cell_id}",
        ),
    )
    if profile == "llm-first":
        return ranked[: min(len(ranked), limit)]
    return ranked[:limit]


def _parse_action_state(text: str, cell: Cell) -> Dict[str, float | str]:
    payload = _extract_json_object(text)
    if payload is None:
        return _heuristic_action_state(cell)
    try:
        state = {
            "strategy_summary": str(payload.get("strategy_summary") or "adaptive planning"),
            "resource_bias": _bounded_float(payload.get("resource_bias"), default=0.55),
            "risk_tolerance": _bounded_float(payload.get("risk_tolerance"), default=0.5),
            "cooperation_bias": _bounded_float(payload.get("cooperation_bias"), default=0.5),
            "policy_sensitivity": _bounded_float(payload.get("policy_sensitivity"), default=0.5),
            "mobility_bias": _bounded_float(payload.get("mobility_bias"), default=0.4),
        }
        action_reason = str(payload.get("action_reason") or payload.get("reason") or "").strip()
        action_target = str(payload.get("action_target") or payload.get("target") or "").strip()
        if action_reason:
            state["action_reason"] = action_reason[:180]
        if action_target:
            state["action_target"] = action_target[:120]
        state["last_action_summary"] = _grounded_action_summary(cell, state)
        state["action_locale"] = get_ui_language()
        return state
    except Exception:
        return _heuristic_action_state(cell)


def _heuristic_action_state(cell: Cell) -> Dict[str, float | str]:
    long_factor = min(1.0, len(cell.long_memory) / 12.0)
    short_factor = min(1.0, len(cell.short_memory) / 12.0)
    energy_factor = max(0.0, min(1.0, float(cell.energy) / 120.0))
    state: Dict[str, float | str] = {
        "resource_bias": 0.45 + 0.35 * energy_factor,
        "risk_tolerance": 0.35 + 0.25 * short_factor,
        "cooperation_bias": 0.45 + 0.3 * long_factor,
        "policy_sensitivity": 0.4 + 0.35 * short_factor,
        "mobility_bias": 0.35 + 0.2 * (1.0 - long_factor),
    }
    state["action_reason"] = _grounded_action_reason(cell)
    state["action_target"] = _grounded_action_target(cell)
    state["strategy_summary"] = _grounded_action_summary(cell, state)
    state["last_action_summary"] = str(state["strategy_summary"])
    state["action_locale"] = get_ui_language()
    return state


def _apply_collective_action_pressure(action_state: Dict[str, float | str]) -> None:
    influence = collective_decision_influence(action_state)
    delta = float(influence["decision_pressure_delta"])
    if bool(influence["collective_influence_applied"]):
        action_state["cooperation_bias"] = _bounded_float(
            float(action_state.get("cooperation_bias", 0.5)) - delta * 0.32,
            default=0.5,
        )
        action_state["policy_sensitivity"] = _bounded_float(
            float(action_state.get("policy_sensitivity", 0.5)) + delta * 0.42,
            default=0.5,
        )
        action_state["mobility_bias"] = _bounded_float(
            float(action_state.get("mobility_bias", 0.4)) + delta * 0.24,
            default=0.4,
        )
        action_state["risk_tolerance"] = _bounded_float(
            float(action_state.get("risk_tolerance", 0.5)) + delta * 0.36,
            default=0.5,
        )
        reason = str(influence["group_pressure_reason"])
        if get_ui_language() == "ko":
            suffix = f"집단 압력 반영: {reason}"
        else:
            suffix = f"collective pressure: {reason}"
        base = str(action_state.get("strategy_summary") or action_state.get("last_action_summary") or "adaptive planning")
        if suffix not in base:
            action_state["strategy_summary"] = f"{base}; {suffix}"
        action_state["last_action_summary"] = str(action_state["strategy_summary"])
    action_state.update(influence)
    action_state["collective_action_decision_delta"] = round(delta, 4)


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


def _bounded_float(value, *, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except Exception:
        return default


def _grounded_action_summary(cell: Cell, state: Dict[str, float | str]) -> str:
    locale = get_ui_language()
    role = _role_label(cell)
    zone = _zone_label(cell)
    action = str(state.get("strategy_summary") or "").strip()
    if _is_abstract_action(action):
        action = _default_action_phrase(cell)
    reason = str(state.get("action_reason") or "").strip() or _grounded_action_reason(cell)
    target = str(state.get("action_target") or "").strip() or _grounded_action_target(cell)
    if locale == "ko":
        return f"행동: {action[:90]}. 이유: {reason[:110]}. 대상: {target[:70]}."
    return f"Action: {action[:90]}. Reason: {reason[:110]}. Target: {target[:70]}."


def _grounded_action_reason(cell: Cell) -> str:
    locale = get_ui_language()
    role = _role_label(cell)
    zone = _zone_label(cell)
    persona = _persona_hint(cell)
    pressure = _pressure_hint(cell)
    recent = _recent_behavior_hint(cell)
    if locale == "ko":
        if pressure:
            return f"{role}가 {zone}에서 {pressure}를 감지했고 {recent}을 바탕으로 조정이 필요함"
        if persona:
            return f"{persona}라는 페르소나와 {zone}의 최근 맥락이 다음 선택을 압박함"
        return f"{role}가 {zone}의 최근 상호작용을 기준으로 위험과 협력 여지를 재평가함"
    if pressure:
        return f"{role} detects {pressure} in {zone} and adjusts from {recent}"
    if persona:
        return f"{persona} and the current {zone} context constrain the next move"
    return f"{role} is reassessing risk and cooperation in {zone}"


def _grounded_action_target(cell: Cell) -> str:
    role = _role_label(cell)
    zone = _zone_label(cell)
    if get_ui_language() == "ko":
        return f"{zone}의 {role} 및 가까운 협의 대상"
    return f"{role} peers and nearby negotiation partners in {zone}"


def _default_action_phrase(cell: Cell) -> str:
    role = _role_label(cell)
    zone = _zone_label(cell)
    pressure = float(dict(cell.action_state).get("collective_pressure", 0.0) or 0.0)
    if get_ui_language() == "ko":
        if pressure >= 0.5:
            return f"{role} 입장에서 {zone}의 갈등 신호를 줄이기 위해 자원과 동맹을 재배치한다"
        return f"{role} 입장에서 {zone}의 협력 가능성과 다음 행동 비용을 점검한다"
    if pressure >= 0.5:
        return f"rebalance resources and alliances as {role} under pressure in {zone}"
    return f"review cooperation options and next-move costs as {role} in {zone}"


def _is_abstract_action(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return True
    generic = {
        "adaptive planning",
        "heuristic adaptive stance",
        "persona_seeded_initial_state",
        "current_state_reflection",
    }
    return lowered in generic or len(lowered.split()) <= 2


def _role_label(cell: Cell) -> str:
    return (cell.role_label or cell.role_key or "agent").strip() or "agent"


def _zone_label(cell: Cell) -> str:
    return (cell.zone_label or cell.zone_id or "local field").strip() or "local field"


def _persona_hint(cell: Cell) -> str:
    text = " ".join(str(cell.persona_text or "").split())
    if text:
        return text[:80]
    attrs = dict(cell.persona_attrs or {})
    for key in ("occupation", "district", "age", "values", "policy_sensitivity"):
        value = str(attrs.get(key) or "").strip()
        if value:
            return value[:80]
    return ""


def _pressure_hint(cell: Cell) -> str:
    action_state = dict(cell.action_state)
    bucket = str(action_state.get("collective_pressure_bucket") or "").strip()
    signal = str(action_state.get("collective_signal") or "").strip()
    pressure = float(action_state.get("collective_pressure", 0.0) or 0.0)
    if get_ui_language() == "ko":
        if bucket or signal:
            return f"집단 압력 {bucket or signal}"
        if pressure >= 0.5:
            return "높아진 집단 압력"
        return ""
    if bucket or signal:
        return f"collective pressure {bucket or signal}"
    if pressure >= 0.5:
        return "rising collective pressure"
    return ""


def _recent_behavior_hint(cell: Cell) -> str:
    for item in reversed(list(cell.behavior_log or [])[-6:]):
        summary = " ".join(str(item.get("summary") or "").split())
        if summary:
            return summary[:90]
    if get_ui_language() == "ko":
        return "최근 관찰된 상호작용"
    return "recent observed interactions"
