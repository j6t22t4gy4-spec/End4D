"""Phase 6: 스텝 루프에 Emotion·Thought·메모리 연동."""
import json
import os

import numpy as np
import pytest

from app.api.run import _build_live_observer_cells
from app.api.snapshots import _cell_to_dict
from app.core.agent_interactions import apply_lightweight_consultations
from app.core.consultation_kernel import (
    precision_active_agent_limit,
    precision_internal_interaction_count,
    scene_source_cells,
    scene_source_limit,
)
from app.core.deep_commit_runtime import run_deep_commit
from app.core.microbeat_events import build_microbeat_consultation_events
from app.core.scene_narrator import render_consultation_scene
from app.core.scene_events import build_intra_t_scene_events
from app.core.scene_selector import select_scene_candidates
from app.core.snapshot import SnapshotStore
from app.core.stream_episode_runtime import run_stream_episode
from app.graph.nodes import step_loop_node
from app.graph.time_flow import _create_initial_cells, create_time_flow_graph
from app.llm import thought as thought_module
from app.models.cell import Cell


@pytest.fixture(autouse=True)
def disable_live_llm(monkeypatch):
    monkeypatch.setenv("ORGANIC4D_LLM_CHAT_ENABLED", "0")
    monkeypatch.setenv("ORGANIC4D_LLM_PROVIDER", "stub")


def test_graph_run_preserves_vector_shapes_and_advances_t():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    out = graph.invoke(
        {
            "initial_cell_count": 3,
            "t_max": 22,
            "snapshot_store": store,
        }
    )
    assert out["current_t"] == 22
    for c in out["cells"]:
        assert c.emotion_vec.shape == (8,)
        assert c.thought_vec.shape == (256,)
        assert c.worldview_vec.shape == (384,)
        assert isinstance(c.memory, list)
        assert isinstance(c.short_memory, list)
        assert isinstance(c.long_memory, list)
        assert isinstance(c.behavior_log, list)
        assert isinstance(c.action_state, dict)
        assert "collective_pressure" in c.action_state
        assert "group_influence_applied" in c.action_state


def test_graph_uses_engine_zone_layout_params():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    out = graph.invoke(
        {
            "initial_cell_count": 6,
            "t_max": 1,
            "snapshot_store": store,
            "engine_params": {
                "zone_count": 3,
                "zone_layout": "bands",
                "zone_spacing": 3.0,
            },
        }
    )
    zone_ids = {c.zone_id for c in out["cells"]}
    ys = {round(float(c.y), 1) for c in out["cells"]}
    assert len(zone_ids) == 3
    assert len(ys) >= 2


def test_swarm_zone_layout_uses_persona_role_and_region_affinity():
    personas = [
        {
            "persona_id": "persona-seoul-market",
            "persona_text": "서울의 자영업 상인",
            "role_key": "자영업 상인",
            "role_label": "자영업 상인",
            "country": "KR",
            "attrs": {"occupation": "자영업", "district": "서울"},
        },
        {
            "persona_id": "persona-busan-public",
            "persona_text": "부산의 정책 담당자",
            "role_key": "정책 담당자",
            "role_label": "정책 담당자",
            "country": "KR",
            "attrs": {"occupation": "공무원", "district": "부산"},
        },
    ]

    cells = _create_initial_cells(
        count=8,
        role_catalog=["fallback"],
        persona_catalog=personas,
        engine_params={
            "simulation_mode": "swarm",
            "zone_count": 4,
            "zone_layout": "swarm",
            "regional_labels": ["서울", "부산"],
        },
    )

    assert {cell.role_key for cell in cells} == {"자영업 상인", "정책 담당자"}
    assert {"서울", "부산"}.issubset({cell.zone_label for cell in cells})
    assert all("persona_prior_summary" in cell.action_state for cell in cells)
    seoul_positions = {(round(cell.x, 2), round(cell.y, 2)) for cell in cells if cell.zone_label == "서울"}
    busan_positions = {(round(cell.x, 2), round(cell.y, 2)) for cell in cells if cell.zone_label == "부산"}
    assert seoul_positions != busan_positions


