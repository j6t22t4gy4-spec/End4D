"""Session API for grouping world runs like a thread."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.session_store import session_store
from app.core.store import world_store

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    title: str = Field(default="", max_length=200)


class UpdateSessionRequest(BaseModel):
    title: str = Field(default="", max_length=200)


class SessionWorldSummary(BaseModel):
    world_id: str
    status: str
    created_at: str = ""
    genesis_prompt: Optional[str] = None
    persona_country: str = ""
    config_version: str = ""
    session_id: str = ""


class SessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    world_count: int
    latest_world_id: str = ""
    worlds: List[SessionWorldSummary] = Field(default_factory=list)


def _world_summary(world_id: str) -> Optional[Dict[str, Any]]:
    entry = world_store.get(world_id)
    if entry is None:
        return None
    world = entry["world"]
    return {
        "world_id": world_id,
        "status": str(entry.get("status") or "idle"),
        "created_at": world.created_at.isoformat() if world.created_at else "",
        "genesis_prompt": entry.get("genesis_prompt"),
        "persona_country": str(entry.get("persona_country") or ""),
        "config_version": str(entry.get("config_version") or ""),
        "session_id": str(entry.get("session_id") or ""),
    }


def _session_response(item: Dict[str, Any]) -> SessionResponse:
    world_ids = list(item.get("world_ids") or [])
    worlds = [summary for wid in reversed(world_ids) if (summary := _world_summary(wid))]
    return SessionResponse(
        session_id=str(item.get("session_id") or ""),
        title=str(item.get("title") or "Untitled Session"),
        created_at=str(item.get("created_at") or ""),
        updated_at=str(item.get("updated_at") or ""),
        world_count=len(world_ids),
        latest_world_id=str(item.get("latest_world_id") or ""),
        worlds=[SessionWorldSummary(**world) for world in worlds],
    )


@router.post("", response_model=SessionResponse)
def create_session(body: CreateSessionRequest):
    session = session_store.create(title=body.title)
    return _session_response(session)


@router.get("", response_model=List[SessionResponse])
def list_sessions():
    return [_session_response(item) for item in session_store.list_sessions()]


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_response(session)


@router.patch("/{session_id}", response_model=SessionResponse)
def update_session(session_id: str, body: UpdateSessionRequest):
    session = session_store.rename(session_id, body.title)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_response(session)


@router.delete("/{session_id}")
def delete_session(session_id: str):
    session = session_store.delete(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "deleted": True}
