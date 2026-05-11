"""Structured review payload builders for post-simulation analysis."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from app.models.cell import Cell
from app.models.world import Snapshot


def build_world_review_payload(entry: dict[str, Any]) -> dict[str, Any]:
    world = entry["world"]
    store = entry["snapshot_store"]
    available_t = list(store.list_t())
    if not available_t:
        raise ValueError("No snapshots available")

    first = store.get(available_t[0])
    latest = store.get(available_t[-1])
    if first is None or latest is None:
        raise ValueError("Snapshot data incomplete")

    timeline_points = [_timeline_point(store.get(t)) for t in available_t if store.get(t) is not None]
    stance_groups = _build_stance_groups(latest)
    zone_z = _zone_z_summary(latest)
    top_z_agents = _top_agent_z_shift(first, latest)
    highlights = _build_highlights(
        first=first,
        latest=latest,
        stance_groups=stance_groups,
        zone_z=zone_z,
        top_z_agents=top_z_agents,
    )

    return {
        "world_id": str(world.world_id),
        "timeline": {
            "first_t": float(first.t),
            "last_t": float(latest.t),
            "points_count": len(timeline_points),
            "points": timeline_points,
            "outcome": _classify_outcome(timeline_points),
        },
        "world_meta": {
            "genesis_prompt": str(entry.get("genesis_prompt") or ""),
            "persona_country": str(entry.get("persona_country") or ""),
            "config_version": str(entry.get("config_version") or ""),
            "session_id": str(entry.get("session_id") or ""),
            "role_catalog": list(entry.get("role_catalog") or []),
            "engine_params": dict(entry.get("engine_params") or {}),
        },
        "policy_events": [_event_summary(event) for event in list(world.nutrients or [])[-8:]],
        "coalitions": {
            "active": dict(entry.get("coalition_state") or {}),
            "history_tail": [dict(item) for item in list(entry.get("coalition_history") or [])[-8:]],
        },
        "metrics": {
            "initial_cell_count": len(first.cells),
            "final_cell_count": len(latest.cells),
            "cell_delta": len(latest.cells) - len(first.cells),
            "initial_total_energy": _total_energy(first.cells),
            "final_total_energy": _total_energy(latest.cells),
            "energy_delta": _total_energy(latest.cells) - _total_energy(first.cells),
            "initial_avg_z": _avg_z(first.cells),
            "final_avg_z": _avg_z(latest.cells),
            "z_delta": _avg_z(latest.cells) - _avg_z(first.cells),
        },
        "stance_summary": {
            "overall_signal": _overall_signal(stance_groups),
            "groups": stance_groups,
        },
        "zone_z_summary": zone_z,
        "top_z_movers": top_z_agents,
        "highlights": highlights,
        "annotation_candidates": build_timeline_annotation_candidates(timeline_points),
    }


def build_timeline_annotation_candidates(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(points) < 2:
        return []
    deltas: list[dict[str, Any]] = []
    max_cell_delta = max(abs(points[i]["cell_count"] - points[i - 1]["cell_count"]) for i in range(1, len(points))) or 1
    max_energy_delta = max(abs(points[i]["total_energy"] - points[i - 1]["total_energy"]) for i in range(1, len(points))) or 1.0
    for i in range(1, len(points)):
        prev = points[i - 1]
        current = points[i]
        cell_delta = current["cell_count"] - prev["cell_count"]
        energy_delta = current["total_energy"] - prev["total_energy"]
        score = abs(cell_delta) / max_cell_delta + abs(energy_delta) / max_energy_delta
        label = "stability shift"
        if cell_delta > 0 and energy_delta > 0:
            label = "growth surge"
        elif cell_delta < 0 and energy_delta < 0:
            label = "contraction shock"
        elif abs(energy_delta) >= abs(cell_delta):
            label = "energy inflection"
        deltas.append(
            {
                "t": float(current["t"]),
                "score": round(float(score), 3),
                "label": label,
                "reason": f"cells {cell_delta:+d}, energy {energy_delta:+.2f}",
            }
        )
    deltas.sort(key=lambda item: (-item["score"], item["t"]))
    return deltas[:5]


def _timeline_point(snapshot: Snapshot | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    return {
        "t": float(snapshot.t),
        "cell_count": len(snapshot.cells),
        "total_energy": _total_energy(snapshot.cells),
        "avg_z": _avg_z(snapshot.cells),
    }


def _build_stance_groups(snapshot: Snapshot) -> list[dict[str, Any]]:
    grouped: dict[str, list[Cell]] = defaultdict(list)
    for cell in snapshot.cells:
        role_key = (cell.role_key or "agent").strip() or "agent"
        role_label = (cell.role_label or role_key).strip() or role_key
        grouped[f"{role_key}:{role_label}"].append(cell)

    groups: list[dict[str, Any]] = []
    for group_id, cells in grouped.items():
        role_label = (cells[0].role_label or cells[0].role_key or "agent").strip() or "agent"
        qualities = [
            float(item.get("quality_score", 0.0))
            for cell in cells
            for item in cell.behavior_log[-16:]
            if item.get("event_type") in {"social_observation", "agent_dialogue", "group_deliberation"}
        ]
        tensions = [
            float(item.get("tension", 0.0))
            for cell in cells
            for item in cell.relationship_state.values()
        ]
        trusts = [
            float(item.get("trust", 0.0))
            for cell in cells
            for item in cell.relationship_state.values()
        ]
        cohesion = float(np.mean(qualities)) if qualities else 0.0
        if trusts:
            cohesion = min(1.0, cohesion * 0.65 + float(np.mean(trusts)) * 0.35)
        tension = float(np.mean(tensions)) if tensions else 0.0
        stance = "diffuse"
        if cohesion >= 0.72 and tension < 0.2:
            stance = "cohesive"
        elif tension >= 0.35:
            stance = "contested"
        elif cohesion >= 0.5:
            stance = "emergent"
        groups.append(
            {
                "group_id": group_id,
                "role_label": role_label,
                "cell_count": len(cells),
                "avg_energy": round(sum(float(cell.energy) for cell in cells) / max(len(cells), 1), 3),
                "avg_z": round(_avg_z(cells), 3),
                "cohesion_score": round(cohesion, 3),
                "tension_score": round(tension, 3),
                "stance": stance,
            }
        )
    groups.sort(key=lambda item: (-item["cell_count"], item["role_label"]))
    return groups


def _overall_signal(groups: list[dict[str, Any]]) -> str:
    if not groups:
        return "no_signal"
    if any(group["stance"] == "contested" for group in groups):
        return "contested"
    if any(group["stance"] == "cohesive" for group in groups):
        return "clustered"
    return "diffuse"


def _zone_z_summary(snapshot: Snapshot) -> list[dict[str, Any]]:
    zones: dict[str, dict[str, Any]] = {}
    for cell in snapshot.cells:
        zone_id = str(getattr(cell, "zone_id", "") or "unassigned")
        zone_label = str(getattr(cell, "zone_label", "") or zone_id)
        bucket = zones.setdefault(
            zone_id,
            {"zone_id": zone_id, "zone_label": zone_label, "z": [], "energy": [], "count": 0},
        )
        bucket["z"].append(float(getattr(cell, "z", 0.0)))
        bucket["energy"].append(float(cell.energy))
        bucket["count"] += 1
    rows = []
    for payload in zones.values():
        rows.append(
            {
                "zone_id": payload["zone_id"],
                "zone_label": payload["zone_label"],
                "cell_count": int(payload["count"]),
                "avg_z": round(float(np.mean(payload["z"])) if payload["z"] else 0.0, 3),
                "avg_energy": round(float(np.mean(payload["energy"])) if payload["energy"] else 0.0, 3),
            }
        )
    rows.sort(key=lambda item: (-item["avg_z"], item["zone_label"]))
    return rows[:8]


def _top_agent_z_shift(first: Snapshot, latest: Snapshot) -> list[dict[str, Any]]:
    first_index = {cell.cell_id: cell for cell in first.cells}
    movers: list[dict[str, Any]] = []
    for cell in latest.cells:
        prev = first_index.get(cell.cell_id)
        if prev is None:
            continue
        delta = float(getattr(cell, "z", 0.0)) - float(getattr(prev, "z", 0.0))
        movers.append(
            {
                "cell_id": cell.cell_id,
                "role_label": str(cell.role_label or cell.role_key or "agent"),
                "persona_country": str(cell.persona_country or ""),
                "z_delta": round(delta, 3),
                "final_z": round(float(getattr(cell, "z", 0.0)), 3),
            }
        )
    movers.sort(key=lambda item: abs(float(item["z_delta"])), reverse=True)
    return movers[:5]


def _build_highlights(
    *,
    first: Snapshot,
    latest: Snapshot,
    stance_groups: list[dict[str, Any]],
    zone_z: list[dict[str, Any]],
    top_z_agents: list[dict[str, Any]],
) -> list[str]:
    lines = [
        f"cells moved from {len(first.cells)} to {len(latest.cells)} across t={float(first.t):.0f}→{float(latest.t):.0f}",
        f"social elevation average shifted by {_avg_z(latest.cells) - _avg_z(first.cells):+.2f}",
    ]
    if stance_groups:
        top = stance_groups[0]
        lines.append(
            f"largest group is {top['role_label']} with stance={top['stance']} cohesion={top['cohesion_score']:.2f}"
        )
    contested = next((group for group in stance_groups if group["stance"] == "contested"), None)
    if contested:
        lines.append(
            f"contested pressure is strongest in {contested['role_label']} tension={contested['tension_score']:.2f}"
        )
    if zone_z:
        lines.append(f"highest elevation zone is {zone_z[0]['zone_label']} avg_z={zone_z[0]['avg_z']:.2f}")
    if top_z_agents:
        mover = top_z_agents[0]
        lines.append(f"largest individual elevation shift is {mover['role_label']} {mover['z_delta']:+.2f}")
    return lines[:5]


def _event_summary(event: Any) -> dict[str, Any]:
    payload = dict(getattr(event, "payload", {}) or {})
    return {
        "t": float(getattr(event, "t", 0.0)),
        "event_type": str(getattr(event, "event_type", "")),
        "name": str(payload.get("name") or payload.get("summary") or payload.get("label") or "event"),
        "target_roles": list(payload.get("target_roles") or []),
        "target_zones": list(payload.get("target_zones") or []),
        "duration_steps": int(payload.get("duration_steps") or 0),
    }


def _classify_outcome(points: list[dict[str, Any]]) -> str:
    if not points:
        return "not_started"
    first = points[0]
    last = points[-1]
    if last["cell_count"] == 0:
        return "extinct"
    if last["cell_count"] >= max(first["cell_count"] * 1.5, first["cell_count"] + 3):
        return "expanding"
    if last["cell_count"] <= first["cell_count"] * 0.6:
        return "contracting"
    if last["total_energy"] > first["total_energy"] * 1.25:
        return "energy_accumulating"
    if last["total_energy"] < first["total_energy"] * 0.75:
        return "energy_depleted"
    return "stable"


def _total_energy(cells: list[Cell]) -> float:
    return round(sum(float(cell.energy) for cell in cells), 3)


def _avg_z(cells: list[Cell]) -> float:
    if not cells:
        return 0.0
    return round(sum(float(getattr(cell, "z", 0.0)) for cell in cells) / len(cells), 3)