def test_scenario_director_roles_and_positions_shape_initial_cells():
    personas = [
        {
            "persona_id": "tenant-0",
            "persona_text": "서울 청년 세입자. 월세와 금리 부담에 민감하다.",
            "role_key": "기존 역할",
            "role_label": "기존 역할",
            "attrs": {"occupation": "청년 세입자", "district": "서울"},
        },
        {
            "persona_id": "landlord-0",
            "persona_text": "소형 임대인. 대출 금리 비용을 걱정한다.",
            "role_key": "기존 역할",
            "role_label": "기존 역할",
            "attrs": {"occupation": "임대인", "district": "부산"},
        },
    ]

    cells = _create_initial_cells(
        count=8,
        role_catalog=["fallback"],
        persona_catalog=personas,
        engine_params={
            "scenario_actor_roles": ["청년 세입자", "소형 임대인", "정책 중재자"],
            "scenario_initial_zones": ["임차인 밀집지", "자산 보유 bloc", "정책 중재권"],
            "scenario_conflict_axes": ["주거비 부담", "자산 기대"],
            "zone_layout": "scenario_social_field",
            "zone_spacing": 1.4,
        },
    )

    assert {"청년 세입자", "소형 임대인"}.issubset({cell.role_key for cell in cells})
    assert {"임차인 밀집지", "자산 보유 bloc", "정책 중재권"}.intersection({cell.zone_label for cell in cells})
    assert all(cell.persona_attrs.get("agent_name") for cell in cells)
    assert all("(" not in cell.role_label for cell in cells)
    assert any("청년 세입자" in str(cell.persona_attrs.get("display_name")) for cell in cells)
    unique_positions = {(round(cell.x, 2), round(cell.y, 2)) for cell in cells}
    assert len(unique_positions) > 4


def test_intra_t_scene_sampler_emits_multiple_neighbor_beats():
    source = Cell(
        x=0,
        y=0,
        z=0,
        t=0,
        energy=1,
        gene_vec=np.zeros(4),
        cell_id="source",
        role_key="merchant",
        role_label="상점 경영자",
        persona_attrs={"agent_name": "고문옥"},
        behavior_log=[
            {
                "event_type": "social_observation",
                "t": 0.4,
                "quality_score": 0.7,
                "payload": {
                    "neighbor_ids": ["target-a", "target-b"],
                    "alignment": "mixed",
                    "quality_score": 0.7,
                },
            }
        ],
    )
    target_a = source.copy(cell_id="target-a", role_key="worker", role_label="노동자", persona_attrs={"agent_name": "김아무개"})
    target_b = source.copy(cell_id="target-b", role_key="admin", role_label="행정 담당자", persona_attrs={"agent_name": "이아무개"})

    events = build_intra_t_scene_events(
        [source, target_a, target_b],
        current_t=0,
        next_t=1,
        internal_interactions=4,
        group_state={},
        limit=6,
    )
    interaction_events = [event for event in events if event.get("scene_type") in {"interaction", "consultation"}]

    assert len(interaction_events) >= 2
    assert {tuple(event.get("target_ids") or []) for event in interaction_events} >= {("target-a",), ("target-b",)}
    assert all("→" in str(event.get("summary") or "") for event in interaction_events)


def test_scene_selector_and_narrator_contracts_are_separate():
    source = Cell(
        x=0,
        y=0,
        z=0,
        t=0,
        energy=1,
        gene_vec=np.zeros(4),
        cell_id="selector-source",
        role_key="merchant",
        role_label="상점 경영자",
        persona_attrs={
            "agent_name": "고문옥",
            "occupation": "소규모 상점 경영자",
            "district": "안양",
            "scenario_prompt": "상권 침체와 기본소득 정책 충격",
        },
        action_state={
            "last_action_summary": "골목 상권 매출과 이웃 소비 여력을 비교",
            "collective_pressure": 0.28,
        },
        behavior_log=[
            {
                "event_type": "social_observation",
                "t": 0.3,
                "quality_score": 0.72,
                "payload": {
                    "neighbor_ids": ["selector-target"],
                    "alignment": "tension",
                    "belief_shift": 0.11,
                    "quality_score": 0.72,
                },
            }
        ],
    )
    target = source.copy(
        cell_id="selector-target",
        role_key="worker",
        role_label="저소득 노동자",
        persona_attrs={"agent_name": "김아무개", "occupation": "저소득 노동자", "district": "안양"},
        action_state={"last_thought_summary": "지원 정책의 체감 속도를 의심", "collective_pressure": 0.31},
        behavior_log=[],
    )

    narrative = render_consultation_scene(
        source=source,
        target=target,
        event_type="hostile",
        payload={"belief_shift": 0.11, "cluster_signal": "ideological_tension"},
    )
    assert narrative["source_label"].startswith("고문옥")
    assert narrative["target_label"].startswith("김아무개")
    assert "→" in narrative["summary"]
    assert narrative["narrative_reason"]
    assert narrative["scenario_relevance"] == "상권 침체와 기본소득 정책 충격"

    events = select_scene_candidates(
        [source, target],
        current_t=0,
        next_t=1,
        internal_interactions=5,
        group_state={
            "groups": {
                "merchant": {
                    "group_id": "merchant",
                    "group_label": "상점 경영자",
                    "avg_collective_pressure": 0.5,
                    "tension": 0.46,
                    "fracture_risk": 0.3,
                }
            }
        },
        limit=4,
    )

    assert events
    assert all(event["scene_count"] == len(events) for event in events)
    assert any(event["scene_type"] == "consultation" for event in events)
    assert any(event["scene_type"] == "pressure_shift" for event in events)


