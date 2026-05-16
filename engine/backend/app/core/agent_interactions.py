"""Agent-to-agent interaction memory for the engine data flywheel.

This layer does not add chatbot/user interaction. It lets cells periodically
observe nearby agents and write compact social experience into memory, which
then feeds Thought/Worldview embedding updates.
"""
from __future__ import annotations

from typing import List

import numpy as np

from app.core.belief_dynamics import apply_belief_update
from app.core.coordinates import cosine_similarity, distance_4d
from app.core.interaction_quality import evaluate_interaction_quality
from app.core.memory_store import append_memory, behavior_event, memory_entry
from app.core.spatial_index import SpatialHashGrid
from app.models.cell import Cell

SOCIAL_INTERACTION_INTERVAL = 10
SOCIAL_RADIUS = 4.0
MAX_NEIGHBORS_PER_CELL = 3
THOUGHT_ALIGNMENT_THRESHOLD = 0.35
WORLDVIEW_ALIGNMENT_THRESHOLD = 0.20


def _blend_unit(base: np.ndarray, target: np.ndarray, weight: float) -> np.ndarray:
    if base.size == 0:
        return base
    out = (1.0 - weight) * base + weight * target
    norm = float(np.linalg.norm(out))
    if norm <= 1e-8:
        return out
    return out / norm


def _salient_memory(neighbor: Cell) -> str:
    for line in reversed(neighbor.memory[-5:]):
        if line.strip():
            return line.strip()
    return neighbor.persona_text[:160].strip() or "no_signal"


