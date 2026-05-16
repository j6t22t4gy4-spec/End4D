import json
from threading import Lock

from app.swarm_v2 import llm_adapter
from app.swarm_v2.runtime import _apply_rule_action_feedback, create_streaming_session_seed, iter_streaming_events, run_session


def test_swarm_v2_agent_decision_parser_normalizes_structured_output():
    decision = llm_adapter._parse_agent_output(
        json.dumps(
            {
                "action": "comment",
                "target_event_id": "swarm-v2-1-1",
                "thought": "나는 상대의 말을 듣고 세금 부담을 다시 계산했다.",
                "content": "그 비용을 누가 감당하는지도 같이 말해야 합니다.",
                "tone": "conflict",
                "relation_delta": -0.5,
                "pressure_delta": 0.5,
                "memory_write": "세금 부담 논쟁을 경계함",
                "next_intent": "납세자 반응을 확인한다",
            },
            ensure_ascii=False,
        )
    )

    assert decision["action"] == "reply"
    assert decision["tone"] == "negative"
    assert decision["relation_delta"] == -0.18
    assert decision["pressure_delta"] == 0.12
    assert decision["memory_write"] == "세금 부담 논쟁을 경계함"


def test_swarm_v2_agent_decision_is_applied_to_event(monkeypatch):
    monkeypatch.setattr(llm_adapter, "get_llm_chat_enabled", lambda: True)

    class FakeFacade:
        def run_prompts_with_meta(self, prompts, *, task):
            return (
                [
                    json.dumps(
                        {
                            "action": "reply",
                            "target_event_id": "swarm-v2-1-1",
                            "thought": "나는 서지훈의 말을 듣고 월세 부담이 내 문제라는 생각이 들었다.",
                            "content": "서지훈님, 공급이 늘어도 당장 월세를 버틸 장치가 없으면 어렵습니다.",
                            "tone": "negative",
                            "relation_delta": -0.07,
                            "pressure_delta": 0.05,
                            "memory_write": "서지훈의 공급 우선 주장에 월세 부담으로 반박함",
                            "next_intent": "같은 처지의 임차인 반응을 확인한다",
                        },
                        ensure_ascii=False,
                    )
                ],
                {"used_fallback": False},
            )

    monkeypatch.setattr(llm_adapter, "llm_facade", FakeFacade())
    event = {
        "event_id": "swarm-v2-1-2",
        "source_id": "a",
        "target_id": "b",
        "reply_to_event_id": "swarm-v2-1-1",
        "topic": "주택 · 충돌",
        "relationship_score": 0.1,
        "summary": "초안",
        "source_memory": "",
        "llm_mode": "agent",
        "interaction_type": "dialogue",
    }
    agents = [
        {
            "agent_id": "a",
            "name": "김민수",
            "role": "청년 세입자",
            "identity": "김민수 · 청년 세입자",
            "zone": "임차인 밀집지",
            "cohort": "public",
            "stance": -0.4,
            "pressure": 0.7,
            "energy": 0.8,
        },
        {"agent_id": "b", "name": "서지훈", "role": "건설 관계자", "zone": "공급 bloc"},
    ]

    llm_adapter.deliberate_stream_event(event, agents=agents, previous_events=[], scenario="주택 공급과 월세 부담")

    assert event["llm_action"] == "reply"
    assert event["agent_thought"].startswith("나는 서지훈")
    assert event["memory_write"] == "서지훈의 공급 우선 주장에 월세 부담으로 반박함"
    assert event["decision_relation_delta"] == -0.07
    assert event["decision_pressure_delta"] == 0.05
    assert event["interaction_type"] == "negative"


def test_swarm_v2_decision_feedback_updates_memory_relation_and_pressure():
    event = {
        "source_id": "a",
        "target_id": "b",
        "llm_mode": "agent",
        "interaction_type": "negative",
        "decision_relation_delta": -0.07,
        "decision_pressure_delta": 0.05,
        "memory_write": "서지훈의 공급 우선 주장에 월세 부담으로 반박함",
        "pressure_delta": 0.02,
    }
    relationships = {("a", "b"): 0.1}
    memories = {"a": "기존 기억", "b": ""}
    pressure = {"a": 0.0, "b": 0.0}

    _apply_rule_action_feedback(event, relationships, agent_memory=memories, pressure_acc=pressure)

    assert relationships[("a", "b")] == 0.03
    assert memories["a"].endswith("월세 부담으로 반박함")
    assert pressure["a"] == 0.05
    assert round(pressure["b"], 4) == 0.0225
    assert event["pressure_delta"] == 0.07


