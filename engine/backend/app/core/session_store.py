"""Thread-like session store for grouping world runs."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.settings import get_persistence_backend, get_state_dir


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


class SessionStore:
    def __init__(self):
        self._sessions: Dict[str, Dict[str, Any]] = {}
        backend = get_persistence_backend()
        self._path = Path(get_state_dir()) / "_sessions.json" if backend == "disk" else None
        self._load()

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        sessions = payload.get("sessions") or []
        for item in sessions:
            sid = str(item.get("session_id") or "")
            if sid:
                self._sessions[sid] = {
                    "session_id": sid,
                    "title": str(item.get("title") or "Untitled Session"),
                    "created_at": str(item.get("created_at") or _now_iso()),
                    "updated_at": str(item.get("updated_at") or item.get("created_at") or _now_iso()),
                    "world_ids": list(item.get("world_ids") or []),
                    "latest_world_id": str(item.get("latest_world_id") or ""),
                }

    def _persist(self) -> None:
        if self._path is None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "sessions": sorted(
                self._sessions.values(),
                key=lambda item: str(item.get("updated_at") or ""),
                reverse=True,
            )
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    def create(self, title: str = "") -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        now = _now_iso()
        entry = {
            "session_id": session_id,
            "title": title.strip() or f"Session {now[:16].replace('T', ' ')}",
            "created_at": now,
            "updated_at": now,
            "world_ids": [],
            "latest_world_id": "",
        }
        self._sessions[session_id] = entry
        self._persist()
        return dict(entry)

    def ensure(self, session_id: Optional[str], title: str = "") -> Dict[str, Any]:
        if session_id and session_id in self._sessions:
            return dict(self._sessions[session_id])
        return self.create(title=title)

    def attach_world(self, session_id: str, world_id: str) -> None:
        entry = self._sessions.get(session_id)
        if entry is None:
            entry = self.create()
            session_id = str(entry["session_id"])
            entry = self._sessions[session_id]
        world_ids = list(entry.get("world_ids") or [])
        if world_id not in world_ids:
            world_ids.append(world_id)
        entry["world_ids"] = world_ids
        entry["latest_world_id"] = world_id
        entry["updated_at"] = _now_iso()
        self._persist()

    def detach_world(self, session_id: str, world_id: str) -> Optional[Dict[str, Any]]:
        entry = self._sessions.get(session_id)
        if entry is None:
            return None
        world_ids = [wid for wid in list(entry.get("world_ids") or []) if wid != world_id]
        entry["world_ids"] = world_ids
        entry["latest_world_id"] = world_ids[-1] if world_ids else ""
        entry["updated_at"] = _now_iso()
        self._persist()
        return dict(entry)

    def rename(self, session_id: str, title: str) -> Optional[Dict[str, Any]]:
        entry = self._sessions.get(session_id)
        if entry is None:
            return None
        cleaned = title.strip()
        if not cleaned:
            cleaned = f"Session {str(entry.get('created_at') or _now_iso())[:16].replace('T', ' ')}"
        entry["title"] = cleaned
        entry["updated_at"] = _now_iso()
        self._persist()
        return dict(entry)

    def delete(self, session_id: str) -> Optional[Dict[str, Any]]:
        entry = self._sessions.pop(session_id, None)
        if entry is None:
            return None
        self._persist()
        return dict(entry)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [
            dict(item)
            for item in sorted(
                self._sessions.values(),
                key=lambda item: str(item.get("updated_at") or ""),
                reverse=True,
            )
        ]

    def get(self, session_id: str) -> Optional[Dict[str, Any]]:
        entry = self._sessions.get(session_id)
        return dict(entry) if entry else None


session_store = SessionStore()