def apply_agent_interactions(
    cells: List[Cell],
    current_t: float,
    *,
    interval: int = SOCIAL_INTERACTION_INTERVAL,
    radius: float = SOCIAL_RADIUS,
    max_neighbors: int = MAX_NEIGHBORS_PER_CELL,
    active_cell_limit: int | None = None,
    force: bool = False,
) -> List[Cell]:
    """Append nearby-agent observations to cell memory at a fixed interval."""
    t_int = int(current_t)
    if not cells or current_t <= 0:
        return cells
    if not force and (t_int <= 0 or t_int % interval != 0):
        return cells
    t_label = _format_t_label(current_t)

    grid = SpatialHashGrid(cells, cell_size=radius)
    active_ids = _active_consultation_ids(
        cells,
        active_cell_limit=active_cell_limit,
        beat_index=t_int,
    )
    out: List[Cell] = []
    for cell in cells:
        if active_ids is not None and cell.cell_id not in active_ids:
            out.append(cell)
            continue
        candidates = [
            other
            for other in grid.candidate_cells(cell, radius)
            if other.cell_id != cell.cell_id and distance_4d(cell, other) <= radius
        ]
        candidates.sort(key=lambda other: distance_4d(cell, other))
        neighbors = candidates[:max_neighbors]
        if not neighbors:
            out.append(cell)
            continue

        role_counts: dict[str, int] = {}
        energy_sum = 0.0
        aligned: List[Cell] = []
        conflicted: List[Cell] = []
        for n in neighbors:
            role = n.role_label or n.role_key or "agent"
            role_counts[role] = role_counts.get(role, 0) + 1
            energy_sum += float(n.energy)
            thought_sim = cosine_similarity(cell.thought_vec, n.thought_vec)
            worldview_sim = cosine_similarity(cell.worldview_vec, n.worldview_vec)
            if (
                thought_sim >= THOUGHT_ALIGNMENT_THRESHOLD
                or worldview_sim >= WORLDVIEW_ALIGNMENT_THRESHOLD
            ):
                aligned.append(n)
            elif thought_sim < 0.0 or worldview_sim < -0.05:
                conflicted.append(n)

        roles = ", ".join(f"{role}:{count}" for role, count in sorted(role_counts.items()))
        avg_energy = energy_sum / len(neighbors)
        quality = evaluate_interaction_quality(cell, neighbors)
        if aligned and conflicted:
            alignment = "mixed"
        elif aligned:
            alignment = "ally"
        elif conflicted:
            alignment = "tension"
        else:
            alignment = "neutral"
        line = (
            f"t={t_label} social_observation neighbors={len(neighbors)} "
            f"roles=[{roles}] avg_neighbor_energy={avg_energy:.1f} alignment={alignment} "
            f"cluster_signal={quality['cluster_signal']} quality={quality['quality_score']:.2f}"
        )
        source_neighbor = aligned[0] if aligned else neighbors[0]

        thought_vec = cell.thought_vec
        worldview_vec = cell.worldview_vec
        if aligned:
            thought_target = np.mean([n.thought_vec for n in aligned], axis=0)
            worldview_target = np.mean([n.worldview_vec for n in aligned], axis=0)
            thought_vec = _blend_unit(cell.thought_vec, thought_target, 0.18)
            worldview_vec = _blend_unit(cell.worldview_vec, worldview_target, 0.08)
        elif conflicted:
            conflict_target = np.mean([n.thought_vec for n in conflicted], axis=0)
            thought_vec = _blend_unit(cell.thought_vec, -conflict_target, 0.10)

        belief = apply_belief_update(
            cell.copy(thought_vec=thought_vec, worldview_vec=worldview_vec),
            neighbors=neighbors,
            quality=quality,
            alignment=alignment,
        )
        thought_vec = belief["thought_vec"]
        worldview_vec = belief["worldview_vec"]

        updated = cell.copy(
            thought_vec=thought_vec,
            worldview_vec=worldview_vec,
        )
        observation_entry = memory_entry(
            t=float(current_t),
            kind="social_observation",
            summary=line,
            importance=float(quality["quality_score"]),
            source="engine.agent_interactions",
            payload={
                "alignment": alignment,
                "roles": roles,
                "avg_neighbor_energy": avg_energy,
                "cluster_signal": quality["cluster_signal"],
                "quality_score": quality["quality_score"],
                "belief_shift": belief["belief_shift"],
                "belief_polarity": belief["belief_polarity"],
            },
            tags=["interaction", "social"],
        )
        behavior = behavior_event(
            t=float(current_t),
            event_type="social_observation",
            source="engine.agent_interactions",
            summary=line,
            quality_score=float(quality["quality_score"]),
            payload={
                "neighbor_ids": [n.cell_id for n in neighbors],
                "alignment": alignment,
                "cluster_signal": quality["cluster_signal"],
                "thought_similarity": quality["thought_similarity"],
                "worldview_similarity": quality["worldview_similarity"],
                "belief_shift": belief["belief_shift"],
                "belief_polarity": belief["belief_polarity"],
            },
        )
        updated = append_memory(
            updated,
            observation_entry,
            behavior=behavior,
            promote=float(quality["quality_score"]) >= 0.72,
        )
        borrowed_summary = f"t={t_label} borrowed_signal={_salient_memory(source_neighbor)[:180]}"
        borrowed_entry = memory_entry(
            t=float(current_t),
            kind="borrowed_signal",
            summary=borrowed_summary,
            importance=max(0.35, float(quality["quality_score"]) * 0.85),
            source="engine.agent_interactions",
            payload={"from_cell_id": source_neighbor.cell_id},
            tags=["interaction", "signal"],
        )
        updated = append_memory(updated, borrowed_entry, promote=False)
        belief_entry = memory_entry(
            t=float(current_t),
            kind="belief_update",
            summary=f"t={t_label} {belief['belief_summary']}",
            importance=max(0.42, min(0.95, float(quality["quality_score"]) * 0.9)),
            source="engine.belief_dynamics",
            payload={
                "belief_shift": belief["belief_shift"],
                "belief_polarity": belief["belief_polarity"],
                "cluster_signal": quality["cluster_signal"],
            },
            tags=["belief", "worldview"],
        )
        updated = append_memory(
            updated,
            belief_entry,
            promote=float(belief["belief_shift"]) >= 0.18 or float(quality["quality_score"]) >= 0.76,
        )
        out.append(updated)
    return out