def test_lightweight_consultations_emit_person_like_micro_utterances():
    source = Cell(
        cell_id="micro-source",
        x=0.0,
        y=0.0,
        z=0.0,
        t=0.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.ones(256) * 0.04,
        worldview_vec=np.ones(384) * 0.03,
        role_key="merchant",
        role_label="상점 경영자",
        persona_attrs={"agent_name": "고문옥", "occupation": "소품점 운영자"},
        action_state={"last_thought_summary": "기본소득 이후 손님들의 소비 여력이 바뀔지 걱정한다."},
    )
    target = source.copy(
        cell_id="micro-target",
        x=0.8,
        y=0.0,
        role_key="worker",
        role_label="저소득 노동자",
        persona_attrs={"agent_name": "김아무개", "occupation": "저소득 노동자"},
        thought_vec=np.ones(256) * -0.02,
    )

    out = apply_lightweight_consultations(
        [source, target],
        0.25,
        radius=2.0,
        max_neighbors=1,
        active_cell_limit=None,
        beat_index=0,
    )
    updated = next(cell for cell in out if cell.cell_id == "micro-source")
    payload = dict(updated.behavior_log[-1]["payload"])

    assert payload["micro_utterance"]
    assert "고문옥" in payload["micro_utterance"]
    assert "김아무개" in payload["micro_utterance"]
    assert updated.action_state["last_consultation_summary"] == payload["micro_utterance"]


def test_microbeat_events_turn_recent_consultations_into_dense_stream():
    source = Cell(
        cell_id="beat-source",
        x=0.0,
        y=0.0,
        z=0.0,
        t=0.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.ones(256) * 0.04,
        worldview_vec=np.ones(384) * 0.03,
        role_key="merchant",
        role_label="상점 경영자",
        persona_attrs={"agent_name": "고문옥"},
        behavior_log=[
            {
                "event_type": "social_observation",
                "t": 0.4,
                "quality_score": 0.82,
                "payload": {
                    "neighbor_ids": ["beat-target-a", "beat-target-b"],
                    "alignment": "mixed",
                    "quality_score": 0.82,
                    "micro_utterance": "고문옥(상점 경영자) → 김아무개(노동자): 손님 감소 이야기를 꺼내고, 공감과 불신이 섞인 반응을 주고받는다.",
                },
            }
        ],
    )
    target_a = source.copy(cell_id="beat-target-a", role_key="worker", role_label="노동자", persona_attrs={"agent_name": "김아무개"})
    target_b = source.copy(cell_id="beat-target-b", role_key="admin", role_label="행정 담당자", persona_attrs={"agent_name": "이아무개"})

    events = build_microbeat_consultation_events(
        [source, target_a, target_b],
        current_t=0.0,
        next_t=1.0,
        scene_t=0.4,
        beat_index=3,
        beat_count=10,
        limit=4,
    )

    assert len(events) >= 2
    assert {tuple(event["target_ids"]) for event in events} >= {("beat-target-a",), ("beat-target-b",)}
    assert all(event["visual_hint"]["kind"] == "microbeat_arc" for event in events)
    assert all(event["stream_phase"] == "micro_consultation" for event in events)


def test_precision_step_runs_internal_interactions_inside_t():
    cells = [
        Cell(
            cell_id=f"precision-agent-{i}",
            x=float(i * 0.8),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=55.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.04 * (i + 1)),
            worldview_vec=np.full(384, 0.03 * (i + 1)),
            role_key="citizen",
            role_label="citizen",
            persona_attrs={"occupation": "청년 세입자", "district": "서울", "scenario_prompt": "금리 인상과 주거 보조금 충격"},
            action_state={
                "policy_sensitivity": 0.95,
                "mobility_bias": 0.65,
                "last_thought_summary": "월세 부담과 보조금 조건을 동시에 재평가함",
                "last_action_summary": "지역 임대인과 정책 담당자에게 조건 조정을 요구",
            },
        )
        for i in range(4)
    ]

    out = step_loop_node(
        {
            "cells": cells,
            "current_t": 0.0,
            "t_max": 1.0,
            "world_events": [],
            "engine_params": {
                "simulation_mode": "precision",
                "min_interactions_per_step": 3,
                "max_interactions_per_step": 3,
            },
        }
    )

    assert out["current_t"] == 1.0
    assert all(int(cell.action_state.get("internal_interactions", 0)) == 3 for cell in out["cells"])
    assert any("t=0." in line and "social_observation" in line for cell in out["cells"] for line in cell.memory)
    assert out["scene_events"]
    assert out["scene_events"][0]["scene_count"] == len(out["scene_events"])
    assert all(0.0 < float(event["scene_progress"]) <= 1.0 for event in out["scene_events"])
    assert any(event["scene_type"] in {"interaction", "consultation"} for event in out["scene_events"])
    interaction = next(event for event in out["scene_events"] if event["scene_type"] in {"interaction", "consultation"})
    assert "→" in interaction["summary"]
    assert "월세 부담" in interaction["summary"] or "조건 조정" in interaction["summary"]
    assert interaction["narrative_reason"]
    assert interaction["scenario_relevance"]
    assert interaction["agent_context"]["source"]["persona"]
    assert interaction["action_record"]["platform"] == "social_field"
    assert interaction["action_record"]["domain"] == "end4d_social_field"
    assert interaction["action_record"]["action_type"].startswith("FIELD_")
    assert interaction["action_record"]["action_label"]
    assert interaction["action_record"]["interpretation"]
    assert interaction["action_record"]["result"] == interaction["summary"]
    assert out["scene_metrics"]["scenes_per_t"] == len(out["scene_events"])
    assert out["scene_metrics"]["relationship_event_count"] >= 1
    assert out["runtime_timing"]["total_ms"] >= 0
    assert "stream_episode" in out["runtime_timing"]["phases"]
    assert "scene_select" in out["runtime_timing"]["phases"]
    assert any("scene_participation_count" in cell.action_state for cell in out["cells"])


