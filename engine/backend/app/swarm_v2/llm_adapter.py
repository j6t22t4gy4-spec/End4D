"""Optional LLM enrichment for Swarm V2.

The V2 runtime must stay fast and independent. LLM output is therefore an
enrichment layer over already-generated swarm events, not the core loop.
"""
from __future__ import annotations

from collections import defaultdict
import json
from typing import Any, Literal

from app.core.settings import get_llm_chat_enabled, get_llm_model, get_llm_provider
from app.llm.facade import llm_facade

SwarmV2LlmMode = Literal["off", "packet", "agent", "hybrid", "full-agent"]
VALID_ACTIONS = {"post", "reply", "repost", "like", "do_nothing"}
VALID_TONES = {"positive", "dialogue", "negative", "hostile"}


def deliberate_stream_event(
    event: dict[str, Any],
    *,
    agents: list[dict[str, Any]],
    previous_events: list[dict[str, Any]],
    scenario: str,
) -> dict[str, Any]:
    """Run a single MiroFish-style per-agent deliberation for live streaming."""
    if not get_llm_chat_enabled():
        event["llm_fallback_reason"] = "llm_disabled"
        return event
    agent_by_id = {str(agent.get("agent_id")): agent for agent in agents}
    prompt = _agent_prompt(event, agent_by_id=agent_by_id, feed=_recent_feed(previous_events + [event], event), scenario=scenario)
    try:
        texts, meta = llm_facade.run_prompts_with_meta([prompt], task="swarm_agent")
        texts = _usable_texts({"texts": texts, "meta": meta}, [prompt])
    except Exception as exc:
        event["llm_fallback_reason"] = f"provider_error:{type(exc).__name__}"
        return event
    if not texts:
        event["llm_fallback_reason"] = "no_provider_text"
        return event
    parsed = _parse_agent_output(texts[0])
    event["llm_enriched"] = True
    event["llm_mode"] = "agent"
    event["llm_summary"] = texts[0]
    _apply_decision_to_event(event, parsed)
    return event


def _apply_decision_to_event(event: dict[str, Any], parsed: dict[str, Any]) -> None:
    event["llm_action"] = parsed["action"]
    event["llm_reasoning"] = parsed["thought"]
    event["llm_content"] = parsed["content"]
    event["agent_thought"] = parsed["thought"] or event.get("agent_thought") or ""
    event["agent_speech"] = parsed["content"] or event.get("agent_speech") or ""
    event["target_event_id"] = parsed["target_event_id"]
    event["decision_tone"] = parsed["tone"]
    event["memory_write"] = parsed["memory_write"]
    event["next_intent"] = parsed["next_intent"]
    event["decision_relation_delta"] = parsed["relation_delta"]
    event["decision_pressure_delta"] = parsed["pressure_delta"]
    event["agent_decision"] = {
        "action": parsed["action"],
        "target_event_id": parsed["target_event_id"],
        "thought": parsed["thought"],
        "content": parsed["content"],
        "tone": parsed["tone"],
        "relation_delta": parsed["relation_delta"],
        "pressure_delta": parsed["pressure_delta"],
        "memory_write": parsed["memory_write"],
        "next_intent": parsed["next_intent"],
        "schema_version": "swarm-agent-decision-v1",
    }
    event["summary"] = _compact(parsed["content"] or parsed["thought"] or event.get("summary") or "", 280)
    event["llm_action_effect"] = round(_action_effect(parsed["action"], parsed["content"]) + parsed["relation_delta"] * 0.35, 4)
    if parsed["tone"] in VALID_TONES:
        event["interaction_type"] = parsed["tone"]


def deliberate_stream_packet(
    event: dict[str, Any],
    *,
    previous_events: list[dict[str, Any]],
    scenario: str,
) -> dict[str, Any]:
    """Run a live packet-level LLM pass for the first event in a stream round."""
    if not get_llm_chat_enabled():
        event["llm_fallback_reason"] = "llm_disabled"
        return event
    key = (
        str(event.get("phase") or "unknown"),
        str(event.get("topic") or "unknown"),
        str(event.get("cohort") or "unknown"),
    )
    items = [item for item in previous_events[-8:] if str(item.get("topic") or "") == key[1]]
    items.append(event)
    prompt = _packet_prompt(key, items[-6:], scenario=scenario)
    try:
        texts, meta = llm_facade.run_prompts_with_meta([prompt], task="swarm_packet")
        texts = _usable_texts({"texts": texts, "meta": meta}, [prompt])
    except Exception as exc:
        event["llm_fallback_reason"] = f"provider_error:{type(exc).__name__}"
        return event
    if not texts:
        event["llm_fallback_reason"] = "no_provider_text"
        return event
    text = texts[0]
    event["llm_enriched"] = True
    event["llm_mode"] = "packet"
    event["llm_summary"] = text
    event["summary"] = _compact(text, 280)
    return event


