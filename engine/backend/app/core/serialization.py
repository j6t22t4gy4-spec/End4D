"""Serialization helpers for world, snapshot, and cell persistence."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import numpy as np

from app.models.cell import Cell
from app.models.world import NutrientEvent, Snapshot, World


def _dt_to_str(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _dt_from_str(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def cell_to_dict(cell: Cell) -> Dict[str, Any]:
    return {
        "cell_id": cell.cell_id,
        "x": float(cell.x),
        "y": float(cell.y),
        "z": float(cell.z),
        "t": float(cell.t),
        "energy": float(cell.energy),
        "gene_vec": cell.gene_vec.tolist(),
        "memory": list(cell.memory),
        "short_memory": [dict(item) for item in cell.short_memory],
        "long_memory": [dict(item) for item in cell.long_memory],
        "behavior_log": [dict(item) for item in cell.behavior_log],
        "action_state": dict(cell.action_state),
        "relationship_state": {
            str(peer_id): dict(state)
            for peer_id, state in cell.relationship_state.items()
        },
        "emotion_vec": cell.emotion_vec.tolist(),
        "thought_vec": cell.thought_vec.tolist(),
        "worldview_vec": cell.worldview_vec.tolist(),
        "role_key": cell.role_key,
        "role_label": cell.role_label,
        "persona_id": cell.persona_id,
        "persona_text": cell.persona_text,
        "persona_country": cell.persona_country,
        "persona_attrs": dict(cell.persona_attrs),
        "zone_id": cell.zone_id,
        "zone_label": cell.zone_label,
        "zone_influence": float(cell.zone_influence),
        "zone_friction": float(cell.zone_friction),
    }


def cell_from_dict(data: Dict[str, Any]) -> Cell:
    return Cell(
        cell_id=str(data.get("cell_id") or ""),
        x=float(data.get("x", 0.0)),
        y=float(data.get("y", 0.0)),
        z=float(data.get("z", 0.0)),
        t=float(data.get("t", 0.0)),
        energy=float(data.get("energy", 0.0)),
        gene_vec=np.asarray(data.get("gene_vec") or [], dtype=np.float32),
        memory=list(data.get("memory") or []),
        short_memory=[dict(item) for item in data.get("short_memory") or []],
        long_memory=[dict(item) for item in data.get("long_memory") or []],
        behavior_log=[dict(item) for item in data.get("behavior_log") or []],
        action_state=dict(data.get("action_state") or {}),
        relationship_state={
            str(peer_id): dict(state)
            for peer_id, state in (data.get("relationship_state") or {}).items()
        },
        emotion_vec=np.asarray(data.get("emotion_vec") or [], dtype=np.float32),
        thought_vec=np.asarray(data.get("thought_vec") or [], dtype=np.float32),
        worldview_vec=np.asarray(data.get("worldview_vec") or [], dtype=np.float32),
        role_key=str(data.get("role_key") or "agent"),
        role_label=str(data.get("role_label") or ""),
        persona_id=str(data.get("persona_id") or ""),
        persona_text=str(data.get("persona_text") or ""),
        persona_country=str(data.get("persona_country") or ""),
        persona_attrs=dict(data.get("persona_attrs") or {}),
        zone_id=str(data.get("zone_id") or "zone-0"),
        zone_label=str(data.get("zone_label") or "Zone 0"),
        zone_influence=float(data.get("zone_influence", 1.0)),
        zone_friction=float(data.get("zone_friction", 0.0)),
    )


def snapshot_to_dict(snapshot: Snapshot) -> Dict[str, Any]:
    return {
        "world_id": snapshot.world_id,
        "t": float(snapshot.t),
        "created_at": _dt_to_str(snapshot.created_at),
        "cells": [cell_to_dict(cell) for cell in snapshot.cells],
        "scene_events": [dict(item) for item in getattr(snapshot, "scene_events", [])],
        "scene_metrics": dict(getattr(snapshot, "scene_metrics", {}) or {}),
    }


def snapshot_from_dict(data: Dict[str, Any]) -> Snapshot:
    return Snapshot(
        world_id=str(data.get("world_id") or ""),
        t=float(data.get("t", 0.0)),
        cells=[cell_from_dict(item) for item in data.get("cells") or []],
        scene_events=[dict(item) for item in data.get("scene_events") or []],
        scene_metrics=dict(data.get("scene_metrics") or {}),
        created_at=_dt_from_str(data.get("created_at")),
    )


def nutrient_event_to_dict(event: NutrientEvent) -> Dict[str, Any]:
    return {
        "t": float(event.t),
        "event_type": event.event_type,
        "payload": dict(event.payload),
    }


def nutrient_event_from_dict(data: Dict[str, Any]) -> NutrientEvent:
    return NutrientEvent(
        t=float(data.get("t", 0.0)),
        event_type=str(data.get("event_type") or ""),
        payload=dict(data.get("payload") or {}),
    )


def world_to_dict(world: World) -> Dict[str, Any]:
    return {
        "world_id": world.world_id,
        "t_max": float(world.t_max),
        "created_at": _dt_to_str(world.created_at),
        "initial_cells": [cell_to_dict(cell) for cell in world.initial_cells],
        "nutrients": [nutrient_event_to_dict(event) for event in world.nutrients],
        "t_step_semantic": world.t_step_semantic,
        "t_step_unit": world.t_step_unit,
        "nutrient_per_step": float(world.nutrient_per_step),
    }


def world_from_dict(data: Dict[str, Any]) -> World:
    return World(
        world_id=str(data.get("world_id") or ""),
        t_max=float(data.get("t_max", 0.0)),
        initial_cells=[cell_from_dict(item) for item in data.get("initial_cells") or []],
        nutrients=[nutrient_event_from_dict(item) for item in data.get("nutrients") or []],
        created_at=_dt_from_str(data.get("created_at")),
        t_step_semantic=str(data.get("t_step_semantic") or "1 스텝 ≈ 1일 (기본)"),
        t_step_unit=str(data.get("t_step_unit") or "day"),
        nutrient_per_step=float(data.get("nutrient_per_step", 1.0)),
    )


def world_entry_to_dict(entry: Dict[str, Any]) -> Dict[str, Any]:
    store = entry["snapshot_store"]
    return {
        "world": world_to_dict(entry["world"]),
        "status": str(entry.get("status") or "idle"),
        "initial_cell_count": int(entry.get("initial_cell_count", 0)),
        "genesis_prompt": entry.get("genesis_prompt"),
        "genesis_rationale": entry.get("genesis_rationale"),
        "role_catalog": list(entry.get("role_catalog") or []),
        "persona_country": str(entry.get("persona_country") or ""),
        "persona_source": str(entry.get("persona_source") or ""),
        "persona_catalog": list(entry.get("persona_catalog") or []),
        "engine_params": dict(entry.get("engine_params") or {}),
        "simulation_config": dict(entry.get("simulation_config") or {}),
        "config_version": str(entry.get("config_version") or ""),
        "comparison_meta": dict(entry.get("comparison_meta") or {}),
        "session_id": str(entry.get("session_id") or ""),
        "coalition_state": {
            str(role): dict(payload)
            for role, payload in dict(entry.get("coalition_state") or {}).items()
        },
        "coalition_history": [dict(item) for item in list(entry.get("coalition_history") or [])],
        "group_state": dict(entry.get("group_state") or {}),
        "review_cache": dict(entry.get("review_cache") or {}),
        "snapshot_index": store.snapshot_index(),
        "snapshot_archive": store.archive_summary(),
        "snapshots": [snapshot_to_dict(store.get(t)) for t in store.list_t() if store.get(t) is not None],
    }