def test_stream_episode_runner_wraps_one_t_as_complete_social_stream():
    cells = [
        Cell(
            cell_id=f"episode-agent-{i}",
            x=float(i),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=64.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.zeros(256),
            worldview_vec=np.zeros(384),
            role_key="resident",
            role_label="주민",
            zone_id="zone-a" if i % 2 == 0 else "zone-b",
            action_state={"last_thought_summary": "상권 변화에 대해 이웃 반응을 살핀다."},
            persona_attrs={"display_name": f"주민{i}"},
        )
        for i in range(8)
    ]
    emitted: list[dict] = []

    result = run_stream_episode(
        cells,
        current_t=0.0,
        next_t=1.0,
        engine_params={
            "min_interactions_per_step": 4,
            "max_interactions_per_step": 4,
            "social_stream_density": 1.0,
        },
        previous_group_state=None,
        scene_event_sink=lambda event, *_: emitted.append(dict(event)),
    )

    assert result.round_count == 4
    assert result.live_scene_events
    assert emitted
    assert {event["stream_episode_id"] for event in result.live_scene_events} == {"t1-00-mirofish-stream"}
    assert all(event["stream_round_count"] == 4 for event in result.live_scene_events)
    assert any(event.get("stream_phase") == "micro_consultation" for event in emitted)


def test_deep_commit_runtime_returns_stable_state_shapes():
    cells = [
        Cell(
            cell_id=f"deep-agent-{i}",
            x=float(i),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=50.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.zeros(256),
            worldview_vec=np.zeros(384),
            role_key="citizen",
            role_label="citizen",
            action_state={"last_thought_summary": "지역 반응을 관찰"},
        )
        for i in range(3)
    ]

    next_cells, coalition_state, coalition_history = run_deep_commit(
        cells,
        next_t=1.0,
        coalition_state={},
        coalition_history=[],
    )

    assert len(next_cells) == len(cells)
    assert isinstance(coalition_state, dict)
    assert isinstance(coalition_history, list)


def test_precision_step_emits_live_scene_events_during_internal_interactions():
    emitted = []
    cells = [
        Cell(
            cell_id=f"live-scene-agent-{i}",
            x=float(i * 0.7),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=55.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.03 * (i + 1)),
            worldview_vec=np.full(384, 0.02 * (i + 1)),
            role_key="citizen",
            role_label="citizen",
            action_state={"policy_sensitivity": 0.95, "mobility_bias": 0.65},
        )
        for i in range(4)
    ]

    out = step_loop_node(
        {
            "cells": cells,
            "current_t": 0.0,
            "t_max": 1.0,
            "world_events": [],
            "engine_params": {
                "simulation_mode": "precision",
                "min_interactions_per_step": 3,
                "max_interactions_per_step": 3,
            },
            "scene_event_sink": emitted.append,
        }
    )

    assert emitted
    assert out["scene_events_live_emitted"] is True
    assert len(emitted) >= 10
    assert any(event.get("stream_phase") == "micro_consultation" for event in emitted)
    assert all(event["live_computed"] is True for event in emitted)
    assert all(0.0 < float(event["scene_progress"]) <= 1.0 for event in emitted)
    assert all(event.get("action_record", {}).get("platform") == "social_field" for event in out["scene_events"])


