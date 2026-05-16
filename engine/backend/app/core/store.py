"""Organic4D Engine — 월드 저장소 (Phase 3.1.1).

world_id → {World, SnapshotStore, 실행 상태} 매핑
ARCHITECTURE_CHECKLIST 1.3: 엔진 격리는 world_id 기준
"""
from __future__ import annotations

from typing import Dict, Optional
import uuid

from app.core.config_versions import build_simulation_config, simulation_config_version
from app.core.persistence import DiskWorldPersistence, WorldPersistenceBackend
from app.core.session_store import session_store
from app.core.settings import get_persistence_backend, get_state_dir
from app.core.snapshot import SnapshotStore
from app.models.world import World


class WorldStore:
    """월드 저장소. 기본은 disk+memory cache."""

    def __init__(self):
        self._worlds: Dict[str, dict] = {}
        backend = get_persistence_backend()
        self._persistence: Optional[WorldPersistenceBackend] = (
            DiskWorldPersistence(get_state_dir()) if backend == "disk" else None
        )
        self._preload()

    def _preload(self) -> None:
        if self._persistence is None:
            return
        for world_id in self._persistence.list_world_ids():
            self._load_from_persistence(world_id)

    def _make_snapshot_store(self, world_id: str) -> SnapshotStore:
        return SnapshotStore(
            world_id=world_id,
            on_change=lambda wid=world_id: self._persist(wid),
        )

    def _persist(self, world_id: str) -> None:
        if self._persistence is None:
            return
        entry = self._worlds.get(world_id)
        if entry is None:
            return
        self._persistence.save(world_id, entry)

    def _load_from_persistence(self, world_id: str) -> Optional[dict]:
        if self._persistence is None:
            return None
        payload = self._persistence.load(world_id)
        if payload is None:
            return None
        store = self._make_snapshot_store(world_id)
        store.load_snapshots(
            payload.pop("snapshots", []),
            snapshot_index=payload.pop("snapshot_index", []),
            archived_t=(payload.pop("snapshot_archive", {}) or {}).get("archived_t", []),
        )
        entry = {**payload, "snapshot_store": store}
        self._worlds[world_id] = entry
        return entry

    def create(
        self,
        t_max: float,
        initial_cell_count: int = 5,
        world_id: Optional[str] = None,
        genesis_prompt: Optional[str] = None,
        genesis_rationale: Optional[str] = None,
        role_catalog: Optional[list] = None,
        t_step_semantic: str = "1 스텝 ≈ 1일 (기본)",
        t_step_unit: str = "day",
        nutrient_per_step: float = 1.0,
        persona_country: str = "",
        persona_source: str = "",
        persona_catalog: Optional[list] = None,
        engine_params: Optional[dict] = None,
        simulation_config: Optional[dict] = None,
        config_version: str = "",
        comparison_meta: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """월드 생성. world_id 반환."""
        wid = world_id or str(uuid.uuid4())
        store = self._make_snapshot_store(wid)
        world = World(
            world_id=wid,
            t_max=t_max,
            initial_cells=[],  # cells는 run 시 생성
            nutrients=[],
            t_step_semantic=t_step_semantic,
            t_step_unit=t_step_unit,
            nutrient_per_step=float(nutrient_per_step),
        )
        params = dict(engine_params or {})
        config = simulation_config or build_simulation_config(
            t_max=float(t_max),
            initial_cell_count=int(initial_cell_count),
            role_catalog=list(role_catalog) if role_catalog else ["agent"],
            t_step_semantic=t_step_semantic,
            t_step_unit=t_step_unit,
            nutrient_per_step=float(nutrient_per_step),
            persona_country=persona_country,
            persona_source=persona_source,
            engine_params=params,
            comparison_meta=dict(comparison_meta or {}),
        )
        version = config_version or simulation_config_version(config)
        session = session_store.ensure(
            session_id,
            title=(genesis_prompt or "").strip()[:80],
        )
        self._worlds[wid] = {
            "world": world,
            "snapshot_store": store,
            "status": "idle",
            "initial_cell_count": initial_cell_count,
            "genesis_prompt": genesis_prompt,
            "genesis_rationale": genesis_rationale,
            "role_catalog": list(role_catalog) if role_catalog else ["agent"],
            "persona_country": persona_country,
            "persona_source": persona_source,
            "persona_catalog": list(persona_catalog or []),
            "engine_params": params,
            "simulation_config": dict(config),
            "config_version": version,
            "comparison_meta": dict(comparison_meta or {}),
            "session_id": str(session.get("session_id") or ""),
            "coalition_state": {},
            "coalition_history": [],
            "group_state": {},
            "review_cache": {},
            "chat_sessions": {},
            "stop_requested": False,
            "action_ledger": [],
        }
        session_store.attach_world(str(session.get("session_id") or ""), wid)
        self._persist(wid)
        return wid

    def get(self, world_id: str) -> Optional[dict]:
        """월드 정보 조회."""
        if world_id not in self._worlds:
            self._load_from_persistence(world_id)
        return self._worlds.get(world_id)

    def delete(self, world_id: str) -> bool:
        """월드를 메모리/디스크/세션 참조에서 제거한다."""
        entry = self.get(world_id)
        if entry is None:
            return False
        session_id = str(entry.get("session_id") or "")
        if session_id:
            session_store.detach_world(session_id, world_id)
        self._worlds.pop(world_id, None)
        if self._persistence is not None:
            self._persistence.delete(world_id)
        return True

    def get_world(self, world_id: str) -> Optional[World]:
        """World 객체 조회."""
        entry = self._worlds.get(world_id)
        return entry["world"] if entry else None

    def get_snapshot_store(self, world_id: str) -> Optional[SnapshotStore]:
        """SnapshotStore 조회."""
        entry = self._worlds.get(world_id)
        return entry["snapshot_store"] if entry else None

    def set_status(self, world_id: str, status: str) -> None:
        """실행 상태 설정 (idle, running, done)."""
        if world_id in self._worlds:
            self._worlds[world_id]["status"] = status
            self._persist(world_id)

    def request_stop(self, world_id: str) -> None:
        if world_id in self._worlds:
            self._worlds[world_id]["stop_requested"] = True
            self._persist(world_id)

    def clear_stop_request(self, world_id: str) -> None:
        if world_id in self._worlds:
            self._worlds[world_id]["stop_requested"] = False
            self._persist(world_id)

    def is_stop_requested(self, world_id: str) -> bool:
        entry = self.get(world_id)
        return bool(entry and entry.get("stop_requested"))

    def update_coalition_state(
        self,
        world_id: str,
        *,
        coalition_state: Optional[dict] = None,
        coalition_history: Optional[list] = None,
    ) -> None:
        if world_id not in self._worlds:
            return
        if coalition_state is not None:
            self._worlds[world_id]["coalition_state"] = {
                str(role): dict(payload)
                for role, payload in dict(coalition_state).items()
            }
        if coalition_history is not None:
            self._worlds[world_id]["coalition_history"] = [dict(item) for item in list(coalition_history)]
        self._persist(world_id)

    def update_group_state(self, world_id: str, *, group_state: Optional[dict] = None) -> None:
        if world_id not in self._worlds or group_state is None:
            return
        self._worlds[world_id]["group_state"] = dict(group_state)
        self._persist(world_id)

    def reset_action_ledger(self, world_id: str) -> None:
        if world_id in self._worlds:
            self._worlds[world_id]["action_ledger"] = []
            self._persist(world_id)

    def append_action_record(self, world_id: str, record: dict, *, max_records: int = 2000) -> dict:
        entry = self.get(world_id)
        if entry is None:
            return {}
        ledger = [dict(item) for item in list(entry.get("action_ledger") or [])]
        item = dict(record or {})
        if not item:
            return {}
        ledger.append(item)
        if len(ledger) > max_records:
            ledger = ledger[-max_records:]
        entry["action_ledger"] = ledger
        # Persist less aggressively than snapshots: action records are compact,
        # but saving every single live beat can still dominate local runs.
        if len(ledger) <= 1 or len(ledger) % 100 == 0:
            self._persist(world_id)
        return item

    def get_recent_action_records(self, world_id: str, *, limit: int = 50) -> list:
        entry = self.get(world_id)
        if entry is None:
            return []
        rows = [dict(item) for item in list(entry.get("action_ledger") or [])]
        return rows[-max(0, int(limit)):]

    def update_runtime_config(
        self,
        world_id: str,
        *,
        engine_params: Optional[dict] = None,
        role_catalog: Optional[list] = None,
        initial_cell_count: Optional[int] = None,
    ) -> None:
        if world_id not in self._worlds:
            return
        entry = self._worlds[world_id]
        if engine_params is not None:
            params = dict(engine_params)
            entry["engine_params"] = params
            config = dict(entry.get("simulation_config") or {})
            config["engine_params"] = params
            config["scenario_prompt"] = str(params.get("scenario_prompt") or config.get("scenario_prompt") or "")
            config["scenario_quality"] = dict(params.get("scenario_quality") or config.get("scenario_quality") or {})
            entry["simulation_config"] = config
        if role_catalog is not None:
            roles = [str(role).strip() for role in list(role_catalog or []) if str(role).strip()]
            if roles:
                entry["role_catalog"] = roles
                config = dict(entry.get("simulation_config") or {})
                config["role_catalog"] = roles
                entry["simulation_config"] = config
        if initial_cell_count is not None:
            count = max(6, int(initial_cell_count))
            entry["initial_cell_count"] = count
            config = dict(entry.get("simulation_config") or {})
            config["initial_cell_count"] = count
            entry["simulation_config"] = config
        self._persist(world_id)

    def get_review_cache(self, world_id: str) -> dict:
        entry = self.get(world_id)
        if entry is None:
            return {}
        return dict(entry.get("review_cache") or {})

    def update_review_cache(self, world_id: str, *, review_cache: Optional[dict] = None) -> None:
        if world_id not in self._worlds or review_cache is None:
            return
        self._worlds[world_id]["review_cache"] = dict(review_cache)
        self._persist(world_id)

    def append_chat_message(
        self,
        world_id: str,
        *,
        session_id: str,
        message: dict,
        context: Optional[dict] = None,
    ) -> dict:
        entry = self.get(world_id)
        if entry is None:
            return {}
        sessions = dict(entry.get("chat_sessions") or {})
        session = dict(sessions.get(session_id) or {})
        messages = [dict(item) for item in list(session.get("messages") or [])]
        messages.append(dict(message))
        session.update(
            {
                "session_id": session_id,
                "world_id": world_id,
                "context": dict(context or session.get("context") or {}),
                "messages": messages,
                "created_at": str(session.get("created_at") or message.get("created_at") or ""),
                "updated_at": str(message.get("created_at") or ""),
            }
        )
        sessions[session_id] = session
        entry["chat_sessions"] = sessions
        self._persist(world_id)
        return session

    def get_initial_cell_count(self, world_id: str) -> int:
        """초기 세포 수."""
        entry = self._worlds.get(world_id)
        return entry.get("initial_cell_count", 5) if entry else 5

    def get_role_catalog(self, world_id: str) -> list:
        """세계별 역할 카탈로그 (초기 세포에 순환 부여)."""
        entry = self._worlds.get(world_id)
        if not entry:
            return ["agent"]
        return list(entry.get("role_catalog") or ["agent"])

    def get_nutrient_per_step(self, world_id: str) -> float:
        """Genesis가 정한 스텝당 영양 유입 (성장·에너지)."""
        w = self.get_world(world_id)
        if w is None:
            return 1.0
        return float(w.nutrient_per_step)

    def get_persona_catalog(self, world_id: str) -> list:
        """세계별 초기 페르소나 seed 목록."""
        entry = self._worlds.get(world_id)
        if not entry:
            return []
        return list(entry.get("persona_catalog") or [])

    def get_engine_params(self, world_id: str) -> dict:
        entry = self._worlds.get(world_id)
        if not entry:
            return {}
        params = entry.get("engine_params")
        if params is not None:
            return dict(params)
        config = dict(entry.get("simulation_config") or {})
        return dict(config.get("engine_params") or {})

    def clone_from_snapshot(
        self,
        source_world_id: str,
        *,
        snapshot_t: float,
        world_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a new world entry that starts from a stored snapshot."""
        source = self.get(source_world_id)
        if source is None:
            return None
        source_store = source["snapshot_store"]
        snap = source_store.get(snapshot_t)
        if snap is None:
            return None

        new_world_id = self.create(
            t_max=float(source["world"].t_max),
            initial_cell_count=len(snap.cells),
            world_id=world_id,
            genesis_prompt=source.get("genesis_prompt"),
            genesis_rationale=source.get("genesis_rationale"),
            role_catalog=list(source.get("role_catalog") or []),
            t_step_semantic=source["world"].t_step_semantic,
            t_step_unit=source["world"].t_step_unit,
            nutrient_per_step=float(source["world"].nutrient_per_step),
            persona_country=str(source.get("persona_country") or ""),
            persona_source=str(source.get("persona_source") or ""),
            persona_catalog=list(source.get("persona_catalog") or []),
            engine_params=dict(source.get("engine_params") or {}),
            simulation_config=dict(source.get("simulation_config") or {}),
            config_version=str(source.get("config_version") or ""),
            comparison_meta={
                "parent_world_id": source_world_id,
                "restored_from_t": float(snapshot_t),
                "mode": "fork",
                "baseline_config_version": str(source.get("config_version") or ""),
            },
            session_id=str(source.get("session_id") or ""),
        )
        new_entry = self.get(new_world_id)
        if new_entry is None:
            return None
        new_entry["coalition_state"] = {
            str(role): dict(payload)
            for role, payload in dict(source.get("coalition_state") or {}).items()
        }
        new_entry["coalition_history"] = [dict(item) for item in list(source.get("coalition_history") or [])]
        new_entry["group_state"] = dict(source.get("group_state") or {})
        new_entry["snapshot_store"].save(float(snapshot_t), [c.copy() for c in snap.cells])
        self._persist(new_world_id)
        return new_world_id


# 전역 싱글톤 (엔진 격리는 world_id로)
world_store = WorldStore()
