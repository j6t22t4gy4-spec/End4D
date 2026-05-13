from app.swarm import SwarmConfig, run_swarm


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
