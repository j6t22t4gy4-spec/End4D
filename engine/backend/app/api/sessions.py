"""Session API for grouping world runs like a thread."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.review_payloads import build_session_review_payload
from app.core.session_store import session_store
from app.core.store import world_store
from app.llm.facade import llm_facade

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


class SessionReviewResponse(BaseModel):
    session_id: str
    title: str
    headline: str
    summary: str
    review_mode: str
    key_findings: List[str] = Field(default_factory=list)
    decision_implications: List[str] = Field(default_factory=list)
    objective_explanation: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)
    strongest_worlds: List[Dict[str, Any]] = Field(default_factory=list)
    ranked_worlds: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_pairs: List[Dict[str, Any]] = Field(default_factory=list)
    grounding: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    citations: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    review_meta: Dict[str, Any] = Field(default_factory=dict)


class SessionReviewQueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class SessionReviewQueryResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    evidence: List[str] = Field(default_factory=list)
    follow_up: List[str] = Field(default_factory=list)
    confidence_notes: List[str] = Field(default_factory=list)
    mode: str
    grounding: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict)
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    review_meta: Dict[str, Any] = Field(default_factory=dict)


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


@router.get("/{session_id}/review", response_model=SessionReviewResponse)
def get_session_review(
    session_id: str,
    objective: str = Query("balanced", description="balanced | stability | cohesion | polarization | fracture"),
):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    world_entries = [world_store.get(wid) for wid in list(session.get("world_ids") or [])]
    try:
        payload = build_session_review_payload(session, [entry for entry in world_entries if entry is not None], objective=objective)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    summary = llm_facade.summarize_session_review(payload)
    return SessionReviewResponse(
        session_id=str(session.get("session_id") or ""),
        title=str(session.get("title") or "Session"),
        headline=str(summary["summary"].get("headline") or ""),
        summary=str(summary["summary"].get("executive_summary") or ""),
        review_mode=str(summary["mode"]),
        key_findings=[str(item) for item in list(summary["summary"].get("key_findings") or [])],
        decision_implications=[str(item) for item in list(summary["summary"].get("decision_implications") or [])],
        objective_explanation=str(
            (summary.get("summary") or {}).get("objective_explanation")
            or payload.get("objective_explanation")
            or ""
        ),
        metrics=dict(payload.get("summary_stats") or {}),
        strongest_worlds=[dict(item) for item in list(payload.get("strongest_worlds") or [])],
        ranked_worlds=[dict(item) for item in list(payload.get("ranked_worlds") or [])],
        recommended_pairs=[dict(item) for item in list(payload.get("recommended_pairs") or [])],
        grounding={key: [dict(item) for item in list(value or [])] for key, value in dict(payload.get("grounding") or {}).items()},
        citations=_session_citations(payload, dict((summary.get("summary") or {}).get("citations") or {})),
        review_meta={
            "summary": {
                "prompt_version": str(summary.get("prompt_version") or ""),
                "prompt_meta": dict(summary.get("prompt_meta") or {}),
                "provider": str(summary.get("provider") or ""),
                "model": str(summary.get("model") or ""),
                "fallback_reason": str(summary.get("fallback_reason") or ""),
            }
        },
    )


@router.post("/{session_id}/review/query", response_model=SessionReviewQueryResponse)
def post_session_review_query(session_id: str, body: SessionReviewQueryRequest):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    world_entries = [world_store.get(wid) for wid in list(session.get("world_ids") or [])]
    try:
        payload = build_session_review_payload(session, [entry for entry in world_entries if entry is not None])
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    query = llm_facade.query_session_review(payload, question=body.question)
    answer = dict(query.get("query") or {})
    return SessionReviewQueryResponse(
        session_id=str(session.get("session_id") or ""),
        question=body.question,
        answer=str(answer.get("answer") or ""),
        evidence=[str(item) for item in list(answer.get("evidence") or [])],
        follow_up=[str(item) for item in list(answer.get("follow_up") or [])],
        confidence_notes=[str(item) for item in list(answer.get("confidence_notes") or [])],
        mode=str(query.get("mode") or "heuristic"),
        grounding={key: [dict(item) for item in list(value or [])] for key, value in dict(payload.get("grounding") or {}).items()},
        citations=_session_query_citations(payload, [str(item) for item in list(answer.get("citations") or [])]),
        review_meta={
            "query": {
                "prompt_version": str(query.get("prompt_version") or ""),
                "prompt_meta": dict(query.get("prompt_meta") or {}),
                "provider": str(query.get("provider") or ""),
                "model": str(query.get("model") or ""),
                "fallback_reason": str(query.get("fallback_reason") or ""),
            }
        },
    )


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


def _session_grounding_index(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for value in dict(payload.get("grounding") or {}).values():
        rows.extend(dict(item) for item in list(value or []))
    return {
        str(item.get("anchor_id") or ""): item
        for item in rows
        if str(item.get("anchor_id") or "").strip()
    }


def _session_query_citations(payload: Dict[str, Any], anchor_ids: List[str]) -> List[Dict[str, Any]]:
    index = _session_grounding_index(payload)
    out: List[Dict[str, Any]] = []
    for anchor_id in anchor_ids[:6]:
        row = index.get(str(anchor_id))
        if row is not None:
            out.append(dict(row))
    return out


def _session_citations(payload: Dict[str, Any], sections: Dict[str, List[str]]) -> Dict[str, List[Dict[str, Any]]]:
    return {
        str(section): _session_query_citations(payload, [str(item) for item in list(anchor_ids or [])])
        for section, anchor_ids in sections.items()
    }