def enrich_result_with_llm(result: dict[str, Any], *, mode: str = "packet", sample_size: int = 12) -> dict[str, Any]:
    normalized = _normalize_mode(mode)
    events = list(result.get("events") or [])
    agents = list(result.get("agents") or [])
    scenario = str(result.get("prompt") or "").strip()
    meta: dict[str, Any] = {
        "enabled": get_llm_chat_enabled(),
        "mode": normalized,
        "provider": get_llm_provider(),
        "model": get_llm_model(),
        "used": False,
        "enriched_events": 0,
        "fallback_reason": "",
    }
    if normalized == "off" or not events or not get_llm_chat_enabled():
        meta["fallback_reason"] = "mode_off" if normalized == "off" else "llm_disabled"
        _attach_meta(result, meta)
        return result

    try:
        enriched = 0
        if normalized in {"packet", "hybrid"}:
            enriched += _enrich_packet_events(events, scenario=scenario, sample_size=max(1, sample_size))
        if normalized in {"agent", "hybrid", "full-agent"}:
            agent_sample_size = len(events) if normalized == "full-agent" else max(1, sample_size)
            if normalized == "full-agent":
                for event in events:
                    event["llm_mode"] = "agent"
            enriched += _enrich_agent_events(events, agents=agents, scenario=scenario, sample_size=agent_sample_size)
        feedback_events = _apply_llm_action_feedback(events) if normalized in {"agent", "hybrid", "full-agent"} else 0
        meta["used"] = enriched > 0
        meta["enriched_events"] = enriched
        meta["action_feedback_events"] = feedback_events
    except Exception as exc:
        meta["fallback_reason"] = f"provider_error:{type(exc).__name__}"
    _attach_meta(result, meta)
    return result


def _normalize_mode(mode: str) -> SwarmV2LlmMode:
    value = str(mode or "packet").strip().lower()
    if value in {"off", "none", "disabled"}:
        return "off"
    if value in {"agent", "1:1", "one-to-one"}:
        return "agent"
    if value in {"full-agent", "all-agent", "agent-full", "full_agent", "all_agent"}:
        return "full-agent"
    if value == "hybrid":
        return "hybrid"
    return "packet"


def _enrich_packet_events(events: list[dict[str, Any]], *, scenario: str, sample_size: int) -> int:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        key = (
            str(event.get("phase") or "unknown"),
            str(event.get("topic") or "unknown"),
            str(event.get("cohort") or "unknown"),
        )
        groups[key].append(event)
    selected = sorted(groups.items(), key=lambda item: len(item[1]), reverse=True)[:sample_size]
    prompts = [_packet_prompt(key, items[:8], scenario=scenario) for key, items in selected]
    if not prompts:
        return 0
    texts, meta = llm_facade.run_prompts_with_meta(prompts, task="swarm_packet")
    texts = _usable_texts({"texts": texts, "meta": meta}, prompts)
    if not texts:
        return 0
    enriched = 0
    for (_, items), text in zip(selected, texts):
        for event in items[:3]:
            event["llm_enriched"] = True
            event["llm_mode"] = "packet"
            event["llm_summary"] = text
            event["summary"] = _compact(text, 260)
            enriched += 1
    return enriched


