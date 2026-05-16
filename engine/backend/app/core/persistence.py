"""Local file persistence bridge for world state."""
from __future__ import annotations

import json
from pathlib import Path
import uuid
from typing import Dict, List, Optional, Protocol

from app.core.storage_manifest import unwrap_payload, wrap_payload
from app.core.serialization import snapshot_from_dict, world_entry_to_dict, world_from_dict


class WorldPersistenceBackend(Protocol):
    def list_world_ids(self) -> List[str]:
        ...

    def save(self, world_id: str, entry: Dict) -> None:
        ...

    def load(self, world_id: str) -> Optional[Dict]:
        ...

    def delete(self, world_id: str) -> None:
        ...


class DiskWorldPersistence:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, world_id: str) -> Path:
        return self.base_dir / f"{world_id}.json"

    def list_world_ids(self) -> List[str]:
        return sorted(path.stem for path in self.base_dir.glob("*.json"))

    def save(self, world_id: str, entry: Dict) -> None:
        path = self._path(world_id)
        payload = world_entry_to_dict(entry)
        envelope = wrap_payload(payload)
        tmp_path = path.with_name(f".{path.stem}.{uuid.uuid4().hex}.json.tmp")
        tmp_path.write_text(
            json.dumps(envelope, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        tmp_path.replace(path)

    def load(self, world_id: str) -> Optional[Dict]:
        path = self._path(world_id)
        if not path.exists():
            return None
        payload = unwrap_payload(json.loads(path.read_text(encoding="utf-8")))
        return {
            "world": world_from_dict(payload.get("world") or {}),
            "status": str(payload.get("status") or "idle"),
            "initial_cell_count": int(payload.get("initial_cell_count", 0)),
            "genesis_prompt": payload.get("genesis_prompt"),
            "genesis_rationale": payload.get("genesis_rationale"),
            "role_catalog": list(payload.get("role_catalog") or []),
            "persona_country": str(payload.get("persona_country") or ""),
            "persona_source": str(payload.get("persona_source") or ""),
            "persona_catalog": list(payload.get("persona_catalog") or []),
            "engine_params": dict(payload.get("engine_params") or {}),
            "simulation_config": dict(payload.get("simulation_config") or {}),
            "config_version": str(payload.get("config_version") or ""),
            "comparison_meta": dict(payload.get("comparison_meta") or {}),
            "session_id": str(payload.get("session_id") or ""),
            "coalition_state": {
                str(role): dict(state)
                for role, state in dict(payload.get("coalition_state") or {}).items()
            },
            "coalition_history": [dict(item) for item in list(payload.get("coalition_history") or [])],
            "group_state": dict(payload.get("group_state") or {}),
            "review_cache": dict(payload.get("review_cache") or {}),
            "chat_sessions": {
                str(key): dict(value)
                for key, value in dict(payload.get("chat_sessions") or {}).items()
            },
            "action_ledger": [dict(item) for item in list(payload.get("action_ledger") or [])],
            "snapshot_index": list(payload.get("snapshot_index") or []),
            "snapshot_archive": dict(payload.get("snapshot_archive") or {}),
            "snapshots": [snapshot_from_dict(item) for item in payload.get("snapshots") or []],
        }

    def delete(self, world_id: str) -> None:
        path = self._path(world_id)
        if path.exists():
            path.unlink()