def test_swarm_v2_full_agent_batch_enriches_every_event(monkeypatch):
    monkeypatch.setattr(llm_adapter, "get_llm_chat_enabled", lambda: True)

    class FakeFacade:
        def __init__(self):
            self.calls = []

        def run_prompts_with_meta(self, prompts, *, task):
            self.calls.append((task, len(prompts)))
            return (
                [
                    json.dumps(
                        {
                            "action": "reply",
                            "target_event_id": None,
                            "thought": f"나는 피드 {index}를 보고 내 입장에서 바로 판단했다.",
                            "content": f"내 관점에서는 {index}번째 쟁점에 이렇게 반응해야 한다.",
                            "tone": "dialogue",
                            "relation_delta": 0.02,
                            "pressure_delta": 0.01,
                            "memory_write": f"{index}번째 발언을 기억함",
                            "next_intent": "다음 반응을 기다린다",
                        },
                        ensure_ascii=False,
                    )
                    for index, _prompt in enumerate(prompts)
                ],
                {"used_fallback": False},
            )

    fake = FakeFacade()
    monkeypatch.setattr(llm_adapter, "llm_facade", fake)

    result = run_session(
        prompt="기본소득과 주택 공급을 둘러싼 시민 토론",
        agent_count=32,
        rounds=4,
        events_per_round=4,
        zone_count=4,
        llm_mode="full-agent",
        llm_sample_size=1,
    )

    events = result["events"]
    assert len(events) == 16
    assert fake.calls == [("swarm_agent", 16)]
    assert all(event["llm_mode"] == "agent" for event in events)
    assert all(event.get("llm_enriched") for event in events)
    assert all(event.get("agent_decision", {}).get("schema_version") == "swarm-agent-decision-v1" for event in events)
    assert result["summary"]["llm"]["mode"] == "full-agent"
    assert result["summary"]["llm"]["enriched_events"] == 16


def test_swarm_v2_full_agent_streaming_waits_for_every_agent_decision(monkeypatch):
    monkeypatch.setattr(llm_adapter, "get_llm_chat_enabled", lambda: True)

    class FakeFacade:
        def __init__(self):
            self.call_count = 0
            self.lock = Lock()

        def run_prompts_with_meta(self, prompts, *, task):
            with self.lock:
                self.call_count += len(prompts)
                current = self.call_count
            return (
                [
                    json.dumps(
                        {
                            "action": "reply",
                            "target_event_id": None,
                            "thought": f"나는 방금 들어온 {current}번째 피드에 개별적으로 반응했다.",
                            "content": f"{current}번째 응답은 내 페르소나의 즉시 판단이다.",
                            "tone": "dialogue",
                            "relation_delta": 0.01,
                            "pressure_delta": 0.01,
                            "memory_write": f"{current}번째 피드 기억",
                            "next_intent": "다음 피드를 관찰한다",
                        },
                        ensure_ascii=False,
                    )
                    for _prompt in prompts
                ],
                {"used_fallback": False},
            )

    fake = FakeFacade()
    monkeypatch.setattr(llm_adapter, "llm_facade", fake)
    result = create_streaming_session_seed(
        prompt="기본소득과 주택 공급을 둘러싼 시민 토론",
        agent_count=32,
        rounds=4,
        events_per_round=4,
        zone_count=4,
        llm_mode="full-agent",
        llm_sample_size=1,
        llm_parallelism=4,
    )

    stream_items = list(iter_streaming_events(result))
    thinking_items = [item for item in stream_items if item.get("_stream_type") == "agent_thinking"]
    log_items = [item for item in stream_items if item.get("_stream_type") == "llm_log"]
    events = [item for item in stream_items if not item.get("_stream_type")]

    assert len(events) == 16
    assert len(thinking_items) == 16
    assert any(item.get("status") == "batch_started" and item.get("parallelism") == 4 for item in log_items)
    assert len([item for item in log_items if item.get("status") == "completed"]) == 16
    assert fake.call_count == 16
    assert all(event["llm_mode"] == "agent" for event in events)
    assert all(event.get("llm_enriched") for event in events)
    assert result["summary"]["llm"]["used"] is True
    assert result["summary"]["llm"]["enriched_events"] == 16