def _enrich_agent_events(events: list[dict[str, Any]], *, agents: list[dict[str, Any]], scenario: str, sample_size: int) -> int:
    if sample_size >= len(events):
        candidates = list(events)
    else:
        candidates = [
            event for event in events
            if str(event.get("llm_mode") or "") == "agent" or int(event.get("reply_depth") or 0) >= 1
        ][:sample_size]
    agent_by_id = {str(agent.get("agent_id")): agent for agent in agents}
    prompts = [_agent_prompt(event, agent_by_id=agent_by_id, feed=_recent_feed(events, event), scenario=scenario) for event in candidates]
    if not prompts:
        return 0
    texts, meta = llm_facade.run_prompts_with_meta(prompts, task="swarm_agent")
    texts = _usable_texts({"texts": texts, "meta": meta}, prompts)
    if not texts:
        return 0
    for event, text in zip(candidates, texts):
        parsed = _parse_agent_output(text)
        event["llm_enriched"] = True
        event["llm_mode"] = "agent"
        event["llm_summary"] = text
        _apply_decision_to_event(event, parsed)
    return len(texts)


def _apply_llm_action_feedback(events: list[dict[str, Any]]) -> int:
    """Let agent LLM decisions bend later rule events.

    The fast swarm loop is still rule-first, but a per-agent LLM decision should
    leave causal residue: replies become more likely, relationships drift, and
    nearby pressure changes inherit the tone of the generated action.
    """
    influenced = 0
    for index, event in enumerate(events):
        if not event.get("llm_enriched") or str(event.get("llm_mode") or "") != "agent":
            continue
        action = str(event.get("llm_action") or "").lower()
        content = str(event.get("llm_content") or event.get("summary") or "")
        relation_delta = float(event.get("decision_relation_delta") or 0.0)
        pressure_delta = float(event.get("decision_pressure_delta") or 0.0)
        effect = _action_effect(action, content) + relation_delta * 0.45 + pressure_delta * 0.2
        if abs(effect) < 0.001 and "nothing" in action:
            effect = -0.03
        event["llm_action_effect"] = round(effect, 4)
        horizon = events[index + 1 : index + 11]
        for later in horizon:
            affinity = _feedback_affinity(event, later)
            if affinity <= 0:
                continue
            current_relation = float(later.get("relationship_score") or 0.0)
            current_intensity = float(later.get("intensity") or 0.0)
            current_delta = float(later.get("pressure_delta") or 0.0)
            relation_next = _clamp(current_relation + effect * affinity * 0.45, -1.0, 1.0)
            intensity_next = _clamp(current_intensity + abs(effect) * affinity * 0.28, 0.05, 1.0)
            delta_next = current_delta + effect * affinity * 0.035
            later["relationship_score"] = round(relation_next, 4)
            later["intensity"] = round(intensity_next, 4)
            later["pressure_delta"] = round(delta_next, 4)
            later["llm_influenced_by_event_id"] = event.get("event_id")
            later["llm_action_effect"] = round(effect * affinity, 4)
            if not later.get("reply_to_event_id") and affinity >= 0.75:
                later["reply_to_event_id"] = event.get("event_id")
                later["reply_depth"] = int(later.get("reply_depth") or 0) + 1
            later["summary"] = _compact(
                f"{later.get('summary', '')} LLM 영향: {event.get('llm_content') or event.get('summary', '')}",
                320,
            )
            influenced += 1
    return influenced


def _action_effect(action: str, content: str) -> float:
    action_base = 0.0
    if "post" in action:
        action_base = 0.06
    elif "reply" in action:
        action_base = 0.08
    elif "repost" in action:
        action_base = 0.12
    elif "nothing" in action or "do nothing" in action:
        action_base = -0.04
    text = content.lower()
    positive = ["협력", "같이", "연대", "타협", "도움", "해결", "지지", "공감"]
    negative = ["불안", "분노", "반대", "충돌", "부담", "위협", "불공정", "화가"]
    tone = 0.0
    tone += sum(1 for token in positive if token in text) * 0.025
    tone -= sum(1 for token in negative if token in text) * 0.03
    return _clamp(action_base + tone, -0.18, 0.18)


def _feedback_affinity(source: dict[str, Any], later: dict[str, Any]) -> float:
    affinity = 0.0
    source_id = str(source.get("source_id") or "")
    target_id = str(source.get("target_id") or "")
    later_source = str(later.get("source_id") or "")
    later_target = str(later.get("target_id") or "")
    if later_source == target_id and later_target == source_id:
        affinity += 0.85
    elif source_id in {later_source, later_target} or target_id in {later_source, later_target}:
        affinity += 0.55
    if str(source.get("topic") or "") == str(later.get("topic") or ""):
        affinity += 0.35
    if str(source.get("cohort") or "") == str(later.get("cohort") or ""):
        affinity += 0.15
    return min(1.0, affinity)