def test_consultation_kernel_limits_live_scene_sources_to_active_cast():
    cells = [
        Cell(
            cell_id=f"agent-{i}",
            x=float(i),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=50.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.zeros(256),
            worldview_vec=np.zeros(384),
            action_state={
                "collective_pressure": 0.1,
                "decision_pressure_delta": 0.02,
                "policy_sensitivity": 0.45,
            },
        )
        for i in range(320)
    ]
    cells[10] = cells[10].copy(
        action_state={
            "last_consultation_t": 0.5,
            "last_consultation_quality": 0.9,
            "collective_pressure": 0.7,
            "decision_pressure_delta": 0.2,
        },
        behavior_log=[
            {
                "event_type": "social_observation",
                "payload": {"neighbor_ids": ["agent-11", "agent-12"]},
            }
        ],
    )

    limit = scene_source_limit(cells, interactions=4)
    selected = scene_source_cells(cells, scene_t=0.5, limit=limit)
    selected_ids = {cell.cell_id for cell in selected}

    assert limit < len(cells)
    assert {"agent-10", "agent-11", "agent-12"}.issubset(selected_ids)
    assert len(selected) <= limit
    assert precision_active_agent_limit(cells, engine_params={"simulation_mode": "precision"}) < len(cells)
    assert precision_internal_interaction_count(
        cells,
        engine_params={"simulation_mode": "precision", "min_interactions_per_step": 3, "max_interactions_per_step": 8},
        previous_group_state={"groups": {"g": {"avg_collective_pressure": 0.7, "fracture_risk": 0.4}}},
    ) >= 3


def test_snapshot_store_keeps_intra_t_scene_events():
    store = SnapshotStore()
    cells = [
        Cell(
            cell_id="scene-agent-0",
            x=0.0,
            y=0.0,
            z=0.0,
            t=1.0,
            energy=50.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.zeros(256),
            worldview_vec=np.zeros(384),
        )
    ]
    store.save(
        1.0,
        cells,
        scene_events=[
            {
                "scene_id": "scene-1",
                "t": 1.0,
                "scene_index": 1,
                "scene_count": 1,
                "scene_type": "interaction",
                "summary": "agent 협의 장면",
            }
        ],
    )

    snap = store.get(1.0)
    assert snap is not None
    assert snap.scene_events[0]["scene_id"] == "scene-1"


def test_dialogue_memory_feeds_human_thought_fallback():
    from app.llm.dialogue import _apply_dialogue_to_cell
    from app.llm.thought import _grounded_thought_fallback

    a = Cell(
        cell_id="a",
        x=0,
        y=0,
        z=0,
        t=0,
        energy=50,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key="시장참여자",
        role_label="시장참여자",
        persona_attrs={"agent_name": "홍길동", "identity_summary": "홍길동(시장참여자) · 서울"},
        action_state={"cooperation_bias": 0.5, "risk_tolerance": 0.5},
    )
    b = Cell(
        cell_id="b",
        x=1,
        y=0,
        z=0,
        t=0,
        energy=50,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.zeros(256),
        worldview_vec=np.zeros(384),
        role_key="저소득층 시민",
        role_label="저소득층 시민",
        persona_attrs={"agent_name": "김아무개", "identity_summary": "김아무개(저소득층 시민) · 임대료 부담"},
        action_state={"last_thought_summary": "기본소득이 월세 부담을 줄일지 궁금하다."},
    )

    updated = _apply_dialogue_to_cell(
        a,
        {
            "summary_a": "",
            "summary_b": "",
            "alignment_delta": 0.03,
            "tension_delta": 0.01,
            "cooperation_delta": 0.02,
            "importance": 0.7,
        },
        side="a",
        peer=b,
        current_t=1.0,
    )
    thought = _grounded_thought_fallback(updated)

    assert "홍길동" in thought
    assert "김아무개" in thought
    assert "들" in thought or "말" in thought


