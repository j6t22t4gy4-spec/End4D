"""In-memory Swarm V2 session registry.

This keeps Swarm V2 isolated from the legacy world store while we iterate on
the new streaming-first runtime path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from app.core.scenario_compiler import prepare_swarm_v2_scenario
from app.core.settings import get_state_dir
from app.swarm_v2.runtime import create_streaming_session_seed, run_session


@dataclass
class SwarmV2Session:
    session_id: str
    created_at: str
    result: dict[str, Any]
    pace_ms: int = 0
    cursor: int = 0


class SwarmV2SessionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: dict[str, SwarmV2Session] = {}

    def create(
        self,
        *,
        prompt: str,
        agent_count: int,
        rounds: int,
        events_per_round: int,
        zone_count: int,
        pace_ms: int,
        llm_mode: str,
        llm_sample_size: int,
        llm_parallelism: int = 4,
    ) -> SwarmV2Session:
        scenario = prepare_swarm_v2_scenario(prompt)
        result = create_streaming_session_seed(
            prompt=str(scenario.get("scenario_prompt") or prompt),
            agent_count=agent_count,
            rounds=rounds,
            events_per_round=events_per_round,
            zone_count=zone_count,
            llm_mode=llm_mode,
            llm_sample_size=llm_sample_size,
            llm_parallelism=llm_parallelism,
            scenario_roles=list(scenario.get("scenario_actor_roles") or []),
            scenario_zones=list(scenario.get("scenario_initial_zones") or []),
        )
        result["raw_prompt"] = scenario.get("raw_prompt") or prompt
        result["scenario"] = scenario
        result["summary"] = {
            **dict(result.get("summary") or {}),
            "scenario_director_mode": scenario.get("scenario_director_mode"),
            "scenario_director_fallback_reason": scenario.get("scenario_director_fallback_reason"),
            "scenario_actor_roles": scenario.get("scenario_actor_roles"),
            "scenario_initial_zones": scenario.get("scenario_initial_zones"),
        }
        session = SwarmV2Session(
            session_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            result=result,
            pace_ms=max(0, min(250, int(pace_ms))),
        )
        with self._lock:
            self._sessions[session.session_id] = session
            self._trim_locked(max_sessions=24)
        self._persist(session)
        return session

    def persist(self, session: SwarmV2Session) -> None:
        with self._lock:
            self._sessions[session.session_id] = session
        self._persist(session)

    def get(self, session_id: str) -> SwarmV2Session | None:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is not None:
            return session
        loaded = self._load(session_id)
        if loaded is not None:
            with self._lock:
                self._sessions[loaded.session_id] = loaded
        return loaded

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        sessions: dict[str, SwarmV2Session] = {}
        with self._lock:
            sessions.update(self._sessions)
        for path in self._session_dir().glob("*.json"):
            session_id = path.stem
            if session_id in sessions:
                continue
            loaded = self._load(session_id)
            if loaded is not None:
                sessions[loaded.session_id] = loaded
        items = [self._summary(session) for session in sessions.values()]
        items.sort(key=lambda item: str(item.get("created_at") or ""), reverse=True)
        return items[: max(1, min(100, int(limit)))]

    def set_cursor(self, session_id: str, cursor: int) -> None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.cursor = max(0, int(cursor))

    def _trim_locked(self, *, max_sessions: int) -> None:
        overflow = len(self._sessions) - max_sessions
        if overflow <= 0:
            return
        oldest = sorted(self._sessions.values(), key=lambda item: item.created_at)[:overflow]
        for session in oldest:
            self._sessions.pop(session.session_id, None)

    def _session_dir(self) -> Path:
        path = get_state_dir().parent / "swarm_v2_sessions"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _session_path(self, session_id: str) -> Path:
        safe = "".join(ch for ch in session_id if ch.isalnum() or ch in "-_")
        return self._session_dir() / f"{safe}.json"

    def _persist(self, session: SwarmV2Session) -> None:
        path = self._session_path(session.session_id)
        payload = {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "pace_ms": session.pace_ms,
            "cursor": session.cursor,
            "result": session.result,
        }
        tmp = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _load(self, session_id: str) -> SwarmV2Session | None:
        path = self._session_path(session_id)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return None
        return SwarmV2Session(
            session_id=str(payload.get("session_id") or session_id),
            created_at=str(payload.get("created_at") or ""),
            result=dict(payload.get("result") or {}),
            pace_ms=int(payload.get("pace_ms") or 12),
            cursor=int(payload.get("cursor") or 0),
        )

    def _summary(self, session: SwarmV2Session) -> dict[str, Any]:
        result = dict(session.result or {})
        summary = dict(result.get("summary") or {})
        return {
            "session_id": session.session_id,
            "created_at": session.created_at,
            "runtime": str(result.get("runtime") or "swarm-v2-cleanroom"),
            "raw_prompt": str(result.get("raw_prompt") or ""),
            "prompt": str(result.get("prompt") or ""),
            "agent_count": int(result.get("agent_count") or 0),
            "rounds": int(result.get("rounds") or 0),
            "events_per_round": int(result.get("events_per_round") or 0),
            "zone_count": int(result.get("zone_count") or 0),
            "pace_ms": session.pace_ms,
            "llm_mode": str(result.get("llm_mode") or "packet"),
            "llm_parallelism": int(result.get("llm_parallelism") or 1),
            "event_count": int(summary.get("expected_event_count") or len(result.get("events") or [])),
            "summary": {
                "avg_pressure": summary.get("avg_pressure"),
                "max_pressure": summary.get("max_pressure"),
                "outcome": summary.get("outcome"),
                "llm": summary.get("llm"),
                "scenario_director_mode": summary.get("scenario_director_mode"),
                "scenario_director_fallback_reason": summary.get("scenario_director_fallback_reason"),
            },
        }


swarm_v2_sessions = SwarmV2SessionStore()