def _usable_texts(batch: dict[str, Any], prompts: list[str]) -> list[str]:
    meta = dict(batch.get("meta") or {})
    if meta.get("used_fallback"):
        return []
    texts = [str(text).strip() for text in (batch.get("texts") or [])]
    return [
        text for text, prompt in zip(texts, prompts)
        if text and text != prompt
    ]


def _packet_prompt(key: tuple[str, str, str], items: list[dict[str, Any]], *, scenario: str) -> str:
    phase, topic, cohort = key
    examples = "\n".join(f"- {item.get('summary', '')}" for item in items[:5])
    return (
        "너는 End4D Swarm V2의 group packet 해석기다. "
        "반드시 전체 시나리오의 구체적 갈등/정책/시장 맥락에 묶어서 한국어로 한 문장만 재작성하라. "
        "금지: 일반론, 추상적 요약, 시나리오와 무관한 안전한 문장. "
        "필수: 누가 무엇을 듣고 어떤 이해관계 때문에 반응했는지 드러내라.\n"
        f"전체 시나리오:\n{_compact(scenario, 900)}\n"
        f"phase={phase}\ntopic={topic}\ncohort={cohort}\n"
        f"events:\n{examples}"
    )


def _agent_prompt(
    event: dict[str, Any],
    *,
    agent_by_id: dict[str, dict[str, Any]],
    feed: list[dict[str, Any]],
    scenario: str,
) -> str:
    source = agent_by_id.get(str(event.get("source_id"))) or {}
    target = agent_by_id.get(str(event.get("target_id"))) or {}
    feed_text = "\n".join(
        f"- @{_agent_label(agent_by_id.get(str(item.get('source_id'))) or {})}: {item.get('summary', '')}"
        for item in feed[-6:]
    ) or "- 아직 피드 없음"
    system_prompt = (
        f"You are {_agent_label(source)}, a simulated social agent in End4D Swarm V2.\n"
        f"Persona identity: {source.get('identity') or _agent_label(source)}\n"
        f"Role: {source.get('role') or 'unknown'}\n"
        f"Region/zone: {source.get('zone') or 'unknown'}\n"
        f"Cohort: {source.get('cohort') or 'unknown'}\n"
        f"Core stance: {source.get('stance')}; pressure={source.get('pressure')}; energy={source.get('energy')}\n"
        f"Goal in this scenario: protect your role group's concrete interest while reacting like a believable person, not an analyst.\n"
        f"Recent memory: {event.get('source_memory') or 'none'}"
    )
    user_prompt = (
        f"Current scenario:\n{_compact(scenario, 900)}\n\n"
        f"Current social feed:\n{feed_text}\n\n"
        f"You just encountered {_agent_label(target)} about topic: {event.get('topic')}.\n"
        f"Target event id if replying: {event.get('reply_to_event_id') or event.get('event_id')}\n"
        f"Relationship score with target: {event.get('relationship_score')}\n"
        f"Event draft: {event.get('summary')}\n\n"
        "Choose one action: post, reply, repost, like, do_nothing.\n"
        "Then produce a structured agent decision.\n"
        "thought must be an inner thought in first person: what I heard, who said it, why it changes my next move.\n"
        "content must be a concrete spoken reply/post with names/context and one scenario-specific detail.\n"
        "memory_write must be one short memory this agent will carry into the next round.\n"
        "relation_delta must be between -0.18 and 0.18. pressure_delta must be between -0.12 and 0.12.\n"
        "Do not summarize the scenario from outside. Do not write a generic analysis. Speak from inside the persona."
    )
    return (
        "SYSTEM PROMPT:\n"
        f"{system_prompt}\n\n"
        "USER PROMPT:\n"
        f"{user_prompt}\n\n"
        "OUTPUT FORMAT: Return compact JSON only, in Korean:\n"
        '{"action":"reply","target_event_id":"swarm-v2-1-1","thought":"나는 방금 누구의 어떤 말을 듣고 무엇을 의심하거나 결심했다","content":"상대에게 실제로 건네는 말","tone":"negative","relation_delta":-0.08,"pressure_delta":0.04,"memory_write":"다음 라운드에 기억할 한 문장","next_intent":"다음에 확인하거나 할 일"}'
    )


