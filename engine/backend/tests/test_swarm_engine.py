import time

from app.swarm import SwarmConfig, project_swarm_scene, run_swarm, run_swarm_compact


PERSONA_CATALOG = [
    {
        "persona_id": "p-market-1",
        "persona_text": "서울의 자영업 상인. 임대료와 소비 위축에 민감하다.",
        "role_key": "자영업 상인",
        "role_label": "자영업 상인",
        "country": "KR",
        "attrs": {"occupation": "자영업", "district": "서울", "age": 43},
    },
    {
        "persona_id": "p-public-1",
        "persona_text": "부산의 공공기관 정책 담당자. 안정과 규제 집행을 중시한다.",
        "role_key": "정책 담당자",
        "role_label": "정책 담당자",
        "country": "KR",
        "attrs": {"occupation": "공무원", "district": "부산", "age": 52},
    },
    {
        "persona_id": "p-logistics-1",
        "persona_text": "대구의 물류 기사. 유가와 이동 제한 정책에 민감하다.",
        "role_key": "물류 기사",
        "role_label": "물류 기사",
        "country": "KR",
        "attrs": {"occupation": "물류", "district": "대구", "age": 31},
    },
]


def test_swarm_runner_preserves_three_tier_shape():
    snapshots = run_swarm(
        SwarmConfig(
            agent_count=300,
            meso_group_count=12,
            steps=6,
            policy_intensity=0.45,
            shock_interval=3,
        )
    )

    final = snapshots[-1]
    assert len(snapshots) == 7
    assert final.t == 6
    assert len(final.agents) == 300
    assert len(final.meso_groups) == 12
    assert final.macro.avg_pressure >= 0
    assert final.metrics["simulation_mode"] == "swarm"


def test_swarm_seed_uses_persona_roles_zones_and_scenario_grounding():
    state, _ = run_swarm_compact(
        SwarmConfig(
            agent_count=120,
            meso_group_count=12,
            steps=1,
            scenario_prompt="서울 자영업과 물류 이동 제한 정책 충격",
            persona_catalog=PERSONA_CATALOG,
        )
    )

    roles = {agent.role for agent in state.agents}
    zones = {agent.zone_label for agent in state.agents}
    assert "자영업 상인" in roles
    assert "정책 담당자" in roles
    assert "서울" in zones
    assert "부산" in zones
    assert min(agent.persona_grounding_score for agent in state.agents) > 0.5
    assert max(agent.scenario_relevance_score for agent in state.agents) > 0.3
    assert state.macro is not None

    scene = project_swarm_scene(
        t=state.t,
        agents=state.agents,
        groups=state.meso_groups,
        macro=state.macro,
        agent_limit=24,
        pressure_grid_size=8,
    )
    assert any(item["role"] == "자영업 상인" for item in scene["agents"])
    assert any(item["zone"] == "zone-서울" for item in scene["agents"])


def test_swarm_packet_mode_records_group_packets():
    snapshots = run_swarm(
        SwarmConfig(
            agent_count=240,
            meso_group_count=10,
            steps=7,
            llm_mode="packet",
            packet_interval=2,
            policy_intensity=0.65,
        )
    )

    final = snapshots[-1]
    assert final.metrics["llm_packet_count"] > 0
    assert final.metrics["llm_prompt_count"] == final.metrics["llm_packet_count"]
    assert any(group.packet_summary for group in final.meso_groups)


def test_swarm_agent_mode_records_agent_sample_prompts():
    snapshots = run_swarm(
        SwarmConfig(
            agent_count=180,
            meso_group_count=9,
            steps=5,
            llm_mode="agent",
            packet_interval=2,
            agent_llm_sample_size=18,
            policy_intensity=0.7,
        )
    )

    final = snapshots[-1]
    assert final.metrics["llm_packet_count"] > 0
    assert final.metrics["llm_prompt_count"] > final.metrics["llm_packet_count"]
    assert final.metrics["llm_prompt_count"] <= 36
    assert any("sampled agents" in group.packet_summary for group in final.meso_groups)


def test_swarm_policy_shock_reaches_macro_field():
    snapshots = run_swarm(
        SwarmConfig(
            agent_count=120,
            meso_group_count=6,
            steps=4,
            shock_interval=2,
            policy_intensity=0.9,
        )
    )

    shocks = [snapshot.macro.shock_strength for snapshot in snapshots]
    assert max(shocks) > 0
    assert snapshots[-1].macro.policy_wave > 0


def test_swarm_compact_runtime_keeps_large_scene_bounded():
    started = time.perf_counter()
    state, trajectory = run_swarm_compact(
        SwarmConfig(
            agent_count=5000,
            meso_group_count=48,
            steps=8,
            packet_interval=4,
            policy_intensity=0.5,
        )
    )
    elapsed = time.perf_counter() - started
    assert elapsed < 3.0
    assert len(state.agents) == 5000
    assert len(trajectory) == 9
    assert state.macro is not None

    scene = project_swarm_scene(
        t=state.t,
        agents=state.agents,
        groups=state.meso_groups,
        macro=state.macro,
        agent_limit=1000,
        pressure_grid_size=24,
    )
    assert scene["agent_count"] == 5000
    assert len(scene["agents"]) <= 1000
    assert len(scene["pressure_grid"]["cells"]) == 576


def test_swarm_adaptive_internal_interactions_scale_with_scenario_pressure():
    quiet_state, quiet_trajectory = run_swarm_compact(
        SwarmConfig(
            agent_count=240,
            meso_group_count=12,
            steps=4,
            policy_intensity=0.0,
            min_interactions_per_step=1,
            max_interactions_per_step=8,
            interaction_sensitivity=0.5,
        )
    )
    intense_state, intense_trajectory = run_swarm_compact(
        SwarmConfig(
            agent_count=240,
            meso_group_count=12,
            steps=4,
            policy_intensity=1.0,
            shock_interval=2,
            min_interactions_per_step=1,
            max_interactions_per_step=8,
            interaction_sensitivity=2.0,
        )
    )

    assert quiet_state.internal_interactions >= 4
    assert intense_state.internal_interactions > quiet_state.internal_interactions
    assert max(point["last_interactions_per_step"] for point in intense_trajectory) > max(
        point["last_interactions_per_step"] for point in quiet_trajectory
    )
