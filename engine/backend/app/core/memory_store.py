"""Structured memory and behavior log helpers."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.cell import Cell

SHORT_MEMORY_LIMIT = 48
LONG_MEMORY_LIMIT = 80
BEHAVIOR_LOG_LIMIT = 160
LONG_TERM_IMPORTANCE_THRESHOLD = 0.72


def _trim_records(records: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    if len(records) <= limit:
        return records
    return records[-limit:]


def memory_entry(
    *,
    t: float,
    kind: str,
    summary: str,
    importance: float,
    source: str,
    payload: Optional[Dict[str, Any]] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "t": float(t),
        "kind": kind,
        "summary": summary,
        "importance": max(0.0, min(1.0, float(importance))),
        "source": source,
        "payload": dict(payload or {}),
        "tags": list(tags or []),
    }


def behavior_event(
    *,
    t: float,
    event_type: str,
    source: str,
    summary: str,
    quality_score: float,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": "behavior-log/v1",
        "t": float(t),
        "event_type": event_type,
        "source": source,
        "summary": summary,
        "quality_score": max(0.0, min(1.0, float(quality_score))),
        "payload": dict(payload or {}),
    }


def flatten_memory(short_memory: List[Dict[str, Any]], long_memory: List[Dict[str, Any]]) -> List[str]:
    ordered = sorted(
        [dict(item) for item in long_memory] + [dict(item) for item in short_memory],
        key=lambda item: (float(item.get("t", 0.0)), float(item.get("importance", 0.0))),
    )
    return [str(item.get("summary") or "") for item in ordered if str(item.get("summary") or "").strip()]


def append_memory(
    cell: Cell,
    entry: Dict[str, Any],
    *,
    behavior: Optional[Dict[str, Any]] = None,
    promote: Optional[bool] = None,
) -> Cell:
    to_long = bool(promote) if promote is not None else float(entry.get("importance", 0.0)) >= LONG_TERM_IMPORTANCE_THRESHOLD
    short_memory = list(cell.short_memory)
    long_memory = list(cell.long_memory)
    if to_long:
        long_memory.append(dict(entry))
    else:
        short_memory.append(dict(entry))

    behavior_log = list(cell.behavior_log)
    if behavior is not None:
        behavior_log.append(dict(behavior))

    short_memory = _trim_records(short_memory, SHORT_MEMORY_LIMIT)
    long_memory = _trim_records(long_memory, LONG_MEMORY_LIMIT)
    behavior_log = _trim_records(behavior_log, BEHAVIOR_LOG_LIMIT)
    memory = flatten_memory(short_memory, long_memory)
    return cell.copy(
        short_memory=short_memory,
        long_memory=long_memory,
        behavior_log=behavior_log,
        memory=memory,
    )


def merge_memory_fields(c1: Cell, c2: Cell) -> Dict[str, List[Dict[str, Any]] | List[str]]:
    short_memory = _trim_records(
        [dict(item) for item in c1.short_memory] + [dict(item) for item in c2.short_memory],
        SHORT_MEMORY_LIMIT,
    )
    long_memory = _trim_records(
        [dict(item) for item in c1.long_memory] + [dict(item) for item in c2.long_memory],
        LONG_MEMORY_LIMIT,
    )
    behavior_log = _trim_records(
        [dict(item) for item in c1.behavior_log] + [dict(item) for item in c2.behavior_log],
        BEHAVIOR_LOG_LIMIT,
    )
    return {
        "short_memory": short_memory,
        "long_memory": long_memory,
        "behavior_log": behavior_log,
        "memory": flatten_memory(short_memory, long_memory),
    }


def seed_memory_from_text(cell: Cell, text: str, *, source: str = "persona_seed") -> Cell:
    text = text.strip()
    if not text:
        return cell
    entry = memory_entry(
        t=float(cell.t),
        kind="persona_seed",
        summary=text,
        importance=0.92,
        source=source,
        payload={"persona_id": cell.persona_id, "role": cell.role_label or cell.role_key},
        tags=["seed", "persona"],
    )
    behavior = behavior_event(
        t=float(cell.t),
        event_type="persona_seed",
        source=source,
        summary=text,
        quality_score=0.92,
        payload={"persona_id": cell.persona_id},
    )
    return append_memory(cell, entry, behavior=behavior, promote=True)