def _recent_feed(events: list[dict[str, Any]], current: dict[str, Any]) -> list[dict[str, Any]]:
    current_index = int(current.get("event_index") or 0)
    topic = str(current.get("topic") or "")
    source_id = str(current.get("source_id") or "")
    candidates = [
        event for event in events
        if int(event.get("event_index") or 0) < current_index
        and (str(event.get("topic") or "") == topic or str(event.get("target_id") or "") == source_id)
    ]
    return candidates[-8:]


def _agent_label(agent: dict[str, Any]) -> str:
    name = str(agent.get("name") or agent.get("agent_id") or "unknown")
    role = str(agent.get("role") or "").strip()
    return f"{name}({role})" if role else name


def _parse_agent_output(text: str) -> dict[str, Any]:
    cleaned = str(text or "").strip()
    try:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(cleaned[start : end + 1])
            return _normalize_decision(data, fallback_text=cleaned)
    except Exception:
        pass
    return _normalize_decision({"content": cleaned}, fallback_text=cleaned)


def _normalize_decision(data: dict[str, Any], *, fallback_text: str) -> dict[str, Any]:
    action = _normalize_action(data.get("action"))
    thought = str(data.get("thought") or data.get("reasoning") or "").strip()
    content = str(data.get("content") or fallback_text or "").strip()
    tone = _normalize_tone(data.get("tone") or data.get("interaction_type"))
    return {
        "action": action,
        "target_event_id": _compact(str(data.get("target_event_id") or data.get("target_post_id") or ""), 80),
        "thought": _compact(thought, 420),
        "content": _compact(content, 420),
        "tone": tone,
        "relation_delta": _clamp_float(data.get("relation_delta"), -0.18, 0.18, _default_relation_delta(tone, action)),
        "pressure_delta": _clamp_float(data.get("pressure_delta"), -0.12, 0.12, _default_pressure_delta(tone)),
        "memory_write": _compact(str(data.get("memory_write") or _fallback_memory(content, thought)), 220),
        "next_intent": _compact(str(data.get("next_intent") or _fallback_intent(action, tone)), 180),
    }


def _normalize_action(value: Any) -> str:
    raw = str(value or "reply").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "do nothing": "do_nothing",
        "nothing": "do_nothing",
        "comment": "reply",
        "share": "repost",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in VALID_ACTIONS else "reply"


def _normalize_tone(value: Any) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "neutral": "dialogue",
        "conflict": "negative",
        "angry": "hostile",
        "supportive": "positive",
    }
    raw = aliases.get(raw, raw)
    return raw if raw in VALID_TONES else "dialogue"


def _clamp_float(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = fallback
    return round(_clamp(num, low, high), 4)


def _default_relation_delta(tone: str, action: str) -> float:
    base = {"positive": 0.07, "dialogue": 0.015, "negative": -0.06, "hostile": -0.12}.get(tone, 0.0)
    if action == "like":
        base += 0.03
    elif action == "do_nothing":
        base *= 0.25
    elif action == "repost":
        base *= 1.2
    return base


def _default_pressure_delta(tone: str) -> float:
    return {"positive": -0.025, "dialogue": 0.01, "negative": 0.045, "hostile": 0.08}.get(tone, 0.0)


def _fallback_memory(content: str, thought: str) -> str:
    text = content or thought
    return _compact(text, 120) if text else "이번 발언의 반응을 다음 라운드에 확인하기로 함"


def _fallback_intent(action: str, tone: str) -> str:
    if action == "do_nothing":
        return "당장 말하지 않고 다음 피드의 반응을 관찰한다"
    if tone in {"negative", "hostile"}:
        return "비슷한 입장의 에이전트가 있는지 확인한다"
    if tone == "positive":
        return "협력 가능한 상대를 더 찾아본다"
    return "상대의 다음 발언을 듣고 입장을 조정한다"


def _compact(text: str, limit: int) -> str:
    cleaned = " ".join(str(text).split())
    return cleaned if len(cleaned) <= limit else cleaned[: limit - 1].rstrip() + "…"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _attach_meta(result: dict[str, Any], meta: dict[str, Any]) -> None:
    summary = dict(result.get("summary") or {})
    summary["llm"] = meta
    result["summary"] = summary