def apply_lightweight_consultations(
    cells: List[Cell],
    current_t: float,
    *,
    radius: float = SOCIAL_RADIUS,
    max_neighbors: int = MAX_NEIGHBORS_PER_CELL,
    active_cell_limit: int | None = None,
    beat_index: int = 0,
) -> List[Cell]:
    """Fast intra-t consultation pass.

    This keeps the field alive inside one t without paying the full memory and
    belief-write cost of `apply_agent_interactions` on every micro beat.
    """
    if not cells or current_t <= 0:
        return cells
    t_label = _format_t_label(current_t)
    grid = SpatialHashGrid(cells, cell_size=radius)
    active_ids = _active_consultation_ids(
        cells,
        active_cell_limit=active_cell_limit,
        beat_index=beat_index,
    )
    out: List[Cell] = []
    for cell in cells:
        if active_ids is not None and cell.cell_id not in active_ids:
            out.append(cell)
            continue
        candidates = [
            other
            for other in grid.candidate_cells(cell, radius)
            if other.cell_id != cell.cell_id and distance_4d(cell, other) <= radius
        ]
        candidates.sort(key=lambda other: distance_4d(cell, other))
        neighbors = candidates[:max_neighbors]
        if not neighbors:
            out.append(cell)
            continue

        role_counts: dict[str, int] = {}
        energy_sum = 0.0
        thought_sims: List[float] = []
        worldview_sims: List[float] = []
        aligned: List[Cell] = []
        conflicted: List[Cell] = []
        for n in neighbors:
            role = n.role_label or n.role_key or "agent"
            role_counts[role] = role_counts.get(role, 0) + 1
            energy_sum += float(n.energy)
            thought_sim = cosine_similarity(cell.thought_vec, n.thought_vec)
            worldview_sim = cosine_similarity(cell.worldview_vec, n.worldview_vec)
            thought_sims.append(thought_sim)
            worldview_sims.append(worldview_sim)
            if thought_sim >= THOUGHT_ALIGNMENT_THRESHOLD or worldview_sim >= WORLDVIEW_ALIGNMENT_THRESHOLD:
                aligned.append(n)
            elif thought_sim < 0.0 or worldview_sim < -0.05:
                conflicted.append(n)

        if aligned and conflicted:
            alignment = "mixed"
        elif aligned:
            alignment = "ally"
        elif conflicted:
            alignment = "tension"
        else:
            alignment = "neutral"
        avg_thought = float(sum(thought_sims) / max(1, len(thought_sims)))
        avg_worldview = float(sum(worldview_sims) / max(1, len(worldview_sims)))
        avg_energy = energy_sum / len(neighbors)
        cluster_signal = (
            "ideological_tension"
            if min(avg_thought, avg_worldview) < -0.05
            else "cooperative_cluster"
            if max(avg_thought, avg_worldview) >= 0.28
            else "ambient_contact"
        )
        quality_score = max(
            0.1,
            min(
                0.95,
                0.34
                + abs(avg_thought) * 0.18
                + abs(avg_worldview) * 0.22
                + min(0.16, len(neighbors) * 0.035)
                + (0.12 if alignment in {"mixed", "tension"} else 0.06 if alignment == "ally" else 0.0),
            ),
        )

        thought_vec = cell.thought_vec
        worldview_vec = cell.worldview_vec
        if aligned:
            thought_vec = _blend_unit(cell.thought_vec, np.mean([n.thought_vec for n in aligned], axis=0), 0.045)
            worldview_vec = _blend_unit(cell.worldview_vec, np.mean([n.worldview_vec for n in aligned], axis=0), 0.025)
        elif conflicted:
            thought_vec = _blend_unit(cell.thought_vec, -np.mean([n.thought_vec for n in conflicted], axis=0), 0.035)

        roles = ", ".join(f"{role}:{count}" for role, count in sorted(role_counts.items()))
        primary_neighbor = aligned[0] if aligned else conflicted[0] if conflicted else neighbors[0]
        micro_utterance = _micro_consultation_summary(
            source=cell,
            target=primary_neighbor,
            alignment=alignment,
            cluster_signal=cluster_signal,
        )
        summary = (
            f"t={t_label} social_observation neighbors={len(neighbors)} roles=[{roles}] "
            f"avg_neighbor_energy={avg_energy:.1f} alignment={alignment} "
            f"cluster_signal={cluster_signal} quality={quality_score:.2f} utterance={micro_utterance}"
        )
        behavior_log = list(cell.behavior_log)
        behavior_log.append(
            {
                "t": float(current_t),
                "event_type": "social_observation",
                "source": "engine.lightweight_consultations",
                "summary": summary,
                "quality_score": round(quality_score, 4),
                "payload": {
                    "neighbor_ids": [n.cell_id for n in neighbors],
                    "alignment": alignment,
                    "cluster_signal": cluster_signal,
                    "thought_similarity": round(avg_thought, 4),
                    "worldview_similarity": round(avg_worldview, 4),
                    "quality_score": round(quality_score, 4),
                    "belief_shift": round(abs(avg_thought - avg_worldview) * 0.12, 4),
                    "belief_polarity": "converging" if alignment == "ally" else "diverging" if alignment == "tension" else "mixed",
                    "micro_utterance": micro_utterance,
                    "primary_target_id": primary_neighbor.cell_id,
                    "primary_target_label": _agent_label(primary_neighbor),
                    "consultation_intensity": round(quality_score, 4),
                },
            }
        )
        action_state = dict(cell.action_state)
        action_state["last_consultation_t"] = float(current_t)
        action_state["last_consultation_neighbors"] = len(neighbors)
        action_state["last_consultation_alignment"] = alignment
        action_state["last_consultation_quality"] = round(quality_score, 4)
        action_state["last_consultation_summary"] = micro_utterance
        action_state["last_consultation_target"] = _agent_label(primary_neighbor)
        out.append(
            cell.copy(
                thought_vec=thought_vec,
                worldview_vec=worldview_vec,
                action_state=action_state,
                behavior_log=behavior_log[-40:],
            )
        )
    return out