def test_swarm_mode_uses_cleanroom_session_runtime(monkeypatch):
    captured: dict[str, str | None] = {}

    def capture_action_env(cells, current_t):
        captured["action_interval"] = os.environ.get("ORGANIC4D_ACTION_INTERVAL")
        captured["sample_size"] = os.environ.get("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE")
        captured["deliberation_interval"] = os.environ.get("ORGANIC4D_GROUP_DELIBERATION_INTERVAL")
        captured["deliberation_groups"] = os.environ.get("ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS")
        captured["action_priority"] = os.environ.get("ORGANIC4D_LLM_PRIORITY_ACTION")
        captured["group_priority"] = os.environ.get("ORGANIC4D_LLM_PRIORITY_GROUP_DELIBERATION")
        return cells

    monkeypatch.setattr("app.graph.nodes.update_thoughts_if_due", lambda cells, current_t: cells)
    monkeypatch.setattr("app.graph.nodes.update_worldviews_if_due", lambda cells, current_t: cells)
    monkeypatch.setattr("app.core.deep_commit_runtime.update_action_states_if_due", capture_action_env)
    monkeypatch.setattr("app.core.deep_commit_runtime.apply_agent_dialogues_if_due", lambda cells, current_t: cells)
    monkeypatch.setattr(
        "app.core.deep_commit_runtime.apply_group_deliberation_if_due",
        lambda cells, current_t, coalition_state=None, coalition_history=None: (
            cells,
            dict(coalition_state or {}),
            list(coalition_history or []),
        ),
    )
    cells = _create_initial_cells(
        count=8,
        role_catalog=["citizen", "worker"],
        engine_params={"simulation_mode": "swarm", "zone_count": 4, "zone_layout": "swarm"},
    )

    out = step_loop_node(
        {
            "cells": cells,
            "current_t": 0.0,
            "t_max": 1.0,
            "engine_params": {
                "simulation_mode": "swarm",
                "swarm_llm_mode": "packet",
                "swarm_tier_model": {"meso": {"group_count": 24, "llm_mode": "packet"}},
            },
            "world_events": [],
        }
    )

    assert out["current_t"] == 1.0
    assert captured == {}
    assert out["scene_events_live_emitted"] is True
    assert out["scene_events"]
    assert out["scene_events"][0]["t_composition_role"] == "mirofish_cleanroom_swarm_session"
    assert out["runtime_timing"]["dominant_phase"] == "miro_swarm_session"
    assert os.environ.get("ORGANIC4D_ACTION_INTERVAL") is None


def test_graph_assigns_social_elevation_from_engine_params():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    out = graph.invoke(
        {
            "initial_cell_count": 4,
            "t_max": 1,
            "snapshot_store": store,
            "engine_params": {
                "z_mode": "wealth",
                "z_weight": 0.16,
                "z_scale": 10.0,
            },
        }
    )
    assert any(float(c.z) > 0.0 for c in out["cells"])
    assert all(c.action_state["z_mode"] == "wealth" for c in out["cells"])
    assert all(float(c.action_state["z_weight"]) == 0.16 for c in out["cells"])


def test_thought_refresh_at_interval_changes_vector():
    """Thought는 첫 스텝과 cadence마다 갱신되어야 한다."""
    store = SnapshotStore()
    graph = create_time_flow_graph()
    graph.invoke(
        {
            "initial_cell_count": 1,
            "t_max": 21,
            "snapshot_store": store,
        }
    )
    snap0 = store.get(0.0)
    snap21 = store.get(21.0)
    assert snap0 is not None and snap21 is not None
    assert not np.allclose(snap0.cells[0].thought_vec, snap21.cells[0].thought_vec)
    assert str(snap21.cells[0].action_state.get("last_thought_summary", "")).strip()
    assert "thought_continuity_score" in snap21.cells[0].action_state
    assert "thought_continuity_state" in snap21.cells[0].action_state


def test_graph_writes_agent_social_memory_before_thought_refresh():
    """Internal agent observations become memory before the next Thought cycle."""
    store = SnapshotStore()
    graph = create_time_flow_graph()
    initial_cells = [
        Cell(
            cell_id=f"agent-{i}",
            x=float(i),
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
        )
        for i, role in enumerate(["citizen", "regulator", "producer"])
    ]
    graph.invoke(
        {
            "initial_cells": initial_cells,
            "t_max": 21,
            "snapshot_store": store,
        }
    )
    snap15 = store.get(15.0)
    snap21 = store.get(21.0)
    assert snap15 is not None and snap21 is not None
    assert any(
        "social_observation" in line
        for cell in snap15.cells
        for line in cell.memory
    )
    assert any(
        "borrowed_signal=" in line
        for cell in snap15.cells
        for line in cell.memory
    )
    assert any(
        str(cell.action_state.get("last_thought_summary", "")).strip()
        for cell in snap21.cells
    )


def test_graph_updates_xy_positions_from_social_field_dynamics():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    initial_cells = [
        Cell(
            cell_id=f"mover-{i}",
            x=float(i * 1.2),
            y=0.0,
            z=0.0,
            t=0.0,
            energy=50.0 + i,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.1 * (i + 1)),
            worldview_vec=np.full(384, 0.05 * (i + 1)),
            role_key="citizen",
            role_label="citizen",
            action_state={"mobility_bias": 0.8},
        )
        for i in range(4)
    ]
    out = graph.invoke(
        {
            "initial_cells": initial_cells,
            "t_max": 5,
            "snapshot_store": store,
        }
    )
    moved = [
        abs(cell.x - initial_cells[idx].x) + abs(cell.y - initial_cells[idx].y)
        for idx, cell in enumerate(out["cells"])
    ]
    assert any(delta > 0.05 for delta in moved)
    assert any(float(cell.action_state.get("last_spatial_shift", 0.0)) > 0.0 for cell in out["cells"])
    assert any(str(cell.action_state.get("mobility_state", "")) for cell in out["cells"])


