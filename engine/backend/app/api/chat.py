"""Conversational world chat APIs."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.store import world_store
from app.llm.facade import llm_facade
from app.models.cell import Cell

router = APIRouter(prefix="/worlds", tags=["chat"])

ChatTargetType = Literal["world", "role", "zone", "agent"]


class ChatContext(BaseModel):
    t: Optional[float] = None
    target_type: ChatTargetType = "world"
    cell_id: Optional[str] = None
    role_key: Optional[str] = None
    zone_id: Optional[str] = None


class WorldChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=800)
    session_id: Optional[str] = None
    context: ChatContext = Field(default_factory=ChatContext)


class ChatGroundingItem(BaseModel):
    anchor_id: str
    kind: str
    label: str
    reason: str = ""
    t: Optional[float] = None
    cell_id: Optional[str] = None
    role_key: Optional[str] = None
    zone_id: Optional[str] = None


class WorldChatResponse(BaseModel):
    world_id: str
    session_id: str
    message_id: str
    question: str
    answer: str
    evidence: List[str] = Field(default_factory=list)
    follow_up: List[str] = Field(default_factory=list)
    confidence_notes: List[str] = Field(default_factory=list)
    mode: str
    context: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    grounding: Dict[str, List[ChatGroundingItem]] = Field(default_factory=dict)
    citations: List[ChatGroundingItem] = Field(default_factory=list)
    chat_meta: Dict[str, Any] = Field(default_factory=dict)


@router.post("/{world_id}/chat", response_model=WorldChatResponse)
def post_world_chat(world_id: str, body: WorldChatRequest):
    entry = world_store.get(world_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="World not found")
    store = entry.get("snapshot_store")
    if store is None:
        raise HTTPException(status_code=404, detail="Snapshot store not found")
    available_t = store.list_t()
    if not available_t:
        raise HTTPException(status_code=404, detail="No snapshot available")

    requested_t = body.context.t
    resolved_t = float(requested_t) if requested_t is not None else float(available_t[-1])
    snap = store.get(resolved_t) or store.get_nearest(resolved_t)
    if snap is None:
        raise HTTPException(status_code=404, detail="No snapshot available")

    context = body.context.model_dump()
    context["requested_t"] = requested_t
    context["resolved_t"] = float(snap.t)
    target_cells = _select_cells(list(snap.cells), body.context)
    if body.context.target_type != "world" and not target_cells:
        raise HTTPException(status_code=404, detail="No cells match chat context")
    if body.context.target_type == "world":
        target_cells = _representative_cells(list(snap.cells), limit=8)

    payload = _build_chat_payload(
        world_id=world_id,
        entry=entry,
        context=context,
        cells=list(snap.cells),
        target_cells=target_cells,
        scene_events=[dict(item) for item in getattr(snap, "scene_events", [])],
        question=body.question,
    )
    try:
        result = llm_facade.chat_world(payload, question=body.question)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"chat_runtime_error:{exc}") from exc

    answer = dict(result.get("query") or {})
    session_id = str(body.session_id or uuid.uuid4())
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    context_payload = dict(payload.get("chat_context") or {})
    world_store.append_chat_message(
        world_id,
        session_id=session_id,
        context=context_payload,
        message={
            "message_id": f"{message_id}:user",
            "role": "user",
            "content": body.question,
            "created_at": now,
            "context": context_payload,
        },
    )
    world_store.append_chat_message(
        world_id,
        session_id=session_id,
        context=context_payload,
        message={
            "message_id": message_id,
            "role": "assistant",
            "content": str(answer.get("answer") or ""),
            "created_at": now,
            "context": context_payload,
            "metadata": dict(payload.get("metadata") or {}),
        },
    )

    grounding = _response_grounding(payload)
    return WorldChatResponse(
        world_id=world_id,
        session_id=session_id,
        message_id=message_id,
        question=body.question,
        answer=str(answer.get("answer") or ""),
        evidence=[str(item) for item in list(answer.get("evidence") or [])],
        follow_up=[str(item) for item in list(answer.get("follow_up") or [])],
        confidence_notes=[str(item) for item in list(answer.get("confidence_notes") or [])],
        mode=str(result.get("mode") or "heuristic"),
        context=context_payload,
        metadata=dict(payload.get("metadata") or {}),
        grounding=grounding,
        citations=_citations_from_ids(grounding, [str(item) for item in list(answer.get("citations") or [])]),
        chat_meta={
            "prompt_version": str(result.get("prompt_version") or ""),
            "prompt_meta": dict(result.get("prompt_meta") or {}),
            "provider": str(result.get("provider") or ""),
            "model": str(result.get("model") or ""),
            "fallback_reason": str(result.get("fallback_reason") or ""),
        },
    )


def _select_cells(cells: List[Cell], context: ChatContext) -> List[Cell]:
    if context.target_type == "agent" and context.cell_id:
        return [cell for cell in cells if cell.cell_id == context.cell_id]
    if context.target_type == "role" and context.role_key:
        key = str(context.role_key)
        return [cell for cell in cells if cell.role_key == key or cell.role_label == key]
    if context.target_type == "zone" and context.zone_id:
        key = str(context.zone_id)
        return [cell for cell in cells if cell.zone_id == key or cell.zone_label == key]
    return list(cells)


def _representative_cells(cells: List[Cell], limit: int) -> List[Cell]:
    return sorted(cells, key=lambda cell: (-float(cell.energy), str(cell.cell_id)))[:limit]


def _build_chat_payload(
    *,
    world_id: str,
    entry: Dict[str, Any],
    context: Dict[str, Any],
    cells: List[Cell],
    target_cells: List[Cell],
    scene_events: List[Dict[str, Any]],
    question: str,
) -> Dict[str, Any]:
    world = entry.get("world")
    target_label = _target_label(context, target_cells)
    personas = [_persona_row(cell, index=index) for index, cell in enumerate(target_cells[:8])]
    events = [_event_row(event, index=index, t=float(context.get("resolved_t") or 0.0)) for index, event in enumerate(scene_events[:10])]
    snapshot = {
        "anchor_id": f"snapshot:{world_id}:t:{float(context.get('resolved_t') or 0.0):g}",
        "world_id": world_id,
        "t": float(context.get("resolved_t") or 0.0),
        "requested_t": context.get("requested_t"),
        "cell_count": len(cells),
        "target_cell_count": len(target_cells),
        "avg_energy": round(sum(float(cell.energy) for cell in target_cells) / max(1, len(target_cells)), 4),
        "avg_z": round(sum(float(cell.z) for cell in target_cells) / max(1, len(target_cells)), 4),
    }
    grounding = {
        "snapshot": [
            {
                "anchor_id": snapshot["anchor_id"],
                "kind": "snapshot",
                "label": f"t={snapshot['t']:g}",
                "reason": f"{snapshot['target_cell_count']} target cells from {snapshot['cell_count']} snapshot cells",
                "t": snapshot["t"],
            }
        ],
        "personas": personas,
        "events": events,
    }
    metadata = {
        "snapshot": snapshot,
        "persona": [
            {key: row.get(key) for key in ("anchor_id", "cell_id", "label", "role_key", "role_label", "zone_id", "zone_label", "persona_id")}
            for row in personas
        ],
        "events": [
            {key: row.get(key) for key in ("anchor_id", "label", "scene_type", "interaction_type", "t")}
            for row in events
        ],
    }
    return {
        "chat_context": {
            **context,
            "target_label": target_label,
            "question": question,
        },
        "world": {
            "world_id": world_id,
            "t_max": float(getattr(world, "t_max", 0.0)),
            "genesis_prompt": str(entry.get("genesis_prompt") or ""),
            "genesis_rationale": str(entry.get("genesis_rationale") or ""),
            "role_catalog": list(entry.get("role_catalog") or []),
            "t_step_semantic": str(getattr(world, "t_step_semantic", "")),
            "simulation_mode": str(dict(entry.get("engine_params") or {}).get("simulation_mode") or "precision"),
        },
        "snapshot": snapshot,
        "target": {
            "type": str(context.get("target_type") or "world"),
            "label": target_label,
            "cell_count": len(target_cells),
        },
        "personas": personas,
        "events": events,
        "group_state": dict(entry.get("group_state") or {}),
        "metadata": metadata,
        "grounding": grounding,
    }


def _persona_row(cell: Cell, *, index: int) -> Dict[str, Any]:
    attrs = dict(cell.persona_attrs or {})
    name = _first_text(attrs.get("agent_name"), attrs.get("display_name"), attrs.get("name"), cell.persona_id, f"agent-{index + 1}")
    label = f"{name}({cell.role_label or cell.role_key or 'agent'})"
    recent_memory = [
        str(item.get("summary") or "")
        for item in (list(cell.short_memory or [])[-2:] + list(cell.long_memory or [])[-2:])
        if str(item.get("summary") or "").strip()
    ]
    recent_behavior = [
        str(item.get("summary") or item.get("event_type") or "")
        for item in list(cell.behavior_log or [])[-3:]
        if str(item.get("summary") or item.get("event_type") or "").strip()
    ]
    return {
        "anchor_id": f"persona:{cell.cell_id}",
        "kind": "persona",
        "label": label,
        "reason": str(attrs.get("identity_summary") or cell.persona_text or "")[:240],
        "t": float(cell.t),
        "cell_id": cell.cell_id,
        "role_key": cell.role_key,
        "role_label": cell.role_label,
        "zone_id": cell.zone_id,
        "zone_label": cell.zone_label,
        "persona_id": cell.persona_id,
        "persona_text": str(cell.persona_text or "")[:500],
        "persona_attrs": attrs,
        "energy": round(float(cell.energy), 4),
        "z": round(float(cell.z), 4),
        "recent_memory": recent_memory,
        "recent_behavior": recent_behavior,
        "action_state": {
            key: cell.action_state.get(key)
            for key in ("last_thought_summary", "last_action_summary", "strategy_summary", "observer_focus")
            if key in cell.action_state
        },
    }


def _event_row(event: Dict[str, Any], *, index: int, t: float) -> Dict[str, Any]:
    scene_id = str(event.get("scene_id") or f"event-{index}")
    return {
        "anchor_id": f"event:{scene_id}",
        "kind": "event",
        "label": str(event.get("summary") or event.get("scene_type") or scene_id)[:120],
        "reason": str(event.get("narrative_reason") or event.get("scenario_relevance") or ""),
        "t": float(event.get("t") or event.get("scene_t") or t),
        "scene_type": str(event.get("scene_type") or ""),
        "interaction_type": str(event.get("interaction_type") or ""),
        "source_id": str(event.get("source_id") or ""),
        "target_ids": [str(item) for item in list(event.get("target_ids") or [])],
        "summary": str(event.get("summary") or ""),
        "narrative_reason": str(event.get("narrative_reason") or ""),
        "scenario_relevance": str(event.get("scenario_relevance") or ""),
    }


def _target_label(context: Dict[str, Any], cells: List[Cell]) -> str:
    target_type = str(context.get("target_type") or "world")
    if target_type == "agent" and cells:
        return _persona_row(cells[0], index=0)["label"]
    if target_type == "role":
        return str(context.get("role_key") or (cells[0].role_label if cells else "") or "role")
    if target_type == "zone":
        return str(context.get("zone_id") or (cells[0].zone_label if cells else "") or "zone")
    return "world"


def _response_grounding(payload: Dict[str, Any]) -> Dict[str, List[ChatGroundingItem]]:
    return {
        key: [
            ChatGroundingItem(
                anchor_id=str(item.get("anchor_id") or ""),
                kind=str(item.get("kind") or key[:-1] or "evidence"),
                label=str(item.get("label") or "evidence"),
                reason=str(item.get("reason") or ""),
                t=float(item.get("t")) if item.get("t") is not None else None,
                cell_id=str(item.get("cell_id")) if item.get("cell_id") is not None else None,
                role_key=str(item.get("role_key")) if item.get("role_key") is not None else None,
                zone_id=str(item.get("zone_id")) if item.get("zone_id") is not None else None,
            )
            for item in list(value or [])
        ]
        for key, value in dict(payload.get("grounding") or {}).items()
    }


def _citations_from_ids(grounding: Dict[str, List[ChatGroundingItem]], anchor_ids: List[str]) -> List[ChatGroundingItem]:
    index = {item.anchor_id: item for rows in grounding.values() for item in rows}
    out: List[ChatGroundingItem] = []
    for anchor_id in anchor_ids[:6]:
        item = index.get(anchor_id)
        if item is not None:
            out.append(item)
    return out


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""