def _active_consultation_ids(
    cells: List[Cell],
    *,
    active_cell_limit: int | None,
    beat_index: int,
) -> set[str] | None:
    """Pick a deterministic active subset for a micro-round.

    MiroFish/OASIS-style simulations feel fast because each round activates a
    slice of agents instead of forcing every actor to deliberate every beat.
    End4D keeps that performance shape, but scores activity from the 4D social
    field: pressure, decision influence, mobility, and local density.
    """
    if active_cell_limit is None or active_cell_limit <= 0 or active_cell_limit >= len(cells):
        return None
    ranked: list[tuple[float, str]] = []
    for cell in cells:
        action = dict(cell.action_state or {})
        pressure = float(action.get("collective_pressure", 0.0) or 0.0)
        decision = float(action.get("decision_pressure_delta", 0.0) or 0.0)
        mobility = float(action.get("mobility_bias", 0.45) or 0.45)
        policy = float(action.get("policy_sensitivity", 0.45) or 0.45)
        density = float(action.get("local_density", 0.0) or 0.0)
        fracture = 0.18 if bool(action.get("fracture_signal_received")) else 0.0
        phase = _stable_phase(cell.cell_id, beat_index)
        score = (
            pressure * 0.34
            + decision * 0.28
            + mobility * 0.12
            + policy * 0.10
            + min(1.0, density) * 0.08
            + fracture
            + phase * 0.16
        )
        ranked.append((score, cell.cell_id))
    ranked.sort(reverse=True)
    return {cell_id for _, cell_id in ranked[: max(1, active_cell_limit)]}


def _stable_phase(cell_id: str, beat_index: int) -> float:
    seed = sum((idx + 1) * ord(ch) for idx, ch in enumerate(str(cell_id)))
    value = (seed + beat_index * 131) % 997
    return value / 997.0


def _micro_consultation_summary(
    *,
    source: Cell,
    target: Cell,
    alignment: str,
    cluster_signal: str,
) -> str:
    source_label = _agent_label(source)
    target_label = _agent_label(target)
    topic = _consultation_topic(source)
    if alignment == "ally":
        verb = "같은 방향의 단서를 확인하며 다음 접촉을 넓힌다"
    elif alignment == "tension":
        verb = "강한 이견을 듣고 자기 입장을 다시 세운다"
    elif alignment == "mixed":
        verb = "공감과 불신이 섞인 반응을 주고받는다"
    else:
        verb = "짧게 말을 걸고 주변 반응을 살핀다"
    signal = f" ({cluster_signal})" if cluster_signal and cluster_signal != "ambient_contact" else ""
    return _compact_text(f"{source_label} → {target_label}: {topic} 이야기를 꺼내고, {verb}{signal}.", 150)


def _consultation_topic(cell: Cell) -> str:
    action = dict(cell.action_state or {})
    for key in ("last_action_summary", "last_thought_summary", "strategy_summary", "persona_prior_summary"):
        value = str(action.get(key) or "").strip()
        if value and value not in {"persona_seeded_initial_state", "adaptive planning", "current_state_reflection"}:
            return _compact_text(value, 38)
    attrs = dict(cell.persona_attrs or {})
    for key in ("motive", "goal", "identity_summary", "occupation", "persona_summary"):
        value = str(attrs.get(key) or "").strip()
        if value:
            return _compact_text(value, 38)
    return _compact_text(str(cell.role_label or cell.role_key or "현재 국면"), 38)


def _agent_label(cell: Cell) -> str:
    attrs = dict(cell.persona_attrs or {})
    name = str(attrs.get("agent_name") or attrs.get("display_name") or attrs.get("name") or "").strip()
    role = str(cell.role_label or cell.role_key or "agent").strip()
    if name:
        return name if role and role in name else f"{name}({role})"
    return role or str(cell.cell_id or "agent")


def _compact_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _format_t_label(current_t: float) -> str:
    if abs(float(current_t) - int(current_t)) < 1e-6:
        return str(int(current_t))
    return f"{float(current_t):.2f}".rstrip("0").rstrip(".")
