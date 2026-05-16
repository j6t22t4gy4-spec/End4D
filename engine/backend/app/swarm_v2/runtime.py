"""Standalone Swarm V2 runtime.

Goal: one fast MiroFish-inspired session without depending on the legacy
Precision world graph. End4D concepts are injected as fields, pressure, roles,
zones, and causal event metadata after the swarm loop is already alive.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
import hashlib
import math
import random
import time
from typing import Any

from app.swarm_v2.llm_adapter import deliberate_stream_event, deliberate_stream_packet, enrich_result_with_llm


ROLE_POOL = [
    "시민",
    "소비자",
    "소규모 상점 경영자",
    "정책 담당자",
    "기업 관계자",
    "노동자",
    "지역 활동가",
    "시장 분석가",
]

KOREAN_NAMES = [
    "김도윤", "이서연", "박민준", "최지우", "정하늘", "강유진", "조현우", "윤서준",
    "장미래", "임태오", "한지민", "오세린", "서지훈", "문가영", "고문옥", "홍길동",
]


@dataclass
class SwarmV2Agent:
    agent_id: str
    name: str
    role: str
    zone: str
    x: float
    y: float
    pressure: float
    stance: float
    energy: float
    llm_channel: str
    identity: str
    cohort: str
    topic_affinity: str


@dataclass
class SwarmV2Event:
    event_id: str
    round: int
    event_index: int
    source_id: str
    target_id: str
    source_label: str
    target_label: str
    interaction_type: str
    intensity: float
    pressure_delta: float
    summary: str
    agent_thought: str
    agent_speech: str
    llm_channel: str
    llm_mode: str
    topic: str
    cohort: str
    active_agent_count: int
    participant_growth: int
    reply_to_event_id: str | None
    reply_depth: int
    source_memory: str
    target_memory: str
    relationship_score: float
    phase: str
    phase_index: int
    phase_progress: float


def run_session(
    *,
    prompt: str,
    agent_count: int = 1200,
    rounds: int = 48,
    events_per_round: int = 18,
    zone_count: int = 24,
    llm_mode: str = "hybrid",
    llm_sample_size: int = 96,
    llm_parallelism: int = 4,
    scenario_roles: list[str] | None = None,
    scenario_zones: list[str] | None = None,
) -> dict[str, Any]:
    seed = _seed(prompt)
    rng = random.Random(seed)
    full_agent_mode = _is_full_agent_mode(llm_mode)
    agent_count = max(32, min(10_000, int(agent_count)))
    rounds = max(4, min(160, int(rounds)))
    events_per_round = max(4, min(80, int(events_per_round)))
    zone_count = max(2, min(128, int(zone_count)))
    agents = _build_agents(
        prompt=prompt,
        count=agent_count,
        zone_count=zone_count,
        rng=rng,
        role_pool=scenario_roles,
        zone_labels=scenario_zones,
    )
    events: list[SwarmV2Event] = []
    pressure_acc = {agent.agent_id: 0.0 for agent in agents}
    participation = {agent.agent_id: 0 for agent in agents}
    agent_memory = {agent.agent_id: "" for agent in agents}
    relationship_memory: dict[tuple[str, str], float] = {}
    last_event_by_topic: dict[str, SwarmV2Event] = {}
    round_topics = _topic_ladder(prompt, rounds)
    scenario_focus = _scenario_focus(prompt)

    ranked = sorted(agents, key=lambda agent: (-agent.pressure, abs(agent.stance), agent.agent_id))
    previous_active_count = 0
    for round_index in range(1, rounds + 1):
        progress = round_index / max(1, rounds)
        phase, phase_index, phase_progress = _session_phase(progress)
        active_count = max(12, min(agent_count, int(agent_count * _growth_curve(progress))))
        participant_growth = max(0, active_count - previous_active_count)
        previous_active_count = active_count
        topic = round_topics[round_index - 1]
        active = _active_pool(ranked, round_index=round_index, active_count=active_count, topic=topic)
        for local_index in range(events_per_round):
            previous = last_event_by_topic.get(topic)
            source = _source_for(active, previous=previous, round_index=round_index, local_index=local_index)
            target = _target_for(source, active, rng=rng, round_index=round_index, local_index=local_index, topic=topic, previous=previous)
            if target is None:
                continue
            relation_key = _relation_key(source.agent_id, target.agent_id)
            relation = relationship_memory.get(relation_key, 0.0)
            tone = _tone(source, target, relation=relation, topic=topic, phase=phase)
            intensity = _intensity(source, target, tone, relation=relation, topic=topic, phase=phase)
            delta = _pressure_delta(tone, intensity)
            pressure_acc[source.agent_id] += delta
            pressure_acc[target.agent_id] += delta
            participation[source.agent_id] += 1
            participation[target.agent_id] += 1
            reply_depth = (previous.reply_depth + 1) if previous and local_index % 3 != 0 else 0
            relationship_memory[relation_key] = _next_relation_score(relation, tone, intensity)
            source_memory = _next_memory(source, target, tone, topic, agent_memory[source.agent_id])
            target_memory = _next_memory(target, source, tone, topic, agent_memory[target.agent_id])
            agent_memory[source.agent_id] = source_memory
            agent_memory[target.agent_id] = target_memory
            event_id = f"swarm-v2-{round_index}-{len(events) + 1}"
            event = SwarmV2Event(
                event_id=event_id,
                round=round_index,
                event_index=len(events) + 1,
                source_id=source.agent_id,
                target_id=target.agent_id,
                source_label=_agent_label(source),
                target_label=_agent_label(target),
                interaction_type=tone,
                intensity=intensity,
                pressure_delta=delta,
                summary=_summary(source, target, tone, topic, previous, source_memory, phase, scenario_focus),
                agent_thought=_agent_thought(source, target, tone, topic, source_memory, scenario_focus, previous),
                agent_speech=_agent_speech(source, target, tone, topic, scenario_focus),
                llm_channel=_llm_channel(source, target, local_index),
                llm_mode="agent" if full_agent_mode or local_index % 5 == 0 else "packet",
                topic=topic,
                cohort=source.cohort if source.cohort == target.cohort else "cross-cohort",
                active_agent_count=active_count,
                participant_growth=participant_growth if local_index == 0 else 0,
                reply_to_event_id=previous.event_id if previous and local_index % 3 != 0 else None,
                reply_depth=reply_depth,
                source_memory=source_memory,
                target_memory=target_memory,
                relationship_score=round(relationship_memory[relation_key], 4),
                phase=phase,
                phase_index=phase_index,
                phase_progress=phase_progress,
            )
            events.append(
                event
            )
            last_event_by_topic[topic] = event

    committed_agents = []
    for idx, agent in enumerate(agents):
        drift = min(0.35, participation[agent.agent_id] * 0.006)
        angle = idx * 2.399963 + pressure_acc[agent.agent_id] * 3.0
        item = asdict(agent)
        item["x"] = round(agent.x + math.cos(angle) * drift, 4)
        item["y"] = round(agent.y + math.sin(angle) * drift, 4)
        item["pressure"] = round(max(0.0, min(1.0, agent.pressure + pressure_acc[agent.agent_id] * 0.08)), 4)
        item["participation"] = participation[agent.agent_id]
        committed_agents.append(item)
    outcome = _outcome_summary(
        agents=committed_agents,
        events=events,
        participation=participation,
        pressure_acc=pressure_acc,
    )

    result = {
        "runtime": "swarm-v2-cleanroom",
        "prompt": prompt,
        "agent_count": agent_count,
        "rounds": rounds,
        "events_per_round": events_per_round,
        "zone_count": zone_count,
        "llm_mode": llm_mode,
        "llm_parallelism": max(1, min(16, int(llm_parallelism))),
        "agents": committed_agents,
        "events": [asdict(event) for event in events],
        "summary": {
            "event_count": len(events),
            "active_agent_count": sum(1 for value in participation.values() if value > 0),
            "avg_pressure": round(sum(agent["pressure"] for agent in committed_agents) / max(1, len(committed_agents)), 4),
            "max_pressure": round(max(agent["pressure"] for agent in committed_agents), 4),
            "topic_count": len(set(round_topics)),
            "agent_channel_events": sum(1 for event in events if event.llm_mode == "agent"),
            "packet_channel_events": sum(1 for event in events if event.llm_mode == "packet"),
            "reply_chain_events": sum(1 for event in events if event.reply_to_event_id),
            "max_reply_depth": max((event.reply_depth for event in events), default=0),
            "phases": _phase_summary(events),
            "outcome": outcome,
        },
    }
    return enrich_result_with_llm(result, mode=llm_mode, sample_size=llm_sample_size)


def create_streaming_session_seed(
    *,
    prompt: str,
    agent_count: int = 1200,
    rounds: int = 48,
    events_per_round: int = 18,
    zone_count: int = 24,
    llm_mode: str = "hybrid",
    llm_sample_size: int = 96,
    llm_parallelism: int = 4,
    scenario_roles: list[str] | None = None,
    scenario_zones: list[str] | None = None,
) -> dict[str, Any]:
    seed = _seed(prompt)
    rng = random.Random(seed)
    agent_count = max(32, min(10_000, int(agent_count)))
    rounds = max(4, min(160, int(rounds)))
    events_per_round = max(4, min(80, int(events_per_round)))
    zone_count = max(2, min(128, int(zone_count)))
    agents = _build_agents(
        prompt=prompt,
        count=agent_count,
        zone_count=zone_count,
        rng=rng,
        role_pool=scenario_roles,
        zone_labels=scenario_zones,
    )
    return {
        "runtime": "swarm-v2-streaming-loop",
        "prompt": prompt,
        "agent_count": agent_count,
        "rounds": rounds,
        "events_per_round": events_per_round,
        "zone_count": zone_count,
        "llm_mode": llm_mode,
        "llm_sample_size": llm_sample_size,
        "llm_parallelism": max(1, min(16, int(llm_parallelism))),
        "agents": [asdict(agent) for agent in agents],
        "events": [],
        "summary": {
            "event_count": 0,
            "expected_event_count": rounds * events_per_round,
            "active_agent_count": 0,
            "avg_pressure": round(sum(agent.pressure for agent in agents) / max(1, len(agents)), 4),
            "max_pressure": round(max(agent.pressure for agent in agents), 4),
            "topic_count": len(set(_topic_ladder(prompt, rounds))),
            "llm": {
                "mode": llm_mode,
                "sample_size": llm_sample_size,
                "used": False,
                "enriched_events": 0,
                "action_feedback_events": 0,
                "streaming_loop": True,
            },
            "phases": [],
            "outcome": None,
        },
        "stream_state": {
            "seed": seed,
            "round_topics": _topic_ladder(prompt, rounds),
            "scenario_focus": _scenario_focus(prompt),
        },
    }


def iter_streaming_events(result: dict[str, Any]):
    prompt = str(result.get("prompt") or "")
    rounds = int(result.get("rounds") or 4)
    events_per_round = int(result.get("events_per_round") or 4)
    llm_mode = str(result.get("llm_mode") or "packet")
    full_agent_mode = _is_full_agent_mode(llm_mode)
    llm_sample_size = max(0, int(result.get("llm_sample_size") or 0))
    llm_parallelism = max(1, min(16, int(result.get("llm_parallelism") or 1)))
    seed = int((result.get("stream_state") or {}).get("seed") or _seed(prompt))
    rng = random.Random(seed)
    agents = [_agent_from_dict(item) for item in list(result.get("agents") or [])]
    pressure_acc = {agent.agent_id: 0.0 for agent in agents}
    participation = {agent.agent_id: 0 for agent in agents}
    agent_memory = {agent.agent_id: "" for agent in agents}
    relationship_memory: dict[tuple[str, str], float] = {}
    last_event_by_topic: dict[str, SwarmV2Event] = {}
    round_topics = list((result.get("stream_state") or {}).get("round_topics") or _topic_ladder(prompt, rounds))
    scenario_focus = str((result.get("stream_state") or {}).get("scenario_focus") or _scenario_focus(prompt))
    ranked = sorted(agents, key=lambda agent: (-agent.pressure, abs(agent.stance), agent.agent_id))
    previous_active_count = 0
    events: list[SwarmV2Event] = []
    live_llm_used = 0
    live_llm_feedback = 0
    full_agent_buffer: list[tuple[SwarmV2Event, dict[str, Any]]] = []

    def flush_full_agent_buffer():
        nonlocal live_llm_used, live_llm_feedback
        if not full_agent_buffer:
            return
        batch = list(full_agent_buffer)
        full_agent_buffer.clear()
        event_dicts = [item[1] for item in batch]
        yield {
            "_stream_type": "llm_log",
            "status": "batch_started",
            "task": "swarm_agent",
            "event_ids": [str(item.get("event_id") or "") for item in event_dicts],
            "batch_size": len(event_dicts),
            "parallelism": llm_parallelism,
            "topic": str(event_dicts[0].get("topic") or "") if event_dicts else "",
        }
        started_at = time.perf_counter()
        enriched_events = _deliberate_stream_event_batch(
            event_dicts,
            agents=list(result.get("agents") or []),
            previous_events=list(result.get("events") or []),
            scenario=prompt,
            parallelism=llm_parallelism,
        )
        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)
        for event_obj, event_dict in zip([item[0] for item in batch], enriched_events):
            if event_dict.get("llm_enriched"):
                live_llm_used += 1
            _apply_rule_action_feedback(
                event_dict,
                relationship_memory,
                agent_memory=agent_memory,
                pressure_acc=pressure_acc,
            )
            if event_dict.get("llm_action_effect") is not None:
                live_llm_feedback += 1
            events.append(event_obj)
            result.setdefault("events", []).append(event_dict)
            yield {
                "_stream_type": "llm_log",
                "status": "completed" if event_dict.get("llm_enriched") else "fallback",
                "task": "swarm_agent",
                "event_id": str(event_dict.get("event_id") or ""),
                "source_label": str(event_dict.get("source_label") or ""),
                "target_label": str(event_dict.get("target_label") or ""),
                "topic": str(event_dict.get("topic") or ""),
                "batch_size": len(event_dicts),
                "parallelism": llm_parallelism,
                "elapsed_ms": elapsed_ms,
                "llm_enriched": bool(event_dict.get("llm_enriched")),
                "fallback_reason": str(event_dict.get("llm_fallback_reason") or ""),
            }
            yield event_dict
    for round_index in range(1, rounds + 1):
        progress = round_index / max(1, rounds)
        phase, phase_index, phase_progress = _session_phase(progress)
        active_count = max(12, min(len(agents), int(len(agents) * _growth_curve(progress))))
        participant_growth = max(0, active_count - previous_active_count)
        previous_active_count = active_count
        topic = round_topics[(round_index - 1) % len(round_topics)]
        active = _active_pool(ranked, round_index=round_index, active_count=active_count, topic=topic)
        for local_index in range(events_per_round):
            previous = last_event_by_topic.get(topic)
            source = _source_for(active, previous=previous, round_index=round_index, local_index=local_index)
            target = _target_for(source, active, rng=rng, round_index=round_index, local_index=local_index, topic=topic, previous=previous)
            if target is None:
                continue
            relation_key = _relation_key(source.agent_id, target.agent_id)
            relation = relationship_memory.get(relation_key, 0.0)
            tone = _tone(source, target, relation=relation, topic=topic, phase=phase)
            intensity = _intensity(source, target, tone, relation=relation, topic=topic, phase=phase)
            delta = _pressure_delta(tone, intensity)
            pressure_acc[source.agent_id] += delta
            pressure_acc[target.agent_id] += delta
            participation[source.agent_id] += 1
            participation[target.agent_id] += 1
            reply_depth = (previous.reply_depth + 1) if previous and local_index % 3 != 0 else 0
            relationship_memory[relation_key] = _next_relation_score(relation, tone, intensity)
            source_memory = _next_memory(source, target, tone, topic, agent_memory[source.agent_id])
            target_memory = _next_memory(target, source, tone, topic, agent_memory[target.agent_id])
            agent_memory[source.agent_id] = source_memory
            agent_memory[target.agent_id] = target_memory
            event = SwarmV2Event(
                event_id=f"swarm-v2-{round_index}-{len(events) + 1}",
                round=round_index,
                event_index=len(events) + 1,
                source_id=source.agent_id,
                target_id=target.agent_id,
                source_label=_agent_label(source),
                target_label=_agent_label(target),
                interaction_type=tone,
                intensity=intensity,
                pressure_delta=delta,
                summary=_summary(source, target, tone, topic, previous, source_memory, phase, scenario_focus),
                agent_thought=_agent_thought(source, target, tone, topic, source_memory, scenario_focus, previous),
                agent_speech=_agent_speech(source, target, tone, topic, scenario_focus),
                llm_channel=_llm_channel(source, target, local_index),
                llm_mode="agent" if full_agent_mode or local_index % 5 == 0 else "packet",
                topic=topic,
                cohort=source.cohort if source.cohort == target.cohort else "cross-cohort",
                active_agent_count=active_count,
                participant_growth=participant_growth if local_index == 0 else 0,
                reply_to_event_id=previous.event_id if previous and local_index % 3 != 0 else None,
                reply_depth=reply_depth,
                source_memory=source_memory,
                target_memory=target_memory,
                relationship_score=round(relationship_memory[relation_key], 4),
                phase=phase,
                phase_index=phase_index,
                phase_progress=phase_progress,
            )
            event_dict = asdict(event)
            if full_agent_mode:
                yield {
                    "_stream_type": "agent_thinking",
                    "session_event_id": event.event_id,
                    "round": event.round,
                    "event_index": event.event_index,
                    "source_id": event.source_id,
                    "target_id": event.target_id,
                    "source_label": event.source_label,
                    "target_label": event.target_label,
                    "topic": event.topic,
                    "phase": event.phase,
                    "llm_mode": "full-agent",
                }
                full_agent_buffer.append((event, event_dict))
                last_event_by_topic[topic] = event
                if len(full_agent_buffer) >= llm_parallelism:
                    yield from flush_full_agent_buffer()
                continue
            elif (
                llm_mode in {"packet", "hybrid"}
                and local_index == 0
                and live_llm_used < llm_sample_size
            ):
                deliberate_stream_packet(
                    event_dict,
                    previous_events=list(result.get("events") or []),
                    scenario=prompt,
                )
                if event_dict.get("llm_enriched"):
                    live_llm_used += 1
            elif (
                llm_mode in {"agent", "hybrid"}
                and event_dict.get("llm_mode") == "agent"
                and live_llm_used < llm_sample_size
            ):
                deliberate_stream_event(
                    event_dict,
                    agents=list(result.get("agents") or []),
                    previous_events=list(result.get("events") or []),
                    scenario=prompt,
                )
                if event_dict.get("llm_enriched"):
                    live_llm_used += 1
            _apply_rule_action_feedback(
                event_dict,
                relationship_memory,
                agent_memory=agent_memory,
                pressure_acc=pressure_acc,
            )
            if event_dict.get("llm_action_effect") is not None:
                live_llm_feedback += 1
            events.append(event)
            result.setdefault("events", []).append(event_dict)
            last_event_by_topic[topic] = event
            yield event_dict
        if full_agent_mode:
            yield from flush_full_agent_buffer()
    _finalize_streaming_result(
        result,
        agents=agents,
        participation=participation,
        pressure_acc=pressure_acc,
        events=events,
        live_llm_used=live_llm_used,
        live_llm_feedback=live_llm_feedback,
    )


def _deliberate_stream_event_batch(
    events: list[dict[str, Any]],
    *,
    agents: list[dict[str, Any]],
    previous_events: list[dict[str, Any]],
    scenario: str,
    parallelism: int,
) -> list[dict[str, Any]]:
    if not events:
        return []
    workers = max(1, min(16, int(parallelism)))
    if workers <= 1 or len(events) <= 1:
        return [
            deliberate_stream_event(
                event,
                agents=agents,
                previous_events=previous_events,
                scenario=scenario,
            )
            for event in events
        ]
    ordered: list[dict[str, Any] | None] = [None] * len(events)
    with ThreadPoolExecutor(max_workers=min(workers, len(events))) as executor:
        futures = {
            executor.submit(
                deliberate_stream_event,
                event,
                agents=agents,
                previous_events=previous_events,
                scenario=scenario,
            ): index
            for index, event in enumerate(events)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                ordered[index] = future.result()
            except Exception as exc:
                fallback_event = events[index]
                fallback_event["llm_fallback_reason"] = f"provider_error:{type(exc).__name__}"
                ordered[index] = fallback_event
    return [event if event is not None else events[index] for index, event in enumerate(ordered)]


def _apply_rule_action_feedback(
    event: dict[str, Any],
    relationship_memory: dict[tuple[str, str], float],
    *,
    agent_memory: dict[str, str] | None = None,
    pressure_acc: dict[str, float] | None = None,
) -> None:
    # Streaming-first mode cannot wait for all events. Give every agent-channel
    # event a small immediate action residue so later target selection sees it.
    if str(event.get("llm_mode") or "") != "agent":
        return
    tone = str(event.get("interaction_type") or "dialogue")
    relation_delta = _safe_float(event.get("decision_relation_delta"), None)
    pressure_delta = _safe_float(event.get("decision_pressure_delta"), 0.0) or 0.0
    effect = float(
        relation_delta
        if relation_delta is not None
        else event.get("llm_action_effect") or (0.08 if tone == "positive" else -0.08 if tone in {"negative", "hostile"} else 0.03)
    )
    key = _relation_key(str(event.get("source_id") or ""), str(event.get("target_id") or ""))
    relationship_memory[key] = round(max(-1.0, min(1.0, relationship_memory.get(key, 0.0) + effect)), 4)
    event["relationship_score"] = relationship_memory[key]
    if pressure_acc is not None and abs(pressure_delta) > 0.0001:
        source_id = str(event.get("source_id") or "")
        target_id = str(event.get("target_id") or "")
        pressure_acc[source_id] = pressure_acc.get(source_id, 0.0) + pressure_delta
        pressure_acc[target_id] = pressure_acc.get(target_id, 0.0) + pressure_delta * 0.45
        event["pressure_delta"] = round(float(event.get("pressure_delta") or 0.0) + pressure_delta, 4)
    if agent_memory is not None and event.get("memory_write"):
        source_id = str(event.get("source_id") or "")
        merged_memory = _merge_memory(str(agent_memory.get(source_id) or ""), str(event.get("memory_write") or ""))
        agent_memory[source_id] = merged_memory
        event["source_memory"] = merged_memory
    event["llm_action"] = event.get("llm_action") or "Reply"
    event["llm_reasoning"] = event.get("llm_reasoning") or "streaming loop에서 이 에이전트가 현재 피드에 즉시 반응했다"
    event["llm_action_effect"] = round(effect, 4)


def _is_full_agent_mode(mode: str) -> bool:
    return str(mode or "").strip().lower().replace("_", "-") in {"full-agent", "all-agent", "agent-full"}


def _finalize_streaming_result(
    result: dict[str, Any],
    *,
    agents: list[SwarmV2Agent],
    participation: dict[str, int],
    pressure_acc: dict[str, float],
    events: list[SwarmV2Event],
    live_llm_used: int = 0,
    live_llm_feedback: int = 0,
) -> None:
    committed_agents = []
    for idx, agent in enumerate(agents):
        drift = min(0.35, participation[agent.agent_id] * 0.006)
        angle = idx * 2.399963 + pressure_acc[agent.agent_id] * 3.0
        item = asdict(agent)
        item["x"] = round(agent.x + math.cos(angle) * drift, 4)
        item["y"] = round(agent.y + math.sin(angle) * drift, 4)
        item["pressure"] = round(max(0.0, min(1.0, agent.pressure + pressure_acc[agent.agent_id] * 0.08)), 4)
        item["participation"] = participation[agent.agent_id]
        committed_agents.append(item)
    result["agents"] = committed_agents
    summary = dict(result.get("summary") or {})
    summary.update(
        {
            "event_count": len(events),
            "active_agent_count": sum(1 for value in participation.values() if value > 0),
            "avg_pressure": round(sum(agent["pressure"] for agent in committed_agents) / max(1, len(committed_agents)), 4),
            "max_pressure": round(max(agent["pressure"] for agent in committed_agents), 4),
            "agent_channel_events": sum(1 for event in events if event.llm_mode == "agent"),
            "packet_channel_events": sum(1 for event in events if event.llm_mode == "packet"),
            "reply_chain_events": sum(1 for event in events if event.reply_to_event_id),
            "max_reply_depth": max((event.reply_depth for event in events), default=0),
            "phases": _phase_summary(events),
            "outcome": _outcome_summary(
                agents=committed_agents,
                events=events,
                participation=participation,
                pressure_acc=pressure_acc,
            ),
        }
    )
    llm_meta = dict(summary.get("llm") or {})
    llm_meta.update(
        {
            "used": live_llm_used > 0,
            "enriched_events": live_llm_used,
            "action_feedback_events": live_llm_feedback,
            "streaming_loop": True,
        }
    )
    summary["llm"] = llm_meta
    result["summary"] = summary


def _agent_from_dict(item: dict[str, Any]) -> SwarmV2Agent:
    return SwarmV2Agent(
        agent_id=str(item.get("agent_id") or ""),
        name=str(item.get("name") or ""),
        role=str(item.get("role") or ""),
        zone=str(item.get("zone") or ""),
        x=float(item.get("x") or 0.0),
        y=float(item.get("y") or 0.0),
        pressure=float(item.get("pressure") or 0.0),
        stance=float(item.get("stance") or 0.0),
        energy=float(item.get("energy") or 0.0),
        llm_channel=str(item.get("llm_channel") or ""),
        identity=str(item.get("identity") or ""),
        cohort=str(item.get("cohort") or ""),
        topic_affinity=str(item.get("topic_affinity") or ""),
    )


def _build_agents(
    *,
    prompt: str,
    count: int,
    zone_count: int,
    rng: random.Random,
    role_pool: list[str] | None = None,
    zone_labels: list[str] | None = None,
) -> list[SwarmV2Agent]:
    prompt_bias = (_seed(prompt) % 1000) / 1000
    zones = [str(label).strip() for label in (zone_labels or []) if str(label).strip()]
    agents = []
    for idx in range(count):
        role = _role_for_prompt(prompt, idx, role_pool=role_pool)
        zone_idx = idx % zone_count
        zone_label = zones[zone_idx % len(zones)] if zones else f"zone-{zone_idx + 1}"
        cohort = _cohort(role, zone_idx)
        affinity = _extract_keywords(prompt)[idx % len(_extract_keywords(prompt))]
        theta = math.tau * ((zone_idx / zone_count) + rng.random() * 0.12)
        radius = 2.0 + zone_idx * 0.12 + rng.random() * 1.8
        name = KOREAN_NAMES[idx % len(KOREAN_NAMES)]
        agent_id = f"sv2-{idx:05d}"
        stance = max(-1.0, min(1.0, math.sin(idx * 0.73 + prompt_bias * 4.0)))
        pressure = max(0.05, min(0.95, 0.22 + abs(stance) * 0.24 + rng.random() * 0.18))
        agents.append(
            SwarmV2Agent(
                agent_id=agent_id,
                name=f"{name}{idx // len(KOREAN_NAMES) + 1}",
                role=role,
                zone=zone_label,
                x=round(math.cos(theta) * radius + rng.uniform(-0.18, 0.18), 4),
                y=round(math.sin(theta) * radius + rng.uniform(-0.18, 0.18), 4),
                pressure=round(pressure, 4),
                stance=round(stance, 4),
                energy=round(0.45 + rng.random() * 0.5, 4),
                llm_channel=f"agent:{agent_id}",
                identity=f"{name}{idx // len(KOREAN_NAMES) + 1} · {role} · {cohort}",
                cohort=cohort,
                topic_affinity=affinity,
            )
        )
    return agents


def _source_for(active: list[SwarmV2Agent], *, previous: SwarmV2Event | None, round_index: int, local_index: int) -> SwarmV2Agent:
    if previous and local_index % 3 != 0:
        for agent in active:
            if agent.agent_id == previous.target_id:
                return agent
    return active[(round_index * 17 + local_index * 7) % len(active)]


def _target_for(
    source: SwarmV2Agent,
    active: list[SwarmV2Agent],
    *,
    rng: random.Random,
    round_index: int,
    local_index: int,
    topic: str,
    previous: SwarmV2Event | None,
) -> SwarmV2Agent | None:
    if len(active) < 2:
        return None
    candidates = [
        agent for agent in active
        if agent.agent_id != source.agent_id
        and (
            agent.zone == source.zone
            or abs(agent.stance - source.stance) > 0.22
            or agent.topic_affinity in topic
            or source.topic_affinity in topic
        )
    ]
    if previous and local_index % 3 != 0:
        reply_candidates = [agent for agent in candidates if agent.agent_id == previous.source_id]
        if reply_candidates:
            return reply_candidates[0]
    if not candidates:
        candidates = [agent for agent in active if agent.agent_id != source.agent_id]
    return candidates[(round_index * 11 + local_index * 5 + rng.randrange(len(candidates))) % len(candidates)]


def _tone(source: SwarmV2Agent, target: SwarmV2Agent, *, relation: float, topic: str, phase: str) -> str:
    gap = abs(source.stance - target.stance)
    pressure = (source.pressure + target.pressure) / 2
    affinity = 0.12 if source.topic_affinity in topic or target.topic_affinity in topic else 0.0
    phase_tension = 0.14 if phase in {"escalation", "branching"} else -0.08 if phase in {"convergence", "outcome"} else 0.0
    if gap - relation + phase_tension > 1.05 or pressure + phase_tension > 0.72:
        return "hostile"
    if gap - relation + phase_tension > 0.54 or pressure + phase_tension > 0.5:
        return "negative"
    if source.role == target.role or source.zone == target.zone or relation + affinity - phase_tension > 0.2:
        return "positive"
    return "dialogue"


def _intensity(source: SwarmV2Agent, target: SwarmV2Agent, tone: str, *, relation: float, topic: str, phase: str) -> float:
    base = abs(source.stance - target.stance) * 0.34 + (source.pressure + target.pressure) * 0.26
    if source.topic_affinity in topic or target.topic_affinity in topic:
        base += 0.08
    base += abs(relation) * 0.12
    if phase == "opening":
        base *= 0.78
    elif phase == "escalation":
        base *= 1.22
    elif phase == "branching":
        base *= 1.12
    elif phase == "convergence":
        base *= 0.92
    elif phase == "outcome":
        base *= 0.82
    if tone == "hostile":
        base += 0.25
    elif tone == "negative":
        base += 0.14
    elif tone == "positive":
        base += 0.08
    return round(max(0.12, min(1.0, base)), 4)


def _pressure_delta(tone: str, intensity: float) -> float:
    sign = -1.0 if tone == "positive" else 1.0 if tone in {"negative", "hostile"} else 0.2
    return round(sign * min(0.16, intensity * 0.05), 4)


def _relation_key(source_id: str, target_id: str) -> tuple[str, str]:
    return tuple(sorted((source_id, target_id)))  # type: ignore[return-value]


def _next_relation_score(previous: float, tone: str, intensity: float) -> float:
    if tone == "positive":
        delta = 0.08 + intensity * 0.05
    elif tone == "dialogue":
        delta = 0.02
    elif tone == "negative":
        delta = -0.06 - intensity * 0.04
    else:
        delta = -0.12 - intensity * 0.06
    return round(max(-1.0, min(1.0, previous * 0.88 + delta)), 4)


def _next_memory(source: SwarmV2Agent, target: SwarmV2Agent, tone: str, topic: str, previous: str) -> str:
    topic_core = _topic_core(topic)
    if tone == "positive":
        phrase = f"{target.name}도 {topic_core}에서는 협력 여지가 있다고 느낌"
    elif tone == "dialogue":
        phrase = f"{target.name}의 반응을 더 들어봐야겠다고 느낌"
    elif tone == "negative":
        phrase = f"{target.name}의 말이 {topic_core} 문제의 불안을 키운다고 느낌"
    else:
        phrase = f"{target.name}과 정면 충돌했고 다음 발언을 경계함"
    pieces = [item.strip() for item in str(previous or "").split(";") if item.strip()]
    pieces = [item for item in pieces if item != phrase][-3:]
    pieces.append(phrase)
    return "; ".join(pieces)[-180:]


def _merge_memory(previous: str, memory_write: str) -> str:
    phrase = str(memory_write or "").strip()
    if not phrase:
        return previous
    pieces = [item.strip() for item in str(previous or "").split(";") if item.strip()]
    pieces = [item for item in pieces if item != phrase][-3:]
    pieces.append(phrase)
    return "; ".join(pieces)[-240:]


def _safe_float(value: Any, fallback: float | None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _agent_label(agent: SwarmV2Agent) -> str:
    return f"{agent.name}({agent.role})"


def _topic_core(topic: str) -> str:
    core = str(topic or "핵심 이슈").split(" · ")[0].strip()
    for suffix in ("과", "와", "이", "가", "은", "는", "을", "를"):
        if len(core) > 2 and core.endswith(suffix):
            return core[: -len(suffix)]
    return core


def _agent_thought(
    source: SwarmV2Agent,
    target: SwarmV2Agent,
    tone: str,
    topic: str,
    source_memory: str,
    scenario_focus: str,
    previous: SwarmV2Event | None,
) -> str:
    topic_core = _topic_core(topic)
    prior = f"방금 {getattr(previous, 'source_label', '누군가')}의 흐름을 들은 뒤, " if previous else ""
    if tone == "positive":
        inner = f"{target.name}도 {topic_core}에서 완전히 반대편은 아니구나. 내 입장에서도 같이 밀어볼 말이 있다."
    elif tone == "dialogue":
        inner = f"{target.name}이 왜 저렇게 보는지 더 들어봐야겠다. 성급히 편을 가르기보다 내 조건을 확인해야 한다."
    elif tone == "negative":
        inner = f"{target.name}의 말은 내 처지에는 부담으로 돌아올 수 있다. {topic_core} 문제가 좋게만 끝나지는 않겠다는 불안이 든다."
    else:
        inner = f"{target.name}의 말은 그냥 넘길 수 없다. 여기서 물러나면 내 쪽 사람들이 손해를 볼 것 같다."
    return (
        f"{source.name}은 {source.role}로서 {scenario_focus} 상황을 자기 문제로 받아들인다. "
        f"{prior}{inner} 최근 기억: {source_memory}"
    )


def _agent_speech(source: SwarmV2Agent, target: SwarmV2Agent, tone: str, topic: str, scenario_focus: str) -> str:
    topic_core = _topic_core(topic)
    if tone == "positive":
        return f"{target.name}님, {topic_core}에서 우리도 같이 요구할 수 있는 부분이 있어요. {source.role} 입장에서도 그 길은 현실적입니다."
    if tone == "dialogue":
        return f"{target.name}님, 지금 말한 게 {topic_core}에 어떤 영향을 준다는 건지 더 듣고 싶어요. 제 상황에서는 아직 판단이 쉽지 않습니다."
    if tone == "negative":
        return f"{target.name}님, 그 주장은 {source.role} 입장에서는 부담이 큽니다. 이 상황이 그렇게 단순하게 해결되진 않아요."
    return f"{target.name}님, 그 말은 받아들이기 어렵습니다. {topic_core} 문제에서 제 쪽이 감당해야 할 손실을 너무 가볍게 보고 있어요."


def _summary(
    source: SwarmV2Agent,
    target: SwarmV2Agent,
    tone: str,
    topic: str,
    previous: SwarmV2Event | None,
    source_memory: str,
    phase: str,
    scenario_focus: str,
) -> str:
    if tone == "positive":
        verb = "그 말에 기대어 같은 해법을 확인했다"
    elif tone == "negative":
        verb = "방금 나온 주장에 불안을 드러냈다"
    elif tone == "hostile":
        verb = "이전 발언을 받아치며 강하게 충돌했다"
    else:
        verb = "상대의 반응을 확인하며 상황을 탐색했다"
    phase_text = {
        "opening": "장면이 열리며",
        "escalation": "긴장이 커지는 가운데",
        "branching": "논점이 갈라지며",
        "convergence": "수렴 가능한 해법을 찾으며",
        "outcome": "이번 판의 결론을 남기며",
    }.get(phase, "흐름 속에서")
    previous_label = getattr(previous, "source_label", "이전 발언자") if previous else ""
    prefix = f"{phase_text} 새 쟁점으로" if previous is None else f"{phase_text} {previous_label}의 발언을 이어"
    return f"{prefix}, {_agent_label(source)}이 {_agent_label(target)}와 '{topic}' 쟁점을 두고 {verb}."


def _growth_curve(progress: float) -> float:
    # Fast early expansion, then saturation: one session feels like a crowd
    # forming around the issue rather than a fixed static roster.
    return min(0.94, 0.08 + 0.88 * (1 - math.exp(-3.2 * progress)))


def _session_phase(progress: float) -> tuple[str, int, float]:
    phases = [
        ("opening", 0.0, 0.18),
        ("escalation", 0.18, 0.42),
        ("branching", 0.42, 0.68),
        ("convergence", 0.68, 0.88),
        ("outcome", 0.88, 1.01),
    ]
    for idx, (name, start, end) in enumerate(phases):
        if start <= progress < end:
            local = (progress - start) / max(0.001, end - start)
            return name, idx, round(max(0.0, min(1.0, local)), 4)
    return "outcome", len(phases) - 1, 1.0


def _phase_summary(events: list[SwarmV2Event]) -> list[dict[str, Any]]:
    order = ["opening", "escalation", "branching", "convergence", "outcome"]
    return [
        {
            "phase": phase,
            "events": sum(1 for event in events if event.phase == phase),
            "avg_intensity": round(
                sum(event.intensity for event in events if event.phase == phase)
                / max(1, sum(1 for event in events if event.phase == phase)),
                4,
            ),
        }
        for phase in order
    ]


def _outcome_summary(
    *,
    agents: list[dict[str, Any]],
    events: list[SwarmV2Event],
    participation: dict[str, int],
    pressure_acc: dict[str, float],
) -> dict[str, Any]:
    by_id = {agent["agent_id"]: agent for agent in agents}
    cohort_stats: dict[str, dict[str, Any]] = {}
    for agent in agents:
        cohort = str(agent.get("cohort") or "unknown")
        stats = cohort_stats.setdefault(cohort, {"cohort": cohort, "participants": 0, "pressure": 0.0, "stance": 0.0, "events": 0})
        stats["participants"] += 1
        stats["pressure"] += float(agent.get("pressure") or 0.0)
        stats["stance"] += abs(float(agent.get("stance") or 0.0))
        stats["events"] += participation.get(str(agent.get("agent_id")), 0)
    coalitions = []
    for stats in cohort_stats.values():
        participants = max(1, int(stats["participants"]))
        event_count = max(1, int(stats["events"]))
        score = (stats["events"] * 0.58) + (stats["pressure"] / participants * 34) + (stats["stance"] / participants * 14)
        coalitions.append(
            {
                "cohort": stats["cohort"],
                "participants": participants,
                "events": int(stats["events"]),
                "avg_pressure": round(stats["pressure"] / participants, 4),
                "avg_stance_abs": round(stats["stance"] / participants, 4),
                "score": round(score / event_count, 4),
            }
        )
    coalitions.sort(key=lambda item: (item["events"], item["avg_pressure"], item["avg_stance_abs"]), reverse=True)
    dominant = coalitions[0] if coalitions else {"cohort": "unknown", "events": 0, "avg_pressure": 0.0}
    losers = sorted(coalitions[1:], key=lambda item: (item["events"], item["avg_pressure"]))[:2]
    hostile_events = [event for event in events if event.interaction_type in {"hostile", "negative"}]
    unresolved = sorted(hostile_events, key=lambda event: (event.intensity, abs(event.relationship_score)), reverse=True)[:4]
    handoff_agents = sorted(
        agents,
        key=lambda agent: (
            participation.get(str(agent.get("agent_id")), 0),
            abs(pressure_acc.get(str(agent.get("agent_id")), 0.0)),
            float(agent.get("pressure") or 0.0),
        ),
        reverse=True,
    )[:8]
    outcome_events = [event for event in events if event.phase == "outcome"]
    final_tone = _dominant_tone(outcome_events or events)
    return {
        "dominant_coalition": dominant,
        "weaker_coalitions": losers,
        "final_tone": final_tone,
        "unresolved_tensions": [
            {
                "topic": event.topic,
                "event_id": event.event_id,
                "tone": event.interaction_type,
                "intensity": event.intensity,
                "relationship_score": event.relationship_score,
                "summary": event.summary,
            }
            for event in unresolved
        ],
        "precision_handoff": [
            {
                "agent_id": str(agent.get("agent_id")),
                "identity": str(agent.get("identity") or agent.get("name")),
                "role": str(agent.get("role")),
                "cohort": str(agent.get("cohort")),
                "pressure": float(agent.get("pressure") or 0.0),
                "participation": participation.get(str(agent.get("agent_id")), 0),
            }
            for agent in handoff_agents
        ],
        "verdict": _verdict(dominant, final_tone, unresolved),
    }


def _dominant_tone(events: list[SwarmV2Event]) -> str:
    if not events:
        return "dialogue"
    counts: dict[str, float] = {}
    for event in events:
        counts[event.interaction_type] = counts.get(event.interaction_type, 0.0) + event.intensity
    return max(counts.items(), key=lambda item: item[1])[0]


def _verdict(dominant: dict[str, Any], final_tone: str, unresolved: list[SwarmV2Event]) -> str:
    cohort = dominant.get("cohort", "unknown")
    if final_tone == "positive" and len(unresolved) <= 2:
        return f"{cohort} coalition이 주도권을 잡았고, 갈등은 제한적으로 수렴했다."
    if final_tone in {"hostile", "negative"}:
        return f"{cohort} coalition이 장을 지배했지만, 미해결 긴장이 다음 판으로 넘어간다."
    return f"{cohort} coalition이 가장 크게 부상했지만, 결론은 탐색 상태로 남았다."


def _active_pool(ranked: list[SwarmV2Agent], *, round_index: int, active_count: int, topic: str) -> list[SwarmV2Agent]:
    topic_seed = _seed(topic) % max(1, len(ranked))
    stride = 3 + (round_index % 11)
    active: list[SwarmV2Agent] = []
    used: set[str] = set()
    cursor = topic_seed
    attempts = 0
    max_attempts = len(ranked) * 2
    while len(active) < active_count and attempts < max_attempts:
        agent = ranked[cursor % len(ranked)]
        if agent.agent_id not in used:
            active.append(agent)
            used.add(agent.agent_id)
        cursor += stride
        attempts += 1
    if len(active) < active_count:
        for agent in ranked:
            if agent.agent_id in used:
                continue
            active.append(agent)
            if len(active) >= active_count:
                break
    return active


def _topic_ladder(prompt: str, rounds: int) -> list[str]:
    base = _extract_keywords(prompt)
    phases = ["문제 정의", "이해관계 충돌", "책임 공방", "대안 탐색", "동맹 형성", "집단 압력", "타협 가능성", "후속 행동"]
    topics = []
    for idx in range(rounds):
        keyword = base[idx % len(base)] if base else "핵심 이슈"
        phase = phases[idx % len(phases)]
        topics.append(f"{keyword} · {phase}")
    return topics


def _extract_keywords(prompt: str) -> list[str]:
    cleaned = "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in prompt)
    words = [word for word in cleaned.split() if len(word) >= 2]
    stop = {"그리고", "그러면", "어떤", "향후", "동시에", "시행되면", "시나리오", "대해서"}
    keywords: list[str] = []
    for word in words:
        if word in stop or word in keywords:
            continue
        keywords.append(word[:18])
        if len(keywords) >= 8:
            break
    return keywords or ["정책 충격", "시장 반응", "생활 압박", "공동 대응"]


def _scenario_focus(prompt: str) -> str:
    text = " ".join(str(prompt or "").split())
    if not text:
        return "정책 충격이 생활과 시장에 미치는 영향"
    if len(text) <= 90:
        return text
    keywords = _extract_keywords(text)
    return " · ".join(keywords[:4])


def _role_for_prompt(prompt: str, idx: int, *, role_pool: list[str] | None = None) -> str:
    if role_pool:
        cleaned = [str(role).strip() for role in role_pool if str(role).strip()]
        if cleaned:
            return cleaned[idx % len(cleaned)]
    text = prompt.lower()
    pool = ROLE_POOL
    if any(token in text for token in ["금리", "주거", "부동산", "대출"]):
        pool = ["임차인", "주택 보유자", "은행 상담원", "청년 가구", "건설 노동자", "정책 담당자", "지역 상인", "시장 분석가"]
    elif any(token in text for token in ["기본소득", "복지", "빈곤", "소득"]):
        pool = ["저소득 시민", "소규모 상점 경영자", "지방행정 담당자", "납세자", "청년 구직자", "노동자", "복지 활동가", "시장 분석가"]
    elif any(token in text for token in ["가격", "담합", "소비자", "프랜차이즈"]):
        pool = ["소비자", "프랜차이즈 점주", "본사 관계자", "공정위 담당자", "배달 노동자", "청년 소비자", "지역 상인", "시장 분석가"]
    return pool[idx % len(pool)]


def _cohort(role: str, zone_idx: int) -> str:
    if any(token in role for token in ["정책", "행정", "공정위"]):
        return "institution"
    if any(token in role for token in ["상점", "점주", "기업", "본사", "은행"]):
        return "market"
    if any(token in role for token in ["활동가", "노동자", "구직", "청년", "시민", "소비자", "임차인"]):
        return "public"
    return f"local-{zone_idx % 4 + 1}"


def _llm_channel(source: SwarmV2Agent, target: SwarmV2Agent, local_index: int) -> str:
    if local_index % 5 == 0:
        return source.llm_channel
    if source.cohort == target.cohort:
        return f"packet:{source.cohort}:{source.zone}"
    return f"packet:cross:{source.cohort}:{target.cohort}"


def _seed(text: str) -> int:
    return int(hashlib.sha256((text or "swarm-v2").encode("utf-8")).hexdigest()[:12], 16)