def test_live_observer_sampling_balances_focus_and_zone_coverage():
    cells = []
    for idx in range(8):
        zone_id = f"zone-{idx % 3}"
        cell = Cell(
            cell_id=f"observer-{idx}",
            x=float(idx),
            y=float(idx % 2),
            z=float(idx),
            t=5.0,
            energy=40.0 + idx * 5,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.05 * (idx + 1)),
            worldview_vec=np.zeros(384),
            role_key=f"role-{idx % 4}",
            role_label=f"role-{idx % 4}",
            zone_id=zone_id,
            zone_label=zone_id,
            action_state={
                "last_thought_summary": "reassess constraints" if idx in {0, 1, 2, 6} else "",
                "last_thought_t": float(4 + idx % 3),
                "thought_continuity_score": 0.75 if idx in {0, 1} else 0.2,
                "last_spatial_shift": 0.6 if idx in {3, 4, 7} else 0.05,
                "mobility_bias": 0.9 if idx in {3, 4} else 0.2,
            },
            short_memory=[{"summary": "recent signal"}] * (idx % 3),
            behavior_log=[{"summary": "behavior", "event_type": "thought_update"}] * (1 + idx % 2),
        )
        cells.append(cell)

    observer_cells, sampled = _build_live_observer_cells(cells, limit=6)
    assert sampled is True
    focuses = {str(cell["action_state"].get("observer_focus")) for cell in observer_cells}
    zones = {str(cell.get("zone_id")) for cell in observer_cells}
    assert "thought" in focuses
    assert "mover" in focuses
    assert "zone" in focuses or len(zones) >= 3
    assert len(zones) >= 2
    assert all("observer_score" in cell["action_state"] for cell in observer_cells)
    assert all("gene_vec" not in cell for cell in observer_cells)
    assert all("thought_vec" not in cell for cell in observer_cells)
    assert all("worldview_vec" not in cell for cell in observer_cells)
    assert all(cell["action_state"].get("stream_payload") == "compact-v1" for cell in observer_cells)
    assert len(json.dumps(observer_cells)) < 32_000


def test_live_observer_includes_compact_interaction_events():
    cells = [
        Cell(
            cell_id=f"interaction-{idx}",
            x=float(idx * 0.5),
            y=0.0,
            z=0.0,
            t=1.0,
            energy=50.0,
            gene_vec=np.zeros(32),
            emotion_vec=np.zeros(8),
            thought_vec=np.full(256, 0.1),
            worldview_vec=np.full(384, 0.1),
            role_key="citizen",
            role_label="citizen",
            behavior_log=[
                {
                    "t": 0.5,
                    "event_type": "social_observation",
                    "summary": "t=0.5 social_observation neighbors=1 alignment=ally",
                    "quality_score": 0.82,
                    "payload": {
                        "neighbor_ids": [f"interaction-{1 if idx == 0 else 0}"],
                        "alignment": "ally",
                        "cluster_signal": "forming_cluster",
                    },
                }
            ]
            if idx < 2
            else [],
        )
        for idx in range(3)
    ]

    observer_cells, _ = _build_live_observer_cells(cells, limit=3)
    events = [event for cell in observer_cells for event in cell.get("interaction_events", [])]
    assert events
    assert events[0]["type"] == "positive"
    assert events[0]["source_id"].startswith("interaction-")
    assert events[0]["target_ids"]


def test_snapshot_cell_response_keeps_interaction_events():
    cell = Cell(
        cell_id="snapshot-interaction-0",
        x=0.0,
        y=0.0,
        z=0.0,
        t=4.0,
        energy=50.0,
        gene_vec=np.zeros(32),
        emotion_vec=np.zeros(8),
        thought_vec=np.full(256, 0.1),
        worldview_vec=np.full(384, 0.1),
        behavior_log=[
            {
                "t": 4.0,
                "event_type": "social_observation",
                "summary": "t=4.0 social_observation neighbors=1 alignment=tension",
                "quality_score": 0.74,
                "payload": {
                    "neighbor_ids": ["snapshot-interaction-1"],
                    "alignment": "tension",
                    "cluster_signal": "ideological_tension",
                    "thought_similarity": -0.12,
                    "worldview_similarity": -0.08,
                },
            }
        ],
    )

    payload = _cell_to_dict(cell)

    assert payload["interaction_events"]
    assert payload["interaction_events"][0]["type"] == "hostile"
    assert payload["interaction_events"][0]["target_ids"] == ["snapshot-interaction-1"]


def test_thought_continuity_prefers_semantic_similarity(monkeypatch):
    def fake_embed_texts(texts, dim):
        vectors = []
        for text in texts:
            if "food crisis" in text:
                vec = np.array([1.0, 0.0, 0.0], dtype=np.float32)
            elif "supply collapse" in text:
                vec = np.array([0.92, 0.08, 0.0], dtype=np.float32)
            else:
                vec = np.array([0.0, 1.0, 0.0], dtype=np.float32)
            padded = np.zeros(dim, dtype=np.float32)
            padded[: len(vec)] = vec
            padded /= np.linalg.norm(padded) + 1e-8
            vectors.append(padded)
        return np.stack(vectors, axis=0)

    monkeypatch.setattr(thought_module, "embed_texts", fake_embed_texts)
    thought_module._CONTINUITY_EMBED_CACHE.clear()

    score = thought_module._thought_continuity_score(
        "The food crisis is escalating, so rationing may be necessary.",
        "A supply collapse is spreading, so rationing still looks necessary.",
    )
    assert score >= 0.8
    assert thought_module._continuity_state_label(score) == "stable"


def test_thought_continuity_falls_back_to_token_overlap(monkeypatch):
    def broken_embed_texts(texts, dim):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(thought_module, "embed_texts", broken_embed_texts)
    thought_module._CONTINUITY_EMBED_CACHE.clear()

    score = thought_module._thought_continuity_score(
        "Local transport pressure keeps rising around the zone boundary.",
        "Local transport pressure keeps rising around the zone boundary tonight.",
    )
    assert score > 0.7


def test_persona_attrs_seed_action_priors():
    persona_catalog = [
        {
            "persona_id": "persona-1",
            "persona_text": "A civic-minded delivery worker in Seoul who volunteers on weekends.",
            "role_key": "citizen",
            "role_label": "citizen",
            "country": "KR",
            "attrs": {
                "occupation": "delivery driver",
                "hobbies_and_interests": "community volunteer, local activism",
                "region": "Seoul metro",
                "transportation": "motorbike and subway",
                "education_level": "master",
            },
        }
    ]
    cells = _create_initial_cells(
        count=1,
        t=0.0,
        role_catalog=["citizen"],
        persona_catalog=persona_catalog,
        engine_params={"zone_count": 1},
    )
    action_state = cells[0].action_state
    assert float(action_state["mobility_bias"]) > 0.55
    assert float(action_state["cooperation_bias"]) > 0.6
    assert float(action_state["policy_sensitivity"]) > 0.55
    assert "persona_prior_summary" in action_state
    assert action_state["persona_prior_factors"]


def test_persona_distribution_bias_seeds_initial_cells():
    persona_catalog = [
        {
            "persona_id": "persona-1",
            "persona_text": "A Seoul public nurse with strong civic engagement.",
            "role_key": "nurse",
            "role_label": "public nurse",
            "country": "KR",
            "attrs": {"occupation": "public nurse", "province": "Seoul", "age": 45},
        }
    ]
    cells = _create_initial_cells(
        count=1,
        t=0.0,
        role_catalog=["nurse"],
        persona_catalog=persona_catalog,
        engine_params={
            "zone_count": 1,
            "persona_initial_bias": {
                "energy_offset": 3.0,
                "cooperation_delta": 0.08,
                "policy_sensitivity_delta": 0.07,
            },
        },
    )
    action_state = cells[0].action_state
    assert cells[0].energy >= 53.0
    assert float(action_state["cooperation_bias"]) >= 0.56
    assert float(action_state["policy_sensitivity"]) >= 0.57
    assert action_state["persona_distribution_bias"]["energy_offset"] == 3.0


def test_graph_emits_collective_group_state_and_feedback():
    store = SnapshotStore()
    graph = create_time_flow_graph()
    initial_cells = [
        Cell(
            cell_id=f"group-{idx}",
            x=float(idx),
            y=float(idx % 2),
            z=0.1 * idx,
            t=0.0,
            energy=45.0 + idx * 3,
            gene_vec=np.zeros(32),
            emotion_vec=np.full(8, 0.05 * (idx + 1)),
            thought_vec=np.full(256, 0.02 * (idx + 1)),
            worldview_vec=np.full(384, 0.03 * (idx + 1)),
            role_key="citizen" if idx < 3 else "merchant",
            role_label="citizen" if idx < 3 else "merchant",
            zone_id="zone-a" if idx % 2 == 0 else "zone-b",
            zone_label="zone-a" if idx % 2 == 0 else "zone-b",
            action_state={"mobility_bias": 0.35 + idx * 0.05},
        )
        for idx in range(6)
    ]
    out = graph.invoke(
        {
            "initial_cells": initial_cells,
            "t_max": 2,
            "snapshot_store": store,
        }
    )
    group_state = dict(out.get("group_state") or {})
    assert group_state["collective_signal"] in {"stable", "realigning", "fracturing"}
    assert "citizen" in group_state["role_groups"]
    assert "zone-a" in group_state["zone_groups"]
    sample = out["cells"][0].action_state
    assert "role_group_cohesion" in sample
    assert "zone_group_tension" in sample
    assert "collective_pressure" in sample
    assert "decision_pressure_delta" in sample
    assert "group_pressure_reason" in sample
